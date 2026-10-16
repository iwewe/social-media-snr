# 0006 - Kontrak observasi dan adapter

- **Status:** diterima (implementasi WP-1.1)
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 7.1 menetapkan bentuk observasi minimum dan kontrak adapter; FR-022, FR-023, FR-024,
FR-026 mewajibkan kontrak terstandar, adapter terpisah per platform, dan kegagalan yang dilaporkan
eksplisit (bukan "tidak ada komentar"). Kontrak ini dipakai seluruh adapter (dataset uji, browser,
lima platform), jadi bentuknya sulit diubah setelah banyak adapter bergantung padanya.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Bentuk objek | `dataclass(frozen=True)` dengan validasi di `__post_init__`; tanpa pustaka baru | Pelanggaran gagal saat objek dibangun, sebelum sampai ke penyimpanan. Pydantic tidak perlu. |
| Nilai tidak diketahui | Selalu `None` (termasuk `published_at`, `text`, ID), tidak pernah nilai bawaan | PRD bagian 9.3 dan 5. |
| `published_at` | Tidak boleh sama dengan `observed_at`/`captured_at`, tidak boleh lebih baru dari `observed_at`; semua waktu wajib timezone-aware | Mencegah waktu pengambilan menyamar sebagai waktu publikasi. |
| ID hilang | `identity_needs_verification=True` wajib bila ID post atau aktor `None` | PRD bagian 5: tidak boleh ada kesan kepastian deduplikasi. |
| Induk reply | `REPLY`/`COMMENT` wajib punya `parent_post_id` atau `parent_unknown=True`; jenis lain tidak boleh punya induk. `QUOTE`/`REPOST` wajib `quoted_post_id`/`reposted_post_id` | Konteks percakapan (AT-08) bergantung pada induk yang sebenarnya; "tidak diketahui" harus eksplisit. |
| Username | `actor_handle`/`actor_display_name` hanya informasi, bukan identitas | PRD bagian 5. |
| Observasi bebas interpretasi | Tidak ada field label/stance/skor; diuji | Observe first, interpret later. |
| Hasil inspeksi | `InspectionResult` dengan `outcome`, `coverage`, `limitations`, `artifacts`, `collector` | FR-021. |
| Invarian hasil | `COMPLETED` ⇒ pagination lengkap dan tanpa keterbatasan yang menghalangi; `PARTIAL` ⇒ ada sebab; `FAILED`/`ACCESS_RESTRICTED`/`UNSUPPORTED` ⇒ tanpa observasi dan keterbatasan yang sesuai; hasil kosong `COMPLETED` hanya bila platform menyatakan jumlah 0 | FR-026, AT-14: kegagalan tidak boleh menyamar sebagai "tidak ada komentar". |
| Dua jumlah | `coverage.platform_displayed_count` (yang ditampilkan platform) terpisah dari jumlah unik teramati | PRD bagian 9.3. |
| Status per observasi | `collection_status` harus konsisten dengan `outcome` hasilnya | Tidak ada observasi "COMPLETED" dari pengumpulan parsial. |
| Isolasi | Observasi dari platform/run lain ditolak; satu `external_post_id` hanya sekali per hasil | FR-024, NFR-06. |
| Kemampuan | Setiap `Capability` wajib dinyatakan eksplisit; hanya `SUPPORTED`/`LIMITED` yang dapat dijalankan; `UNTESTED`/`UNSUPPORTED` wajib beralasan | PRD bagian 15 (I3): hanya yang teruji dan diizinkan yang aktif. |
| Gerbang kemampuan | `Adapter.inspect()` (template method) menegakkan gerbang dan memeriksa hasil; adapter mengimplementasikan `collect()` dan tidak boleh menimpa `inspect()` | Gerbang tidak dapat dilewati secara tidak sengaja. |
| Galat tak terduga | Dibiarkan merambat ke orchestrator (run `FAILED`); keterbatasan yang diharapkan dilaporkan lewat hasil | Bug tidak boleh disamarkan sebagai keterbatasan sumber. |
| Artefak | Adapter mengembalikan `ArtifactCapture` (bytes); penulisan ke disk oleh orchestrator lewat `preservation.storage` | Adapter tidak menyentuh akar evidence. |
| Suite kontrak | `tests/contracts/contract_suite.py` dijalankan terhadap setiap harness terdaftar; diuji sendiri terhadap 10 adapter pelanggar; jaringan diblokir | Adapter baru wajib lulus suite yang sama. |

## Keterbatasan dan hal terbuka

- `published_at` bisa berupa perkiraan (TikTok menampilkan waktu relatif); presisinya belum
  dimodelkan. Menambah field opsional kelak kompatibel mundur.
- Artefak dikembalikan sebagai `bytes` di memori; media besar perlu aliran (streaming) pada WP-1.5.
- `ArtifactCapture` belum disaring dari cookies/token; itu WP-1.5.
- Aturan "hasil kosong COMPLETED hanya bila jumlah platform 0" konservatif: adapter yang tidak
  dapat mengetahui jumlah harus tetap mengembalikan objek target itu sendiri.
- Suite kontrak memakai skenario yang disimulasikan harness; kualitas fixture tiap adapter
  menentukan kekuatan pengujiannya. Belum ada adapter nyata (WP-1.7, WP-1.8, I3).
- Pemetaan `InspectionOutcome` ke status `InspectionRun` dan penanganan `REVIEW_REQUIRED` ada di
  WP-1.6.
