#!/usr/bin/env bash
# A2: uji hipotesis rollback berulang (database sementara). Prasyarat: make up.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a
DB="snr_perf_diag_$$"
PSQL=(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q)
trap '"${PSQL[@]}" -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1 || true' EXIT
"${PSQL[@]}" -c "CREATE DATABASE $DB" >/dev/null
# Rencana query yang lambat (>100 ms) dicatat di log PostgreSQL: docker compose logs postgres
for setting in "session_preload_libraries = 'auto_explain'" "auto_explain.log_min_duration = '-1'" \
  "auto_explain.log_analyze = on" "auto_explain.log_buffers = on" "auto_explain.log_triggers = on" "auto_explain.log_nested_statements = on"; do
  "${PSQL[@]}" -c "ALTER DATABASE $DB SET $setting" >/dev/null
done
docker compose run --rm --no-deps -T -e POSTGRES_DB=$DB web python manage.py migrate --noinput >/dev/null
docker compose run --rm --no-deps -T -e POSTGRES_DB=$DB -e PYTHONPATH=/app:/bench \
  -e PERF_N="${1:-5000}" -e PERF_VACUUM="${PERF_VACUUM:-1}" \
  -v "$PWD/tests/benchmarks:/bench:ro" web python /bench/perf_diag.py
