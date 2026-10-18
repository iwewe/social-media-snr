# 0028 - Interaction Network dan Stance Network View (M4, bagian struktur)

- **Status:** diterima (implementasi WP-2.4; FR-070, FR-071, FR-073, FR-074; AT-11, AT-13). Indikator koordinasi (Behavioral Coordination Network) adalah WP-2.5 dan sengaja tidak termasuk di sini.
- **Tanggal:** 2026-10-18

## Konteks

M4 menyediakan tiga representasi; PRD melarang menjadikan struktur jaringan sebagai penentu pengendali atau koordinasi, dan
mewajibkan analisis satu platform per graf. Interaction Network berisi hanya relasi yang benar-benar teramati; stance
hanya atribut. Rencana juga meminta stabilitas deteksi komunitas diuji (PRD bagian 18: belum diketahui) dan batas skala dicatat.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Satu platform | `GraphProjection.platform` tunggal; trigger menolak proyeksi yang platformnya berbeda dari dataset, node dengan akun platform lain, dan edge yang ujungnya bukan node graf yang sama. | AT-13, NFR-06, FR-073: ditegakkan di database. |
| Node | `ActorAccount` yang menulis observasi dalam dataset beku (termasuk yang tanpa relasi) + akun yang dituju. | Akun dengan stance sama tetapi tanpa interaksi tetap terlihat, tanpa edge (AT-11). |
| Edge | Relasi teramati `reply_to`, `quote_of`, `repost_of`, `mentions` dari `PostRelation`, arah dari penulis ke akun yang dituju, digabung per (dari, ke, jenis). Menyimpan jenis, bobot, **ID observasi asal**, hitungan stance respons pembentuk, rentang waktu. | FR-070; asal tersimpan per edge. |
| Dikecualikan | Interaksi ke diri sendiri, relasi dengan akun tak diketahui, jenis tak terpilih, di luar jendela, waktu tak diketahui (bila kebijakan `exclude`) dihitung per alasan di `exclusions`, tidak hilang diam-diam. | Transparansi. |
| Stance | Hanya ATRIBUT: hitungan stance dan `stance_summary` (PRO/CONTRA/MIXED/UNDETERMINED, aturan ATRIBUT bukan label akun) pada node; hitungan stance pada edge. Opsional: butuh `source_run` M2 + hash penilaian dikunci (seperti M3). **Stance sama tidak pernah membuat edge.** | FR-071, AT-11. |
| Parameter | Semua eksplisit: jenis relasi, bobot (`count`/`binary`), jendela, kebijakan waktu tak diketahui, `resolution`, `seed`, `compute_betweenness`, `metrics_max_nodes`, `stability_seeds`. Disimpan di definisi graf. | FR-074; ADR 0024. |
| Metrik | NetworkX: derajat dan kekuatan per node, betweenness (opsional), komunitas Louvain (berbobot, seed tersimpan, label diurutkan menurut ID akun terkecil), modularitas, versi pustaka. Setiap graf memuat catatan: *menggambarkan struktur, bukan penentu pengendali, koordinasi, atau niat*. | PRD 11.4. |
| Stabilitas | `stability_seeds` > 0 mengukur kestabilan komunitas (indeks Rand antar-seed, jumlah partisi berbeda) dan menyimpannya bersama komunitas. | PRD 18; ketidakstabilan terlihat setiap kali komunitas dilaporkan. |
| Skala | `metrics_max_nodes` (eksplisit) membuat metrik mahal `SKIPPED_TOO_LARGE`; derajat tetap dihitung; graf tetap tersimpan. | Tanpa klaim skala. |
| Penyimpanan | `GraphProjection`/`GraphNode`/`GraphEdge` append-only (trigger), ditulis hanya saat run M4 `RUNNING`; atomik dengan eksekusi (gagal -> tak ada baris). | Pola ADR 0025-0027. |

## Hasil ukur (mesin dev snr-dev, satu proses; angka orde besar, bukan jaminan)

