# Protokol pilot (WP-4.1)

Persiapan pilot investigasi. Dokumen ini adalah **daftar periksa yang diisi organisasi**; bagian yang bertanda
`[ISI]` tidak boleh diisi atau diasumsikan oleh tim developer. PRD tidak menetapkan "target lulus": jangan
menambahkannya di sini.

## 1. Cakupan (ISI sebelum mulai)

| Butir | Nilai |
|---|---|
| Investigasi (satu, terbatas) | `[ISI]` |
| Issue dan proposition | `[ISI]` |
| Target nyata dan platform | `[ISI]` (hanya melalui jalur yang disetujui; lihat `docs/adapters/`) |
| Periode data | `[ISI]` |
| Penanggung jawab pilot | `[ISI]` |
| Jalur perolehan data per target | `[ISI]` (dataset impor yang sah, atau adapter yang telah diaktifkan lewat keputusan tertulis) |

Prasyarat teknis: pada 2026-10-19 seluruh pengambilan otomatis `DISABLED` (ADR 0036); satu-satunya jalur siap pakai
adalah **impor dataset** dari sumber yang sah. Pilot yang membutuhkan pengambilan langsung menunggu keputusan
organisasi atas dokumen kelayakan platform.

## 2. Dasar izin dan retensi (ISI; tertulis)

- [ ] Dasar izin penggunaan data (siapa memberi izin, ruang lingkup, tanggal): `[ISI]`
- [ ] Kebijakan retensi **sementara** untuk pilot (durasi, penghapusan, nasib backup): `[ISI]`. Durasi final belum
      ditentukan di PRD; pilot memakai kebijakan sementara yang tertulis.
- [ ] Penilai anotasi telah menyetujui penanganan teks pihak ketiga (set anotasi diperlakukan setara bukti).
- [ ] HTTPS aktif (`docs/operations.md`), backup di perangkat terpisah, dan satu uji restore terbaru tercatat.

## 3. Set anotasi (50-100 respons; ideal dua penilai independen, PRD 16.3)

1. Jalankan klasifikasi M2 (`run_analyses`) pada data pilot.
2. Buat set: `manage.py pilot_annotation_set --run <id M2> --out <direktori-di-luar-Git> --annotators penilai-A penilai-B --n 60 --seed <angka>`.
   Pengambilan contoh dibuat bergilir antar kategori mesin agar beragam dan dapat diulang (benih dicatat di `manifest.json`).
   Direktori keluaran berizin 700 dan berkas 600; **jangan masukkan ke Git** (`pilot-data/` diabaikan).
3. `sheet.json` untuk penilai TIDAK memuat label mesin. Tiap penilai mengisi labelnya sendiri tanpa melihat label
   mesin maupun penilai lain. Tambahkan tag (mis. `sarcasm`, `informal`, `nested`) bila relevan.
4. Adjudikasi: perbedaan antar-penilai diputuskan bersama; tulis `gold` pada tiap item. Satu penilai: label penilai itu
   menjadi putusan akhir (dicatat sebagai keterbatasan).
5. Evaluasi: `python -m intelligence.evaluation --gold sheet-terisi.json --pred predictions.json`
   dan `--agreement penilai-A penilai-B`. `predictions.json` berisi label mesin yang **asli** (bukan hasil koreksi).
6. Seluruh angka berlabel PILOT: contoh kecil, tanpa interval kepercayaan. Jangan memilih model/penyedia NLP (D-01)
   hanya dari angka ini.

## 4. Metrik yang dicatat (tanpa ambang lulus)

`manage.py pilot_metrics [--json]` mencetak:

- kelengkapan pengambilan: respons teramati dibanding yang ditampilkan platform (hanya run yang melaporkan keduanya)
  dan jumlah run dengan paginasi tidak lengkap;
- kegagalan parser (`PARSE_FAILED`) dan keadaan tidak didukung per platform, hasil run per platform;
- durasi run per pengambil data (min/p50/p95/maks) dan waktu antre;
- ukuran penyimpanan (evidence, jumlah artefak, ukuran database);
- hasil uji restore (catat di `docs/operations.md`).

Dicatat manual: F1 dan kesepakatan per kelas (dari harness), kualitas graf dan stabilitas komunitas (catatan
stabilitas pada tab Jaringan), integritas preservasi (verifikasi hash), dan kegunaan petunjuk dalam aplikasi.

## 5. Aturan selama pilot

- Alur A, B, C, D dijalankan pada target nyata, **termasuk setidaknya dua kali reinspection pada jarak waktu berbeda**.
- Tidak ada perubahan baseline atau ambang secara spekulatif. Perubahan hanya lewat keputusan tertulis (ADR) dengan
  dasar temuan pilot. Parameter indikator koordinasi hanya disesuaikan sebagai parameter `AnalysisRun`.
- Setiap temuan tetap melalui peninjauan manusia; tidak ada vonis tentang operasi berbayar atau pengendali akun.
- Kelemahan yang ditemukan dicatat apa adanya di `hasil-validasi.md`.
