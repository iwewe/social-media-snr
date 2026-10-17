# 0012 - Orchestrator dan siklus hidup run

- **Status:** diterima (implementasi WP-1.6). Angka batas waktu sengaja belum ditetapkan.
- **Tanggal:** 2026-10-17

## Konteks

PRD FR-020/021/025/026 dan AT-14: pemeriksaan harus dapat dijalankan ulang tanpa menggandakan data, kegagalan
adapter tidak boleh tampak sebagai "nol respons", dan hasil yang bermasalah harus ditinjau manusia. Celery
dapat mengirim ulang pesan (acks late, pekerja mati), jadi eksekusi harus aman diulang.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| At-most-once | Klaim adalah satu `UPDATE ... WHERE status='PENDING'`; pemanggil yang tidak mendapat baris tidak menjalankan adapter | Pengiriman ganda/percobaan ulang tidak menjalankan adapter dua kali (diuji dengan dua thread). Adapter yang gagal di tengah tidak diulang otomatis: efek ke platform tidak dapat dibatalkan. |
| Pemeriksaan ulang | Selalu lewat run BARU (`request_inspection`), bukan menghidupkan run lama | Run lama tetap utuh sebagai catatan; sejalan dengan append-only. |
| Tabel transisi | Satu tabel di Python (`orchestrator/states.py`) dan trigger DB yang sama; tes membandingkan 8x8 pasangan | Penjaga ganda: bug kode tidak dapat melompati status. Tabel tidak boleh menyimpang antara dua tempat. |
| Data final tak berubah | Setelah status final, coverage/limitations/source_method/collector/started_at/finished_at ditolak DB; ingestion/reconciliation/preservation/review/claimed_by tetap dapat ditulis | Hasil adapter adalah catatan; kolom lanjutan memang diisi setelahnya. |
| Tanpa sukses palsu | COMPLETED hanya bila adapter COMPLETED dan ingestion + artefak bersih; selain itu REVIEW_REQUIRED dengan alasan. Tinjauan manusia (`acknowledge_review`) mengembalikan hasil adapter yang tercatat, tanpa mengubah data, dan mencatat siapa/kapan/catatan | AT-14, FR-026. |
| Artefak ditolak penyaring | Run tetap COMPLETED; penolakan tercatat di laporan ingestion/manifest | Penolakan rahasia adalah perilaku normal, bukan kegagalan run (ADR 0011). |
| Kegagalan buatan orchestrator | Tidak ada adapter, URL tak dikenal -> UNSUPPORTED; galat adapter/pelanggaran kontrak -> FAILED + `ADAPTER_ERROR`; SoftTimeLimit -> FAILED + `TIMEOUT`. Semua dikonversi menjadi InspectionResult dan melewati ingestion yang sama | Pencatatan seragam. Pesan galat tidak disalin ke run (dapat memuat isi/rahasia); hanya jenis galat, rinciannya di log server. |
| Antrean | `Adapter.execution_queue` (`analysis` atau `browser`), divalidasi suite kontrak (C16); pengiriman lewat `transaction.on_commit`; broker gagal -> run FAILED/`NETWORK_ERROR` | Run tidak terlihat pekerja sebelum commit, dan tidak menggantung PENDING bila broker mati. |
| Penyapu | `sweep_stale_runs` / `manage.py sweep_inspections --older-than N`: RUNNING basi -> PARTIAL bila ada observasi, FAILED bila tidak, keterbatasan `TIMEOUT`; UPDATE bersyarat sehingga run yang selesai bersamaan tidak ditimpa | Run tidak menggantung selamanya. Penanda ingestion `IN_PROGRESS` tidak dihapus, jadi rekonsiliasi tetap menolak run itu. |
| Batas waktu | Wajib eksplisit: penyapu menolak `None`/<=0; `SNR_INSPECTION_SOFT_TIME_LIMIT` hanya aktif bila diset | PRD tidak menetapkan angka dan angka itu harus diukur pada adapter nyata (WP-1.8/I3). Tidak ada angka bawaan yang dikarang. |
| Rekonsiliasi | Dijalankan hanya untuk COMPLETED/PARTIAL; galatnya dicatat di `run.reconciliation` dan tidak menjatuhkan run | Dapat diulang; ACCESS_RESTRICTED/FAILED bukan "semua objek hilang". |

## Batas yang diketahui

- Pekerja yang mati meninggalkan run RUNNING sampai penyapu dijalankan; penjadwalan penyapu (Celery beat/cron) belum dipasang.
- Tidak ada pembatasan laju per platform (belum ada adapter nyata).
- Batas waktu penyapu dan soft time limit harus ditetapkan dari pengukuran.
