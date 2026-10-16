# 0005 - Fondasi preservasi dan uji arsitektur

- **Status:** diterima (implementasi WP-0.6)
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 10 dan 13 memisahkan bukti dari sesi browser dan melarang bukti ditimpa (FR-039). PRD
bagian 1, 3.3, FR-022, FR-024, FR-041, FR-075, dan FR-079 menetapkan batas arsitektur: observasi
dipisahkan dari interpretasi, adapter per platform terpisah, analisis ulang tidak mengambil data,
dan tidak ada skor atau vonis otomatis.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Jalur tulis bukti | `preservation.storage.write_new` satu-satunya jalur; berkas ditulis ke berkas sementara lalu `os.link` ke nama akhir | `link` atomik dan gagal bila nama sudah ada: dua penulis bersamaan tidak saling menimpa dan pembaca tidak pernah melihat berkas setengah jadi. Diuji dengan 8 penulis serentak. |
| Jalur tidak sah | Ditolak: kosong, absolut, `..`, `.`, `//`, `\`, NUL, komponen > 255, jalur > 1024, symlink keluar akar, area sesi browser | Mencegah penulisan di luar akar evidence. |
| Hash | SHA-256 dihitung selagi menulis (streaming) | NFR-02. Hash hanya membuktikan berkas tidak berubah, bukan keaslian konten. |
| Izin | Berkas `0440`; tiap direktori dibuat satu per satu dengan `0750` | `Path.mkdir(parents=True, mode=)` hanya memakai `mode` untuk komponen terakhir; induknya mengikuti umask (terdeteksi tes sebagai `0755`). |
| Ekspor | `ensure_exportable` menolak apa pun di bawah akar sesi browser dan apa pun di luar akar evidence | Cookies/profil adalah kredensial dan tidak pernah menjadi artefak. |
| Konfigurasi | System check `snr.E001` (akar harus absolut) dan `snr.E002` (evidence dan sesi browser tidak boleh sama atau bersarang, termasuk lewat symlink) | Kesalahan konfigurasi terdeteksi saat startup. |
| Isolasi compose | Tes membaca `compose.yaml`: hanya `worker-browser` memasang `browser-profiles`; DB/Valkey/worker tanpa port; port terbuka hanya ke loopback; secret tanpa nilai bawaan | Regresi isolasi gagal di CI. |
| Aturan impor | AST statis: collection dan preservation tidak mengimpor intelligence; intelligence tidak memakai Playwright/adapter/orchestrator; Playwright hanya di `collection.adapters`; adapter satu platform tidak mengimpor platform lain | FR-022, FR-024, FR-041. |
| Identifier terlarang | Urutan kata `buzzer`, `bot score`, `bot probability`, `is bot`, `paid account`, `coordination score`/`verdict` pada identifier kode, nama model/field/tabel (backend) dan kode TypeScript | PRD bagian 1 dan FR-079. Pemecahan kata (snake/camel) menghindari salah deteksi seperti `bottom`. Teks yang tampil dan komentar boleh menyebutnya (untuk melarangnya). |
| Akar penyimpanan | `SNR_EVIDENCE_ROOT` dan `SNR_BROWSER_PROFILES_ROOT` hanya boleh dipakai `config.settings`, `preservation.storage`, `preservation.checks` | Jalur tulis tunggal dapat ditegakkan secara statis. |
| Pemeriksa diuji sendiri | Pemeriksa dijalankan terhadap kode buatan (pelanggaran dan bukan pelanggaran) dan harus mendeteksi; pemindaian kode nyata harus non-kosong | Agar tes tidak lulus karena tidak melihat apa pun. |

## Keterbatasan yang diketahui

- `os.link` mensyaratkan filesystem yang mendukung hard link (ext4/xfs/btrfs ya; sebagian jaringan/FAT
  tidak). Tidak ada cadangan untuk kasus itu; penulisan akan gagal dengan galat, bukan menimpa.
- Izin baca-saja bersifat penjagaan terhadap kesalahan; pemilik berkas masih dapat `chmod`.
- Aturan tunggal-jalur-tulis hanya mendeteksi pemakaian *nama pengaturan*. Kode yang menulis jalur
  literal (mis. `"/srv/snr/evidence"`) atau memakai impor dinamis (`importlib`) tidak terdeteksi.
- `ensure_exportable` belum dipanggil kode ekspor mana pun (belum ada). Kewajiban memanggilnya
  harus ditegakkan saat fitur ekspor ditulis (WP-1.5/WP-1.10).
- Penyaringan nama berkas rahasia (cookies, token, `storage_state`) ditunda ke WP-1.5.
- Daftar kata terlarang adalah heuristik; eufemisme (mis. `propaganda_rating`) tidak tertangkap.
  Penjaga akhirnya tetap tinjauan manusia.
- Keberadaan/izin direktori evidence tidak diperiksa saat startup (hanya bentuk konfigurasi).
