# Hasil validasi pilot (WP-4.3)

**STATUS: BELUM DILAKSANAKAN.** Pilot (WP-4.2) membutuhkan target nyata yang diperoleh secara sah, dasar izin
tertulis, dan penilai manusia; belum ada satu pun yang tersedia pada 2026-10-19. Dokumen ini adalah kerangka;
**tidak ada angka di bawah ini yang boleh diisi dari data sintetis**. Hasil atas data sintetis hanya menguji
alur (lihat `docs/synthetic-dataset-i2.md`).

## 1. Cakupan pilot
`[ISI setelah pilot]` investigasi, platform, jalur data, periode, jumlah target dan run, jumlah reinspection (minimal dua).

## 2. Kualitas pengambilan
`[ISI]` Keluaran `pilot_metrics`: teramati vs ditampilkan, paginasi tidak lengkap, kegagalan parser per platform, durasi, penyimpanan.

## 3. Kualitas klasifikasi
`[ISI]` Ukuran set anotasi, jumlah penilai, kesepakatan (kappa), precision/recall/F1 per kelas, matriks kebingungan,
analisis galat (sarkasme, parent bertingkat, bahasa informal Indonesia). Label PILOT, tanpa interval kepercayaan.

## 4. Graf dan indikator koordinasi
`[ISI]` Stabilitas komunitas antar-seed pada data nyata; apakah indikator CO menghasilkan terlalu banyak positif
palsu; parameter `AnalysisRun` yang dipakai (bukan ambang baku).

## 5. Preservasi dan operasi
`[ISI]` Hasil verifikasi hash, hasil uji restore terbaru, ukuran penyimpanan, kendala operasional.

## 6. Kegunaan antarmuka
`[ISI]` Temuan dari pemakaian petunjuk dalam aplikasi, label ketidakpastian, tab analisis.

## 7. Kelemahan nyata
`[ISI]` Apa adanya, tanpa mengubah baseline secara spekulatif.

## 8. Daftar perbaikan terprioritas
`[ISI]` Prioritas, dasar temuan, usulan; perubahan baseline hanya lewat keputusan tertulis.

## 9. Keputusan terbuka yang diperbarui
`[ISI]` Perbarui bagian 11 rencana implementasi dengan angka dan keputusan baru (mis. D-01 model NLP, retensi,
kapasitas penyimpanan, durasi penyapu). Desain laporan (FR-096) dibahas SETELAH hasil ini ada.
