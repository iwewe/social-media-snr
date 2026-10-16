# 0002 - Autentikasi dan pembatasan login

- **Status:** diterima (usulan implementasi WP-0.3; angka belum disepakati)
- **Tanggal:** 2026-10-16

## Konteks

PRD FR-001 dan FR-006 menetapkan Django Authentication, semua data tidak dapat diakses tanpa login,
dan izin dasar lewat Django Groups/Permissions. PRD bagian 13 meminta pembatasan percobaan login
tetapi tidak menetapkan angka.

## Keputusan

- Wajib-login **global** memakai `LoginRequiredMiddleware` bawaan Django 5.2. Pengecualian hanya
  lewat `@login_not_required`; saat ini hanya halaman login aplikasi (`/accounts/login/`) dan login
  admin Django.
- Tes `test_every_url_requires_login_except_whitelist` mengenumerasi seluruh URL pattern dan gagal
  jika ada path di luar daftar putih yang dapat diakses anonim.
- Pembatasan login: `django-axes`, kunci per kombinasi IP + username. Nilai awal **usulan**: 5
  kegagalan, jeda 15 menit (`AXES_FAILURE_LIMIT`, `AXES_COOLOFF_MINUTES`). Belum ada keputusan.
- Satu grup dasar `analyst` dibuat lewat migrasi data tanpa izin; izin ditambah saat model domain ada.

## Keterbatasan yang diketahui

- URL yang tidak terpetakan menghasilkan 404 untuk anonim (middleware hanya berjalan pada URL
  terpetakan). Tidak membocorkan halaman nyata.
- Dua pola regex kompleks tidak ikut dienumerasi oleh tes.
- Di belakang reverse proxy, IP klien untuk axes harus dikonfigurasi (ditunda ke WP-3.6 bersama
  HTTPS). Cookie sesi belum ditandai `Secure` karena HTTPS belum ada.
