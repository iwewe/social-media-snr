# 0008 - Ingestion idempoten

- **Status:** diterima (implementasi WP-1.3)
- **Tanggal:** 2026-10-16

## Konteks

Hasil inspeksi (`InspectionResult`, kontrak WP-1.1) harus masuk ke model WP-1.2 tanpa menggandakan
identitas (FR-032, NFR-03), tanpa merusak data yang sudah valid bila gagal di tengah (NFR-04), dan
dengan provenance lengkap (NFR-05). PRD bagian 9.2: 20 reply lama ditambah 5 baru berarti +5
identitas, bukan 25.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Pintu masuk | `collection.ingestion.ingest_result(run, result)` mengembalikan `IngestionReport` | Satu jalur tulis hasil adapter. |
| Idempotensi | Identitas dipakai ulang lewat `(platform, ID sumber)`; observasi yang sudah ada dengan isi sama dihitung duplikat dan dilewati | Meng-ingest hasil yang sama dua kali tidak menambah baris apa pun (diuji, termasuk berulang dengan ukuran batch berbeda). |
| Konflik | Observasi/induk/metadata berbeda pada run yang sama **tidak ditimpa**; dilaporkan (`OBSERVATION_CONFLICT`, `RELATION_CONFLICT`, `METADATA_CONFLICT`) | Satu run adalah satu peristiwa pengamatan; perubahan isi berarti run baru. |
| Kegagalan sebagian | Observasi ditulis per batch dalam transaksi tersendiri; batch gagal dibatalkan utuh, dicatat di laporan, batch lain tetap; berhenti setelah 3 batch gagal; menjalankan ulang menyelesaikan batch yang tertinggal | NFR-04. Tidak ada baris setengah jadi. |
| Balapan | Identitas dibuat `INSERT ... ON CONFLICT DO NOTHING` lalu dibaca ulang; baris run dikunci per batch; "dibuat" dihitung dari `first_seen_run` | Dua ingestion bersamaan membuat tiap identitas tepat sekali dan tidak menghitungnya dua kali (diuji dengan dua thread). |
| Objek tanpa ID | Kandidat `NEEDS_VERIFICATION` per observasi; tidak pernah digabung. Dalam satu run dicocokkan sebagai multiset `(jenis, teks, waktu terbit, handle, nama)` hanya agar re-ingest idempoten. Aktor tanpa ID: `author=NULL`, tanpa baris aktor | PRD bagian 5. |
| Penanda | Observasi bertanda `identity_needs_verification` membuat baris baru `NEEDS_VERIFICATION`; baris yang sudah ada tidak diubah | Tidak ada kenaikan/penurunan status otomatis. |
| Objek yang hanya dirujuk | Induk/kutipan/repost/aktor yang disebut mendapat baris identitas `VERIFIED` (ID dari sumber) tanpa observasi | Relasi membutuhkan tujuan; ketiadaan observasi dibedakan dari objek yang diamati. |
| Dua jumlah | `run.coverage` menyimpan `platform_displayed_count` dan `observed_reply_count` terpisah | PRD bagian 9.3. |
| Kegagalan adapter | Hasil `FAILED`/`ACCESS_RESTRICTED`/`UNSUPPORTED` dicatat (keterbatasan dan cakupan pada run) tanpa observasi | FR-026, AT-14. |
| Status ingestion | `run.ingestion`: `IN_PROGRESS` di awal; `FINISHED` atau `FINISHED_WITH_PROBLEMS` (+ laporan) di akhir | Menutup celah yang ditemukan saat pengukuran: bila proses mati di tengah, metadata sudah tercatat tetapi laporan hilang; penanda `IN_PROGRESS` yang tertinggal membuat run terputus dapat dikenali. |
| Artefak | Tidak disimpan di sini; laporan menandai `ARTIFACTS_NOT_PERSISTED` | Tidak dibuang diam-diam; preservasi artefak ada di WP-1.5. |
| Status run | Tidak diubah oleh ingestion | Tanggung jawab orchestrator (WP-1.6). |

## Pengukuran (mesin dev, PostgreSQL lokal, data sintetis)

Skrip: `tests/benchmarks/ingestion_bench.py` (dalam transaksi yang di-rollback). "Trigger mati"
hanya untuk mengukur biaya penjaga WP-1.2; tidak dilakukan pada data nyata.

| Observasi | Batch | Trigger aktif | Trigger mati | Query |
|---|---|---|---|---|
| 1.000 | 500 | 0,75 s | 0,54 s | 32 |
| 5.000 | 500 | 2,83 s | 2,57 s | 136 |
| 5.000 | 1.000 | 2,64 s | 2,34 s | 71 |
| 10.000 | 1.000 | 5,03 s | 4,88 s | 136 |

Sekitar 0,5 ms per observasi (kurang lebih 2.000 observasi/detik). Query tumbuh linear terhadap
jumlah batch (tidak ada N+1; dijaga tes). Biaya trigger penjaga platform dan identitas kecil
(sekitar 3% pada 10.000 observasi, hingga sekitar 30% pada batch kecil). Ini jawaban atas butir
terbuka di ADR 0007. Angka ini bukan target performa produksi (PRD tidak menetapkan SLA).

## Keterbatasan dan hal terbuka

- Kandidat tanpa ID tetap menumpuk lintas run (tidak ada kunci aman). Antrean peninjauan belum ada.
- Galat apa pun dalam batch dicatat sebagai batch gagal (dengan log); bug pemrograman juga tampak
  seperti itu, jadi `ok=False` harus selalu ditindaklanjuti, bukan diabaikan.
- Seluruh `InspectionResult` berada di memori; hasil yang sangat besar perlu aliran (belum perlu).
- Re-ingest hanya idempoten bila hasilnya identik; adapter yang menghasilkan `observed_at`
  berbeda untuk objek yang sama pada run yang sama akan menghasilkan konflik (disengaja).
- `run.ingestion` hanya penanda; tindakan atas `IN_PROGRESS` yang menggantung (menandai
  `REVIEW_REQUIRED`) ada di WP-1.6.
- Pengukuran memakai 200 aktor unik dan teks pendek; data nyata dapat berbeda.
