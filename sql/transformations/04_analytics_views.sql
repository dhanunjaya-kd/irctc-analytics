-- 04_analytics_views.sql: KPI parameters and analytical views. KPI logic follows docs/KPI_definitions.md (approved) and is NOT adjusted to force reconciliation.
-- SYNTHETIC data from a SAMPLED simulation (768 of 19,708 scheduled runs): compare months with per-run and capacity-normalised measures.
-- No view here forecasts anything. Ratios return NULL (not 0) when the denominator is 0.

CREATE TABLE analytics.kpi_parameter (
    parameter_name   TEXT PRIMARY KEY,
    parameter_value  NUMERIC NOT NULL,
    description      TEXT NOT NULL
);
INSERT INTO analytics.kpi_parameter VALUES
 ('rac_seat_weight',       0.5, 'RAC passengers count as this many seats in occupancy. A configurable SIMULATION ASSUMPTION, not an official railway rule (assumption A-09).'),
 ('on_time_threshold_min', 15,  'A run is on time when arrival delay <= this many minutes. A project convention (assumption A-11).'),
 ('chart_prep_hours',      4,   'Bookings and cancellations close this many hours before departure (assumption A-05).'),
 ('max_advance_days',      120, 'Maximum booking lead time in days (assumption A-05).');

CREATE FUNCTION analytics.param(p_name TEXT) RETURNS NUMERIC
LANGUAGE sql STABLE AS $$ SELECT parameter_value FROM analytics.kpi_parameter WHERE parameter_name = p_name $$;

-- bookings with month, lead time and lead bucket (buckets as in the Excel workbook and Python reference)
CREATE VIEW analytics.v_booking AS
SELECT b.booking_id, b.booking_reference, b.train_id, t.train_number, t.train_type, b.route_id, r.route_name,
       b.journey_date, to_char(b.journey_date, 'YYYY-MM') AS journey_month, b.travel_class, b.booking_ts,
       (b.journey_date - b.booking_ts::date) AS lead_days,
       CASE WHEN (b.journey_date - b.booking_ts::date) <= 3  THEN '0-3 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 14 THEN '4-14 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 30 THEN '15-30 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 60 THEN '31-60 days'
            ELSE '61-120 days' END AS lead_bucket,
       b.num_passengers, b.booking_status, b.total_fare
FROM core.bookings b
JOIN core.trains t ON t.train_id = b.train_id
JOIN core.routes r ON r.route_id = b.route_id;

-- passengers with their booking's attributes (aggregate to the join grain BEFORE joining to capacity: see v_class_run)
CREATE VIEW analytics.v_passenger AS
SELECT bp.passenger_id, bp.booking_id, bp.passenger_seq, bp.age_band, bp.fare_amount, bp.initial_status, bp.final_status, bp.cancellation_id,
       vb.train_id, vb.train_type, vb.route_id, vb.route_name, vb.journey_date, vb.journey_month, vb.travel_class, vb.lead_bucket
FROM core.booking_passengers bp
JOIN analytics.v_booking vb ON vb.booking_id = bp.booking_id;

-- one row per simulated train-class run: capacity, passengers by final status, occupancy, waitlist pressure
-- occupancy = (Confirmed + RAC weight x RAC) / seats on final statuses; waitlisted passengers hold no seat (waitlist_pressure, not occupancy)
CREATE VIEW analytics.v_class_run AS
WITH pax AS (
    SELECT b.train_id, b.journey_date, b.travel_class,
           count(DISTINCT b.booking_id) AS bookings,
           count(*) AS passengers,
           count(*) FILTER (WHERE bp.final_status = 'Confirmed')  AS confirmed_pax,
           count(*) FILTER (WHERE bp.final_status = 'RAC')        AS rac_pax,
           count(*) FILTER (WHERE bp.final_status = 'Waitlisted') AS wl_final_pax,
           count(*) FILTER (WHERE bp.final_status = 'Cancelled')  AS cancelled_pax,
           count(*) FILTER (WHERE bp.initial_status = 'Waitlisted') AS initial_wl_pax
    FROM core.booking_passengers bp
    JOIN core.bookings b ON b.booking_id = bp.booking_id
    GROUP BY b.train_id, b.journey_date, b.travel_class)
