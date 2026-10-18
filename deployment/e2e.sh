#!/usr/bin/env bash
# E2E browser untuk workspace (WP-0.5). Memakai DATABASE TERPISAH (snr_e2e) dan container
# sementara, sehingga data uji tidak mengotori database dev (versi konteks append-only,
# tidak bisa dihapus). Semua dibersihkan saat selesai. Prasyarat: `make up` (stack dev hidup).
set -euo pipefail
cd "$(dirname "$0")/.."

DB=snr_e2e
WEB=snr-e2e-web
FRONT=snr-e2e-front
WORKER=snr-e2e-worker
E2E_DATA="$(mktemp -d)"
SHOTS="$PWD/e2e-shots"
PASSWORD="$(openssl rand -base64 18 | tr -d '/+=')"
E2E_USER=e2e_user
E2E_ADMIN=e2e_admin

set -a
# shellcheck disable=SC1091
. ./.env
set +a

cleanup() {
  docker rm -f "$WEB" "$FRONT" "$WORKER" >/dev/null 2>&1 || true
  rm -rf "$E2E_DATA"
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1 || true
  echo "dibersihkan: container sementara dan database $DB"
}
trap cleanup EXIT

mkdir -p "$SHOTS"
cleanup >/dev/null

echo "== menyiapkan database $DB"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $DB" >/dev/null
docker compose run --rm --no-deps -e POSTGRES_DB=$DB web python manage.py migrate --noinput >/dev/null
docker compose run --rm --no-deps -e POSTGRES_DB=$DB -e E2E_PW="$PASSWORD" web python manage.py shell -c \
  "import os; from django.contrib.auth.models import User; User.objects.create_user('$E2E_USER', password=os.environ['E2E_PW']); User.objects.create_superuser('$E2E_ADMIN', password=os.environ['E2E_PW'])"

echo "== menjalankan backend dan frontend sementara"
# Broker terpisah (Valkey DB 1) agar worker dev tidak mengambil tugas E2E (dan sebaliknya); data bukti
# E2E di direktori sementara, bukan di evidence dev. Adapter dataset memakai datasets/sample.
mkdir -p "$E2E_DATA/evidence" "$E2E_DATA/browser-profiles"
chmod 700 "$E2E_DATA/browser-profiles"
E2E_ENV=(-e POSTGRES_DB=$DB -e CELERY_BROKER_URL=redis://valkey:6379/1
  -e SNR_DATA_ROOT=/e2edata -e SNR_FIXTURE_DATASETS_DIR=/datasets/sample -v "$E2E_DATA:/e2edata")
docker compose run -d --no-deps --name "$WEB" "${E2E_ENV[@]}" \
  -e DJANGO_ALLOWED_HOSTS="$FRONT,localhost" \
  web python manage.py runserver 0.0.0.0:8001 >/dev/null
docker compose run -d --no-deps --name "$WORKER" "${E2E_ENV[@]}" \
  web celery -A config worker -Q analysis,celery -c 1 -l info >/dev/null
docker compose run -d --no-deps --name "$FRONT" \
  -e VITE_API_PROXY="http://$WEB:8001" -e VITE_ALLOWED_HOSTS="$FRONT" \
  frontend npm run dev -- --host 0.0.0.0 --port 5174 >/dev/null

echo "== menunggu frontend siap"
for _ in $(seq 1 60); do
  if docker compose run --rm --no-deps web python -c \
    "import urllib.request as u; u.urlopen('http://$FRONT:5174/')" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "== menunggu worker siap"
for _ in $(seq 1 60); do
  if docker logs "$WORKER" 2>&1 | grep -q " ready\."; then break; fi
  sleep 1
done
docker logs "$WORKER" 2>&1 | grep -q " ready\." || { echo "worker E2E tidak siap"; docker logs "$WORKER" | tail -20; exit 1; }

echo "== menjalankan skenario browser"
for flow in workspace_flow inspection_flow team_flow; do
  echo "-- $flow"
  docker compose run --rm --no-deps \
    -v "$PWD/tests/e2e:/e2e:ro" -v "$SHOTS:/shots" \
    -e E2E_BASE_URL="http://$FRONT:5174" -e E2E_USER="$E2E_USER" -e E2E_ADMIN="$E2E_ADMIN" \
    -e E2E_PASSWORD="$PASSWORD" -e E2E_SHOTS=/shots \
    worker-browser python "/e2e/$flow.py"
done

echo "-- analysis_flow (analisis I2 dari run_analyses pada data E2E)"
ANALYSIS_IDS="$(docker compose run --rm --no-deps -e POSTGRES_DB=$DB web python manage.py shell -c \
  "from collection.models import InspectionRun; from investigations.models import Issue, Proposition; \
r = [x for x in InspectionRun.objects.order_by('id') if isinstance(x.ingestion, dict) and x.ingestion.get('state', '').startswith('FINISHED')]; \
inv = r[0].target.investigation; \
issue = inv.issues.first() or Issue.objects.create(investigation=inv, title='Isu analisis E2E', created_by=inv.created_by); \
p = issue.propositions.first() or Proposition.objects.create(issue=issue, number=1, statement='Klaim uji E2E', created_by=inv.created_by); \
print('IDS', inv.pk, p.pk)" | grep '^IDS' | tail -1)"
read -r _ ANALYSIS_INV ANALYSIS_PROP <<<"$ANALYSIS_IDS"
docker compose run --rm --no-deps -e POSTGRES_DB=$DB web python manage.py run_analyses \
  --investigation "$ANALYSIS_INV" --proposition "$ANALYSIS_PROP" --user "$E2E_USER" \
  --pro-cue setuju --contra-cue tolak --exploratory
docker compose run --rm --no-deps \
  -v "$PWD/tests/e2e:/e2e:ro" -v "$SHOTS:/shots" \
  -e E2E_BASE_URL="http://$FRONT:5174" -e E2E_USER="$E2E_USER" -e E2E_PASSWORD="$PASSWORD" \
  -e E2E_INVESTIGATION="$ANALYSIS_INV" -e E2E_SHOTS=/shots \
  worker-browser python /e2e/analysis_flow.py

echo "-- tamper_flow (berkas bukti diubah di disk)"
TARGET_FILE="$(find "$E2E_DATA/evidence" -type f -name 'putaran4.html' | head -1)"
[ -n "$TARGET_FILE" ] || { echo "berkas DOM bukti tidak ditemukan untuk uji pengubahan"; exit 1; }
chmod u+w "$TARGET_FILE"
printf '<!-- diubah -->' >> "$TARGET_FILE"
docker compose run --rm --no-deps \
  -v "$PWD/tests/e2e:/e2e:ro" -v "$SHOTS:/shots" \
  -e E2E_BASE_URL="http://$FRONT:5174" -e E2E_USER="$E2E_USER" -e E2E_PASSWORD="$PASSWORD" \
  -e E2E_SHOTS=/shots \
  worker-browser python /e2e/tamper_flow.py
