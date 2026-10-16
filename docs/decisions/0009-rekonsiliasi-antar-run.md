# 0009 - Rekonsiliasi antar-run

- **Status:** diterima (implementasi WP-1.4). Aturan "perubahan relevan" adalah **asumsi kerja** yang berversi.
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 9.2 menetapkan status `NEW`, `UNCHANGED`, `MODIFIED`, `NOT_OBSERVED`, `CONFIRMED_UNAVAILABLE`
dengan aturan wajib: 20 reply lama ditambah 5 baru berarti identitas bertambah 5, bukan 25; objek yang
tidak muncul pada pemeriksaan parsial **tidak** dianggap terhapus (FR-036, AT-04); perubahan isi pada ID
yang sama menghasilkan observasi baru dengan riwayat lama utuh (AT-05).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Cakupan pembanding | Seluruh run SEBELUMNYA pada TARGET yang sama; pembanding tiap objek = observasi terbarunya | PRD 4.2: pemeriksaan ulang membandingkan dengan observasi sebelumnya atas target itu. Objek yang pernah terlihat di target lain tetap `NEW` bagi riwayat target ini (identitasnya tidak digandakan). |
| `NOT_OBSERVED` | Pernah terlihat, kini tidak muncul; pada run `COMPLETED` maupun `PARTIAL`; tidak ada status "dihapus" | FR-036. |
| `CONFIRMED_UNAVAILABLE` | Hanya bila adapter menyatakan eksplisit (`InspectionResult.confirmed_unavailable`, hanya pada hasil `COMPLETED`, objek tidak boleh sekaligus teramati) lengkap dengan bukti; disimpan di `run.coverage` | PRD 9.2 dan butir 2 rencana. Kontrak WP-1.1 diperluas (kompatibel mundur). |
| Tidak dibawa maju | Pernyataan "tidak tersedia" berlaku untuk run yang menyatakannya; run berikutnya kembali `NOT_OBSERVED` kecuali dinyatakan ulang | Pernyataan baru butuh bukti baru. |
| Perubahan relevan (v1) | Jenis objek, **teks**, penulis (ID), induk atau "induk tidak diketahui", objek yang dikutip, objek yang di-repost, himpunan akun yang disebut. `published_at` dibandingkan hanya bila keduanya diketahui dan berbeda | Asumsi kerja (disetujui lewat usulan, belum diputuskan eksplisit). |
| Tidak dihitung | `observed_at`/`captured_at`, username/nama tampilan, `collection_status`, flag verifikasi | Selalu berubah atau dicatat per observasi. |
| Normalisasi teks | Unicode NFC; `\r\n`→`\n`; spasi/tab beruntun jadi satu dan tepi baris dipangkas; ≥3 baris kosong jadi 2; U+200B dan U+FEFF dibuang; `None` ≠ teks kosong; ZWJ/ZWNJ dipertahankan | Perbedaan render tidak memicu `MODIFIED` (butir 3 rencana). |
| Versi aturan | `content_hash` + `content_hash_version` pada observasi; hash beda versi atau kosong (data lama) dihitung ulang dari data mentah | Aturan dapat diganti tanpa menulis ulang data append-only. |
| Penyimpanan | `ObservationReconciliation` append-only per (run, objek): status, observasi pembanding dan saat ini, `changed_fields`, bukti; integritas rujukan dijaga trigger (pembanding harus dari run SEBELUMNYA pada target yang SAMA, observasi saat ini milik post dan run itu, platform sama) | FR-035: disimpan sebagai data, tidak dihitung ulang saat ditampilkan. |
| Status run | `run.reconciliation`: `DONE` (akhir, idempoten), `SKIPPED`, `BLOCKED` (dihitung ulang saat dipanggil lagi) | |
| Ditolak (`BLOCKED`) | Ingestion run ini atau run pembanding belum tuntas (terputus, batch gagal, konflik); run `RUNNING` tanpa ingestion; run `PENDING` yang tidak pernah dijalankan tidak menghalangi | Data yang hilang karena kegagalan ingestion tidak boleh terbaca sebagai "tidak muncul" (akan menghasilkan `NOT_OBSERVED` palsu). |
| Dilewati (`SKIPPED`) | Run tanpa observasi (`FAILED`, `ACCESS_RESTRICTED`, `UNSUPPORTED`) | Tidak ada yang dapat dibandingkan; tanpa ini seluruh objek lama ditandai `NOT_OBSERVED`. |
| Objek tanpa ID | Tidak direkonsiliasi; hanya dihitung (`unmatched_candidates_*`) | Tidak ada kunci aman; mencegah banjir `NOT_OBSERVED`. |
| Pemanggilan | Tidak otomatis; orchestrator (WP-1.6) memanggil setelah ingestion dan menangani `BLOCKED`/`SKIPPED` | Pemisahan tanggung jawab. |

