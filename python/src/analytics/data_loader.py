"""Reproducible data-ingestion layer. Reads the validated Phase 2 cleaned tables and the Phase 3/4 reference outputs; never writes to them.

Source of truth: data/processed/cleaned/*.csv (the FULL cleaned dataset: 201,182 bookings, 405,200 passengers). The 48-run Excel sample
(data/sample/excel) is NOT used here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CLEAN_DIR = ROOT / "data" / "processed" / "cleaned"
RAW_DIR = ROOT / "data" / "raw" / "synthetic"
DERIVED_DIR = ROOT / "data" / "processed" / "derived"
REPORTS_DIR = ROOT / "reports"

TABLES = ["stations", "routes", "trains", "train_stops", "calendar", "seat_capacity", "train_operations", "bookings", "booking_passengers", "cancellations"]

# i int64, I nullable Int64, f float64, s str, b bool, d date (parsed), t timestamp (parsed)
SCHEMA = {
    "stations": dict(station_id="i", station_code="s", station_name="s", city="s", state="s", region="s", data_origin="s"),
    "routes": dict(route_id="i", origin_station_id="i", destination_station_id="i", route_name="s", distance_km="f", data_origin="s"),
    "trains": dict(train_id="i", train_number="s", train_name="s", train_type="s", route_id="i", run_days="s", data_origin="s"),
    "train_stops": dict(train_id="i", stop_sequence="i", station_id="i", arrival_time="s", departure_time="s", day_offset="i", distance_from_origin_km="f", data_origin="s"),
    "calendar": dict(calendar_date="d", year="i", quarter="i", month_number="i", month_name="s", week_of_year="i", day_of_month="i", day_of_week_number="i", day_name="s",
                     is_weekend="b", season="s", fiscal_year="i", is_holiday="b", holiday_name="s", is_peak_travel_period="b", peak_period_name="s", data_origin="s"),
    "seat_capacity": dict(capacity_id="i", train_id="i", journey_date="d", travel_class="s", coaches_attached="i", seats_per_coach="i", total_seats="i", rac_berths="i", wl_limit="i", data_origin="s"),
    "train_operations": dict(operation_id="i", train_id="i", run_date="d", departure_delay_min="i", arrival_delay_min="I", data_origin="s"),
    "bookings": dict(booking_id="i", booking_reference="s", train_id="i", journey_date="d", route_id="i", boarding_station_id="i", destination_station_id="i", travel_class="s",
                     booking_ts="t", num_passengers="i", booking_status="s", total_fare="f", data_origin="s"),
    "booking_passengers": dict(passenger_id="i", booking_id="i", passenger_seq="i", age_band="s", fare_amount="f", initial_status="s", final_status="s", cancellation_id="I", data_origin="s"),
    "cancellations": dict(cancellation_id="i", booking_id="i", cancellation_ts="t", cancellation_type="s", status_at_cancellation="s", cancelled_passengers="i",
                          original_fare_amount="f", cancellation_charge="f", refund_amount="f", data_origin="s"),
}
_DTYPE = {"i": "int64", "I": "Int64", "f": "float64", "s": "str", "b": "bool"}

# foreign-key relationships (child table, child column, parent table, parent column): the same 16 single-column relationships as docs/data_dictionary.md
RELATIONSHIPS = [
    ("routes", "origin_station_id", "stations", "station_id"), ("routes", "destination_station_id", "stations", "station_id"), ("trains", "route_id", "routes", "route_id"),
    ("train_stops", "train_id", "trains", "train_id"), ("train_stops", "station_id", "stations", "station_id"), ("seat_capacity", "train_id", "trains", "train_id"),
    ("seat_capacity", "journey_date", "calendar", "calendar_date"), ("train_operations", "train_id", "trains", "train_id"), ("train_operations", "run_date", "calendar", "calendar_date"),
    ("bookings", "train_id", "trains", "train_id"), ("bookings", "journey_date", "calendar", "calendar_date"), ("bookings", "route_id", "routes", "route_id"),
    ("bookings", "boarding_station_id", "stations", "station_id"), ("bookings", "destination_station_id", "stations", "station_id"),
    ("booking_passengers", "booking_id", "bookings", "booking_id"), ("booking_passengers", "cancellation_id", "cancellations", "cancellation_id"),
    ("cancellations", "booking_id", "bookings", "booking_id"),
]
REFERENCE_FILES = {
    "kpi_reference": REPORTS_DIR / "kpi_reference_values.csv",
    "monthly_reference": DERIVED_DIR / "monthly_kpis.csv",
    "row_movement": REPORTS_DIR / "data_quality" / "row_movement.csv",
    "phase4_checks": REPORTS_DIR / "phase4_check_results.csv",
    "phase4_kpi": REPORTS_DIR / "phase4_kpi_reconciliation.csv",
}


def source_paths() -> list[Path]:
    """Every file the Phase 5 analysis reads (cleaned tables, the raw originals they came from, and the reference outputs)."""
    paths = [CLEAN_DIR / f"{t}.csv" for t in TABLES] + [RAW_DIR / f"{t}.csv" for t in TABLES] + list(REFERENCE_FILES.values())
    return [p for p in paths if p.exists()]


def fingerprint(paths: list[Path] | None = None) -> dict:
    """SHA-256, size and modification time of each file: used to prove that the analysis did not change any source file."""
    out = {}
    for p in paths if paths is not None else source_paths():
        st = p.stat()
        out[str(p.relative_to(ROOT)).replace("\\", "/")] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
    return out


def load_cleaned(clean_dir: Path = CLEAN_DIR) -> dict[str, pd.DataFrame]:
    """Read the cleaned tables with explicit dtypes (read-only). Dates and timestamps are parsed; nullable integers stay nullable."""
    tables = {}
    for name in TABLES:
        spec = SCHEMA[name]
        dtype = {c: _DTYPE[k] for c, k in spec.items() if k in _DTYPE}
        parse = [c for c, k in spec.items() if k in ("d", "t")]
        df = pd.read_csv(clean_dir / f"{name}.csv", dtype=dtype, parse_dates=parse)
        assert list(df.columns) == list(spec), f"{name}: unexpected columns {list(df.columns)}"
        tables[name] = df
    return tables


def load_reference() -> dict:
    """Phase 2/3/4 reference outputs (values the Python analysis is compared with). Missing optional files are returned as None."""
    ref = {k: (pd.read_csv(p) if p.exists() else None) for k, p in REFERENCE_FILES.items()}
    for key in ("phase4_checks", "phase4_kpi"):          # PostgreSQL exported booleans as t / f
        df = ref[key]
        if df is not None and "passed" in df:
            df["passed"] = df["passed"].astype(str).str.lower().isin(["t", "true"])
    manifest = REPORTS_DIR / "phase3_data_manifest.json"
    ref["manifest"] = json.loads(manifest.read_text()) if manifest.exists() else None
    return ref


@dataclass
class Dataset:
    tables: dict
    reference: dict
    fingerprint_before: dict = field(default_factory=dict)


def load_dataset() -> Dataset:
    fp = fingerprint()                       # taken BEFORE reading, compared again at the end of a run
    return Dataset(tables=load_cleaned(), reference=load_reference(), fingerprint_before=fp)


def profile_tables(tables: dict) -> pd.DataFrame:
    """Rows, columns, memory, nulls, date range and data-origin status of every table."""
    rows = []
    for name, df in tables.items():
        date_cols = [c for c in df.columns if str(df[c].dtype).startswith("datetime")]
        rng = "; ".join(f"{c}: {df[c].min():%Y-%m-%d} to {df[c].max():%Y-%m-%d}" for c in date_cols) if date_cols else ""
        rows.append(dict(table=name, rows=len(df), columns=df.shape[1], null_cells=int(df.isna().sum().sum()), date_range=rng,
                         data_origin=",".join(sorted(df["data_origin"].unique())) if "data_origin" in df else "",
                         dtypes=", ".join(f"{c}:{df[c].dtype}" for c in df.columns[:6]) + (" ..." if df.shape[1] > 6 else "")))
    return pd.DataFrame(rows)


def relationship_report(tables: dict) -> pd.DataFrame:
    """Orphan count for every foreign-key relationship (child values with no parent row; NULL children are allowed and not counted)."""
    out = []
    for child, ccol, parent, pcol in RELATIONSHIPS:
        c = tables[child][ccol].dropna()
        out.append(dict(child=f"{child}.{ccol}", parent=f"{parent}.{pcol}", child_rows=len(c), orphans=int((~c.isin(tables[parent][pcol])).sum())))
    return pd.DataFrame(out)


def source_register(tables: dict) -> pd.DataFrame:
    return pd.DataFrame([dict(source=f"data/processed/cleaned/{t}.csv", rows=len(df), role="primary analytical source (full cleaned dataset)") for t, df in tables.items()])
