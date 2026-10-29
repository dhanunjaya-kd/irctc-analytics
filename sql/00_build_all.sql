-- 00_build_all.sql: rebuild the whole PostgreSQL layer from scripts. Run from the PROJECT ROOT:
--     psql -X -v ON_ERROR_STOP=1 -d irctc_analytics -f sql/00_build_all.sql
-- (sql/run_all.ps1 on Windows, sql/run_all.sh on Linux/macOS do this and add safety prompts.)
--
-- DESTRUCTIVE for the schemas stg, core, analytics, qa and sandbox of the target database.
-- ALL DATA IS SYNTHETIC (sampled simulation: 768 of 19,708 scheduled runs). Not IRCTC data. No forecasts.
\set ON_ERROR_STOP on
\encoding UTF8
\if :{?expected_db}
\else
  \set expected_db irctc_analytics
\endif
SELECT (current_database() = :'expected_db') AS right_db \gset
\if :right_db
\else
  \echo 'ERROR: connected to the wrong database (expected' :expected_db '). Nothing was changed. Use: psql -d irctc_analytics ...'
  \quit
\endif
\timing off
\echo '=== Phase 4 build: PostgreSQL layer for the IRCTC-inspired SYNTHETIC analytics project ==='
SELECT version() AS server_version, current_setting('server_encoding') AS server_encoding;

\ir schema/01_schemas.sql
\ir schema/02_core_tables.sql
\ir schema/04_staging_tables.sql
\ir schema/05_qa_tables.sql
\ir transformations/01_load_staging.sql
\ir transformations/02_load_core.sql
\ir schema/03_indexes.sql
\ir transformations/03_post_load.sql
\ir transformations/04_analytics_views.sql
\ir transformations/05_star_schema_views.sql
\ir transformations/06_load_reference.sql
\ir validation/01_data_quality_checks.sql
\ir validation/02_kpi_reconciliation.sql
\ir validation/03_run_validation.sql
\echo '=== build finished ==='
