# 0041 — Menjalankan analisis dari antarmuka (WP-2.9)

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti temuan 3.3 dan 3.4 pada `analisis-snr.txt`.

## Masalah

Analisis M2-M5 hanya dapat dibuat lewat `manage.py run_analyses` (alat operator, sinkron, `--exploratory`). Analis
bergantung pada operator terminal untuk beralih dari inspeksi ke analisis dan untuk analisis ulang (alur A langkah 8,
alur B langkah 7, FR-041). Selain itu catatan konteks target belum dibaca klasifier, tetapi antarmuka tidak
menyatakannya.

## Keputusan

- **API:** `GET investigations/{id}/analysis-setup/` (Pembaca; dataset, pemeriksaan yang boleh dibekukan, proposition,
  run M2 selesai, contoh eksplorasi, catatan), `POST investigations/{id}/datasets/` (Anggota; bekukan observasi dari
  pemeriksaan terpilih, satu platform), `POST investigations/{id}/analysis-runs/` (Anggota; mulai analisis),
  `POST analysis-runs/{id}/reanalyze/` (Anggota; analisis ulang pada data terbaru, `use_latest_context` opsional;
  tanpa observasi baru: 409 `nothing_new`). Daftar run kini memuat `error`.
- **Parameter selalu eksplisit** (ADR 0024): setiap metode menerima himpunan field yang TEPAT; field hilang atau
  tambahan ditolak (400) dan tidak ada nilai bawaan tersembunyi. M2: cue pro/kontra ditulis analis (dipangkas,
  deduplikasi, minimal satu). M3/M4: run M2 sumber harus selesai dan memakai dataset yang sama; stance view M4 butuh
  proposition DAN run M2. Indikator koordinasi: seluruh parameter. Nilai contoh hanya diisi lewat tombol "Isi contoh
  eksplorasi" dan tetap dikirim eksplisit; moduler `intelligence/examples.py` dipakai bersama `run_analyses`.
- **Dijalankan worker, bukan proses web:** run dibuat PENDING bersama catatan audit dalam satu transaksi, dikirim ke
  antrean `analysis` setelah commit; tugas `snr.execute_analysis` memanggil `execute_run` (klaim atomik: tugas ganda
  aman). Antrean yang tak tersedia menandai run FAILED (tidak menggantung PENDING). Status PENDING/RUNNING/COMPLETED/
  FAILED dan galat tampil di antarmuka dan diperbarui otomatis (polling 3 detik hanya selama ada analisis berjalan).
- **Audit:** aksi baru `ANALYSIS_RUN` mencatat pelaku, metode, versi, nomor dataset, dan digest parameter (dan run
  asal pada analisis ulang). Semua run lama dan dataset lama tetap utuh.
- **Antarmuka:** tab "Jalankan analisis" (dataset, pembuatan dataset, formulir per metode, daftar status, analisis ulang).
  Pembaca hanya melihat daftar.
- **Batas konteks dinyatakan:** teks catatan konteks target tersimpan dan berversi tetapi belum dibaca klasifier; yang
  dipakai stance awal target, cue analis, dan rantai balasan. Pernyataan ada pada formulir, teks bantuan respons
  terklasifikasi, dan bahan formulir API; mengubah penjelasan konteks saja tidak mengubah klasifikasi.

## Alasan

Analis harus dapat melanjutkan dari inspeksi ke analisis tanpa terminal, tetapi tanpa mengorbankan prinsip bahwa
setiap angka berasal dari parameter yang dinyatakan eksplisit dan dicatat. Menjalankan di worker menjaga proses web tetap
responsif dan konsisten dengan inspeksi.

## Batas yang diketahui

- Nilai contoh tetap contoh, bukan konfigurasi yang telah dievaluasi (pilot belum dilaksanakan).
- Cue M2 hanya untuk stance proposition; daftar setuju/tidak setuju dan karakter respons memakai daftar dasar modul
  (belum dapat disunting dari antarmuka). Baseline belum memahami negasi umum dan tidak mengisi narrative function.
- Tidak ada pembatalan analisis yang sedang berjalan dan tidak ada batas waktu eksekusi bawaan (menunggu pengukuran, D-06).
- Antrean/worker harus berjalan; bila tidak, run ditandai FAILED dengan pesan, dan pengguna harus mengirim ulang manual.
