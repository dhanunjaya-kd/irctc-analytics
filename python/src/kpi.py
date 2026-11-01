"""Reference KPI implementation. Excel, SQL, Power BI and Tableau must reconcile to these numbers.

Definitions follow docs/KPI_definitions.md exactly (passenger-based cancellation rate, initial-status waiting-list demand,
fully-confirmed booking count, occupancy on passenger counts). All values describe SYNTHETIC data from a SAMPLED
simulation (768 simulated runs of 19,708 scheduled); they are not IRCTC network-wide metrics.

Also writes the Phase 3 derived datasets (data/processed/derived) and the run-complete Excel sample (data/sample/excel).
"""
import numpy as np
import pandas as pd

import config as cfg

LEAD_EDGES = [-1, 3, 14, 30, 60, 120]
LEAD_LABELS = ["0-3 days", "4-14 days", "15-30 days", "31-60 days", "61-120 days"]
DERIVED_DIR = cfg.ROOT / "data" / "processed" / "derived"
EXCEL_SAMPLE_DIR = cfg.SAMPLE_DIR / "excel"
SAMPLE_RUNS_PER_MONTH = 2

# key, name, unit, numerator key, denominator key (None for plain counts/values)
KPI_SPEC = [
    ("total_bookings", "Total Bookings", "bookings", None, None),
    ("total_passengers", "Total Passengers", "passengers", None, None),
    ("confirmed_bookings", "Confirmed Booking Count (all passengers Confirmed)", "bookings", None, None),
    ("mixed_bookings", "Mixed Booking Count", "bookings", None, None),
    ("cancelled_bookings", "Cancelled Booking Count", "bookings", None, None),
    ("cancelled_passengers", "Cancelled Passengers", "passengers", None, None),
    ("passenger_cancellation_rate", "Cancellation Rate (passenger-based)", "share", "cancelled_passengers", "total_passengers"),
    ("booking_cancellation_rate", "Booking Cancellation Rate (companion)", "share", "cancelled_bookings", "total_bookings"),
    ("gross_value", "Gross Booking Value", "INR", None, None),
    ("refund_total", "Refund Amount", "INR", None, None),
    ("refund_passenger", "Refund Amount: Passenger events", "INR", None, None),
    ("refund_system", "Refund Amount: System events", "INR", None, None),
    ("retained_charges", "Retained Cancellation Charges", "INR", None, None),
    ("net_value", "Net Booking Value", "INR", None, None),
    ("avg_fare_per_passenger", "Average Fare per passenger", "INR", "gross_value", "total_passengers"),
    ("avg_fare_per_booking", "Average Fare per booking (secondary)", "INR", "gross_value", "total_bookings"),
    ("wl_demand", "Waiting-List Demand (initially waitlisted passengers)", "passengers", None, None),
    ("wl_cleared", "Waitlisted passengers later Confirmed or RAC", "passengers", None, None),
    ("wl_clearance_rate", "Waitlist Clearance Rate", "share", "wl_cleared", "wl_demand"),
    ("wl_uncleared", "Uncleared Waitlist Passengers (final Waitlisted)", "passengers", None, None),
    ("seat_supply", "Available Seats (capacity)", "seats", None, None),
    ("booked_seats", "Booked Seats (Confirmed + 0.5 x RAC)", "seat-equivalents", None, None),
    ("occupancy", "Seat Occupancy %", "share", "booked_seats", "seat_supply"),
    ("confirmed_occupancy", "Confirmed Occupancy %", "share", "confirmed_pax", "seat_supply"),
    ("waitlist_pressure", "Waitlist Pressure %", "share", "wl_uncleared", "seat_supply"),
    ("simulated_runs", "Simulated train runs", "runs", None, None),
    ("bookings_per_run", "Bookings per Simulated Run", "bookings/run", "total_bookings", "simulated_runs"),
    ("passengers_per_run", "Passengers per Simulated Run", "passengers/run", "total_passengers", "simulated_runs"),
    ("otp", "On-Time Performance %", "share", "on_time_runs", "runs_with_delay"),
    ("avg_delay", "Average Delay (early = 0)", "minutes", "delay_sum_pos", "runs_with_delay"),
    ("delayed_runs", "Delayed Train Runs", "runs", None, None),
]


