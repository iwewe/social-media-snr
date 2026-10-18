# Kelayakan Threads

Tanggal pencarian: 2026-10-19. Status: bukan keputusan hukum; lihat [README](README.md).

## 1. Jalur perolehan yang sah
- **Threads API resmi (Meta).** Dokumentasi resmi: izin `threads_basic` diperlukan untuk semua endpoint dan
  `threads_read_replies` untuk membaca balasan; endpoint percakapan `/{MEDIA_ID}/conversation` dimaksudkan untuk
  thread tingkat akar yang memiliki balasan.
- **Belum diverifikasi:** apakah akses ke posting milik akun lain (bukan pemilik token) diizinkan untuk kebutuhan
  investigasi, dan bentuk persis endpoint balasan; harus dicek pada dokumentasi dan Graph API Explorer.
- **Ekspor/dataset impor:** tersedia lewat adapter dataset (WP-1.7).
- **Browser terotorisasi:** syarat layanan belum ditinjau organisasi.

## 2. Kemampuan teruji
Belum ada pengujian. Threads tidak diasumsikan identik dengan X (PRD bagian 7).

## 3. Ketahanan parser
Tidak berlaku bila memakai API; untuk browser belum diukur.

## 4. Batasan
Izin dan peninjauan aplikasi Meta berlaku; ruang lingkup akses atas konten pihak lain belum terverifikasi.

## 5. Keputusan
- Pengambilan otomatis: **`DISABLED`** sampai organisasi memutuskan dan akses yang sah terbukti mencakup kebutuhan ini.
- Impor dataset: **`ACTIVE`**.

Sumber: developers.facebook.com/docs/threads (retrieve-and-manage-replies, changelog). Tutorial pihak ketiga
berbeda soal nama izin; dokumentasi Meta yang dipakai.
