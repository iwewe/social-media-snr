# 0035 — HTTPS, riwayat akses bukti, dan izin berkas (WP-3.6b)

Status: diterima. Tanggal: 2026-10-19.

## Keputusan

- **HTTPS lewat proxy Caddy** (`compose.tls.yaml`, `deployment/Caddyfile`): TLS diakhiri proxy, HTTP otomatis
  dialihkan ke HTTPS, frontend dilayani sebagai berkas statis hasil build dengan CSP ketat
  (`default-src 'self'`, tanpa skrip inline), API dan admin diteruskan ke aplikasi. Sertifikat: CA lokal Caddy
  (`SNR_TLS=internal`, bawaan, tanpa domain publik) atau sertifikat sendiri (`SNR_TLS=/certs/cert.pem /certs/key.pem`).
  Port diikat ke `127.0.0.1` kecuali `SNR_BIND_ADDR` diubah (keputusan operator). Frontend dev (vite) hanya dengan `--profile dev`.
- **Aplikasi memakai gunicorn** (bukan `runserver`) pada overlay ini; dependensi `gunicorn` ditambahkan.
- **Pengaturan Django aktif hanya dengan `SNR_HTTPS=1`:** cookie sesi dan CSRF `Secure`, kepercayaan pada
  `X-Forwarded-Proto` dari proxy, HSTS (`SNR_HSTS_SECONDS`, nilai awal usulan 3600; naikkan bertahap setelah
  HTTPS terbukti stabil). Salah konfigurasi menghentikan startup: `DJANGO_DEBUG=1` bersama HTTPS, atau
  `DJANGO_ALLOWED_HOSTS` kosong/berisi `*`. `check --deploy` bersih (diuji); tiga peringatan dibungkam
  sengaja: pengalihan SSL di Django (W008; proxy yang mengalihkan), subdomain HSTS (W005) dan preload HSTS (W021)
  karena domain belum ditetapkan dan preload hampir tidak dapat dibatalkan.
- **Riwayat akses bukti:** `GET /api/investigations/{id}/evidence-access/` (Pembaca ke atas) menampilkan siapa
  mengunduh/memverifikasi artefak, kapan, untuk apa, dan hasilnya. Sumbernya `ArtifactVerification` yang
  sudah append-only dan sudah ditulis oleh setiap unduhan dan verifikasi (WP-1.10), jadi tidak ada penyimpanan
  ganda. Jalur berkas dan hash tidak ditampilkan. UI: tab "Akses bukti".
- **Pemeriksaan izin berkas** (`manage.py check_data_permissions [--backup-dir D]`): evidence tertutup bagi
  "other" dan berkasnya read-only; browser-profiles dan backup hanya untuk pemilik; symlink tidak diperbolehkan.
  Hanya melaporkan, tidak mengubah izin.
- **Uji HTTPS terisolasi:** `deployment/tls_check.sh` (`make tls-check`) menyalakan tumpukan sementara dengan
  overlay (proyek compose, data, dan port sendiri) lalu memeriksa pengalihan, CSP, HSTS, cookie Secure/HttpOnly,
  aset dan static, `check --deploy`, serta alur browser (login dan buat investigasi) di balik CSP.

## Alasan

PRD bagian 13 meminta pengerasan sebelum data nyata masuk: lalu lintas terenkripsi, cookie tidak bocor lewat
HTTP, akses bukti dapat ditelusuri, dan berkas sensitif tidak terbuka bagi pengguna OS lain. Memakai catatan
verifikasi yang sudah ada menghindari dua sumber kebenaran untuk akses bukti.

## Batas yang diketahui

- Tidak ada domain atau sertifikat produksi; CA lokal Caddy tidak dipercaya peramban sampai CA-nya diimpor.
- Yang tercatat sebagai akses bukti hanyalah unduhan dan verifikasi. Melihat daftar observasi atau metadata
  artefak tidak dicatat (bukan isi bukti).
- CSP diuji pada alur login/investigasi; halaman analisis (graf Cytoscape) belum diuji di balik CSP.
- Rate limiting dan WAF di level proxy belum ada (pembatasan login oleh django-axes tetap berlaku).
- Rotasi kunci dan manajemen rahasia produksi (selain `.env` lokal) belum dirancang.
