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
```

Variabel environment wajib untuk menjalankan Django: `DJANGO_SECRET_KEY` (atau `DJANGO_DEBUG=1`
untuk dev lokal). Jangan pernah meng-commit `.env`, cookies, atau profil browser.

## Status

I0 (Repository Bootstrap) sedang dikerjakan. Lihat rencana untuk paket kerja (WP-0.1 sampai WP-0.6).
