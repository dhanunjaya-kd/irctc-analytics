"""Phase 4 tests: PostgreSQL schema, load, constraints, data-quality checks, KPI reconciliation, analytical SQL.

Run from the project root (needs psql on PATH and a reachable PostgreSQL server with the irctc_analytics database):
    python python/tests/test_phase4_postgres.py         # prints results and writes reports/phase4_postgresql_validation.txt
    pytest python/tests/test_phase4_postgres.py -q
Connection: the usual PGHOST / PGPORT / PGUSER / PGPASSWORD variables (PGDATABASE defaults to irctc_analytics); optional PSQL = path to psql.
WARNING: the first test REBUILDS the stg, core, analytics, qa and sandbox schemas of that database from the SQL scripts.
Only psql is used (no Python database driver), so the same file runs on Windows, Linux and macOS.
"""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SQL, CLEAN, DER, REP = ROOT / "sql", ROOT / "data/processed/cleaned", ROOT / "data/processed/derived", ROOT / "reports"
TABLES = ["stations", "routes", "trains", "train_stops", "calendar", "seat_capacity", "train_operations", "bookings", "booking_passengers", "cancellations"]
ENV = os.environ.copy()
ENV.setdefault("PGDATABASE", "irctc_analytics")
ENV["PGCLIENTENCODING"] = "UTF8"
PSQL = os.environ.get("PSQL", "psql")


# ------------------------------------------------------------------ psql helpers
def run(args=(), sql=None, timeout=900):
    return subprocess.run([PSQL, "-X", "-q", "-v", "ON_ERROR_STOP=1", *args], input=sql, capture_output=True, text=True, env=ENV, cwd=ROOT, timeout=timeout)


def q(sql):
    """Run one query and return rows as lists of strings."""
    r = run(["-At", "-F", "|", "-c", sql])
    assert r.returncode == 0, r.stderr
    return [line.split("|") for line in r.stdout.splitlines() if line != ""]


def qv(sql):
    return q(sql)[0][0]


def result_of(script):
    """Run a multi-statement script; return the values of lines printed as RESULT|<value>."""
    r = run(["-At", "-F", "|"], sql=script)
    assert r.returncode == 0, r.stderr
    return [line.split("|", 1)[1] for line in r.stdout.splitlines() if line.startswith("RESULT|")]


def block(file, label):
    """Extract one labelled statement ('-- [W2] ...') from an analysis file."""
    text = (SQL / "analysis" / file).read_text(encoding="utf-8")
    m = re.search(rf"^-- \[{re.escape(label)}\].*?(?=^-- \[|\Z)", text, flags=re.S | re.M)
    assert m, f"{label} not found in {file}"
    return "\n".join(l for l in m.group(0).splitlines() if not l.startswith("--")).strip()


def rows(sql):
    r = run(["-At", "-F", "|", "-c", sql])
    assert r.returncode == 0, r.stderr
    return [line.split("|") for line in r.stdout.splitlines() if line]


@lru_cache(maxsize=1)
def built():
    r = run(["-f", str(SQL / "00_build_all.sql")])
    assert r.returncode == 0, r.stderr[-1500:]
    assert "=== build finished ===" in r.stdout
    return r


def counts():
    return {t: int(qv(f"SELECT count(*) FROM core.{t}")) for t in TABLES}


# ------------------------------------------------------------------ build and structure
def test_build_from_scripts_succeeds():
    r = built()
    assert "PostgreSQL" in r.stdout


def test_rebuild_is_repeatable_and_deterministic():
    before = counts(); sums_before = q("SELECT sum(total_fare), sum(booking_id) FROM core.bookings")
    r = run(["-f", str(SQL / "00_build_all.sql")])
    assert r.returncode == 0, r.stderr[-1500:]
    assert counts() == before and q("SELECT sum(total_fare), sum(booking_id) FROM core.bookings") == sums_before


def test_schema_inventory_matches_the_design():
    built()
    assert sorted(x[0] for x in q("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('stg','core','analytics','qa','sandbox')")) == ["analytics", "core", "qa", "stg"]
    assert sorted(x[0] for x in q("SELECT table_name FROM information_schema.tables WHERE table_schema='core' AND table_type='BASE TABLE'")) == sorted(TABLES)
    assert sorted(x[0] for x in q("SELECT table_name FROM information_schema.tables WHERE table_schema='stg'")) == sorted(TABLES)
    con = dict((x[0], int(x[1])) for x in q("SELECT contype, count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='core' GROUP BY contype"))
    assert con == {"p": 10, "f": 18, "u": 8, "c": 55}, con
    assert int(qv("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='core' AND NOT convalidated")) == 0
    assert int(qv("SELECT count(*) FROM pg_indexes WHERE schemaname='core' AND indexname LIKE 'ix\\_%'")) == 13
    assert sorted(x[0] for x in q("SELECT table_name||'.'||column_name FROM information_schema.columns WHERE table_schema='core' AND is_nullable='YES'")) == sorted(
        ["train_stops.arrival_time", "train_stops.departure_time", "calendar.holiday_name", "calendar.peak_period_name", "train_operations.arrival_delay_min", "booking_passengers.cancellation_id"])
    views = {x[0] for x in q("SELECT table_name FROM information_schema.views WHERE table_schema='analytics'")}
    assert {"v_booking", "v_passenger", "v_class_run", "v_run", "v_monthly_kpis", "v_kpi_overall", "v_kpi_overall_long", "v_monthly_kpis_long", "dim_date", "dim_station", "dim_route", "dim_train", "dim_travel_class", "fact_passenger", "fact_booking", "fact_class_run", "fact_train_run", "fact_cancellation_event"} <= views


