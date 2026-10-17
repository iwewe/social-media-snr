# 0014 - PoC browser (Playwright) pada halaman simulasi

- **Status:** diterima (implementasi WP-1.8). Ini PoC pada halaman buatan sendiri, bukan adapter platform nyata.
- **Tanggal:** 2026-10-17

## Konteks

PRD I1: "browser-assisted proof of concept pada halaman uji yang dikendalikan sendiri". Tujuannya membuktikan jalur
browser -> observasi -> artefak -> manifest -> hash -> orchestrator bekerja, dan bahwa tiap jenis kegagalan punya
status sendiri (AT-14), sebelum ada studi izin per platform (WP-3.0).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Simulasi | `collection/simulation/`: server `http.server` (hanya pustaka standar), data sintetis, skenario dipilih lewat `/s/<skenario>/` atau tabel ID | Tanpa dependensi baru; deterministik; dapat dijalankan juga untuk demo (`python -m collection.simulation`). Pagination memakai JavaScript (klik "Muat lebih banyak"), bukan tautan, agar mirip situs nyata. |
| Skenario | complete, empty_post, partial (halaman 2 gagal), login_wall, forbidden (403), challenge, not_found (404), server_error (500), parse_failure, identity_missing, changing (beda per kunjungan), external (permintaan pihak ketiga), slow | Tiap kegagalan harus punya status sendiri; "nol balasan" tidak boleh menyamar sebagai sukses. |
| Toolkit vs adapter | `collection/browser/runtime.py` (`BrowserSession`, profil) dipisah dari `simulated.py` (adapter simulasi) | I3 memakai toolkit yang sama untuk adapter platform. Aturan arsitektur: Playwright boleh di `collection.adapters` dan `collection.browser`, tidak di tempat lain (diuji, termasuk selftest). |
| Profil browser | `browser-profiles/<platform>` mode 0700, dibuat bertahap, symlink ditolak; disiapkan saat `collect` (di worker-browser), bukan saat adapter dibuat; isi profil tidak pernah dibaca/disalin | Profil adalah kredensial dan terpisah dari bukti (PRD 10/13). Proses web membuat instans adapter hanya untuk membaca antrean dan tidak memasang volume profil. |
| Konkurensi | `worker-browser -c 1` | Profil Chromium hanya dapat dipakai satu proses. |
| Sandbox | Sandbox Chromium tetap aktif; diuji berjalan sebagai non-root di kontainer | `no_sandbox` hanya opsi sadar di `BrowserSession`, tidak dipakai. |
| Tanpa melewati pembatasan | Tantangan/CAPTCHA/403 -> `ACCESS_RESTRICTED`; tembok login setelah sebagian terbaca -> `PARTIAL` + `AUTH_REQUIRED`; tidak ada upaya mengisi atau mengakali | PRD bagian 13; WP-1.8 tugas 4. |
| Status per kegagalan | 403/401 -> ACCESS_RESTRICTED; 404 -> FAILED/`TARGET_UNAVAILABLE`; 5xx -> FAILED/`NETWORK_ERROR`; struktur tak dikenal -> FAILED/`PARSE_FAILED`; timeout -> FAILED/`TIMEOUT`; host tak terjangkau -> FAILED/`NETWORK_ERROR`; pagination putus -> PARTIAL/`PAGINATION_INCOMPLETE` | FR-026, AT-14. |
| Isolasi origin | Permintaan ke origin selain target diblokir (`route.abort`); jumlahnya di catatan cakupan tanpa host/URL | Pelacak/pihak ketiga tidak dikunjungi; cakupan tetap jujur. |
| Artefak | Screenshot (PNG, halaman penuh) dan DOM (`#conversation`, atau seluruh halaman bila tak ada) hanya bila kemampuan diminta; juga untuk halaman gagal (bukti penolakan). Melewati penyaring rahasia yang sama | Bukti mengapa run gagal. |
| Versi collector | `browser-sim 1 (playwright X, chromium Y)` tercatat di run dan manifest | WP-1.8 tugas 5; hasil dapat ditelusuri ke versi peramban. |
| Label sumber | Observasi simulasi `synthetic_fixture`, bukan `authorized_observation` | Data sintetis tidak boleh tampak sebagai pengamatan. |
| Galat infrastruktur | Browser gagal diluncurkan tidak ditelan: merambat ke orchestrator -> FAILED/`ADAPTER_ERROR` | Bukan keterbatasan sumber. |
| Pendaftaran | Hanya bila `SNR_SIMULATION_BASE_URL` diset (`SNR_SIMULATION_PLATFORM`, bawaan `x`); bentrok dengan adapter dataset pada platform yang sama menghasilkan galat registry (eksplisit) | Tidak terdaftar bawaan; satu adapter per platform. |
| Pengujian | `tests/browser/` jalan di image `worker-browser`/CI; tanpa Chromium dilewati kecuali `SNR_REQUIRE_BROWSER=1` (diset di `make test` dan CI) | Tes browser yang diam-diam dilewati bukan bukti. |

## Batas yang diketahui

- Batas waktu 30 s adalah bawaan Playwright yang ditulis eksplisit, belum diukur pada situs nyata; begitu pula pengaman 1000 klik.
- Suite kontrak (C05) hanya dapat mendeteksi jaringan lewat Python; lalu lintas Chromium tidak terlihat olehnya. Isolasi origin diuji terpisah.
- Struktur halaman simulasi buatan sendiri; selector platform nyata dan ketahanannya terhadap perubahan baru dipelajari di I3.
- Halaman akun, media, dan beberapa tab belum disimulasikan. Kinerja Chromium per run (peluncuran ~1 s) belum dioptimalkan.
- Tidak ada login: profil disiapkan tetapi PoC tidak memakai sesi. Penanganan sesi sungguhan menunggu WP-3.0.
