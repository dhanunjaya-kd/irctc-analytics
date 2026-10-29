-- 03_case_subqueries.sql: CASE expressions and subqueries (scalar, correlated, IN / EXISTS / NOT EXISTS, derived tables).

-- [C1] CASE: lead-time buckets and the passenger cancellation rate in each (the generator builds in a rising rate with lead time; this shows how to analyse such a pattern).
SELECT CASE WHEN (b.journey_date - b.booking_ts::date) <= 3  THEN '1: 0-3 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 14 THEN '2: 4-14 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 30 THEN '3: 15-30 days'
            WHEN (b.journey_date - b.booking_ts::date) <= 60 THEN '4: 31-60 days'
            ELSE '5: 61-120 days' END AS lead_bucket,
       count(*) AS passengers,
       round(count(*) FILTER (WHERE bp.final_status = 'Cancelled')::numeric / count(*), 4) AS passenger_cancellation_rate
FROM core.booking_passengers bp
JOIN core.bookings b ON b.booking_id = bp.booking_id
GROUP BY 1
ORDER BY 1;

-- [C2] CASE: class-run occupancy bands (waitlisted passengers are not part of occupancy).
SELECT CASE WHEN occupancy < 0.50 THEN 'Below 50%' WHEN occupancy < 0.75 THEN '50% to below 75%' WHEN occupancy < 0.95 THEN '75% to below 95%' ELSE '95% and above' END AS occupancy_band,
       count(*) AS class_runs, round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM analytics.v_class_run
GROUP BY 1
ORDER BY min(occupancy);

-- [C3] CASE inside an aggregate: refunds split by event type without a second pass.
SELECT sum(CASE WHEN cancellation_type = 'Passenger' THEN refund_amount ELSE 0 END) AS refund_passenger_events,
       sum(CASE WHEN cancellation_type = 'System'    THEN refund_amount ELSE 0 END) AS refund_system_events,
       sum(refund_amount) AS refund_total, sum(cancellation_charge) AS retained_charges
FROM core.cancellations;

-- [S1] Scalar subquery: class-runs whose occupancy is above the overall seat-weighted occupancy.
SELECT count(*) AS class_runs_above_overall_occupancy,
       (SELECT round(sum(booked_seats) / sum(total_seats), 4) FROM analytics.v_class_run) AS overall_occupancy
FROM analytics.v_class_run
WHERE occupancy > (SELECT sum(booked_seats) / sum(total_seats) FROM analytics.v_class_run);

-- [S2] Correlated subquery: class-runs whose capacity is above the average capacity of their OWN class (the subquery is re-evaluated per outer row, so it targets a small table).
SELECT sc.travel_class, count(*) AS class_runs_above_class_average_capacity
FROM core.seat_capacity sc
WHERE sc.total_seats > (SELECT avg(sc2.total_seats) FROM core.seat_capacity sc2 WHERE sc2.travel_class = sc.travel_class)
GROUP BY sc.travel_class
ORDER BY sc.travel_class;

-- [S3] IN subquery: trains that had at least one waitlisted passenger at booking time.
SELECT t.train_number, t.train_name
FROM core.trains t
WHERE t.train_id IN (SELECT b.train_id FROM core.bookings b JOIN core.booking_passengers bp ON bp.booking_id = b.booking_id WHERE bp.initial_status = 'Waitlisted')
ORDER BY t.train_number
LIMIT 10;

-- [S4] NOT EXISTS: trains with no System refund event (no uncleared waiting list) in the simulated data.
SELECT t.train_number, t.train_name
FROM core.trains t
WHERE NOT EXISTS (SELECT 1 FROM core.bookings b JOIN core.cancellations c ON c.booking_id = b.booking_id
                  WHERE b.train_id = t.train_id AND c.cancellation_type = 'System')
ORDER BY t.train_number;

-- [S5] Subquery in FROM: the five months with the highest passengers per simulated run.
SELECT journey_month, simulated_runs, passengers, round(passengers::numeric / simulated_runs, 1) AS passengers_per_run
FROM (SELECT p.journey_month, count(*) AS passengers, (SELECT count(*) FROM analytics.v_run o WHERE o.journey_month = p.journey_month) AS simulated_runs
      FROM analytics.v_passenger p GROUP BY p.journey_month) m
ORDER BY passengers_per_run DESC
LIMIT 5;
