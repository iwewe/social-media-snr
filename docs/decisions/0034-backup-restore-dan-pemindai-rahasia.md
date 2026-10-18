# 0034 — Backup, restore, dan pemindai rahasia (WP-3.6a)

Status: diterima. Tanggal: 2026-10-19.

## Keputusan

- **Apa yang dibackup:** PostgreSQL (`pg_dump -Fc`) dan `evidence/` (tar), ditambah `snapshot.json` (jumlah
  baris model domain dan katalog artefak) dan `SHA256SUMS`. **Tidak dibackup:** `browser-profiles/` (cookie/sesi
  adalah kredensial rahasia, PRD bagian 13) dan `.env`. Akibatnya setelah restore sesi login platform harus dibuat
  ulang, dan itu disengaja.
- **Terpisah dari penyimpanan utama (NFR-10):** `backup.sh` menolak bila `SNR_BACKUP_DIR` berada di perangkat yang
  sama dengan data (kode 2). Pengecualian `SNR_BACKUP_ALLOW_SAME_DEVICE=1` hanya untuk uji. Perangkat dan
  kapasitas ditentukan dari pengukuran pilot (PRD); skrip tidak menebaknya.
- **Konsistensi:** snapshot direkam sebelum dan sesudah dump. Bila berbeda (ada tulis selama backup), backup
  ditandai `INCONSISTENT`, skrip keluar dengan kode 3, dan `restore.sh` menolaknya. Jalankan saat tidak ada
  inspeksi berjalan.
- **Restore tidak pernah menimpa:** `restore.sh` menolak bila checksum salah, backup `INCONSISTENT`, database
  target sudah ada, atau direktori evidence target tidak kosong. Restore selalu ke database dan direktori BARU.
- **Verifikasi hasil restore (`manage.py restore_check verify`):** jumlah baris tiap model domain sama dengan
  snapshot, katalog artefak (jalur, hash, ukuran) sama, dan setiap berkas bukti dihitung ulang hash dan ukurannya
  (memakai pemeriksa yang sama dengan API verifikasi). Berkas tak tercatat hanya peringatan. Hash membuktikan
  berkas sama dengan saat dicatat, bukan keaslian konten platform.
- **Uji restore terencana:** `deployment/restore_test.sh` (backup, restore ke database sementara, verifikasi,
  uji negatif: backup rusak harus ditolak dan berkas bukti yang diubah harus terdeteksi, lalu bersih-bersih).
  Dijalankan di `make e2e` pada data E2E dan dapat dijalankan pada stack nyata (`make restore-test`). Hasilnya
  dicatat di `docs/operations.md`.
- **Pemindai rahasia:** `tests/tools/secret_scan.py` memeriksa berkas yang dilacak git (atau jalur/log/stdin)
  untuk cookie sesi, header cookie, bearer/token akses, kunci privat/cloud, dump cookie JSON, dan nama berkas
  terlarang (`cookies*`, `storage_state*`, `*.har`, `*.pem`, `.env`). Temuan dicetak tanpa nilai. Baris contoh
  sengaja ditandai `secret-scan: allow`; nilai penampung diabaikan. Dijaga oleh 40 tes, mutasi, dan tes
  "repo ini bersih" yang berjalan di CI, plus `make secrets` dan hook pre-commit.

## Alasan

NFR-10 menuntut backup terpisah dan restore yang pernah benar-benar diuji. Backup yang tidak pernah
dipulihkan tidak membuktikan apa pun, dan restore yang tidak dibandingkan dengan sumber dapat diam-diam
kehilangan data. Pemindai rahasia menjaga aturan PRD bagian 13 (cookies/token tidak masuk repo atau log)
secara otomatis, bukan lewat ingatan.

## Batas yang diketahui

- Backup penuh setiap kali (tanpa inkremental); evidence yang besar membutuhkan strategi lain dari pengukuran pilot.
- Backup tidak dienkripsi; izin OS (700/600) dan perangkat yang dikontrol adalah satu-satunya perlindungan.
  Enkripsi at-rest ditunda sampai ada keputusan kunci dan pemulihannya.
- Tidak ada penjadwalan otomatis (cron/timer); jadwal ditetapkan operator.
- Pemindai berbasis pola: tidak menjamin menangkap semua format rahasia. Ia pagar tambahan di atas
  `.gitignore`, penyaring rahasia artefak (ADR 0011), dan `detect-private-key`.
- Retensi/penghapusan data: kerangka prosedur ada di `docs/operations.md`, angka durasi BELUM ditentukan.