def test_row_counts_equal_csv_and_phase2_cleaned_counts():
    built()
    mv = pd.read_csv(REP / "data_quality/row_movement.csv").set_index("table")["clean_rows"]
    for t in TABLES:
        n_csv = len(pd.read_csv(CLEAN / f"{t}.csv"))
        assert int(qv(f"SELECT count(*) FROM stg.{t}")) == n_csv == int(qv(f"SELECT count(*) FROM core.{t}")) == int(mv[t]), t


def test_loaded_values_equal_the_csv_files():
    built()
    bk, ps, ev = pd.read_csv(CLEAN / "bookings.csv"), pd.read_csv(CLEAN / "booking_passengers.csv"), pd.read_csv(CLEAN / "cancellations.csv")
    assert abs(float(qv("SELECT sum(total_fare) FROM core.bookings")) - bk.total_fare.sum()) < 0.01
    assert abs(float(qv("SELECT sum(fare_amount) FROM core.booking_passengers")) - ps.fare_amount.sum()) < 0.01
    assert abs(float(qv("SELECT sum(refund_amount) FROM core.cancellations")) - ev.refund_amount.sum()) < 0.01
    assert int(qv("SELECT sum(booking_id) FROM core.bookings")) == int(bk.booking_id.sum()) and int(qv("SELECT sum(passenger_id) FROM core.booking_passengers")) == int(ps.passenger_id.sum())
    assert qv("SELECT min(journey_date)||' to '||max(journey_date) FROM core.bookings") == f"{bk.journey_date.min()} to {bk.journey_date.max()}"
    assert int(qv("SELECT count(*) FROM core.train_operations WHERE arrival_delay_min IS NULL")) == int(pd.read_csv(CLEAN / "train_operations.csv").arrival_delay_min.isna().sum())
    assert int(qv("SELECT count(*) FROM core.booking_passengers WHERE age_band='Unknown'")) == int((ps.age_band == "Unknown").sum())
    assert qv("SELECT train_name FROM core.trains ORDER BY train_id LIMIT 1") == pd.read_csv(CLEAN / "trains.csv").train_name.iloc[0]      # the en dash survives the UTF-8 load


def test_source_data_files_are_unchanged():
    now = {}
    for folder in ("data/raw/synthetic", "data/processed/cleaned"):
        for t in TABLES:
            p = ROOT / folder / f"{t}.csv"
            now[f"{folder}/{t}.csv"] = hashlib.sha256(p.read_bytes()).hexdigest()
    assert now == json.loads((REP / "phase3_data_manifest.json").read_text())


def test_phase4_leaves_approved_phase1_to_phase3_deliverables_unchanged():
    zp = ROOT.parent / "irctc-analytics-phase3-final.zip"
    assert zp.exists(), "irctc-analytics-phase3-final.zip (approved Phase 3 package) not found next to the project folder"
    allowed = {"README.md", "docs/project_plan.md", "docs/KPI_consistency_matrix.md", "requirements.txt", ".gitignore", "reports/phase1_validation.txt", "reports/phase2_validation.txt", "reports/phase3_validation.txt", "python/tests/test_phase3_excel.py", "python/tests/audit_phase3.py", "reports/phase3_review_report.md", "reports/phase3_audit_results.txt"}
    z = zipfile.ZipFile(zp); changed = []
    for n in z.namelist():
        rel = n.split("/", 1)[1]
        if rel in allowed or rel.endswith(".pyc"):
            continue
        p = ROOT / rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != hashlib.sha256(z.read(n)).hexdigest():
            changed.append(rel)
    assert not changed, changed


