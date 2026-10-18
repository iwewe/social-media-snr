#!/usr/bin/env bash
# Restore backup SNR ke database dan direktori evidence BARU lalu verifikasi (WP-3.6, NFR-10).
# Pakai: restore.sh <direktori-backup> <nama-db-target> <direktori-evidence-target>
# Menolak: checksum backup salah, backup INCONSISTENT, database target sudah ada, direktori target tidak
# kosong (tidak pernah menimpa data yang ada). Setelah restore: `manage.py restore_check verify`
# (jumlah baris sama, katalog artefak sama, hash setiap berkas bukti dihitung ulang).
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP="${1:?direktori backup}"
TARGET_DB="${2:?nama database target}"
TARGET_EVIDENCE="${3:?direktori evidence target}"
set -a
# shellcheck disable=SC1091
. ./.env
set +a

[ -d "$BACKUP" ] || { echo "backup tidak ada: $BACKUP" >&2; exit 1; }
[ ! -e "$BACKUP/INCONSISTENT" ] || { echo "backup ditandai INCONSISTENT; ditolak" >&2; exit 1; }
(cd "$BACKUP" && sha256sum -c --quiet SHA256SUMS) || { echo "checksum backup tidak cocok; ditolak" >&2; exit 1; }
if [ -e "$TARGET_EVIDENCE" ] && [ -n "$(ls -A "$TARGET_EVIDENCE")" ]; then
  echo "direktori evidence target tidak kosong: $TARGET_EVIDENCE" >&2
  exit 1
fi
exists="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -Atc \
  "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'")"
[ -z "$exists" ] || { echo "database target sudah ada: $TARGET_DB" >&2; exit 1; }

echo "== membuat database $TARGET_DB dan memulihkan"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $TARGET_DB" >/dev/null
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" \
  --no-owner --exit-on-error <"$BACKUP/db.dump"
umask 077
mkdir -p "$TARGET_EVIDENCE"
tar -C "$TARGET_EVIDENCE" -xpf "$BACKUP/evidence.tar"

echo "== verifikasi hasil restore"
docker compose run --rm --no-deps -T -e POSTGRES_DB="$TARGET_DB" -e SNR_DATA_ROOT=/restore \
  -v "$(realpath "$TARGET_EVIDENCE"):/restore/evidence:ro" -v "$(realpath "$BACKUP"):/backup:ro" \
  web python manage.py restore_check verify --expect /backup/snapshot.json
echo "RESTORE OK: $TARGET_DB + $TARGET_EVIDENCE"
