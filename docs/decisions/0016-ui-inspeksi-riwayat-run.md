# 0016 - UI inspeksi: riwayat run, keadaan data, polling

- **Status:** diterima (WP-1.9b). Tabel respons mentah per run, UI tinjauan, dan E2E dengan worker menyusul (WP-1.9c).
- **Tanggal:** 2026-10-17

## Konteks

PR API (ADR 0015) menyediakan run, `data_state`, dan pesan. UI harus menampilkannya tanpa menafsirkan ulang,
membedakan belum diperiksa / tidak ada data / gagal mengakses (NFR-08), dan menampilkan dua angka terpisah (PRD 9.3).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| UI tidak menafsirkan | Keadaan data dan pesan dibaca dari server; UI hanya memetakan ke label dan gaya | Satu sumber kebenaran; kegagalan tidak dapat tampil sebagai "tidak ada data" karena klien. |
| Tiga keadaan wajib | Label berbeda ("Belum diperiksa", "Tidak ada data", "Gagal mengakses data") dengan penjelasan; gagal mengakses selalu bertuliskan BUKAN berarti tidak ada balasan | NFR-08. Diuji (label tidak kembar, kata kunci). |
| Dua angka | "Ditampilkan platform" dan "Balasan/Objek unik teramati" selalu terpisah; `null` ditulis "tidak diketahui", `0` tetap `0` | PRD 9.3; ketidakpastian eksplisit. |
| Satu tombol bergantian | "Inspect" bila belum ada run, "Inspect Again" bila sudah; dinonaktifkan selama memuat atau ada run berjalan | Cocok dengan aturan satu-run-aktif; 409 tetap ditangani (pesan ditampilkan, keadaan sebenarnya dimuat). |
| Polling | `useInspections`: muat ulang tiap 2 detik hanya selama run terbaru `in_progress`; berhenti saat final, saat galat (tombol "Muat ulang"), dan saat unmount; induk diberi tahu sekali saat run menjadi final | Hasil run asinkron (Celery). 2 detik adalah pilihan antarmuka, bukan batas riset. Tidak mengulang tanpa henti saat server galat. |
| Tanpa permintaan sia-sia | `latest_inspection === null` berarti belum ada run: riwayat kosong tanpa memanggil API | Hemat; kartu baru tidak memicu permintaan. |
| Riwayat | Run terbaru terbuka; yang lama dilipat (`<details>`); detail teknis (keterbatasan mentah, collector, sumber) dilipat | Ringkas tetapi dapat ditelusuri. |
| Teks respons tidak di kartu run | Isi balasan platform hanya akan tampil pada tampilan respons (WP-1.9c) | Memisahkan ringkasan status dari data mentah; tes memastikan kartu run tidak merender isi. |
| Pesan galat | `role="alert"` hanya untuk level error; info/peringatan `role="note"` | Aksesibilitas; tidak semua pesan perlu mengganggu. |
| Petunjuk | `startInspection` tidak lagi mengaku "belum tersedia"; ditambah petunjuk `dataStates` | PRD 12, FR-004. |

## Catatan pengujian

- Testing Library hanya menguras timer palsu bila ada global `jest`; pada vitest tes dengan timer palsu menggantung
  tanpa itu. Tes polling memasangnya di `beforeEach` dan menghapusnya setelahnya.
- Tes menangkap bug nyata: pesan 409 terhapus oleh pemuatan ulang yang berhasil (diperbaiki di hook).

## Batas yang diketahui

- Belum ada tampilan respons mentah per run, aksi tinjauan, atau tautan artefak (WP-1.9c, WP-1.10).
- Polling per kartu target; bila satu investigasi punya banyak run bersamaan, beban permintaan bertambah linear.
