"""Central configuration for the synthetic data pipeline.

Every number here is a PROJECT ASSUMPTION for a synthetic dataset. None of it describes how IRCTC or
Indian Railways actually operates, prices, refunds or schedules trains. See docs/assumptions.md and
docs/data_sources.md.
"""
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "synthetic"
CLEAN_DIR = ROOT / "data" / "processed" / "cleaned"
INTERIM_DIR = ROOT / "data" / "interim" / "synthetic_truth"   # pre-corruption source data (git-ignored)
SAMPLE_DIR = ROOT / "data" / "sample"
DQ_DIR = ROOT / "reports" / "data_quality"
REPORTS_DIR = ROOT / "reports"

# ---------------------------------------------------------------- reproducibility
SEED = 42

# ---------------------------------------------------------------- date window (approved decision D-03)
JOURNEY_START = date(2024, 9, 1)
JOURNEY_END = date(2026, 8, 31)
CALENDAR_START = date(2024, 5, 1)      # journey start minus the 120-day booking window, rounded to month start
CALENDAR_END = date(2026, 12, 31)      # leaves room for forecast horizon features
AS_OF_DATE = JOURNEY_END

# ---------------------------------------------------------------- booking / status rules (parameters, A-05 to A-11)
MAX_ADVANCE_DAYS = 120
MAX_PASSENGERS = 6
CHART_PREP_HOURS = 4                   # bookings and cancellations close this long before departure
RAC_SEAT_WEIGHT = 0.5                  # configurable simulation assumption, NOT an official railway rule
ON_TIME_THRESHOLD_MIN = 15
DELAY_SANITY_MIN, DELAY_SANITY_MAX = -60, 1440

# ---------------------------------------------------------------- network structure
N_TARGET_TRAIN_PAIRS = 26              # 26 pairs = 52 trains (>= 50 required)
MIN_ROUTE_KM, MAX_ROUTE_KM = 450, 2600
RAIL_CIRCUITY = 1.25                   # great-circle distance x this = illustrative rail distance
RUNS_PER_MONTH = 32                    # SIMULATED train runs per calendar month, drawn across trains (decision D-01)

# ---------------------------------------------------------------- capacity (real seats per coach, modest coach counts)
CLASS_SEATS = {"1A": 24, "2A": 46, "3A": 64, "SL": 72, "CC": 78, "2S": 108}
COACH_RANGE = {"1A": (1, 1), "2A": (1, 2), "3A": (2, 3), "SL": (2, 4), "CC": (2, 3), "2S": (2, 3)}
RAC_CLASSES = {"SL", "3A", "2A"}       # RAC modelled only for berth classes (simulation assumption)
RAC_BERTH_SHARE = 0.11                 # share of seats reserved as RAC berths; each holds 2 RAC passengers
WL_LIMIT_SHARE = 0.30                  # max waitlisted passengers as a share of total seats

# ---------------------------------------------------------------- demand model
DEMAND_MEDIAN = 0.80                   # requested passengers / capacity, before multipliers
DEMAND_SIGMA = 0.34                    # run-to-run lognormal noise
CLASS_DEMAND = {"SL": 1.05, "3A": 1.00, "2A": 0.85, "1A": 0.55, "CC": 0.95, "2S": 0.90}
WEEKDAY_DEMAND = [1.00, 0.90, 0.90, 1.00, 1.15, 1.05, 1.15]     # Mon..Sun (by journey date)
SEASON_DEMAND = {"Winter": 1.00, "Summer": 1.15, "Monsoon": 0.92, "Post-Monsoon": 1.00}
PEAK_PERIOD_MULT = 1.35
HOLIDAY_MULT = 1.10
MONTHLY_TREND = 0.010                  # +1.0% demand per month since the window start
PAX_VALUES = [1, 2, 3, 4, 5, 6]
PAX_PROBS = [0.46, 0.28, 0.11, 0.10, 0.02, 0.03]
LEAD_BUCKETS = [(0, 3), (4, 14), (15, 30), (31, 60), (61, 120)]
LEAD_PROBS = [0.14, 0.26, 0.24, 0.24, 0.12]
AGE_BANDS = ["Child", "Adult", "Senior"]
AGE_PROBS = [0.10, 0.75, 0.15]

# ---------------------------------------------------------------- cancellation model
CANCEL_BASE = 0.08                     # cancel probability at lead time 0 ...
CANCEL_LEAD_SLOPE = 0.16               # ... rising linearly to this much more at 90+ days lead
CANCEL_CLASS_MULT = {"SL": 1.15, "2S": 1.15, "CC": 1.00, "3A": 1.00, "2A": 0.85, "1A": 0.70}
CANCEL_WL_MULT = 1.6
CANCEL_RAC_MULT = 1.2
PARTIAL_CANCEL_PROB = 0.25             # for bookings with 2+ passengers

