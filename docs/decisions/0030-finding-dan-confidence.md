# 0030 - Finding, evaluasi kualitas bukti, dan analytical confidence (M5)

- **Status:** diterima (implementasi WP-2.6; FR-077, FR-078, FR-079, FR-080; NFR-09; AT-15, AT-16). Menutup rantai I2: indikator -> tinjauan manusia -> temuan.
- **Tanggal:** 2026-10-18

## Konteks

Hasil indikator dan klasifikasi hanyalah bahan. PRD meminta temuan baru lahir setelah peninjauan manusia yang menimbang hipotesis alternatif; kualitas bukti
dinilai pada empat sumbu terpisah; confidence disertai alasan dan boleh `NOT_ASSESSABLE`; tidak ada skor buzzer atau vonis operasi berbayar; dan temuan dapat
digantikan tanpa menghilangkan sejarah.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Finding | Isi **tersegel** (tidak dapat diubah/dihapus; trigger). Tertaut ke satu atau lebih `AnalysisRun` selesai (satu investigasi, satu platform), observasi anggota dataset run itu, dan indikator dari run itu. Memuat pernyataan pola, interpretasi, confidence + alasan, empat sumbu bukti, pertimbangan alternatif, jumlah kelompok bukti independen, penanda data sintetis, dan catatan bukan-vonis. | FR-080. |
| Siklus hidup | `FindingReview` append-only: `ENDORSE` dan/atau `WITHDRAW` (satu per jenis). Status diturunkan: DRAFT -> ENDORSED -> (WITHDRAWN atau SUPERSEDED). | Isi tak berubah; keputusan manusia tercatat dengan pelaku dan catatan. |
| Pengesahan | Trigger menolak `ENDORSE` kecuali **keempat** hipotesis alternatif (mobilisasi organik, peristiwa eksternal, salin konten publik, bias cakupan) sudah dinilai (hasil sah + alasan), temuan belum ditarik, dan belum digantikan penerus yang disahkan. Draft dengan alternatif belum lengkap boleh dibuat, tetapi plafon confidence-nya LOW dan tak dapat disahkan; perbaikannya lewat revisi. | FR-077 dan rencana WP-2.6 butir 6, ditegakkan di database. |
| Empat sumbu bukti | `integrity`, `provenance`, `completeness`, `relevance`: level (`GOOD`/`ACCEPTABLE`/`POOR`/`NOT_ASSESSABLE`) + alasan wajib, disertai **saran sistem** dari fakta: integrity <- hasil verifikasi hash TERAKHIR tiap artefak run terkait (WP-1.10; hash bukan bukti keaslian); completeness <- metadata cakupan run (outcome, paginasi, keterbatasan); provenance <- metode sumber (sintetis/impor/lain); relevance hanya manusia. Penilaian lebih baik daripada saran (yang pasti) wajib `override_reason`. | FR-078. |
| Plafon confidence | Kebijakan eksplisit, bukan probabilitas: sumbu bukti POOR/NOT_ASSESSABLE -> maks LOW; alternatif belum dinilai/tak dapat dinilai -> maks LOW, belum disingkirkan -> maks MODERATE; bukti independen < 2 kelompok -> maks MODERATE; **data sintetis -> maks LOW**. `NOT_ASSESSABLE` selalu diizinkan. HIGH hanya bila semua syarat terpenuhi. Pelanggaran ditolak dengan alasannya. | NFR-09: tidak ada kesimpulan paksa; PRD 11.5: indikator dari peristiwa sama bukan bukti independen. |
| Bukti independen | Dari `pair_summary` jaringan koordinasi (ADR 0029); untuk beberapa pasangan dipakai jumlah TERKECIL (konservatif); tanpa indikator = tidak diketahui (maks MODERATE). | PRD 11.5. |
| Larangan vonis | Layanan menolak istilah vonis (buzzer, akun bayaran, operasi berbayar, aktor pengendali, pasukan siber, troll, botnet, dll., cocok pada kata utuh) pada judul, pernyataan, interpretasi, dan alasan confidence. Teks alternatif boleh membahasnya sebagai hal yang dinilai. Daftar istilah ada di berkas data `m5/verdict_terms.txt`, bukan di kode: pemindai arsitektur melarang identifier bertema vonis di kode, dan daftar penolak sengaja tidak dilonggarkan lewat pengecualian. Tidak ada kolom skor/vonis/probabilitas; tes menjaga nama. | FR-079. |
| Supersession | `revise_finding` membuat temuan baru dengan `supersedes` (satu penerus, trigger); yang lama tetap utuh, tertaut ke AnalysisRun lamanya. Lama berstatus SUPERSEDED hanya setelah penerus DISAHKAN. `current_findings` hanya yang berlaku. | FR-080, AT-15. |
| Empat tingkat hasil | `MODEL_TIERS` mengklasifikasikan setiap model: observasi/artefak (1), penilaian M2 (2), profil/graf/indikator (3), Finding (4); model infrastruktur ditandai eksplisit tanpa tingkat. Tes memastikan model baru di `intelligence` wajib diklasifikasikan. | PRD 11.5. |