def safe(n, d):
    return float(n) / float(d) if d else float("nan")


def enrich(T):
    """Bookings with month, lead time, bucket, run key and route name."""
    bk = T["bookings"].copy()
    jd = pd.to_datetime(bk["journey_date"].astype(str))
    bk["journey_month"] = jd.dt.strftime("%Y-%m")
    bk["lead_days"] = (jd - bk["booking_ts"].dt.normalize()).dt.days
    bk["lead_bucket"] = pd.cut(bk["lead_days"], LEAD_EDGES, labels=LEAD_LABELS).astype(str)
    bk["run_class_key"] = bk["train_id"].astype(str) + "|" + bk["journey_date"].astype(str) + "|" + bk["travel_class"]
    bk["route_name"] = bk["route_id"].map(T["routes"].set_index("route_id")["route_name"])
    return bk


def compute_kpis(bk, ps, ev, cap, ops):
    fs, ist = ps["final_status"], ps["initial_status"]
    conf, rac = int((fs == "Confirmed").sum()), int((fs == "RAC").sum())
    wl_final, canc = int((fs == "Waitlisted").sum()), int((fs == "Cancelled").sum())
    wl_init = int((ist == "Waitlisted").sum())
    wl_cleared = int(((ist == "Waitlisted") & fs.isin(["Confirmed", "RAC"])).sum())
    gross, refund = float(bk["total_fare"].sum()), float(ev["refund_amount"].sum())
    ref_p = float(ev.loc[ev["cancellation_type"] == "Passenger", "refund_amount"].sum())
    ref_s = float(ev.loc[ev["cancellation_type"] == "System", "refund_amount"].sum())
    seats = int(cap["total_seats"].sum())
    booked = conf + cfg.RAC_SEAT_WEIGHT * rac
    arr = ops["arrival_delay_min"].dropna().astype(float)
    d = dict(total_bookings=len(bk), total_passengers=len(ps), confirmed_bookings=int((bk["booking_status"] == "Confirmed").sum()),
             mixed_bookings=int((bk["booking_status"] == "Mixed").sum()), cancelled_bookings=int((bk["booking_status"] == "Cancelled").sum()),
             cancelled_passengers=canc, confirmed_pax=conf, rac_pax=rac, gross_value=gross, refund_total=refund,
             refund_passenger=ref_p, refund_system=ref_s, retained_charges=float(ev["cancellation_charge"].sum()),
             net_value=gross - refund, wl_demand=wl_init, wl_cleared=wl_cleared, wl_uncleared=wl_final, seat_supply=seats,
             booked_seats=booked, simulated_runs=len(ops), class_runs=len(cap), runs_with_delay=len(arr),
             on_time_runs=int((arr <= cfg.ON_TIME_THRESHOLD_MIN).sum()), delayed_runs=int((arr > cfg.ON_TIME_THRESHOLD_MIN).sum()),
             delay_sum_pos=float(arr.clip(lower=0).sum()))
    d["passenger_cancellation_rate"] = safe(canc, len(ps)); d["booking_cancellation_rate"] = safe(d["cancelled_bookings"], len(bk))
    d["avg_fare_per_passenger"] = safe(gross, len(ps)); d["avg_fare_per_booking"] = safe(gross, len(bk))
    d["wl_clearance_rate"] = safe(wl_cleared, wl_init); d["occupancy"] = safe(booked, seats)
    d["confirmed_occupancy"] = safe(conf, seats); d["rac_occupancy"] = safe(cfg.RAC_SEAT_WEIGHT * rac, seats)
    d["waitlist_pressure"] = safe(wl_final, seats)
    d["bookings_per_run"] = safe(len(bk), len(ops)); d["passengers_per_run"] = safe(len(ps), len(ops))
    d["otp"] = safe(d["on_time_runs"], len(arr)); d["avg_delay"] = safe(d["delay_sum_pos"], len(arr))
    return d


