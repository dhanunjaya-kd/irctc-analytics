# sql/: PostgreSQL layer (Phase 4)

All data is **synthetic** from a **sampled simulation** (768 simulated runs of 19,708 scheduled). Not IRCTC data. No forecasts. Full guide: [../docs/phase4_postgresql.md](../docs/phase4_postgresql.md).

Quick start (from the project root, with the empty database `irctc_analytics` and the cleaned CSV files in place):

```powershell
powershell -ExecutionPolicy Bypass -File sql\run_all.ps1        # Windows (asks you to type YES; -Force skips the prompt)
```
```bash
sql/run_all.sh --yes                                             # Linux / macOS
```

`schema/` creates schemas, tables, constraints and indexes; `transformations/` loads the cleaned CSV files and builds the analytical and star-schema views; `validation/` holds the 72 data-quality checks and the KPI reconciliation; `analysis/` holds the labelled analytical queries, the DDL/DML examples and the EXPLAIN examples. The build drops and recreates the schemas `stg`, `core`, `analytics`, `qa` and `sandbox`.
