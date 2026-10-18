# 0037 — Persiapan pilot (WP-4.1)

Status: diterima. Tanggal: 2026-10-19.

## Keputusan

- **Protokol pilot** (`docs/pilot/protokol-pilot.md`): daftar periksa cakupan, dasar izin dan retensi sementara,
  prosedur set anotasi, metrik, dan aturan pilot. Bagian yang menyangkut keputusan organisasi bertanda `[ISI]`;
  tim developer tidak mengisinya. Tidak ada "target lulus" (PRD tidak menetapkannya).
- **Alat set anotasi** (`manage.py pilot_annotation_set`): dari satu run M2, mengambil sampel bergilir antar kategori
  mesin (acak berbenih wajib, dapat diulang), menulis `sheet.json` untuk penilai TANPA label mesin, `predictions.json`
  berisi label mesin yang asli (hasil koreksi manusia tidak dipakai), dan `manifest.json` (benih, ukuran, penanda
  bila di bawah 50 item, strata). Tag otomatis hanya untuk konteks (nested, parent_unknown, no_parent,
  machine_flagged, short_or_missing_text); tag kualitatif (sarkasme, informal) ditambah penilai. Keluaran berizin
  700/600 dan `pilot-data/` diabaikan Git: teks pihak ketiga diperlakukan setara bukti. Format lembar yang sudah diisi
  langsung dibaca harness evaluasi yang ada (`python -m intelligence.evaluation`).
- **Metrik pilot** (`manage.py pilot_metrics`): kelengkapan (teramati vs ditampilkan), paginasi tidak lengkap,
  kegagalan parser dan keadaan tidak didukung per platform, hasil run, durasi, penyimpanan; tanpa ambang.
- **Kerangka hasil** (`docs/pilot/hasil-validasi.md`) berstatus **BELUM DILAKSANAKAN** dan melarang pengisian dari data sintetis.

## Alasan

Rencana WP-4.1 meminta set anotasi dan metrik yang siap sebelum pilot. Alat ini membuat anotasi tidak bias oleh
label mesin, dapat diulang, dan langsung terhubung ke harness yang sudah diuji, sehingga pilot menghabiskan waktu
untuk menilai, bukan menyiapkan skrip.

## Batas yang diketahui

- **WP-4.2 (pelaksanaan) dan WP-4.3 (hasil) belum dapat dikerjakan**: membutuhkan target nyata yang sah, izin
  tertulis, dan penilai manusia yang berada di luar kode dan di luar kewenangan tim developer. Hasil validasi tidak
  boleh dipalsukan dari data sintetis.
- Pengambilan contoh bergilir menurut stance mesin memberi keragaman tetapi bukan sampel acak murni; jangan memakainya
  untuk memperkirakan prevalensi kelas.
- Satu penilai tidak memberi kesepakatan antar-penilai; protokol mencatatnya sebagai keterbatasan.
