# Keputusan organisasi: jalur perolehan data

Tanggal: 2026-10-19. Ditetapkan oleh pemilik proyek dan disampaikan langsung kepada tim developer; tim developer
mencatatnya apa adanya di sini. Dokumen ini adalah keputusan tentang **jalur yang dipilih**, bukan penilaian hukum.

## Keputusan

> Semua platform harus mempergunakan browser dengan sesi milik operator. Hal ini karena kita harus bertindak
> seperti layaknya orang yang melakukan riset dan bukan mesin. Alat ini tidak berjalan secara otomatis dan
> monitor 24 jam, hanya jika diperlukan saja diaktivasi. Isu biaya juga menjadi pertimbangan kenapa harus
> memakai sesi browser.

Rinciannya:

1. **Jalur tunggal untuk semua platform (X, Threads, TikTok, Instagram, Facebook): pemeriksaan lewat browser dengan
   sesi login milik operator.** API resmi berbayar tidak dipilih.
2. **Alasan:** (a) bertindak seperti peneliti manusia, bukan mesin; (b) biaya.
3. **Cara pakai:** tidak berjalan otomatis dan tidak dipantau 24 jam; diaktifkan hanya bila diperlukan.

## Turunan untuk pengembangan (ditulis tim developer; mohon dikonfirmasi bila ada yang keliru)

- Adapter platform dibangun di atas lapisan browser yang sudah ada (Playwright, worker `browser`, sesi di
  `browser-profiles/` yang terpisah dari bukti). Sesi dibuat lewat login interaktif oleh operator; cookies tidak
  ditempel ke percakapan, Git, log, atau bukti (PRD bagian 13).
- **Pemicu manual saja.** Tidak ada pemeriksaan atau pemeriksaan ulang terjadwal (selaras dengan D-09: penjadwalan
  otomatis ditunda). Penyapu run basi tetap nonaktif kecuali dikonfigurasi eksplisit. Tidak ada proses yang
  menganggur menunggu target.
- **Skala dan laju seperti peneliti:** satu worker browser, satu target per run, tanpa pengambilan massal.
- "Bertindak seperti orang yang meneliti" dibaca sebagai: dimulai dan diawasi operator, skala kecil, mengikuti
  ritme penelusuran manual. **Bukan** menyamarkan otomatisasi atau menghindari deteksi: tidak ada pemalsuan sidik
  jari peramban, rotasi identitas, atau penyamaran sejenis.

## Batas yang tetap berlaku (dari PRD bagian 7 dan 13)

- Login browser bukan persetujuan pengumpulan otomatis. Bila platform menampilkan CAPTCHA, tantangan keamanan, atau
  membatasi akses, adapter **berhenti** dan melapor `ACCESS_RESTRICTED`; tidak ada jalan memutarnya.
- Memeriksa apakah syarat layanan tiap platform mengizinkan cara ini adalah tanggung jawab organisasi; tim developer
  tidak menyimpulkan legalitas (PRD bagian 1). Keputusan ini mencatat jalur yang dipilih, bukan jaminan kebolehannya.
- Kegagalan parser ditandai `PARSE_FAILED` atau `PARTIAL`, bukan data kosong (AT-14).

## Status dan langkah berikutnya

- Seluruh adapter platform tetap `DISABLED` (ADR 0036) sampai diaktifkan **satu per satu**: (1) pemilik proyek
  memilih platform pertama, (2) operator menangkap rekaman halaman yang sah sebagai fixture, (3) adapter lulus
  suite kontrak dan AT-13/AT-14, (4) kemampuan dinaikkan dari `UNTESTED` lewat PR beserta pembaruan dokumen
  kelayakan platform itu.
- Dokumen kelayakan (`docs/adapters/*-feasibility.md`) mencatat jalur API resmi hanya sebagai alternatif yang tidak
  dipilih; jalur browser pada dokumen itu kini mengacu ke keputusan ini.
