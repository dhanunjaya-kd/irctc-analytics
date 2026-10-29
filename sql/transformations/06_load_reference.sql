-- 06_load_reference.sql: load the reference values SQL must reproduce (Phase 2 and Phase 3 CSV files). Paths are relative to the project root.
\echo '>> loading reference values'
\copy qa.stg_kpi_reference         FROM 'reports/kpi_reference_values.csv'      WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy qa.stg_monthly_kpi_reference FROM 'data/processed/derived/monthly_kpis.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy qa.stg_phase2_row_movement   FROM 'reports/data_quality/row_movement.csv'  WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

INSERT INTO qa.kpi_reference
SELECT kpi_key, kpi, value::numeric, unit, NULLIF(numerator, '')::numeric, NULLIF(denominator, '')::numeric, scope, data_origin FROM qa.stg_kpi_reference;

INSERT INTO qa.phase2_row_movement
SELECT table_name, raw_rows::int, clean_rows::int, duplicates::int, orphans::int, family_rejected::int, other::int FROM qa.stg_phase2_row_movement;

CREATE TABLE qa.monthly_kpi_reference AS
SELECT journey_month,
       NULLIF(total_bookings, '')::numeric AS total_bookings,
       NULLIF(total_passengers, '')::numeric AS total_passengers,
       NULLIF(confirmed_bookings, '')::numeric AS confirmed_bookings,
       NULLIF(mixed_bookings, '')::numeric AS mixed_bookings,
       NULLIF(cancelled_bookings, '')::numeric AS cancelled_bookings,
       NULLIF(cancelled_passengers, '')::numeric AS cancelled_passengers,
       NULLIF(confirmed_pax, '')::numeric AS confirmed_pax,
       NULLIF(rac_pax, '')::numeric AS rac_pax,
       NULLIF(gross_value, '')::numeric AS gross_value,
       NULLIF(refund_total, '')::numeric AS refund_total,
       NULLIF(refund_passenger, '')::numeric AS refund_passenger,
       NULLIF(refund_system, '')::numeric AS refund_system,
       NULLIF(retained_charges, '')::numeric AS retained_charges,
       NULLIF(net_value, '')::numeric AS net_value,
       NULLIF(wl_demand, '')::numeric AS wl_demand,
       NULLIF(wl_cleared, '')::numeric AS wl_cleared,
       NULLIF(wl_uncleared, '')::numeric AS wl_uncleared,
       NULLIF(seat_supply, '')::numeric AS seat_supply,
       NULLIF(booked_seats, '')::numeric AS booked_seats,
       NULLIF(simulated_runs, '')::numeric AS simulated_runs,
       NULLIF(class_runs, '')::numeric AS class_runs,
       NULLIF(runs_with_delay, '')::numeric AS runs_with_delay,
       NULLIF(on_time_runs, '')::numeric AS on_time_runs,
       NULLIF(delayed_runs, '')::numeric AS delayed_runs,
       NULLIF(delay_sum_pos, '')::numeric AS delay_sum_pos,
       NULLIF(passenger_cancellation_rate, '')::numeric AS passenger_cancellation_rate,
       NULLIF(booking_cancellation_rate, '')::numeric AS booking_cancellation_rate,
       NULLIF(avg_fare_per_passenger, '')::numeric AS avg_fare_per_passenger,
       NULLIF(avg_fare_per_booking, '')::numeric AS avg_fare_per_booking,
       NULLIF(wl_clearance_rate, '')::numeric AS wl_clearance_rate,
       NULLIF(occupancy, '')::numeric AS occupancy,
       NULLIF(confirmed_occupancy, '')::numeric AS confirmed_occupancy,
       NULLIF(rac_occupancy, '')::numeric AS rac_occupancy,
       NULLIF(waitlist_pressure, '')::numeric AS waitlist_pressure,
       NULLIF(bookings_per_run, '')::numeric AS bookings_per_run,
       NULLIF(passengers_per_run, '')::numeric AS passengers_per_run,
       NULLIF(otp, '')::numeric AS otp,
       NULLIF(avg_delay, '')::numeric AS avg_delay,
       NULLIF(bookings_growth, '')::numeric AS bookings_growth,
       NULLIF(bookings_per_run_growth, '')::numeric AS bookings_per_run_growth,
       data_origin
FROM qa.stg_monthly_kpi_reference;
ALTER TABLE qa.monthly_kpi_reference ADD PRIMARY KEY (journey_month);
COMMENT ON TABLE qa.monthly_kpi_reference IS 'Copy of data/processed/derived/monthly_kpis.csv (Phase 3): monthly values SQL must reproduce. NULL growth in the first month is expected.';
