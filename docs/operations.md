# Operasi: backup, restore, retensi, dan rahasia

Ringkasan prosedur operasional SNR (WP-3.6). Keputusan dan alasannya: ADR 0034. Angka yang tidak ditetapkan PRD
sengaja dibiarkan kosong; jangan diisi tanpa keputusan.

## Backup

```
SNR_BACKUP_DIR=/mnt/backup-snr bash deployment/backup.sh     # atau: make backup
```

- `SNR_BACKUP_DIR` harus berada di perangkat berbeda dari data utama (skrip menolak bila sama).
- Hasil: `snr-<waktu-utc>/` berisi `db.dump`, `evidence.tar`, `snapshot.json`, `BACKUP_INFO.json`, `SHA256SUMS`
  (izin 700/600). `browser-profiles/` dan `.env` tidak ikut (kredensial).
- Jalankan saat tidak ada inspeksi berjalan. Kode keluar 3 = data berubah selama backup (`INCONSISTENT`); ulangi.
- Jadwal dan jumlah salinan yang disimpan ditetapkan operator (belum ditentukan PRD).

## Restore

```
bash deployment/restore.sh <direktori-backup> <nama-db-baru> <direktori-evidence-baru>
```

Menolak checksum salah, backup `INCONSISTENT`, database target sudah ada, atau direktori target tidak kosong.
Setelah restore, `restore_check verify` memeriksa jumlah baris, katalog artefak, dan hash setiap berkas bukti.
Sesi login platform harus dibuat ulang (tidak dibackup).

## Uji restore terencana

```
make restore-test        # stack nyata; atau otomatis di dalam `make e2e` pada data E2E
```

Langkah: backup, restore ke database sementara, verifikasi, uji negatif (backup rusak ditolak; berkas bukti
yang diubah terdeteksi), bersih-bersih. Lakukan sebelum pilot dan setiap kali format backup berubah; catat hasilnya di bawah.

### Catatan hasil uji restore

| Tanggal | Sumber | Hasil |
|---|---|---|
| 2026-10-19 | Data E2E (`make e2e`): 2 artefak bukti, seluruh model domain | Lulus: restore setia (jumlah baris dan katalog sama, hash semua berkas cocok); checksum backup rusak ditolak; berkas bukti yang diubah terdeteksi |
| 2026-10-19 | Database demo sintetis (3 target x 4 putaran, seluruh rantai analisis dan audit; tanpa artefak berkas) | Lulus: jumlah baris semua model domain sama; checksum backup rusak ditolak; uji berkas bukti dilewati karena sumber tidak punya artefak |

## HTTPS (TLS)

```
cp .env.example .env   # isi DJANGO_SECRET_KEY, POSTGRES_PASSWORD, SNR_DOMAIN, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS
docker compose -f compose.yaml -f compose.tls.yaml --profile build run --rm frontend-build
docker compose -f compose.yaml -f compose.tls.yaml up -d --build
make tls-check          # uji terisolasi (tumpukan sementara, port 8443/8080)
```

- Proxy Caddy mengakhiri TLS dan mengalihkan HTTP ke HTTPS. `SNR_TLS=internal` memakai CA lokal Caddy (impor CA-nya
  ke peramban); untuk sertifikat sendiri taruh `cert.pem` dan `key.pem` di `SNR_CERTS_DIR` dan set
  `SNR_TLS="/certs/cert.pem /certs/key.pem"`.
- Port diikat ke `127.0.0.1` (ubah `SNR_BIND_ADDR` hanya dengan sengaja). HSTS: mulai `SNR_HSTS_SECONDS=3600`,
  naikkan bertahap setelah HTTPS stabil.
- Perubahan `compose.yaml` biasa (stack dev) tidak terpengaruh; frontend dev hanya dengan `--profile dev`.

## Akses bukti dan izin berkas

- Siapa mengunduh atau memverifikasi bukti: tab "Akses bukti" pada halaman analisis (API
  `GET /api/investigations/{id}/evidence-access/`).
- Periksa izin berkas data lokal: `docker compose exec web python manage.py check_data_permissions --backup-dir <dir>`
  (laporan saja; kebijakan: evidence read-only dan tertutup bagi other, browser-profiles dan backup hanya pemilik).

## Retensi dan penghapusan (kerangka)

Belum ada keputusan durasi. Sampai ada keputusan: tidak ada penghapusan otomatis; data investigasi bersifat
append-only (trigger basis data) dan penghapusan tidak tersedia di aplikasi. Prosedur yang harus disepakati
sebelum pilot: (1) siapa yang berwenang meminta penghapusan, (2) durasi per jenis data (bukti, observasi, hasil
analisis, audit), (3) cara penghapusan yang tidak merusak keterkaitan temuan, (4) pencatatan penghapusan.
Backup yang sudah ada tidak ikut terhapus otomatis; prosedur harus menyebutnya.

## Rahasia (cookie, token, kunci)

- `make secrets` (atau hook pre-commit) memindai berkas yang dilacak git; CI menjalankannya lewat tes
  "repo ini bersih". Log dapat dipindai: `docker compose logs --no-color | python3 tests/tools/secret_scan.py --stdin`.
- Cookie/sesi platform hanya hidup di `browser-profiles/` (di luar evidence dan di luar backup).
