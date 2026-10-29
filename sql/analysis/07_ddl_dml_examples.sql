-- 07_ddl_dml_examples.sql: DDL and DML examples in a throwaway SANDBOX schema. Nothing in core, stg, analytics or qa is changed;
-- the schema is dropped at the end (the Phase 4 tests check that core row counts are identical before and after).

-- [D1] DDL: create a schema and a table with PRIMARY KEY, UNIQUE, NOT NULL and CHECK constraints.
CREATE SCHEMA sandbox;
CREATE TABLE sandbox.kpi_snapshot (
    snapshot_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kpi_key      TEXT NOT NULL UNIQUE,
    value        NUMERIC NOT NULL CHECK (value >= 0),
    note         TEXT
);

-- [D2] DML: INSERT ... SELECT from an analytics view.
INSERT INTO sandbox.kpi_snapshot (kpi_key, value)
SELECT kpi_key, value FROM analytics.v_kpi_overall_long WHERE kpi_key IN ('total_bookings', 'total_passengers', 'occupancy', 'passenger_cancellation_rate');

-- [D3] DDL: ALTER TABLE (add a column and a constraint) and CREATE INDEX.
ALTER TABLE sandbox.kpi_snapshot ADD COLUMN data_origin TEXT NOT NULL DEFAULT 'DERIVED';
ALTER TABLE sandbox.kpi_snapshot ADD CONSTRAINT ck_kpi_snapshot_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'));
CREATE INDEX ix_kpi_snapshot_value ON sandbox.kpi_snapshot (value);

-- [D4] DML: multi-row INSERT with ON CONFLICT (upsert).
INSERT INTO sandbox.kpi_snapshot (kpi_key, value, note) VALUES ('occupancy', 0.0, 'overwritten by upsert'), ('simulated_runs', 768, 'new row')
ON CONFLICT (kpi_key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;

-- [D5] DML: UPDATE using values from another table (UPDATE ... FROM).
UPDATE sandbox.kpi_snapshot s SET value = o.value, note = 'restored from analytics.v_kpi_overall_long'
FROM analytics.v_kpi_overall_long o WHERE o.kpi_key = s.kpi_key AND s.kpi_key = 'occupancy';

-- [D6] DML: DELETE with a subquery.
DELETE FROM sandbox.kpi_snapshot WHERE kpi_key IN (SELECT kpi_key FROM sandbox.kpi_snapshot WHERE note = 'new row');

-- [D7] DML: MERGE (PostgreSQL 15 and later) to synchronise a target with a source.
MERGE INTO sandbox.kpi_snapshot t
USING (SELECT 'otp'::text AS kpi_key, value FROM analytics.v_kpi_overall_long WHERE kpi_key = 'otp') s ON t.kpi_key = s.kpi_key
WHEN MATCHED THEN UPDATE SET value = s.value
WHEN NOT MATCHED THEN INSERT (kpi_key, value, note) VALUES (s.kpi_key, s.value, 'merged');

-- [D8] A constraint violation is rejected (caught here so the script continues): negative values are not allowed.
DO $$
BEGIN
    INSERT INTO sandbox.kpi_snapshot (kpi_key, value) VALUES ('bad_value', -1);
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'rejected as expected: %', SQLERRM;
END $$;

-- [D9] Transactions: SAVEPOINT and ROLLBACK TO SAVEPOINT keep the earlier work and discard the later change.
BEGIN;
INSERT INTO sandbox.kpi_snapshot (kpi_key, value, note) VALUES ('kept_row', 1, 'inside the transaction');
SAVEPOINT before_risky_change;
DELETE FROM sandbox.kpi_snapshot;
ROLLBACK TO SAVEPOINT before_risky_change;
COMMIT;

-- [D10] CREATE TABLE AS, CREATE VIEW, TRUNCATE.
CREATE TABLE sandbox.snapshot_copy AS SELECT * FROM sandbox.kpi_snapshot;
CREATE VIEW sandbox.v_snapshot_summary AS SELECT count(*) AS kpis, min(value) AS min_value, max(value) AS max_value FROM sandbox.snapshot_copy;
TRUNCATE sandbox.snapshot_copy;

-- [D11] Clean up: drop the sandbox schema and everything in it.
DROP SCHEMA sandbox CASCADE;
