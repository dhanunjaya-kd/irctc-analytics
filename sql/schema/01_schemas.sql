-- 01_schemas.sql: (re)create the project schemas. DESTRUCTIVE for these schemas only: stg, core, analytics, qa, sandbox.
-- Run only against the irctc_analytics database (the master script checks the database name).
--
-- ALL DATA IN THIS DATABASE IS SYNTHETIC and comes from a SAMPLED SIMULATION: 768 simulated train runs over 24 months,
-- against 19,708 scheduled runs in the modelled schedule (3.9%). It is not IRCTC or Indian Railways data and not a
-- representative full railway schedule. No object in this database forecasts anything.
DROP SCHEMA IF EXISTS sandbox   CASCADE;
DROP SCHEMA IF EXISTS analytics CASCADE;
DROP SCHEMA IF EXISTS qa        CASCADE;
DROP SCHEMA IF EXISTS core      CASCADE;
DROP SCHEMA IF EXISTS stg       CASCADE;

CREATE SCHEMA stg;
CREATE SCHEMA core;
CREATE SCHEMA analytics;
CREATE SCHEMA qa;

COMMENT ON SCHEMA stg       IS 'Staging: cleaned CSV files loaded as text, exactly as delivered by Phase 2. SYNTHETIC data, sampled simulation (768 of 19,708 scheduled runs).';
COMMENT ON SCHEMA core      IS 'Core: typed, constrained tables implementing docs/data_dictionary.md. SYNTHETIC data, sampled simulation (768 of 19,708 scheduled runs); not IRCTC data.';
COMMENT ON SCHEMA analytics IS 'Analytics: KPI parameters and views using the approved KPI definitions (docs/KPI_definitions.md). SYNTHETIC, sampled simulation (768 of 19,708 scheduled runs): use per-run and capacity-normalised measures; not network-wide metrics; no forecasts.';
COMMENT ON SCHEMA qa        IS 'Quality assurance: reference values, data-quality checks and KPI reconciliation results. SYNTHETIC data, sampled simulation (768 of 19,708 scheduled runs).';