# ---------------------------------------------------------------- illustrative fare and refund rules (A-10, NOT real tariffs)
FARE_RATE_PER_KM = {"1A": 3.9, "2A": 2.3, "3A": 1.6, "SL": 0.6, "CC": 1.45, "2S": 0.5}
FARE_RESERVATION = {"1A": 60, "2A": 50, "3A": 40, "SL": 20, "CC": 40, "2S": 15}
FARE_TYPE_MULT = {"Premium": 1.25, "Superfast": 1.05, "Express": 1.00}
FARE_AGE_FACTOR = {"Child": 0.5, "Adult": 1.0, "Senior": 0.6}
CANCEL_FLAT_FEE = {"1A": 240, "2A": 200, "3A": 180, "SL": 120, "CC": 180, "2S": 60}   # per passenger
WL_CLERKAGE = 30                       # per passenger, waitlist cancellations and system auto-refunds
CANCEL_PCT_12_48H = 0.25               # share of fare retained when cancelled 12-48h before departure (min flat fee)
CANCEL_PCT_4_12H = 0.50                # share of fare retained when cancelled 4-12h before departure (min flat fee)

# ---------------------------------------------------------------- calendar (modelled, NOT an official holiday list)
FIXED_HOLIDAYS = {(1, 26): "Republic Day (fixed date)", (8, 15): "Independence Day (fixed date)",
                  (10, 2): "Gandhi Jayanti (fixed date)", (12, 25): "Christmas Day (fixed date)"}
PEAK_WINDOWS = [
    ("Summer vacation window (modelled)", date(2024, 5, 1), date(2024, 6, 15)),
    ("Summer vacation window (modelled)", date(2025, 5, 1), date(2025, 6, 15)),
    ("Summer vacation window (modelled)", date(2026, 5, 1), date(2026, 6, 15)),
    ("Autumn festival window (modelled)", date(2024, 10, 28), date(2024, 11, 6)),
    ("Autumn festival window (modelled)", date(2025, 10, 16), date(2025, 10, 26)),
    ("Autumn festival window (modelled)", date(2026, 11, 1), date(2026, 11, 10)),
    ("Spring festival window (modelled)", date(2025, 3, 11), date(2025, 3, 17)),
    ("Spring festival window (modelled)", date(2026, 3, 1), date(2026, 3, 7)),
    ("Year-end holiday window (modelled)", date(2024, 12, 22), date(2025, 1, 2)),
    ("Year-end holiday window (modelled)", date(2025, 12, 22), date(2026, 1, 2)),
]
SEASON_BY_MONTH = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Summer", 4: "Summer", 5: "Summer",
                   6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon", 10: "Post-Monsoon", 11: "Post-Monsoon"}

# ---------------------------------------------------------------- operations (delay model, simulated)
LATE_BASE_PROB = 0.17
LATE_MEDIAN_MIN = 40
LATE_SIGMA = 0.85
TYPE_DELAY_MULT = {"Premium": 0.7, "Superfast": 0.9, "Express": 1.1}
SEASON_DELAY_MULT = {"Winter": 1.4, "Summer": 1.0, "Monsoon": 1.3, "Post-Monsoon": 1.0}

# ---------------------------------------------------------------- data-quality injection rates (share of bookings unless noted)
DQ_RATES = {
    "dup_booking_rows": 0.0050,
    "dup_passenger_rows": 0.0025,
    "dup_cancellation_rows": 0.0050,        # share of cancellation events
    "missing_total_fare": 0.0040,
    "total_fare_currency_format": 0.0030,
    "total_fare_invalid": 0.0030,
    "negative_passenger_fare": 0.0020,
    "missing_route_id": 0.0030,
    "station_code_format": 0.0060,
    "station_code_unknown": 0.0020,
    "missing_booking_ts": 0.0010,
    "journey_date_format": 0.0030,
    "journey_date_impossible": 0.0010,
    "booking_after_journey": 0.0010,
    "booking_status_alias": 0.0060,
    "booking_status_invalid": 0.0020,
    "passenger_status_alias": 0.0040,
    "passenger_final_status_invalid": 0.0010,
    "passenger_initial_status_invalid": 0.0005,
    "num_passengers_invalid": 0.0030,
    "missing_age_band": 0.0050,
    "orphan_cancellation_rows": 0.0030,     # share of cancellation events (extra rows added)
    "orphan_passenger_rows": 0.0005,        # share of bookings (extra rows added)
    "cancellation_before_booking": 0.0010,  # share of cancellation events
    "refund_exceeds_fare": 0.0020,          # share of cancellation events
    "capacity_total_mismatch": 0.0200,      # share of capacity rows
    "capacity_seats_per_coach_invalid": 0.0120,
    "capacity_conflicting_duplicate": 0.0080,
    "missing_arrival_delay": 0.0200,        # share of operations rows
    "delay_out_of_range": 0.0100,
}
