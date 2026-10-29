"""Clean the RAW synthetic extract.

Principles
  * Detection is independent: this module never reads the injection log.
  * Raw files are only READ. Cleaned tables are written to a different folder.
  * A value is repaired only where a documented rule can recover it exactly (dq_catalog.CATALOG). Otherwise the field is
    left NULL / 'Unknown' (retained) or the record is rejected. Nothing is imputed statistically.
  * Booking-family integrity: if a booking cannot be trusted, the booking, its passengers and its cancellation events are
    all rejected, so the cleaned tables never contain half a booking.
"""
import hashlib

import numpy as np
import pandas as pd

import config as cfg
import dq_catalog as dq

TABLES = ["stations", "routes", "trains", "train_stops", "calendar", "seat_capacity", "train_operations",
          "bookings", "booking_passengers", "cancellations"]
TS_FMT = "%Y-%m-%d %H:%M:%S"
CURRENCY_STRIP = r"(?i)rs\.?|inr|\u20b9|,|\s"


def read_raw(raw_dir=cfg.RAW_DIR):
    return {n: pd.read_csv(raw_dir / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}


def file_checksums(folder, names=TABLES):
    return {n: hashlib.sha256((folder / f"{n}.csv").read_bytes()).hexdigest() for n in names}


def _num(s):
    return pd.to_numeric(s.str.strip().replace("", np.nan), errors="coerce")


def _type_reference(R):
    st = R["stations"].copy()
    st["station_id"] = st["station_id"].astype("int64")
    rt = R["routes"].copy()
    for c in ("route_id", "origin_station_id", "destination_station_id"):
        rt[c] = rt[c].astype("int64")
    rt["distance_km"] = rt["distance_km"].astype(float)
    tr = R["trains"].copy()
    tr["train_id"] = tr["train_id"].astype("int64")
    tr["route_id"] = tr["route_id"].astype("int64")
    sp = R["train_stops"].copy()
    for c in ("train_id", "stop_sequence", "station_id", "day_offset"):
        sp[c] = sp[c].astype("int64")
    sp["distance_from_origin_km"] = sp["distance_from_origin_km"].astype(float)
    for c in ("arrival_time", "departure_time"):
        sp[c] = sp[c].replace("", np.nan)
    cal = R["calendar"].copy()
    for c in ("year", "quarter", "month_number", "week_of_year", "day_of_month", "day_of_week_number", "fiscal_year"):
        cal[c] = cal[c].astype("int64")
    for c in ("is_weekend", "is_holiday", "is_peak_travel_period"):
        cal[c] = cal[c].map({"True": True, "False": False})
    for c in ("holiday_name", "peak_period_name"):
        cal[c] = cal[c].replace("", np.nan)
    cal["calendar_date"] = pd.to_datetime(cal["calendar_date"]).dt.date
    return dict(stations=st, routes=rt, trains=tr, train_stops=sp, calendar=cal)


class Results:
    def __init__(self):
        self.issues = {c: dict(detected=0, corrected=0, retained=0, rejected=0) for c in dq.ORDER}
        self.cascade = {}
        self.anomalies = {}
        self.movement = {}

    def rec(self, code, n, corrected=None, retained=None, rejected=None):
        n = int(n)
        out = dq.CATALOG[code]["outcome"]
        d = self.issues[code]
        d["detected"] = n
        d["corrected"] = n if out == "corrected" and corrected is None else (corrected or 0)
        d["retained"] = n if out == "retained" and retained is None else (retained or 0)
        d["rejected"] = n if out == "rejected" and rejected is None else (rejected or 0)

    def anomaly(self, name, n):
        self.anomalies[name] = int(n)


def clean(raw=None, raw_dir=cfg.RAW_DIR):
    R = raw if raw is not None else read_raw(raw_dir)
    res = Results()
    ref = _type_reference(R)
    for n in ("stations", "routes", "trains", "train_stops", "calendar"):
        res.movement[n] = dict(raw_rows=len(R[n]), clean_rows=len(ref[n]), duplicates=0, orphans=0, family_rejected=0, other=0)
    st_id_of_code = dict(zip(ref["stations"]["station_code"], ref["stations"]["station_id"]))
    route_of_train = dict(zip(ref["trains"]["train_id"], ref["trains"]["route_id"]))
    origin_of_route = dict(zip(ref["routes"]["route_id"], ref["routes"]["origin_station_id"]))
    dest_of_route = dict(zip(ref["routes"]["route_id"], ref["routes"]["destination_station_id"]))

    b, ps, ev = R["bookings"].copy(), R["booking_passengers"].copy(), R["cancellations"].copy()
    mv = {t: dict(raw_rows=len(R[t]), duplicates=0, orphans=0, family_rejected=0, other=0)
          for t in ("bookings", "booking_passengers", "cancellations", "seat_capacity", "train_operations")}

    # ---------------------------------------------------------------- 1. duplicates
    for tbl, df, key, code in (("bookings", b, "booking_id", "dup_booking_rows"),
                               ("booking_passengers", ps, "passenger_id", "dup_passenger_rows"),
                               ("cancellations", ev, "cancellation_id", "dup_cancellation_rows")):
        dup = df.duplicated(key, keep="first")
        res.rec(code, dup.sum())
        res.anomaly(f"{tbl}: duplicate keys that are not exact copies", dup.sum() - df.duplicated(keep="first").sum())
        mv[tbl]["duplicates"] = int(dup.sum())
    b = b[~b.duplicated("booking_id", keep="first")].reset_index(drop=True)
    ps = ps[~ps.duplicated("passenger_id", keep="first")].reset_index(drop=True)
    ev = ev[~ev.duplicated("cancellation_id", keep="first")].reset_index(drop=True)

    # ---------------------------------------------------------------- 2. orphans
    bset = set(b["booking_id"])
    o = ~ps["booking_id"].isin(bset)
    res.rec("orphan_passenger_rows", o.sum()); mv["booking_passengers"]["orphans"] = int(o.sum())
    ps = ps[~o].reset_index(drop=True)
    o = ~ev["booking_id"].isin(bset)
    res.rec("orphan_cancellation_rows", o.sum()); mv["cancellations"]["orphans"] = int(o.sum())
    ev = ev[~o].reset_index(drop=True)

    reject = {}                                         # booking_id -> reason code

    def flag(ids, code):
        for i in ids:
            reject.setdefault(i, code)

    # ---------------------------------------------------------------- 3. booking dates
    jd = b["journey_date"].str.strip()
    is_iso = jd.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    is_dmy = jd.str.fullmatch(r"\d{2}-\d{2}-\d{4}")
    iso_dt = pd.to_datetime(jd.where(is_iso), format="%Y-%m-%d", errors="coerce")
    dmy_dt = pd.to_datetime(jd.where(is_dmy), format="%d-%m-%Y", errors="coerce")
    jdate = iso_dt.fillna(dmy_dt)
    res.rec("journey_date_format", (is_dmy & dmy_dt.notna()).sum())
    imp = jdate.isna()
    res.rec("journey_date_impossible", imp.sum()); flag(b.loc[imp, "booking_id"], "journey_date_impossible")

    bts_raw = b["booking_ts"].str.strip()
    bts = pd.to_datetime(bts_raw.where(bts_raw != ""), format=TS_FMT, errors="coerce")
    miss = bts.isna()
    res.rec("missing_booking_ts", miss.sum()); flag(b.loc[miss, "booking_id"], "missing_booking_ts")
    after = bts.notna() & jdate.notna() & (bts.dt.normalize() > jdate)
    res.rec("booking_after_journey", after.sum()); flag(b.loc[after, "booking_id"], "booking_after_journey")

    # ---------------------------------------------------------------- 4. route and stations
    train_id = pd.to_numeric(b["train_id"])
    route_from_train = train_id.map(route_of_train)
    route_raw = b["route_id"].str.strip()
    miss_route = route_raw == ""
    res.rec("missing_route_id", miss_route.sum())
    route_num = pd.to_numeric(route_raw.where(~miss_route), errors="coerce")
    res.anomaly("bookings: route_id present but different from the train's route", (~miss_route & (route_num != route_from_train)).sum())
    route_id = route_from_train
    bc = b["boarding_station_code"].str.strip().str.upper()
    dc = b["destination_station_code"].str.strip().str.upper()
    b_known, d_known = bc.isin(st_id_of_code), dc.isin(st_id_of_code)
    fmt = ((b["boarding_station_code"] != bc) & b_known) | ((b["destination_station_code"] != dc) & d_known)
    unk = ~b_known | ~d_known
    res.rec("station_code_format", fmt.sum()); res.rec("station_code_unknown", unk.sum())
    board_id = route_id.map(origin_of_route)
    dest_id = route_id.map(dest_of_route)
    res.anomaly("bookings: recognised station code differs from route origin/destination",
                ((b_known & (bc.map(st_id_of_code) != board_id)) | (d_known & (dc.map(st_id_of_code) != dest_id))).sum())

    # ---------------------------------------------------------------- 5. passenger statuses
    lk = dq.STATUS_LOOKUP
    ok_init, ok_final = {"Confirmed", "RAC", "Waitlisted"}, set(dq.CANONICAL_STATUS)
    ci = ps["initial_status"].str.strip().str.lower().map(lk)
    cf = ps["final_status"].str.strip().str.lower().map(lk)
    ci_bad = ci.isna() | ~ci.isin(ok_init)
    cf_bad = cf.isna() | ~cf.isin(ok_final)
    alias_any = (~ci_bad & (ps["initial_status"] != ci)) | (~cf_bad & (ps["final_status"] != cf))
    res.rec("passenger_status_alias", alias_any.sum())
    res.rec("passenger_initial_status_invalid", ci_bad.sum())
    flag(ps.loc[ci_bad, "booking_id"], "passenger_initial_status_invalid")
    ctype = dict(zip(ev["cancellation_id"], ev["cancellation_type"]))
    link = ps["cancellation_id"].str.strip()
    derived = link.map(ctype).map({"Passenger": "Cancelled", "System": "Waitlisted"})
    can_derive = cf_bad & derived.notna()
    res.rec("passenger_final_status_invalid", cf_bad.sum(), corrected=can_derive.sum(), rejected=(cf_bad & ~can_derive).sum())
    flag(ps.loc[cf_bad & ~can_derive, "booking_id"], "unrecoverable_other")
    final_status = cf.where(~cf_bad, derived)
    initial_status = ci
    age = ps["age_band"].str.strip()
    res.rec("missing_age_band", (age == "").sum())
    age = age.replace("", "Unknown")

    # ---------------------------------------------------------------- 6. passenger fares, totals, counts
    fare = _num(ps["fare_amount"])
    bad = fare.isna() | (fare <= 0)
    n_bad = bad.groupby(ps["booking_id"]).sum()
    s0 = b["total_fare"].str.strip()
    plain = s0.str.fullmatch(r"-?\d+(\.\d+)?")
    tot_plain = pd.to_numeric(s0.where(plain), errors="coerce")
    tot_cur = pd.to_numeric(s0.where(~plain & (s0 != "")).str.replace(CURRENCY_STRIP, "", regex=True), errors="coerce")
    tot_val = tot_plain.fillna(tot_cur)
    tot_by_booking = pd.Series(tot_val.to_numpy(), index=b["booking_id"].to_numpy())
    good_sum = fare.where(~bad, 0.0).groupby(ps["booking_id"]).sum()
    recon = ps["booking_id"].map(tot_by_booking) - ps["booking_id"].map(good_sum)
    fix = bad & (ps["booking_id"].map(n_bad) == 1) & (ps["booking_id"].map(tot_by_booking) > 0) & (recon > 0)
    res.rec("negative_passenger_fare", bad.sum(), corrected=fix.sum(), rejected=(bad & ~fix).sum())
    flag(ps.loc[bad & ~fix, "booking_id"], "unrecoverable_other")
    fare_final = fare.where(~fix, recon.round(2))
    sum_pax = fare_final.groupby(ps["booking_id"]).sum(min_count=1)
    n_rows = ps.groupby("booking_id").size()
    sum_b = b["booking_id"].map(sum_pax)
    no_pax = sum_b.isna()
    flag(b.loc[no_pax, "booking_id"], "unrecoverable_other")
    missing_t = s0 == ""
    ok_plain = plain & ((tot_plain - sum_b).abs() < 0.005)
    ok_cur = ~plain & ~missing_t & tot_cur.notna() & ((tot_cur - sum_b).abs() < 0.005)
    res.rec("missing_total_fare", missing_t.sum())
    res.rec("total_fare_currency_format", ok_cur.sum())
    res.rec("total_fare_invalid", (~missing_t & ~ok_plain & ~ok_cur).sum())
    np_raw = pd.to_numeric(b["num_passengers"].str.strip().replace("", np.nan), errors="coerce")
    res.rec("num_passengers_invalid", (np_raw.isna() | (np_raw != b["booking_id"].map(n_rows))).sum())

    # ---------------------------------------------------------------- 7. booking status (roll-up is authoritative)
    grp = final_status.groupby(ps["booking_id"])
    rollup = grp.first().where(grp.nunique() == 1, "Mixed")
    roll_b = b["booking_id"].map(rollup)
    canon_b = b["booking_status"].str.strip().str.lower().map(lk)
    res.rec("booking_status_alias", (canon_b.notna() & (b["booking_status"] != canon_b)).sum())
    res.rec("booking_status_invalid", canon_b.isna().sum())
    res.anomaly("bookings: recognised booking_status differs from passenger roll-up", (canon_b.notna() & roll_b.notna() & (canon_b != roll_b)).sum())

    # ---------------------------------------------------------------- 8. cancellation events
    ets = pd.to_datetime(ev["cancellation_ts"].str.strip().replace("", np.nan), format=TS_FMT, errors="coerce")
    res.anomaly("cancellations: unparseable cancellation_ts", ets.isna().sum())
    bts_of = pd.Series(bts.to_numpy(), index=b["booking_id"].to_numpy())
    # root-cause attribution: events of a family already rejected for another reason (e.g. corrupted booking_ts)
    # are not counted a second time
    before = (ets < ev["booking_id"].map(bts_of)) & ~ev["booking_id"].isin(set(reject))
    res.rec("cancellation_before_booking", before.sum()); flag(ev.loc[before, "booking_id"], "cancellation_before_booking")
    orig, chg, ref_amt = _num(ev["original_fare_amount"]), _num(ev["cancellation_charge"]), _num(ev["refund_amount"])
    exceeds = ref_amt > orig + 0.005
    res.rec("refund_exceeds_fare", exceeds.sum())
    other_mm = ~exceeds & ((ref_amt + chg - orig).abs() > 0.01)
    res.anomaly("cancellations: refund + charge differs from original fare (not exceeding)", other_mm.sum())
    refund_final = ref_amt.where(~(exceeds | other_mm), orig - chg).round(2)

    # ---------------------------------------------------------------- 9. booking-family rejection
    rej_ids = set(reject)
    reasons = {}
    for bid, code in reject.items():
        reasons.setdefault(code, set()).add(bid)
    for code, ids in reasons.items():
        pcount = int(ps["booking_id"].isin(ids).sum())
        ecount = int(ev["booking_id"].isin(ids).sum())
        res.cascade[code] = dict(bookings=len(ids), passengers=pcount, cancellations=ecount)
    mv["bookings"]["family_rejected"] = int(b["booking_id"].isin(rej_ids).sum())
    mv["booking_passengers"]["family_rejected"] = int(ps["booking_id"].isin(rej_ids).sum())
    mv["cancellations"]["family_rejected"] = int(ev["booking_id"].isin(rej_ids).sum())
    kb, kp, ke = ~b["booking_id"].isin(rej_ids), ~ps["booking_id"].isin(rej_ids), ~ev["booking_id"].isin(rej_ids)

    # ---------------------------------------------------------------- 10. assemble cleaned transactional tables
    bookings = pd.DataFrame(dict(
        booking_id=b["booking_id"].astype("int64"), booking_reference=b["booking_reference"], train_id=train_id.astype("int64"),
        journey_date=jdate.dt.date, route_id=route_id.astype("int64"), boarding_station_id=board_id.astype("int64"),
        destination_station_id=dest_id.astype("int64"), travel_class=b["travel_class"].str.strip(), booking_ts=bts,
        num_passengers=b["booking_id"].map(n_rows), booking_status=roll_b, total_fare=sum_b.round(2),
        data_origin=b["data_origin"]))[kb].reset_index(drop=True)
    bookings["num_passengers"] = bookings["num_passengers"].astype("int64")
    passengers = pd.DataFrame(dict(
        passenger_id=ps["passenger_id"].astype("int64"), booking_id=ps["booking_id"].astype("int64"),
        passenger_seq=ps["passenger_seq"].astype("int64"), age_band=age, fare_amount=fare_final.round(2),
        initial_status=initial_status, final_status=final_status,
        cancellation_id=pd.to_numeric(link.replace("", np.nan), errors="coerce").astype("Int64"),
        data_origin=ps["data_origin"]))[kp].reset_index(drop=True)
    cancellations = pd.DataFrame(dict(
        cancellation_id=ev["cancellation_id"].astype("int64"), booking_id=ev["booking_id"].astype("int64"), cancellation_ts=ets,
        cancellation_type=ev["cancellation_type"].str.strip(), status_at_cancellation=ev["status_at_cancellation"].str.strip(),
        cancelled_passengers=pd.to_numeric(ev["cancelled_passengers"]).astype("int64"), original_fare_amount=orig.round(2),
        cancellation_charge=chg.round(2), refund_amount=refund_final, data_origin=ev["data_origin"]))[ke].reset_index(drop=True)
    bookings = bookings.sort_values("booking_id").reset_index(drop=True)
    passengers = passengers.sort_values("passenger_id").reset_index(drop=True)
    cancellations = cancellations.sort_values("cancellation_id").reset_index(drop=True)

    # ---------------------------------------------------------------- 11. seat capacity
    cap = R["seat_capacity"].copy()
    for c in ("capacity_id", "train_id", "coaches_attached", "seats_per_coach", "total_seats", "rac_berths", "wl_limit"):
        cap[c] = pd.to_numeric(cap[c])
    cap["_ord"] = np.arange(len(cap))
    std = cap["travel_class"].map(cfg.CLASS_SEATS)
    cap["_cons"] = (cap["seats_per_coach"] == std) & (cap["total_seats"] == cap["coaches_attached"] * cap["seats_per_coach"])
    key = ["train_id", "journey_date", "travel_class"]
    srt = cap.sort_values(key + ["_cons", "_ord"], ascending=[True, True, True, False, True])
    keep = ~srt.duplicated(key, keep="first")
    res.rec("capacity_conflicting_duplicate", (~keep).sum()); mv["seat_capacity"]["duplicates"] = int((~keep).sum())
    cap = srt[keep].sort_values("_ord").reset_index(drop=True)
    std = cap["travel_class"].map(cfg.CLASS_SEATS)
    spc_bad = (cap["seats_per_coach"] != std) & (cap["total_seats"] == cap["coaches_attached"] * std)
    tot_bad = (cap["seats_per_coach"] == std) & (cap["total_seats"] != cap["coaches_attached"] * cap["seats_per_coach"])
    res.rec("capacity_seats_per_coach_invalid", spc_bad.sum()); res.rec("capacity_total_mismatch", tot_bad.sum())
    res.anomaly("seat_capacity: inconsistent in a way no rule covers", ((cap["seats_per_coach"] != std) & ~spc_bad).sum())
    cap["seats_per_coach"] = std
    cap["total_seats"] = cap["coaches_attached"] * std
    seat_capacity = cap[["capacity_id", "train_id", "journey_date", "travel_class", "coaches_attached", "seats_per_coach",
                         "total_seats", "rac_berths", "wl_limit", "data_origin"]].copy()
    seat_capacity["journey_date"] = pd.to_datetime(seat_capacity["journey_date"]).dt.date
    for c in ("capacity_id", "train_id", "coaches_attached", "seats_per_coach", "total_seats", "rac_berths", "wl_limit"):
        seat_capacity[c] = seat_capacity[c].astype("int64")

    # ---------------------------------------------------------------- 12. train operations
    ops = R["train_operations"].copy()
    arr_raw = ops["arrival_delay_min"].str.strip()
    is_missing = arr_raw == ""
    val = pd.to_numeric(arr_raw.where(~is_missing), errors="coerce")
    res.anomaly("train_operations: non-numeric arrival delay", (~is_missing & val.isna()).sum())
    oor = val.notna() & ((val < cfg.DELAY_SANITY_MIN) | (val > cfg.DELAY_SANITY_MAX))
    res.rec("missing_arrival_delay", is_missing.sum()); res.rec("delay_out_of_range", oor.sum())
    val = val.where(~oor)
    operations = pd.DataFrame(dict(
        operation_id=ops["operation_id"].astype("int64"), train_id=ops["train_id"].astype("int64"),
        run_date=pd.to_datetime(ops["run_date"]).dt.date, departure_delay_min=pd.to_numeric(ops["departure_delay_min"]).astype("int64"),
        arrival_delay_min=val.round().astype("Int64"), data_origin=ops["data_origin"]))

    cleaned = dict(ref)
    cleaned.update(seat_capacity=seat_capacity, train_operations=operations, bookings=bookings,
                   booking_passengers=passengers, cancellations=cancellations)
    for t in mv:
        mv[t]["clean_rows"] = len(cleaned[t])
        mv[t]["other"] = mv[t]["raw_rows"] - mv[t]["clean_rows"] - mv[t]["duplicates"] - mv[t]["orphans"] - mv[t]["family_rejected"]
    res.movement.update(mv)
    return cleaned, res


def write_clean(cleaned, out_dir=cfg.CLEAN_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in cleaned.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)


def read_clean(clean_dir=cfg.CLEAN_DIR):
    """Read the cleaned CSVs back with proper types (used by validation and tests)."""
    T = {}
    dates = {"calendar": ["calendar_date"], "seat_capacity": ["journey_date"], "train_operations": ["run_date"],
             "bookings": ["journey_date"]}
    stamps = {"bookings": ["booking_ts"], "cancellations": ["cancellation_ts"]}
    for n in TABLES:
        df = pd.read_csv(clean_dir / f"{n}.csv")
        for c in dates.get(n, []):
            df[c] = pd.to_datetime(df[c]).dt.date
        for c in stamps.get(n, []):
            df[c] = pd.to_datetime(df[c])
        if n == "booking_passengers":
            df["cancellation_id"] = df["cancellation_id"].astype("Int64")
        if n == "train_operations":
            df["arrival_delay_min"] = df["arrival_delay_min"].astype("Int64")
        T[n] = df
    return T
