# 0022 - UI tim, peran, dan akun

- **Status:** diterima (A3b). Melengkapi ADR 0021 (backend).
- **Tanggal:** 2026-10-17

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| UI menyesuaikan, server menegakkan | `canWrite` (ADMIN/OWNER/MEMBER) dan `canManage` (ADMIN/OWNER) hanya menyembunyikan atau menonaktifkan kontrol; setiap aksi tetap ditolak server (403/404) bila peran kurang | Tampilan bukan batas keamanan. Tes matriks backend (ADR 0021) adalah penegaknya. |
| Pembaca | Catatan "Anda berperan Pembaca", tanpa formulir issue/proposition/target, tanpa revisi catatan, Inspect nonaktif beralasan, tinjauan hanya dijelaskan; data, hasil inspeksi, bukti, dan verifikasi tetap terlihat | Peran baca-saja yang tetap berguna bagi peninjau. |
| Panel Tim | Semua peran melihat anggota (peran, sejak kapan, ditambahkan oleh); Pemilik dan Super admin menambah (nama pengguna + peran), mengubah peran lewat pilihan, dan mencabut dengan konfirmasi dua langkah ("Cabut akses?" / "Keluar dari investigasi?"). Aturan server (OWNER terakhir, anggota ganda, akun tak dikenal/nonaktif) ditampilkan apa adanya | Pencabutan tidak boleh terjadi karena satu klik tak sengaja; pesan server satu-satunya sumber aturan. |
| Halaman Akun (`/users`) | Khusus super admin: daftar akun (status, masuk terakhir, jumlah investigasi), buat akun, aktifkan/nonaktifkan (akun sendiri terkunci), atur kata sandi. Pengguna biasa melihat penolakan tanpa memanggil API; tautan "Akun" hanya muncul bagi super admin | Anda membuat akun anggota; tidak ada pendaftaran mandiri. |
| Kata sandi | Kolom `type=password`, `autocomplete=new-password`; setelah dikirim kolom dikosongkan; kata sandi tidak pernah ditampilkan kembali (diuji pada DOM) | Menghindari kebocoran lewat layar, riwayat isian, atau salinan. |
| Lencana peran | Tampil pada daftar dan halaman investigasi (Pemilik / Anggota / Pembaca / Super admin) dengan penjelasan di tooltip; `my_role` juga ada pada detail run agar hak "akui tinjauan" mengikuti peran | Pengguna selalu tahu apa yang boleh dilakukannya. |
| Petunjuk | `teamRoles` ditambahkan (PRD 12, FR-004): tiga peran, non-anggota tidak melihat investigasi, riwayat tidak dihapus | |

## Catatan temuan selama pengujian

- Aturan CSS global `select { width: auto }` mengubah formulir target sehingga popover petunjuk menutupi tombol "Daftarkan target"
  (ditangkap E2E lama). Aturan dipersempit ke `td select`.
- Aturan `.message > strong` (judul pesan run) memecah catatan "Anda berperan Pembaca" menjadi tiga baris (tangkapan layar);
  diganti elemen sebaris dan dijaga tes.
- Tes menangkap dua kekurangan kode: tombol "Revisi catatan" masih tampil bagi Pembaca; dan mock respons 204 yang tidak sah membuat
  tes pencabutan lulus semu sampai mock diperbaiki.

## Batas yang diketahui

- Belum ada "wajib ganti kata sandi saat login pertama", pengiriman email, atau MFA.
- Tidak ada antarmuka untuk melihat riwayat keanggotaan (hanya anggota aktif); riwayat tersimpan di basis data.
- Super admin tidak dapat dibuat atau dicabut lewat UI (hanya `createsuperuser`).
