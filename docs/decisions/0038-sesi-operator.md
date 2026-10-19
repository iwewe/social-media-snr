# 0038 — Sesi operator pada profil browser (WP-3.1, persiapan adapter X)

Status: diterima. Tanggal: 2026-10-19.

## Keputusan

- Menindaklanjuti keputusan organisasi (browser dengan sesi milik operator), ditambahkan `manage.py browser_session`
  (`import`, `status`, `clear`) yang berjalan di worker-browser dan menulis hanya ke profil
  `browser-profiles/<platform>` (dibuat 0700) lewat `BrowserSession` yang sudah ada.
- Format masukan: `storage_state` Playwright atau daftar cookie hasil ekspor ekstensi browser. Hanya cookie domain
  platform yang dipilih diterima; yang lain dibuang dan dihitung; tanpa satu pun cookie platform, impor ditolak.
- **Nilai cookie tidak pernah dicetak, dilog, atau masuk pesan galat/ringkasan**: hanya jumlah, nama, dan kedaluwarsa
  paling awal. Masukan dapat dari stdin agar tidak ada berkas tersisa; `--delete-source` menghapus berkas sumber.
- **Cookie sesi tidak bertahan di profil Chromium** (diuji: cookie tanpa kedaluwarsa hilang saat konteks ditutup). Maka
  impor memberi cookie semacam itu umur eksplisit `--session-days` (bawaan 7; 0 = tidak diubah) dan melaporkannya.
  Alternatif berkas `storage_state` terpisah ditolak agar tidak ada penyimpanan kredensial kedua di luar profil.
- Rekaman halaman untuk uji parser ditangkap manusia (operator) dan dianonimkan sebelum masuk Git
  (`docs/adapters/x-rekaman-halaman.md`); tim developer tidak mengakses x.com untuk keperluan itu.

## Alasan

Adapter browser membutuhkan sesi login; menyediakannya lewat jalur yang aman (profil terpisah, izin ketat, tanpa nilai
pada keluaran) menjaga aturan PRD bagian 13. Pengujian dengan Chromium nyata mengungkap perilaku cookie sesi yang
akan membuat sesi "hilang" tanpa diketahui bila tidak ditangani.

## Batas yang diketahui

- Impor tidak menguji apakah sesi masih valid di platform (itu butuh akses ke platform; ditunda ke adapter).
- Cookie yang diberi umur buatan tetap berlaku di mesin ini selama umur itu meski sesi platform telah dicabut; operator
  menghapusnya dengan `clear` bila perlu. Profil tidak dienkripsi; perlindungannya izin OS dan pengecualian dari backup.
- Mengimpor sesi bukan jawaban atas kebolehan memakainya; keputusan organisasi dan peninjauan syarat layanan tetap berlaku.
