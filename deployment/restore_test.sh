#!/usr/bin/env bash
# Uji restore terencana (WP-3.6, NFR-10): backup -> restore ke database dan direktori sementara ->
# verifikasi -> uji negatif (berkas bukti diubah harus TERDETEKSI) -> bersihkan.
# Env sama dengan backup.sh. Mengembalikan 0 hanya bila restore setia DAN pengubahan terdeteksi.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a
SRC_DB="${BACKUP_DB:-$POSTGRES_DB}"
WORK="$(mktemp -d)"
TEST_DB="${SRC_DB}_restoretest"
if [ -z "${SNR_BACKUP_DIR:-}" ]; then
  # Uji sementara: direktori kerja ada di perangkat yang sama dengan data (bukan backup sungguhan).
  export SNR_BACKUP_DIR="$WORK/backups" SNR_BACKUP_ALLOW_SAME_DEVICE=1
fi

cleanup() {
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $TEST_DB WITH (FORCE)" >/dev/null 2>&1 || true
  chmod -R u+w "$WORK" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $TEST_DB WITH (FORCE)" >/dev/null

echo "###### 1. backup"
BACKUP_LINE="$(bash deployment/backup.sh | tee /dev/stderr | grep '^BACKUP ' | tail -1)"
BACKUP="${BACKUP_LINE#BACKUP }"
echo "###### 2. restore ke $TEST_DB"
RESTORED="$WORK/evidence-restored"
bash deployment/restore.sh "$BACKUP" "$TEST_DB" "$RESTORED"

echo "###### 3. uji negatif: backup yang rusak harus ditolak"
cp -r "$BACKUP" "$WORK/rusak"
printf 'x' >>"$WORK/rusak/db.dump"
if bash deployment/restore.sh "$WORK/rusak" "${TEST_DB}_x" "$WORK/ev-x" >/dev/null 2>&1; then
  echo "GAGAL: backup rusak diterima" >&2; exit 1
fi
echo "ok: backup dengan checksum salah ditolak"

echo "###### 4. uji negatif: berkas bukti hasil restore diubah harus terdeteksi"
TARGET_FILE="$(find "$RESTORED" -type f ! -name 'manifest*' | head -1)"
if [ -n "$TARGET_FILE" ]; then
  chmod u+w "$TARGET_FILE"
  printf 'diubah' >>"$TARGET_FILE"
  if docker compose run --rm --no-deps -T -e POSTGRES_DB="$TEST_DB" -e SNR_DATA_ROOT=/restore \
      -v "$(realpath "$RESTORED"):/restore/evidence:ro" -v "$(realpath "$BACKUP"):/backup:ro" \
      web python manage.py restore_check verify --expect /backup/snapshot.json >/dev/null 2>&1; then
    echo "GAGAL: perubahan berkas bukti tidak terdeteksi" >&2; exit 1
  fi
  echo "ok: perubahan berkas bukti terdeteksi"
else
  echo "(tidak ada berkas bukti pada sumber; uji negatif berkas dilewati)"
fi
echo "UJI RESTORE LULUS"