SELECT sc.capacity_id, sc.train_id, sc.journey_date, to_char(sc.journey_date, 'YYYY-MM') AS journey_month, sc.travel_class,
       sc.coaches_attached, sc.total_seats, sc.rac_berths, sc.wl_limit,
       coalesce(p.bookings, 0) AS bookings, coalesce(p.passengers, 0) AS passengers,
       coalesce(p.confirmed_pax, 0) AS confirmed_pax, coalesce(p.rac_pax, 0) AS rac_pax, coalesce(p.wl_final_pax, 0) AS wl_final_pax,
       coalesce(p.cancelled_pax, 0) AS cancelled_pax, coalesce(p.initial_wl_pax, 0) AS initial_wl_pax,
       coalesce(p.confirmed_pax, 0) + analytics.param('rac_seat_weight') * coalesce(p.rac_pax, 0) AS booked_seats,
       (coalesce(p.confirmed_pax, 0) + analytics.param('rac_seat_weight') * coalesce(p.rac_pax, 0)) / sc.total_seats AS occupancy,
       coalesce(p.confirmed_pax, 0)::numeric / sc.total_seats AS confirmed_occupancy,
       coalesce(p.wl_final_pax, 0)::numeric / sc.total_seats AS waitlist_pressure
FROM core.seat_capacity sc
LEFT JOIN pax p ON p.train_id = sc.train_id AND p.journey_date = sc.journey_date AND p.travel_class = sc.travel_class;

-- one row per simulated train run; on_time is NULL where the arrival delay is missing (never imputed)
CREATE VIEW analytics.v_run AS
SELECT o.operation_id, o.train_id, t.train_number, t.train_type, t.route_id, r.route_name, o.run_date,
       to_char(o.run_date, 'YYYY-MM') AS journey_month, c.season, o.departure_delay_min, o.arrival_delay_min,
       CASE WHEN o.arrival_delay_min IS NULL THEN NULL
            WHEN o.arrival_delay_min <= analytics.param('on_time_threshold_min') THEN 1 ELSE 0 END AS on_time
FROM core.train_operations o
JOIN core.trains t   ON t.train_id = o.train_id
JOIN core.routes r   ON r.route_id = t.route_id
JOIN core.calendar c ON c.calendar_date = o.run_date;

