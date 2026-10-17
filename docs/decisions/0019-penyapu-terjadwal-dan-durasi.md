# 0019 - Penyapu run basi terjadwal dan pengukuran durasi

- **Status:** diterima (A1: utang I1). Angka batas waktu untuk platform nyata belum ditetapkan.
- **Tanggal:** 2026-10-17

## Konteks

Aturan satu-run-aktif per target (ADR 0015) berarti run yang ditinggal mati pekerja (`RUNNING` selamanya) mengunci
targetnya. Penyapu (`sweep_stale_runs`, ADR 0012) sudah ada tetapi belum dijadwalkan. PRD tidak menetapkan batas waktu,
dan angka itu harus diukur pada adapter nyata; kita belum memilikinya.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Penjadwal | Layanan `scheduler` (celery beat) mengirim `snr.sweep_stale_inspections` ke antrean `analysis` | Memakai jalur Celery yang sama; tugasnya idempoten dan memakai UPDATE bersyarat. Tanpa volume data (tidak memasang evidence maupun browser-profiles) dan tanpa port. |
| Tanpa angka bawaan | Aktif hanya bila `SNR_SWEEP_OLDER_THAN_SECONDS` dan `SNR_SWEEP_INTERVAL_SECONDS` KEDUANYA diisi; kosong = tidak dijadwalkan | Angka yang dikarang tampak seperti keputusan. Compose meneruskan kedua variabel dengan bawaan kosong; `.env.example` memuatnya hanya sebagai komentar. |
| Gagal keras | Satu variabel saja, bukan bilangan bulat ASCII positif, interval > batas, atau batas <= `SNR_INSPECTION_SOFT_TIME_LIMIT` menghentikan startup dengan `ImproperlyConfigured` | Penyapu yang diam-diam tidak berjalan (atau menandai run sah yang masih berjalan) lebih buruk daripada startup yang gagal. Digit Unicode non-ASCII ditolak (`int()` menerimanya). |
| Pengukuran | `manage.py inspection_durations [--json]`: min/p50/p95/max lama eksekusi dan tunggu antrean per pengambil data (nearest-rank); run yang disapu tidak ikut diukur tetapi dihitung terpisah | Memberi dasar menetapkan batas. Run yang disapu durasinya adalah batas penyapu itu sendiri; jumlahnya justru sinyal batas terlalu rendah atau pekerja sering mati. Tes mengikat penanda penyapu ke pesan sebenarnya. |
| Skrip ukur | `deployment/measure.sh [N]` memakai database dan direktori data sementara | Run append-only: mengukur di database dev akan mengotorinya. |

## Hasil pengukuran awal (simulasi/dataset sintetis, N=20, mesin dev)

| Pengambil data | n | eksekusi p50 | p95 | maks | tunggu antrean maks |
|---|---|---|---|---|---|
| `browser-sim` (Chromium, termasuk peluncuran) | 51 | 1,29 s | 1,45 s | 1,46 s | 0,003 s |
| `fixture-dataset` | 20 | 0,026 s | 0,027 s | 0,033 s | 0,002 s |

Angka ini hanya membuktikan mekanismenya bekerja. **Bukan dasar untuk platform nyata**: halaman nyata lebih lambat,
bervariasi, dan dibatasi laju. Peluncuran Chromium mendominasi pada simulasi. Batas waktu produksi harus ditetapkan
setelah adapter nyata (I3) diukur; pilot (I4) memvalidasinya.

## Cara menetapkan nilai

1. Jalankan adapter nyata pada sampel target; baca `inspection_durations` (perhatikan p95 dan maks).
2. Tetapkan `SNR_INSPECTION_SOFT_TIME_LIMIT` di atas maks yang sah, lalu `SNR_SWEEP_OLDER_THAN_SECONDS` di atasnya.
3. Pantau jumlah `disapu`; kenaikannya berarti batas terlalu rendah atau pekerja bermasalah.

## Batas yang diketahui

- Satu instans beat saja (dua instans mengirim tugas ganda; aman karena idempoten, tetapi boros).
- Run yang masih benar-benar berjalan saat disapu akan gagal difinalkan oleh pekerja (UPDATE bersyarat); datanya
  yang sempat masuk tetap ada dan run ditandai PARTIAL. Itu sebab batas harus jauh di atas durasi sah.
- Tidak ada peringatan otomatis bila penyapu tidak berjalan (belum ada pemantauan).
