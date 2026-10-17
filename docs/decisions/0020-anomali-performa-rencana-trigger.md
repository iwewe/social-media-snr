# 0020 - Anomali performa: rencana query trigger yang membeku

- **Status:** diterima (A2: utang I1). Menutup catatan "anomali belum terjelaskan" di ADR 0009.
- **Tanggal:** 2026-10-17

## Gejala

Selama WP-1.4, ingestion dan rekonsiliasi kadang jauh lebih lambat dan tidak konsisten pada data yang sama
(10.000 objek: 18 s dan 135 s, normalnya 6-7 s), dengan CPU PostgreSQL 100%, lalu "sembuh sendiri" setelah autovacuum.
Hipotesis awal: statistik tabel basi.

## Temuan (percobaan terkontrol, `deployment/perf*.sh`)

1. **Tidak tereproduksi** pada transaksi sungguhan di database baru (6 skenario: autovacuum on/off, `ANALYZE`
   manual, JIT on/off): semua konsisten 6-8 s per 10.000 objek. Hipotesis statistik basi dan JIT tidak didukung.
2. **Tereproduksi 100%** (19,6 s dan 24,3 s) setelah `VACUUM (ANALYZE)` pada tabel kosong, tanpa perlu baris mati:
   statistik menjadi `relpages=0, reltuples=0`. Dengan 3.000 objek efeknya ringan (3,2 s): kuadratik terhadap ukuran.
3. `auto_explain` (nested + trigger) menunjuk **trigger penjaga platform** (`post_relation_platform_guard`: 18,3 s,
   `post_observation_platform_guard`: 13,5 s dari ~19.000 panggilan; ~190 buffer per baris), bukan query ingestion.
4. Di dalam trigger, `SELECT platform FROM collection_post WHERE id = NEW.from_post_id` berjalan sebagai
   **Seq Scan**. Pada tabel 500 baris (batch pertama) dengan statistik 0/0 perencana memilih
   `Seq Scan (cost 0.00..5.69)`, persis biaya di log; pada 1.000 baris ke atas memilih indeks. Fungsi PL/pgSQL
   men-cache rencana itu selama sesi; saat tabel tumbuh ke 10.000 baris setiap panggilan memindai tabel.
   Seq scan dengan `SELECT ... INTO` berhenti pada baris pertama yang cocok, jadi biayanya bergantung pada POSISI
   baris: data yang merujuk post baru (induk beragam) memperlihatkannya; rujukan ke baris pertama tidak
   (sebab uji awal yang memakai induk tetap tidak tereproduksi).
5. Menyambung ulang sesi tidak membantu (rencana dibuat ulang pada panggilan pertama, saat tabel masih kecil).
   Autovacuum yang menganalisis tabel pada ukuran lebih besar membatalkan rencana itu: itulah mengapa "sembuh sendiri".

## Keputusan

| Varian | Beban normal (10.000 objek) | Setelah VACUUM tabel kosong |
|---|---|---|
| tanpa perbaikan | ingestion 6,4-7,9 s; rekonsiliasi 5,8-6,6 s | 19,8-24,1 s |
| `plan_cache_mode = force_custom_plan` | ingestion 8,9-10,1 s; rekonsiliasi **9,6-10,5 s** (+40-60%) | 9,2 s |
| **`enable_seqscan = off` pada fungsi** | ingestion 6,5-7,7 s; rekonsiliasi 5,9-6,6 s (sama) | **6,2 s** |

Diterapkan: `ALTER FUNCTION ... SET enable_seqscan = off` pada fungsi penjaga (`snr_run_platform`,
`snr_identity_platform_guard`, `snr_observation_platform_guard`, `snr_relation_platform_guard`,
`snr_reconciliation_guard`, `snr_artifact_platform_guard`) lewat migrasi `collection 0010` dan `preservation 0005`
(dapat dibalik). Pengaturan berlaku hanya di dalam fungsi, bukan global. Fungsi-fungsi ini hanya mencari baris lewat
primary key, jadi melarang seq scan di dalamnya tidak berbahaya (seq scan hanya dibebani biaya besar, tidak dilarang
mutlak) dan rencana yang di-cache pasti memakai indeks tanpa biaya perencanaan ulang per panggilan.

## Pengujian

- `tests/test_trigger_plan_stability.py`: (1) setiap fungsi penjaga memiliki `enable_seqscan=off`; (2) perilaku:
  setelah `VACUUM` pada tabel kosong, `INSERT` 500 relasi ke post terakhir membaca <30.000 buffer (sebelum perbaikan:
  65.755; sesudah: ~15.000); (3) SQL migrasi dapat dibalik dan diterapkan ulang. Tes (1) dan (2) **merah sebelum
  perbaikan**.
- Alat ukur (bukan tes): `deployment/perf.sh` (matriks), `perf_rollback.sh` (reproduksi dan varian lewat `PERF_FIX`),
  `perf_diag.sh` (rencana di dalam trigger), `tests/benchmarks/perf_*.py`.

## Batas yang diketahui

- Trigger tetap memakai dua sampai empat pencarian per baris (~0,4 ms/baris di mesin dev). Mengganti pemeriksaan
  isolasi platform dengan foreign key komposit (kolom `platform` pada observasi/relasi) akan menghilangkan biaya
  itu, tetapi mengubah skema; ditunda dan belum dibutuhkan.
- Perbaikan menutup satu keluarga masalah (rencana trigger membeku). Query ORM lain yang di-prepare server-side
  (psycopg `prepare_threshold`) dapat mengalami hal serupa pada keadaan statistik ekstrem; pantau durasi per batch pada
  pilot (I4).
- Angka berasal dari mesin dev (4 vCPU, PostgreSQL 17 bawaan); gambaran relatif, bukan target produksi.