# ------------------------------------------------------------------ constraints reject bad data
NEGATIVE = [
    ("duplicate primary key", "INSERT INTO core.stations SELECT * FROM core.stations LIMIT 1;", "pk_stations"),
    ("unique booking reference", "UPDATE core.bookings SET booking_reference = (SELECT booking_reference FROM core.bookings WHERE booking_id=1000002) WHERE booking_id=1000001;", "uq_bookings_reference"),
    ("foreign key (route)", "UPDATE core.bookings SET route_id = 99999 WHERE booking_id = 1000001;", "fk_bookings_route"),
    ("composite foreign key to seat_capacity (BR-07)", "UPDATE core.bookings SET travel_class = '1A' WHERE booking_id = (SELECT booking_id FROM core.bookings WHERE travel_class='SL' LIMIT 1);", "fk_bookings_capacity"),
    ("passenger status domain (BR-01)", "UPDATE core.booking_passengers SET final_status = 'Boarded' WHERE passenger_id = 1;", "ck_booking_passengers_final"),
    ("cancellation link (BR-10a)", "UPDATE core.booking_passengers SET final_status='Confirmed' WHERE passenger_id=(SELECT passenger_id FROM core.booking_passengers WHERE final_status='Cancelled' AND initial_status='Waitlisted' LIMIT 1);", "ck_booking_passengers_link"),
    ("status demotion (BR-17)", "UPDATE core.booking_passengers SET final_status='RAC' WHERE passenger_id=(SELECT passenger_id FROM core.booking_passengers WHERE initial_status='Confirmed' AND final_status='Confirmed' LIMIT 1);", "ck_booking_passengers_transition"),
    ("refund arithmetic (BR-11c)", "UPDATE core.cancellations SET refund_amount = refund_amount + 1 WHERE cancellation_id = 1;", "ck_cancellations_arithmetic"),
    ("System events are Waitlisted (BR-11d)", "UPDATE core.cancellations SET status_at_cancellation='Confirmed' WHERE cancellation_id=(SELECT cancellation_id FROM core.cancellations WHERE cancellation_type='System' LIMIT 1);", "ck_cancellations_system"),
    ("capacity arithmetic (BR-09a)", "UPDATE core.seat_capacity SET total_seats = total_seats + 1 WHERE capacity_id = 1;", "ck_seat_capacity_total"),
    ("class standard seats (BR-09b)", "UPDATE core.seat_capacity SET seats_per_coach = 70 WHERE capacity_id=(SELECT capacity_id FROM core.seat_capacity WHERE travel_class='SL' LIMIT 1);", "ck_seat_capacity_"),
    ("station code format (BR-16)", "UPDATE core.stations SET station_code = lower(station_code) WHERE station_id = 1;", "ck_stations_code_format"),
    ("NOT NULL booking_ts", "UPDATE core.bookings SET booking_ts = NULL WHERE booking_id = 1000001;", 'null value in column "booking_ts"'),
    ("delete of a referenced row", "DELETE FROM core.trains WHERE train_id = 1;", "violates foreign key constraint"),
    ("holiday needs a name", "UPDATE core.calendar SET holiday_name = NULL WHERE calendar_date = (SELECT calendar_date FROM core.calendar WHERE is_holiday LIMIT 1);", "ck_calendar_holiday_name"),
    ("passengers per booking 1..6", "UPDATE core.bookings SET num_passengers = 7 WHERE booking_id = 1000001;", "ck_bookings_pax"),
    ("boarding differs from destination", "UPDATE core.bookings SET destination_station_id = boarding_station_id WHERE booking_id = 1000001;", "ck_bookings_stations"),
    ("run_days pattern", "UPDATE core.trains SET run_days = 'NNNNNNN' WHERE train_id = 1;", "ck_trains_run_days"),
    ("positive route distance", "UPDATE core.routes SET distance_km = 0 WHERE route_id = 1;", "ck_routes_distance"),
]


def test_constraints_reject_invalid_data():
    built(); before = counts(); failures = []
    for name, stmt, expected in NEGATIVE:
        r = run(sql=f"BEGIN;\n{stmt}\nROLLBACK;")
        if r.returncode == 0 or expected not in r.stderr:
            failures.append((name, r.returncode, r.stderr.strip()[:160]))
    assert not failures, failures
    assert counts() == before


# ------------------------------------------------------------------ data-quality checks
def test_all_data_quality_checks_pass():
    built()
    n, passed, failed = (int(x) for x in q("SELECT checks, passed, failed FROM qa.v_check_summary")[0])
    assert n >= 70 and failed == 0 and passed == n, q("SELECT check_id, violations FROM qa.v_check_results WHERE violations <> 0")
    assert int(qv("SELECT count(*) FROM qa.check_results WHERE NOT passed")) == 0 and int(qv("SELECT count(*) FROM qa.check_results")) == n
    cats = {x[0] for x in q("SELECT DISTINCT category FROM qa.check_results")}
    assert {"STRUCTURE", "ROWS", "BUSINESS RULE", "DOMAIN", "LABELLING", "SIZE"} <= cats
    ids = {x[0] for x in q("SELECT check_id FROM qa.check_results")}
    for i in range(1, 18):
        assert any(c == f"BR-{i:02d}" or c.startswith(f"BR-{i:02d}") for c in ids), f"BR-{i:02d} has no check"


