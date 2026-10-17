# 0021 - Peran dan anggota tim per investigasi

- **Status:** diterima (A3a: backend). UI (A3b) menyusul. Keputusan kebijakan di bawah adalah asumsi saya yang perlu Anda tinjau.
- **Tanggal:** 2026-10-17

## Konteks

Sampai sekarang semua pengguna terautentikasi melihat dan mengubah semua investigasi (asumsi sementara, ADR 0001-0020).
Tim akan beranggotakan beberapa orang dengan Anda sebagai super admin. PRD bagian 13: "Profil dan temuan individual
diberi akses terbatas, dengan pencatatan perubahan dan peninjauan manusia" dan autentikasi Django dengan izin dasar.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Super admin | `user.is_superuser` (Django). Bukan anggota investigasi; melihat dan mengelola SEMUA. Dibuat hanya lewat `createsuperuser`, tidak lewat API | Satu mekanisme bawaan Django; tidak ada jalur API untuk menaikkan hak ke super admin. |
| Peran per investigasi | `OWNER` (kelola anggota + semua hak MEMBER), `MEMBER` (baca, tulis issue/proposition/target/konteks, jalankan inspeksi, akui tinjauan), `VIEWER` (baca saja, termasuk bukti dan verifikasi hash) | Tiga tingkat cukup untuk pemilik, analis, dan peninjau; peran lebih halus ditunda sampai ada kebutuhan nyata. |
| Non-anggota = tidak ada | Tanpa akses mendapat 404 yang SAMA dengan id yang tidak ada (diuji: badan respons identik); peran kurang mendapat 403 `insufficient_role` | Keberadaan investigasi (dan isinya) tidak bocor ke orang luar. |
| Pembuat jadi OWNER | `create_investigation` membuat keanggotaan OWNER dalam transaksi yang sama; migrasi 0003 membuat OWNER bagi investigasi yang sudah ada | Tanpa itu pemilik lama kehilangan akses. Siapa pun yang terautentikasi boleh membuat investigasi (menjadi pemiliknya). |
| Keanggotaan tidak pernah dihapus | Dicabut lewat `revoked_at/revoked_by`; mengubah peran = mencabut baris lama + baris baru; trigger DB melarang DELETE dan perubahan selain pencabutan satu kali; constraint: satu keanggotaan aktif per (investigasi, pengguna) | Riwayat siapa pernah punya akses tetap ada (selaras dengan append-only). |
| OWNER terakhir | Tidak boleh diturunkan atau dicabut (`last_owner`, 409), termasuk oleh super admin; kunci baris per investigasi membuat dua penurunan bersamaan hanya satu yang berhasil (diuji dengan thread) | Investigasi tanpa pemilik tidak dapat dikelola kecuali lewat basis data. |
| Penegakan terpusat | View memakai `api/access.py` (`investigation_for`, `target_for`, `run_for`, `artifact_for`, `issue_for`); tes statis melarang `get_object_or_404` langsung atas model terlindungi di `api/views.py`; tes matriks (17 endpoint x 5 peran) dan tes yang memastikan setiap rute berid ada di matriks | Endpoint baru tanpa otorisasi gagal di CI, bukan baru ketahuan di produksi. |
| Akun pengguna | `GET/POST /api/users/`, `POST /api/users/<id>/activation/`, `/password/`: hanya super admin (403 `superuser_required`). Nama pengguna unik tanpa membedakan huruf, validasi karakter Django, kata sandi lewat validator Django; tidak dapat menonaktifkan akun sendiri; respons tanpa hash kata sandi | Anggota tim dibuat oleh Anda; tidak ada pendaftaran mandiri. |
| Daftar anggota | Semua peran dapat melihat siapa timnya | Pembaca perlu tahu siapa pemilik/anggota lain. |

## Pertanyaan kebijakan untuk Anda (saya pilih bawaan di bawah; mudah diubah)

1. **Siapa boleh membuat investigasi?** Bawaan: semua pengguna terautentikasi. Alternatif: hanya super admin.
2. **Apakah VIEWER boleh mengunduh isi bukti?** Bawaan: ya (baca saja, hash menjaga keutuhan). Alternatif: hanya MEMBER ke atas.
3. **Siapa boleh mengakui tinjauan (`REVIEW_REQUIRED`)?** Bawaan: MEMBER ke atas. Alternatif: hanya OWNER.
4. **Kata sandi awal anggota:** Anda yang mengisinya (lalu memberitahu orangnya). Belum ada "wajib ganti saat login pertama" maupun pengiriman email.

## Batas yang diketahui

- Belum ada AuditEvent umum (WP-2.8). Riwayat keanggotaan tersimpan, tetapi tindakan data (siapa mengubah apa) hanya tercatat
  pada objek yang memang menyimpan pembuatnya.
- Peran berlaku per investigasi; belum ada pembagian hak per platform atau per target.
- Penguncian login (django-axes) tetap berlaku; belum ada MFA.
- Frontend belum menampilkan peran, daftar tim, atau halaman akun (A3b).
