# Kelayakan X

Tanggal pencarian: 2026-10-19. Status: bukan keputusan hukum; lihat [README](README.md).

## 1. Jalur perolehan yang sah
- **API resmi (X API v2).** Dokumentasi resmi menyatakan balasan sebuah posting dapat diambil dengan operator
  `conversation_id:<id posting akar>` pada endpoint pencarian terbaru; ID percakapan sama dengan ID posting akar.
- **Model biaya.** Catatan perubahan resmi menggambarkan model berbasis pemakaian; sumber pihak ketiga berbeda
  tentang paket tetap lama (Basic/Pro). Harga baca untuk pencarian **belum dapat dipastikan** dari sumber resmi
  yang ditemukan dan harus dicek langsung di halaman resmi sebelum keputusan.
- **Ekspor/dataset impor:** tersedia lewat adapter dataset (WP-1.7) bila organisasi memiliki data yang sah.
- **Browser terotorisasi:** syarat layanan belum ditinjau organisasi; tidak diasumsikan boleh.

## 2. Kemampuan teruji
Belum ada pengujian terhadap platform. Yang tercatat hanya yang dinyatakan dokumentasi: posting dan balasan
lewat pencarian percakapan; urutan hasil terbalik kronologis; pagination via token. Cakupan balasan (batas jendela
pencarian, retweet tidak lagi muncul pada pencarian kata kunci sejak 2026-05-04 menurut catatan perubahan resmi)
membatasi kelengkapan dan harus tampil sebagai `PARTIAL`, bukan lengkap.

## 3. Ketahanan parser
Tidak berlaku bila memakai API; untuk browser belum diukur.

## 4. Batasan yang diketahui dari sumber
Dibatasi kuota/biaya; kelengkapan tidak dijamin; objek tertentu (mis. Following, Likes, Quote-Posts) disebut
dihapus dari tingkat self-serve oleh catatan perubahan resmi.

## 5. Keputusan
- Pengambilan otomatis: **`DISABLED`** sampai organisasi memutuskan memakai API resmi dan menyediakan kredensial.
- Impor dataset: **`ACTIVE`**.
- Syarat membuka: lihat daftar pada README; tambahan khusus X: tetapkan anggaran pemakaian dan batas per-run.

Sumber: docs.x.com (conversation-id, changelog). Sumber pihak ketiga tentang harga tidak dipakai.
