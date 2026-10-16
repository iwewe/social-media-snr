# 0010 - Penyimpanan artefak dan manifest

- **Status:** diterima (implementasi WP-1.5a). Penyaringan rahasia: WP-1.5b (ADR 0011).
- **Tanggal:** 2026-10-17

## Konteks

PRD bagian 10 mewajibkan artefak preservasi tidak ditimpa, memiliki manifest, timestamp/provenance,
dan SHA-256; berkas yang tidak tersedia atau tidak boleh disimpan dicatat sebagai keterbatasan,
bukan diganti berkas kosong (FR-037 sampai FR-039, FR-042; NFR-04).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Tata letak | `screenshots/<run>/<nama>` untuk screenshot; `captures/<run>/<nama>` untuk jenis lain; `manifests/<run>/manifest-<hash16>.json`. `<run>` = `public_id` run | Sesuai struktur PRD bagian 10; satu direktori per run mencegah tabrakan antar-pemeriksaan (FR-039). |
| Layanan | `preservation.service.persist_run_artifacts(run, result, *, policy)` | Satu jalur dari hasil adapter ke disk lewat `preservation.storage` (tidak pernah menimpa). |
| Kebijakan wajib | `policy` tanpa nilai bawaan; `UncheckedPolicy` hanya untuk tes dan dijaga uji arsitektur | Tidak ada jalur yang menyimpan artefak tanpa pemeriksaan. Penyaring produksi: WP-1.5b. |
| Penolakan | Artefak ditolak dicatat di `manifest.unavailable` dengan identitas aturan (tidak pernah isinya) dan **tidak disimpan**; tanpa berkas kosong pengganti | FR-042. |
| Idempoten | Jalur sudah tercatat dengan isi sama dilewati; isi berbeda = konflik, tidak ditimpa | NFR-03/FR-039. |
| Tahan terputus | Berkas yatim (tertulis, baris DB belum dibuat) diadopsi bila hash-nya cocok; bila berbeda = konflik | Proses dapat mati di antara dua langkah itu. |
| Isolasi kegagalan | Kegagalan satu artefak (terlalu besar, aliran putus) dicatat dan tidak merusak yang lain; tidak ada berkas parsial/sementara | NFR-04. Galat dicatat hanya jenisnya, bukan pesannya (pesan dapat memuat isi). |
| Serialisasi | Advisory lock PostgreSQL per run | Dua penyimpanan bersamaan atas run yang sama tidak saling bentrok. Diuji dengan tiga thread. |
| Manifest | Memuat `inspection_run_id`, target dan URL sumber, cara perolehan, versi collector, status/cakupan, daftar artefak yang benar-benar tersimpan (kind, path, SHA-256, ukuran, tipe, `stored_at`), `unavailable`, keterbatasan adapter, `generated_at` | PRD bagian 10. |
| Penamaan manifest | Memuat hash isi kanonik (tanpa `generated_at`); manifest dicatat sebagai artefak jenis `manifest` dan di-hash | Isi sama = berkas sama (tanpa ganda); isi berubah = manifest baru, yang lama utuh. Batas ukuran artefak tidak berlaku untuk manifest. |
| Status | `run.preservation`: `IN_PROGRESS` di awal; `FINISHED`/`FINISHED_WITH_PROBLEMS` + laporan | Penyimpanan yang terputus dapat dikenali (pola sama dengan `run.ingestion`). |
| Aliran | `ArtifactCapture` menerima `content` (bytes) ATAU `chunks` (pabrik aliran yang dapat dipanggil ulang) | Berkas besar tanpa memuat semuanya ke memori; pabrik dipanggil ulang saat pengulangan. |
| Batas ukuran | `SNR_ARTIFACT_MAX_BYTES` (usulan 512 MiB), ditegakkan di tengah aliran | **Angka asumsi**; PRD belum menetapkan. |
| Jenis `manifest` | Hanya dibuat SNR; adapter dilarang menghasilkannya (kontrak) | Adapter tidak boleh memalsukan manifest. |
| Ingestion | `ingest_result(..., artifact_sink=...)`; tanpa sink artefak ditandai `ARTIFACTS_NOT_PERSISTED`; sink gagal = `ARTIFACT_PERSISTENCE_FAILED`; ada kegagalan/konflik = `ARTIFACT_PERSISTENCE_PROBLEMS` | Tidak dibuang diam-diam; tidak membatalkan ingestion. Semuanya tidak memblokir rekonsiliasi (soal artefak, bukan kelengkapan observasi). |
| Verifikasi | `verify_run_artifacts(run)` membandingkan hash disk dengan catatan (hilang, hash berbeda) | FR-040, AT-06. |

## Keterbatasan dan hal terbuka

- Penyaringan cookies/token **belum ada** di PR ini; karena itu kebijakan wajib dan tidak ada bawaan.
  Jangan menyimpan data nyata sebelum WP-1.5b.
- Belum ada pemanggil produksi: orchestrator (WP-1.6) harus memasang `make_artifact_sink(kebijakan)`.
- Hash hanya membuktikan berkas tidak berubah sejak di-hash, bukan keaslian konten platform. Manifest
  tidak ditandatangani: pihak dengan akses tulis ke disk dan database sekaligus dapat mengubah
  keduanya secara konsisten (baris DB dijaga trigger append-only, tetapi bukan dari superuser).
- `ArtifactCapture` belum menyatakan post sasaran; kolom `EvidenceArtifact.post` belum terisi.
- Pabrik `chunks` harus menghasilkan isi yang sama pada pemanggilan ulang, jika tidak adopsi dan
  perbandingan akan melaporkan konflik. Ini tanggung jawab adapter.
- Untuk artefak yang sudah tersimpan, pemeriksaan idempoten menghitung ulang hash dari sumber
  (membaca aliran sekali lagi); mahal untuk media besar.
- Kuota disk, retensi, dan backup artefak belum diatur (WP-3.6).
