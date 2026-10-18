# Kelayakan Facebook

Tanggal pencarian: 2026-10-19. Status: bukan keputusan hukum; lihat [README](README.md).

## 1. Jalur perolehan yang sah
- **Meta Content Library dan API untuk peneliti.** Sumber resmi: konten publik (Facebook, Instagram, WhatsApp
  Channels); pemohon harus berafiliasi dengan institusi yang memenuhi syarat (akademik terakreditasi atau organisasi
  nirlaba dengan penelitian ilmiah/kepentingan publik sebagai kegiatan utama), tidak berada di yurisdiksi bersanksi,
  tanpa biaya, dengan sertifikasi ulang tahunan; keluaran di platform peneliti dihapus berkala (30 hari). Sumber lama
  menyebut pendaftaran lewat ICPSR; halaman resmi (diperbarui 2026-04-30) menyebut Research Tools Manager dengan
  peninjauan CASD. **Cakupan komentar tidak terkonfirmasi.**
- **Graph API untuk Page yang dikelola organisasi:** terikat izin dan peninjauan aplikasi Meta.
- **Ekspor/dataset impor:** tersedia lewat adapter dataset (WP-1.7).
- **Browser terotorisasi:** syarat layanan belum ditinjau organisasi.

## 2. Kemampuan teruji
Belum ada. Aturan produk: post dan konteks Page/ruang publik yang sah; jenis ruang asal dan pembatasan akses dicatat (PRD bagian 7).

## 3. Ketahanan parser
Tidak berlaku bila memakai API; untuk browser belum diukur.

## 4. Batasan
Konten privat/grup tertutup di luar cakupan; kelayakan institusi dan proses aplikasi harus dinilai organisasi.

## 5. Keputusan
- Pengambilan otomatis: **`DISABLED`** sampai kelayakan dinilai dan persetujuan akses diperoleh.
- Impor dataset: **`ACTIVE`**.

Sumber: developers.facebook.com/docs/content-library-and-api (faqs, get-access); transparency.meta.com (research tools).
