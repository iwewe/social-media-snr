# 0007 - Model inti pengumpulan data

- **Status:** diterima (implementasi WP-1.2)
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 8 dan 9 menetapkan entitas inti (`InspectionRun`, `ActorAccount`, `Post`,
`PostObservation`, `PostRelation`, `EvidenceArtifact`), identitas unik per platform, observasi
append-only, dan isolasi platform (FR-030, FR-031, FR-033; NFR-03, NFR-05, NFR-06; AT-13). Skema ini
sulit diubah setelah data nyata masuk, jadi jaminannya ditegakkan di database.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Lokasi | `InspectionRun`, `Post`, `ActorAccount`, `PostObservation`, `PostRelation` di app `collection`; `EvidenceArtifact` di `preservation` (FK ke `collection`) | Sesuai struktur PRD bagian 17. Ketergantungan model satu arah (preservation → collection). |
| Identitas | Unik per `(platform, external_*_id)` lewat unique index parsial; ID yang sama di platform lain adalah objek lain | AT-13, NFR-06. |
| Tanpa ID stabil | Baris kandidat dengan ID `NULL` dan `NEEDS_VERIFICATION`; tidak pernah digabung otomatis; `.verified()` dipakai analisis | PRD bagian 5. CHECK: ID `NULL` hanya boleh bila `NEEDS_VERIFICATION`. |
| Perubahan identitas | Trigger hanya mengizinkan ID `NULL → terisi` dan `NEEDS_VERIFICATION → VERIFIED`; platform, ID terisi, provenance, dan status terverifikasi tidak dapat diubah; tidak dapat dihapus | Identitas adalah acuan seluruh analisis. Tidak ada fungsi penggabungan (belum dibutuhkan). |
| Provenance | `first_seen_run` wajib pada Post dan ActorAccount | NFR-05. |
| Observasi | Satu baris per `(Post, run)`, append-only (kode + trigger); `None`/`NULL` = tidak diketahui; `published_at`, `observed_at`, `captured_at` terpisah; CHECK `published_at` ≠ dan ≤ `observed_at` | FR-033, PRD bagian 9.3. Pemeriksaan ulang menambah baris. |
| Penulis dan handle | Pada observasi, bukan pada Post | Handle dapat berubah; yang teramati dicatat per run. |
| Relasi | `PostRelation` terikat run: `reply_to`, `quote_of`, `repost_of`, `mentions`; tipe menentukan target (post atau akun); satu induk per reply per run; tidak boleh ke diri sendiri; append-only | Riwayat relasi (mis. induk berubah) tercatat otomatis per pemeriksaan. Sumber relasi = `run.source_method`. |
| Isolasi platform | Trigger menolak identitas, observasi, relasi, dan artefak yang platformnya berbeda dari platform target run | FR-024, NFR-06; tidak bergantung pada disiplin kode. |
| InspectionRun | `public_id` UUID dipakai sebagai `inspection_run_id` kontrak; `sequence` per target diberi di bawah kunci baris; kolom identitas tidak dapat diubah; run tidak dapat dihapus; status valid dijaga CHECK | FR-020, FR-021, AT-01. |
| Keterkaitan investigasi | Post muncul di banyak investigasi lewat run → target → investigasi; tidak ada tabel penghubung | PRD bagian 8, relasi 3 ("keterkaitan dataset/target"). **Menyimpang dari rencana WP-1.2 butir 6** (tabel penghubung): tabel itu data turunan yang harus disinkronkan dan tidak menambah informasi. |
| EvidenceArtifact | Kerangka: `relative_path` unik, `sha256` dicek format, `size_bytes`, append-only, penunjuk divalidasi (tidak keluar akar evidence), platform post harus sama dengan run | FR-037, FR-038, FR-039. Manifest dan penyaringan rahasia di WP-1.5. |

## Belum termasuk

- `content_hash` untuk deteksi `MODIFIED` (WP-1.4), `DatasetVersion` (WP-2.1), `AuditEvent` untuk
  verifikasi identitas (WP-2.8), ingestion (WP-1.3), dan tabel transisi status run serta
  imutabilitas run yang sudah selesai (WP-1.6).

## Keterbatasan dan hal terbuka

- Kandidat tanpa ID akan menumpuk: tiap pemeriksaan ulang objek tanpa ID membuat baris kandidat
  baru, karena tidak ada kunci aman untuk mencocokkannya. Antrean peninjauan untuk menyatukannya
  belum dibangun; volumenya perlu diukur pada pilot.
- Trigger platform menjalankan subquery per `INSERT`. Dampak performa pada ingestion massal belum
  diukur (WP-1.3 dan pilot).
- Trigger tidak memblokir `TRUNCATE`, dan superuser/pemilik DB masih dapat menghapus trigger.
- Status run belum dijaga tabel transisi: run `COMPLETED` secara teknis masih dapat diubah
  statusnya sampai WP-1.6.
- `requested`, `coverage`, dan `limitations` pada run berupa JSON tanpa skema di DB.
