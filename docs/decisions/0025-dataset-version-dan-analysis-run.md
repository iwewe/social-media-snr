# 0025 - DatasetVersion dan AnalysisRun: input analisis yang dibekukan

- **Status:** diterima (implementasi WP-2.1; FR-014, FR-041, NFR-01, AT-07)
- **Tanggal:** 2026-10-18

## Konteks

Analisis I2 harus dapat diulang dan diperiksa: hasil lama tidak boleh berubah ketika konteks direvisi atau data baru masuk,
dan analisis ulang harus menambah, bukan menimpa. Perlu satu rantai yang jelas dari observasi sampai keluaran.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Dataset | `DatasetVersion` = daftar ID observasi tak-berubah (tabel anggota) + `observation_digest` (SHA-256 atas ID terurut) + cara pemilihan (run, target) | Usulan rencana WP-2.1; hash daftar memudahkan memeriksa dua dataset sama. Hash bukan bukti keaslian. |
| Penyegelan | Dibuat belum tersegel, diisi anggotanya, disegel sekali (`sealed_at`). Penyegelan hanya sah bila jumlah anggota = `observation_count`; setelah itu tidak ada perubahan dan anggota tidak dapat ditambah (trigger) | Mencegah dataset yang diam-diam berubah atau terpotong. |
| Isolasi | Satu dataset = satu platform dan satu investigasi; anggota dari platform/investigasi lain ditolak trigger | FR-073, FR-081, NFR-06 ditegakkan di database, bukan hanya layanan. |
| AnalysisRun | Menunjuk dataset tersegel, versi konteks issue (boleh `None` secara eksplisit), versi konteks tiap target dataset (boleh `None`), metode+versi, parameter, hash parameter | AT-07: revisi konteks tidak mengubah run lama. |
| Parameter | Wajib eksplisit, divalidasi per metode, tanpa nilai bawaan tersembunyi | ADR 0024: tidak ada ambang baku. |
| Pembekuan | Kolom masukan terkunci trigger; hanya status, waktu, galat, keluaran yang berubah, dengan transisi satu arah PENDING -> RUNNING -> COMPLETED/FAILED (PENDING -> FAILED) dan keluaran hanya saat COMPLETED. Tidak ada DELETE. | NFR-01. |
| Konteks target | Tabel `AnalysisRunTargetContext`, hanya dapat ditambah selagi run PENDING; target harus pada investigasi dan platform yang sama | Konteks dibekukan per run. |
| Analisis ulang | `reanalyze`: dataset dan run BARU dari semua run ter-ingest pada target yang sama; metode dan parameter sama; konteks sama dengan run sebelumnya kecuali `use_latest_context=True`; tanpa observasi baru -> `NothingNew` (tidak membuat apa pun). Run lama tidak disentuh dan tertaut lewat `previous_run`. | FR-041, alur B; perilaku bawaan konservatif. |
| Metode pertama | `dataset-summary` v1 (hitungan dataset, penulis teratas dengan seri diputus ID). Bukan analisis perilaku; ada agar rantai ujung-ke-ujung dan reproduksibilitas teruji sebelum M2-M4. | Metode asli datang pada WP-2.2 dst. |
| Kegagalan | Galat metode dicatat pada run (`FAILED`, tipe + pesan terpotong), bukan disembunyikan atau dianggap nol hasil | Konsisten dengan FR-026. |

## Pengujian

`tests/test_analysis_runs.py` (33 tes): pembekuan dan hash, pilihan tidak sah, isolasi platform/investigasi, dataset tersegel tidak
dapat diubah lewat SQL langsung, penyegelan tidak dapat menyelundupkan perubahan, kunci masukan run (tiap kolom diuji
bersama transisi yang sah), konteks dibekukan dan keluaran identik meski konteks dan data berubah (AT-07, NFR-01), analisis
ulang, dan stabilitas rencana trigger (ADR 0020). Mutasi: `tests/mutation_specs/wp21_service.py` 22/22 tertangkap,
`wp21_triggers.py` 21/21. Tiga mutasi trigger pertama sempat lolos karena tes memukul penjaga lain (transisi status/check
constraint); tes diperbaiki agar tiap penjaga teruji sendiri.

## Batas yang diketahui

- Belum ada API, UI, atau otorisasi untuk membuat/menjalankan analisis (WP-2.7); layanan menerima `by` tetapi belum memeriksa peran.
- Eksekusi sinkron di dalam proses pemanggil; belum ada antrean Celery untuk analisis berat.
- Trigger anggota melakukan 4 pencarian per baris (dataset, observasi, post, run, target); sama seperti trigger lain dan
  dijaga `enable_seqscan = off` (ADR 0020). Dataset sangat besar belum diukur.
- Tidak ada `AuditEvent` (WP-2.8); jejak hanya `created_by`/`created_at`.
- Dataset memuat semua observasi pada run terpilih, bukan "keadaan terbaru per objek"; pemilihan yang lebih halus
  (mis. observasi terakhir per post) ditambahkan bila metode membutuhkannya.
