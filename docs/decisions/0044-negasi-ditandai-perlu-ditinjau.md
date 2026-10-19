# 0044 — Negasi dekat cue stance ditandai "perlu tinjauan manusia" (A3)

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti butir negasi pada `analisis-snr.txt`.

## Masalah

Klasifier aturan M2 mencocokkan cue pada teks. "Tidak benar bahwa perusahaan harus diaudit" cocok dengan cue PRO
"harus diaudit" sehingga dibaca PRO, padahal maksudnya kebalikan. Memahami negasi secara umum tidak mungkin dengan
aturan sederhana, dan menebak membalik stance berisiko lebih buruk daripada salah yang tampak.

## Keputusan

- Dua parameter M2 OPSIONAL, harus bersama-sama: `negation_cues` (daftar kata) dan `negation_window` (bilangan bulat
  1..10 kata). Tanpa keduanya perilaku identik dengan sebelumnya, sehingga run lama dan `reanalyze` tetap valid dan
  versi metode tetap "1".
- Bila ada kata negasi (kata utuh) dalam `negation_window` kata SEBELUM kecocokan cue pro/kontra/setuju/tidak setuju,
  respons ditandai `needs_human_review`, rule `review:negation_near_stance_cue` dicatat, dan `basis.matched.negation`
  memuat cue, kelasnya, dan kata negasinya.
- Stance TIDAK diubah. Mesin hanya mencegah hasil yang mungkin terbalik tampil seolah pasti.
- Negasi di dalam cue itu sendiri ("tidak perlu diaudit") tidak dihitung: cue memang ditulis analis dengan negasinya.
- `example_parameters` (dipakai peluncuran dari antarmuka) menyertakan kata negasi bahasa Indonesia dan jendela 5.
- Antarmuka menampilkan badge "Perlu tinjauan manusia" dan satu baris penjelasan negasi.

## Batas yang diakui

Penanda berbasis kedekatan, bukan pemahaman: dapat menandai berlebihan (negasi yang tak terkait) dan dapat
terlewat (negasi di luar jendela, ironi, negasi ganda). Hasil tetap perlu ditinjau manusia; tidak ada klaim akurasi.
