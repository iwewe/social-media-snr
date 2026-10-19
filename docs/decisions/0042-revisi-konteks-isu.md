# 0042 — Revisi konteks isu lewat API dan antarmuka (FR-014)

Status: diterima. Tanggal: 2026-10-19. Menindaklanjuti butir 4.3 pada `analisis-snr.txt`.

## Masalah

`revise_issue_context` dan pembuatan versi konteks isu (append-only, dengan audit) sudah ada, tetapi tidak ada rute API
maupun tombol, sehingga pengguna tidak dapat memperbarui penjelasan isu. Catatan konteks target sudah dapat direvisi;
konteks isu belum.

## Keputusan

- `POST /api/issues/{id}/context-versions/` (Anggota ke atas; non-anggota 404, Pembaca 403) dengan `definition` (wajib; boleh
  kosong untuk mengosongkan). Menghasilkan versi baru; definisi yang SAMA dengan versi terbaru ditolak (400) agar tidak ada
  versi tanpa perubahan. Perbedaan spasi dihitung sebagai revisi.
- Representasi issue memuat `context_history` (semua versi, terbaru dulu, dengan pembuat dan waktu); versi lama tidak
  pernah dihapus. Revisi tercatat sebagai `ISSUE_CONTEXT` dengan nilai sebelum/sesudah (WP-2.8).
- Antarmuka: kartu issue memuat tombol "Revisi konteks isu" (Anggota), formulir terisi definisi saat ini, nomor versi, dan
  riwayat versi. Formulir menyatakan bahwa penjelasan belum dibaca klasifier mesin.

## Batas yang diketahui

- Run analisis yang sudah ada tetap membekukan versi konteks lamanya (ADR 0025); revisi baru dipakai oleh run berikutnya
  (pemilihan versi eksplisit pada A2) atau analisis ulang dengan konteks terbaru.
- Tidak ada penyuntingan atau penghapusan versi lama; koreksi = versi baru.
