#!/usr/bin/env bash
# Demo web SNR dengan data SINTETIS pada database terpisah (snr_demo). Bukan bagian CI.
# Pakai:  bash deployment/demo.sh up | down     (atau: make demo / make demo-down)
# Akun demo dibuat dengan kata sandi ACAK dan ditulis ke ~/snr-demo/credentials.txt (izin 600; di luar Git).
# Web hanya di 127.0.0.1:5174: buka lewat tunnel SSH (ssh -L 5174:127.0.0.1:5174 <host>). Tanpa HTTPS.
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO="$HOME/snr-demo"
DB=snr_demo
WEB=snr-demo-web
FRONT=snr-demo-front
WORKER=snr-demo-worker
set -a; . ./.env; set +a

down() {
  docker rm -f "$WEB" "$FRONT" "$WORKER" >/dev/null 2>&1 || true
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1 || true
}

if [ "${1:-}" = "down" ]; then down; echo "demo dihentikan; database $DB dihapus"; exit 0; fi

down
rm -rf "$DEMO"; mkdir -p "$DEMO/data/evidence" "$DEMO/data/browser-profiles" "$DEMO/syn"
chmod 700 "$DEMO/data/browser-profiles"
rand() { openssl rand -base64 18 | tr -d '/+=' ; }
PW_ADMIN="$(rand)"; PW_OWNER="$(rand)"; PW_VIEWER="$(rand)"
umask 077
printf 'demo_admin  %s\ndemo_owner  %s\ndemo_viewer %s\n' "$PW_ADMIN" "$PW_OWNER" "$PW_VIEWER" > "$DEMO/credentials.txt"

echo "== dataset sintetis"
docker compose run --rm --no-deps -v "$DEMO/syn:/syn" web python -m intelligence.synthetic --out /syn

DEMO_ENV=(-e POSTGRES_DB=$DB -e CELERY_BROKER_URL=redis://valkey:6379/2 -e SNR_DATA_ROOT=/demodata
  -e SNR_FIXTURE_DATASETS_DIR=/demo-datasets -v "$DEMO/data:/demodata" -v "$DEMO/syn/datasets:/demo-datasets:ro")

echo "== database"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $DB" >/dev/null
docker compose run --rm --no-deps "${DEMO_ENV[@]}" web python manage.py migrate --noinput >/dev/null

echo "== seed"
docker compose run --rm --no-deps -T "${DEMO_ENV[@]}" -e PW_ADMIN="$PW_ADMIN" -e PW_OWNER="$PW_OWNER" -e PW_VIEWER="$PW_VIEWER" \
  web python manage.py shell < deployment/demo_seed.py

echo "== menjalankan web, worker, frontend"
docker compose run -d --no-deps --name "$WEB" -p 127.0.0.1:8001:8001 "${DEMO_ENV[@]}" \
  -e DJANGO_ALLOWED_HOSTS="$FRONT,$WEB,localhost,127.0.0.1" \
  web python manage.py runserver 0.0.0.0:8001 >/dev/null
docker compose run -d --no-deps --name "$WORKER" "${DEMO_ENV[@]}" \
  web celery -A config worker -Q analysis,celery -c 1 -l info >/dev/null
docker compose run -d --no-deps --name "$FRONT" -p 127.0.0.1:5174:5174 \
  -e VITE_API_PROXY="http://$WEB:8001" -e VITE_ALLOWED_HOSTS="$FRONT,localhost" \
  frontend npm run dev -- --host 0.0.0.0 --port 5174 >/dev/null
echo "siap: http://localhost:5174 (lewat tunnel SSH ke VM). Akun: $DEMO/credentials.txt"
