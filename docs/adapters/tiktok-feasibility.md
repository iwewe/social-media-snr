# Kelayakan TikTok

Tanggal pencarian: 2026-10-19. Status: bukan keputusan hukum; lihat [README](README.md).

## 1. Jalur perolehan yang sah
- **Research API resmi.** Sumber resmi menyebut akses untuk peneliti independen/akademik yang bekerja pada institusi
  nirlaba (kodebuku menyebut universitas nirlaba di AS dan Eropa), dengan persetujuan etik institusi. Terdapat
  endpoint komentar video (teks, jumlah suka dan balasan, waktu). Pengalaman satu lembaga riset independen melaporkan
  proses panjang dan tafsir kelayakan yang sempat sempit; itu laporan satu organisasi, bukan kebijakan.
- **Kelayakan organisasi ini belum dinilai**; hanya organisasi yang memenuhi kriteria yang dapat mengajukan.
- **Ekspor/dataset impor:** tersedia lewat adapter dataset (WP-1.7).
- **Browser terotorisasi:** syarat layanan belum ditinjau organisasi.

## 2. Kemampuan teruji
Belum ada. Aturan produk: video dan caption dipreservasi dan tidak ditranskrip (PRD bagian 7).

## 3. Ketahanan parser
Tidak berlaku bila memakai API; untuk browser belum diukur.

## 4. Batasan
Kuota dan syarat Research API; kriteria berubah dari waktu ke waktu dan harus dicek pada halaman resmi sebelum mengajukan.

## 5. Keputusan
- Pengambilan otomatis: **`DISABLED`** sampai kelayakan dinilai dan persetujuan akses diperoleh.
- Impor dataset: **`ACTIVE`**.

Sumber: developers.tiktok.com (about-research-api, research-api-codebook). Blog vendor tentang batas/alternatif tidak dipakai.
