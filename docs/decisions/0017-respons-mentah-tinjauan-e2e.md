# 0017 - Tampilan respons mentah, tinjauan, artefak, dan E2E dengan worker

- **Status:** diterima (WP-1.9c; menutup WP-1.9).
- **Tanggal:** 2026-10-17

## Konteks

WP-1.9 meminta daftar respons mentah per run (penulis, waktu publikasi atau "tidak diketahui", parent, status
rekonsiliasi, tautan artefak), pesan ramah, dan pembedaan keadaan data. PR sebelumnya menyediakan API (ADR 0015) dan
riwayat run (ADR 0016); PR ini menambah halaman detail run dan E2E yang menjalankan seluruh jalur.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Halaman terpisah | `/inspections/:id` memuat ringkasan run, panel tinjauan, artefak, dan tabel respons; kartu target menautkannya ("Lihat respons mentah dan bukti") hanya untuk run yang sudah final | Isi balasan platform tidak dicampur dengan ringkasan status di kartu target. Detail run menyertakan `target` (id, platform, URL ternormalisasi, investigasi) untuk judul dan tautan kembali, tanpa catatan konteks. |
| Tabel respons | Satu baris per objek: jenis, ID, penulis (handle sebagai informasi, ID akun sebagai identitas), isi, waktu publikasi, induk, perubahan, keterangan. Tidak ada kolom stance, klasifikasi, atau skor (tes memeriksa) | Data mentah dulu; interpretasi nanti (I2). |
| Ketidakpastian | `null` ditulis "tidak diketahui"/"tidak tersedia"/"tanpa ID (perlu verifikasi)"/"induk tidak diketahui", bukan kosong | PRD 9.3. |
| Objek tidak teramati | Tetap ditampilkan (di akhir) dengan label "Tidak teramati kali ini", data terakhir terlihat, dan "Terakhir terlihat pada run #N"; label tidak memakai kata "dihapus". CONFIRMED_UNAVAILABLE menampilkan bukti dari sumber | FR-036, AT-04. |
| Isi tidak dipercaya | Teks balasan dirender sebagai teks React (bukan HTML); teks panjang (>300 karakter) dilipat | Isi berasal dari platform dan dapat memuat markup. Diuji dengan `<script>`. |
| Daftar kosong dijelaskan menurut keadaan | access_failed: "bukan berarti tidak ada balasan"; partial/needs_review: "jangan simpulkan tidak ada balasan"; selebihnya: "Tidak ada respons pada run ini." | NFR-08. Gagal akses tidak pernah dijelaskan sebagai nol respons. |
| Run gagal tidak menampilkan "0 teramati" | Pada keadaan `access_failed`, hitungan teramati ditulis "tidak diambil (pengambilan gagal)" | Ditemukan lewat tinjauan tangkapan layar: nol dari run yang tidak mengambil apa pun mudah terbaca sebagai "tidak ada balasan". Run COMPLETED dengan nol balasan tetap menulis 0. |
| Tinjauan | Panel hanya untuk `REVIEW_REQUIRED` yang belum diakui; mengakui memanggil API, lalu halaman memuat ulang; tinjauan yang sudah diakui menampilkan siapa/kapan/catatan; 409 `not_awaiting_review` memuat ulang | FR-026. Panel menjelaskan bahwa data run tidak diubah dan hasil adapter yang tercatat dipulihkan. |
| Artefak | Tabel jenis/ukuran/SHA-256 (16 karakter + hash penuh pada `title`), pernyataan bahwa hash tidak membuktikan keaslian konten platform, dan catatan jumlah artefak yang ditolak karena tampak memuat kredensial (tanpa nama berkas) | PRD 10 dan 13. Isi berkas dan verifikasi ulang hash adalah WP-1.10. |
| Paginasi | 25 baris per halaman; tombol Sebelumnya/Berikutnya; "Menampilkan a-b dari N" | Server membatasi 200; offset cukup untuk skala saat ini. |
| E2E dengan worker | `deployment/e2e.sh` menjalankan worker Celery sementara dengan broker Valkey DB 1 (terpisah dari worker dev), direktori data sementara (bukan evidence dev), dan dataset `datasets/sample`; skenario `inspection_flow.py` menekan Inspect lewat UI sampai hasil (4 putaran, objek tidak teramati, dinyatakan tidak tersedia, artefak + hash, akses ditolak, parser gagal, melebihi dataset) | AT-01..06, AT-14, AT-18 diuji pada jalur sebenarnya: UI -> API -> Celery -> adapter -> ingestion -> rekonsiliasi -> UI. |

## Catatan

- Tinjauan tangkapan layar menemukan tiga masalah keterbacaan yang tidak terlihat oleh tes DOM: ID terpecah per karakter,
  label badge terputus, dan judul pesan tidak menonjol. Diperbaiki lewat CSS (`nowrap`, judul tebal).
- Skenario `REVIEW_REQUIRED` tidak dapat dipicu lewat dataset sampel; jalurnya diuji pada tes komponen dan API.

## Batas yang diketahui

- Belum ada filter/sorting pada tabel respons (paginasi dilakukan server; filter perlu parameter API).
- Isi artefak belum dapat dibuka dari UI dan hash belum dapat diverifikasi ulang (WP-1.10).
- Tabel tidak menampilkan hubungan non-reply (quote, repost, mention); hanya induk reply.
