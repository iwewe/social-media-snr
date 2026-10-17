#!/usr/bin/env bash
# Percobaan anomali performa (A2) pada database sementara per skenario. Prasyarat: make up.
# Pemakaian: deployment/perf.sh [N] [REPS]   (matriks autovacuum x analyze x jit)
set -euo pipefail
cd "$(dirname "$0")/.."
N="${1:-10000}"
REPS="${2:-3}"
set -a
# shellcheck disable=SC1091
. ./.env
set +a
PSQL=(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q)
run_case() {  # autovacuum analyze jit
  local db="snr_perf_$$"
  "${PSQL[@]}" -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" >/dev/null
  "${PSQL[@]}" -c "CREATE DATABASE $db" >/dev/null
  "${PSQL[@]}" -d "$db" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements" >/dev/null 2>&1 || true
  "${PSQL[@]}" -c "ALTER DATABASE $db SET session_preload_libraries = 'auto_explain'" >/dev/null
  "${PSQL[@]}" -c "ALTER DATABASE $db SET auto_explain.log_min_duration = '1500ms'" >/dev/null
  "${PSQL[@]}" -c "ALTER DATABASE $db SET auto_explain.log_analyze = on" >/dev/null
  "${PSQL[@]}" -c "ALTER DATABASE $db SET auto_explain.log_buffers = on" >/dev/null
  "${PSQL[@]}" -c "ALTER DATABASE $db SET auto_explain.log_format = 'text'" >/dev/null
  docker compose run --rm --no-deps -T -e POSTGRES_DB=$db web python manage.py migrate --noinput >/dev/null
  echo "## autovacuum=$1 analyze=$2 jit=$3"
  docker compose run --rm --no-deps -T -e POSTGRES_DB=$db -e PYTHONPATH=/app \
    -e PERF_FIX="${PERF_FIX:-keep}" -e PERF_N="$N" -e PERF_REPS="$REPS" -e PERF_AUTOVACUUM="$1" -e PERF_ANALYZE="$2" -e PERF_JIT="$3" \
    -v "$PWD/tests/benchmarks:/bench:ro" web python /bench/perf_matrix.py
  "${PSQL[@]}" -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" >/dev/null
}
trap '"${PSQL[@]}" -c "DROP DATABASE IF EXISTS snr_perf_$$ WITH (FORCE)" >/dev/null 2>&1 || true' EXIT
CASES=("on never on" "off never on" "off after_ingest on" "on never off" "off never off" "off after_ingest off")
[ -n "${PERF_ONLY:-}" ] && CASES=("$PERF_ONLY")
for case in "${CASES[@]}"; do
  # shellcheck disable=SC2086
  run_case $case
done
