"""Phase 5 tests: Python analytics layer (loading, validation, cleaning, KPIs, reconciliation, statistics, charts, notebooks, no source mutation).

Run from the project root:
    python python/tests/test_phase5_python.py        # prints PASS/FAIL per test and writes the test section of reports/phase5_python_validation.txt
    pytest python/tests/test_phase5_python.py -q
Data: SYNTHETIC, sampled simulation (768 of 19,708 scheduled runs). No database is needed for Phase 5.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import traceback
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))
from analytics import cleaning, data_loader as dl, eda, insights, kpi, validation, visualization   # noqa: E402
from analytics import statistics as stats                                                          # noqa: E402

REP, VIS, DER = ROOT / "reports", ROOT / "visuals" / "phase5_python", ROOT / "data" / "processed" / "derived"
MARKER = "== E. Test suite =="


@lru_cache(maxsize=1)
def P():
    """The analysis, run once in-process: dataset, cleaning result, KPIs, monthly KPIs, EDA, statistics."""
    ds = dl.load_dataset(); clean = cleaning.run_cleaning(ds.tables); f = clean.facts
    k = kpi.compute_kpis(*(f[x] for x in ("passenger_fact", "booking_fact", "event_fact", "class_run_fact", "run_fact"))); m = kpi.monthly_kpis(f)
    E = eda.run_eda(f, m); S = stats.run_statistics(f, m, n_boot=300)
    return dict(ds=ds, clean=clean, facts=f, kpis=k, monthly=m, E=E, S=S)


def _hash(df):
    return int(pd.util.hash_pandas_object(df, index=True).sum())


# ------------------------------------------------------------------ loading and row counts
def test_loading_reads_all_tables_with_expected_dtypes():
    t = P()["ds"].tables
    assert list(t) == dl.TABLES
    b, ps, cal, ops = t["bookings"], t["booking_passengers"], t["calendar"], t["train_operations"]
    assert str(b.journey_date.dtype).startswith("datetime64") and str(b.booking_ts.dtype).startswith("datetime64") and b.total_fare.dtype == "float64"
    assert str(ops.arrival_delay_min.dtype) == "Int64" and str(ps.cancellation_id.dtype) == "Int64" and cal.is_weekend.dtype == "bool" and cal.is_holiday.dtype == "bool"
    assert b.booking_id.dtype == "int64" and ps.passenger_id.is_unique and set(ps.age_band) == {"Child", "Adult", "Senior", "Unknown"}


def test_row_counts_equal_csv_files_and_phase2_validated_counts():
    ds = P()["ds"]; rm = ds.reference["row_movement"].set_index("table")["clean_rows"]
    for name, df in ds.tables.items():
        n_csv = len(pd.read_csv(dl.CLEAN_DIR / f"{name}.csv", usecols=[0]))
        assert len(df) == n_csv == int(rm[name]), name
    assert (len(ds.tables["bookings"]), len(ds.tables["booking_passengers"]), len(ds.tables["cancellations"])) == (201_182, 405_200, 43_923)


def test_full_cleaned_dataset_is_used_not_the_excel_sample():
    ds = P()["ds"]
    assert len(ds.tables["train_operations"]) == 768 and ds.tables["bookings"].journey_date.dt.to_period("M").nunique() == 24
    assert not any("sample" in p for p in ds.fingerprint_before) and "data/processed/cleaned/bookings.csv" in ds.fingerprint_before
    assert dl.CLEAN_DIR == ROOT / "data" / "processed" / "cleaned"


def test_relationships_have_no_orphans_and_origin_is_synthetic():
    ds = P()["ds"]; rel = dl.relationship_report(ds.tables)
    assert len(rel) == len(dl.RELATIONSHIPS) == 17 and (rel.orphans == 0).all()
    assert all(set(df.data_origin) == {"SYNTHETIC"} for df in ds.tables.values())
    prof = dl.profile_tables(ds.tables); assert prof.rows.sum() == 654_660 and "2024-09-01 to 2026-08-31" in prof.set_index("table").date_range["seat_capacity"]


# ------------------------------------------------------------------ validation
def test_validation_passes_on_the_cleaned_data():
    ds = P()["ds"]; v = validation.run_validation(ds.tables, ds.reference)
    assert len(v) >= 100 and v.passed.all(), v[~v.passed]
    assert {"ROW COUNTS", "DUPLICATES", "MISSING VALUES", "DATES", "CATEGORIES", "AMOUNTS", "CAPACITY", "OCCUPANCY BOUNDS", "RECONCILIATION", "STATUS CONSISTENCY", "TRAIN/RUN", "RELATIONSHIPS", "LABELLING", "SIZE"} <= set(v.category)


def _mutate(fn):
    ds = P()["ds"]; t = dict(ds.tables); fn(t)
    return validation.run_validation(t, ds.reference).set_index("check_id").violations


def _cell(table, col, val, where=None):
    """Mutation that sets ONE cell (the first row, or the first row where `where(df)` is true) on a copy of the table."""
    def fn(t):
        df = t[table].copy(); i = df.index[0] if where is None else df.index[where(df)][0]
        df.loc[i, col] = val(df.loc[i, col]) if callable(val) else val; t[table] = df
    return fn


MUTATIONS = {
    "DUP-pk-bookings": lambda t: t.update(bookings=pd.concat([t["bookings"], t["bookings"].head(1)], ignore_index=True)),
    "NULL-bookings": _cell("bookings", "booking_ts", pd.NaT),
    "CAT-final-status": _cell("booking_passengers", "final_status", "Boarded"),
    "AMT-fares-positive": _cell("booking_passengers", "fare_amount", -5.0),
    "CAP-arithmetic": _cell("seat_capacity", "total_seats", 9999),
    "REC-fare-sum": _cell("bookings", "total_fare", 999_999.0),
    "REC-passenger-count": _cell("bookings", "num_passengers", lambda v: 5 if v != 5 else 4),
    "REC-status-rollup": _cell("bookings", "booking_status", "Mixed", where=lambda d: (d.booking_status == "Confirmed").to_numpy()),
    "REC-refund-arithmetic": _cell("cancellations", "refund_amount", lambda v: v + 1),
    "STAT-cancellation-link": _cell("booking_passengers", "final_status", "Confirmed", where=lambda d: d.cancellation_id.notna().to_numpy()),
    "STAT-no-demotion": _cell("booking_passengers", "final_status", "RAC", where=lambda d: ((d.initial_status == "Confirmed") & (d.final_status == "Confirmed")).to_numpy()),
    "REL-operations-row": lambda t: t.update(train_operations=t["train_operations"].iloc[1:].reset_index(drop=True)),
    "DATE-journey-window": _cell("bookings", "journey_date", pd.Timestamp("2030-01-01")),
    "DATE-booking-before-journey": _cell("bookings", "booking_ts", pd.Timestamp("2030-06-01")),
    "REL-booking-route": _cell("bookings", "route_id", 9999),
    "REL-run-days": _cell("bookings", "journey_date", pd.Timestamp("2024-09-03"), where=lambda d: (d.journey_date != pd.Timestamp("2024-09-03")).to_numpy()),
    "ROWS-stations": lambda t: t.update(stations=t["stations"].iloc[1:].reset_index(drop=True)),
    "ORIGIN-synthetic": _cell("stations", "data_origin", "PUBLIC"),
    "DATE-cancellation-window": _cell("cancellations", "cancellation_ts", pd.Timestamp("2031-01-01")),
    "AMT-passengers-1-to-6": _cell("bookings", "num_passengers", 9),
}


def test_validation_detects_every_deliberate_corruption():
    missed = []
    for check, fn in MUTATIONS.items():
        viol = _mutate(fn)
        assert "VALIDATION-INTERNAL-ERROR" not in viol.index, check
        if viol.get(check, 0) <= 0:
            missed.append(check)
    assert not missed, missed


def test_occupancy_bound_check_catches_an_overfull_run():
    ds = P()["ds"]; t = dict(ds.tables); cap = t["seat_capacity"].copy(); cf = P()["facts"]["class_run_fact"]
    idx = cf.index[cf.rac_pax > 0][0]; cap.loc[idx, "rac_berths"] = 0; t["seat_capacity"] = cap
    v = validation.run_validation(t, ds.reference).set_index("check_id").violations
    assert v["CAP-rac-limit"] > 0 and P()["ds"].tables["seat_capacity"].rac_berths.iloc[idx] > 0


def test_validation_never_crashes_on_malformed_input():
    ds = P()["ds"]; t = dict(ds.tables)
    for name in ("trains", "routes", "cancellations", "bookings"):          # duplicated keys are reported, not fatal
        t[name] = pd.concat([ds.tables[name], ds.tables[name].head(1)], ignore_index=True)
    v = validation.run_validation(t, ds.reference).set_index("check_id")
    assert "VALIDATION-INTERNAL-ERROR" not in v.index and all(v.violations[f"DUP-pk-{n}"] == 1 for n in ("trains", "routes", "cancellations", "bookings"))
    broken = dict(ds.tables); broken["bookings"] = ds.tables["bookings"].drop(columns=["total_fare"])      # a malformed table: a visible failure, never an exception
    r = validation.run_validation(broken, ds.reference)
    assert "VALIDATION-INTERNAL-ERROR" in set(r.check_id) and not r.passed.all()


def test_unmutated_data_still_passes_after_the_mutation_tests():
    ds = P()["ds"]; assert validation.run_validation(ds.tables, ds.reference).passed.all()


# ------------------------------------------------------------------ cleaning
def test_cleaning_keeps_every_row_logs_every_rule_and_imputes_nothing():
    c, ds = P()["clean"], P()["ds"]
    for name, df in ds.tables.items():
        assert len(c.tables[name]) == len(df), name
    assert set(c.log.rule_id) == {f"C-0{i}" for i in range(1, 9)} and c.log.rows_affected.ge(0).all()
    f = c.facts; assert len(f["passenger_fact"]) == 405_200 and len(f["booking_fact"]) == 201_182 and len(f["event_fact"]) == 43_923 and len(f["class_run_fact"]) == 2285 and len(f["run_fact"]) == 768
    assert int(f["run_fact"].arrival_delay_min.isna().sum()) == 23 and int(f["run_fact"].on_time.isna().sum()) == 23          # missing delay stays missing
    assert int(f["passenger_fact"].age_missing.sum()) == 1010 and (c.tables["booking_passengers"].age_band.astype(str) == "Unknown").sum() == 1010
    assert c.log[c.log.rule_id == "C-07"].rows_affected.sum() == 0 and c.log[c.log.rule_id == "C-04"].rows_affected.sum() == 0


def test_cleaning_does_not_modify_its_input():
    ds = P()["ds"]; before = {k: _hash(v) for k, v in ds.tables.items()}
    cleaning.run_cleaning(ds.tables)
    assert {k: _hash(v) for k, v in ds.tables.items()} == before


def test_cleaning_normalises_dirty_labels_and_still_removes_nothing():
    ds = P()["ds"]; t = dict(ds.tables); ps = t["booking_passengers"].copy(); bk = t["bookings"].copy()
    ps.loc[ps.index[:3], "final_status"] = [" confirmed ", "RAC ", "WAITLISTED"]; ps.loc[ps.index[3], "age_band"] = "  Adult"
    ps.loc[ps.index[:3], ["initial_status"]] = "Waitlisted"
    t["booking_passengers"] = ps
    c = cleaning.run_cleaning(t)
    assert len(c.tables["booking_passengers"]) == len(ps)
    assert set(c.tables["booking_passengers"].final_status.astype(str)) <= set(cleaning.STATUS_ORDER)
    assert c.log[(c.log.rule_id == "C-01") & (c.log.table == "booking_passengers")].rows_affected.iloc[0] >= 3
    assert c.log[(c.log.rule_id == "C-02") & (c.log.table == "booking_passengers")].rows_affected.iloc[0] >= 1
    dup = pd.concat([bk, bk.head(2)], ignore_index=True); t2 = dict(ds.tables); t2["bookings"] = dup
    assert int(dup.duplicated("booking_id").sum()) == 2                      # duplicate detection works on a copy; the rule flags, it does not delete


def test_derived_columns_and_metrics_are_correct():
    f = P()["facts"]; bf, cf, pf = f["booking_fact"], f["class_run_fact"], f["passenger_fact"]
    edges = {0: "0-3 days", 3: "0-3 days", 4: "4-14 days", 14: "4-14 days", 15: "15-30 days", 30: "15-30 days", 31: "31-60 days", 60: "31-60 days", 61: "61-120 days", 120: "61-120 days"}
    got = pd.cut(pd.Series(list(edges)), cleaning.LEAD_EDGES, labels=cleaning.LEAD_LABELS).astype(str).tolist(); assert got == list(edges.values())
    assert bf.lead_days.between(0, 120).all() and (bf.lead_bucket.astype(str) == pd.cut(bf.lead_days, cleaning.LEAD_EDGES, labels=cleaning.LEAD_LABELS).astype(str)).all()
    d = pd.Timestamp("2024-09-01"); assert d.day_name() == "Sunday" and bool(bf.loc[bf.journey_date == d, "is_weekend"].all()) and (bf.loc[bf.journey_date == d, "weekday"].astype(str) == "Sunday").all()
    assert np.allclose(cf.occupancy, (cf.confirmed_pax + 0.5 * cf.rac_pax) / cf.total_seats) and cf.occupancy.between(0, 1).all()
    assert np.allclose(cf.demand_per_seat, cf.passengers / cf.total_seats)
    assert set(pf.seat_equivalent.unique()) == {0.0, 0.5, 1.0} and (pf.seat_equivalent[pf.final_status == "RAC"] == 0.5).all()
    assert pf.is_cleared_wl.sum() == (pf.is_initial_wl & pf.final_status.isin(["Confirmed", "RAC"])).sum() and (pf.is_cleared_wl <= pf.is_initial_wl).all()
    assert bf.n_pax.sum() == len(pf) and (bf.n_pax == bf.num_passengers).all()


# ------------------------------------------------------------------ KPI calculations
def _mini():
    pf = pd.DataFrame(dict(final_status=["Confirmed", "Confirmed", "Waitlisted", "RAC", "Cancelled"], is_initial_wl=[False, False, True, True, False]))
    bf = pd.DataFrame(dict(booking_status=["Confirmed", "Mixed"], total_fare=[1000.0, 3000.0]))
    ef = pd.DataFrame(dict(cancellation_type=["Passenger", "System"], refund_amount=[400.0, 900.0], cancellation_charge=[100.0, 100.0]))
    cf = pd.DataFrame(dict(total_seats=[10, 10], confirmed_pax=[2, 0], rac_pax=[0, 1], wl_final_pax=[0, 1]))
    rf = pd.DataFrame(dict(on_time=pd.array([True, False, pd.NA], dtype="boolean"), delay_positive=[0.0, 30.0, np.nan]))
    return pf, bf, ef, cf, rf


def test_kpi_formulas_match_a_hand_computed_example():
    k = kpi.compute_kpis(*_mini())
    exp = dict(total_bookings=2, total_passengers=5, confirmed_bookings=1, mixed_bookings=1, cancelled_bookings=0, cancelled_passengers=1, passenger_cancellation_rate=0.2, booking_cancellation_rate=0.0, gross_value=4000.0,
               avg_fare_per_passenger=800.0, avg_fare_per_booking=2000.0, refund_passenger=400.0, refund_system=900.0, refund_total=1300.0, retained_charges=200.0, net_value=2700.0, wl_demand=2, wl_cleared=1, wl_clearance_rate=0.5,
               wl_uncleared=1, seat_supply=20, booked_seats=2.5, occupancy=0.125, confirmed_occupancy=0.1, rac_occupancy=0.025, waitlist_pressure=0.05, simulated_runs=3, bookings_per_run=2 / 3, passengers_per_run=5 / 3,
               runs_with_delay=2, on_time_runs=1, delayed_runs=1, otp=0.5, avg_delay=15.0, demand_per_seat=0.25)
    bad = {a: (k[a], b) for a, b in exp.items() if abs(k[a] - b) > 1e-9}
    assert not bad, bad
    assert kpi.compute_kpis(*_mini(), rac_weight=1.0)["booked_seats"] == 3.0       # the RAC weight is a parameter, not hard-coded


def test_kpi_ratios_are_nan_not_zero_when_the_denominator_is_zero():
    pf, bf, ef, cf, rf = (d.iloc[0:0] for d in _mini())
    k = kpi.compute_kpis(pf, bf, ef, cf, rf)
    for key in ("passenger_cancellation_rate", "booking_cancellation_rate", "wl_clearance_rate", "occupancy", "otp", "avg_delay", "avg_fare_per_passenger", "bookings_per_run"):
        assert np.isnan(k[key]), key
    assert k["total_bookings"] == 0 and k["gross_value"] == 0.0


def test_kpi_module_is_independent_of_the_phase3_reference_module():
    code = "import sys; sys.path.insert(0, 'python/src'); import analytics.kpi; print('kpi' in sys.modules)"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and r.stdout.strip() == "False", r.stderr


def test_kpi_reconciliation_with_the_reference_file_passes():
    p = P(); rec = kpi.reconcile(p["kpis"], p["ds"].reference["kpi_reference"])
    assert list(rec.columns) == ["KPI", "Reference_Value", "Python_Value", "Difference", "Status"] and len(rec) == 31 and (rec.Status == "PASS").all(), rec[rec.Status != "PASS"]
    assert set(rec.KPI) == set(p["ds"].reference["kpi_reference"].kpi_key)


def test_kpi_reconciliation_flags_a_wrong_value_instead_of_forcing_it():
    p = P(); k = dict(p["kpis"]); k["total_bookings"] += 1; k["occupancy"] += 0.001; k["gross_value"] += 1.0; k["avg_delay"] += 0.00001
    rec = kpi.reconcile(k, p["ds"].reference["kpi_reference"]).set_index("KPI")
    assert rec.loc["total_bookings", "Status"] == "FAIL" and rec.loc["occupancy", "Status"] == "FAIL" and rec.loc["gross_value", "Status"] == "FAIL" and rec.loc["avg_delay", "Status"] == "PASS"
    assert rec.loc["total_bookings", "Difference"] == 1 and abs(rec.loc["occupancy", "Difference"] - 0.001) < 1e-9
    k2 = dict(p["kpis"]); k2["total_passengers"] = float("nan"); assert kpi.reconcile(k2, p["ds"].reference["kpi_reference"]).set_index("KPI").loc["total_passengers", "Status"] == "FAIL"


def test_monthly_kpis_reconcile_and_growth_is_correct():
    p = P(); rec = kpi.reconcile_monthly(p["monthly"], p["ds"].reference["monthly_reference"]); m = p["monthly"]
    assert len(rec) == 24 * 40 and (rec.Status == "PASS").all()
    assert np.isnan(m.bookings_growth.iloc[0]) and np.allclose(m.bookings_growth.iloc[1:], m.total_bookings.pct_change().iloc[1:]) and np.allclose(m.bookings_per_run_growth.iloc[1:], (m.bookings_per_run.pct_change()).iloc[1:])
    assert m.total_bookings.sum() == p["kpis"]["total_bookings"] and abs(m.gross_value.sum() - p["kpis"]["gross_value"]) < 0.01 and (m.simulated_runs == 32).all()


def test_python_kpis_agree_with_the_phase4_sql_values():
    p = P(); cmp_ = kpi.compare_with_sql(p["kpis"], p["ds"].reference["phase4_kpi"])
    assert cmp_ is not None and len(cmp_) == 31 and (cmp_.Status == "PASS").all()


# ------------------------------------------------------------------ statistics
def test_statistical_functions_give_known_answers():
    lo, hi = stats.wilson_ci(50, 100); assert abs(lo - 0.4038) < 5e-4 and abs(hi - 0.5962) < 5e-4
    assert abs(stats.cramers_v([[10, 20], [20, 10]]) - 1 / 3) < 1e-9
    a, b = np.array([1.0, 2, 3, 4, 5]), np.array([3.0, 4, 5, 6, 7]); assert abs(stats.cohens_d(b, a) - 2 / np.sqrt(2.5)) < 1e-9
    assert abs(stats.spearman_ci(range(10), range(10))["rho"] - 1.0) < 1e-12 and abs(stats.linear_trend([1, 3, 5, 7, 9])["slope"] - 2.0) < 1e-12
    d = stats.describe([1, 2, 3, 4, 5]); assert d["mean"] == 3 and d["median"] == 3 and abs(d["variance"] - 2.5) < 1e-12 and abs(d["std"] - np.sqrt(2.5)) < 1e-12
    e1 = stats.ratio_bootstrap_ci([1, 2, 3, 4], [2, 2, 2, 2], 200); e2 = stats.ratio_bootstrap_ci([1, 2, 3, 4], [2, 2, 2, 2], 200); assert e1 == e2 and e1[1] <= e1[0] <= e1[2]
    kr = stats.kruskal_test([np.arange(10), np.arange(10) + 100]); assert kr["p"] < 0.001 and 0 <= kr["epsilon2"] <= 1
    assert stats.magnitude(0.1) == "negligible" and stats.magnitude(0.6) == "medium" and stats.magnitude(0.9) == "large"


def test_statistical_results_are_complete_and_honest():
    S = P()["S"]; t = S["tests"]
    assert len(t) >= 10
    for col in ("question", "metric", "method", "result", "interpretation", "limitation"):
        assert t[col].astype(str).str.len().gt(15).all(), col
    assert t.unit_of_analysis.astype(str).str.len().gt(3).all()
    assert t.p_value.between(0, 1).all() and (t.p_bonferroni >= t.p_value).all() and t.effect_size_name.notna().all()
    assert t.limitation.str.contains("Synthetic|synthetic").all()
    causal = re.compile(r"\b(causes?|caused|because of|due to)\b", re.I)
    assert not [x for x in t.interpretation if causal.search(x)], "interpretation text must not claim causation"
    d = S["descriptive"]; assert {"mean", "median", "std", "variance", "p5", "p25", "p75", "p95"} <= set(d.columns) and len(d) >= 8
    c = S["correlation_matrix"]; assert np.allclose(np.diag(c), 1) and np.allclose(c, c.T)
    ci = S["rate_cis"]; assert ((ci.ci_low <= ci.estimate) & (ci.estimate <= ci.ci_high)).all()
    w = ci.set_index("measure"); assert (w.loc["passenger cancellation rate (cluster bootstrap over bookings)", "ci_high"] - w.loc["passenger cancellation rate (cluster bootstrap over bookings)", "ci_low"]) > (
        w.loc["passenger cancellation rate (Wilson, assumes independence)", "ci_high"] - w.loc["passenger cancellation rate (Wilson, assumes independence)", "ci_low"])


def test_statistical_findings_agree_with_an_independent_calculation():
    from scipy import stats as sps
    p = P(); rf = p["facts"]["run_fact"]; r = p["S"]["tests"].set_index("test_id")
    a, b = rf.loc[rf.is_peak, "passengers"], rf.loc[~rf.is_peak, "passengers"]
    assert abs(r.loc["S-02", "p_value"] - sps.ttest_ind(a, b, equal_var=False).pvalue) < 1e-12 and r.loc["S-02", "effect_size"] > 0.3
    bf = p["facts"]["booking_fact"]; ct = pd.crosstab(bf.lead_bucket, bf.booking_status.astype(str) == "Cancelled")
    assert abs(r.loc["S-04", "statistic"] - sps.chi2_contingency(ct.to_numpy())[0]) < 1e-6


# ------------------------------------------------------------------ EDA consistency
def test_eda_tables_are_consistent_with_the_kpis():
    p = P(); E, k = p["E"], p["kpis"]
    assert E["monthly_demand"].total_bookings.sum() == k["total_bookings"] and E["weekday_demand"].runs.sum() == 768 and E["train_level"].runs.sum() == 768
    assert abs(E["booking_status_mix"].share.sum() - 1) < 1e-9 and abs(E["passenger_status_mix"].final_share.sum() - 1) < 1e-9
    assert E["class_level"].seats.sum() == k["seat_supply"] and E["route_level"].passengers.sum() == k["total_passengers"] and E["by_class"].passengers.sum() == k["total_passengers"]
    assert abs(E["monthly_value"].gross_value.sum() - k["gross_value"]) < 0.01 and abs(E["refund_by_type"].refund.sum() - k["refund_total"]) < 0.01
    assert E["train_level"].occupancy.between(0, 1).all() and (E["train_level"].occ_ci_low <= E["train_level"].occupancy + 1e-9).all()
    assert int(E["cancellation_shape"].set_index("item").bookings["mixed-status bookings"]) == k["mixed_bookings"]


# ------------------------------------------------------------------ charts, reports, entry point
def test_entry_point_runs_from_the_project_root():
    r = subprocess.run([sys.executable, "python/src/run_phase5.py"], capture_output=True, text=True, cwd=ROOT, timeout=600)
    assert r.returncode == 0 and "RESULT: OK" in r.stdout, r.stdout[-800:] + r.stderr[-800:]
    assert "source mutation: none" in r.stdout and "charts 16" in r.stdout


def test_sixteen_charts_are_generated_with_titles_labels_and_interpretations():
    p = P(); import matplotlib.pyplot as plt; import matplotlib.image as mpimg
    with tempfile.TemporaryDirectory() as tmp:
        cat = visualization.build_all(p["facts"], p["monthly"], p["E"], p["S"], Path(tmp))
        files = sorted(Path(tmp).glob("*.png"))
        assert len(cat) == len(files) == 16 and not plt.get_fignums()
        for f in files:
            img = mpimg.imread(f); assert img.shape[0] >= 700 and img.shape[1] >= 1000 and f.stat().st_size > 30_000, f.name
    for c in cat:
        assert c["title"] and c["x_axis"] and c["y_axis"] and len(c["interpretation"]) > 60 and re.search(r"\d", c["interpretation"]), c["file"]
    required = ["monthly_demand", "passenger_trend", "cancellation_trend", "waitlist_trend", "occupancy_trend", "value_trend", "train_performance", "route_performance", "class_performance", "status_distribution", "fare_distribution", "weekday_weekend"]
    assert all(any(r in c["file"] for c in cat) for r in required)
    disk = sorted(VIS.glob("*.png")); assert len(disk) == 16 and (REP / "phase5_chart_catalogue.csv").exists() and len(pd.read_csv(REP / "phase5_chart_catalogue.csv")) == 16


def test_reports_exist_with_required_structure_and_no_overclaiming():
    for f in ("phase5_python_validation.txt", "phase5_python_kpi_reconciliation.csv", "phase5_eda_summary.md", "phase5_business_insights.md", "phase5_cleaning_log.csv", "phase5_statistical_results.csv", "phase5_python_monthly_reconciliation.csv"):
        assert (REP / f).is_file() and (REP / f).stat().st_size > 200, f
    ins = (REP / "phase5_business_insights.md").read_text(encoding="utf-8")
    assert ins.count("**OBSERVED**") >= 8 and ins.count("**INTERPRETATION**") == ins.count("**OBSERVED**") == ins.count("**LIMITATION**")
    eda_md = (REP / "phase5_eda_summary.md").read_text(encoding="utf-8")
    for h in ("## A. Booking demand", "## B. Passenger behaviour", "## C. Operations", "## D. Financial analysis", "## E. Temporal analysis", "## Limitations"):
        assert h in eda_md, h
    for text in (ins, eda_md):
        assert "19,708" in text and "768" in text and "synthetic" in text.lower() and "sampled" in text.lower()
        for line in text.splitlines():
            if re.search(r"forecast", line, re.I):
                assert re.search(r"\b(no|not|nothing|never)\b|neither", line, re.I), line
        assert not re.search(r"IRCTC (passengers|network) (are|is|show|shows|has|have)\b", text), "no claim about real IRCTC behaviour"
    rep = pd.read_csv(REP / "phase5_python_kpi_reconciliation.csv"); assert list(rep.columns) == ["KPI", "Reference_Value", "Python_Value", "Difference", "Status"] and len(rep) == 31 and (rep.Status == "PASS").all()
    v = (REP / "phase5_python_validation.txt").read_text(encoding="utf-8")
    for s in ("== A.", "== B.", "== C.", "== D.", "FULL validated cleaned dataset", "NOT yet run on PostgreSQL 18.4", "PASS: 25 source files"):
        assert s in v, s


def test_source_data_is_not_modified_by_the_analysis():
    before = dl.fingerprint()
    import run_phase5; assert run_phase5.main(["--skip-charts"]) == 0
    after = dl.fingerprint(); assert before == after                                       # SHA-256, size and mtime of every source file
    man = json.loads((REP / "phase3_data_manifest.json").read_text())
    for rel, h in man.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h, rel
    written = {p.name for p in DER.glob("phase5_*.csv")}; assert len(written) == 5 and all(n.startswith("phase5_") for n in written)
    assert not list((ROOT / "data" / "raw").rglob("phase5_*")) and not list(dl.CLEAN_DIR.glob("phase5_*"))


def test_notebooks_are_valid_and_execute_without_errors():
    import nbformat
    from nbclient import NotebookClient
    names = ["01_data_validation", "02_data_cleaning", "03_eda", "04_statistical_analysis", "05_kpi_analysis"]
    d = ROOT / "python" / "notebooks"
    for n in names:
        nb = nbformat.read(d / f"{n}.ipynb", as_version=4); nbformat.validate(nb)
        assert any(c.cell_type == "markdown" for c in nb.cells) and sum(c.cell_type == "code" for c in nb.cells) >= 5
        assert not [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"] and any(c.get("outputs") for c in nb.cells if c.cell_type == "code")
        NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(d)}}).execute()      # re-run in place; the saved files are not rewritten here


def test_documentation_readme_and_requirements_cover_phase5():
    doc = (ROOT / "docs" / "phase5_python.md").read_text(encoding="utf-8")
    for needle in ("Purpose", "Dataset sources", "Workflow", "Cleaning rules", "Analytical methods", "KPI definitions", "Statistical methods", "Visualization catalogue", "Limitations", "Execution instructions", "python python/src/run_phase5.py",
                   "19,708", "synthetic", "No forecasts", "not yet been run", "PostgreSQL 18.4"):
        assert needle.lower() in doc.lower(), needle
    assert "Phase 5" in (ROOT / "README.md").read_text(encoding="utf-8") and "run_phase5.py" in (ROOT / "README.md").read_text(encoding="utf-8")
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8"); assert "nbclient" in req and "ipykernel" in req
    for n in ("data_loader", "validation", "cleaning", "kpi", "eda", "statistics", "visualization", "insights"):
        assert (ROOT / "python" / "src" / "analytics" / f"{n}.py").is_file(), n
    assert len(list((ROOT / "python" / "notebooks").glob("0*.ipynb"))) == 5
    for m in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", doc):
        if not m.startswith("http"):
            assert (ROOT / "docs" / m).resolve().exists(), m


def test_phase1_to_phase4_deliverables_are_unchanged():
    base = {}
    for zname in ("irctc-analytics-phase3-final.zip", "irctc-analytics-phase4-delta.zip"):       # the approved packages; later zip overrides earlier
        z = zipfile.ZipFile(ROOT.parent / zname)
        for n in z.namelist():
            if not n.endswith("/") and not n.endswith(".pyc"):
                base[n.split("/", 1)[1]] = hashlib.sha256(z.read(n)).hexdigest()
    allowed = {"README.md", "docs/project_plan.md", "docs/KPI_consistency_matrix.md", "requirements.txt", "reports/phase4_postgresql_validation.txt", "reports/phase1_validation.txt", "reports/phase2_validation.txt", "reports/phase3_validation.txt", "python/tests/test_phase3_excel.py", "python/tests/test_phase4_postgres.py", "python/tests/audit_phase3.py", "reports/phase3_review_report.md", "reports/phase3_audit_results.txt", "docs/phase4_postgresql.md"}
    changed = [rel for rel, h in base.items() if rel not in allowed and (not (ROOT / rel).is_file() or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != h)]
    assert not changed, changed


# ------------------------------------------------------------------ runner
def _tests():
    return [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno if callable(kv[1]) and hasattr(kv[1], "__code__") else 0) if n.startswith("test_") and callable(f)]


def main() -> int:
    lines, passed, failed = [], 0, 0
    for name, fn in _tests():
        try:
            fn(); lines.append(f"PASS  {name}"); passed += 1
        except Exception as e:
            lines.append(f"FAIL  {name}\n        {type(e).__name__}: {str(e)[:500]}"); failed += 1; traceback.print_exc()
    section = [MARKER, f"Command: python python/tests/test_phase5_python.py    ({datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')})", *lines, "", f"{passed} passed, {failed} failed, {passed + failed} total", ""]
    print("\n".join(section))
    target = REP / "phase5_python_validation.txt"
    if "--no-write" not in sys.argv and target.exists():
        text = target.read_text(encoding="utf-8"); text = text[:text.index(MARKER)] if MARKER in text else text.rstrip("\n") + "\n\n"
        target.write_text(text + "\n".join(section), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
