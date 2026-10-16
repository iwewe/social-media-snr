# 0001 - Tooling baseline repository

- **Status:** diterima (usulan implementasi WP-0.1, dapat direvisi setelah dipakai)
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 19 menetapkan baseline: Django Authentication, PostgreSQL, Playwright, Celery/Valkey,
NetworkX, React/Cytoscape.js. PRD tidak menetapkan manajer paket, linter, atau versi bahasa.
Rencana implementasi WP-0.1 mengusulkan `uv`, `ruff`, `mypy`, dan `eslint`/`prettier`.

## Keputusan

| Area | Pilihan | Catatan |
|---|---|---|
| Python | 3.13 (via `uv`) | 3.14 tidak dipakai karena dukungan Django/Celery/Playwright belum diverifikasi. |
| Manajer paket Python | `uv` dengan `uv.lock` | Instalasi CI memakai `--locked`. |
| Django | 5.2 (seri LTS) | Dibatasi `<6`. |
| Lint/format Python | `ruff` | Aturan: E, F, W, I, B, UP, DJ, S. |
| Type-check Python | `mypy` + `django-stubs` | |
| Test | `pytest` + `pytest-django` + `pytest-env` | Test berada di `tests/` (root repo). |
| Node | 24 LTS | |
| Frontend | React + TypeScript + Vite | |
| Lint frontend | `oxlint` | **Berbeda dari rencana**: template Vite terbaru memakai `oxlint`, bukan ESLint. Fungsi setara untuk kebutuhan WP-0.1. |
| Format frontend | `prettier` | |

## Alasan dan konsekuensi

- Versi dikunci lewat lockfile sehingga lingkungan dapat direproduksi.
- Belum ada pembuktian bahwa seluruh dependensi baseline (Playwright, Celery) berjalan baik pada
  Python 3.13; itu diverifikasi pada WP-0.2 dan WP-1.8.
- Jika `oxlint` terbukti kurang memadai, ganti ke ESLint dengan mencatat keputusan baru.