-- KPIs per journey month (cohort basis: refunds follow the booking's journey month)
CREATE VIEW analytics.v_monthly_kpis AS
WITH bk AS (
    SELECT journey_month, count(*) AS total_bookings,
           count(*) FILTER (WHERE booking_status = 'Confirmed') AS confirmed_bookings,
           count(*) FILTER (WHERE booking_status = 'Mixed')     AS mixed_bookings,
           count(*) FILTER (WHERE booking_status = 'Cancelled') AS cancelled_bookings,
           sum(total_fare) AS gross_value
    FROM analytics.v_booking GROUP BY journey_month),
ps AS (
    SELECT journey_month, count(*) AS total_passengers,
           count(*) FILTER (WHERE final_status = 'Cancelled') AS cancelled_passengers,
           count(*) FILTER (WHERE final_status = 'Confirmed') AS confirmed_pax,
           count(*) FILTER (WHERE final_status = 'RAC')       AS rac_pax,
           count(*) FILTER (WHERE initial_status = 'Waitlisted') AS wl_demand,
           count(*) FILTER (WHERE initial_status = 'Waitlisted' AND final_status IN ('Confirmed','RAC')) AS wl_cleared,
           count(*) FILTER (WHERE final_status = 'Waitlisted') AS wl_uncleared
    FROM analytics.v_passenger GROUP BY journey_month),
ev AS (
    SELECT vb.journey_month,
           coalesce(sum(c.refund_amount) FILTER (WHERE c.cancellation_type = 'Passenger'), 0) AS refund_passenger,
           coalesce(sum(c.refund_amount) FILTER (WHERE c.cancellation_type = 'System'), 0)    AS refund_system,
           coalesce(sum(c.cancellation_charge), 0) AS retained_charges
    FROM core.cancellations c JOIN analytics.v_booking vb ON vb.booking_id = c.booking_id GROUP BY vb.journey_month),
cp AS (SELECT journey_month, count(*) AS class_runs, sum(total_seats) AS seat_supply FROM analytics.v_class_run GROUP BY journey_month),
op AS (
    SELECT journey_month, count(*) AS simulated_runs, count(arrival_delay_min) AS runs_with_delay,
           count(*) FILTER (WHERE on_time = 1) AS on_time_runs, count(*) FILTER (WHERE on_time = 0) AS delayed_runs,
           coalesce(sum(greatest(arrival_delay_min, 0)), 0) AS delay_sum_pos
    FROM analytics.v_run GROUP BY journey_month),
m AS (
    SELECT bk.journey_month, bk.total_bookings, ps.total_passengers, bk.confirmed_bookings, bk.mixed_bookings, bk.cancelled_bookings,
           ps.cancelled_passengers, ps.confirmed_pax, ps.rac_pax, bk.gross_value,
           coalesce(ev.refund_passenger, 0) + coalesce(ev.refund_system, 0) AS refund_total, coalesce(ev.refund_passenger, 0) AS refund_passenger,
           coalesce(ev.refund_system, 0) AS refund_system, coalesce(ev.retained_charges, 0) AS retained_charges,
           bk.gross_value - (coalesce(ev.refund_passenger, 0) + coalesce(ev.refund_system, 0)) AS net_value,
           ps.wl_demand, ps.wl_cleared, ps.wl_uncleared, cp.seat_supply,
           ps.confirmed_pax + analytics.param('rac_seat_weight') * ps.rac_pax AS booked_seats,
           op.simulated_runs, cp.class_runs, op.runs_with_delay, op.on_time_runs, op.delayed_runs, op.delay_sum_pos
    FROM bk JOIN ps USING (journey_month) LEFT JOIN ev USING (journey_month) JOIN cp USING (journey_month) JOIN op USING (journey_month))
SELECT m.*,
       cancelled_passengers::numeric / NULLIF(total_passengers, 0) AS passenger_cancellation_rate,
       cancelled_bookings::numeric / NULLIF(total_bookings, 0) AS booking_cancellation_rate,
       gross_value / NULLIF(total_passengers, 0) AS avg_fare_per_passenger,
       gross_value / NULLIF(total_bookings, 0) AS avg_fare_per_booking,
       wl_cleared::numeric / NULLIF(wl_demand, 0) AS wl_clearance_rate,
       booked_seats / NULLIF(seat_supply, 0) AS occupancy,
       confirmed_pax::numeric / NULLIF(seat_supply, 0) AS confirmed_occupancy,
       analytics.param('rac_seat_weight') * rac_pax / NULLIF(seat_supply, 0) AS rac_occupancy,
       wl_uncleared::numeric / NULLIF(seat_supply, 0) AS waitlist_pressure,
       total_bookings::numeric / NULLIF(simulated_runs, 0) AS bookings_per_run,
       total_passengers::numeric / NULLIF(simulated_runs, 0) AS passengers_per_run,
       on_time_runs::numeric / NULLIF(runs_with_delay, 0) AS otp,
       delay_sum_pos::numeric / NULLIF(runs_with_delay, 0) AS avg_delay,
       total_bookings::numeric / NULLIF(lag(total_bookings) OVER (ORDER BY journey_month), 0) - 1 AS bookings_growth,
       (total_bookings::numeric / NULLIF(simulated_runs, 0))
         / NULLIF(lag(total_bookings::numeric / NULLIF(simulated_runs, 0)) OVER (ORDER BY journey_month), 0) - 1 AS bookings_per_run_growth
FROM m;

-- overall KPIs computed DIRECTLY from the base tables (independent of the monthly view)
CREATE VIEW analytics.v_kpi_overall AS
WITH bk AS (
    SELECT count(*) AS total_bookings, count(*) FILTER (WHERE booking_status = 'Confirmed') AS confirmed_bookings,
           count(*) FILTER (WHERE booking_status = 'Mixed') AS mixed_bookings, count(*) FILTER (WHERE booking_status = 'Cancelled') AS cancelled_bookings,
           sum(total_fare) AS gross_value
    FROM core.bookings),
ps AS (
    SELECT count(*) AS total_passengers, count(*) FILTER (WHERE final_status = 'Cancelled') AS cancelled_passengers,
           count(*) FILTER (WHERE final_status = 'Confirmed') AS confirmed_pax, count(*) FILTER (WHERE final_status = 'RAC') AS rac_pax,
           count(*) FILTER (WHERE initial_status = 'Waitlisted') AS wl_demand,
           count(*) FILTER (WHERE initial_status = 'Waitlisted' AND final_status IN ('Confirmed','RAC')) AS wl_cleared,
           count(*) FILTER (WHERE final_status = 'Waitlisted') AS wl_uncleared
    FROM core.booking_passengers),
ev AS (
    SELECT coalesce(sum(refund_amount), 0) AS refund_total,
           coalesce(sum(refund_amount) FILTER (WHERE cancellation_type = 'Passenger'), 0) AS refund_passenger,
           coalesce(sum(refund_amount) FILTER (WHERE cancellation_type = 'System'), 0) AS refund_system,
           coalesce(sum(cancellation_charge), 0) AS retained_charges
    FROM core.cancellations),
cp AS (SELECT count(*) AS class_runs, sum(total_seats) AS seat_supply FROM core.seat_capacity),
op AS (
    SELECT count(*) AS simulated_runs, count(arrival_delay_min) AS runs_with_delay,
           count(*) FILTER (WHERE arrival_delay_min <= analytics.param('on_time_threshold_min')) AS on_time_runs,
           count(*) FILTER (WHERE arrival_delay_min >  analytics.param('on_time_threshold_min')) AS delayed_runs,
           coalesce(sum(greatest(arrival_delay_min, 0)), 0) AS delay_sum_pos
    FROM core.train_operations),
m AS (
    SELECT bk.total_bookings, ps.total_passengers, bk.confirmed_bookings, bk.mixed_bookings, bk.cancelled_bookings, ps.cancelled_passengers, ps.confirmed_pax, ps.rac_pax,
           bk.gross_value, ev.refund_total, ev.refund_passenger, ev.refund_system, ev.retained_charges, bk.gross_value - ev.refund_total AS net_value,
           ps.wl_demand, ps.wl_cleared, ps.wl_uncleared, cp.seat_supply, ps.confirmed_pax + analytics.param('rac_seat_weight') * ps.rac_pax AS booked_seats,
           op.simulated_runs, cp.class_runs, op.runs_with_delay, op.on_time_runs, op.delayed_runs, op.delay_sum_pos
    FROM bk, ps, ev, cp, op)
SELECT m.*,
       cancelled_passengers::numeric / NULLIF(total_passengers, 0) AS passenger_cancellation_rate,
       cancelled_bookings::numeric / NULLIF(total_bookings, 0) AS booking_cancellation_rate,
       gross_value / NULLIF(total_passengers, 0) AS avg_fare_per_passenger,
       gross_value / NULLIF(total_bookings, 0) AS avg_fare_per_booking,
       wl_cleared::numeric / NULLIF(wl_demand, 0) AS wl_clearance_rate,
       booked_seats / NULLIF(seat_supply, 0) AS occupancy,
       confirmed_pax::numeric / NULLIF(seat_supply, 0) AS confirmed_occupancy,
       analytics.param('rac_seat_weight') * rac_pax / NULLIF(seat_supply, 0) AS rac_occupancy,
       wl_uncleared::numeric / NULLIF(seat_supply, 0) AS waitlist_pressure,
       total_bookings::numeric / NULLIF(simulated_runs, 0) AS bookings_per_run,
       total_passengers::numeric / NULLIF(simulated_runs, 0) AS passengers_per_run,
       on_time_runs::numeric / NULLIF(runs_with_delay, 0) AS otp,
       delay_sum_pos::numeric / NULLIF(runs_with_delay, 0) AS avg_delay
FROM m;

CREATE VIEW analytics.v_kpi_overall_long AS
SELECT k.kpi_key, k.value
FROM analytics.v_kpi_overall o
CROSS JOIN LATERAL (VALUES
    ('total_bookings', o.total_bookings::numeric),
    ('total_passengers', o.total_passengers::numeric),
    ('confirmed_bookings', o.confirmed_bookings::numeric),
    ('mixed_bookings', o.mixed_bookings::numeric),
    ('cancelled_bookings', o.cancelled_bookings::numeric),
    ('cancelled_passengers', o.cancelled_passengers::numeric),
    ('confirmed_pax', o.confirmed_pax::numeric),
    ('rac_pax', o.rac_pax::numeric),
    ('gross_value', o.gross_value::numeric),
    ('refund_total', o.refund_total::numeric),
    ('refund_passenger', o.refund_passenger::numeric),
    ('refund_system', o.refund_system::numeric),
    ('retained_charges', o.retained_charges::numeric),
    ('net_value', o.net_value::numeric),
    ('wl_demand', o.wl_demand::numeric),
    ('wl_cleared', o.wl_cleared::numeric),
    ('wl_uncleared', o.wl_uncleared::numeric),
    ('seat_supply', o.seat_supply::numeric),
    ('booked_seats', o.booked_seats::numeric),
    ('simulated_runs', o.simulated_runs::numeric),
    ('class_runs', o.class_runs::numeric),
    ('runs_with_delay', o.runs_with_delay::numeric),
    ('on_time_runs', o.on_time_runs::numeric),
    ('delayed_runs', o.delayed_runs::numeric),
    ('delay_sum_pos', o.delay_sum_pos::numeric),
    ('passenger_cancellation_rate', o.passenger_cancellation_rate::numeric),
    ('booking_cancellation_rate', o.booking_cancellation_rate::numeric),
    ('avg_fare_per_passenger', o.avg_fare_per_passenger::numeric),
    ('avg_fare_per_booking', o.avg_fare_per_booking::numeric),
    ('wl_clearance_rate', o.wl_clearance_rate::numeric),
    ('occupancy', o.occupancy::numeric),
    ('confirmed_occupancy', o.confirmed_occupancy::numeric),
    ('rac_occupancy', o.rac_occupancy::numeric),
    ('waitlist_pressure', o.waitlist_pressure::numeric),
    ('bookings_per_run', o.bookings_per_run::numeric),
    ('passengers_per_run', o.passengers_per_run::numeric),
    ('otp', o.otp::numeric),
    ('avg_delay', o.avg_delay::numeric)
) AS k(kpi_key, value);

CREATE VIEW analytics.v_monthly_kpis_long AS
SELECT m.journey_month, k.kpi_key, k.value
FROM analytics.v_monthly_kpis m
CROSS JOIN LATERAL (VALUES
    ('total_bookings', m.total_bookings::numeric),
    ('total_passengers', m.total_passengers::numeric),
    ('confirmed_bookings', m.confirmed_bookings::numeric),
    ('mixed_bookings', m.mixed_bookings::numeric),
    ('cancelled_bookings', m.cancelled_bookings::numeric),
    ('cancelled_passengers', m.cancelled_passengers::numeric),
    ('confirmed_pax', m.confirmed_pax::numeric),
    ('rac_pax', m.rac_pax::numeric),
    ('gross_value', m.gross_value::numeric),
    ('refund_total', m.refund_total::numeric),
    ('refund_passenger', m.refund_passenger::numeric),
    ('refund_system', m.refund_system::numeric),
    ('retained_charges', m.retained_charges::numeric),
    ('net_value', m.net_value::numeric),
    ('wl_demand', m.wl_demand::numeric),
    ('wl_cleared', m.wl_cleared::numeric),
    ('wl_uncleared', m.wl_uncleared::numeric),
    ('seat_supply', m.seat_supply::numeric),
    ('booked_seats', m.booked_seats::numeric),
    ('simulated_runs', m.simulated_runs::numeric),
    ('class_runs', m.class_runs::numeric),
    ('runs_with_delay', m.runs_with_delay::numeric),
    ('on_time_runs', m.on_time_runs::numeric),
    ('delayed_runs', m.delayed_runs::numeric),
    ('delay_sum_pos', m.delay_sum_pos::numeric),
    ('passenger_cancellation_rate', m.passenger_cancellation_rate::numeric),
    ('booking_cancellation_rate', m.booking_cancellation_rate::numeric),
    ('avg_fare_per_passenger', m.avg_fare_per_passenger::numeric),
    ('avg_fare_per_booking', m.avg_fare_per_booking::numeric),
    ('wl_clearance_rate', m.wl_clearance_rate::numeric),
    ('occupancy', m.occupancy::numeric),
    ('confirmed_occupancy', m.confirmed_occupancy::numeric),
    ('rac_occupancy', m.rac_occupancy::numeric),
    ('waitlist_pressure', m.waitlist_pressure::numeric),
    ('bookings_per_run', m.bookings_per_run::numeric),
    ('passengers_per_run', m.passengers_per_run::numeric),
    ('otp', m.otp::numeric),
    ('avg_delay', m.avg_delay::numeric),
    ('bookings_growth', m.bookings_growth::numeric),
    ('bookings_per_run_growth', m.bookings_per_run_growth::numeric)
) AS k(kpi_key, value);

COMMENT ON VIEW analytics.v_class_run     IS 'One row per SIMULATED train-class run (2,285 rows). Occupancy excludes waitlisted passengers. Synthetic, sampled simulation.';
COMMENT ON VIEW analytics.v_monthly_kpis  IS 'KPIs per journey month. Only 32 runs per month are simulated: use the per-run and normalised columns for comparisons. Synthetic; no forecasts.';
COMMENT ON VIEW analytics.v_kpi_overall   IS 'Overall KPIs for the full cleaned dataset (768 simulated runs). Not IRCTC network-wide metrics.';
