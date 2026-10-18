# 0032 — Antarmuka analisis I2 (WP-2.7b)

Status: diterima. Tanggal: 2026-10-18.

## Keputusan

- Satu halaman `/investigations/:id/analysis` dengan empat tab: Respons, Jaringan, Profil akun, Temuan.
  Tab dipilih lewat query `?tab=`; tautan "Analisis" ada di halaman investigasi.
- Setiap hasil membawa lencana kategori dari server (`category`/`category_label`): Fakta observasi,
  Hasil mesin, Ditinjau manusia, Temuan yang telah ditinjau (FR-094). Draf temuan memakai lencana
  "Draf temuan (belum ditinjau)", bukan "Temuan yang telah ditinjau".
- Graf memakai Cytoscape. Edge interaksi = garis penuh berpanah berwarna per jenis relasi; edge
  kemiripan perilaku (indikator CO) = garis putus-putus oranye tanpa panah, dengan legenda yang
  menyatakan bahwa itu bukan interaksi dan bukan bukti koordinasi (AT-12). Warna node adalah
  atribut stance hasil mesin, bukan label akun.
- Profil akun menampilkan pernyataan cakupan di atas tabel; dimensi tanpa data cukup tampil
  "data belum cukup", bukan nol.
- Temuan: formulir memuat empat sumbu bukti (dengan saran sistem dan alasan override), empat
  hipotesis alternatif, confidence + alasan. Plafon confidence dan larangan vonis tetap ditegakkan
  server; UI hanya menampilkan pesannya. Sahkan/tarik/revisi hanya untuk Anggota ke atas.
- Jejak bukti: laci (drawer) per observasi lewat `/api/observations/{id}/`.
- Tidak ada elemen UI bertema skor/peringkat/kecurigaan; dijaga tes komponen, tes teks bantuan,
  tes arsitektur identifier, dan E2E.

## Alasan

Pengguna harus dapat menelusuri dari hasil ke bukti dan membedakan fakta, hasil mesin, dan temuan
yang disahkan manusia. Pembedaan visual interaksi vs kemiripan mencegah pembacaan kesamaan perilaku
sebagai hubungan nyata.

## Batas yang diketahui

- Analisis belum dapat dipicu dari UI (hanya `manage.py run_analyses`); halaman menjelaskan hal ini
  bila belum ada analisis.
- Navigasi satu klik node/edge/label/temuan → observasi dan halaman jejak versi lengkap menunggu WP-2.8
  (AuditEvent).
- Graf dibatasi `max_nodes` (300) di server; tata letak cose belum diukur pada graf besar.
- E2E memakai data sample hasil `run_analyses` (nilai contoh eksploratori); alur pembuatan/pengesahan
  temuan di browser baru diuji pada tingkat formulir, bukan simpan-sahkan.
