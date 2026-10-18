# 0026 - Klasifikasi respons M2: baseline aturan, penilaian, tinjauan, dan harness evaluasi

- **Status:** diterima (implementasi WP-2.2 dan WP-2.2e; FR-050..FR-057, AT-08, AT-09, AT-10, AT-16). **D-01 (model/penyedia NLP) tetap terbuka.**
- **Tanggal:** 2026-10-18

## Konteks

M2 menilai tiap respons terhadap proposition dengan dimensi terpisah (stance isu, keselarasan dengan induk langsung,
sentimen, karakter RC-01..RC-10, fungsi naratif), memakai rantai induk nyata, dengan jejak peninjauan manusia.
PRD tidak menetapkan model NLP; rencana meminta baseline yang dapat diperiksa dan harness evaluasi lebih dulu.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Klasifier | Antarmuka murni `classify(ClassifierInput) -> Assessment`; implementasi pertama `RulesClassifier` (`m2-rules` v1), berbasis cue | Alur dan harness teruji tanpa memilih model; setiap keputusan punya `basis` (cue cocok, asal propagasi). |
| Pengetahuan | Seluruh cue (stance per proposition, setuju/tidak setuju, karakter, sentimen, `min_matches`) berupa **parameter eksplisit** AnalysisRun; tidak ada bawaan tersembunyi. `example_rules` hanya contoh yang harus disalin. | ADR 0024: tanpa ambang/daftar baku; tercatat di run (NFR-01). |
| Konteks | Rantai induk dibangun dari relasi `reply_to` nyata pada dataset beku; induk diambil dari run yang sama. Stance posting target dari versi konteks target yang DIBEKUKAN pada run. Induk tak terlacak -> `parent_unknown`, tidak ditebak. | AT-08; AT-07. |
| Stance | Cue proposition; tanpa cue, "setuju/tidak setuju" menurunkan stance dari stance induk langsung HANYA bila induk PRO/CONTRA. Selain itu `UNDETERMINED` (didorong), `NOT_RELEVANT` hanya untuk pengalih/promosi murni. | FR-056; aturan konteks PRD 11.2. |
| Dimensi terpisah | `target_alignment` dinilai terhadap induk langsung; karakter multi-label; `narrative_function` TIDAK diisi baseline (None). | FR-052, FR-053; tidak mengklaim yang belum dibuktikan. |
| RC-07 | Selalu `needs_human_review`. | Rencana WP-2.2 butir 7. |
| Penyimpanan | `ResponseAssessment` append-only (trigger). Mesin hanya menulis saat run `RUNNING`, hanya untuk metode `m2-*`, hanya untuk anggota dataset beku dan proposition investigasi yang sama. Baris ditulis dalam transaksi eksekusi: metode gagal -> tidak ada baris tersisa. | NFR-01; integritas di database. |
| Tinjauan manusia | Baris BARU `source=HUMAN` yang menggantikan (`supersedes`, satu penerus), dengan peninjau, alasan wajib, dimensi yang berubah (`basis.changed`), dan rujukan bukti terbawa. Hasil mesin tidak pernah ditimpa. Hanya pada run `COMPLETED`; hanya versi terbaru yang dapat ditinjau. | FR-055, AT-16. `AuditEvent` umum menunggu WP-2.8. |
| Harness | `intelligence/evaluation.py` (murni): kappa Cohen per dimensi dan per kode RC, precision/recall/F1 per kelas, macro/micro, matriks kebingungan, galat per tag, putusan adjudikasi wajib bila banyak penilai. Setiap laporan memuat peringatan PILOT dan peringatan ukuran (<50). | PRD 16.3: pilot, bukan klaim kualitas. |

## Hasil ukur (dataset sintetis, seed bawaan, 300 respons)

Baseline mencapai 100% stance, 100% alignment, dan 100% kecocokan himpunan karakter. **Ini bukan kualitas model**:
cue contoh ditulis dengan melihat templat dataset yang sama, jadi angka itu adalah *batas atas uji kewarasan alur*.
Nilai sebenarnya dari pengukuran ini adalah apa yang ditemukan harness sebelum cue disetel:

- Kunci jawaban sintetis memuat dua ketidakkonsistenan yang terlihat sebagai "galat klasifier": pesan kelompok
  terkoordinasi diberi RC-08 dan balasan "tautan populer" diberi stance PRO padahal teksnya tidak menyatakan sikap.
  Keduanya salah label pada kunci jawaban dan diperbaiki (RC-10 / UNDETERMINED).
- Cue contoh meleset pada "Apa bukti keterlibatannya?" (Lampiran A) dan pada varian informal "nggak mengerti apa-apa";
  cue ditambah. Contoh ini menunjukkan mengapa cakupan cue harus diuji pada data yang tidak dipakai menulisnya.
- Hasil awal sebelum perbaikan: stance 90,3% (NOT_RELEVANT F1 29,4%), RC-10 presisi 46,7%.

## Batas yang diketahui (diuji sebagai "tes batas"; bila berubah, tes memberi tahu)

- **Negasi cue tidak dipahami**: "Tidak benar bahwa perusahaan harus diaudit" dinilai PRO.
- **Sarkasme tanpa cue tidak terdeteksi** (jatuh ke UNDETERMINED/RC-10).
- Aturan hanya melihat teks; isi media (video/gambar) tidak dianalisis (AT-09: UNDETERMINED).
- Bahasa Indonesia informal (singkatan, campur bahasa) hanya tertangani lewat cue yang ditulis analis.
- Belum ada anotasi manusia nyata: harness siap memuat set pilot 50-100 respons dengan dua penilai, tetapi belum ada
  datanya. Kesepakatan antar-penilai belum pernah diukur pada data sungguhan.
- Konteks percakapan dimuat seluruhnya di memori per run (cukup untuk MVP; dataset sangat besar belum diukur).
- Satu proposition diproses terpisah dari proposition lain; belum ada penilaian lintas-proposition.
- Belum ada API/UI/otorisasi untuk menjalankan atau meninjau (WP-2.7); `AuditEvent` umum di WP-2.8.

## Pengujian

`tests/test_m2_rules.py` (38), `tests/test_m2_assessment.py` (29), `tests/test_m2_evaluation.py` (26). Mutasi:
`wp22_rules.py` 25/25 (klasifier + harness), `wp22_assessment.py` 15 tertangkap + 1 setara (versi lama ditinjau: ditolak
constraint unik dengan galat yang sama), `wp22_triggers.py` 11/11. Mutasi awal yang lolos memperlihatkan celah tes
(ambang `min_matches` untuk cue kontra, batas NOT_RELEVANT, penolakan oleh constraint lain alih-alih trigger) dan
ditutup. Menjalankan harness: `python -m intelligence.evaluation --synthetic` atau `--gold F --pred F`.
