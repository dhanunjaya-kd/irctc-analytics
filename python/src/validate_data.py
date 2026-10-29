"""Validate the cleaned dataset against the documented rules (docs/data_dictionary.md, BR-01 .. BR-17).

Each check reports the number of VIOLATING records; a check passes when that number is 0.
"""
import re
from datetime import date

import numpy as np
import pandas as pd

import config as cfg

PK = {
    "stations": ["station_id"], "routes": ["route_id"], "trains": ["train_id"],
    "train_stops": ["train_id", "stop_sequence"], "calendar": ["calendar_date"],
    "seat_capacity": ["capacity_id"], "train_operations": ["operation_id"], "bookings": ["booking_id"],
    "booking_passengers": ["passenger_id"], "cancellations": ["cancellation_id"],
}
NATURAL_UNIQUE = {
    "seat_capacity": ["train_id", "journey_date", "travel_class"], "train_operations": ["train_id", "run_date"],
    "bookings": ["booking_reference"], "trains": ["train_number"], "stations": ["station_code"],
}
FK = [  # child table, child column(s), parent table, parent column(s)
    ("routes", ["origin_station_id"], "stations", ["station_id"]), ("routes", ["destination_station_id"], "stations", ["station_id"]),
    ("trains", ["route_id"], "routes", ["route_id"]), ("train_stops", ["train_id"], "trains", ["train_id"]),
    ("train_stops", ["station_id"], "stations", ["station_id"]), ("seat_capacity", ["train_id"], "trains", ["train_id"]),
    ("train_operations", ["train_id"], "trains", ["train_id"]), ("bookings", ["train_id"], "trains", ["train_id"]),
    ("bookings", ["route_id"], "routes", ["route_id"]), ("bookings", ["boarding_station_id"], "stations", ["station_id"]),
    ("bookings", ["destination_station_id"], "stations", ["station_id"]),
    ("booking_passengers", ["booking_id"], "bookings", ["booking_id"]),
    ("cancellations", ["booking_id"], "bookings", ["booking_id"]),
]
PII_COLUMN_TOKENS = ["email", "phone", "mobile", "address", "aadhaar", "aadhar", "pan_number", "dob", "birth", "passenger_name",
                     "first_name", "last_name", "passport"]
STD = cfg.CLASS_SEATS
STATUS_INIT = {"Confirmed", "RAC", "Waitlisted"}
STATUS_FINAL = {"Confirmed", "RAC", "Waitlisted", "Cancelled"}
ALLOWED_TRANSITIONS = {("Confirmed", "Confirmed"), ("Confirmed", "Cancelled"),
                       ("RAC", "RAC"), ("RAC", "Confirmed"), ("RAC", "Cancelled"),
                       ("Waitlisted", "Waitlisted"), ("Waitlisted", "RAC"), ("Waitlisted", "Confirmed"), ("Waitlisted", "Cancelled")}


