#!/usr/bin/env bash
# Rebuild the whole PostgreSQL layer from the SQL scripts (Linux / macOS / WSL / Git Bash).
#   sql/run_all.sh [--yes]        connection settings come from the usual PG* environment variables
# DESTRUCTIVE for the schemas stg, core, analytics, qa and sandbox of the target database.
# All data is SYNTHETIC (sampled simulation: 768 of 19,708 scheduled runs). Not IRCTC data.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PGDATABASE="${PGDATABASE:-irctc_analytics}"
export PGCLIENTENCODING="${PGCLIENTENCODING:-UTF8}"
for f in stations routes trains train_stops calendar seat_capacity train_operations bookings booking_passengers cancellations; do
  [ -f "data/processed/cleaned/$f.csv" ] || { echo "Missing data/processed/cleaned/$f.csv. Run: python python/src/pipeline.py" >&2; exit 2; }
done
if [ "${1:-}" != "--yes" ]; then
  echo "This DROPS and recreates the schemas stg, core, analytics, qa and sandbox in database '$PGDATABASE'."
  read -r -p "Type YES to continue: " answer
  [ "$answer" = "YES" ] || { echo "Cancelled. Nothing was changed."; exit 1; }
fi
psql -X -v ON_ERROR_STOP=1 -f sql/00_build_all.sql
echo "Build finished. Results: reports/phase4_check_results.csv and reports/phase4_kpi_reconciliation.csv"
