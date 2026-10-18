# 0033 — AuditEvent dan jejak bukti (WP-2.8)

Status: diterima. Tanggal: 2026-10-18.

## Keputusan

- App baru `audit` dengan model `AuditEvent`: investigasi, pelaku, waktu, aksi, objek
  (`subject_type`, `subject_id`), `before` (null = baru dibuat), `after`, `reason`. Hanya dapat
  ditambahkan: `save()`/`delete()` ditolak di kode dan trigger DB (`snr_forbid_modification`) menolak
  UPDATE/DELETE termasuk lewat SQL langsung.
- Objek dirujuk dengan (jenis, id) tanpa FK agar `audit` tidak bergantung pada app yang dicatatnya;
  `investigations` dan `intelligence` memanggil `audit.services.record`, bukan sebaliknya.
- Tujuh aksi: konteks issue, konteks target (versi pertama dan revisi), tinjauan klasifikasi,
  temuan dibuat, direvisi, disahkan, ditarik. Pencatatan ada DI DALAM transaksi perubahan yang sama
  (`record` menolak dipanggil di luar transaksi): perubahan batal = audit batal; perubahan yang ditolak
  validasi tidak meninggalkan audit.
- Isi audit: konteks mencatat versi + definisi/catatan + posisi awal; klasifikasi mencatat nilai
  lama/baru per dimensi, alasan, serta rujukan observasi/run/proposition; temuan mencatat judul,
  confidence, status, run, jumlah observasi, dan alasan; pengesahan/penarikan mencatat status lama dan baru.
- API: `GET /api/investigations/{id}/audit/` (VIEWER; filter `action`, `subject_type`, `subject_id`,
  `actor`, `observation`; urut terbaru; paginasi). `GET /api/observations/{id}/` memuat
  `classification_trail` (riwayat koreksi klasifikasi observasi itu).
- UI: tab "Jejak audit" (sebelum/sesudah per bagian, alasan, pelaku, tautan satu klik ke observasi dan
  temuan); laci jejak bukti memuat riwayat koreksi; node graf menautkan ke respons akunnya
  ("Lihat respons akun ini"); detail temuan menautkan ke jejak audit temuannya. Bersama tautan
  edge/indikator/baris respons dari WP-2.7, setiap node, edge, label, dan temuan dapat ditelusuri
  satu klik ke observasi dan artefak (FR-005).

## Alasan

AT-16 mensyaratkan perubahan dan rujukan bukti tercatat. Tabel versi yang sudah append-only
(konteks, klasifikasi, tinjauan temuan) hanya menjawab "apa isinya"; audit menjawab "siapa mengubah
dari apa menjadi apa, kapan, dan mengapa" di satu tempat yang tidak dapat disunting.

## Batas yang diketahui

- Peristiwa yang terjadi SEBELUM WP-2.8 (data lama) tidak punya audit; tidak ada pengisian ulang.
- Tidak dicatat: pembuatan proposition, pendaftaran akun/anggota tim, dan penjalanan analisis/inspeksi
  (sudah punya catatan sendiri: versi proposition tak dapat diubah, keanggotaan riwayat, `AnalysisRun`).
- Konteks target lewat API tidak membawa kolom alasan; alasan kosong, isi catatan ada pada `after.note`.
- Audit tidak ditandatangani/dirantai (tamper-evident hash chain) dan tidak dapat dilindungi dari
  superuser basis data; perlindungan yang ada adalah trigger dan pembatasan akses aplikasi.
- Belum ada ekspor jejak untuk laporan (FR-096 ditunda).
