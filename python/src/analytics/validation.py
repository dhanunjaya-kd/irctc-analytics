"""Python data-validation checks on the loaded cleaned tables (independent of python/src/validate_data.py and of the PostgreSQL checks).

Each check returns the number of violating records (0 = PASS). Important counts are compared with the Phase 2 validated results
(reports/data_quality/row_movement.csv). Business rules BR-01..BR-17 are those of docs/data_dictionary.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg
from .data_loader import RELATIONSHIPS, relationship_report

PK = {"stations": ["station_id"], "routes": ["route_id"], "trains": ["train_id"], "train_stops": ["train_id", "stop_sequence"], "calendar": ["calendar_date"],
      "seat_capacity": ["capacity_id"], "train_operations": ["operation_id"], "bookings": ["booking_id"], "booking_passengers": ["passenger_id"], "cancellations": ["cancellation_id"]}
ALLOWED_NULL = {"train_stops": ["arrival_time", "departure_time"], "calendar": ["holiday_name", "peak_period_name"], "train_operations": ["arrival_delay_min"], "booking_passengers": ["cancellation_id"]}
CLASSES = {"1A": 24, "2A": 46, "3A": 64, "SL": 72, "CC": 78, "2S": 108}
JOURNEY_START, JOURNEY_END = pd.Timestamp(cfg.JOURNEY_START), pd.Timestamp(cfg.JOURNEY_END)


def _chart_prep(bookings: pd.DataFrame, stops: pd.DataFrame, date_col: str) -> pd.Series:
    dep = pd.to_timedelta(stops.loc[stops.stop_sequence == 1].drop_duplicates("train_id").set_index("train_id")["departure_time"])
    return bookings[date_col] + bookings["train_id"].map(dep) - pd.Timedelta(hours=cfg.CHART_PREP_HOURS)


def run_validation(tables: dict, reference: dict | None = None, rac_weight: float = cfg.RAC_SEAT_WEIGHT) -> pd.DataFrame:
    """All checks as a DataFrame (check_id, category, description, violations, passed). Never raises on bad data: an unexpected internal error becomes a failing
    VALIDATION-INTERNAL-ERROR row, and lookups tolerate duplicated keys (the duplicate checks report them)."""
    res: list = []
    try:
        _run_checks(tables, reference, rac_weight, res)
    except Exception as exc:
        res.append(dict(check_id="VALIDATION-INTERNAL-ERROR", category="INTERNAL", description=f"validation stopped early: {type(exc).__name__}: {str(exc)[:160]}", violations=1))
    out = pd.DataFrame(res)
    out["passed"] = out.violations == 0
    return out


def _run_checks(tables: dict, reference, rac_weight: float, res: list) -> None:
    T = tables
    bk, ps, ev, cap, ops, trains, routes, stops, cal, st = (T[k] for k in ("bookings", "booking_passengers", "cancellations", "seat_capacity", "train_operations", "trains", "routes",
                                                                           "train_stops", "calendar", "stations"))

    def add(cid, cat, desc, viol):
        res.append(dict(check_id=cid, category=cat, description=desc, violations=int(viol)))

    # ---- row counts against the Phase 2 validated cleaned counts
    rm = reference["row_movement"].set_index("table")["clean_rows"] if reference and reference.get("row_movement") is not None else None
    for t, df in T.items():
        if rm is not None:
            add(f"ROWS-{t}", "ROW COUNTS", f"{t}: row count equals the Phase 2 validated cleaned count ({int(rm[t]):,})", abs(len(df) - int(rm[t])))
    # ---- duplicate identifiers
    for t, df in T.items():
        add(f"DUP-pk-{t}", "DUPLICATES", f"{t}: primary key {PK[t]} is unique", df.duplicated(PK[t]).sum())
    add("DUP-booking-reference", "DUPLICATES", "bookings: booking_reference is unique", bk.duplicated("booking_reference").sum())
    add("DUP-capacity-run-class", "DUPLICATES", "seat_capacity: one row per train, date and class", cap.duplicated(["train_id", "journey_date", "travel_class"]).sum())
    add("DUP-operations-run", "DUPLICATES", "train_operations: one row per train and run date", ops.duplicated(["train_id", "run_date"]).sum())
    add("DUP-passenger-seq", "DUPLICATES", "booking_passengers: one row per booking and passenger_seq", ps.duplicated(["booking_id", "passenger_seq"]).sum())
    add("DUP-station-code", "DUPLICATES", "stations: station_code is unique", st.duplicated("station_code").sum())
    # ---- missing values (only the six documented columns may be empty)
    for t, df in T.items():
        cols = [c for c in df.columns if c not in ALLOWED_NULL.get(t, [])]
        add(f"NULL-{t}", "MISSING VALUES", f"{t}: no missing values outside the documented nullable columns", df[cols].isna().sum().sum())
    # ---- dates
    for t, cols in {"calendar": ["calendar_date"], "seat_capacity": ["journey_date"], "train_operations": ["run_date"], "bookings": ["journey_date", "booking_ts"], "cancellations": ["cancellation_ts"]}.items():
        add(f"DATE-parse-{t}", "DATES", f"{t}: date columns {cols} are valid datetimes", T[t][cols].isna().sum().sum())
    add("DATE-journey-window", "DATES", "booking journey dates are inside 2024-09-01 .. 2026-08-31", ((bk.journey_date < JOURNEY_START) | (bk.journey_date > JOURNEY_END)).sum())
    add("DATE-calendar-coverage", "DATES", "every journey, capacity and run date exists in the calendar table",
        (~bk.journey_date.isin(cal.calendar_date)).sum() + (~cap.journey_date.isin(cal.calendar_date)).sum() + (~ops.run_date.isin(cal.calendar_date)).sum())
    lead = (bk.journey_date - bk.booking_ts.dt.normalize()).dt.days
    add("DATE-booking-before-journey", "DATES", "booking date is on or before the journey date (BR-04)", (lead < 0).sum())
    add("DATE-lead-range", "DATES", f"lead time is 0..{cfg.MAX_ADVANCE_DAYS} days (BR-04)", (lead > cfg.MAX_ADVANCE_DAYS).sum())
    chart = _chart_prep(bk, stops, "journey_date")
    add("DATE-booking-before-chart-prep", "DATES", "booking_ts is before chart preparation, 4 hours before departure (BR-04)", (bk.booking_ts > chart).sum())
    m = ev.merge(bk[["booking_id", "booking_ts"]].assign(chart=chart), on="booking_id", how="left")
    add("DATE-cancellation-window", "DATES", "booking_ts <= cancellation_ts <= chart preparation (BR-12)", ((m.cancellation_ts < m.booking_ts) | (m.cancellation_ts > m.chart)).sum())
    # ---- categories and statuses
    dom = {"CAT-travel-class-bookings": (bk.travel_class, list(CLASSES)), "CAT-travel-class-capacity": (cap.travel_class, list(CLASSES)), "CAT-age-band": (ps.age_band, ["Child", "Adult", "Senior", "Unknown"]),
           "CAT-initial-status": (ps.initial_status, ["Confirmed", "RAC", "Waitlisted"]), "CAT-final-status": (ps.final_status, ["Confirmed", "RAC", "Waitlisted", "Cancelled"]),
           "CAT-booking-status": (bk.booking_status, ["Confirmed", "RAC", "Waitlisted", "Cancelled", "Mixed"]), "CAT-cancellation-type": (ev.cancellation_type, ["Passenger", "System"]),
           "CAT-status-at-cancellation": (ev.status_at_cancellation, ["Confirmed", "RAC", "Waitlisted"]), "CAT-train-type": (trains.train_type, ["Superfast", "Express", "Premium"]),
           "CAT-season": (cal.season, ["Winter", "Summer", "Monsoon", "Post-Monsoon"]), "CAT-region": (st.region, ["North", "South", "East", "West", "Central", "Northeast"])}
    for cid, (s, ok) in dom.items():
        add(cid, "CATEGORIES", f"{cid[4:].replace('-', ' ')} values are in the documented domain", (~s.astype(str).isin(ok)).sum())
    # ---- amounts
    add("AMT-fares-positive", "AMOUNTS", "passenger fares and booking totals are positive", (ps.fare_amount <= 0).sum() + (bk.total_fare <= 0).sum())
    add("AMT-refund-charge-nonnegative", "AMOUNTS", "refunds and cancellation charges are not negative", (ev.refund_amount < 0).sum() + (ev.cancellation_charge < 0).sum())
    add("AMT-distance-positive", "AMOUNTS", "route distances and cumulative stop distances are valid", (routes.distance_km <= 0).sum() + (stops.distance_from_origin_km < 0).sum())
    add("AMT-passengers-1-to-6", "AMOUNTS", "passengers per booking are 1..6", ((bk.num_passengers < 1) | (bk.num_passengers > cfg.MAX_PASSENGERS)).sum())
    # ---- capacity and occupancy bounds
    add("CAP-arithmetic", "CAPACITY", "total_seats = coaches_attached x seats_per_coach (BR-09)", (cap.total_seats != cap.coaches_attached * cap.seats_per_coach).sum())
    add("CAP-class-standard", "CAPACITY", "seats_per_coach equals the class standard (BR-09)", (cap.seats_per_coach != cap.travel_class.map(CLASSES)).sum())
    add("CAP-rac-berths", "CAPACITY", "0 <= rac_berths <= total_seats and wl_limit >= 0", ((cap.rac_berths < 0) | (cap.rac_berths > cap.total_seats) | (cap.wl_limit < 0)).sum())
    px = ps.merge(bk.drop_duplicates("booking_id")[["booking_id", "train_id", "journey_date", "travel_class"]], on="booking_id")
    cnt = px.groupby(["train_id", "journey_date", "travel_class", "final_status"]).size().unstack(fill_value=0)
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled"):
        if s not in cnt:
            cnt[s] = 0
    occ = cap.merge(cnt.reset_index(), on=["train_id", "journey_date", "travel_class"], how="left").fillna({"Confirmed": 0, "RAC": 0, "Waitlisted": 0, "Cancelled": 0})
    booked = occ.Confirmed + rac_weight * occ.RAC
    add("CAP-confirmed-limit", "OCCUPANCY BOUNDS", "Confirmed passengers <= total_seats - rac_berths (BR-08)", (occ.Confirmed > occ.total_seats - occ.rac_berths).sum())
    add("CAP-rac-limit", "OCCUPANCY BOUNDS", "RAC passengers <= 2 x rac_berths (BR-08)", (occ.RAC > 2 * occ.rac_berths).sum())
    add("CAP-occupancy-at-most-100", "OCCUPANCY BOUNDS", "Confirmed + RAC weight x RAC <= total_seats, so occupancy <= 100% (BR-08)", (booked > occ.total_seats + 1e-9).sum())
    add("CAP-waitlist-limit", "OCCUPANCY BOUNDS", "waitlisted passengers <= wl_limit (BR-08)", (occ.Waitlisted > occ.wl_limit).sum())
    # ---- booking <-> passenger reconciliation
    g = ps.groupby("booking_id")
    n, fare = g.size(), g.fare_amount.sum()
    b_i = bk.drop_duplicates("booking_id").set_index("booking_id")
    add("REC-passenger-count", "RECONCILIATION", "num_passengers equals the number of passenger rows (BR-03)", (b_i.num_passengers != n.reindex(b_i.index)).sum())
    add("REC-fare-sum", "RECONCILIATION", "booking total_fare equals the sum of passenger fares (BR-03)", ((b_i.total_fare - fare.reindex(b_i.index)).abs() > 0.005).sum())
    expected = g.final_status.first().where(g.final_status.nunique() == 1, "Mixed")
    add("REC-status-rollup", "RECONCILIATION", "booking_status is the roll-up of passenger final statuses (BR-02)", (b_i.booking_status.astype(str) != expected.reindex(b_i.index).astype(str)).sum())
    seq = g.passenger_seq.agg(["min", "max", "count"])
    add("REC-passenger-sequence", "RECONCILIATION", "passenger_seq runs 1..n within each booking (BR-03)", ((seq["min"] != 1) | (seq["max"] != seq["count"])).sum())
    # ---- cancellation <-> refund reconciliation and waitlist/status consistency
    linked = ps[ps.cancellation_id.notna()].copy(); linked["cid"] = linked.cancellation_id.astype("int64")
    lg = linked.groupby("cid").agg(n=("passenger_id", "size"), fare=("fare_amount", "sum"))
    e_i = ev.drop_duplicates("cancellation_id").set_index("cancellation_id")
    add("REC-event-passenger-count", "RECONCILIATION", "cancelled_passengers equals the passengers linked to the event (BR-11)", (e_i.cancelled_passengers != lg.n.reindex(e_i.index)).sum())
    add("REC-event-fare-sum", "RECONCILIATION", "original_fare_amount equals the linked passengers' fares (BR-11)", ((e_i.original_fare_amount - lg.fare.reindex(e_i.index)).abs() > 0.005).sum())
    add("REC-refund-arithmetic", "RECONCILIATION", "refund + charge = original fare for every event (BR-11)", ((e_i.refund_amount + e_i.cancellation_charge - e_i.original_fare_amount).abs() > 0.005).sum())
    add("REC-event-booking-match", "RECONCILIATION", "linked passengers belong to the event's booking (BR-10)", (linked.booking_id != linked.cid.map(e_i.booking_id)).sum())
    add("STAT-cancellation-link", "STATUS CONSISTENCY", "cancellation_id is set exactly when final status is Cancelled or Waitlisted (BR-10)", (ps.cancellation_id.notna() != ps.final_status.isin(["Cancelled", "Waitlisted"])).sum())
    et = linked.cid.map(e_i.cancellation_type)
    add("STAT-event-type", "STATUS CONSISTENCY", "Passenger events link Cancelled passengers; System events link Waitlisted passengers (BR-10)",
        ((et == "Passenger") & (linked.final_status != "Cancelled")).sum() + ((et == "System") & (linked.final_status != "Waitlisted")).sum())
    ok = {("Confirmed", "Confirmed"), ("Confirmed", "Cancelled"), ("RAC", "RAC"), ("RAC", "Confirmed"), ("RAC", "Cancelled"), ("Waitlisted", "Waitlisted"), ("Waitlisted", "RAC"), ("Waitlisted", "Confirmed"), ("Waitlisted", "Cancelled")}
    pair = pd.Series(list(zip(ps.initial_status.astype(str), ps.final_status.astype(str))))
    add("STAT-no-demotion", "STATUS CONSISTENCY", "no passenger is demoted between initial and final status (BR-17)", (~pair.isin(ok)).sum())
    add("STAT-system-waitlisted", "STATUS CONSISTENCY", "System auto-refund events cover only waitlisted passengers (BR-11)", ((ev.cancellation_type == "System") & (ev.status_at_cancellation != "Waitlisted")).sum())
    add("STAT-events-have-passengers", "STATUS CONSISTENCY", "every cancellation event has at least one linked passenger (BR-11)", (~ev.cancellation_id.isin(lg.index)).sum())
    # ---- train / run relationships
    tr = trains.drop_duplicates("train_id").set_index("train_id")
    dow = bk.journey_date.dt.dayofweek.to_numpy()
    rdays = bk.train_id.map(tr.run_days).to_numpy()
    add("REL-run-days", "TRAIN/RUN", "bookings fall on a scheduled run day of the train (BR-05)", sum(s[d] != "Y" for s, d in zip(rdays, dow)))
    ops_keys = set(zip(ops.train_id, ops.run_date))
    add("REL-operations-row", "TRAIN/RUN", "every booking train/date has a train_operations row (BR-05)", sum(k not in ops_keys for k in zip(bk.train_id, bk.journey_date)))
    cap_keys = set(zip(cap.train_id, cap.journey_date, cap.travel_class))
    add("REL-capacity-row", "TRAIN/RUN", "every booking train/date/class has a seat_capacity row (BR-07)", sum(k not in cap_keys for k in zip(bk.train_id, bk.journey_date, bk.travel_class)))
    add("REL-capacity-operations", "TRAIN/RUN", "every capacity row has a train_operations row", sum(k not in ops_keys for k in zip(cap.train_id, cap.journey_date)))
    add("REL-booking-route", "TRAIN/RUN", "booking route equals the train's route (BR-06)", (bk.train_id.map(tr.route_id) != bk.route_id).sum())
    r_i = routes.drop_duplicates("route_id").set_index("route_id")
    add("REL-booking-stations", "TRAIN/RUN", "boarding and destination stations equal the route's origin and destination (BR-06)",
        (bk.route_id.map(r_i.origin_station_id) != bk.boarding_station_id).sum() + (bk.route_id.map(r_i.destination_station_id) != bk.destination_station_id).sum())
    sg = stops.sort_values(["train_id", "stop_sequence"]).groupby("train_id")
    s_ok = sg.stop_sequence.agg(["min", "max", "count"])
    add("REL-stop-sequence", "TRAIN/RUN", "train stops are numbered 1..n and distances strictly increase (BR-13)",
        ((s_ok["min"] != 1) | (s_ok["max"] != s_ok["count"])).sum() + (sg.distance_from_origin_km.diff().dropna() <= 0).sum())
    first = stops[stops.stop_sequence == 1].drop_duplicates("train_id").set_index("train_id").station_id
    last = sg.station_id.last()
    add("REL-stop-terminals", "TRAIN/RUN", "first and last stop equal the route origin and destination (BR-13)",
        (trains.train_id.map(first).to_numpy() != trains.route_id.map(r_i.origin_station_id).to_numpy()).sum() + (trains.train_id.map(last).to_numpy() != trains.route_id.map(r_i.destination_station_id).to_numpy()).sum())
    for _, r in relationship_report(T).iterrows():
        add(f"FK-{r.child}", "RELATIONSHIPS", f"{r.child} -> {r.parent}: no orphan rows", r.orphans)
    # ---- labelling and size
    add("ORIGIN-synthetic", "LABELLING", "every row of every table is labelled data_origin = SYNTHETIC", sum((df["data_origin"] != "SYNTHETIC").sum() for df in T.values()))
    add("SIZE-bookings", "SIZE", "at least 100,000 bookings", max(0, 100_000 - len(bk)))
    add("SIZE-trains", "SIZE", "at least 50 trains", max(0, 50 - len(trains)))
    add("SIZE-stations", "SIZE", "at least 30 stations", max(0, 30 - len(st)))
    add("SIZE-months", "SIZE", "at least 24 months of journeys", max(0, 24 - bk.journey_date.dt.to_period("M").nunique()))


def documented_gaps(tables: dict) -> pd.DataFrame:
    """Missing values that are documented and deliberately retained (never imputed)."""
    ps, ops = tables["booking_passengers"], tables["train_operations"]
    return pd.DataFrame([
        dict(item="train_operations.arrival_delay_min is NULL", rows=int(ops.arrival_delay_min.isna().sum()), treatment="retained as NULL; excluded from delay KPIs (denominator = runs with a recorded delay)"),
        dict(item="booking_passengers.age_band = 'Unknown'", rows=int((ps.age_band == "Unknown").sum()), treatment="retained as 'Unknown'; no age imputed; not used by any KPI"),
        dict(item="booking_passengers.cancellation_id is NULL", rows=int(ps.cancellation_id.isna().sum()), treatment="expected: Confirmed and RAC passengers have no refund event")])


def format_report(results: pd.DataFrame) -> str:
    lines = [f"{'PASS' if r.passed else 'FAIL'}  {r.check_id:<34} violations={r.violations:<7} {r.description}" for r in results.itertuples()]
    lines.append(f"\n{int(results.passed.sum())}/{len(results)} checks passed")
    return "\n".join(lines)
