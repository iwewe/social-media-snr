# 0029 - Indikator koordinasi CO-01..CO-06 dan baseline permutasi

- **Status:** diterima (implementasi WP-2.5; FR-072, FR-075, FR-076, FR-077; AT-11, AT-12, AT-13). Mengimplementasikan definisi ADR 0024. Hasilnya **indikator, bukan temuan**; temuan menunggu WP-2.6.
- **Tanggal:** 2026-10-18

## Konteks

PRD meminta indikasi koordinasi yang dilaporkan terpisah dari interaksi langsung, tanpa ambang baku, tanpa skor per akun, dengan baseline
dan hipotesis alternatif, dan tidak boleh dipicu oleh kesamaan stance atau intensitas saja.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Representasi | `CoordinationNetwork` + `CoordinationEdge`: tabel dan model terpisah dari graf interaksi. Satu tepi = satu indikator untuk satu pasangan akun (a < b) dengan nilai, dukungan, bukti, penjelasan. | FR-072: dibedakan dari interaksi. |
| Satu platform | Trigger: jaringan hanya pada run `co-` RUNNING dengan platform sama dengan dataset; kedua akun tepi harus berplatform sama; append-only. | AT-13, NFR-06. |
| Unit respons | Satu **Post** = satu respons, diwakili observasi terbarunya pada dataset. | Pemeriksaan berulang atas objek yang sama tidak menggandakan hitungan. |
| Tanpa stance | Indikator tidak membaca M2/stance sama sekali; parameter tak memuat `source_run`. | FR-075, AT-11. |
| Parameter | 18 parameter eksplisit di AnalysisRun (jendela waktu, ambang minimum tiap indikator, n-gram dan ambang kemiripan, frasa, permutasi, seed, batas bukti, batas ukuran); tanpa bawaan. | ADR 0024. |
| CO-01 | Jaccard atas himpunan posting induk yang dibalas; dukungan = jumlah induk bersama. | ADR 0024. |
| CO-02 | Jumlah induk tempat dua akun membalas dalam jendela W detik (waktu tak diketahui dikecualikan dan dihitung). | idem |
| CO-03 | Kemiripan Jaccard n-gram karakter pada teks ternormalisasi; nilai = kemiripan tertinggi, dukungan = jumlah pasangan respons mirip. Dilewati terlihat bila respons > `similarity_max_responses`. | idem |
| CO-04 | Jumlah objek yang di-repost/dikutip kedua akun dalam jendela waktu. | idem |
| CO-05 | Varian `url` (domain+path, tanpa skema/www/query/fragmen) dan `phrase` (frasa k kata sama; tautan tidak dihitung sebagai frasa). Dukungan = jumlah **pasangan respons** yang berbagi token (pengulangan terlihat; jumlah token berbeda tersimpan di detail). | Jumlah token berbeda tidak membedakan satu tautan yang dibagikan berulang. |
| CO-06 | Jumlah target berbeda tempat kedua akun sama-sama merespons. | idem |
| Baseline | Permutasi label akun antar respons (jumlah respons tiap akun tetap), `permutations` kali dengan seed tetap; peristiwa pasangan-respons tidak berubah. Pembanding = **maksimum antar-pasangan** per indikator (kendali atas banyaknya pasangan); tiap tepi menyimpan `p_max_ge` = (1 + permutasi dengan maks >= nilai) / (1 + R), `baseline_p95_of_max`, dan `exceeds_baseline_p95`. Besaran yang dibandingkan = **dukungan** untuk semua indikator. | Keputusan D-07 (usulan ADR 0024). Pembanding konteks, bukan uji signifikansi. |
| Korelasi | Indikator pada pasangan yang sama dengan bukti (ID observasi) bersinggungan ditandai dependen (`overlaps_with`); `pair_summary` memuat kelompok bukti independen. | Rencana WP-2.5 butir 6. |
| Hipotesis alternatif | Setiap tepi memuat empat hipotesis umum (mobilisasi organik, peristiwa eksternal, salin konten publik, bias cakupan) + satu spesifik indikator. | PRD 11.5. |
| Bukan temuan | Tidak ada field/ tabel temuan, skor, atau keyakinan; definisi memuat pernyataan "indikator, bukan temuan". Tes menjaga nama. | FR-077, FR-079. |

## Koreksi rancangan yang ditemukan lewat pengukuran

Pada percobaan pertama (parameter ditetapkan sebelum melihat hasil), pembanding baseline memakai nilai deskriptif tiap indikator.
Itu **jenuh**: Jaccard CO-01 bernilai 1,0 untuk dua akun yang masing-masing hanya membalas satu posting yang sama, dan kemiripan tertinggi
CO-03 jenuh di 1,0 sehingga baseline tak dapat membedakan satu pasangan mirip dari banyak. Pembanding diganti menjadi dukungan
(jumlah kejadian); nilai deskriptif tetap dilaporkan. Begitu pula dukungan CO-05 semula = jumlah tautan berbeda (menyembunyikan
pengulangan berbagi tautan yang sama) dan diganti menjadi jumlah pasangan respons.

## Hasil ukur pada dataset sintetis (X, 324 respons, 50 akun; 3 target x 4 putaran) - PILOT

