"""Build the RAW dataset from the clean synthetic truth by injecting CONTROLLED data-quality issues.

* Every table is converted to text (as a raw extract would be).
* Issues are injected at documented rates (config.DQ_RATES) into DISJOINT sets of booking families, so each
  affected family carries exactly one issue type and the expected counts are exact.
* Only transactional / operational tables are corrupted; reference tables (stations, routes, trains, train_stops,
  calendar) are left intact.
* An injection log (issue, table, key) is written to reports/data_quality/injection_log.csv. The cleaner never reads it;
  it is used only to verify that the cleaner detected what was injected.
"""
from datetime import timedelta

import numpy as np
import pandas as pd

import config as cfg
import dq_catalog as dq

MONEY = {"total_fare", "fare_amount", "original_fare_amount", "cancellation_charge", "refund_amount"}
ONE_DP = {"distance_km", "distance_from_origin_km"}
STD_SEATS = cfg.CLASS_SEATS


def to_text(df):
    out = {}
    for c in df.columns:
        s = df[c]
        if c in MONEY:
            out[c] = s.map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
        elif c in ONE_DP:
            out[c] = s.map(lambda v: "" if pd.isna(v) else f"{v:.1f}")
        elif pd.api.types.is_datetime64_any_dtype(s):
            out[c] = s.dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            out[c] = s.astype(object).where(s.notna(), "").astype(str)
    return pd.DataFrame(out)


