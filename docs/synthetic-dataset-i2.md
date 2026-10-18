# Dataset sintetis I2 (WP-2.0)

Generator deterministik untuk menguji analisis I2 tanpa platform eksternal (PRD 16.1, FR-029, AT-18).
Kode: `backend/intelligence/synthetic/`. Definisi indikator yang diuji: ADR 0024.

## Menjalankan

```
cd backend && python -m intelligence.synthetic --out /tmp/syn-i2 [--seed N]
SNR_FIXTURE_DATASETS_DIR=/tmp/syn-i2/datasets   # agar adapter dataset memuatnya
```

Keluaran: `datasets/*.json` (format v1, `docs/format-dataset-impor.md`) dan `ground-truth.json` **di luar** direktori
dataset (adapter membaca semua `*.json` di direktorinya). Hasil tidak di-commit; seed bawaan selalu menghasilkan isi
yang sama.

## Isi (seed bawaan)

- 3 target X (id posting sama dengan id pada URL), masing-masing ~100 balasan, 4 putaran inspeksi; 1 dataset TikTok kecil.
- 50 akun sintetis: organik PRO/CONTRA, penanya/netral, penyerang personal, kelompok K (10 akun), 3 akun pemosting.
- Skenario: percakapan organik; serangan personal independen; **pola yang sengaja ditanam** (K membalas posting yang sama
  dalam <= 90 detik, teks nyaris sama, tautan sama, me-repost posting yang sama, pada ketiga target); perubahan antar
  putaran (teks diedit, objek hilang saat putaran parsial lalu kembali, objek dinyatakan tidak tersedia oleh sumber).
- Kasus tepi: Lampiran A PRD persis (AT-08 "setuju" pada reply tingkat dua), acuan video (AT-09), kritik sah vs serangan
  (AT-10), banyak akun stance sama tanpa koordinasi (AT-11), username sama di X dan TikTok (AT-13), akun dengan cakupan
  sebagian (AT-17).
- **Lawan uji (hard negative)**: ledakan balasan organik dalam menit pertama dengan teks berbeda (CO-02), tautan populer yang
  dibagikan organik (CO-05).

## Kunci jawaban

`ground-truth.json` memuat, per observasi: `issue_stance`, `target_alignment`, `expression_sentiment`,
`response_character` (RC-xx), `needs_human_review`, kelompok, dan kasus. Ini bahan **evaluasi** (WP-2.2e) dan uji indikator
(WP-2.5): pola yang ditanam harus terdeteksi sebagai *indikator* (bukan vonis) dan pola organik tidak boleh. Data seluruhnya
fiktif; angka ukurannya adalah target latihan, bukan klaim kecukupan statistik.

## Verifikasi

`tests/test_synthetic_dataset.py` (16 tes: loader + kontrak adapter, determinisme per komponen, kecocokan ground truth
dengan data, pola ditanam benar-benar sinkron di data, hard negative, perubahan antar putaran, isolasi platform) dan
mutasi `tests/mutation_specs/wp20_synthetic.py` (20/20 tertangkap).
