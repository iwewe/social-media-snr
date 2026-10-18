# Kelayakan Instagram

Tanggal pencarian: 2026-10-19. Status: bukan keputusan hukum; lihat [README](README.md).

## 1. Jalur perolehan yang sah
- **Instagram Graph API (Meta).** Endpoint komentar media memerlukan token dari pengguna yang membuat media dan
  izin `instagram_basic` + `instagram_manage_comments` (Facebook Login) atau padanannya pada Instagram Login;
  hanya komentar tingkat atas, maksimum 50 per permintaan, tanpa filter waktu. API hanya untuk akun profesional
  (bisnis/kreator); akses atas akun yang tidak dimiliki memerlukan Advanced Access.
- **Meta Content Library untuk peneliti:** menyediakan konten publik Instagram bagi institusi yang memenuhi syarat
  (lihat Facebook); cakupan komentar tidak terkonfirmasi.
- **Ekspor/dataset impor:** tersedia lewat adapter dataset (WP-1.7).
- **Browser terotorisasi:** syarat layanan belum ditinjau organisasi.

## 2. Kemampuan teruji
Belum ada. Aturan produk: post, carousel, Reel; media dipreservasi dan tidak ditafsirkan (PRD bagian 7).

## 3. Ketahanan parser
Tidak berlaku bila memakai API; untuk browser belum diukur.

## 4. Batasan
Akses terikat kepemilikan akun profesional atau persetujuan Advanced Access; balasan komentar bertingkat dan kelengkapan belum dikonfirmasi.

## 5. Keputusan
- Pengambilan otomatis: **`DISABLED`** sampai organisasi memutuskan jalur (akun yang dikelola, atau Meta Content Library).
- Impor dataset: **`ACTIVE`**.

Sumber: developers.facebook.com/docs/instagram-platform (ig-media/comments, overview).
