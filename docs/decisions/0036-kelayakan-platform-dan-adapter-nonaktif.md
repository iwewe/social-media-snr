# 0036 — Kelayakan platform dan adapter nonaktif (WP-3.0 s.d. 3.5)

Status: diterima. Tanggal: 2026-10-19.

## Keputusan

- **WP-3.0:** satu dokumen kelayakan per platform di `docs/adapters/` (X, Threads, TikTok, Instagram, Facebook)
  dengan lima bagian dari rencana: jalur perolehan yang sah, kemampuan teruji, ketahanan parser, batasan,
  keputusan. Isinya merangkum apa yang dinyatakan sumber resmi pada 2026-10-19, menandai sumber pihak ketiga yang
  tidak dipakai, dan memisahkan yang belum diverifikasi. Tim developer **tidak menyimpulkan legalitas**; kelayakan
  sebagai penerima akses, syarat layanan, dan izin adalah keputusan organisasi.
- **Keputusan awal untuk kelima platform: pengambilan otomatis `DISABLED`, impor dataset `ACTIVE`.** Alasannya:
  tidak ada akses yang sah dan disetujui yang dapat diuji hari ini; jalur resmi yang ada (API berbayar, akses
  peneliti, akun yang dikelola) membutuhkan keputusan, kredensial, atau kelayakan yang hanya dapat diberikan organisasi.
  Ini mengikuti rekomendasi dan prinsip PRD: hanya kemampuan yang diuji dan diizinkan yang dinyatakan aktif.
- **WP-3.1 s.d. 3.5:** satu adapter per platform (`collection/adapters/<platform>`) berbagi dasar
  `PendingPermissionAdapter`. Yang diimplementasikan dan diuji: validasi URL spesifik platform (posting vs akun,
  tautan pendek, jalur yang dicadangkan; ID stabil HANYA diambil bila ID pada URL sama dengan ID platform: posting X
  dan video TikTok; kode Threads/Instagram dan ID gabungan Facebook tidak dijadikan ID), serta pernyataan
  kemampuan: setiap `Capability` `UNTESTED` dengan alasan yang menunjuk dokumen kelayakan. Gerbang
  `Adapter.inspect` karenanya menjawab `UNSUPPORTED` dengan alasan itu (UI menampilkannya), dan `collect` tidak dapat
  dijangkau (sengaja gagal bila dipanggil langsung). **Tidak ada kode pengambilan data.**
- **Pendaftaran:** `register_disabled_adapters` (dipanggil di `CollectionConfig.ready`) mendaftarkan adapter nonaktif
  hanya untuk platform yang belum punya adapter; dataset, simulasi, dan `SNR_ADAPTERS` tetap menang.
- **Mengaktifkan satu kemampuan** membutuhkan: keputusan tertulis organisasi, akses yang sah, fixture rekaman yang
  sah, lulus suite kontrak dan AT-13/AT-14 untuk adapter itu, dan pembaruan dokumen platform. Sampai itu terpenuhi
  kelas nonaktif tidak boleh dilonggarkan.

## Alasan

Rencana menempatkan feasibility sebelum adapter dan menyatakan verifikasi izin di luar kode. Membangun adapter
pengambilan data tanpa akses yang sah akan memaksa menebak struktur respons dan berisiko menormalkan jalur yang
dilarang. Yang dapat dikerjakan dengan benar sekarang adalah memastikan sistem jujur: platform tanpa akses
terdaftar sebagai tidak didukung dengan alasan yang jelas, URL tervalidasi, dan jalur impor dataset sah tetap tersedia.

## Batas yang diketahui

- Tidak ada pengamatan terhadap platform nyata; ketahanan parser belum diukur untuk platform mana pun.
- Informasi dokumen dapat usang (harga, kriteria, endpoint); tiap dokumen bertanggal dan perlu dicek ulang
  sebelum keputusan organisasi.
- Pola URL dibuat dari bentuk URL publik yang dikenal; perubahan format platform dapat membuat URL valid ditolak
  (aman: ditolak, bukan salah diklasifikasi). Tautan pendek tidak dapat dibedakan jenisnya tanpa jaringan.
- Exit criteria I3 ("kemampuan yang diuji dan diizinkan dinyatakan aktif") terpenuhi secara hampa: tidak ada
  kemampuan aktif; AT-13/AT-14 untuk adapter aktif belum berlaku karena belum ada adapter aktif.
