# 0040 — Isolasi platform dan dataset pada tampilan jaringan

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti temuan 3.2 pada `analisis-snr.txt` (pemeriksaan commit `63a2104`).

## Masalah

Backend membatasi dataset dan graf per platform, tetapi `NetworkPanel` memilih run graf dan run indikator koordinasi
secara terpisah dan meneruskan keduanya ke `buildElements` tanpa memeriksa platform atau dataset. `buildElements` juga
menambahkan akun dari indikator yang belum ada di graf sebagai node tambahan. Hasilnya, graf X dengan indikator TikTok
dapat tampil sebagai satu jaringan (FR-073, FR-081, NFR-06). Yang tercampur adalah tampilan; database tidak.

## Keputusan

- **Penawaran:** hanya run indikator pada **dataset yang sama** dengan graf aktif yang ditawarkan (dataset satu platform,
  jadi platform otomatis sama). Bila ada yang disembunyikan, UI menyatakan jumlahnya. Perbandingan antar-dataset kelak
  harus berupa alur tersendiri yang menyatakan perbedaan cakupan secara eksplisit.
- **Penggantian:** mengganti graf mengosongkan pilihan indikator, data indikator, dan seleksi; mengganti run indikator
  mengosongkan data indikator lama. Jawaban terlambat dari run indikator lama diabaikan (pembatalan efek).
- **Penolakan berlapis:** `incompatibility(graph, source)` memeriksa platform (lebih dulu) lalu dataset dari muatan yang
  benar-benar diterima; bila tidak cocok, panel menampilkan peringatan dan TIDAK menampilkan indikator. `buildElements`
  melempar `IncompatibleAnalysisError` bila ada indikator tanpa asal yang diketahui atau asal yang tidak cocok, sehingga
  pemanggil lain pun tidak dapat mencampur hasil secara tidak sengaja.

## Alasan

Isolasi platform (baseline lock nomor 3) harus berlaku sampai ke apa yang dilihat analis, bukan hanya pada penyimpanan.
Pertahanan berlapis (penawaran, pembersihan state, pemeriksaan muatan, penolakan di fungsi penggabung) menjaga isolasi
walau satu lapis terlewat.

## Batas yang diketahui

- Tidak ada alur perbandingan antar-dataset yang disengaja; bila diperlukan, harus dirancang terpisah.
- Pemeriksaan bergantung pada `platform` dan `run.dataset.id` pada muatan API; keduanya sudah dijamin backend.
- Pengosongan `coordination` saat graf diganti bersifat defensif (tampilan sudah dijaga `coRunId`): mutasi atas baris itu
  setara secara perilaku.
