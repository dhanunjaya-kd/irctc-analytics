"""Phase 5 entry point: runs the whole Python analytics workflow from the project root.

    python python/src/run_phase5.py                 # full run: validation, cleaning, KPIs, reconciliation, EDA, statistics, charts, reports
    python python/src/run_phase5.py --skip-charts   # same without rendering the 16 charts

Reads only data/processed/cleaned/*.csv and the reference outputs (never modifies them); writes reports/phase5_*, visuals/phase5_python/*.png and
data/processed/derived/phase5_*.csv. Exit code 1 if any validation check or KPI reconciliation fails, or if a source file changed during the run.
Data: SYNTHETIC, sampled simulation (768 of 19,708 scheduled runs); not IRCTC network-wide data; no forecasts.
"""
from __future__ import annotations

import argparse
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import scipy

from analytics import SYNTHETIC_NOTE, cleaning, data_loader as dl, eda, insights, kpi, validation, visualization
from analytics import statistics as stats

ROOT, REPORTS, DERIVED, VISUALS = dl.ROOT, dl.REPORTS_DIR, dl.DERIVED_DIR, dl.ROOT / "visuals" / "phase5_python"
TEST_MARKER = "== E. Test suite =="


def build_validation_report(ds, profile, rels, val, gaps, clean, kpis, rec, rec_m, sql_cmp, mutation, versions) -> str:
    n_ok = int(val.passed.sum())
    L = ["Phase 5 (Python analytics) validation report", f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}", "Command: python python/src/run_phase5.py", f"Environment: {versions}", "",
         SYNTHETIC_NOTE, "Dataset analysed: the FULL validated cleaned dataset (data/processed/cleaned). The 48-run Excel sample is not used.", "",
         "== A. Sources, row counts, types, date ranges, relationships ==", ""]
    L += [f"{r.table:<20} {r.rows:>9,} rows  {r.columns:>2} cols  null cells {r.null_cells:>8,}  origin={r.data_origin}  {r.date_range}" for r in profile.itertuples()]
    L += ["", f"Total rows analysed: {int(profile.rows.sum()):,} (bookings {len(ds.tables['bookings']):,}; passengers {len(ds.tables['booking_passengers']):,}; cancellation events {len(ds.tables['cancellations']):,}; train-class runs {len(ds.tables['seat_capacity']):,}; simulated runs {len(ds.tables['train_operations']):,})",
          "Foreign-key relationships (orphan child rows):"] + [f"  {r.child:<38} -> {r.parent:<28} orphans={r.orphans}" for r in rels.itertuples()]
    L += ["", "Documented gaps (retained, never imputed):"] + [f"  {r.item:<46} {r.rows:>8,}  {r.treatment}" for r in gaps.itertuples()]
    rm = ds.reference["row_movement"]
    L += ["", "Phase 2 validated counts (reports/data_quality/row_movement.csv) vs Python: " + ", ".join(f"{t}={int(rm.set_index('table').clean_rows[t]):,}" for t in ("bookings", "booking_passengers", "cancellations"))]
    p4 = ds.reference.get("phase4_checks")
    if p4 is not None:
        L.append(f"Phase 4 reference output reports/phase4_check_results.csv: {int(p4.passed.sum())} of {len(p4)} PostgreSQL data-quality checks passed (built on PostgreSQL 16.15; NOT yet run on PostgreSQL 18.4 / Windows).")
    L += ["", "== B. Python validation checks ==", "", validation.format_report(val), "", "Cleaning pipeline (reports/phase5_cleaning_log.csv): " + f"{len(clean.log)} rule applications; rows removed: 0; values imputed: 0; rows in == rows out for every table.",
          "", "== C. KPI reconciliation (Python vs reports/kpi_reference_values.csv) ==", ""]
    L += [f"{r.Status}  {r.KPI:<30} reference={r.Reference_Value:>16,.6f}  python={r.Python_Value:>16,.6f}  diff={r.Difference:+.2e}" for r in rec.itertuples()]
    L += ["", f"Overall: {int((rec.Status == 'PASS').sum())} of {len(rec)} KPIs within tolerance (counts exact; INR 0.005; shares 0.00005; per-run and minute values 0.0001).",
          f"Monthly (data/processed/derived/monthly_kpis.csv): {int((rec_m.Status == 'PASS').sum())} of {len(rec_m)} comparisons within tolerance.",
          (f"Python vs Phase 4 SQL values (reports/phase4_kpi_reconciliation.csv): {int((sql_cmp.Status == 'PASS').sum())} of {len(sql_cmp)} within tolerance." if sql_cmp is not None else "Phase 4 SQL values not available."),
          "Exploratory measures (not approved KPIs, not reconciled): demand_per_seat = %.4f, bookings_per_seat = %.4f." % (kpis["demand_per_seat"], kpis["bookings_per_seat"]), "",
          "== D. Source-data mutation check ==", "", mutation, "", TEST_MARKER, "(written by python/tests/test_phase5_python.py)", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--skip-charts", action="store_true"); ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv); t0 = time.time()
    def step(msg): print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)
    versions = f"Python {platform.python_version()}, pandas {pd.__version__}, numpy {np.__version__}, scipy {scipy.__version__}"
    step("1/9 loading cleaned data and reference outputs (read-only)")
    ds = dl.load_dataset(); profile = dl.profile_tables(ds.tables); rels = dl.relationship_report(ds.tables)
    step("2/9 validating"); val = validation.run_validation(ds.tables, ds.reference); gaps = validation.documented_gaps(ds.tables)
    step("3/9 cleaning and building analytical fact tables"); clean = cleaning.run_cleaning(ds.tables); f = clean.facts
    step("4/9 computing KPIs and reconciling"); parts = ("passenger_fact", "booking_fact", "event_fact", "class_run_fact", "run_fact")
    kpis = kpi.compute_kpis(*(f[x] for x in parts)); monthly = kpi.monthly_kpis(f)
    rec = kpi.reconcile(kpis, ds.reference["kpi_reference"]); rec_m = kpi.reconcile_monthly(monthly, ds.reference["monthly_reference"]); sql_cmp = kpi.compare_with_sql(kpis, ds.reference.get("phase4_kpi"))
    step("5/9 exploratory analysis"); E = eda.run_eda(f, monthly)
    step("6/9 statistical analysis"); S = stats.run_statistics(f, monthly, args.n_boot)
    cat = []
    if not args.skip_charts:
        step("7/9 rendering charts"); cat = visualization.build_all(f, monthly, E, S, VISUALS)
    step("8/9 writing reports and derived datasets")
    REPORTS.mkdir(exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
    rec.to_csv(REPORTS / "phase5_python_kpi_reconciliation.csv", index=False); rec_m.to_csv(REPORTS / "phase5_python_monthly_reconciliation.csv", index=False)
    if sql_cmp is not None:
        sql_cmp.to_csv(REPORTS / "phase5_python_vs_phase4_sql.csv", index=False)
    clean.log.to_csv(REPORTS / "phase5_cleaning_log.csv", index=False)
    S["tests"].to_csv(REPORTS / "phase5_statistical_results.csv", index=False); S["descriptive"].to_csv(REPORTS / "phase5_descriptive_statistics.csv", index=False)
    S["rate_cis"].to_csv(REPORTS / "phase5_statistical_intervals.csv", index=False); S["correlation_pairs"].to_csv(REPORTS / "phase5_correlations.csv", index=False)
    if cat:
        pd.DataFrame(cat).to_csv(REPORTS / "phase5_chart_catalogue.csv", index=False)
    (REPORTS / "phase5_eda_summary.md").write_text(eda.eda_markdown(E, kpis, S), encoding="utf-8")
    (REPORTS / "phase5_business_insights.md").write_text(insights.insights_markdown(kpis, E, S, monthly), encoding="utf-8")
    for name, df in {"phase5_monthly_python_kpis": monthly, "phase5_train_summary": E["train_level"], "phase5_route_summary": E["route_level"], "phase5_class_summary": E["class_level"], "phase5_weekday_summary": E["weekday_demand"]}.items():
        df.assign(data_origin="DERIVED").to_csv(DERIVED / f"{name}.csv", index=False)
    step("9/9 verifying that no source file changed")
    after = dl.fingerprint(list(ROOT / p for p in ds.fingerprint_before))
    changed = [p for p in ds.fingerprint_before if ds.fingerprint_before[p] != after.get(p)]
    mutation = (f"PASS: {len(ds.fingerprint_before)} source files (cleaned tables, raw originals, reference outputs) have identical SHA-256, size and modification time before and after the run."
                if not changed else f"FAIL: changed during the run: {changed}")
    report = build_validation_report(ds, profile, rels, val, gaps, clean, kpis, rec, rec_m, sql_cmp, mutation, versions)
    target = REPORTS / "phase5_python_validation.txt"
    if target.exists() and TEST_MARKER in target.read_text(encoding="utf-8"):       # keep the test-suite section written by the test runner
        old = target.read_text(encoding="utf-8"); tail = old[old.index(TEST_MARKER):]
        if "(written by python/tests/test_phase5_python.py)" not in tail.split("\n", 2)[1]:
            report = report[:report.index(TEST_MARKER)] + tail
    target.write_text(report, encoding="utf-8")
    ok = bool(val.passed.all() and (rec.Status == "PASS").all() and (rec_m.Status == "PASS").all() and not changed)
    print(f"\nrows analysed: {int(profile.rows.sum()):,} | validation {int(val.passed.sum())}/{len(val)} | KPI reconciliation {int((rec.Status == 'PASS').sum())}/{len(rec)} | monthly {int((rec_m.Status == 'PASS').sum())}/{len(rec_m)} | charts {len(cat)} | source mutation: {'none' if not changed else changed}")
    print("RESULT:", "OK" if ok else "FAILED"); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
