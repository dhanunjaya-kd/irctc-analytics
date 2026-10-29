-- 05_star_schema_views.sql: star-schema VIEWS (dimensions and facts) over the core tables, for BI tools (Power BI in Phase 6, Tableau in Phase 7).
-- Views, not copies: no data is duplicated. SYNTHETIC data, sampled simulation (768 of 19,708 scheduled runs). No forecasts.
-- Grain of each fact is stated in its comment. Dimension keys are the natural integer / date keys of the core tables.

CREATE VIEW analytics.dim_date AS
SELECT calendar_date AS date_key, year, quarter, month_number, month_name, to_char(calendar_date, 'YYYY-MM') AS year_month, week_of_year,
       day_of_week_number, day_name, is_weekend, season, fiscal_year, is_holiday, holiday_name, is_peak_travel_period, peak_period_name
FROM core.calendar;

CREATE VIEW analytics.dim_station AS
SELECT station_id AS station_key, station_code, station_name, city, state, region FROM core.stations;

CREATE VIEW analytics.dim_route AS
SELECT r.route_id AS route_key, r.route_name, r.distance_km, o.station_code AS origin_code, o.city AS origin_city, d.station_code AS destination_code, d.city AS destination_city
FROM core.routes r
JOIN core.stations o ON o.station_id = r.origin_station_id
JOIN core.stations d ON d.station_id = r.destination_station_id;

CREATE VIEW analytics.dim_train AS
SELECT train_id AS train_key, train_number, train_name, train_type, run_days, route_id AS route_key FROM core.trains;

CREATE VIEW analytics.dim_travel_class AS
SELECT * FROM (VALUES ('1A', 'First AC', 24, false), ('2A', 'Second AC', 46, true), ('3A', 'Third AC', 64, true),
                      ('SL', 'Sleeper', 72, true), ('CC', 'Chair Car', 78, false), ('2S', 'Second Sitting', 108, false)) AS v(class_key, class_name, seats_per_coach, rac_modelled);

CREATE VIEW analytics.fact_passenger AS
SELECT bp.passenger_id, b.booking_id, b.journey_date AS date_key, b.train_id AS train_key, b.route_id AS route_key, b.travel_class AS class_key,
       bp.age_band, bp.initial_status, bp.final_status, bp.fare_amount,
       (bp.final_status = 'Cancelled')::int AS is_cancelled,
       (bp.initial_status = 'Waitlisted')::int AS is_initial_waitlist,
       (bp.initial_status = 'Waitlisted' AND bp.final_status IN ('Confirmed', 'RAC'))::int AS is_waitlist_cleared,
       (bp.final_status = 'Waitlisted')::int AS is_uncleared_waitlist,
       CASE bp.final_status WHEN 'Confirmed' THEN 1 WHEN 'RAC' THEN analytics.param('rac_seat_weight') ELSE 0 END AS seat_equivalent
FROM core.booking_passengers bp JOIN core.bookings b ON b.booking_id = bp.booking_id;
COMMENT ON VIEW analytics.fact_passenger IS 'Fact, grain = one passenger on a booking. SYNTHETIC, sampled simulation.';

CREATE VIEW analytics.fact_booking AS
SELECT booking_id, journey_date AS date_key, train_id AS train_key, route_id AS route_key, travel_class AS class_key, booking_status, num_passengers, total_fare, (journey_date - booking_ts::date) AS lead_days
FROM core.bookings;
COMMENT ON VIEW analytics.fact_booking IS 'Fact, grain = one booking (booking_status is the roll-up of passenger final statuses). SYNTHETIC, sampled simulation.';

CREATE VIEW analytics.fact_class_run AS
SELECT capacity_id, journey_date AS date_key, train_id AS train_key, travel_class AS class_key, total_seats, rac_berths, wl_limit, bookings, passengers,
       confirmed_pax, rac_pax, wl_final_pax, cancelled_pax, initial_wl_pax, booked_seats
FROM analytics.v_class_run;
COMMENT ON VIEW analytics.fact_class_run IS 'Fact, grain = one SIMULATED train-class run. Capacity is simulated. Occupancy = SUM(booked_seats) / SUM(total_seats) (ratio of sums).';

CREATE VIEW analytics.fact_train_run AS
SELECT o.operation_id, o.run_date AS date_key, o.train_id AS train_key, t.route_id AS route_key, o.departure_delay_min, o.arrival_delay_min,
       CASE WHEN o.arrival_delay_min IS NULL THEN NULL WHEN o.arrival_delay_min <= analytics.param('on_time_threshold_min') THEN 1 ELSE 0 END AS on_time
FROM core.train_operations o JOIN core.trains t ON t.train_id = o.train_id;
COMMENT ON VIEW analytics.fact_train_run IS 'Fact, grain = one SIMULATED train run. Delays are simulated; NULL arrival delay = missing, never imputed.';

CREATE VIEW analytics.fact_cancellation_event AS
SELECT c.cancellation_id, c.booking_id, b.journey_date AS date_key, b.train_id AS train_key, b.route_id AS route_key, b.travel_class AS class_key,
       c.cancellation_type, c.status_at_cancellation, c.cancelled_passengers, c.original_fare_amount, c.cancellation_charge, c.refund_amount
FROM core.cancellations c JOIN core.bookings b ON b.booking_id = c.booking_id;
COMMENT ON VIEW analytics.fact_cancellation_event IS 'Fact, grain = one refund event (Passenger cancellation or System auto-refund). SYNTHETIC, sampled simulation.';