## Batas yang diketahui

- Plafon confidence adalah **kebijakan analitik** yang kami tetapkan (bukan ambang kebenaran); angka dua kelompok bukti independen adalah pilihan konservatif, bukan hasil kalibrasi.
- Sumbu `relevance` tidak punya fakta sistem; kualitas penilaiannya bergantung pada peninjau.
- Saran `provenance` hanya membedakan sintetis/impor/lain; legalitas dan keabsahan sumber diverifikasi di luar kode (PRD 13).
- Larangan vonis berbasis daftar kata: tidak menangkap parafrase yang menyiratkan vonis. Daftar dapat diperluas; tinjauan manusia tetap yang utama.
- Peninjau dan pembuat dapat orang yang sama (kerja sendiri sebagai super admin); belum ada aturan "dua mata" atau pemeriksaan peran (WP-2.7); `AuditEvent` umum di WP-2.8.
- Belum ada API/UI; DB tidak menegakkan plafon confidence (hanya layanan) dan tidak dapat menegakkan "minimal satu tautan" selain saat penyegelan.
- Temuan berbasis profil (M3) atau klasifikasi (M2) tanpa indikator belum punya jalur khusus; saat ini tertaut lewat observasi dan AnalysisRun.

## Pengujian

`tests/test_m5_policy.py` (63, murni: larangan vonis, plafon confidence, saran sumbu bukti, validasi penilaian, empat tingkat) dan `tests/test_findings.py`
(61: evaluasi bukti dari verifikasi hash dan metadata cakupan, pembuatan dan validasi temuan, plafon di layanan, alur DRAFT -> ENDORSED -> WITHDRAWN,
supersession AT-15 dengan data lama utuh, klasifikasi tingkat hasil, dan penjaga database untuk penyegelan, tautan, dan pengesahan). Mutasi: `wp26_policy.py` 36/36,
`wp26_run.py` 24 tertangkap + 3 setara terdokumentasi (pelindung berlapis yang menghasilkan galat dan pesan yang sama dengan batasan di database),
`wp26_triggers.py` 22 tertangkap + 2 setara (pemeriksaan redundan; `AFTER DELETE` yang melempar galat).

Mutasi awal menemukan celah tes yang serupa dengan WP sebelumnya dan ditutup: kasus penolakan yang sebenarnya dilakukan penjaga lain (batasan unik,
pemeriksaan lain pada kondisi gabungan) alih-alih penjaga yang dimaksud (penerus lintas investigasi/platform/predesesor belum tersegel, tautan pada temuan
tersegel, pengesahan setelah penarikan, tiga bentuk alternatif tak lengkap pada tingkat database), serta pemilihan kelompok bukti terkecil, temuan tanpa indikator,
penyimpanan `override_reason`, dan platform campur.
