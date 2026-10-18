# Verifikasi bertingkat

Tujuan: cepat saat menulis kode, teliti sebelum kode masuk. Ketelitian tidak diturunkan untuk kode
yang menjaga integritas; yang dikurangi adalah pengulangan yang tidak menambah keyakinan.

## Empat tingkat

| Tingkat | Kapan | Perintah | Lama (VM dev) | Isi |
|---|---|---|---|---|
| 0 | tiap perubahan | `make fast`, `make t T="../tests/test_x.py -k nama"` | detik sampai ~1 menit | lint + typecheck + sinkron migrasi (`makemigrations --check`) bersamaan; tes terarah yang sedang ditulis |
| 1 | sebelum commit/PR | `make ci` | ~4 menit | `fast` + semua tes (backend paralel, browser, frontend bersamaan) |
| 2 | kode kritis, sebelum PR | `make mutate SPEC=tests/mutation_specs/<spek>.py` | menit | mutasi sengaja: membuktikan tes dapat gagal |
| 3 | tiap PR (otomatis) | CI GitHub | ~4 menit | semuanya pada lingkungan bersih; dijalankan sambil pekerjaan berikutnya berlanjut |

`make e2e` (E2E browser dengan worker, ~5 menit) dijalankan sekali per PR **bila** perubahan menyentuh alur UI,
API yang dipakai UI, worker, atau penyimpanan bukti. Perubahan murni dokumentasi atau alat tidak memerlukannya.

## Kapan tingkat 2 (mutasi) wajib

Wajib untuk kode yang bila salah akan merusak kepercayaan pada data atau akses:
- otorisasi, peran, keanggotaan, akun;
- integritas bukti: hash, manifest, penyaring rahasia, penyimpanan artefak, verifikasi;
- ingestion, rekonsiliasi, status run, orchestrator;
- (I2) klasifikasi, indikator koordinasi, evaluasi bukti, temuan.

Tidak wajib untuk: gaya tampilan, teks, tata letak, dan refaktor tanpa perubahan perilaku. Untuk UI, tes komponen
dan E2E sudah cukup; mutasi UI dipakai bila ada logika keputusan (mis. kapan tombol tampil menurut peran).

## Aturan mutasi (dijaga alat `tests/tools/mutate.py`)

1. Baseline harus hijau; bila merah alat berhenti (kode keluar 2).
2. Pola harus muncul tepat sekali; selain itu status `ERROR` (tidak ada SKIP diam-diam) dan eksekusi dianggap gagal.
3. Keputusan memakai kode keluar perintah tes, bukan teks keluaran. Kode 5 (tidak ada tes) dan batas waktu dilaporkan
   terpisah.
4. Berkas dipulihkan dan hash-nya diperiksa setelah tiap mutasi.
5. Mutan yang benar-benar setara diberi `equivalent="alasan"`; bila kelak tertangkap, alat memintanya dibersihkan.
6. Mutan yang lolos adalah celah tes: tambahkan tes, jangan menghapus mutasinya.

Spek disimpan di `tests/mutation_specs/` sebagai artefak hidup (dapat dijalankan ulang bila kode berubah).

## Kecepatan: apa yang diubah dan mengapa aman

- **Tes paralel** (`pytest-xdist`, `-n auto`): tiap worker memakai database uji sendiri (`test_snr_gwN`), jadi tidak
  berbagi keadaan. Aturan untuk tes baru: jangan bergantung pada nama berkas/port tetap, data global, atau urutan antar
  tes; pakai `tmp_path`, port 0, dan fixture. Tes yang butuh DB tanpa transaksi (`django_db(transaction=True)`) aman karena
  basis datanya milik worker itu sendiri.
- **Tes browser** tetap di image `worker-browser` dan berjalan bersamaan dengan tes backend (database uji berbeda).
- **`--reuse-db`** dipakai hanya oleh alat mutasi untuk spek yang tidak menyentuh migrasi; baseline selalu `--create-db`.
  Jangan memakai `--reuse-db` setelah mengubah migrasi.
- **Jangan menunggu CI**: mulai pekerjaan berikutnya dari `main` selagi CI berjalan. Jangan menumpuk PR di atas branch
  PR lain dan jangan memakai `--delete-branch` pada PR basis (PR di atasnya tertutup sendiri).
- Gabungkan WP kecil yang saling terkait dalam satu PR; pisahkan hanya bila ukuran atau risikonya berbeda.

## Yang tidak dikurangi

CI GitHub tetap menjalankan semuanya pada tiap PR. Tes yang harus merah dulu sebelum perbaikan (bukti bahwa tes mampu
gagal), tinjauan tangkapan layar untuk perubahan UI, dan pemeriksaan baseline pada mutasi tetap berlaku.
