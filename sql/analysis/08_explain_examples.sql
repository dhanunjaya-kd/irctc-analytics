-- 08_explain_examples.sql: EXPLAIN (ANALYZE, BUFFERS) examples. Timings and row estimates differ from machine to machine; read the plan SHAPE
-- (index scan vs sequential scan, join method, aggregate). Everything here is read-only (SET LOCAL lasts for one transaction).

-- [E1] Primary-key lookup: an Index Scan on pk_bookings, not a sequential scan of 201,182 rows.
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM core.bookings WHERE booking_id = 1000100;

-- [E2] Composite lookup of all bookings of one train-class run: uses ix_bookings_run_class.
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM core.bookings WHERE train_id = 5 AND journey_date = DATE '2025-01-02' AND travel_class = 'SL';

-- [E3] Partial index: passengers linked to a refund event use ix_bp_cancellation (it only holds rows with a cancellation_id).
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM core.booking_passengers WHERE cancellation_id = 100;

-- [E4] A reporting join and aggregation (hash join + hash aggregate): passengers by class and final status.
EXPLAIN (ANALYZE, BUFFERS) SELECT b.travel_class, bp.final_status, count(*) FROM core.booking_passengers bp JOIN core.bookings b ON b.booking_id = bp.booking_id GROUP BY b.travel_class, bp.final_status;

-- [E5] Index versus sequential scan on the same predicate: with sequential scans disabled for this transaction the planner shows the index alternative.
BEGIN;
SET LOCAL enable_seqscan = off;
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM core.bookings WHERE journey_date = DATE '2025-03-15';
ROLLBACK;

-- [E6] A window-function query (WindowAgg over a sorted monthly aggregate).
EXPLAIN (ANALYZE, BUFFERS) SELECT journey_month, bookings_per_run, lag(bookings_per_run) OVER (ORDER BY journey_month) FROM analytics.v_monthly_kpis;
