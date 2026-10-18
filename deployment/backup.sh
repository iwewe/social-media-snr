#!/usr/bin/env bash
# Backup lokal SNR (WP-3.6, NFR-10): PostgreSQL (pg_dump -Fc) + evidence/ + snapshot + SHA256SUMS.
#
# TIDAK dibackup: browser-profiles/ (berisi cookie/sesi = kredensial rahasia, PRD bagian 13) dan .env.
# Backup harus berada di perangkat/penyimpanan BERBEDA dari data utama; skrip menolak bila satu
# perangkat (kecuali SNR_BACKUP_ALLOW_SAME_DEVICE=1, hanya untuk uji; itu bukan perlindungan sungguhan).
#
# Env: SNR_BACKUP_DIR (wajib), BACKUP_DB (bawaan POSTGRES_DB), SNR_EVIDENCE_HOST_DIR (bawaan
# ${SNR_HOST_DATA:-./snr-data}/evidence). Keluaran: satu direktori bertanda waktu di SNR_BACKUP_DIR;
# jalurnya dicetak di baris terakhir ("BACKUP <jalur>"). Kode keluar 3 = data berubah selama backup
# (tidak konsisten; ulangi saat tidak ada inspeksi berjalan).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

: "${SNR_BACKUP_DIR:?SNR_BACKUP_DIR wajib diisi (penyimpanan terpisah dari data utama)}"
DB="${BACKUP_DB:-$POSTGRES_DB}"
EVIDENCE="${SNR_EVIDENCE_HOST_DIR:-${SNR_HOST_DATA:-./snr-data}/evidence}"
[ -d "$EVIDENCE" ] || { echo "direktori evidence tidak ada: $EVIDENCE" >&2; exit 1; }

umask 077
mkdir -p "$SNR_BACKUP_DIR"
chmod 700 "$SNR_BACKUP_DIR"
if [ "$(stat -c %d "$EVIDENCE")" = "$(stat -c %d "$SNR_BACKUP_DIR")" ]; then
  if [ "${SNR_BACKUP_ALLOW_SAME_DEVICE:-0}" != "1" ]; then
    echo "SNR_BACKUP_DIR berada di perangkat yang sama dengan data utama: bukan backup yang terpisah." >&2
    exit 2
  fi
  echo "PERINGATAN: backup di perangkat yang sama dengan data (hanya untuk uji)." >&2
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SNR_BACKUP_DIR/snr-$STAMP"
mkdir "$OUT"

snapshot() {
  docker compose run --rm --no-deps -T -e POSTGRES_DB="$DB" -e SNR_DATA_ROOT=/snap \
    -v "$(realpath "$EVIDENCE"):/snap/evidence:ro" -v "$OUT:/out" \
    web python manage.py restore_check snapshot --out "/out/$1" >/dev/null
}

echo "== snapshot sebelum"
snapshot snapshot.json
echo "== pg_dump ($DB)"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$DB" -Fc >"$OUT/db.dump"
echo "== evidence"
tar -C "$EVIDENCE" -cf "$OUT/evidence.tar" .
echo "== snapshot sesudah"
snapshot snapshot-after.json

if ! cmp -s "$OUT/snapshot.json" "$OUT/snapshot-after.json"; then
  : >"$OUT/INCONSISTENT"
  echo "Data berubah selama backup; backup ditandai INCONSISTENT dan ditolak saat restore." >&2
  echo "BACKUP $OUT"
  exit 3
fi
rm "$OUT/snapshot-after.json"

printf '{"created_utc": "%s", "database": "%s", "format": 1}\n' "$STAMP" "$DB" >"$OUT/BACKUP_INFO.json"
(cd "$OUT" && sha256sum db.dump evidence.tar snapshot.json BACKUP_INFO.json >SHA256SUMS)
chmod -R go-rwx "$OUT"
echo "BACKUP $OUT"
