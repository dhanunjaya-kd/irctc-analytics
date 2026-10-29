-- 04_ctes.sql: common table expressions, chained and recursive.

-- [T1] Waiting-list funnel by class (CTE chain). Waiting-List Demand = passengers waitlisted AT BOOKING TIME; clearance rate denominator = that demand.
WITH wl AS (
    SELECT travel_class, count(*) AS wl_demand,
           count(*) FILTER (WHERE final_status IN ('Confirmed','RAC')) AS cleared,
           count(*) FILTER (WHERE final_status = 'Cancelled') AS cancelled_while_waiting,
           count(*) FILTER (WHERE final_status = 'Waitlisted') AS uncleared_refunded_by_system
    FROM analytics.v_passenger
    WHERE initial_status = 'Waitlisted'
    GROUP BY travel_class),
rates AS (
    SELECT *, round(cleared::numeric / wl_demand, 4) AS clearance_rate, round(uncleared_refunded_by_system::numeric / wl_demand, 4) AS uncleared_share
    FROM wl)
SELECT * FROM rates ORDER BY travel_class;

-- [T2] RECURSIVE CTE: rebuild the cumulative distance of one train from its legs and compare with the stored distance_from_origin_km.
WITH RECURSIVE legs AS (
    SELECT a.train_id, a.stop_sequence AS seq, 0::numeric AS walked_km, a.distance_from_origin_km AS stored_km
    FROM core.train_stops a WHERE a.stop_sequence = 1 AND a.train_id = (SELECT min(train_id) FROM core.trains)
  UNION ALL
    SELECT l.train_id, s.stop_sequence, l.walked_km + (s.distance_from_origin_km - p.distance_from_origin_km), s.distance_from_origin_km
    FROM legs l
    JOIN core.train_stops p ON p.train_id = l.train_id AND p.stop_sequence = l.seq
    JOIN core.train_stops s ON s.train_id = l.train_id AND s.stop_sequence = l.seq + 1)
SELECT train_id, seq, walked_km, stored_km, (walked_km = stored_km) AS consistent FROM legs ORDER BY seq;

-- [T3] Chained CTEs: per-run, capacity-normalised demand by month and its gap to the all-months average (no raw-total comparisons).
WITH monthly AS (
    SELECT b.journey_month, count(*) AS bookings,
           (SELECT count(*) FROM analytics.v_run o WHERE o.journey_month = b.journey_month) AS simulated_runs,
           (SELECT sum(c.total_seats) FROM core.seat_capacity c WHERE to_char(c.journey_date, 'YYYY-MM') = b.journey_month) AS seat_supply
    FROM analytics.v_booking b GROUP BY b.journey_month),
norm AS (
    SELECT journey_month, bookings::numeric / simulated_runs AS bookings_per_run, bookings::numeric / seat_supply AS bookings_per_seat FROM monthly)
SELECT journey_month, round(bookings_per_run, 1) AS bookings_per_run, round(bookings_per_seat, 3) AS bookings_per_seat,
       round(bookings_per_run - avg(bookings_per_run) OVER (), 1) AS gap_to_average_per_run
FROM norm
ORDER BY journey_month
LIMIT 12;

-- [T4] Data-modifying CTE on a scratch copy (rolled back, so core stays untouched): update and report the changed rows in one statement.
BEGIN;
CREATE TEMP TABLE tmp_capacity AS SELECT * FROM core.seat_capacity LIMIT 5;
WITH changed AS (UPDATE tmp_capacity SET wl_limit = wl_limit + 10 RETURNING capacity_id, wl_limit)
SELECT count(*) AS rows_changed, min(wl_limit) AS min_new_wl_limit FROM changed;
ROLLBACK;
