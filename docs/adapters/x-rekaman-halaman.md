# Rekaman halaman X untuk uji adapter (WP-3.1)

Sesuai [keputusan organisasi](keputusan-organisasi.md) pemeriksaan X dilakukan lewat browser dengan sesi operator.
Agar parser adapter dibangun dan diuji terhadap **struktur halaman yang nyata** (bukan tebakan), operator menyediakan
rekaman halaman yang ditangkap sendiri. Pengambilan ini dilakukan manusia di browsernya sendiri; tim developer tidak
mengakses x.com dari CI atau dari mesin lain untuk keperluan ini.

Target uji awal: `https://x.com/Alitt4mb3ng/status/2111742533080625549` (URL valid untuk adapter X; ID posting
`2111742533080625549`).

## Cara menangkap (operator)

1. Di browser Anda yang sudah login ke X, buka URL target. Gulir sampai balasan yang ingin diuji termuat
   (cukup beberapa layar; tidak perlu seluruhnya).
2. Simpan halaman sebagai HTML: `Ctrl+S` lalu pilih "Webpage, HTML only" (atau "Webpage, Complete"). Satu berkas
   `.html` cukup. Jangan memakai ekstensi yang mengunggah halaman ke layanan lain.
3. Catat di berkas teks terpisah: tanggal dan jam tangkap (zona waktu), bahasa antarmuka X, apakah Anda login, dan apakah
   ada balasan yang sengaja tidak dimuat (mis. "tampilkan balasan lain" tidak diklik).
4. Kirim kedua berkas ke VM dengan `scp` ke `~/capture/` (direktori dibuat dengan izin 700). **Jangan** menempelkannya
   ke percakapan atau memasukkannya ke Git.

## Yang akan dilakukan tim developer terhadap rekaman

- Rekaman asli **tidak masuk Git**. Berkas di VM diperlakukan setara bukti (izin 600).
- Fixture untuk tes dibuat dari rekaman itu setelah **dianonimkan**: nama pengguna, nama tampilan, teks, dan tautan diganti
  nama samaran deterministik; struktur HTML dipertahankan. Fixture anonim itulah yang masuk Git.
- Parser diuji terhadap fixture anonim (pure, tanpa jaringan). Bila struktur halaman tidak sesuai harapan, hasilnya
  `PARSE_FAILED` atau `PARTIAL`, bukan data kosong.
- Rekaman asli dapat dihapus setelah fixture disetujui; backup yang sudah ada tidak ikut terhapus otomatis.

## Catatan privasi

Rekaman memuat akun dan teks pihak ketiga. Gunakan hanya untuk uji adapter ini, jangan dibagikan, dan hapus bila tidak
diperlukan lagi. Keputusan retensi final belum ada (lihat `docs/operations.md`).
