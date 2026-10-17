# 0013 - Adapter dataset uji/impor

- **Status:** diterima (implementasi WP-1.7).
- **Tanggal:** 2026-10-17

## Konteks

FR-029/AT-18: sistem harus dapat dikembangkan dan diuji end-to-end tanpa izin atau akses platform. Skenario PRD
bagian 16.1 membutuhkan beberapa putaran inspeksi yang dapat diulang persis sama.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Lokasi | `collection/datasets/`, bukan `collection/adapters/` | Aturan arsitektur menetapkan `collection.adapters.*` hanya lima paket platform (isolasi per platform). Adapter dataset bukan platform. |
| Satu kelas per platform | `fixture_adapter_class(platform)` membuat subkelas dengan `platform` di kelas; registry tetap satu adapter per platform | Registry dan kontrak mengandalkan `platform` pada kelas; instans tidak dapat mengaku platform lain. |
| Putaran deterministik | `InspectionRequest.run_sequence` (opsional, diisi orchestrator); run ke-N memutar snapshot ke-N | Adapter tidak boleh membaca database. Adapter platform tidak boleh bergantung pada field ini. |
| Berkas = target + snapshot | Satu berkas JSON per target (bukan satu berkas per snapshot) | Urutan snapshot dan targetnya terikat dalam satu berkas; tidak ada penamaan/urutan berkas implisit yang bisa salah. |
| JSON saja | CSV ditunda | Induk-anak, keterbatasan, dan objek tidak tersedia tidak natural di CSV. |
| Validasi saat parse | Kunci tak dikenal ditolak; waktu wajib bertimezone; tiap snapshot diuji-bangun menjadi `InspectionResult` sungguhan | Pelanggaran kontrak terlihat sebagai galat dataset dengan lokasi, bukan `ADAPTER_ERROR` saat run. Pesan hanya lokasi, tidak pernah isi. |
| Tanpa sukses palsu | Target tak ada dataset / run melebihi snapshot -> `UNSUPPORTED`; berkas rusak yang mungkin relevan -> `FAILED`/`PARSE_FAILED`; dataset ganda -> `FAILED` | Tidak ada hasil kosong yang tampak sukses (AT-14). |
| Sumber data | `source_method` hanya `synthetic_fixture` atau `imported_dataset` | Data uji tidak boleh berlabel pengamatan/API resmi. |
| Tidak terdaftar bawaan | Hanya terdaftar bila `SNR_FIXTURE_DATASETS_DIR` diset | Data uji tidak menyamar sebagai platform di lingkungan nyata. |
| Klasifikasi URL | Aturan sederhana per platform di `collection.datasets.adapter.classify_url` | Cukup untuk dataset; BUKAN pengganti adapter nyata (WP-3.0/3.x mempelajari struktur URL tiap platform). |
| `max_items` | Dihormati: terpotong -> `PARTIAL` + `MAX_ITEMS_REACHED` | Field kontrak tidak boleh diabaikan diam-diam. |

## Batas yang diketahui

- Dataset sampel kecil (3 berkas, ~8 balasan); generator 3 target/50 akun/~300 balasan adalah WP-2.0.
- Berkas dibaca ulang tiap run (sederhana, tidak di-cache); tidak ada pengindeksan untuk direktori besar.
- Legalitas dataset impor diverifikasi di luar kode.