MUTATIONS = [
    ("BR-03a", "UPDATE core.bookings SET num_passengers = CASE WHEN num_passengers = 6 THEN 5 ELSE num_passengers + 1 END WHERE booking_id = 1000001;"),
    ("BR-03b", "UPDATE core.bookings SET total_fare = total_fare + 1 WHERE booking_id = 1000001;"),
    ("BR-02", "UPDATE core.bookings SET booking_status = 'Mixed' WHERE booking_id = (SELECT booking_id FROM core.bookings WHERE booking_status = 'Confirmed' LIMIT 1);"),
    ("BR-04b", "UPDATE core.bookings SET booking_ts = journey_date + time '23:30' WHERE booking_id = (SELECT booking_id FROM core.bookings LIMIT 1);"),
    ("BR-05b", "DELETE FROM core.train_operations WHERE (train_id, run_date) = (SELECT train_id, journey_date FROM core.bookings LIMIT 1);"),
    ("BR-08b", "UPDATE core.seat_capacity SET rac_berths = 0 WHERE capacity_id = (SELECT capacity_id FROM analytics.v_class_run WHERE rac_pax > 0 LIMIT 1);"),
    ("BR-11a", "UPDATE core.cancellations SET cancelled_passengers = CASE WHEN cancelled_passengers = 6 THEN 5 ELSE cancelled_passengers + 1 END WHERE cancellation_id = 1;"),
    ("BR-12", "UPDATE core.cancellations SET cancellation_ts = cancellation_ts + interval '400 days' WHERE cancellation_id = 1;"),
    ("BR-13", "UPDATE core.train_stops SET distance_from_origin_km = 0 WHERE train_id = 1 AND stop_sequence = 2;"),
    ("BR-14", "ALTER TABLE core.stations ADD COLUMN email text;"),
    ("DOM-origin", "UPDATE core.stations SET data_origin = 'PUBLIC' WHERE station_id = 1;"),
    ("ROWS-stg-core-stations", "DELETE FROM stg.stations WHERE station_id = '1';"),
    ("STRUCT-check-constraints", "ALTER TABLE core.stations DROP CONSTRAINT ck_stations_region;"),
]


def test_validation_detects_deliberate_corruption():
    built(); missed = []
    for check, mutation in MUTATIONS:
        out = result_of(f"BEGIN;\n{mutation}\nSELECT 'RESULT|' || violations FROM qa.v_check_results WHERE check_id = '{check}';\nROLLBACK;")
        if not out or int(out[0]) <= 0:
            missed.append((check, out))
    assert not missed, missed
    assert int(qv("SELECT failed FROM qa.v_check_summary")) == 0          # every mutation was rolled back


# ------------------------------------------------------------------ KPI reconciliation
def test_kpi_reconciliation_against_reference_file_passes():
    built()
    ref = pd.read_csv(REP / "kpi_reference_values.csv")
    rec = pd.DataFrame(q("SELECT kpi_key, reference_value, sql_value, abs_diff, tolerance, passed FROM qa.v_kpi_reconciliation ORDER BY kpi_key"), columns=["kpi_key", "ref", "sql", "diff", "tol", "passed"])
    assert len(rec) == len(ref) == 31 and set(rec.kpi_key) == set(ref.kpi_key)
    assert (rec.passed == "t").all(), rec[rec.passed != "t"]
    chk = rec.merge(ref[["kpi_key", "value"]], on="kpi_key")
    assert (chk.ref.astype(float) - chk.value).abs().max() < 1e-9               # the reference table is a faithful copy of the CSV, not altered
    assert (rec["sql"].astype(float) - rec["ref"].astype(float)).abs().max() < 0.005


def test_monthly_kpi_reconciliation_passes():
    built()
    n, p = (int(x) for x in q("SELECT count(*), count(*) FILTER (WHERE passed) FROM qa.v_monthly_kpi_reconciliation")[0])
    assert n == 24 * 40 and p == n


def test_kpi_views_never_read_the_reference_tables():
    built()
    for v in ("v_booking", "v_passenger", "v_class_run", "v_run", "v_monthly_kpis", "v_kpi_overall", "v_kpi_overall_long", "v_monthly_kpis_long"):
        d = qv(f"SELECT pg_get_viewdef('analytics.{v}'::regclass)")
        assert "qa." not in d and "kpi_reference" not in d, v
    assert dict(q("SELECT parameter_name, parameter_value FROM analytics.kpi_parameter")) == {"rac_seat_weight": "0.5", "on_time_threshold_min": "15", "chart_prep_hours": "4", "max_advance_days": "120"}


