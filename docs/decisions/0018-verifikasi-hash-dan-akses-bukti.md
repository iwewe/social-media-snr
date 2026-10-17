# 0018 - Verifikasi hash dan akses isi artefak bukti

- **Status:** diterima (WP-1.10; menutup I1).
- **Tanggal:** 2026-10-17

## Konteks

FR-040: pengguna dapat memverifikasi hash artefak dan membuka rujukan bukti sesuai hak akses. PRD bagian 10 membatasi
pernyataan yang boleh dibuat: hash memeriksa apakah berkas yang tersimpan masih sama dengan saat di-hash, dan **tidak**
membuktikan konten platform autentik, lengkap, atau benar secara faktual.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Hitung ulang dari disk | Verifikasi membaca berkas dan menghitung SHA-256 + ukuran; catatan basis data hanya pembanding | Memeriksa catatan terhadap dirinya sendiri tidak membuktikan apa pun. |
| Empat hasil | `MATCH`, `MISMATCH` (hash atau ukuran berbeda), `MISSING`, `UNREADABLE` (jalur tidak sah, symlink, bukan berkas biasa, galat baca) | Kegagalan tidak pernah disamarkan jadi cocok; tiap hasil punya pesan sendiri. |
| Berkas dibuka sekali | Hash dan aliran unduhan memakai deskriptor yang sama; `O_NOFOLLOW`, `O_NONBLOCK`, dan pemeriksaan berkas biasa (`S_ISREG`) | Penggantian jalur setelah pemeriksaan tidak berpengaruh; FIFO tidak menggantung pekerja; direktori/perangkat ditolak. Diuji, termasuk kebocoran deskriptor. |
| Symlink | Komponen jalur berupa symlink selalu `UNREADABLE`, walau isinya identik | Bukti yang jalurnya dibelokkan tidak boleh dianggap utuh. |
| Riwayat append-only | `ArtifactVerification` (siapa, kapan, tujuan, hasil, hash/ukuran diharapkan dan dihitung) dengan trigger DB dan constraint `MATCH` mensyaratkan hash sama. Ketidakcocokan yang pernah terjadi tetap tercatat walau berkas kemudian dipulihkan | Ketidakcocokan adalah kejadian, bukan keadaan sesaat. Jalur berkas tidak pernah dicatat. |
| Manifest sebagai sumber kedua | `verify_run` memverifikasi semua artefak dan membandingkan manifest terbaru dengan catatan DB (hash, ukuran, daftar, run). Manifest yang sendiri tidak lolos hash `UNTRUSTED` dan isinya tidak dipakai | Dua sumber independen (DB dan berkas manifest) saling memeriksa. |
| Isi hanya bila hash cocok | `GET /api/artifacts/<id>/content/` menolak 409 `artifact_integrity_failed` untuk selain `MATCH` (termasuk nama berkas menyerupai rahasia lewat `ensure_exportable`); setiap akses dicatat sebagai verifikasi `download` | Menyajikan bukti yang berubah tanpa peringatan lebih berbahaya daripada menolaknya; rinciannya ada di endpoint verifikasi. |
| Isi tidak dipercaya | Selalu lampiran `application/octet-stream` kecuali jenis `screenshot` bergambar aman (png/jpeg/webp/gif) yang inline; `nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, `no-store`, CORP same-origin; nama unduhan dibuat sendiri | DOM/HTML dari platform tidak boleh dieksekusi pada origin aplikasi (XSS). SVG dan jenis salah-label tidak pernah inline (diuji). |
| UI | Verifikasi per artefak dan "Verifikasi semua"; hasil tampil dengan role alert untuk kegagalan; Unduh memverifikasi dulu dan hanya mengunduh bila `MATCH`; pernyataan integritas selalu terlihat | Pengguna tidak dapat membawa pulang berkas yang tidak utuh tanpa melihat alasannya. |
| Hak akses | Pengguna terautentikasi (aturan yang sama dengan seluruh API) | Pembedaan peran menunggu WP-3.6; belum ada model hak per investigasi. |

## Batas yang diketahui

- Hash tidak mendeteksi penggantian berkas **beserta** catatan DB dan manifest sekaligus; perlindungan terhadap itu perlu
  cadangan terpisah dan kontrol akses server (operasional, WP-3.6).
- Berkas yang diubah di tempat di antara hash dan pembacaan aliran (deskriptor sama) masih mungkin; berkas dibuat
  read-only (0444) dan unduhan besar tidak di-hash dua kali. Risiko diterima untuk MVP lokal.
- Verifikasi besar (ratusan MiB) berjalan sinkron di permintaan web; belum ada tugas latar belakang.
- Riwayat verifikasi tidak punya antarmuka penelusuran lengkap (hanya yang terakhir per artefak).
- Pembedaan peran (mis. hanya peninjau yang boleh mengunduh) belum ada.