## Pengukuran (mesin dev, PostgreSQL lokal, data sintetis)

Skrip `tests/benchmarks/ingestion_bench.py` (dalam transaksi yang di-rollback). Skenario: run 2 memuat
semua objek run 1, 1% diedit, 10% baru, 5% hilang.

| Objek | Rekonsiliasi | Query |
|---|---|---|
| 1.000 | 0,57 s | 12 |
| 5.000 | 3,12 s | 16 |
| 10.000 | 7,20 s | 21 |

Sekitar 0,6–0,7 ms per objek, linear; jumlah query nyaris tetap (dijaga tes terhadap N+1).

### Anomali performa yang BELUM terjelaskan

Selama pengukuran, rekonsiliasi dan ingestion beberapa kali **jauh lebih lambat dan tidak konsisten**
pada data yang sama: 10.000 objek memakan 18 s dan 135 s (normalnya 7 s), dan 5.000 objek sekali 35 s.
Proses PostgreSQL memakai CPU 100% selama lebih dari 10 menit pada satu sesi; sempat tertangkap
sebuah query pencarian kandidat tanpa ID (`JOIN` observasi-post dengan `external_post_id IS NULL`)
berjalan 5–15 detik per panggilan. Setelah perubahan di bawah dan berjalannya autovacuum, keadaan
kembali linear dan cepat, dan **saya tidak dapat mereproduksinya secara terkontrol** (bentuk query lama
tetap cepat bahkan dengan nested loop dipaksa).

Hipotesis (tidak terbukti): statistik tabel basi dan baris mati akibat transaksi besar yang
berulang kali di-rollback membuat perencana query memilih rencana kuadratik sampai autovacuum
menganalisis tabel. Perubahan defensif yang dilakukan: indeks parsial `post_candidates_by_run_idx`
(`Post.first_seen_run` untuk `external_post_id IS NULL`), pencarian kandidat dalam dua langkah, dan
query pembanding rekonsiliasi memakai filter `run_id IN (...)` tanpa JOIN ke tabel run. Tes
memastikan indeks itu dapat dipakai. **Rekomendasi operasional:** jalankan `ANALYZE` setelah impor
besar dan pantau durasi per batch pada pilot (I4).

## Keterbatasan dan hal terbuka

- Rekonsiliasi dibatasi per target: dua target pada investigasi yang sama tidak saling membandingkan.
- Kandidat tanpa ID tidak direkonsiliasi; antrean peninjauan belum ada.
- Perubahan yang hanya mengubah spasi atau baris kosong tidak terdeteksi (teks mentah tetap utuh).
- Perubahan username/nama tampilan tidak dilaporkan sebagai `MODIFIED` (terlihat pada observasi).
- Aturan v1 adalah asumsi kerja; evaluasi pada data nyata (I4) dapat menaikkan versi.
- `confirmed_unavailable` belum dihasilkan adapter mana pun; kualitas buktinya ditentukan adapter
  platform (I3).
- Anomali performa di atas belum dipahami akar penyebabnya.