Parameter (sebelum melihat hasil): jendela sinkron 120 detik, amplifikasi 300 detik, n-gram 3, ambang kemiripan 0,8, minimum 20 karakter,
frasa 5 kata, minimum 1 untuk semua indikator, 200 permutasi, seed 1. Satu run 9 detik (6.797 peristiwa, 2.407 tepi, 1.034 pasangan).

| Indikator | Tepi | p95 maks. baseline | maks. teramati |
|---|---|---|---|
| CO-01 | 1.032 | 5 | 4 |
| CO-02 | 92 | 2 | 3 |
| CO-03 | 187 | 9 | 9 |
| CO-04 | 43 | 2 | 3 |
| CO-05 url | 36 | 6 | 4 |
| CO-05 frasa | 284 | 21 | 42 |
| CO-06 | 733 | 3 | 3 |

- **Pola yang ditanam (kelompok K, 45 pasangan):** 10 pasangan (22%) melampaui baseline, lewat CO-02 dan CO-04 (tiga kejadian pada tiga target);
  tidak ada pasangan organik yang melampaui baseline lewat CO-02/CO-04. Sebagian besar pasangan K hanya punya 1-2 kejadian per indikator,
  sama dengan yang terjadi kebetulan pada baseline, sehingga **tidak terdeteksi**. Sinyalnya memang kecil (tiga balasan per akun).
- **Hard negative organik:** ledakan balasan awal organik tidak melampaui baseline (CO-02); tautan populer yang dibagikan organik
  tidak melampaui baseline (CO-05 url).
- **Positif palsu yang diketahui:** 23 pasangan organik melampaui baseline lewat **CO-05 frasa** karena templat sintetis memakai klaim yang sama
  berulang pada banyak akun organik (hipotesis alternatif "penyalinan konten publik"). Inilah alasan indikator tidak boleh dibaca sebagai bukti.
- CO-01 dan CO-06 tidak membedakan apa pun di data ini: hampir semua balasan menuju tiga posting target dan hanya ada tiga target.

Angka ini hanya menunjukkan perilaku metode pada data buatan; bukan estimasi kinerja pada data nyata.

**Biaya (mesin dev; graf acak, jendela dan ambang minimum 1):**

| Respons | Peristiwa+indikator (tanpa baseline) | Tepi yang dihasilkan | Dengan permutasi |
|---|---|---|---|
| 500 | 1,0 s | 5.389 | 100 permutasi: 10,6 s |
| 1.000 | 4,0 s | 19.199 | 100 permutasi: 38 s |
| 2.000 | 16 s | 67.741 | 50 permutasi: 76 s |
| 4.000 | 70 s | 256.046 | - |

CO-03 kuadratik terhadap jumlah respons; jumlah tepi tumbuh kira-kira kuadratik bila ambang minimum 1. Karena itu ambang minimum, `similarity_max_responses`,
dan `max_pair_events` adalah parameter wajib; melewati `max_pair_events` menggagalkan run dengan pesan jelas (tidak memotong diam-diam).
Tidak ada klaim skala di atas 4.000 respons.

## Batas yang diketahui

- Indikator tidak membuktikan koordinasi, pengendali, atau niat; setiap tepi wajib ditinjau manusia terhadap hipotesis alternatif (WP-2.6).
- Baseline permutasi memakai statistik maksimum yang konservatif: sinyal kecil (<= 2-3 kejadian) tidak dapat dibedakan dari kebetulan; ia tidak
  menjaga struktur waktu dan topik (peristiwa tetap, hanya label akun diacak), jadi akun yang memang aktif pada waktu yang sama karena peristiwa
  eksternal tetap tampak istimewa. Belum ada pembanding alternatif (mis. geser waktu dalam induk).
- Posting target dan balasan tingkat pertama membuat CO-01/CO-06 hampir universal pada data satu-topik; perlu data dengan banyak induk berbeda.
- Frasa dan kemiripan teks bergantung pada normalisasi sederhana (huruf kecil, tanda baca diratakan); tidak menangani parafrase, kode-campur, atau emoji.
- Waktu publikasi antar-platform memiliki ketelitian berbeda; analisis hanya dalam satu platform.
- Observasi terbaru per Post dipakai; perubahan teks antar putaran (edit) tidak dianalisis di sini.
- Belum ada API/UI/otorisasi (WP-2.7), `AuditEvent` umum di WP-2.8, eksekusi sinkron dan memuat dataset di memori.

## Pengujian

`tests/test_co_indicators.py` (35, murni: tiap indikator, normalisasi tautan, baseline, korelasi, penjaga nama) dan `tests/test_co_run.py` (42: pipeline basis
data, dedup antar putaran, jendela/waktu/akun tak dikenal, parameter, baseline, isolasi platform, penjaga trigger, serta uji ujung ke ujung atas dataset sintetis
WP-2.0). Mutasi: `wp25_indicators.py` 29/29, `wp25_run.py` 16 tertangkap + 1 setara (pelindung berlapis tak terjangkau), `wp25_triggers.py` 9/9. Mutasi awal
menemukan statistik pembanding yang jenuh (diatasi), dua celah tes (batas kemiripan inklusif, observasi terbaru, batas akhir jendela eksklusif), dan tes
trigger yang tertolak oleh constraint pengurutan pasangan alih-alih trigger platform.
