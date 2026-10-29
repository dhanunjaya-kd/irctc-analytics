-- 04_staging_tables.sql: staging tables. Every column is TEXT so the cleaned CSV files load exactly as delivered; typing and
-- constraint enforcement happen when rows move from stg to core (sql/transformations/02_load_core.sql).
-- Generated from the headers of data/processed/cleaned/*.csv and the reference CSVs; kept as plain SQL so the build needs only psql.

CREATE TABLE stg.stations (
    station_id TEXT,
    station_code TEXT,
    station_name TEXT,
    city TEXT,
    state TEXT,
    region TEXT,
    data_origin TEXT
);

CREATE TABLE stg.routes (
    route_id TEXT,
    origin_station_id TEXT,
    destination_station_id TEXT,
    route_name TEXT,
    distance_km TEXT,
    data_origin TEXT
);

CREATE TABLE stg.trains (
    train_id TEXT,
    train_number TEXT,
    train_name TEXT,
    train_type TEXT,
    route_id TEXT,
    run_days TEXT,
    data_origin TEXT
);

CREATE TABLE stg.train_stops (
    train_id TEXT,
    stop_sequence TEXT,
    station_id TEXT,
    arrival_time TEXT,
    departure_time TEXT,
    day_offset TEXT,
    distance_from_origin_km TEXT,
    data_origin TEXT
);

CREATE TABLE stg.calendar (
    calendar_date TEXT,
    year TEXT,
    quarter TEXT,
    month_number TEXT,
    month_name TEXT,
    week_of_year TEXT,
    day_of_month TEXT,
    day_of_week_number TEXT,
    day_name TEXT,
    is_weekend TEXT,
    season TEXT,
    fiscal_year TEXT,
    is_holiday TEXT,
    holiday_name TEXT,
    is_peak_travel_period TEXT,
    peak_period_name TEXT,
    data_origin TEXT
);

CREATE TABLE stg.seat_capacity (
    capacity_id TEXT,
    train_id TEXT,
    journey_date TEXT,
    travel_class TEXT,
    coaches_attached TEXT,
    seats_per_coach TEXT,
    total_seats TEXT,
    rac_berths TEXT,
    wl_limit TEXT,
    data_origin TEXT
);

CREATE TABLE stg.train_operations (
    operation_id TEXT,
    train_id TEXT,
    run_date TEXT,
    departure_delay_min TEXT,
    arrival_delay_min TEXT,
    data_origin TEXT
);

CREATE TABLE stg.bookings (
    booking_id TEXT,
    booking_reference TEXT,
    train_id TEXT,
    journey_date TEXT,
    route_id TEXT,
    boarding_station_id TEXT,
    destination_station_id TEXT,
    travel_class TEXT,
    booking_ts TEXT,
    num_passengers TEXT,
    booking_status TEXT,
    total_fare TEXT,
    data_origin TEXT
);

CREATE TABLE stg.booking_passengers (
    passenger_id TEXT,
    booking_id TEXT,
    passenger_seq TEXT,
    age_band TEXT,
    fare_amount TEXT,
    initial_status TEXT,
    final_status TEXT,
    cancellation_id TEXT,
    data_origin TEXT
);

CREATE TABLE stg.cancellations (
    cancellation_id TEXT,
    booking_id TEXT,
    cancellation_ts TEXT,
    cancellation_type TEXT,
    status_at_cancellation TEXT,
    cancelled_passengers TEXT,
    original_fare_amount TEXT,
    cancellation_charge TEXT,
    refund_amount TEXT,
    data_origin TEXT
);