def test_sql_kpis_equal_independent_pandas_calculation():
    built()
    bk, ps, ev, cap, ops = (pd.read_csv(CLEAN / f"{t}.csv") for t in ("bookings", "booking_passengers", "cancellations", "seat_capacity", "train_operations"))
    fs, ist = ps.final_status, ps.initial_status
    exp = {"total_bookings": len(bk), "total_passengers": len(ps), "passenger_cancellation_rate": (fs == "Cancelled").mean(), "wl_demand": (ist == "Waitlisted").sum(),
           "wl_clearance_rate": ((ist == "Waitlisted") & fs.isin(["Confirmed", "RAC"])).sum() / (ist == "Waitlisted").sum(), "gross_value": bk.total_fare.sum(), "net_value": bk.total_fare.sum() - ev.refund_amount.sum(),
           "occupancy": ((fs == "Confirmed").sum() + 0.5 * (fs == "RAC").sum()) / cap.total_seats.sum(), "otp": (ops.arrival_delay_min.dropna() <= 15).mean()}
    got = dict((k, float(v)) for k, v in q("SELECT kpi_key, value FROM analytics.v_kpi_overall_long WHERE kpi_key IN (" + ",".join(f"'{k}'" for k in exp) + ")"))
    bad = {k: (got[k], exp[k]) for k in exp if abs(got[k] - float(exp[k])) > 1e-6 * max(1, abs(float(exp[k])))}
    assert not bad, bad


def test_reconciliation_detects_a_wrong_kpi_or_a_changed_parameter():
    built()
    out = result_of("BEGIN;\nUPDATE core.bookings SET total_fare = total_fare + 1 WHERE booking_id = 1000001;\n"
                    "SELECT 'RESULT|' || string_agg(kpi_key, ',' ORDER BY kpi_key) FROM qa.v_kpi_reconciliation WHERE NOT passed;\nROLLBACK;")
    assert out and "gross_value" in out[0] and "net_value" in out[0], out
    out = result_of("BEGIN;\nUPDATE analytics.kpi_parameter SET parameter_value = 0.6 WHERE parameter_name = 'rac_seat_weight';\n"
                    "SELECT 'RESULT|' || string_agg(kpi_key, ',' ORDER BY kpi_key) FROM qa.v_kpi_reconciliation WHERE NOT passed;\nROLLBACK;")
    assert out and "occupancy" in out[0] and "booked_seats" in out[0], out
    assert int(qv("SELECT count(*) FROM qa.v_kpi_reconciliation WHERE NOT passed")) == 0


# ------------------------------------------------------------------ analytical SQL
def test_every_analysis_file_runs_without_error():
    built(); before = counts()
    for f in sorted((SQL / "analysis").glob("0*.sql")):
        r = run(["-f", str(f)])
        assert r.returncode == 0 and "ERROR" not in r.stderr, (f.name, r.stderr[-400:])
    assert counts() == before
    assert int(qv("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'sandbox'")) == 0         # DDL/DML examples cleaned up after themselves


