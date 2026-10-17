#!/usr/bin/env bash
# Mengukur durasi run (A1) pada database sementara; tidak menyentuh data dev. Prasyarat: make up.
# Hasil dari simulasi/dataset sintetis BUKAN dasar angka untuk platform nyata.
set -euo pipefail
cd "$(dirname "$0")/.."
DB=snr_measure
N="${1:-20}"
DATA="$(mktemp -d)"
set -a
# shellcheck disable=SC1091
. ./.env
set +a
cleanup() {
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1 || true
  rm -rf "$DATA"
}
trap cleanup EXIT
cleanup >/dev/null 2>&1 || true
DATA="$(mktemp -d)"
mkdir -p "$DATA/evidence" "$DATA/browser-profiles"
chmod 700 "$DATA/browser-profiles"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $DB" >/dev/null
docker compose run --rm --no-deps -e POSTGRES_DB=$DB web python manage.py migrate --noinput >/dev/null
docker compose run --rm --no-deps -e POSTGRES_DB=$DB -e SNR_DATA_ROOT=/mdata -e PYTHONPATH=/app -v "$DATA:/mdata" \
  -v "$PWD/tests/benchmarks:/bench:ro" worker-browser python /bench/measure_durations.py "$N"
