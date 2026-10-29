-- 03_run_validation.sql: store the validation results, print them, and export CSV copies. Paths are relative to the project root.
TRUNCATE qa.check_results;
INSERT INTO qa.check_results (check_id, category, description, violations, passed)
SELECT check_id, category, description, violations, violations = 0 FROM qa.v_check_results;

\echo '=== data-quality checks ==='
SELECT checks, passed, failed FROM qa.v_check_summary;
SELECT check_id, violations, description FROM qa.check_results WHERE NOT passed ORDER BY check_id;

\echo '=== KPI reconciliation (SQL vs reports/kpi_reference_values.csv and monthly_kpis.csv) ==='
SELECT * FROM qa.v_reconciliation_summary;
SELECT kpi_key, reference_value, sql_value, abs_diff, tolerance FROM qa.v_kpi_reconciliation WHERE NOT passed ORDER BY kpi_key;

\copy (SELECT check_id, category, description, violations, passed FROM qa.check_results ORDER BY check_id) TO 'reports/phase4_check_results.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy (SELECT kpi_key, kpi, unit, reference_value, sql_value, abs_diff, tolerance, passed FROM qa.v_kpi_reconciliation ORDER BY kpi_key) TO 'reports/phase4_kpi_reconciliation.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