def test_analysis_results_match_pandas():
    built()
    bk, ps, ops, trains = (pd.read_csv(CLEAN / f"{t}.csv") for t in ("bookings", "booking_passengers", "train_operations", "trains"))
    # G1: passenger-based cancellation rate by class
    m = ps.merge(bk[["booking_id", "travel_class"]], on="booking_id")
    exp = (m.groupby("travel_class").final_status.apply(lambda s: round((s == "Cancelled").mean(), 4)))
    got = {r[0]: float(r[3]) for r in rows(block("02_group_by_having.sql", "G1"))}
    assert got == {k: float(v) for k, v in exp.items()}
    # W2: RANK vs DENSE_RANK on simulated runs per train
    runs = ops.merge(trains[["train_id", "train_number"]], on="train_id").groupby("train_number").size().rename("n").reset_index().sort_values(["n", "train_number"], ascending=[False, True]).reset_index(drop=True)
    runs["rank"] = runs.n.rank(method="min", ascending=False).astype(int); runs["dense"] = runs.n.rank(method="dense", ascending=False).astype(int)
    sql_rows = rows(block("05_window_functions.sql", "W2"))
    assert [(r[0], int(r[1]), int(r[2]), int(r[3])) for r in sql_rows] == [(r.train_number, r.n, r["rank"], r.dense) for _, r in runs.head(15).iterrows()]
    assert any(r[2] != r[3] for r in sql_rows), "ties should make RANK and DENSE_RANK differ"
    # W4: LAG growth equals the Phase 3 derived monthly file
    mo = pd.read_csv(DER / "monthly_kpis.csv").set_index("journey_month")
    for r in rows(block("05_window_functions.sql", "W4")):
        e = mo.loc[r[0], "bookings_per_run_growth"]
        assert (r[3] == "" and np.isnan(e)) or abs(float(r[3]) - e) < 6e-5, r
    # J6: legs add up to the route distance
    for r in rows(block("01_joins.sql", "J6")):
        assert abs(float(r[1]) - float(r[2])) < 1e-6
    # J8: right-grain join keeps seats and passengers whole
    j8 = rows(block("01_joins.sql", "J8"))
    assert sum(int(r[1]) for r in j8) == pd.read_csv(CLEAN / "seat_capacity.csv").total_seats.sum() and sum(int(r[2]) for r in j8) == len(ps)
    # C2: occupancy bands against the Phase 3 class-run file
    oc = pd.read_csv(DER / "occupancy_class_runs.csv").occupancy
    bands = {r[0]: int(r[1]) for r in rows(block("03_case_subqueries.sql", "C2"))}
    assert bands == {"Below 50%": int((oc < .5).sum()), "50% to below 75%": int(((oc >= .5) & (oc < .75)).sum()), "75% to below 95%": int(((oc >= .75) & (oc < .95)).sum()), "95% and above": int((oc >= .95).sum())}
    # T1: waiting-list funnel totals equal the reference KPIs; T2: recursive CTE agrees with stored distances
    ref = pd.read_csv(REP / "kpi_reference_values.csv").set_index("kpi_key")["value"]
    t1 = rows(block("04_ctes.sql", "T1"))
    assert sum(int(r[1]) for r in t1) == ref["wl_demand"] and sum(int(r[2]) for r in t1) == ref["wl_cleared"] and sum(int(r[4]) for r in t1) == ref["wl_uncleared"]
    assert all(r[4] == "t" for r in rows(block("04_ctes.sql", "T2")))
    # K blocks equal the reference file
    k5 = rows(block("06_business_kpi_queries.sql", "K5"))[0]; assert abs(float(k5[2]) - ref["passenger_cancellation_rate"]) < 6e-5 and abs(float(k5[5]) - ref["booking_cancellation_rate"]) < 6e-5
    k10 = rows(block("06_business_kpi_queries.sql", "K10"))[0]; assert abs(float(k10[2]) - ref["occupancy"]) < 6e-5 and abs(float(k10[5]) - ref["waitlist_pressure"]) < 6e-5
    refdf = pd.read_csv(REP / "kpi_reference_values.csv").set_index("kpi_key")
    k12 = rows(block("06_business_kpi_queries.sql", "K12"))[0]; assert int(k12[0]) == refdf.loc["otp", "numerator"] and int(k12[1]) == refdf.loc["otp", "denominator"] and abs(float(k12[2]) - ref["otp"]) < 6e-5
    assert abs(float(rows(block("06_business_kpi_queries.sql", "K6"))[0][0]) - ref["gross_value"]) < 0.005


def test_required_sql_features_are_all_demonstrated():
    text = {f.name: f.read_text(encoding="utf-8").upper() for f in (SQL / "analysis").glob("0*.sql")}
    allsql = "\n".join(text.values())
    need = {"INNER JOIN (JOIN ... ON)": r"\bJOIN\b", "LEFT JOIN": r"LEFT JOIN", "RIGHT JOIN": r"RIGHT JOIN", "FULL OUTER JOIN": r"FULL OUTER JOIN", "CROSS JOIN": r"CROSS JOIN", "GROUP BY": r"GROUP BY", "HAVING": r"\bHAVING\b",
            "CASE": r"\bCASE\b", "IN subquery": r"\bIN \(SELECT", "EXISTS": r"\bEXISTS \(", "NOT EXISTS": r"NOT EXISTS", "scalar subquery": r"\(\s*SELECT [A-Z_]+\(", "CTE": r"\bWITH [A-Z_]+ AS", "recursive CTE": r"WITH RECURSIVE",
            "ROW_NUMBER": r"ROW_NUMBER\(\)", "RANK": r"\bRANK\(\)", "DENSE_RANK": r"DENSE_RANK\(\)", "LAG": r"\bLAG\(", "LEAD": r"\bLEAD\(", "ROLLUP": r"ROLLUP", "GROUPING SETS": r"GROUPING SETS", "FILTER": r"FILTER \(WHERE",
            "CREATE TABLE": r"CREATE TABLE", "ALTER TABLE": r"ALTER TABLE", "CREATE INDEX": r"CREATE INDEX", "INSERT": r"\bINSERT INTO", "UPDATE": r"\bUPDATE\b", "DELETE": r"\bDELETE FROM", "MERGE": r"\bMERGE INTO", "TRUNCATE": r"\bTRUNCATE", "DROP": r"\bDROP SCHEMA"}
    missing = [k for k, p in need.items() if not re.search(p, allsql)]
    assert not missing, missing
    assert re.search(r"INSERT INTO", text["07_ddl_dml_examples.sql"]) and "MERGE INTO" in text["07_ddl_dml_examples.sql"]
    for kid in range(1, 16):
        assert f"-- [K{kid}]" in (SQL / "analysis/06_business_kpi_queries.sql").read_text(encoding="utf-8"), f"KPI {kid} query missing"


