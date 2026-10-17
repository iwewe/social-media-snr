# 0023 - Kecepatan verifikasi tanpa mengurangi ketelitian

- **Status:** diterima.
- **Tanggal:** 2026-10-17

## Konteks

Satu PR memakan puluhan menit hanya untuk verifikasi: `make ci` ~10 menit (tes backend 9 menit, serial), E2E ~5 menit,
mutasi 10-35 menit (skrip sekali pakai), dan CI GitHub ~4 menit yang ditunggu. Pengukuran: VM 4 vCPU idle 96% saat tes
(tes berjalan di satu inti), jadi hambatan utamanya serialisasi dan pengulangan, bukan kapasitas VM.

## Keputusan dan hasil ukur

| Perubahan | Sebelum | Sesudah |
|---|---|---|
| Tes backend paralel (`pytest-xdist -n auto`, DB per worker) | 542 s (1094 tes) | **181 s** (1093 tes), tanpa kegagalan |
| `make ci` (lint+typecheck bersamaan; backend, browser, frontend bersamaan) | ~10 menit | **224 s** |
| Alat mutasi baku `tests/tools/mutate.py` + spek tersimpan | skrip sekali pakai per WP | satu alat, diuji (15 tes), spek A3 dapat dijalankan ulang |
| Verifikasi bertingkat (`docs/verification.md`) | semua selalu penuh | tingkat 0-3 dengan syarat jelas |

Hasil mutasi spek otorisasi A3 (32 mutasi) lewat alat baru: lihat bagian "Hasil" di bawah.

## Mengapa ketelitian tidak turun

- CI GitHub tetap menjalankan seluruh tes pada tiap PR.
- Alat mutasi memperkeras aturan lama: baseline hijau wajib, pola yang tidak ditemukan adalah ERROR (bukan SKIP), keputusan
  dari kode keluar (bukan teks), pemulihan berkas diperiksa hash-nya. Semua kekeliruan manual sebelumnya (baseline merah
  yang tidak terdeteksi, SKIP diam-diam, salah baca keluaran) kini tidak mungkin terjadi diam-diam.
- Mutasi tetap wajib untuk kode kritis; yang dilonggarkan hanya mutasi pada tampilan murni.
- Tes baru harus terbukti dapat merah sebelum perbaikan (pelajaran A2).

## Risiko dan penanganannya

- **Tes yang saling bergantung** muncul sebagai kegagalan acak saat paralel. Suite penuh lulus bersih pada percobaan ini;
  CI (2 worker) dan `make ci` (4 worker) menjadi pemantau terus-menerus. Bila ada kegagalan sporadis, perlakukan sebagai bug tes.
- **Beban memori**: 4 worker + PostgreSQL + (bersamaan) Chromium pada VM 4 GB berjalan lancar saat diukur; bila I2 membawa
  dataset besar, naikkan RAM VM (keputusan operasional di luar kode).
- **`--reuse-db`** dapat menyembunyikan perubahan migrasi; karena itu hanya untuk alat mutasi dengan baseline `--create-db`.

## Hasil

Spek otorisasi A3 (32 mutasi) lewat alat slot, 3 slot paralel: **32 CAUGHT, 0 SURVIVED, 0 ERROR, 662 s**
(alat serial lama: 1019 s, 30 CAUGHT, 1 ERROR, 1 SURVIVED).

- Percepatan hanya sekitar 35%, bukan 3x: mutasi yang menyentuh basis data (membuat DB tes per slot) tetap 77-127 s.
- Dua temuan alat sebelumnya ditutup: pola revoke OWNER terakhir dikoreksi, dan tes deterministik kunci keanggotaan
  (`test_membership_changes_wait_for_the_investigation_lock`) kini menangkap mutasi "kunci investigasi dilepas".
