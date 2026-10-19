# SNR

Aplikasi investigasi media sosial berbasis target (on-demand, per platform). Nama kerja.

- Spesifikasi: [`prd-snr.md`](prd-snr.md)
- Rencana kerja: [`rencana-implementasi-snr.md`](rencana-implementasi-snr.md)
- Dokumentasi lain: [`docs/`](docs/README.md)

## Prasyarat pengembangan

Python 3.13 dan [`uv`](https://docs.astral.sh/uv/), Node 24, Docker + Compose, `make`, `pre-commit`.

## Perintah umum

```text
make help        daftar perintah
make install     pasang dependensi backend dan frontend
make ci          lint, typecheck, test, build (sama dengan CI)
make up          jalankan lingkungan Docker (butuh .env; salin dari .env.example)
make down        hentikan lingkungan (data di snr-data/ tetap ada)
make ps / logs   status dan log layanan
make test        test backend (di container, PostgreSQL) dan frontend (vitest)
make e2e         E2E browser pada database terpisah (butuh stack hidup)
make secrets     pindai berkas yang dilacak git untuk cookie/token/kunci
make backup / restore-test   backup lokal dan uji restore terencana (docs/operations.md)
make tls-check   uji HTTPS terisolasi; make demo / demo-down  demo dengan data sintetis
```

Setelah `make up`, antarmuka ada di `http://127.0.0.1:5173` (proxy ke API Django). Pada server jarak
jauh, buka lewat SSH tunnel: `ssh -L 5173:127.0.0.1:5173 <user>@<host>`. Buat akun dengan
`docker compose exec web python manage.py createsuperuser`.

Layanan Compose: `postgres`, `valkey`, `web` (127.0.0.1:8000), `worker-analysis`, `worker-browser`,
`scheduler` (celery beat; penyapu run basi), `frontend` (127.0.0.1:5173). Hanya `worker-browser` yang memasang `browser-profiles/`; web dan
worker analisis tidak dapat melihatnya. Port database dan Valkey tidak dibuka ke host.

Variabel environment wajib untuk menjalankan Django: `DJANGO_SECRET_KEY` (atau `DJANGO_DEBUG=1`
untuk dev lokal). Jangan pernah meng-commit `.env`, cookies, atau profil browser.

## Status (2026-10-19)

Status dipisah menjadi lima hal yang berbeda; satu tidak menggantikan yang lain.

| Aspek | Status | Rujukan |
|---|---|---|
| **Implementasi dan uji fungsional (data sintetis)** | I0, I1, I2 selesai; alur investigasi, inspeksi dan reinspection, preservasi berhash, klasifikasi respons, profil akun, jaringan, indikator koordinasi, temuan, dan audit teruji dengan data sintetis dan halaman simulasi. Semua terbukti dengan tes otomatis, E2E, dan uji mutasi. | `docs/mvp-acceptance.md`, `docs/decisions/` |
| **Kesiapan alur pengguna** | Pengguna dapat membuat investigasi, menjalankan pemeriksaan, meninjau klasifikasi, menelusuri bukti, dan mengelola temuan dari antarmuka. **Analisis (M2-M5) belum dapat dipicu dari antarmuka**: dijalankan operator lewat `manage.py run_analyses`. Catatan konteks target tersimpan dan berversi, tetapi teksnya belum dibaca klasifier (dukungan konteks parsial). | `docs/decisions/0031`, `0032`, `0026` |
| **Adapter platform** | X, Threads, TikTok, Instagram, Facebook: **seluruhnya nonaktif**; belum ada pengambilan data nyata. Keputusan organisasi: browser dengan sesi milik operator, dipicu manual. Tersedia: impor dataset yang sah, adapter simulasi, validasi URL per platform, dan impor sesi operator. Adapter dibuka satu per satu setelah rekaman halaman yang sah diuji. | `docs/adapters/` |
| **Validasi data nyata** | **Belum ada.** Pilot belum dilaksanakan; tidak ada klaim mutu klasifikasi atau indikator pada data nyata. Hasil sintetis hanya menguji alur. | `docs/pilot/` |
| **Operasional** | Backup, restore terukur, pemindai rahasia, HTTPS (overlay, CA lokal), riwayat akses bukti, dan pemeriksaan izin tersedia. Belum ada domain/sertifikat produksi, enkripsi backup, atau penjadwalan otomatis. | `docs/operations.md` |

Ditunda atau di luar cakupan saat ini: profil Level B dan Inspect Actor (ADR 0027), desain laporan (menunggu data
nyata), `narrative_function` oleh klasifier (hanya koreksi manusia). Keputusan yang masih terbuka: model NLP,
retensi, kapasitas dan perangkat backup, batas waktu job, desain laporan (`rencana-implementasi-snr.md` bagian 11).

Mencoba tanpa data nyata: `make demo` menyiapkan database terpisah berisi data sintetis lengkap dengan akun acak
(lihat `docs/mvp-acceptance.md`).