def test_star_schema_views_are_complete_and_join_cleanly():
    built()
    assert int(qv("SELECT count(*) FROM analytics.fact_passenger")) == int(qv("SELECT count(*) FROM core.booking_passengers"))
    assert int(qv("SELECT count(*) FROM analytics.fact_booking")) == int(qv("SELECT count(*) FROM core.bookings"))
    assert int(qv("SELECT count(*) FROM analytics.fact_class_run")) == 2285 and int(qv("SELECT count(*) FROM analytics.fact_train_run")) == 768
    assert int(qv("SELECT count(*) FROM analytics.fact_cancellation_event")) == int(qv("SELECT count(*) FROM core.cancellations"))
    orphans = 0
    for fact in ("fact_passenger", "fact_booking", "fact_class_run", "fact_train_run", "fact_cancellation_event"):
        for key, dim, dk in (("date_key", "dim_date", "date_key"), ("train_key", "dim_train", "train_key"), ("class_key", "dim_travel_class", "class_key")):
            if fact == "fact_train_run" and key == "class_key":
                continue
            orphans += int(qv(f"SELECT count(*) FROM analytics.{fact} f LEFT JOIN analytics.{dim} d ON d.{dk} = f.{key} WHERE d.{dk} IS NULL"))
        if fact in ("fact_passenger", "fact_booking", "fact_train_run", "fact_cancellation_event"):
            orphans += int(qv(f"SELECT count(*) FROM analytics.{fact} f LEFT JOIN analytics.dim_route d ON d.route_key = f.route_key WHERE d.route_key IS NULL"))
    assert orphans == 0
    # a star query reproduces the KPI: gross value and passengers by month and class equal the booking view
    a = q("SELECT d.year_month, c.class_key, sum(f.total_fare) FROM analytics.fact_booking f JOIN analytics.dim_date d ON d.date_key = f.date_key JOIN analytics.dim_travel_class c ON c.class_key = f.class_key GROUP BY 1, 2 ORDER BY 1, 2")
    b = q("SELECT journey_month, travel_class, sum(total_fare) FROM analytics.v_booking GROUP BY 1, 2 ORDER BY 1, 2")
    assert a == b


def test_indexes_support_selective_lookups():
    built()
    def plan(sql):
        r = run(["-At", "-c", f"EXPLAIN (FORMAT JSON) {sql}"]); assert r.returncode == 0, r.stderr
        return r.stdout
    assert "Index" in plan("SELECT * FROM core.bookings WHERE booking_id = 1000100")
    assert "ix_bookings_run_class" in plan("SELECT * FROM core.bookings WHERE train_id = 5 AND journey_date = (SELECT journey_date FROM core.seat_capacity WHERE train_id = 5 LIMIT 1) AND travel_class = 'SL'") or "uq_seat_capacity_run_class" in plan("SELECT * FROM core.seat_capacity WHERE train_id = 5 AND journey_date = DATE '2025-01-01' AND travel_class = 'SL'")
    assert "ix_cancellations_booking" in plan("SELECT * FROM core.cancellations WHERE booking_id = 1000100")
    assert "ix_bp_cancellation" in plan("SELECT * FROM core.booking_passengers WHERE cancellation_id = 100")


# ------------------------------------------------------------------ labelling, scope and documentation
def test_synthetic_and_sampling_limitations_are_stated_in_the_database():
    built()
    for s in ("stg", "core", "analytics"):
        c = qv(f"SELECT obj_description('{s}'::regnamespace, 'pg_namespace')")
        assert "SYNTHETIC" in c.upper() and "19,708" in c, (s, c)
    qa_c = qv("SELECT obj_description('qa'::regnamespace, 'pg_namespace')"); assert "SYNTHETIC" in qa_c.upper() and "19,708" in qa_c
    assert int(qv("SELECT count(*) FROM core.stations WHERE data_origin <> 'SYNTHETIC'")) == 0
    for v in ("v_class_run", "v_monthly_kpis", "v_kpi_overall"):
        c = qv(f"SELECT obj_description('analytics.{v}'::regclass, 'pg_class')")
        assert "ynthetic" in c or "SYNTHETIC" in c or "ampled" in c or "network-wide" in c, v