def make_raw(truth, seed=cfg.SEED + 1):
    rng = np.random.default_rng(seed)
    R = cfg.DQ_RATES
    log = []

    def L(code, keys, detail=""):
        for k in keys:
            log.append((code, dq.CATALOG[code]["table"], k, dq.CATALOG[code]["outcome"], detail))

    tt = {k: to_text(v) for k, v in truth.items()}

    # ---------- raw booking extract carries station CODES instead of station ids
    code_of = dict(zip(truth["stations"]["station_id"], truth["stations"]["station_code"]))
    b = tt["bookings"].copy()
    tb = truth["bookings"]
    b["boarding_station_code"] = tb["boarding_station_id"].map(code_of).to_numpy()
    b["destination_station_code"] = tb["destination_station_id"].map(code_of).to_numpy()
    b = b.drop(columns=["boarding_station_id", "destination_station_id"])
    b = b[["booking_id", "booking_reference", "train_id", "journey_date", "route_id", "boarding_station_code",
           "destination_station_code", "travel_class", "booking_ts", "num_passengers", "booking_status", "total_fare",
           "data_origin"]]
    ps = tt["booking_passengers"].copy()
    ev = tt["cancellations"].copy()
    cap = tt["seat_capacity"].copy()
    ops = tt["train_operations"].copy()

    ids = tb["booking_id"].to_numpy()
    pos_b = {int(i): k for k, i in enumerate(ids)}
    ps_bid = truth["booking_passengers"]["booking_id"].to_numpy()
    p_first = pd.Series(np.arange(len(ps_bid))).groupby(ps_bid).first()
    linked_mask = truth["booking_passengers"]["cancellation_id"].notna().to_numpy()
    p_linked_first = pd.Series(np.flatnonzero(linked_mask)).groupby(ps_bid[linked_mask]).first()
    ev_bid = truth["cancellations"]["booking_id"].to_numpy()
    e_first = pd.Series(np.arange(len(ev_bid))).groupby(ev_bid).first()

    N, NE = len(b), len(ev)
    all_pool = [int(x) for x in rng.permutation(ids)]
    ev_pool = [int(x) for x in rng.permutation(e_first.index.to_numpy())]
    used = set()

    def take(n, pool):
        out = []
        while len(out) < n:
            x = pool.pop()
            if x in used:
                continue
            used.add(x)
            out.append(x)
        return out

    cnt = lambda rate, base: int(round(rate * base))
    bpos = lambda bids: np.array([pos_b[i] for i in bids], dtype=int)

    extra_ps, extra_ev, extra_b = [], [], []

    # ================= issues on bookings that HAVE cancellation events (chosen first)
    bids = take(cnt(R["cancellation_before_booking"], NE), ev_pool)
    for bid in bids:
        e = int(e_first[bid])
        bts = pd.Timestamp(b.at[pos_b[bid], "booking_ts"])
        ev.at[e, "cancellation_ts"] = (bts - timedelta(hours=int(rng.integers(1, 72)))).strftime("%Y-%m-%d %H:%M:%S")
    L("cancellation_before_booking", [int(ev.at[int(e_first[x]), "cancellation_id"]) for x in bids])

    bids = take(cnt(R["refund_exceeds_fare"], NE), ev_pool)
    for bid in bids:
        e = int(e_first[bid])
        orig = float(ev.at[e, "original_fare_amount"])
        ev.at[e, "refund_amount"] = f"{orig * rng.uniform(1.1, 2.0):.2f}"
    L("refund_exceeds_fare", [int(ev.at[int(e_first[x]), "cancellation_id"]) for x in bids])

    bids = take(cnt(R["dup_cancellation_rows"], NE), ev_pool)
    for bid in bids:
        extra_ev.append(ev.iloc[int(e_first[bid])].copy())
    L("dup_cancellation_rows", [int(ev.at[int(e_first[x]), "cancellation_id"]) for x in bids])

    bids = take(cnt(R["passenger_final_status_invalid"], N), ev_pool)
    for bid in bids:
        p = int(p_linked_first[bid])
        ps.at[p, "final_status"] = str(rng.choice(dq.PASSENGER_STATUS_GARBAGE))
    L("passenger_final_status_invalid", [int(ps.at[int(p_linked_first[x]), "passenger_id"]) for x in bids])

    # ================= issues on any booking family
    def bk_ids(x):
        return [int(b.at[pos_b[i], "booking_id"]) for i in x]

    # --- duplicates
    bids = take(cnt(R["dup_booking_rows"], N), all_pool)
    for bid in bids:
        extra_b.append(b.iloc[pos_b[bid]].copy())
    L("dup_booking_rows", bids)

    bids = take(cnt(R["dup_passenger_rows"], N), all_pool)
    for bid in bids:
        extra_ps.append(ps.iloc[int(p_first[bid])].copy())
    L("dup_passenger_rows", [int(ps.at[int(p_first[x]), "passenger_id"]) for x in bids])

    # --- fares
    bids = take(cnt(R["missing_total_fare"], N), all_pool)
    b.loc[bpos(bids), "total_fare"] = ""
    L("missing_total_fare", bids)

    bids = take(cnt(R["total_fare_currency_format"], N), all_pool)
    for k, bid in enumerate(bids):
        v = float(b.at[pos_b[bid], "total_fare"])
        b.at[pos_b[bid], "total_fare"] = f"\u20b9{v:,.2f}" if k % 2 == 0 else f"Rs. {v:.0f}"
    L("total_fare_currency_format", bids)

    bids = take(cnt(R["total_fare_invalid"], N), all_pool)
    for bid in bids:
        v = float(b.at[pos_b[bid], "total_fare"])
        kind = int(rng.integers(0, 4))
        b.at[pos_b[bid], "total_fare"] = [f"{-v:.2f}", "0.00", "N/A", f"{v * 10:.2f}"][kind]
    L("total_fare_invalid", bids)

    bids = take(cnt(R["negative_passenger_fare"], N), all_pool)
    for bid in bids:
        p = int(p_first[bid])
        ps.at[p, "fare_amount"] = f"{-float(ps.at[p, 'fare_amount']):.2f}"
    L("negative_passenger_fare", [int(ps.at[int(p_first[x]), "passenger_id"]) for x in bids])

    # --- references / identifiers
    bids = take(cnt(R["missing_route_id"], N), all_pool)
    b.loc[bpos(bids), "route_id"] = ""
    L("missing_route_id", bids)

    bids = take(cnt(R["station_code_format"], N), all_pool)
    for k, bid in enumerate(bids):
        for col in ("boarding_station_code", "destination_station_code"):
            v = b.at[pos_b[bid], col]
            b.at[pos_b[bid], col] = [v.lower(), f" {v} ", f"{v.lower()} "][k % 3]
    L("station_code_format", bids)

    bids = take(cnt(R["station_code_unknown"], N), all_pool)
    for k, bid in enumerate(bids):
        col = "boarding_station_code" if k % 2 == 0 else "destination_station_code"
        b.at[pos_b[bid], col] = str(rng.choice(dq.UNKNOWN_STATION_CODES))
    L("station_code_unknown", bids)

    # --- dates
    bids = take(cnt(R["missing_booking_ts"], N), all_pool)
    b.loc[bpos(bids), "booking_ts"] = ""
    L("missing_booking_ts", bids)

    bids = take(cnt(R["journey_date_format"], N), all_pool)
    for bid in bids:
        y, m, d = b.at[pos_b[bid], "journey_date"].split("-")
        b.at[pos_b[bid], "journey_date"] = f"{d}-{m}-{y}"
    L("journey_date_format", bids)

    bids = take(cnt(R["journey_date_impossible"], N), all_pool)
    for bid in bids:
        y = b.at[pos_b[bid], "journey_date"][:4]
        b.at[pos_b[bid], "journey_date"] = str(rng.choice([f"{y}-02-30", f"{y}-13-05", f"{y}-04-31", f"{y}-00-10"]))
    L("journey_date_impossible", bids)

    bids = take(cnt(R["booking_after_journey"], N), all_pool)
    for bid in bids:
        jd = pd.Timestamp(b.at[pos_b[bid], "journey_date"])
        b.at[pos_b[bid], "booking_ts"] = (jd + timedelta(days=int(rng.integers(1, 6)), hours=int(rng.integers(6, 22)))
                                          ).strftime("%Y-%m-%d %H:%M:%S")
    L("booking_after_journey", bids)

    # --- statuses
    bids = take(cnt(R["booking_status_alias"], N), all_pool)
    for bid in bids:
        canon = b.at[pos_b[bid], "booking_status"]
        b.at[pos_b[bid], "booking_status"] = str(rng.choice(dq.STATUS_VARIANTS[canon]))
    L("booking_status_alias", bids)

    bids = take(cnt(R["booking_status_invalid"], N), all_pool)
    for bid in bids:
        b.at[pos_b[bid], "booking_status"] = str(rng.choice(dq.STATUS_GARBAGE))
    L("booking_status_invalid", bids)

    bids = take(cnt(R["passenger_status_alias"], N), all_pool)
    for k, bid in enumerate(bids):
        p = int(p_first[bid])
        col = "final_status" if k % 2 == 0 else "initial_status"
        canon = ps.at[p, col]
        ps.at[p, col] = str(rng.choice(dq.STATUS_VARIANTS[canon]))
    L("passenger_status_alias", [int(ps.at[int(p_first[x]), "passenger_id"]) for x in bids])

    bids = take(cnt(R["passenger_initial_status_invalid"], N), all_pool)
    for bid in bids:
        ps.at[int(p_first[bid]), "initial_status"] = str(rng.choice(dq.PASSENGER_STATUS_GARBAGE))
    L("passenger_initial_status_invalid", [int(ps.at[int(p_first[x]), "passenger_id"]) for x in bids])

    bids = take(cnt(R["num_passengers_invalid"], N), all_pool)
    for k, bid in enumerate(bids):
        n = int(b.at[pos_b[bid], "num_passengers"])
        b.at[pos_b[bid], "num_passengers"] = ["", str(n + 1), "0", "two"][k % 4]
    L("num_passengers_invalid", bids)

    bids = take(cnt(R["missing_age_band"], N), all_pool)
    for bid in bids:
        ps.at[int(p_first[bid]), "age_band"] = ""
    L("missing_age_band", [int(ps.at[int(p_first[x]), "passenger_id"]) for x in bids])

    # ================= orphan rows (extra rows pointing at bookings that do not exist)
    n_orph_e = cnt(R["orphan_cancellation_rows"], NE)
    max_cid = int(truth["cancellations"]["cancellation_id"].max())
    src = rng.choice(NE, size=n_orph_e, replace=False)
    orph_ev = []
    for k, s in enumerate(src):
        row = ev.iloc[int(s)].copy()
        row["cancellation_id"] = str(max_cid + 1 + k)
        row["booking_id"] = str(9_000_000 + k)
        orph_ev.append(row)
    L("orphan_cancellation_rows", [max_cid + 1 + k for k in range(n_orph_e)])

    n_orph_p = cnt(R["orphan_passenger_rows"], N)
    max_pid = int(truth["booking_passengers"]["passenger_id"].max())
    src = rng.choice(len(ps), size=n_orph_p, replace=False)
    orph_ps = []
    for k, s in enumerate(src):
        row = ps.iloc[int(s)].copy()
        row["passenger_id"] = str(max_pid + 1 + k)
        row["booking_id"] = str(9_500_000 + k)
        row["cancellation_id"] = ""
        row["initial_status"] = row["final_status"] = "Confirmed"
        orph_ps.append(row)
    L("orphan_passenger_rows", [max_pid + 1 + k for k in range(n_orph_p)])

    # ================= capacity
    ncap = len(cap)
    cap_pool = [int(x) for x in rng.permutation(ncap)]
    cap_used = set()

    def take_cap(n):
        out = []
        while len(out) < n:
            x = cap_pool.pop()
            if x in cap_used:
                continue
            cap_used.add(x)
            out.append(x)
        return out

    rows = take_cap(cnt(R["capacity_total_mismatch"], ncap))
    for r in rows:
        delta = int(rng.choice([d for d in range(-40, 61) if d != 0]))
        cap.at[r, "total_seats"] = str(int(cap.at[r, "total_seats"]) + delta)
    L("capacity_total_mismatch", [int(cap.at[r, "capacity_id"]) for r in rows])

    rows = take_cap(cnt(R["capacity_seats_per_coach_invalid"], ncap))
    for r in rows:
        std = STD_SEATS[cap.at[r, "travel_class"]]
        cap.at[r, "seats_per_coach"] = str(std + int(rng.choice([-12, -8, -6, 6, 8, 12])))
    L("capacity_seats_per_coach_invalid", [int(cap.at[r, "capacity_id"]) for r in rows])

    rows = take_cap(cnt(R["capacity_conflicting_duplicate"], ncap))
    max_capid = int(truth["seat_capacity"]["capacity_id"].max())
    extra_cap = []
    for k, r in enumerate(rows):
        row = cap.iloc[r].copy()
        row["capacity_id"] = str(max_capid + 1 + k)
        row["total_seats"] = str(int(row["total_seats"]) + int(rng.choice([-30, -20, 20, 30, 40])))
        extra_cap.append(row)
    L("capacity_conflicting_duplicate", [max_capid + 1 + k for k in range(len(rows))])

    # ================= operations
    nop = len(ops)
    op_pool = [int(x) for x in rng.permutation(nop)]
    rows = op_pool[:cnt(R["missing_arrival_delay"], nop)]
    rows_b = op_pool[len(rows):len(rows) + cnt(R["delay_out_of_range"], nop)]
    ops.loc[rows, "arrival_delay_min"] = ""
    L("missing_arrival_delay", [int(ops.at[r, "operation_id"]) for r in rows])
    for r in rows_b:
        ops.at[r, "arrival_delay_min"] = str(int(rng.choice([2500, 5000, 9999, -500, -999])))
    L("delay_out_of_range", [int(ops.at[r, "operation_id"]) for r in rows_b])

    # ================= append extra rows (duplicates and orphans are appended, as a late re-ingestion would be)
    def app(df, rows):
        return pd.concat([df, pd.DataFrame(rows)], ignore_index=True) if rows else df

    b = app(b, extra_b)
    ps = app(ps, extra_ps + orph_ps)
    ev = app(ev, extra_ev + orph_ev)
    cap = app(cap, extra_cap)

    raw = dict(tt)
    raw.update(bookings=b, booking_passengers=ps, cancellations=ev, seat_capacity=cap, train_operations=ops)
    inj = pd.DataFrame(log, columns=["issue_code", "table", "record_key", "expected_outcome", "detail"])
    return raw, inj


def write_raw(raw, inj, raw_dir=cfg.RAW_DIR, log_dir=cfg.DQ_DIR):
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    for name, df in raw.items():
        df.to_csv(raw_dir / f"{name}.csv", index=False)
    inj.to_csv(log_dir / "injection_log.csv", index=False)


if __name__ == "__main__":
    import generate_synthetic_data as g
    truth = g.generate(verbose=False)
    raw, inj = make_raw(truth)
    write_raw(raw, inj)
    print(inj.groupby("issue_code").size().to_string())