def _prep(T):
    bk = enrich(T)
    ps = T["booking_passengers"].merge(bk[["booking_id", "train_id", "journey_date", "journey_month", "travel_class", "route_name",
                                            "lead_bucket", "run_class_key"]], on="booking_id")
    ev = T["cancellations"].merge(bk[["booking_id", "journey_month", "travel_class", "route_name"]], on="booking_id")
    cap = T["seat_capacity"].copy()
    cap["journey_month"] = pd.to_datetime(cap["journey_date"].astype(str)).dt.strftime("%Y-%m")
    cap["run_class_key"] = cap["train_id"].astype(str) + "|" + cap["journey_date"].astype(str) + "|" + cap["travel_class"]
    cap["route_name"] = cap["train_id"].map(T["trains"].set_index("train_id")["route_id"]).map(T["routes"].set_index("route_id")["route_name"])
    ops = T["train_operations"].copy()
    ops["journey_month"] = pd.to_datetime(ops["run_date"].astype(str)).dt.strftime("%Y-%m")
    ops = ops.merge(T["trains"][["train_id", "train_number", "train_type", "route_id"]], on="train_id")
    ops["route_name"] = ops["route_id"].map(T["routes"].set_index("route_id")["route_name"])
    return bk, ps, ev, cap, ops


def monthly_frame(bk, ps, ev, cap, ops):
    rows = []
    for m in sorted(bk["journey_month"].unique()):
        d = compute_kpis(bk[bk.journey_month == m], ps[ps.journey_month == m], ev[ev.journey_month == m],
                         cap[cap.journey_month == m], ops[ops.journey_month == m])
        rows.append(dict(journey_month=m, **d))
    df = pd.DataFrame(rows)
    df["bookings_growth"] = df["total_bookings"].pct_change()
    df["bookings_per_run_growth"] = df["bookings_per_run"].pct_change()
    return df


def class_runs_frame(ps, cap, bk):
    cnt = ps.groupby(["run_class_key", "final_status"]).size().unstack(fill_value=0)
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled"):
        if s not in cnt:
            cnt[s] = 0
    init = ps[ps.initial_status == "Waitlisted"].groupby("run_class_key").size().rename("initial_wl_pax")
    nb = bk.groupby("run_class_key").size().rename("bookings")
    df = cap.merge(cnt, left_on="run_class_key", right_index=True, how="left").merge(init, left_on="run_class_key", right_index=True, how="left") \
            .merge(nb, left_on="run_class_key", right_index=True, how="left").fillna({"Confirmed": 0, "RAC": 0, "Waitlisted": 0, "Cancelled": 0, "initial_wl_pax": 0, "bookings": 0})
    df = df.rename(columns={"Confirmed": "confirmed_pax", "RAC": "rac_pax", "Waitlisted": "wl_final_pax", "Cancelled": "cancelled_pax"})
    for c in ("confirmed_pax", "rac_pax", "wl_final_pax", "cancelled_pax", "initial_wl_pax", "bookings"):
        df[c] = df[c].astype(int)
    df["passengers"] = df[["confirmed_pax", "rac_pax", "wl_final_pax", "cancelled_pax"]].sum(axis=1)
    df["booked_seats"] = df["confirmed_pax"] + cfg.RAC_SEAT_WEIGHT * df["rac_pax"]
    df["occupancy"] = df["booked_seats"] / df["total_seats"]
    df["confirmed_occupancy"] = df["confirmed_pax"] / df["total_seats"]
    df["waitlist_pressure"] = df["wl_final_pax"] / df["total_seats"]
    return df


def _save(df, path):
    df = df.copy(); df["data_origin"] = "DERIVED"
    df.to_csv(path, index=False)


