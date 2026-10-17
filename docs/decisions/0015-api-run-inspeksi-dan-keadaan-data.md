# 0015 - API run inspeksi dan keadaan data

- **Status:** diterima (WP-1.9a, bagian API dari WP-1.9). UI menyusul pada PR berikutnya.
- **Tanggal:** 2026-10-17

## Konteks

FR-090/FR-095/NFR-08: antarmuka harus menunjukkan target, status inspeksi, riwayat run, pesan yang mudah
dipahami, dan membedakan **tidak ada data**, **belum diperiksa**, dan **gagal mengakses data**. Dua angka
(jumlah ditampilkan platform vs jumlah unik teramati) tidak boleh digabung (PRD 9.3).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Endpoint | `POST/GET /api/targets/<id>/inspections/`, `GET /api/inspections/<id>/`, `GET /api/inspections/<id>/observations/`, `POST /api/inspections/<id>/acknowledge-review/` | "Inspect" dan "Inspect Again" sama-sama membuat run BARU pada target yang sama (AT-01). |
| 202 + polling | POST mengembalikan 202 dengan run `PENDING`; hasil diketahui dengan membaca run | Eksekusi lewat Celery (jalur produksi); tidak ada eksekusi sinkron di request web. |
| Satu run aktif per target | Permintaan eksklusif ditolak 409 `inspection_in_progress` bila ada run `PENDING`/`RUNNING`, diperiksa di bawah kunci target yang sama dengan pembuatan run | Rekonsiliasi membandingkan run berurutan; dua run bersamaan dan klik ganda dapat merusak dasar perbandingan. Service lain tetap boleh membuat banyak run. |
| Keadaan data dihitung server | `data_state`: `not_inspected`, `in_progress`, `has_data`, `no_data`, `partial`, `access_failed`, `needs_review` | NFR-08 secara konsisten. `no_data` hanya untuk run COMPLETED dengan 0 balasan teramati; kegagalan akses TIDAK PERNAH menjadi `no_data`; PARTIAL dengan 0 balasan adalah `partial`; hitungan teramati yang tidak diketahui bukan `no_data`. |
| Pesan dari kode, bukan teks bebas | `api/messages.py` membangun pesan dari status, `LimitationCode`, alasan tinjauan, dan status ingestion/rekonsiliasi/preservasi; teks bebas adapter/galat tidak pernah disalin ke pesan | Mencegah isi data atau galat mentah bocor ke UI. Tes: setiap `LimitationCode` wajib bertext (kode baru menggagalkan tes). Teks dapat dipoles tanpa mengubah kode. |
| Dua angka terpisah | `coverage.platform_displayed_count` dan `observed_reply_count`/`observed_object_count` selalu terpisah; selisihnya dijelaskan dengan pesan `count_mismatch` | PRD 9.3. |
| `null` tetap `null` | Waktu publikasi, teks, penulis, jumlah ditampilkan: tidak diketahui = `null`, bukan kosong atau 0 | Ketidakpastian eksplisit. |
| Daftar respons | Dasar: baris rekonsiliasi bila rekonsiliasi `DONE` (NEW/UNCHANGED/MODIFIED, lalu NOT_OBSERVED/CONFIRMED_UNAVAILABLE di akhir dengan data terakhir terlihat dan `observed_in_this_run=false`); bila tidak, observasi run tanpa status | Objek yang tidak muncul tetap terlihat (bukan DELETED). Hasil rekonsiliasi dibaca, tidak dihitung ulang. |
| Whitelist bidang | Tidak ada identitas pekerja, jalur berkas, UUID publik, atau laporan mentah di JSON; artefak hanya metadata + hash | Isi dan verifikasi hash adalah WP-1.10. |
| Konteks belum cukup | `notices` pada target: `context_insufficient` bila catatan kosong dan tanpa posisi awal | FR-095. |
| Tinjauan | `acknowledge-review` memanggil service yang ada; 409 `not_awaiting_review` bila tidak relevan | Tidak mengubah data run; hanya mencatat siapa/kapan/catatan. |

## Batas yang diketahui

- Run yang ditinggal mati pekerja tetap `RUNNING` sampai penyapu dijalankan (`manage.py sweep_inspections --older-than N`); sampai itu, target terkunci oleh aturan satu-run-aktif. Penjadwalan penyapu dan angka batas waktunya belum ditetapkan (harus diukur).
- Semua pengguna terautentikasi masih dapat melihat semua investigasi (asumsi lama; WP-3.6).
- Pesan berbahasa Indonesia redaksi awal developer; boleh dipoles (PRD bagian 12).
- Paginasi memakai offset (cukup untuk ratusan-ribuan baris); perlu ditinjau bila run mencapai puluhan ribu objek.
