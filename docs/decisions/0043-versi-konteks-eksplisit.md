# 0043 — Memilih versi konteks yang dibekukan pada analisis (A2)

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti sisa butir 3.4 pada `analisis-snr.txt`.

## Masalah

Analisis dari antarmuka (ADR 0041) selalu membekukan konteks isu dan konteks target TERBARU. Dokumen meminta
pemilihan dataset, proposition, versi konteks, dan parameter; versi konteks belum dapat dipilih, padahal analisis
harus kadang mengikuti konteks yang berlaku pada saat tertentu (AT-07: versi lama tidak ditimpa).

## Keputusan

- `POST analysis-runs` menerima `issue_context_version` (nomor versi; kosong = terbaru) dan `target_context_versions`
  (id target -> nomor versi, atau `null` = tanpa konteks; target yang tidak disebut memakai terbaru).
- Versi yang tidak ada ditolak (400), target di luar dataset ditolak, dan versi konteks isu ditolak untuk metode tanpa
  isu (indikator koordinasi). Tidak ada tebakan diam-diam.
- Bahan formulir memuat semua versi konteks isu dan target (terbaru dulu) serta target tiap dataset. Antarmuka menampilkan
  bagian "Versi konteks yang dibekukan": default versi terbaru, pilihan versi lama, dan "Tanpa konteks target"; pilihan
  selalu dikirim eksplisit (apa yang terlihat adalah apa yang dibekukan).
- Pilihan tercatat pada run (`issue_context_version`, `target_contexts`) dan pada audit `ANALYSIS_RUN`
  (`issue_context_version`, `target_context_versions`).

## Batas yang diketahui

- Konteks tetap hanya dipakai klasifier sebagai stance awal target dan metadata; teks catatan belum dibaca mesin
  (ADR 0041). Memilih versi lama mengubah stance awal yang dibekukan, bukan pemahaman teks.
- Analisis ulang tetap memakai konteks run asal atau konteks terbaru (`use_latest_context`); pemilihan versi eksplisit
  belum ada pada analisis ulang.