def write_derived(T, out_dir=DERIVED_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    bk, ps, ev, cap, ops = _prep(T)
    monthly = monthly_frame(bk, ps, ev, cap, ops)
    _save(monthly, out_dir / "monthly_kpis.csv")
    crf = class_runs_frame(ps, cap, bk)
    cal = T["calendar"].set_index("calendar_date")
    crf["weekday"] = pd.to_datetime(crf["journey_date"].astype(str)).dt.day_name()
    crf["season"] = crf["journey_date"].map(cal["season"]); crf["is_peak_travel_period"] = crf["journey_date"].map(cal["is_peak_travel_period"])
    crf = crf.merge(T["trains"][["train_id", "train_number", "train_type"]], on="train_id")
    _save(crf[["run_class_key", "capacity_id", "train_id", "train_number", "train_type", "route_name", "journey_date", "journey_month", "weekday", "season",
         "is_peak_travel_period", "travel_class", "coaches_attached", "seats_per_coach", "total_seats", "rac_berths", "wl_limit", "bookings",
         "passengers", "confirmed_pax", "rac_pax", "wl_final_pax", "cancelled_pax", "initial_wl_pax", "booked_seats", "occupancy",
         "confirmed_occupancy", "waitlist_pressure"]], out_dir / "occupancy_class_runs.csv")
    run_agg = crf.groupby(["train_id", "journey_date"]).agg(class_runs=("capacity_id", "size"), seats=("total_seats", "sum"), bookings=("bookings", "sum"),
                                                              passengers=("passengers", "sum"), booked_seats=("booked_seats", "sum")).reset_index()
    tr = ops.merge(run_agg, left_on=["train_id", "run_date"], right_on=["train_id", "journey_date"], how="left").drop(columns="journey_date")
    tr["season"] = tr["run_date"].map(cal["season"]); tr["has_delay"] = tr["arrival_delay_min"].notna()
    tr["on_time"] = np.where(tr["has_delay"], tr["arrival_delay_min"] <= cfg.ON_TIME_THRESHOLD_MIN, np.nan)
    tr["delay_positive"] = tr["arrival_delay_min"].clip(lower=0)
    tr["run_occupancy"] = tr["booked_seats"] / tr["seats"]
    tr[["operation_id", "train_id", "train_number", "train_type", "route_name", "run_date", "journey_month", "season", "departure_delay_min",
        "arrival_delay_min", "has_delay", "on_time", "delay_positive", "class_runs", "seats", "bookings", "passengers", "booked_seats",
        "run_occupancy"]].pipe(_save, out_dir / "train_runs.csv")
    g = ps.groupby(["lead_bucket", "travel_class"]).agg(passengers=("passenger_id", "size"), cancelled_pax=("final_status", lambda s: int((s == "Cancelled").sum())),
                                                        initial_wl_pax=("initial_status", lambda s: int((s == "Waitlisted").sum()))).reset_index()
    g["passenger_cancellation_rate"] = g["cancelled_pax"] / g["passengers"]
    g["lead_bucket"] = pd.Categorical(g["lead_bucket"], LEAD_LABELS, ordered=True); g = g.sort_values(["lead_bucket", "travel_class"])
    _save(g, out_dir / "cancellation_by_lead_and_class.csv")
    rs = []
    for r, name in T["routes"].set_index("route_id")["route_name"].items():
        k = compute_kpis(bk[bk.route_name == name], ps[ps.route_name == name], ev[ev.route_name == name], cap[cap.route_name == name], ops[ops.route_name == name])
        rs.append(dict(route_id=r, route_name=name, simulated_runs=k["simulated_runs"], class_runs=k["class_runs"], bookings=k["total_bookings"],
                       passengers=k["total_passengers"], passengers_per_run=k["passengers_per_run"], seat_supply=k["seat_supply"], booked_seats=k["booked_seats"],
                       occupancy=k["occupancy"], wl_demand=k["wl_demand"], cancelled_pax=k["cancelled_passengers"],
                       passenger_cancellation_rate=k["passenger_cancellation_rate"], runs_with_delay=k["runs_with_delay"], otp=k["otp"], avg_delay=k["avg_delay"]))
    _save(pd.DataFrame(rs), out_dir / "route_summary.csv")
    e = ev.groupby(["journey_month", "cancellation_type", "status_at_cancellation"]).agg(events=("cancellation_id", "size"), passengers=("cancelled_passengers", "sum"),
            original_fare=("original_fare_amount", "sum"), charges=("cancellation_charge", "sum"), refunds=("refund_amount", "sum")).reset_index()
    _save(e, out_dir / "refund_events_summary.csv")
    mc = []
    for (m, c), _ in cap.groupby(["journey_month", "travel_class"]):
        s = crf[(crf.journey_month == m) & (crf.travel_class == c)]
        mc.append(dict(journey_month=m, travel_class=c, class_runs=len(s), seats=int(s.total_seats.sum()), bookings=int(s.bookings.sum()), passengers=int(s.passengers.sum()),
                       confirmed_pax=int(s.confirmed_pax.sum()), rac_pax=int(s.rac_pax.sum()), wl_final_pax=int(s.wl_final_pax.sum()),
                       initial_wl_pax=int(s.initial_wl_pax.sum()), cancelled_pax=int(s.cancelled_pax.sum())))
    _save(pd.DataFrame(mc), out_dir / "monthly_class_occupancy.csv")
    overall = compute_kpis(bk, ps, ev, cap, ops)
    ref = []
    for key, name, unit, nk, dk in KPI_SPEC:
        ref.append(dict(kpi_key=key, kpi=name, value=overall[key], unit=unit, numerator=overall[nk] if nk else "", denominator=overall[dk] if dk else "",
                        scope="full cleaned dataset (768 simulated runs)", data_origin="SYNTHETIC"))
    pd.DataFrame(ref).to_csv(cfg.REPORTS_DIR / "kpi_reference_values.csv", index=False)
    return dict(monthly=monthly, overall=overall)


def select_sample(T, per_month=SAMPLE_RUNS_PER_MONTH, seed=cfg.SEED + 3):
    """Run-complete sample: `per_month` simulated runs per journey month, with every booking of those runs."""
    bk, ps, ev, cap, ops = _prep(T)
    picks = []
    for m, g in ops.groupby("journey_month"):
        picks.append(g.sample(n=min(per_month, len(g)), random_state=seed + int(m.replace("-", ""))))
    sel = pd.concat(picks).sort_values(["run_date", "train_id"])
    keys = set(zip(sel["train_id"], sel["run_date"]))
    sb = bk[[(t, d) in keys for t, d in zip(bk["train_id"], bk["journey_date"])]]
    ids = set(sb["booking_id"])
    return dict(bk=sb, ps=ps[ps["booking_id"].isin(ids)], ev=ev[ev["booking_id"].isin(ids)],
                cap=cap[[(t, d) in keys for t, d in zip(cap["train_id"], cap["journey_date"])]],
                ops=ops[[(t, d) in keys for t, d in zip(ops["train_id"], ops["run_date"])]])


def write_sample(T, out_dir=EXCEL_SAMPLE_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    S = select_sample(T)
    S["bk"].to_csv(out_dir / "bookings.csv", index=False); S["ps"].to_csv(out_dir / "booking_passengers.csv", index=False)
    S["ev"].to_csv(out_dir / "cancellations.csv", index=False); S["cap"].to_csv(out_dir / "seat_capacity.csv", index=False)
    S["ops"].to_csv(out_dir / "train_operations.csv", index=False)
    k = compute_kpis(S["bk"], S["ps"], S["ev"], S["cap"], S["ops"])
    pd.DataFrame([dict(kpi_key=key, kpi=name, value=k[key], scope="Excel sample (2 runs per month)") for key, name, *_ in KPI_SPEC]).to_csv(
        cfg.REPORTS_DIR / "kpi_reference_values_excel_sample.csv", index=False)
    return S, k


if __name__ == "__main__":
    import clean_data as cl
    T = cl.read_clean()
    r = write_derived(T)
    S, k = write_sample(T)
    print("overall:", {x: (round(v, 4) if isinstance(v, float) else v) for x, v in r["overall"].items() if x in ("total_bookings", "total_passengers", "passenger_cancellation_rate", "occupancy", "wl_clearance_rate", "otp")})
    print("sample: runs", k["simulated_runs"], "bookings", k["total_bookings"], "passengers", k["total_passengers"], "class_runs", k["class_runs"],
          "| occ %.3f cancel %.3f" % (k["occupancy"], k["passenger_cancellation_rate"]))
