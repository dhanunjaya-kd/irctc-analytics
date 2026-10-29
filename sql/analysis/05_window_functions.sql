-- 05_window_functions.sql: ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, running totals and moving averages.
-- Months are compared on PER-RUN measures: only 32 runs per month are simulated, so raw monthly totals reflect the sampling design.

-- [W1] ROW_NUMBER: the three busiest simulated class-runs in each month (ties broken by capacity_id so the numbering is deterministic).
SELECT journey_month, rn, capacity_id, travel_class, passengers, total_seats
FROM (SELECT cr.*, row_number() OVER (PARTITION BY journey_month ORDER BY passengers DESC, capacity_id) AS rn FROM analytics.v_class_run cr) x
WHERE rn <= 3
ORDER BY journey_month, rn
LIMIT 12;

-- [W2] RANK vs DENSE_RANK: trains ranked by number of simulated runs. RANK leaves gaps after ties, DENSE_RANK does not.
SELECT t.train_number, count(*) AS simulated_runs,
       rank()       OVER (ORDER BY count(*) DESC) AS rank_with_gaps,
       dense_rank() OVER (ORDER BY count(*) DESC) AS dense_rank
FROM core.train_operations o
JOIN core.trains t ON t.train_id = o.train_id
GROUP BY t.train_number
ORDER BY simulated_runs DESC, t.train_number
LIMIT 15;

-- [W3] RANK on a normalised measure: routes by passengers per simulated run (run counts shown; routes with few runs deserve caution).
SELECT route_name, simulated_runs, passengers, round(passengers::numeric / simulated_runs, 1) AS passengers_per_run,
       rank() OVER (ORDER BY passengers::numeric / simulated_runs DESC) AS demand_rank
FROM (SELECT p.route_name, count(*) AS passengers, (SELECT count(*) FROM analytics.v_run o WHERE o.route_name = p.route_name) AS simulated_runs
      FROM analytics.v_passenger p GROUP BY p.route_name) r
WHERE simulated_runs > 0
ORDER BY demand_rank, route_name
LIMIT 10;

-- [W4] LAG: month-over-month growth in bookings per simulated run (first month has no previous month, so NULL).
WITH m AS (SELECT journey_month, count(*)::numeric / (SELECT count(*) FROM analytics.v_run o WHERE o.journey_month = b.journey_month) AS bookings_per_run
           FROM analytics.v_booking b GROUP BY journey_month)
SELECT journey_month, round(bookings_per_run, 2) AS bookings_per_run, round(lag(bookings_per_run) OVER (ORDER BY journey_month), 2) AS previous_month,
       round(bookings_per_run / NULLIF(lag(bookings_per_run) OVER (ORDER BY journey_month), 0) - 1, 4) AS growth_vs_previous_month
FROM m
ORDER BY journey_month;

-- [W5] LEAD: each month's seat occupancy next to the following month's and the change (last month has no next month).
SELECT journey_month, round(occupancy, 4) AS occupancy, round(lead(occupancy) OVER (ORDER BY journey_month), 4) AS next_month_occupancy,
       round(lead(occupancy) OVER (ORDER BY journey_month) - occupancy, 4) AS change_to_next_month
FROM analytics.v_monthly_kpis
ORDER BY journey_month
LIMIT 12;

-- [W6] Running total and moving average: cumulative refunds and a 3-month moving average of occupancy.
SELECT journey_month, refund_total, sum(refund_total) OVER (ORDER BY journey_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_refunds,
       round(avg(occupancy) OVER (ORDER BY journey_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 4) AS occupancy_3m_moving_avg
FROM analytics.v_monthly_kpis
ORDER BY journey_month
LIMIT 12;

-- [W7] DENSE_RANK within groups: for every month, classes ranked by seat occupancy (ratio of sums within the month and class).
SELECT journey_month, travel_class, round(sum(booked_seats) / sum(total_seats), 4) AS occupancy,
       dense_rank() OVER (PARTITION BY journey_month ORDER BY sum(booked_seats) / sum(total_seats) DESC) AS class_rank_in_month
FROM analytics.v_class_run
GROUP BY journey_month, travel_class
ORDER BY journey_month, class_rank_in_month
LIMIT 12;

-- [W8] NTILE and FIRST_VALUE: occupancy quartile of each class-run and the highest occupancy seen in its class (first 10 class-runs).
SELECT capacity_id, travel_class, round(occupancy, 4) AS occupancy, ntile(4) OVER (ORDER BY occupancy) AS occupancy_quartile,
       round(first_value(occupancy) OVER (PARTITION BY travel_class ORDER BY occupancy DESC), 4) AS best_in_class
FROM analytics.v_class_run
ORDER BY capacity_id
LIMIT 10;