def test_no_forecast_objects_or_statements():
    built()
    assert int(qv("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('stg','core','analytics','qa') AND c.relname ILIKE '%forecast%'")) == 0
    assert int(qv("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('analytics','qa') AND p.proname ILIKE '%forecast%'")) == 0
    for f in SQL.rglob("*.sql"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if re.search(r"forecast", line, re.I):
                assert re.search(r"\b(?:no|nothing|not)\b", line, re.I), (f.name, line)          # only negations: nothing here forecasts


def test_runner_scripts_and_master_script_are_safe_and_complete():
    ps, sh = (SQL / "run_all.ps1").read_text(encoding="utf-8"), (SQL / "run_all.sh").read_text(encoding="utf-8")
    master = (SQL / "00_build_all.sql").read_text(encoding="utf-8")
    for t in (ps, sh):
        assert "ON_ERROR_STOP=1" in t and "00_build_all.sql" in t and "YES" in t and "pipeline.py" in t
    assert "postgresql-x64-18" in ps and "$PgHost" in ps and "$Host " not in ps and "PGCLIENTENCODING" in ps and "Program Files\\PostgreSQL" in ps
    assert ps.count("{") == ps.count("}") and ps.count("(") == ps.count(")")
    assert "current_database() = :'expected_db'" in master and "\\quit" in master and master.count("\\ir ") == 14
    order = re.findall(r"\\ir (\S+)", master)
    for f in order:
        assert (SQL / f).is_file(), f
    assert order.index("transformations/02_load_core.sql") < order.index("schema/03_indexes.sql") < order.index("transformations/04_analytics_views.sql") < order.index("validation/03_run_validation.sql")


def test_documentation_covers_phase4():
    d = (ROOT / "docs/phase4_postgresql.md").read_text(encoding="utf-8")
    for needle in ["PostgreSQL 18", "psql", "postgresql-x64-18", "run_all.ps1", "synthetic", "19,708", "No forecasts", "sampled", "stg", "core", "analytics", "qa", "reconciliation", "ROW_NUMBER", "DENSE_RANK", "LAG", "LEAD", "Troubleshooting", "not been run on PostgreSQL 18"]:
        assert needle.lower() in d.lower(), needle
    assert "Phase 4" in (ROOT / "README.md").read_text(encoding="utf-8") and (SQL / "README.md").exists()


# ------------------------------------------------------------------ runner
def _tests():
    return [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno if callable(kv[1]) and hasattr(kv[1], "__code__") else 0) if n.startswith("test_") and callable(f)]


def main():
    lines, passed, failed = [], 0, 0
    for name, fn in _tests():
        try:
            fn(); lines.append(f"PASS  {name}"); passed += 1
        except Exception as e:
            lines.append(f"FAIL  {name}\n        {type(e).__name__}: {str(e)[:600]}"); failed += 1; traceback.print_exc()
    info = []
    try:
        info.append("Server: " + qv("SELECT version()"))
        info.append(f"Database: {qv('SELECT current_database()')} | encoding {qv('SHOW server_encoding')} | client {qv('SHOW client_encoding')}")
        tbl = []
        for sch in ("stg", "core"):
            for (t,) in q(f"SELECT table_name FROM information_schema.tables WHERE table_schema='{sch}' AND table_type='BASE TABLE' ORDER BY table_name"):
                tbl.append(f"  {sch}.{t:<22} {int(qv(f'SELECT count(*) FROM {sch}.{t}')):>9,} rows")
        info += ["Tables and rows loaded:"] + tbl
        info.append("Other objects: " + qv("SELECT count(*) FROM information_schema.views WHERE table_schema='analytics'") + " analytics views, " + qv("SELECT count(*) FROM pg_indexes WHERE schemaname='core' AND indexname LIKE 'ix\\_%'") + " secondary indexes, "
                    + qv("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='core'") + " constraints in core")
        c = q("SELECT checks, passed, failed FROM qa.v_check_summary")[0]
        info.append(f"Data-quality checks (stored in qa.check_results): {c[1]} of {c[0]} passed, {c[2]} failed")
        for s, n, p, f in q("SELECT * FROM qa.v_reconciliation_summary"):
            info.append(f"KPI reconciliation, {s}: {p} of {n} comparisons within tolerance ({f} failed)")
    except Exception as e:
        info.append(f"(could not query the database for the report: {e})")
    out = [f"Phase 4 validation run: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}",
           "Command: python python/tests/test_phase4_postgres.py    (build: sql/run_all.ps1 or sql/run_all.sh)",
           f"Client: Python {platform.python_version()}, pandas {pd.__version__}, {subprocess.run([PSQL, '--version'], capture_output=True, text=True).stdout.strip()}, OS {platform.system()}", "",
           "== A. Test suite ==", *lines, "", f"{passed} passed, {failed} failed, {passed + failed} total", "", "== B. PostgreSQL results (measured in this run) ==", *info, "",
           "== C. Scope notes ==", "- All data is SYNTHETIC from a SAMPLED simulation (768 simulated runs of 19,708 scheduled); not IRCTC or Indian Railways data; no forecasts.",
           "- The target environment (PostgreSQL 18.4 on Windows, service postgresql-x64-18) was not reachable from the build environment; see docs/phase4_postgresql.md for how to run this suite there."]
    text = "\n".join(out)
    print(text)
    if "--no-write" not in sys.argv:
        (REP / "phase4_postgresql_validation.txt").write_text(text + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
