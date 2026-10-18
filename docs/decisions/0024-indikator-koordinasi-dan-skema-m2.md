# 0024. I2: definisi indikator koordinasi dan skema klasifikasi M2

Status: **Diterima** (pengguna menyetujui keempat keputusan, 2026-10-18). Belum ada kode. Dasar: PRD 6.5, 6.7, 11.2, 11.4, 11.5; rencana WP-2.0..2.6.

## Prinsip yang mengikat semua indikator

- Indikator = angka terhitung beserta bukti pendukung, bukan temuan dan bukan skor. Tidak ada agregasi menjadi satu nilai per akun (FR-079).
- Satu platform per AnalysisRun; tidak ada pencocokan lintas platform (FR-073, FR-081).
- Tidak ada ambang bawaan. Setiap parameter (jendela, ukuran minimum, baseline) wajib diisi eksplisit per AnalysisRun dan disimpan bersamanya.
- Data yang tidak diketahui (None) tidak dihitung sebagai nol: pasangan akun dengan cakupan tidak sebanding ditandai "tidak dapat dinilai".
- Setiap hasil membawa: bukti (id observasi), baseline, hipotesis alternatif, dan korelasi dengan indikator lain.

## Dasar data (DatasetVersion dan AnalysisRun, WP-2.1)

- `DatasetVersion` = daftar id observasi tak-berubah + hash daftar (dibekukan).
- `AnalysisRun` = DatasetVersion + versi konteks + parameter (JSON) + versi metode + platform. Keluaran deterministik harus identik saat diulang (NFR-01).

## Definisi indikator (usulan)

Unit: pasangan akun (a, b) pada satu platform. Hasil per pasangan: nilai, jumlah kejadian pendukung, bukti.

| Kode | Definisi | Parameter wajib | Catatan kesalahan tafsir |
|---|---|---|---|
| CO-01 Co-Response | Jumlah posting induk berbeda yang dibalas oleh a dan b, dinormalkan terhadap jumlah posting induk yang dibalas masing-masing (Jaccard). | min. jumlah induk bersama | Topik viral membuat banyak akun membalas induk yang sama secara organik. |
| CO-02 Temporal Synchronization | Jumlah pasangan balasan (a,b) pada induk yang sama dengan selisih waktu <= jendela W. Hanya waktu yang teramati; waktu None dilewati dan dihitung sebagai "tidak diketahui". | W, min. kejadian | Reaksi serentak pada peristiwa luar; ketelitian waktu platform berbeda-beda. |
| CO-03 Content Similarity | Kemiripan teks antar balasan a dan b (normalisasi huruf/URL/spasi; kemiripan n-gram karakter). Hanya teks yang tersimpan utuh. | n, metode, min. panjang | Salin-tempel organik, kutipan, jawaban pendek ("setuju") mirip secara wajar. |
| CO-04 Co-Amplification | Jumlah objek yang sama yang diamplifikasi (repost/quote) oleh a dan b dalam jendela W. Hanya relasi amplifikasi yang teramati. | W, min. kejadian | Daftar amplifikasi bisa tidak lengkap per platform (isu cakupan). |
| CO-05 Shared Narrative / URL | Tautan (setelah normalisasi) atau frasa naratif yang sama muncul pada balasan a dan b. Tautan dihitung berdasarkan domain+path, bukan pengaruh tautan. | cara normalisasi, min. kejadian | Tautan berita populer dibagikan banyak orang tanpa koordinasi. |
| CO-06 Repeated Participation | Jumlah target investigasi berbeda (satu platform) tempat a dan b sama-sama berpartisipasi. | min. jumlah target | Komunitas dengan minat sama selalu muncul bersama. |

## Baseline (keputusan D-07, usulan)

Permutasi dengan seed tetap pada dataset yang sama: (i) acak-ulang label akun pada balasan dalam satu induk, (ii) geser waktu dalam induk. Laporkan nilai teramati, sebaran baseline, dan persentil. Baseline adalah pembanding, bukan uji signifikansi dan bukan bukti.

## Hipotesis alternatif (wajib disertakan di setiap hasil)

Mobilisasi organik, efek peristiwa eksternal, penyalinan konten publik, bias sampling/cakupan. Indikator yang bersumber dari event yang sama ditandai berkorelasi, tidak dihitung sebagai bukti independen.

## Skema M2 (usulan)

`ResponseAssessment` (append-only, versi baru untuk koreksi): observasi, proposition, versi konteks, AnalysisRun, `issue_stance` (6 label), `target_alignment` (SUPPORT/OPPOSE/UNCLEAR terhadap induk langsung), `expression_sentiment` (nullable), `response_character` (multi-label RC-01..10), `narrative_function` (nullable, 6 fungsi kerja), `basis` (teks alasan + id observasi yang dipakai, termasuk rantai induk), `needs_human_review` (wajib benar untuk RC-07), `source` (MACHINE/HUMAN), `supersedes`.
- Klasifier awal berupa aturan sederhana yang dapat diperiksa; model NLP dipilih setelah harness evaluasi (D-01). Tidak ada klaim kualitas sebelum evaluasi.
- Konteks dibangun dari rantai induk nyata; UNDETERMINED sah dan didorong.

## Keputusan yang dibutuhkan dari pengguna

1. Setuju definisi enam indikator di atas sebagai titik awal eksplorasi? Adakah yang dihapus/diganti?
2. Baseline permutasi (i)+(ii) sebagai bawaan?
3. Urutan: WP-2.0 (dataset sintetis dengan kunci jawaban) -> WP-2.1 -> WP-2.2 -> WP-2.3/2.4 -> WP-2.5 -> WP-2.6 -> UI. Setuju?
4. Bahasa teks sintetis: Indonesia informal (rekomendasi saya), termasuk sarkasme dan "setuju" bertingkat.
