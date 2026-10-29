-- 05_qa_tables.sql: quality-assurance tables (reference values loaded from Phase 2/3 CSV files, and stored check results).

CREATE TABLE qa.stg_kpi_reference (
    kpi_key TEXT,
    kpi TEXT,
    value TEXT,
    unit TEXT,
    numerator TEXT,
    denominator TEXT,
    scope TEXT,
    data_origin TEXT
);

CREATE TABLE qa.stg_monthly_kpi_reference (
    journey_month TEXT,
    total_bookings TEXT,
    total_passengers TEXT,
    confirmed_bookings TEXT,
    mixed_bookings TEXT,
    cancelled_bookings TEXT,
    cancelled_passengers TEXT,
    confirmed_pax TEXT,
    rac_pax TEXT,
    gross_value TEXT,
    refund_total TEXT,
    refund_passenger TEXT,
    refund_system TEXT,
    retained_charges TEXT,
    net_value TEXT,
    wl_demand TEXT,
    wl_cleared TEXT,
    wl_uncleared TEXT,
    seat_supply TEXT,
    booked_seats TEXT,
    simulated_runs TEXT,
    class_runs TEXT,
    runs_with_delay TEXT,
    on_time_runs TEXT,
    delayed_runs TEXT,
    delay_sum_pos TEXT,
    passenger_cancellation_rate TEXT,
    booking_cancellation_rate TEXT,
    avg_fare_per_passenger TEXT,
    avg_fare_per_booking TEXT,
    wl_clearance_rate TEXT,
    occupancy TEXT,
    confirmed_occupancy TEXT,
    rac_occupancy TEXT,
    waitlist_pressure TEXT,
    bookings_per_run TEXT,
    passengers_per_run TEXT,
    otp TEXT,
    avg_delay TEXT,
    bookings_growth TEXT,
    bookings_per_run_growth TEXT,
    data_origin TEXT
);

CREATE TABLE qa.stg_phase2_row_movement (
    table_name TEXT, raw_rows TEXT, clean_rows TEXT, duplicates TEXT, orphans TEXT, family_rejected TEXT, other TEXT
);

CREATE TABLE qa.kpi_reference (
    kpi_key      TEXT PRIMARY KEY,
    kpi          TEXT NOT NULL,
    value        NUMERIC NOT NULL,
    unit         TEXT NOT NULL,
    numerator    NUMERIC,
    denominator  NUMERIC,
    scope        TEXT NOT NULL,
    data_origin  TEXT NOT NULL
);
COMMENT ON TABLE qa.kpi_reference IS 'Copy of reports/kpi_reference_values.csv (Phase 3): the values SQL must reproduce. SYNTHETIC, sampled simulation.';

CREATE TABLE qa.phase2_row_movement (
    table_name      TEXT PRIMARY KEY,
    raw_rows        INTEGER NOT NULL,
    clean_rows      INTEGER NOT NULL,
    duplicates      INTEGER NOT NULL,
    orphans         INTEGER NOT NULL,
    family_rejected INTEGER NOT NULL,
    other           INTEGER NOT NULL
);
COMMENT ON TABLE qa.phase2_row_movement IS 'Copy of reports/data_quality/row_movement.csv (Phase 2): expected cleaned row counts per table.';

CREATE TABLE qa.check_results (
    check_id     TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    description  TEXT NOT NULL,
    violations   BIGINT NOT NULL,
    passed       BOOLEAN NOT NULL,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE qa.check_results IS 'Stored result of the data-quality checks (qa.v_check_results) from the last validation run.';
