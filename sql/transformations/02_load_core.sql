-- 02_load_core.sql: typed load from stg to core in foreign-key dependency order, in ONE transaction.
-- Any constraint violation aborts the whole load (nothing partial is left in core).
BEGIN;
\echo '>> loading core tables (typed, constrained)'

INSERT INTO core.stations
SELECT station_id::integer, station_code, station_name, city, state, region, data_origin FROM stg.stations;

INSERT INTO core.routes
SELECT route_id::integer, origin_station_id::integer, destination_station_id::integer, route_name, distance_km::numeric(7,1), data_origin FROM stg.routes;

INSERT INTO core.trains
SELECT train_id::integer, train_number, train_name, train_type, route_id::integer, run_days, data_origin FROM stg.trains;

INSERT INTO core.train_stops
SELECT train_id::integer, stop_sequence::smallint, station_id::integer, arrival_time::time, departure_time::time,
       day_offset::smallint, distance_from_origin_km::numeric(7,1), data_origin FROM stg.train_stops;

INSERT INTO core.calendar
SELECT calendar_date::date, year::smallint, quarter::smallint, month_number::smallint, month_name, week_of_year::smallint, day_of_month::smallint,
       day_of_week_number::smallint, day_name, is_weekend::boolean, season, fiscal_year::smallint, is_holiday::boolean, holiday_name,
       is_peak_travel_period::boolean, peak_period_name, data_origin FROM stg.calendar;

INSERT INTO core.seat_capacity
SELECT capacity_id::bigint, train_id::integer, journey_date::date, travel_class, coaches_attached::smallint, seats_per_coach::smallint,
       total_seats::integer, rac_berths::smallint, wl_limit::integer, data_origin FROM stg.seat_capacity;

INSERT INTO core.train_operations
SELECT operation_id::bigint, train_id::integer, run_date::date, departure_delay_min::integer, arrival_delay_min::integer, data_origin FROM stg.train_operations;

INSERT INTO core.bookings
SELECT booking_id::bigint, booking_reference, train_id::integer, journey_date::date, route_id::integer, boarding_station_id::integer,
       destination_station_id::integer, travel_class, booking_ts::timestamp, num_passengers::smallint, booking_status, total_fare::numeric(12,2), data_origin
FROM stg.bookings;

INSERT INTO core.cancellations
SELECT cancellation_id::bigint, booking_id::bigint, cancellation_ts::timestamp, cancellation_type, status_at_cancellation, cancelled_passengers::smallint,
       original_fare_amount::numeric(12,2), cancellation_charge::numeric(10,2), refund_amount::numeric(12,2), data_origin FROM stg.cancellations;

INSERT INTO core.booking_passengers
SELECT passenger_id::bigint, booking_id::bigint, passenger_seq::smallint, age_band, fare_amount::numeric(10,2), initial_status, final_status,
       cancellation_id::bigint, data_origin FROM stg.booking_passengers;

COMMIT;
