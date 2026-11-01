"""Reproducible Pandas cleaning and preparation pipeline.

The input tables were already cleaned in Phase 2 (defects repaired or rejected, documented in docs/data_quality_report.md). This pipeline
re-applies the project's rules idempotently, adds the derived columns and flags the analysis needs, and builds aggregation-ready fact tables.
Guarantees: NO row is removed (rows_in == rows_out for every rule) and nothing is imputed. Every rule is logged with the number of rows it
touched (`CleanResult.log`, written to reports/phase5_cleaning_log.csv). Source files are never modified; everything works on copies.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config as cfg

STATUS_ORDER = ["Confirmed", "RAC", "Waitlisted", "Cancelled"]
BOOKING_STATUS_ORDER = ["Confirmed", "RAC", "Waitlisted", "Cancelled", "Mixed"]
CLASS_ORDER = ["1A", "2A", "3A", "SL", "CC", "2S"]
LEAD_EDGES = [-1, 3, 14, 30, 60, 120]
LEAD_LABELS = ["0-3 days", "4-14 days", "15-30 days", "31-60 days", "61-120 days"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CANON_STATUS = {"confirmed": "Confirmed", "rac": "RAC", "waitlisted": "Waitlisted", "cancelled": "Cancelled", "mixed": "Mixed"}
CATEGORICAL = {"booking_passengers": {"initial_status": STATUS_ORDER[:3], "final_status": STATUS_ORDER, "age_band": ["Child", "Adult", "Senior", "Unknown"]},
               "bookings": {"booking_status": BOOKING_STATUS_ORDER, "travel_class": CLASS_ORDER}, "seat_capacity": {"travel_class": CLASS_ORDER},
               "cancellations": {"cancellation_type": ["Passenger", "System"], "status_at_cancellation": STATUS_ORDER[:3]},
               "trains": {"train_type": ["Premium", "Superfast", "Express"]}}


@dataclass
class CleanResult:
    tables: dict          # typed base tables (all original columns kept, original rows kept)
    facts: dict           # aggregation-ready analytical datasets
    log: pd.DataFrame     # one row per cleaning rule


def _cat(s: pd.Series, order: list) -> pd.Series:
    return pd.Categorical(s.astype(str), categories=order, ordered=True)


def run_cleaning(tables: dict, rac_weight: float = cfg.RAC_SEAT_WEIGHT, on_time_min: float = cfg.ON_TIME_THRESHOLD_MIN) -> CleanResult:
    t = {k: v.copy() for k, v in tables.items()}          # never touch the loaded frames in place
    n_in = {k: len(v) for k, v in t.items()}
    log = []

    def rule(rule_id, table, description, affected, action, rows_out=None):
        log.append(dict(rule_id=rule_id, table=table, description=description, rows_in=n_in.get(table, np.nan), rows_out=len(t[table]) if table in t and rows_out is None else rows_out,
                        rows_affected=int(affected), action=action))

    # C-01 text normalisation: trim whitespace and map status labels to their canonical spelling (idempotent; expected to change nothing)
    for name, df in t.items():
        changed = 0
        for c in [c for c in df.columns if pd.api.types.is_string_dtype(df[c])]:
            s = df[c]; stripped = s.str.strip()
            changed += int((s.notna() & (s != stripped)).sum()); df[c] = stripped
        rule("C-01", name, "trim leading/trailing whitespace in text columns", changed, "values trimmed; no rows removed")
    for name, cols in {"booking_passengers": ["initial_status", "final_status"], "bookings": ["booking_status"], "cancellations": ["status_at_cancellation"]}.items():
        changed = 0
        for c in cols:
            mapped = t[name][c].str.lower().map(CANON_STATUS)
            changed += int((mapped.notna() & (mapped != t[name][c])).sum()); t[name][c] = mapped.fillna(t[name][c])
        rule("C-02", name, "map status labels to canonical spelling (Confirmed, RAC, Waitlisted, Cancelled, Mixed)", changed, "labels normalised; unknown labels kept and caught by validation")
    # C-03 types: ordered categoricals for statuses, classes and age bands (consistent order in tables and charts)
    for name, cols in CATEGORICAL.items():
        for c, order in cols.items():
            t[name][c] = _cat(t[name][c], order)
        rule("C-03", name, f"convert {', '.join(cols)} to ordered categorical", 0, "dtype conversion only")
    # C-04 duplicates: detected and reported, never silently removed (Phase 2 already removed the injected duplicates)
    keys = {"bookings": ["booking_id"], "booking_passengers": ["passenger_id"], "cancellations": ["cancellation_id"], "seat_capacity": ["train_id", "journey_date", "travel_class"],
            "train_operations": ["train_id", "run_date"]}
    for name, k in keys.items():
        rule("C-04", name, f"detect duplicate rows on {k}", t[name].duplicated(k).sum(), "flagged only; nothing removed (0 expected after Phase 2)")
    # C-05 missing values: documented, retained, never imputed
    ops = t["train_operations"]; ops["delay_missing"] = ops.arrival_delay_min.isna()
    rule("C-05", "train_operations", "arrival_delay_min is NULL: flag delay_missing, keep NULL", ops.delay_missing.sum(), "retained as NULL; excluded from delay KPIs; not imputed")
    ps = t["booking_passengers"]; ps["age_missing"] = ps.age_band.astype(str) == "Unknown"
    rule("C-05", "booking_passengers", "age_band is 'Unknown': flag age_missing, keep 'Unknown'", ps.age_missing.sum(), "retained; no age imputed")

    # ---- derived columns: calendar attributes, lead time, flags
    cal = t["calendar"].set_index("calendar_date")
    trn = t["trains"].merge(t["routes"][["route_id", "route_name", "distance_km"]], on="route_id", validate="m:1").set_index("train_id")
    bk = t["bookings"]
    bk["journey_month"] = bk.journey_date.dt.strftime("%Y-%m")
    bk["weekday"] = pd.Categorical(bk.journey_date.dt.day_name(), categories=WEEKDAYS, ordered=True)
    bk["is_weekend"] = bk.journey_date.dt.dayofweek >= 5
    bk["season"] = bk.journey_date.map(cal.season)
    bk["is_peak"] = bk.journey_date.map(cal.is_peak_travel_period)
    bk["is_holiday"] = bk.journey_date.map(cal.is_holiday)
    bk["lead_days"] = (bk.journey_date - bk.booking_ts.dt.normalize()).dt.days
    bk["lead_bucket"] = pd.cut(bk.lead_days, LEAD_EDGES, labels=LEAD_LABELS)
    for c in ("train_number", "train_name", "train_type", "route_name"):
        bk[c] = bk.train_id.map(trn[c])
    rule("C-06", "bookings", "derive journey_month, weekday, is_weekend, season, is_peak, is_holiday, lead_days, lead_bucket, train and route attributes", len(bk), "columns added; no rows removed")
    ps["is_cancelled"] = (ps.final_status == "Cancelled"); ps["is_initial_wl"] = (ps.initial_status == "Waitlisted")
    ps["is_cleared_wl"] = ps.is_initial_wl & ps.final_status.isin(["Confirmed", "RAC"]); ps["is_uncleared_wl"] = (ps.final_status == "Waitlisted")
    ps["seat_equivalent"] = np.select([ps.final_status == "Confirmed", ps.final_status == "RAC"], [1.0, rac_weight], default=0.0)
    rule("C-06", "booking_passengers", "derive is_cancelled, is_initial_wl, is_cleared_wl, is_uncleared_wl, seat_equivalent (RAC weight is a configurable assumption)", len(ps), "columns added; no rows removed")
    ops["journey_month"] = ops.run_date.dt.strftime("%Y-%m")
    ops["on_time"] = pd.array(np.where(ops.arrival_delay_min.isna(), pd.NA, ops.arrival_delay_min <= on_time_min), dtype="boolean")
    ops["delay_positive"] = ops.arrival_delay_min.clip(lower=0)
    rule("C-06", "train_operations", "derive journey_month, on_time (NULL where the delay is missing), delay_positive (early = 0)", len(ops), "columns added; no rows removed")

    # ---- validation flags (all expected to be False; flagged rows would be kept and reported, not dropped)
    flags = {"flag_nonpositive_fare": int((ps.fare_amount <= 0).sum() + (bk.total_fare <= 0).sum()), "flag_lead_out_of_range": int(((bk.lead_days < 0) | (bk.lead_days > cfg.MAX_ADVANCE_DAYS)).sum()),
             "flag_negative_refund": int((t["cancellations"].refund_amount < 0).sum())}
    for k, v in flags.items():
        rule("C-07", "bookings" if "fare" in k or "lead" in k else "cancellations", f"validation flag {k}", v, "flag counted; rows retained")

    # ---- aggregation-ready fact tables
    book_cols = ["booking_id", "train_id", "train_number", "train_name", "train_type", "route_id", "route_name", "journey_date", "journey_month", "weekday", "is_weekend", "season", "is_peak",
                 "is_holiday", "travel_class", "lead_days", "lead_bucket"]
    pf = ps.merge(bk[book_cols], on="booking_id", how="left", validate="m:1")
    assert pf.train_id.notna().all(), "passenger rows without a booking"
    per_booking = pf.groupby("booking_id").agg(n_pax=("passenger_id", "size"), n_cancelled=("is_cancelled", "sum"), n_initial_wl=("is_initial_wl", "sum"), n_uncleared_wl=("is_uncleared_wl", "sum"))
    bf = bk.merge(per_booking, left_on="booking_id", right_index=True, validate="1:1")
    bf["is_mixed"] = bf.booking_status == "Mixed"
    bf["partially_cancelled"] = (bf.n_cancelled > 0) & (bf.n_cancelled < bf.n_pax)
    ef = t["cancellations"].merge(bk[["booking_id", "journey_month", "journey_date", "travel_class", "train_id", "route_name", "train_type"]], on="booking_id", validate="m:1")

    g = pf.assign(is_conf=(pf.final_status == "Confirmed"), is_rac=(pf.final_status == "RAC"), is_wl=(pf.final_status == "Waitlisted")).groupby(["train_id", "journey_date", "travel_class"], observed=True)
    agg = g.agg(bookings=("booking_id", "nunique"), passengers=("passenger_id", "size"), confirmed_pax=("is_conf", "sum"), rac_pax=("is_rac", "sum"), wl_final_pax=("is_wl", "sum"),
                cancelled_pax=("is_cancelled", "sum"), initial_wl_pax=("is_initial_wl", "sum"), gross_fare=("fare_amount", "sum")).reset_index()
    agg["travel_class"] = _cat(agg.travel_class, CLASS_ORDER)
    cap = t["seat_capacity"].merge(agg, on=["train_id", "journey_date", "travel_class"], how="left", validate="1:1")
    for c in ["bookings", "passengers", "confirmed_pax", "rac_pax", "wl_final_pax", "cancelled_pax", "initial_wl_pax"]:
        cap[c] = cap[c].fillna(0).astype("int64")
    cap["gross_fare"] = cap.gross_fare.fillna(0.0)
    cap["booked_seats"] = cap.confirmed_pax + rac_weight * cap.rac_pax
    cap["occupancy"] = cap.booked_seats / cap.total_seats
    cap["waitlist_pressure"] = cap.wl_final_pax / cap.total_seats
    cap["demand_per_seat"] = cap.passengers / cap.total_seats          # EDA measure (all requested passengers per seat); NOT an approved KPI
    cap["journey_month"] = cap.journey_date.dt.strftime("%Y-%m")
    cap["weekday"] = pd.Categorical(cap.journey_date.dt.day_name(), categories=WEEKDAYS, ordered=True)
    cap["is_weekend"] = cap.journey_date.dt.dayofweek >= 5
    cap["season"] = cap.journey_date.map(cal.season); cap["is_peak"] = cap.journey_date.map(cal.is_peak_travel_period)
    for c in ("train_number", "train_type", "route_name"):
        cap[c] = cap.train_id.map(trn[c])
    run_agg = cap.groupby(["train_id", "journey_date"]).agg(class_runs=("capacity_id", "size"), seats=("total_seats", "sum"), bookings=("bookings", "sum"), passengers=("passengers", "sum"),
                                                           confirmed_pax=("confirmed_pax", "sum"), rac_pax=("rac_pax", "sum"), wl_final_pax=("wl_final_pax", "sum"),
                                                           initial_wl_pax=("initial_wl_pax", "sum"), cancelled_pax=("cancelled_pax", "sum"), booked_seats=("booked_seats", "sum"), gross_fare=("gross_fare", "sum")).reset_index()
    rf = ops.merge(run_agg, left_on=["train_id", "run_date"], right_on=["train_id", "journey_date"], how="left", validate="1:1").drop(columns="journey_date")
    rf["occupancy"] = rf.booked_seats / rf.seats
    rf["weekday"] = pd.Categorical(rf.run_date.dt.day_name(), categories=WEEKDAYS, ordered=True); rf["is_weekend"] = rf.run_date.dt.dayofweek >= 5
    rf["season"] = rf.run_date.map(cal.season); rf["is_peak"] = rf.run_date.map(cal.is_peak_travel_period)
    for c in ("train_number", "train_name", "train_type", "route_id", "route_name"):
        rf[c] = rf.train_id.map(trn[c])
    rf["distance_km"] = rf.route_id.map(trn.set_index("route_id").distance_km.groupby(level=0).first())
    facts = dict(passenger_fact=pf, booking_fact=bf, event_fact=ef, class_run_fact=cap, run_fact=rf)
    for k, v in facts.items():
        rule("C-08", k, "build aggregation-ready fact table", len(v), f"{len(v):,} rows", rows_out=len(v))
    out_tables = {k: v for k, v in t.items()}
    out_tables["bookings"] = bk
    # the central guarantee: no observation was dropped
    for name in tables:
        assert len(out_tables[name]) == n_in[name], f"{name}: row count changed during cleaning"
    assert len(pf) == n_in["booking_passengers"] and len(bf) == n_in["bookings"] and len(ef) == n_in["cancellations"] and len(cap) == n_in["seat_capacity"] and len(rf) == n_in["train_operations"]
    return CleanResult(tables=out_tables, facts=facts, log=pd.DataFrame(log))
