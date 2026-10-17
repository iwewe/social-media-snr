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
```

Setelah `make up`, antarmuka ada di `http://127.0.0.1:5173` (proxy ke API Django). Pada server jarak
jauh, buka lewat SSH tunnel: `ssh -L 5173:127.0.0.1:5173 <user>@<host>`. Buat akun dengan
`docker compose exec web python manage.py createsuperuser`.

Layanan Compose: `postgres`, `valkey`, `web` (127.0.0.1:8000), `worker-analysis`, `worker-browser`,
`scheduler` (celery beat; penyapu run basi), `frontend` (127.0.0.1:5173). Hanya `worker-browser` yang memasang `browser-profiles/`; web dan
worker analisis tidak dapat melihatnya. Port database dan Valkey tidak dibuka ke host.

Variabel environment wajib untuk menjalankan Django: `DJANGO_SECRET_KEY` (atau `DJANGO_DEBUG=1`
untuk dev lokal). Jangan pernah meng-commit `.env`, cookies, atau profil browser.

## Status

I0 (Repository Bootstrap) selesai (WP-0.1 sampai WP-0.6). Berikutnya I1: inspeksi, preservasi, dan reinspection; lihat `rencana-implementasi-snr.md`.
