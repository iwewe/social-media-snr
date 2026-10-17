# Format dataset uji / impor (skema versi 1)

Dipakai adapter dataset (`collection.datasets`, WP-1.7; FR-029, AT-18) agar SNR dapat dikembangkan dan diuji
**tanpa platform eksternal**. Contoh lengkap: `datasets/sample/`.

## Aturan umum

- Satu berkas JSON UTF-8 = satu **target** dengan urutan **snapshot**. Snapshot ke-N diputar pada run ke-N target itu
  (run 1 -> snapshot 1, dst.), sehingga skenario beberapa putaran dapat diulang secara deterministik.
- Target tanpa dataset, atau run melebihi jumlah snapshot, menghasilkan `UNSUPPORTED` dengan alasan; bukan hasil kosong.
- Berkas tidak sah dilaporkan (run `FAILED`, `PARSE_FAILED`) hanya bila tidak ada dataset sah yang cocok; tidak diabaikan diam-diam.
- Dua berkas untuk target yang sama dianggap ambigu (`FAILED`). Ukuran berkas maksimum 16 MiB. Hanya `*.json` pada
  direktori itu (tidak rekursif). Berkas dibaca ulang pada tiap run.
- Kunci yang tidak dikenal ditolak (salah ketik tidak boleh lolos). Semua waktu ISO-8601 **dengan zona waktu**.
- Pesan galat menyebut lokasi (mis. `x.json.snapshots[2].observations[5].parent`) dan jenis masalah, tidak pernah isi data.
- Dataset divalidasi terhadap kontrak adapter yang sama dengan adapter nyata (mis. `COMPLETED` wajib paginasi lengkap
  dan tanpa keterbatasan blocking; balasan wajib punya induk).

## Akar

| Kunci | Wajib | Keterangan |
|---|---|---|
| `schema_version` | ya | `1` |
| `name` | ya | nama dataset (muncul di catatan cakupan run) |
| `platform` | ya | `x`, `threads`, `tiktok`, `instagram`, `facebook` |
| `target_url` | ya | URL target; dinormalisasi seperti URL target di aplikasi |
| `source_method` | ya | `synthetic_fixture` (data buatan) atau `imported_dataset` (dataset sah dari luar). Metode lain ditolak |
| `snapshots` | ya | daftar snapshot, minimal satu |

## Snapshot

| Kunci | Wajib | Keterangan |
|---|---|---|
| `observed_at` | ya | waktu pengamatan |
| `outcome` | ya | `COMPLETED`, `PARTIAL`, `FAILED`, `ACCESS_RESTRICTED`, `UNSUPPORTED` |
| `pagination_complete` | ya | `true`/`false`/`null` (tidak diketahui; tidak dianggap lengkap) |
| `displayed_count` | tidak | jumlah yang **ditampilkan platform**; berbeda dari jumlah teramati |
| `observations` | tidak | daftar observasi; kosong untuk `FAILED`/`ACCESS_RESTRICTED`/`UNSUPPORTED` |
| `limitations` | tidak | `{code, message, capability?}`; kode seperti `PAGINATION_INCOMPLETE`, `ACCESS_RESTRICTED`, `PARSE_FAILED` |
| `confirmed_unavailable` | tidak | `{id, evidence}`: sumber **menyatakan** objek tidak tersedia. Absen dari daftar saja bukan bukti (menjadi `NOT_OBSERVED`) |
| `artifacts` | tidak | `{kind, filename, content_type, text, note?}`; berlaku penyaring rahasia yang sama. `manifest` dilarang |
| `notes` | tidak | catatan cakupan |

## Observasi

`type` wajib (`post`, `reply`, `comment`, `quote`, `repost`; jenis asli platform dipertahankan). Lainnya opsional:
`id`, `actor` (boleh `null` bersama `needs_verification: true`), `parent`, `parent_unknown`, `quoted`, `reposted`,
`mentions`, `published_at`, `captured_at`, `text` (`null` = tidak diketahui, beda dari string kosong), `handle`,
`display_name`, `needs_verification`. Username/nama tampilan hanya informasi; identitas adalah `actor`.

## Menjalankan

Set `SNR_FIXTURE_DATASETS_DIR` ke direktori dataset (di compose dev: `/datasets/sample`). Tanpa variabel ini adapter
dataset **tidak terdaftar** sehingga data uji tidak dapat menyamar sebagai pengamatan platform; observasinya selalu
bertanda `synthetic_fixture` atau `imported_dataset`.

## Dataset sungguhan

Dataset impor harus sah secara hukum dan etika; itu diverifikasi **di luar kode** (PRD bagian 13). Memberi label
`imported_dataset` bukan bukti keabsahan sumber. Jangan menaruh dataset sungguhan atau data pribadi di repositori.

## Belum didukung

CSV (rencana awal menyebut JSON/CSV; JSON dipilih karena struktur induk-anak dan keterbatasan sulit dinyatakan di CSV).
