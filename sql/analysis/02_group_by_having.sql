-- 02_group_by_having.sql: aggregation, FILTER, HAVING, ROLLUP / GROUPING SETS.
-- Cancellation Rate is PASSENGER-based (denominator: total passengers); see docs/KPI_definitions.md.

-- [G1] GROUP BY: passengers and passenger-based cancellation rate by travel class.
SELECT travel_class, count(*) AS passengers, count(*) FILTER (WHERE final_status = 'Cancelled') AS cancelled_passengers,
       round(count(*) FILTER (WHERE final_status = 'Cancelled')::numeric / count(*), 4) AS passenger_cancellation_rate
FROM analytics.v_passenger
GROUP BY travel_class
ORDER BY passenger_cancellation_rate DESC;

-- [G2] HAVING: routes with at least 8 simulated runs whose cancellation rate is above the overall rate. Run counts are shown because trains have only 9 to 20 runs.
SELECT p.route_name, count(DISTINCT p.train_id::text || p.journey_date::text) AS simulated_runs, count(*) AS passengers,
       round(count(*) FILTER (WHERE p.final_status = 'Cancelled')::numeric / count(*), 4) AS passenger_cancellation_rate
FROM analytics.v_passenger p
GROUP BY p.route_name
HAVING count(DISTINCT p.train_id::text || p.journey_date::text) >= 8
   AND count(*) FILTER (WHERE p.final_status = 'Cancelled')::numeric / count(*) > (SELECT count(*) FILTER (WHERE final_status = 'Cancelled')::numeric / count(*) FROM core.booking_passengers)
ORDER BY passenger_cancellation_rate DESC, p.route_name
LIMIT 10;

-- [G3] Several FILTER aggregates in one pass: final-status mix by class (Confirmed, RAC, Waitlisted, Cancelled kept distinguishable).
SELECT travel_class,
       count(*) FILTER (WHERE final_status = 'Confirmed')  AS confirmed,
       count(*) FILTER (WHERE final_status = 'RAC')        AS rac,
       count(*) FILTER (WHERE final_status = 'Waitlisted') AS waitlisted,
       count(*) FILTER (WHERE final_status = 'Cancelled')  AS cancelled,
       count(*) AS passengers
FROM analytics.v_passenger
GROUP BY travel_class
ORDER BY travel_class;

-- [G4] ROLLUP: bookings and gross value by journey month and class, with month subtotals and a grand total (first 14 rows).
SELECT coalesce(journey_month, 'ALL MONTHS') AS journey_month, coalesce(travel_class, 'ALL CLASSES') AS travel_class, count(*) AS bookings, sum(total_fare) AS gross_value
FROM analytics.v_booking
GROUP BY ROLLUP (journey_month, travel_class)
ORDER BY journey_month, travel_class
LIMIT 14;

-- [G5] GROUPING SETS: three summaries (by class, by season of travel, overall) in one query.
SELECT coalesce(v.travel_class, '-') AS travel_class, coalesce(c.season, '-') AS season, count(*) AS bookings
FROM analytics.v_booking v
JOIN core.calendar c ON c.calendar_date = v.journey_date
GROUP BY GROUPING SETS ((v.travel_class), (c.season), ())
ORDER BY travel_class, season;

-- [G6] HAVING on a normalised measure: months whose bookings per simulated run exceed 300 (raw monthly totals reflect the sampling design).
SELECT b.journey_month, b.bookings, o.simulated_runs, round(b.bookings::numeric / o.simulated_runs, 1) AS bookings_per_run
FROM (SELECT journey_month, count(*) AS bookings FROM analytics.v_booking GROUP BY journey_month) b
JOIN (SELECT journey_month, count(*) AS simulated_runs FROM analytics.v_run GROUP BY journey_month) o USING (journey_month)
GROUP BY b.journey_month, b.bookings, o.simulated_runs
HAVING b.bookings::numeric / o.simulated_runs > 300
ORDER BY bookings_per_run DESC;
