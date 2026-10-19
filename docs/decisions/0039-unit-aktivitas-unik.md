# 0039 — Satu Post = satu aktivitas (M3 dan M4)

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti temuan 3.1 pada `analisis-snr.txt` (pemeriksaan commit `63a2104`).

## Masalah

Profil M3 dan jaringan M4 menghitung SETIAP observasi. Satu komentar yang sama pada empat inspeksi terhitung empat
respons (partisipasi, distribusi stance, karakter, aktivitas temporal), empat teks dalam kelompok pengulangan
(konsistensi narasi), dan menambah bobot dan stance edge dengan relasi yang sama. Akibatnya akun tampak lebih aktif
dan lebih repetitif, dan frekuensi pengamatan terbaca sebagai intensitas interaksi sosial, hanya karena diperiksa
lebih sering. Indikator koordinasi (WP-2.5) sudah memakai satu Post = satu respons, sehingga unit hitung antarbagian
analisis tidak konsisten.

## Keputusan

- **Unit aktivitas = Post.** Untuk M3 dan M4, setiap Post diwakili oleh **observasi terbarunya dalam dataset**
  (urutan sequence run, lalu id), aturan yang sama dengan indikator koordinasi. Penilaian M2 yang dipakai, waktu
  publikasi, dan teks berasal dari observasi itu.
- **Observasi lama tetap bukti historis** dan dilaporkan terpisah, tidak dihitung sebagai aktivitas:
  - M3 `participation`: `responses` (unik), `observations` (riwayat), `responses_with_changed_text`, dan `unit`.
    `coverage.observations_collapsed_into_unique_posts` dan keluaran run mencatat jumlah observasi yang disatukan.
    Cakupan (`runs_covered`, `targets_covered`) tetap mencatat SEMUA pemeriksaan yang berkontribusi.
  - M4: relasi dari observasi lama dilewati dan dihitung pada `exclusions.relation_from_superseded_observation`;
    bobot edge = jumlah Post berbeda; `stance_counts` edge dan node per Post (observasi terbaru); atribut node
    `posts` (unik) dan `observations` (riwayat).
- **Perubahan teks bukan aktivitas baru:** dilaporkan (`responses_with_changed_text`), dan teks serta stance terbaru yang
  dipakai. Komentar yang benar-benar baru pada inspeksi berikutnya menambah tepat satu aktivitas.
- **Versi metode dinaikkan:** `m3-profile` dan `m4-network` menjadi versi `2`. Run lama (versi 1) tidak diubah
  (append-only) dan tetap memakai aturan lama; jalankan ulang analisis untuk hasil dengan aturan baru.
- Antarmuka: daftar profil menyatakan "respons unik" dan, bila ada riwayat, jumlah observasi historis serta teks
  yang berubah; detail node graf menyatakan Post unik dan observasi historis.

## Alasan

Reinspection harus menambah bukti dan riwayat, bukan mengubah angka aktivitas (FR-062; prinsip reinspection tanpa
penggandaan). Memakai satu aturan pemilihan versi di seluruh analisis menjaga angka M3, M4, dan indikator koordinasi
dapat dibandingkan.

## Batas yang diketahui

- Bila relasi suatu Post berbeda antar-inspeksi (mis. induk berubah), hanya relasi pada observasi terbaru yang dihitung;
  relasi lama dilaporkan sebagai pengecualian, tidak digabung.
- Aturan "observasi terbaru" bergantung pada urutan run dalam dataset; Post yang hanya muncul pada run lama (menghilang
  kemudian) tetap diwakili observasi terakhirnya yang teramati.
- Run M3/M4 versi 1 yang sudah ada tidak dihitung ulang otomatis.
