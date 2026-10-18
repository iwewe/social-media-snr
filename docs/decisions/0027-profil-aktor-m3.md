# 0027 - Profil aktor M3 Level A: tujuh dimensi, cakupan wajib, perbandingan tanpa skor

- **Status:** diterima (implementasi WP-2.3; FR-060..FR-065, AT-17). **Level B ditunda** (lihat di bawah).
- **Tanggal:** 2026-10-18

## Konteks

M3 merangkum perilaku **akun pada satu platform** pada isu yang diteliti. PRD melarang menjadikannya label kepribadian,
identitas orang, klasifikasi buzzer permanen, atau klaim seluruh riwayat akun, dan mewajibkan pernyataan cakupan.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Level | Hanya **Level A**: respons teramati pada target investigasi, dari penilaian M2 yang berlaku. Level B (inspeksi tambahan, FR-061) tidak diimplementasikan; kolom `level` dikunci `A` (check constraint). | Level B membutuhkan pengumpulan baru dan keputusan izin platform (WP-3.0); keputusan pengguna 2026-10-18. |
| Sumber | Metode `m3-profile` v1 pada AnalysisRun, membaca satu run M2 SELESAI pada dataset beku yang sama. Hasil tinjauan manusia menggantikan hasil mesin. | Rantai ADR 0025/0026; profil tidak membaca data baru. |
| Keterulangan | Parameter memuat `assessments_digest` (hash himpunan penilaian berlaku). Bila himpunan berubah (mis. tinjauan baru) sebelum run dieksekusi, run `FAILED` dengan pesan jelas dan harus dibuat ulang. | NFR-01: keluaran identik untuk masukan sama; tinjauan baru tidak diam-diam mengubah run lama. |
| Parameter | Semua ambang eksplisit dan wajib: `min_responses`, `bucket_hours`, `min_active_buckets`, `narrative_min_texts`, periode (dengan zona waktu), proposition. Tanpa nilai bawaan. | ADR 0024. |
| Tujuh dimensi | participation, stance_distribution, response_character, temporal_activity, target_concentration, narrative_consistency, activity_evolution. | PRD 11.3. |
| Data kurang | Dimensi bernilai `INSUFFICIENT_DATA` dengan alasan, jumlah teramati, dan minimum; **tidak pernah nol**, dan tanpa angka distribusi. `participation` (fakta hitungan) selalu ada. | Rencana WP-2.3 butir 2. |
| Konsentrasi target | `INSUFFICIENT_DATA` bila dataset hanya memuat satu target. | Konsentrasi tak bermakna. |
| Narasi | Hanya repetisi teks tersedia (normalisasi sama dengan M2); isi teks tidak disalin; tidak menyimpulkan tujuan atau koordinasi. | PRD: "narrative consistency dalam teks yang tersedia". |
| Evolusi | Hitungan stance per bucket waktu; tanpa kunci tren/kemiringan. | Deskriptif, bukan klaim perubahan sikap. |
| Cakupan | `coverage` WAJIB (trigger menolak tanpa `statement` dan `targets_covered`): level, platform, sumber, versi dataset, run M2 sumber, periode, target tercakup vs target investigasi, `partial_coverage`, pemeriksaan tidak lengkap (status), respons tanpa waktu, respons di luar periode, respons tanpa akun, dan kalimat pernyataan ("bukan seluruh aktivitas akun, bukan identitas orang, bukan klasifikasi permanen"). | FR-063, AT-17. |
| Perbandingan | `compare_profiles(a, b)` murni: menolak lintas platform; memberi peringatan untuk cakupan target/periode/dataset/proposition berbeda, cakupan sebagian, pemeriksaan tak lengkap, waktu tak diketahui, dan dimensi berdata kurang (tidak dibandingkan). Keluaran hanya `comparable`, `warnings`, dan berdampingan; tanpa skor atau peringkat. | FR-064, FR-065. |
| Penyimpanan | `ActorIssueProfile` append-only (trigger); hanya ditulis saat run M3 `RUNNING`; akun harus sama platform dengan dataset; sumber harus run M2 selesai pada dataset yang sama; proposition satu investigasi; satu profil per (run, akun). Penulisan atomik dengan eksekusi (gagal -> tak ada baris). | Integritas di database (pola ADR 0025/0026). |
| Penjaga nama (FR-065) | Tes memindai AST paket `m3`, kunci dimensi/profil tersimpan, dan nama kolom model: tidak boleh memuat buzzer, score/skor, rank/peringkat, personality/kepribadian, verdict/vonis, dan sejenisnya. | FR-065. |

## Batas yang diketahui

- **Level B belum ada** (alur C/FR-061); profil hanya sebanyak data target yang diperiksa. Karena itu `partial_coverage` sering
  benar pada investigasi nyata dan peringatan perbandingan akan sering muncul; itu memang tujuannya.
- Akun dengan identitas belum terverifikasi (tanpa ID sumber) tidak diprofilkan; jumlahnya dilaporkan di cakupan.
- Waktu publikasi tidak diketahui tidak dapat ditempatkan pada bucket; dilaporkan, tidak ditebak.
- Profil bergantung pada kualitas M2 (baseline berbasis aturan, ADR 0026); kesalahan klasifikasi merambat. Tidak ada propagasi
  ketidakpastian numerik.
- Bucket waktu tetap (UTC) sejak awal periode; belum ada pola harian/jam-dalam-hari.
- Belum ada API/UI/otorisasi (WP-2.7); `AuditEvent` umum menunggu WP-2.8; eksekusi masih sinkron.
- Jumlah dan ambang pada contoh tes bukan rekomendasi nilai untuk data nyata.

## Pengujian

`tests/test_m3_profile.py` (29; dimensi murni, perbandingan, penjaga nama) dan `tests/test_m3_run.py` (38; ujung ke
ujung, AT-17, tinjauan M2 vs hash, validasi, penjaga database). Mutasi: `wp23_profile.py` 23/23, `wp23_run.py` 15/15,
`wp23_triggers.py` 13 tertangkap + 1 setara (kondisi "bukan objek" redundan dengan syarat `targets_covered`). Mutasi awal yang
lolos menunjukkan tiga celah tes (ambang konsentrasi target, jumlah induk, validasi sumber) dan tujuh kasus penolakan yang
ternyata dilakukan penjaga lain (constraint unik, status) alih-alih trigger yang dimaksud; semuanya ditutup.
