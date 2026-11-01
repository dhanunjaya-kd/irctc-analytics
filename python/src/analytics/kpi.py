"""Phase 5 KPI calculations: the approved Phase 1-3 definitions (docs/KPI_definitions.md) implemented independently in Pandas.

Computed from the cleaned fact tables, NOT by importing python/src/kpi.py, so the reconciliation against reports/kpi_reference_values.csv is a real
check. Definitions are never adjusted to force agreement; a difference is reported as FAIL with its size.

Denominators: passenger cancellation rate = cancelled passengers / total passengers; booking cancellation rate = cancelled bookings / total bookings;
waitlist clearance = cleared / passengers waitlisted AT BOOKING TIME; occupancy = (Confirmed + RAC weight x RAC) / seat supply of the same train-class runs
(waitlisted passengers hold no seat); OTP and average delay use runs with a RECORDED arrival delay (NULL excluded, never imputed); average fare = gross value / total
passengers. `demand_per_seat` and `bookings_per_seat` are EXPLORATORY measures, not approved KPIs, and are not reconciled.
Ratios are NaN (not 0) when the denominator is 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg

COUNT_KEYS = ["total_bookings", "total_passengers", "confirmed_bookings", "mixed_bookings", "cancelled_bookings", "cancelled_passengers", "confirmed_pax", "rac_pax", "wl_demand", "wl_cleared",
              "wl_uncleared", "seat_supply", "simulated_runs", "class_runs", "runs_with_delay", "on_time_runs", "delayed_runs", "delay_sum_pos"]
MONEY_KEYS = ["gross_value", "refund_total", "refund_passenger", "refund_system", "retained_charges", "net_value"]
RATIO_KEYS = ["passenger_cancellation_rate", "booking_cancellation_rate", "wl_clearance_rate", "occupancy", "confirmed_occupancy", "rac_occupancy", "waitlist_pressure", "otp"]
PER_UNIT_KEYS = ["avg_fare_per_passenger", "avg_fare_per_booking", "bookings_per_run", "passengers_per_run", "avg_delay", "booked_seats"]
GROWTH_KEYS = ["bookings_growth", "bookings_per_run_growth"]
EXPLORATORY_KEYS = ["demand_per_seat", "bookings_per_seat"]
TOL_BY_UNIT = {"INR": 0.005, "share": 0.00005, "seat-equivalents": 0.0001, "minutes": 0.0001, "bookings/run": 0.0001, "passengers/run": 0.0001}   # counts: exact (0)

KPI_CATALOGUE = [
    ("total_bookings", "Booking volume", "count of bookings", "none"),
    ("total_passengers", "Passenger volume", "count of passengers (all final statuses)", "none"),
    ("confirmed_bookings", "Fully confirmed booking count", "bookings where every passenger finished Confirmed", "none"),
    ("mixed_bookings", "Mixed-status booking count", "bookings whose passengers finished with different statuses", "none"),
    ("passenger_cancellation_rate", "Passenger cancellation rate", "cancelled passengers / total passengers", "total passengers"),
    ("booking_cancellation_rate", "Booking-based cancellation rate", "fully cancelled bookings / total bookings", "total bookings"),
    ("wl_demand", "Initial waitlist demand", "passengers waitlisted at booking time", "none"),
    ("wl_clearance_rate", "Waitlist clearance rate", "initially waitlisted passengers who finished Confirmed or RAC / initially waitlisted passengers", "initial waitlist demand"),
    ("wl_uncleared", "Uncleared waitlist passengers", "passengers still Waitlisted at chart preparation (refunded by the System)", "none"),
    ("occupancy", "Seat occupancy", "(Confirmed + 0.5 x RAC passengers) / seat supply of the same train-class runs", "seat supply"),
    ("waitlist_pressure", "Waitlist pressure", "uncleared waitlisted passengers / seat supply (waitlisted passengers hold no seat)", "seat supply"),
    ("gross_value", "Gross booking value", "sum of booking fares before refunds (INR; not revenue)", "none"),
    ("refund_total", "Refund amount", "sum of refunds, Passenger and System events (INR)", "none"),
    ("net_value", "Net booking value", "gross booking value minus refund amount (INR; not revenue or profit)", "none"),
    ("avg_fare_per_passenger", "Average fare per passenger", "gross booking value / total passengers (INR)", "total passengers"),
    ("bookings_growth", "Monthly booking growth", "bookings / previous month's bookings - 1", "previous month's bookings"),
    ("bookings_per_run_growth", "Monthly growth in bookings per simulated run", "bookings per run / previous month's bookings per run - 1", "previous month's bookings per run"),
    ("demand_per_seat", "Demand per available seat (EXPLORATORY, not an approved KPI)", "total passengers requested / seat supply", "seat supply")]


def _div(a, b):
    return float(a) / float(b) if b else float("nan")


def compute_kpis(pf: pd.DataFrame, bf: pd.DataFrame, ef: pd.DataFrame, cf: pd.DataFrame, rf: pd.DataFrame, rac_weight: float = cfg.RAC_SEAT_WEIGHT) -> dict:
    """KPIs for the given passenger, booking, event, class-run and run tables (the full dataset, or one month of it)."""
    k = {}
    status = bf.booking_status.astype(str).value_counts()
    k["total_bookings"], k["total_passengers"] = len(bf), len(pf)
    k["confirmed_bookings"], k["mixed_bookings"], k["cancelled_bookings"] = (int(status.get(s, 0)) for s in ("Confirmed", "Mixed", "Cancelled"))
    fin = pf.final_status.astype(str).value_counts()
    k["cancelled_passengers"], k["confirmed_pax"], k["rac_pax"] = (int(fin.get(s, 0)) for s in ("Cancelled", "Confirmed", "RAC"))
    k["passenger_cancellation_rate"] = _div(k["cancelled_passengers"], k["total_passengers"])
    k["booking_cancellation_rate"] = _div(k["cancelled_bookings"], k["total_bookings"])
    k["gross_value"] = float(bf.total_fare.sum())
    by_type = ef.groupby(ef.cancellation_type.astype(str)).refund_amount.sum()
    k["refund_passenger"], k["refund_system"] = float(by_type.get("Passenger", 0.0)), float(by_type.get("System", 0.0))
    k["refund_total"] = k["refund_passenger"] + k["refund_system"]
    k["retained_charges"] = float(ef.cancellation_charge.sum())
    k["net_value"] = k["gross_value"] - k["refund_total"]
    k["avg_fare_per_passenger"] = _div(k["gross_value"], k["total_passengers"])
    k["avg_fare_per_booking"] = _div(k["gross_value"], k["total_bookings"])
    k["wl_demand"] = int(pf.is_initial_wl.sum())
    k["wl_cleared"] = int((pf.is_initial_wl & pf.final_status.astype(str).isin(["Confirmed", "RAC"])).sum())
    k["wl_uncleared"] = int((pf.final_status.astype(str) == "Waitlisted").sum())
    k["wl_clearance_rate"] = _div(k["wl_cleared"], k["wl_demand"])
    k["seat_supply"] = int(cf.total_seats.sum()); k["class_runs"] = len(cf)
    k["booked_seats"] = float(cf.confirmed_pax.sum() + rac_weight * cf.rac_pax.sum())
    k["occupancy"] = _div(k["booked_seats"], k["seat_supply"])
    k["confirmed_occupancy"] = _div(cf.confirmed_pax.sum(), k["seat_supply"])
    k["rac_occupancy"] = _div(rac_weight * cf.rac_pax.sum(), k["seat_supply"])
    k["waitlist_pressure"] = _div(cf.wl_final_pax.sum(), k["seat_supply"])
    k["simulated_runs"] = len(rf)
    k["bookings_per_run"] = _div(k["total_bookings"], k["simulated_runs"])
    k["passengers_per_run"] = _div(k["total_passengers"], k["simulated_runs"])
    ot = rf.on_time.dropna().astype(bool)
    k["runs_with_delay"], k["on_time_runs"] = len(ot), int(ot.sum()); k["delayed_runs"] = k["runs_with_delay"] - k["on_time_runs"]
    k["delay_sum_pos"] = float(rf.loc[rf.on_time.notna(), "delay_positive"].sum())
    k["otp"] = _div(k["on_time_runs"], k["runs_with_delay"])
    k["avg_delay"] = _div(k["delay_sum_pos"], k["runs_with_delay"])
    k["demand_per_seat"] = _div(k["total_passengers"], k["seat_supply"])          # exploratory, not approved
    k["bookings_per_seat"] = _div(k["total_bookings"], k["seat_supply"])          # exploratory, not approved
    return k


def monthly_kpis(facts: dict, rac_weight: float = cfg.RAC_SEAT_WEIGHT) -> pd.DataFrame:
    """The same KPI function per journey month (refunds follow the booking's journey month) plus the two approved growth metrics (NaN for the first month)."""
    pf, bf, ef, cf, rf = (facts[k] for k in ("passenger_fact", "booking_fact", "event_fact", "class_run_fact", "run_fact"))
    parts = {n: dict(tuple(df.groupby("journey_month"))) for n, df in dict(pf=pf, bf=bf, ef=ef, cf=cf, rf=rf).items()}
    rows = [dict(journey_month=m, **compute_kpis(parts["pf"][m], parts["bf"][m], parts["ef"][m], parts["cf"][m], parts["rf"][m], rac_weight)) for m in sorted(parts["bf"])]
    out = pd.DataFrame(rows)
    out["bookings_growth"] = out.total_bookings.pct_change(); out["bookings_per_run_growth"] = out.bookings_per_run.pct_change()
    return out


def kpi_table(kpis: dict) -> pd.DataFrame:
    """Readable table of the KPI catalogue: name, value, definition, denominator, approval status."""
    rows = []
    for key, name, definition, denom in KPI_CATALOGUE:
        if key in GROWTH_KEYS:
            continue
        rows.append(dict(kpi_key=key, kpi=name, value=kpis[key], definition=definition, denominator=denom, status="approved" if key not in EXPLORATORY_KEYS else "exploratory (not an approved KPI)"))
    return pd.DataFrame(rows)


def tolerance(unit: str) -> float:
    return TOL_BY_UNIT.get(unit, 0.0)


def reconcile(kpis: dict, reference: pd.DataFrame, detail: bool = False) -> pd.DataFrame:
    """Python KPIs vs reports/kpi_reference_values.csv. Columns: KPI, Reference_Value, Python_Value, Difference, Status (PASS/FAIL) [+ Unit, Tolerance]."""
    rows = []
    for r in reference.itertuples():
        py = kpis.get(r.kpi_key, float("nan"))
        diff = py - r.value
        ok = bool(np.isfinite(py) and abs(diff) <= tolerance(r.unit))
        rows.append(dict(KPI=r.kpi_key, Reference_Value=r.value, Python_Value=py, Difference=diff, Status="PASS" if ok else "FAIL", Unit=r.unit, Tolerance=tolerance(r.unit)))
    out = pd.DataFrame(rows)
    return out if detail else out[["KPI", "Reference_Value", "Python_Value", "Difference", "Status"]]


def _monthly_tol(key: str) -> float:
    if key in MONEY_KEYS + ["avg_fare_per_passenger", "avg_fare_per_booking"]:
        return 0.005
    if key in RATIO_KEYS + GROWTH_KEYS:
        return 0.00005
    if key in ("booked_seats", "bookings_per_run", "passengers_per_run", "avg_delay"):
        return 0.0001
    return 0.0


def reconcile_monthly(monthly: pd.DataFrame, reference_monthly: pd.DataFrame) -> pd.DataFrame:
    """Python monthly KPIs vs data/processed/derived/monthly_kpis.csv (24 months x 40 columns). NaN == NaN counts as agreement (first-month growth)."""
    ref = reference_monthly.set_index("journey_month"); py = monthly.set_index("journey_month")
    rows = []
    for key in [c for c in ref.columns if c not in ("data_origin",)]:
        for m in ref.index:
            a, b = py.at[m, key] if m in py.index else np.nan, ref.at[m, key]
            both_nan = pd.isna(a) and pd.isna(b)
            ok = both_nan or (pd.notna(a) and pd.notna(b) and abs(a - b) <= _monthly_tol(key))
            rows.append(dict(journey_month=m, KPI=key, Reference_Value=b, Python_Value=a, Difference=(a - b) if not both_nan and pd.notna(a) and pd.notna(b) else np.nan, Status="PASS" if ok else "FAIL"))
    return pd.DataFrame(rows)


def compare_with_sql(kpis: dict, phase4_kpi: pd.DataFrame | None) -> pd.DataFrame | None:
    """Python values next to the values PostgreSQL produced in Phase 4 (reports/phase4_kpi_reconciliation.csv; built on PostgreSQL 16, not yet run on 18.4)."""
    if phase4_kpi is None:
        return None
    rows = []
    for r in phase4_kpi.itertuples():
        py = kpis.get(r.kpi_key, float("nan"))
        rows.append(dict(KPI=r.kpi_key, SQL_Value=r.sql_value, Python_Value=py, Difference=py - r.sql_value, Status="PASS" if abs(py - r.sql_value) <= tolerance(r.unit) else "FAIL"))
    return pd.DataFrame(rows)