**Dataset sintetis (X, 3 target x 4 putaran): 50 node, 171 edge; satu run M4 137 ms.** Komunitas pada resolusi 1.0: 4 komunitas,
modularitas 0,155 (rendah: struktur lemah).

**Stabilitas komunitas terhadap seed (50 seed pada graf yang sama):**

| Resolusi | Partisi berbeda | Rand rata-rata vs pertama | Rand minimum |
|---|---|---|---|
| 0,5 | 1 | 1,000 | 1,000 |
| 1,0 | **29** | 0,853 | 0,653 |
| 1,5 | 48 | 0,864 | 0,801 |
| 2,0 | 46 | 0,961 | 0,935 |

Temuan: pada graf sintetis ini deteksi komunitas **tidak stabil terhadap seed** pada resolusi 1,0 ke atas (29-48 partisi berbeda dari
50 seed). Komunitas tidak boleh dilaporkan sebagai fakta struktural tanpa seed dan ukuran kestabilannya; itulah alasan stabilitas
disimpan di graf. Resolusi 0,5 stabil, tetapi bisa jadi karena partisi menjadi kasar; kestabilan tidak berarti kebenaran.

**Skala (graf acak berarah, 5 edge per node, tanpa betweenness):**

| Node | Edge | Bangun + derajat + Louvain |
|---|---|---|
| 1.000 | ~5.000 | 0,44 s |
| 5.000 | ~25.000 | 3,8 s |
| 20.000 | ~100.000 | 29 s |
| 50.000 | ~250.000 | 208 s |

Betweenness (tak berbobot, berarah): 500 node 1,1 s; 1.000 node 4,5 s; 2.000 node 18 s (kira-kira kubik). Biaya meningkat lebih cepat dari
linear. **Tidak ada klaim skala di atas ini**; nilai `metrics_max_nodes` yang masuk akal di mesin dev sekitar 20.000 tanpa betweenness dan 2.000 dengan.

## Batas yang diketahui

- Interaction Network hanya memuat interaksi langsung teramati; **pola koordinasi tidak terlihat di sini** (mis. kelompok yang
  membalas posting yang sama tidak terhubung satu sama lain). Itu justru pekerjaan indikator CO (WP-2.5).
- Louvain tidak stabil terhadap seed pada graf tertentu (lihat tabel); belum ada metode pembanding (mis. Leiden) atau konsensus antar-seed.
- Graf sintetis terlalu kecil dan terlalu teratur untuk menyimpulkan perilaku pada data nyata; modularitas rendah wajar di sini.
- Metrik berarah memakai bobot gabungan antar-jenis relasi; pembobotan per jenis belum ada.
- Edge `mentions` memakai akun yang disebut tanpa memeriksa apakah akun itu terobservasi pada dataset.
- Belum ada API/UI/otorisasi (WP-2.7); `AuditEvent` umum di WP-2.8; eksekusi masih sinkron dan memuat seluruh dataset di memori.
- NetworkX ditambahkan sebagai dependensi runtime (3.7) beserta `types-networkx` (dev).

## Pengujian

`tests/test_m4_network.py` (28, murni) dan `tests/test_m4_run.py` (48, termasuk uji ujung ke ujung atas dataset sintetis WP-2.0:
platform terpisah, tidak ada edge antar-anggota kelompok yang ditanam, graf terulang). Mutasi: `wp24_network.py` 22/22,
`wp24_run.py` 16 tertangkap + 4 setara terdokumentasi (pelindung berlapis yang tak terjangkau karena trigger dataset), `wp24_triggers.py` 12/12.
Mutasi awal menemukan: relasi dengan jenis tak terpilih tidak pernah tercatat sebagai pengecualian (diperbaiki); empat celah tes
(validasi sumber, induk lintas-run, parameter stance sebagian, tahap bukti min/mean stabilitas); dua tes trigger yang ditolak oleh
constraint unik alih-alih trigger.