def run_checks(T):
    out = []

    def add(cid, desc, violations, detail=""):
        out.append(dict(check=cid, description=desc, violations=int(violations), passed=int(violations) == 0, detail=detail))

    bk, ps, ev, cap = T["bookings"], T["booking_passengers"], T["cancellations"], T["seat_capacity"]
    ops, stops, trains, routes, st = T["train_operations"], T["train_stops"], T["trains"], T["routes"], T["stations"]
    cal = T["calendar"]

    # ------------------------------------------------ keys
    for t, cols in PK.items():
        df = T[t]
        add(f"PK-{t}", f"{t}: primary key {cols} is unique and not null", df.duplicated(cols).sum() + df[cols].isna().any(axis=1).sum())
    for t, cols in NATURAL_UNIQUE.items():
        add(f"UQ-{t}", f"{t}: natural key {cols} is unique", T[t].duplicated(cols).sum())

    # ------------------------------------------------ foreign keys
    for child, ccols, parent, pcols in FK:
        keys = set(map(tuple, T[parent][pcols].to_numpy().tolist()))
        vals = T[child][ccols].to_numpy().tolist()
        add(f"FK-{child}.{'+'.join(ccols)}", f"{child}.{ccols} references {parent}.{pcols}", sum(tuple(v) not in keys for v in vals))
    linked = ps["cancellation_id"].dropna().astype("int64")
    add("FK-booking_passengers.cancellation_id", "booking_passengers.cancellation_id references cancellations", (~linked.isin(set(ev["cancellation_id"]))).sum())

    # ------------------------------------------------ BR-01 status domains
    add("BR-01", "initial_status in {Confirmed, RAC, Waitlisted}; final_status in {Confirmed, RAC, Waitlisted, Cancelled}",
        (~ps["initial_status"].isin(STATUS_INIT)).sum() + (~ps["final_status"].isin(STATUS_FINAL)).sum())

    # ------------------------------------------------ BR-02 booking status roll-up
    grp = ps.groupby("booking_id")["final_status"]
    roll = grp.first().where(grp.nunique() == 1, "Mixed")
    add("BR-02", "booking_status equals the roll-up of passenger final_status (single status, else 'Mixed')",
        (bk["booking_id"].map(roll) != bk["booking_status"]).sum() + (~bk["booking_status"].isin(STATUS_FINAL | {"Mixed"})).sum())

    # ------------------------------------------------ BR-03 counts and fares
    n_rows = ps.groupby("booking_id").size()
    fsum = ps.groupby("booking_id")["fare_amount"].sum()
    add("BR-03a", "num_passengers equals the number of passenger rows", (bk["booking_id"].map(n_rows) != bk["num_passengers"]).sum())
    add("BR-03b", "total_fare equals SUM(passenger fare_amount)", ((bk["booking_id"].map(fsum) - bk["total_fare"]).abs() > 0.005).sum())
    seqs = ps.groupby("booking_id")["passenger_seq"].agg(["min", "max", "count"])
    add("BR-03c", "passenger_seq runs 1..n within each booking", ((seqs["min"] != 1) | (seqs["max"] != seqs["count"])).sum())

    # ------------------------------------------------ BR-04 booking timing
    first_dep = stops[stops["stop_sequence"] == 1].set_index("train_id")["departure_time"]
    dep_dt = pd.to_datetime(bk["journey_date"].astype(str)) + pd.to_timedelta(bk["train_id"].map(first_dep))
    chart = dep_dt - pd.Timedelta(hours=cfg.CHART_PREP_HOURS)
    lead = (pd.to_datetime(bk["journey_date"].astype(str)) - bk["booking_ts"].dt.normalize()).dt.days
    add("BR-04a", "booking_ts is on or before the journey date and lead time is 0..120 days", ((lead < 0) | (lead > cfg.MAX_ADVANCE_DAYS)).sum())
    add("BR-04b", "booking_ts is before chart preparation (departure - 4h)", (bk["booking_ts"] > chart).sum())
    add("BR-04c", "journey_date inside the approved window 2024-09-01..2026-08-31",
        ((bk["journey_date"] < cfg.JOURNEY_START) | (bk["journey_date"] > cfg.JOURNEY_END)).sum())

    # ------------------------------------------------ BR-05 run days and operations row
    rd = trains.set_index("train_id")["run_days"]
    wd = pd.to_datetime(bk["journey_date"].astype(str)).dt.weekday
    on_day = [rd[t][w] == "Y" for t, w in zip(bk["train_id"], wd)]
    add("BR-05a", "booking journey_date falls on a scheduled run day of the train", (~np.array(on_day)).sum())
    ops_keys = set(zip(ops["train_id"], ops["run_date"]))
    add("BR-05b", "each booking's (train, journey_date) has a train_operations row",
        sum((t, d) not in ops_keys for t, d in zip(bk["train_id"], bk["journey_date"])))
    wd_c = pd.to_datetime(cap["journey_date"].astype(str)).dt.weekday
    add("BR-05c", "seat_capacity rows fall on scheduled run days with an operations row",
        sum((rd[t][w] != "Y") or ((t, d) not in ops_keys) for t, w, d in zip(cap["train_id"], wd_c, cap["journey_date"])))

    # ------------------------------------------------ BR-06 end-to-end stations and route
    tr_route = trains.set_index("train_id")["route_id"]
    rt = routes.set_index("route_id")
    add("BR-06a", "booking route_id equals the train's route", (bk["train_id"].map(tr_route) != bk["route_id"]).sum())
    add("BR-06b", "boarding/destination stations equal the route origin/destination",
        ((bk["route_id"].map(rt["origin_station_id"]) != bk["boarding_station_id"]) |
         (bk["route_id"].map(rt["destination_station_id"]) != bk["destination_station_id"])).sum())
    add("BR-06c", "boarding and destination stations differ", (bk["boarding_station_id"] == bk["destination_station_id"]).sum())

    # ------------------------------------------------ BR-07 / BR-08 capacity and occupancy
    cap_keys = set(zip(cap["train_id"], cap["journey_date"], cap["travel_class"]))
    add("BR-07", "each booking's (train, date, class) has a seat_capacity row",
        sum(k not in cap_keys for k in zip(bk["train_id"], bk["journey_date"], bk["travel_class"])))
    m = ps.merge(bk[["booking_id", "train_id", "journey_date", "travel_class"]], on="booking_id")
    cnt = m.groupby(["train_id", "journey_date", "travel_class", "final_status"]).size().unstack(fill_value=0)
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled"):
        if s not in cnt:
            cnt[s] = 0
    cnt = cnt.reset_index()
    occ = cap.merge(cnt, on=["train_id", "journey_date", "travel_class"], how="left").fillna(0)
    add("BR-08a", "Confirmed passengers <= total_seats - rac_berths", (occ["Confirmed"] > occ["total_seats"] - occ["rac_berths"]).sum())
    add("BR-08b", "RAC passengers <= 2 x rac_berths (no RAC where rac_berths = 0)", (occ["RAC"] > 2 * occ["rac_berths"]).sum())
    seat_eq = occ["Confirmed"] + cfg.RAC_SEAT_WEIGHT * occ["RAC"]
    add("BR-08c", "Confirmed + RAC_weight x RAC <= total_seats (occupancy <= 100%)", (seat_eq > occ["total_seats"] + 1e-9).sum())
    add("BR-08d", "Waitlisted passengers <= wl_limit", (occ["Waitlisted"] > occ["wl_limit"]).sum())

    # ------------------------------------------------ BR-09 capacity arithmetic
    add("BR-09a", "total_seats = coaches_attached x seats_per_coach", (cap["total_seats"] != cap["coaches_attached"] * cap["seats_per_coach"]).sum())
    add("BR-09b", "seats_per_coach equals the class standard", (cap["seats_per_coach"] != cap["travel_class"].map(STD)).sum())

    # ------------------------------------------------ BR-10 cancellation linkage
    has_link = ps["cancellation_id"].notna()
    need_link = ps["final_status"].isin({"Cancelled", "Waitlisted"})
    add("BR-10a", "cancellation_id is set exactly when final_status is Cancelled or Waitlisted", (has_link != need_link).sum())
    ctype = ev.set_index("cancellation_id")["cancellation_type"]
    cbook = ev.set_index("cancellation_id")["booking_id"]
    lp = ps[has_link].copy()
    lp["cid"] = lp["cancellation_id"].astype("int64")
    exp = lp["cid"].map(ctype).map({"Passenger": "Cancelled", "System": "Waitlisted"})
    add("BR-10b", "Passenger events link Cancelled passengers; System events link Waitlisted passengers", (exp != lp["final_status"]).sum())
    add("BR-10c", "linked passengers belong to the event's booking", (lp["cid"].map(cbook) != lp["booking_id"]).sum())

    # ------------------------------------------------ BR-11 event arithmetic
    n_link = lp.groupby("cid").size()
    f_link = lp.groupby("cid")["fare_amount"].sum()
    add("BR-11a", "cancelled_passengers equals the number of linked passengers (and >= 1)",
        (ev["cancellation_id"].map(n_link).fillna(0) != ev["cancelled_passengers"]).sum() + (ev["cancelled_passengers"] < 1).sum())
    add("BR-11b", "original_fare_amount equals SUM(linked passenger fares)",
        ((ev["cancellation_id"].map(f_link).fillna(0) - ev["original_fare_amount"]).abs() > 0.005).sum())
    add("BR-11c", "refund_amount + cancellation_charge = original_fare_amount; refund and charge >= 0",
        ((ev["refund_amount"] + ev["cancellation_charge"] - ev["original_fare_amount"]).abs() > 0.005).sum()
        + (ev["refund_amount"] < 0).sum() + (ev["cancellation_charge"] < 0).sum())
    add("BR-11d", "status_at_cancellation in {Confirmed, RAC, Waitlisted}; System events are Waitlisted; type in {Passenger, System}",
        (~ev["status_at_cancellation"].isin(STATUS_INIT)).sum() + (~ev["cancellation_type"].isin({"Passenger", "System"})).sum()
        + ((ev["cancellation_type"] == "System") & (ev["status_at_cancellation"] != "Waitlisted")).sum())
    ev_per_pass_status = lp.groupby("cid").size()
    add("BR-11e", "every cancellation event has at least one linked passenger", (~ev["cancellation_id"].isin(ev_per_pass_status.index)).sum())

    # ------------------------------------------------ BR-12 cancellation timing
    b_ts = ev["booking_id"].map(bk.set_index("booking_id")["booking_ts"])
    b_chart = ev["booking_id"].map(chart.set_axis(bk["booking_id"]))
    add("BR-12", "booking_ts <= cancellation_ts <= chart preparation time",
        (ev["cancellation_ts"] < b_ts).sum() + (ev["cancellation_ts"] > b_chart).sum())

    # ------------------------------------------------ BR-13 train stops
    s = stops.sort_values(["train_id", "stop_sequence"])
    g = s.groupby("train_id")
    bad_seq = (g["stop_sequence"].max() != g["stop_sequence"].count()) | (g["stop_sequence"].min() != 1)
    inc = s.groupby("train_id")["distance_from_origin_km"].apply(lambda x: bool((x.diff().dropna() > 0).all()))
    first_ok = s[s["stop_sequence"] == 1].set_index("train_id")            # explicit rows: groupby.first() would skip nulls
    last_ok = s.loc[g["stop_sequence"].idxmax()].set_index("train_id")
    t_route = trains.set_index("train_id")["route_id"]
    ends_bad = ((first_ok["station_id"] != t_route.map(rt["origin_station_id"]).reindex(first_ok.index)) |
                (last_ok["station_id"] != t_route.map(rt["destination_station_id"]).reindex(last_ok.index)) |
                first_ok["arrival_time"].notna() | last_ok["departure_time"].notna())
    add("BR-13", "train_stops: sequence 1..n, distance strictly increasing, terminals match the route",
        bad_seq.sum() + (~inc).sum() + ends_bad.sum())

    # ------------------------------------------------ BR-14 no PII
    bad_cols = [(t, c) for t, df in T.items() for c in df.columns if any(tok in c.lower() for tok in PII_COLUMN_TOKENS)]
    pat_hits = 0
    for t in ("bookings", "booking_passengers", "cancellations", "stations", "trains"):
        for c in T[t].select_dtypes(include=["object", "string"]).columns:
            col = T[t][c].dropna().astype(str)
            pat_hits += col.str.contains(r"@|\b\d{10}\b", regex=True).sum()
    add("BR-14", "no personally identifiable columns or values (name, e-mail, phone, address, ID numbers)", len(bad_cols) + pat_hits)

    # ------------------------------------------------ BR-15 numeric ranges, BR-16 station codes
    add("BR-15", "fares > 0, passengers per booking 1..6, refunds/charges >= 0",
        (ps["fare_amount"] <= 0).sum() + (bk["total_fare"] <= 0).sum() + ((bk["num_passengers"] < 1) | (bk["num_passengers"] > cfg.MAX_PASSENGERS)).sum())
    codes = st["station_code"]
    add("BR-16", "station_code unique, upper-case, trimmed", codes.duplicated().sum() + (codes != codes.str.strip().str.upper()).sum())

    # ------------------------------------------------ BR-17 status transitions
    add("BR-17", "no demotion between initial and final passenger status",
        sum((a, b_) not in ALLOWED_TRANSITIONS for a, b_ in zip(ps["initial_status"], ps["final_status"])))

    # ------------------------------------------------ other domains
    add("DOM-class", "travel_class in {1A, 2A, 3A, SL, CC, 2S} for bookings and capacity",
        (~bk["travel_class"].isin(STD)).sum() + (~cap["travel_class"].isin(STD)).sum())
    add("DOM-age", "age_band in {Child, Adult, Senior, Unknown}", (~ps["age_band"].isin({"Child", "Adult", "Senior", "Unknown"})).sum())
    add("DOM-delay", "non-null delays inside -60..1440 minutes",
        ((ops["arrival_delay_min"].dropna() < cfg.DELAY_SANITY_MIN) | (ops["arrival_delay_min"].dropna() > cfg.DELAY_SANITY_MAX)).sum())
    origin_bad = sum((T[t]["data_origin"] != "SYNTHETIC").sum() for t in T if "data_origin" in T[t])
    add("DOM-origin", "every row is labelled data_origin = SYNTHETIC", origin_bad)

    # ------------------------------------------------ size requirements
    months = pd.Series(pd.to_datetime(bk["journey_date"].astype(str))).dt.to_period("M").nunique()
    add("SIZE-bookings", f"at least 100,000 bookings (found {len(bk):,})", max(0, 100_000 - len(bk)))
    add("SIZE-trains", f"at least 50 trains (found {len(trains)})", max(0, 50 - len(trains)))
    add("SIZE-stations", f"at least 30 stations (found {len(st)})", max(0, 30 - len(st)))
    add("SIZE-months", f"at least 24 months of journeys (found {months})", max(0, 24 - months))
    return out


def format_results(results):
    lines = []
    for r in results:
        lines.append(f"{'PASS' if r['passed'] else 'FAIL'}  {r['check']:<38} violations={r['violations']:<6} {r['description']}")
    n_pass = sum(r["passed"] for r in results)
    lines.append(f"\n{n_pass}/{len(results)} checks passed")
    return "\n".join(lines)
