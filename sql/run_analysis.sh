#!/usr/bin/env bash
# Run the analytical SQL files in sql/analysis (all, or one: sql/run_analysis.sh 05_window_functions.sql).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PGDATABASE="${PGDATABASE:-irctc_analytics}" PGCLIENTENCODING="${PGCLIENTENCODING:-UTF8}"
files=("sql/analysis/${1:-}")
[ -n "${1:-}" ] || files=(sql/analysis/*.sql)
for f in "${files[@]}"; do echo "=== $f ==="; psql -X -v ON_ERROR_STOP=1 -f "$f"; done
