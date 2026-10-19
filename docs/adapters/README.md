# Kelayakan dan izin per platform (WP-3.0)

Satu dokumen per platform. Format dan batasnya mengikuti rencana WP-3.0 dan PRD bagian 7 dan 13.

**Keputusan organisasi (2026-10-19):** jalur tunggal untuk semua platform adalah pemeriksaan browser dengan sesi
milik operator, dipicu manual dan tidak berjalan otomatis; lihat [keputusan-organisasi.md](keputusan-organisasi.md).
Tabel di bawah menunjukkan status adapter, bukan jalur yang dipilih.

## Pernyataan yang berlaku untuk semua platform

- Tidak ada mekanisme untuk melewati CAPTCHA, pembatasan akses, atau larangan platform. Login browser bukan
  persetujuan untuk pengumpulan otomatis. Bila jalur yang sah tidak ada atau belum disetujui, adapter melaporkan
  `UNSUPPORTED` / `ACCESS_RESTRICTED` dan UI menampilkan alasannya.
- **Tim developer tidak menyimpulkan legalitas.** Dokumen ini mencatat apa yang dinyatakan sumber resmi pada
  tanggal tertulis, apa yang belum diverifikasi, dan apa yang harus diputuskan organisasi. Izin, syarat layanan,
  dan kelayakan sebagai peneliti/penerima akses adalah keputusan organisasi/pengguna di luar kode (PRD bagian 1).
- Sumber berupa blog atau vendor pihak ketiga hanya dipakai sebagai petunjuk dan ditandai; tidak dijadikan dasar keputusan.
- Pengukuran ketahanan parser (seberapa sering struktur halaman berubah) membutuhkan pengamatan berulang atas
  akses yang sah; **belum dilakukan** untuk platform mana pun.

## Matriks keputusan saat ini (2026-10-19)

| Platform | Jalur yang sah (ringkasan) | Pengambilan otomatis | Impor dataset (WP-1.7) |
|---|---|---|---|
| [X](x-feasibility.md) | API resmi berbayar sesuai pemakaian | `DISABLED` (menunggu keputusan organisasi) | `ACTIVE` |
| [Threads](threads-feasibility.md) | API resmi Meta, terutama untuk akun milik sendiri | `DISABLED` (menunggu keputusan organisasi) | `ACTIVE` |
| [TikTok](tiktok-feasibility.md) | Research API (peneliti nirlaba/akademik, melalui aplikasi) | `DISABLED` (menunggu kelayakan dan persetujuan) | `ACTIVE` |
| [Instagram](instagram-feasibility.md) | Graph API untuk akun profesional yang dikelola; Meta Content Library untuk peneliti | `DISABLED` (menunggu keputusan organisasi) | `ACTIVE` |
| [Facebook](facebook-feasibility.md) | Meta Content Library untuk peneliti; Graph API untuk Page yang dikelola | `DISABLED` (menunggu kelayakan dan persetujuan) | `ACTIVE` |

`DISABLED` berarti: adapter platform terpasang tetapi seluruh kemampuannya dinyatakan tidak didukung beserta alasan
yang mengarah ke dokumen ini (`backend/collection/adapters/`). Mengaktifkan satu kemampuan membutuhkan: (1) keputusan
tertulis organisasi, (2) kredensial/izin akses yang sah, (3) rekaman respons sah sebagai fixture, (4) lulus suite
kontrak dan uji AT-13/AT-14 untuk adapter itu, lalu (5) pembaruan dokumen platform ini.

Impor dataset (format di `docs/format-dataset-impor.md`) tetap menjadi jalur yang tersedia untuk semua platform
selama data berasal dari sumber yang sah; pencatatan sumbernya ada pada `source_method` observasi.

Uji adapter X: lihat [x-rekaman-halaman.md](x-rekaman-halaman.md) (rekaman halaman ditangkap operator, dianonimkan sebelum masuk Git).
