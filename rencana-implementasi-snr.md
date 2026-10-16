# SNR - Rencana Implementasi Rinci v0.1

**Rujukan:** `prd-snr.md` v0.1 (16 Oktober 2026)
**Bahasa:** Indonesia
**Sifat dokumen:** Rencana kerja turunan dari PRD. Dokumen ini tidak mengubah baseline PRD. Hal yang tidak ada di PRD ditandai **[Usulan]** dan dapat diubah setelah diuji.
**Tim:** Satu tim developer terpadu. Tidak ada pembagian peran atau jabatan.
**Estimasi:** Tidak ada tanggal atau durasi, karena PRD menyatakan milestone bukan komitmen tanggal. Ukuran pekerjaan memakai **S / M / L / XL** (relatif, bukan jam).

---

## 0. Cara memakai dokumen ini

- Setiap paket kerja (WP) memuat: tujuan, tugas, FR/NFR/AT yang dipenuhi, dependensi, dan kriteria selesai.
- Urutan WP mengikuti milestone PRD (I0 sampai I4). Satu WP baru dianggap selesai bila kriteria selesainya lulus, bukan saat kodenya ditulis.
- Prioritas P0/P1 mengikuti PRD bagian 6. P0 dikerjakan lebih dulu, tetapi tabel di bagian 3 menunjukkan bahwa sebagian P1 harus masuk lebih awal agar exit criteria milestone tercapai.
- Setiap keputusan teknis di luar baseline dicatat di `docs/decisions/` (satu berkas per keputusan, format ringkas: konteks, pilihan, keputusan, alasan).

## 1. Prinsip eksekusi

Diambil dari PRD bagian 3.3 dan 19, diterjemahkan menjadi aturan kerja:

1. **Observasi dan interpretasi dipisahkan di kode.** Modul `collection/` dan `preservation/` tidak boleh mengimpor `intelligence/`. Dijaga dengan uji arsitektur otomatis (WP-0.6).
2. **Append-only.** Tabel observasi dan artefak tidak memiliki jalur `UPDATE`/`DELETE` di kode aplikasi. Dijaga dengan model tanpa method ubah, permission DB, dan uji.
3. **Isolasi platform dijaga di skema.** Kolom `platform` wajib pada `ActorAccount`, `Post`, dan `GraphProjection`. Unique constraint selalu memuat `platform`. Fungsi analisis menerima satu `platform` sebagai argumen wajib.
4. **Ketidakpastian adalah status, bukan error.** Enum `NOT_OBSERVED`, `PARTIAL`, `ACCESS_RESTRICTED`, `UNSUPPORTED`, `UNDETERMINED`, `NOT_ASSESSABLE` dimodelkan sejak awal.
5. **Tidak ada vonis.** Tidak ada field, kolom, atau fungsi bernama atau berfungsi sebagai buzzer score. Dijaga dengan uji lint nama dan peninjauan kode.
6. **Dataset uji lebih dulu, platform nyata terakhir.** Seluruh I0 sampai I2 berjalan tanpa platform eksternal (FR-029, AT-18).
7. **Tidak ada bypass.** Tidak ada kode untuk CAPTCHA, rate-limit evasion, atau pemakaian akun palsu.

## 2. Peta ketergantungan

```text
I0 Bootstrap
  └─> I1 Inspeksi, Preservasi, Reinspection  (kontrak observasi, adapter uji, rekonsiliasi)
        └─> I2 Analisis & Jaringan           (M1-M5 di atas dataset uji)
        └─> I3 Adapter Platform              (bisa mulai setelah kontrak observasi stabil di I1)
              └─> I4 Pilot Investigasi       (butuh I2 dan minimal satu adapter I3 yang lulus uji)
```

Catatan: I3 hanya bergantung pada kontrak observasi (WP-1.1) dan feasibility. I3 tidak perlu menunggu I2 selesai. Studi feasibility per platform (WP-3.0) sebaiknya dimulai **paralel sejak I1** karena hasilnya belum diketahui dan bisa mengubah urutan I3.

## 3. Ringkasan paket kerja

| WP | Nama | Milestone | Ukuran | Prioritas PRD |
|---|---|---|---|---|
| WP-0.1 | Struktur repo dan tooling | I0 | M | P0 |
| WP-0.2 | Compose, PostgreSQL, Valkey | I0 | M | P0 |
| WP-0.3 | Auth Django dan izin dasar | I0 | S | P0 |
| WP-0.4 | Model Investigation, Issue, Proposition, Target, Context | I0 | M | P0 |
| WP-0.5 | UI workspace awal dan petunjuk kontekstual | I0 | M | P0 |
| WP-0.6 | Fondasi filesystem, pemisahan sesi browser, uji arsitektur | I0 | S | P0 |
| WP-1.1 | Kontrak observasi dan kontrak adapter | I1 | M | P0 |
| WP-1.2 | Model inti: ActorAccount, Post, PostRelation, PostObservation, InspectionRun | I1 | L | P0 |
| WP-1.3 | Ingestion idempoten | I1 | L | P0 |
| WP-1.4 | Rekonsiliasi antar-run | I1 | L | P0 |
| WP-1.5 | Preservasi: EvidenceArtifact, manifest, SHA-256 | I1 | L | P0 |
| WP-1.6 | Orchestrator dan Celery job lifecycle | I1 | L | P0 |
| WP-1.7 | Adapter dataset uji / impor | I1 | M | P0 |
| WP-1.8 | PoC Playwright pada halaman simulasi | I1 | L | P0 |
| WP-1.9 | UI target, run, riwayat, dan pesan status | I1 | M | P0 |
| WP-1.10 | Verifikasi hash dan akses bukti | I1 | S | P1 |
| WP-2.0 | Generator dataset sintetis | I2 | L | P0 (untuk validasi) |
| WP-2.1 | Versi konteks dan AnalysisRun/DatasetVersion | I2 | M | P0/P1 |
| WP-2.2 | Klasifikasi respons M2 dan review | I2 | XL | P1 |
| WP-2.3 | Profil aktor M3 | I2 | L | P1 |
| WP-2.4 | Interaction dan Stance Network | I2 | L | P1 |
| WP-2.5 | Behavioral Coordination Network dan indikator CO-01..06 | I2 | XL | P1 |
| WP-2.6 | Finding, confidence, evaluasi bukti M5 | I2 | L | P1 |
| WP-2.7 | UI respons, graf, profil, temuan | I2 | XL | P1 |
| WP-2.8 | Penelusuran bukti dan AuditEvent | I2 | M | P1 |
| WP-3.0 | Studi feasibility dan izin per platform | I3 | M per platform | prasyarat |
| WP-3.1 s.d. 3.5 | Adapter X, Threads, TikTok, Instagram, Facebook | I3 | L per platform | P1 |
| WP-3.6 | Pengerasan operasional (backup, restore, login limit, TLS) | I3 | M | P0/NFR |
| WP-4.1 | Persiapan pilot | I4 | M | - |
| WP-4.2 | Pelaksanaan pilot dan evaluasi | I4 | L | - |
| WP-4.3 | Catatan validasi dan daftar perbaikan | I4 | S | - |

---

## 4. I0 - Repository Bootstrap

**Tujuan:** aplikasi dasar berjalan; pengguna bisa login, membuat investigasi, mengisi target dan konteks, dan melihat catatan tersimpan.

### WP-0.1 Struktur repo dan tooling (M)

Tugas:
1. Buat struktur sesuai PRD bagian 17: `backend/`, `workers/`, `frontend/`, `tests/`, `deployment/`, `docs/`, `compose.yaml`.
2. Backend: proyek Django dengan app `accounts`, `investigations`, `collection`, `preservation`, `intelligence`, `reporting` (placeholder kosong, berisi README yang menyatakan "desain laporan ditunda").
3. Manajemen dependensi dan versi Python. **[Usulan]** `uv` atau `pip-tools` dengan lockfile; versi dikunci.
4. Linter, formatter, type-check **[Usulan]**: `ruff`, `mypy` (atau `pyright`) untuk backend; `eslint`, `prettier`, `tsc` untuk frontend.
5. Pre-commit hook dan CI dasar **[Usulan]** (GitHub Actions: lint, test, build).
6. `docs/decisions/` dan template keputusan; `docs/glossary.md` memuat istilah PRD bagian 5.
7. `.gitignore` yang memastikan `browser-profiles/`, `evidence/`, `.env`, cookies, dan dump database tidak pernah ter-commit (PRD bagian 13).

Kriteria selesai: `lint`, `typecheck`, dan `test` (walau masih kosong) berjalan di CI; `git status` bersih setelah membuat direktori data lokal.

### WP-0.2 Compose, PostgreSQL, Valkey (M)

Tugas:
1. `compose.yaml` dengan layanan: `web` (Django), `postgres`, `valkey`, `worker-analysis` (Celery), `worker-browser` (Celery + Playwright), `frontend` (dev server). Modular monolith: satu basis kode, beberapa proses.
2. Volume bind ke jalur yang selaras PRD bagian 10: `data/postgres`, `evidence/{captures,screenshots,manifests}`, `exports`, `browser-profiles`, `backups`. Volume `browser-profiles` hanya dipasang pada `worker-browser`.
3. Konfigurasi lewat environment variable; `.env.example` tanpa rahasia.
4. Health check tiap layanan.
5. Satu perintah untuk menjalankan seluruh lingkungan dev (`make up` atau setara).

Kriteria selesai: `compose up` pada mesin bersih menghasilkan aplikasi yang bisa diakses; worker Celery terhubung ke Valkey dan menjalankan tugas uji.

### WP-0.3 Auth Django dan izin dasar (S)

Memenuhi FR-001, FR-006.

Tugas:
1. Login/logout memakai Django Authentication; tidak ada Keycloak.
2. Semua view dan endpoint API mensyaratkan autentikasi secara default (middleware atau permission class global); halaman publik hanya login.
3. Django Groups/Permissions dasar tanpa merinci jabatan. **[Usulan]** satu grup bawaan "analyst" dan akun superuser.
4. Pembatasan percobaan login (PRD bagian 13). **[Usulan]** `django-axes` atau setara; boleh digeser ke WP-3.6 bila perlu, tetapi harus tercatat.
5. Uji: akses tanpa login ditolak untuk seluruh URL (uji yang mengiterasi seluruh URL pattern).

### WP-0.4 Model Investigation, Issue, Proposition, Target, Context (M)

Memenuhi FR-002, FR-003, FR-010 sampai FR-014, FR-016.

Tugas:
1. Model: `Investigation`, `Issue`, `Proposition`, `IssueContextVersion`, `CollectionTarget`, `TargetContextVersion`.
2. `CollectionTarget`: `platform` (enum 5 platform), `url`, jenis target (posting/akun), unik per `(investigation, platform, url_ternormalisasi)` agar AT-01 terpenuhi.
3. Versioning konteks: revisi membuat baris baru; baris lama tidak diubah (FR-014). Hanya satu versi "terkini" per target, tetapi semua versi dapat dirujuk.
4. Stance awal target: enum `PRO`, `CONTRA`, `MIXED`, `UNDETERMINED` (FR-013). Struktur sudah mendukung banyak proposition per target (FR-015), walau UI P1.
5. Field `Target Context Note` teks bebas; validasi panjang saja, tanpa membatasi isi.
6. Normalisasi URL target disimpan sebagai fungsi murni dengan uji (hapus parameter pelacakan, dsb.). **[Usulan]** aturan normalisasi dibuat per platform di adapter; di I0 cukup normalisasi generik.

Kriteria selesai: uji model memastikan revisi konteks tidak menimpa versi lama (AT-07 bagian data) dan URL yang sama tidak membuat target ganda (AT-01 bagian target).

### WP-0.5 UI workspace awal dan petunjuk kontekstual (M)

Memenuhi FR-004 (bagian I0), FR-090 (awal).

Tugas:
1. Kerangka frontend React + TypeScript; klien API; penanganan sesi Django (CSRF, cookie sesi).
2. Layar: login, daftar Investigation, detail Investigation (issue, proposition, target), formulir target dengan Target Context Note.
3. Komponen petunjuk kontekstual yang dapat dipakai ulang (`<ContextHelp id="...">`); teks bantuan disimpan di satu berkas konten agar mudah dipoles (PRD bagian 12). Isi petunjuk untuk: membuat Issue, mengisi Target Note, memulai inspeksi, reinspection, label ketidakpastian.
4. Daftar target menampilkan status inspeksi (awalnya "belum diperiksa").

Kriteria selesai: skenario manual "login, buat investigasi, issue, proposition, target, catatan konteks, lihat tersimpan" berjalan; petunjuk muncul di semua titik yang disebut PRD bagian 12 untuk langkah yang sudah ada.

### WP-0.6 Fondasi filesystem, sesi browser, dan uji arsitektur (S)

Tugas:
1. Modul `preservation.storage` yang menyediakan satu-satunya jalur menulis berkas bukti; menolak menimpa berkas yang sudah ada (FR-039). Detail lengkap di WP-1.5, di sini hanya kerangka dan uji "tidak menimpa".
2. Direktori `browser-profiles/` terpisah dari `evidence/`; uji bahwa kode ekspor/arsip bukti menolak jalur di bawah `browser-profiles/`.
3. Uji arsitektur otomatis: `collection/` dan `preservation/` tidak mengimpor `intelligence/`; tidak ada simbol bernama `*buzzer*` atau `*bot_score*`.

**Exit criteria I0 (dari PRD):** aplikasi dasar dapat dijalankan; pengguna bisa login, membuat investigasi, mengisi target dan konteks, serta melihat catatan tersimpan.

---

## 5. I1 - Inspection, Preservation & Reinspection

**Tujuan:** data respons dapat bertambah antarrun tanpa menggandakan identitas lama; bukti tiap run dapat diverifikasi dan ditelusuri.

### WP-1.1 Kontrak observasi dan kontrak adapter (M)

Memenuhi FR-022, FR-023, FR-024, FR-026; PRD bagian 7.1.

Tugas:
1. Definisikan skema observasi ternormalisasi (dataclass/pydantic) dengan field minimum dari PRD bagian 7.1: `platform`, `source_object_type`, `external_post_id`, `external_actor_id`, `parent_post_id`, `published_at`, `observed_at`, `text`, `inspection_run_id`, `collection_status`, `source_method`. Semua yang "jika tersedia" bersifat opsional dan eksplisit `None`, bukan nilai bawaan palsu.
2. Aturan: `published_at` tidak pernah diisi dengan `observed_at` (PRD bagian 9.3). Uji kontrak untuk ini.
3. Aturan identitas: bila sumber tidak punya ID stabil, observasi membawa flag `identity_needs_verification` dan tidak boleh digabung otomatis (PRD bagian 5).
4. Antarmuka adapter (PRD bagian 7.1): `capabilities()`, `validate_target_url()`, `inspect(request) -> InspectionResult` (observasi ternormalisasi plus metadata cakupan: pagination lengkap atau tidak, jumlah tampil di platform bila ada, kendala), pelaporan kegagalan terstruktur.
5. Enum status kegagalan: `ACCESS_RESTRICTED`, `UNSUPPORTED`, `PARSE_FAILED`, `PARTIAL`, dsb.
6. Suite uji kontrak di `tests/contracts/` yang dapat dijalankan terhadap **setiap** adapter (reusable, parametrized per adapter).

Kriteria selesai: adapter tiruan lulus suite kontrak; adapter yang melanggar (misalnya mengisi `published_at` dari `observed_at`) gagal.

### WP-1.2 Model inti data (L)

Memenuhi FR-030, FR-031, FR-033, bagian 8 PRD.

Tugas:
1. Model: `ActorAccount`, `Post`, `PostRelation`, `PostObservation`, `InspectionRun`, `EvidenceArtifact` (kerangka; detail di WP-1.5).
2. Unique constraint: `Post(platform, external_post_id)`, `ActorAccount(platform, external_actor_id)`.
3. `PostObservation`: satu baris per (Post, InspectionRun); menyimpan teks, atribut yang berubah, `published_at`, `observed_at`, `captured_at` terpisah; field "tidak diketahui" eksplisit.
4. `PostRelation`: tipe `reply`, `quote`, `repost`, `mention`, sumber relasi dicatat; relasi bisa punya observasi sendiri agar perubahan parent dapat dilacak.
5. Penanganan objek tanpa ID stabil: tabel/status kandidat identitas (`identity_unverified`) yang tidak ikut analisis sampai diverifikasi. **[Usulan]** field boolean plus antrean peninjauan.
6. Post dapat terkait ke beberapa Investigation lewat tabel penghubung (bukan duplikasi) - PRD bagian 8, relasi 3.
7. Migrasi dan indeks (pencarian per run, per target, per parent).
8. Penegakan append-only: tidak ada method `update` di manager observasi; **[Usulan]** trigger/permission DB yang menolak `UPDATE`/`DELETE` pada tabel observasi dan artefak.

Kriteria selesai: uji integritas model (unik per platform; akun bernama sama pada dua platform menjadi dua baris - dasar AT-13).

### WP-1.3 Ingestion idempoten (L)

Memenuhi FR-032, NFR-03, NFR-04, NFR-05.

Tugas:
1. Layanan ingestion: menerima `InspectionResult`, memvalidasi terhadap kontrak, menulis dalam transaksi per batch.
2. Upsert identitas: `get_or_create` pada kunci unik; race condition ditangani lewat constraint dan retry.
3. Setiap `PostObservation` membawa `inspection_run_id` dan sumber (provenance, NFR-05).
4. Kegagalan di tengah batch tidak merusak observasi yang sudah tervalidasi pada run itu atau run sebelumnya (NFR-04); batch yang gagal ditandai, bukan dibuang diam-diam.
5. Ingestion tidak pernah menghitung "jumlah komentar" dari satu angka; simpan terpisah `displayed_count` (dari platform) dan hitungan unik teramati (PRD bagian 9.3).

Uji: AT-02, AT-03 (pada tingkat layanan); uji properti: ingest ulang run yang sama dua kali tidak menambah baris `Post`/`ActorAccount` (NFR-03).

### WP-1.4 Rekonsiliasi antar-run (L)

Memenuhi FR-034, FR-035, FR-036; PRD bagian 9.2.

Tugas:
1. Fungsi rekonsiliasi: bandingkan observasi run baru dengan run sebelumnya pada target yang sama, hasil per objek: `NEW`, `UNCHANGED`, `MODIFIED`, `NOT_OBSERVED`.
2. `CONFIRMED_UNAVAILABLE` hanya bisa ditetapkan bila ada bukti memadai: **[Usulan]** syaratnya adalah run dengan cakupan "lengkap" menurut metadata adapter **dan** adapter menyatakan objek tidak ditemukan secara eksplisit (misalnya halaman objek mengembalikan status tidak tersedia). Tidak pernah diturunkan dari absensi di daftar.
3. Definisi "perubahan relevan" untuk `MODIFIED`: teks, parent, penulis, atribut yang disimpan. **[Usulan]** perbandingan atas representasi kanonik (hash isi ternormalisasi) agar perbedaan spasi/render tidak memicu `MODIFIED`.
4. Hasil rekonsiliasi disimpan sebagai data (tabel status per objek per run), bukan dihitung ulang tiap tampil.
5. Pemeriksaan jumlah: uji skenario wajib PRD: 20 lama + 5 baru = +5 identitas, bukan 25.
6. Run parsial: objek yang tidak muncul pada run `PARTIAL` selalu `NOT_OBSERVED`, tidak pernah dihapus.

Uji: AT-02, AT-03, AT-04, AT-05, AT-01.

### WP-1.5 Preservasi: EvidenceArtifact, manifest, SHA-256 (L)

Memenuhi FR-037, FR-038, FR-039, FR-042, NFR-02, NFR-07; PRD bagian 10.

Tugas:
1. Layanan penulisan artefak: tulis ke jalur yang unik per run (mis. mengandung `inspection_run_id` dan UUID), hitung SHA-256 saat penulisan, tulis manifest, catat di PostgreSQL (path, tipe, ukuran, hash, provenance).
2. Manifest per capture memuat: `inspection_run_id`, target dan URL sumber, timestamp, cara perolehan (`source_method`), status/cakupan, versi collector, daftar artefak yang benar-benar tersimpan.
3. Manifest sendiri di-hash dan dicatat.
4. Penulisan atomik (tulis ke berkas sementara lalu rename) agar kegagalan tidak meninggalkan artefak setengah jadi yang tercatat valid.
5. Pencatatan keterbatasan: bila screenshot/media/raw capture tidak tersedia atau tidak boleh disimpan, catat alasannya di manifest; jangan buat berkas kosong (FR-042).
6. Pencegahan kebocoran: filter yang menolak penyimpanan cookies/token/header autentikasi ke arsip bukti; uji dengan fixture yang sengaja memuat cookie.
7. Pembatasan akses file bukti lewat view Django terautentikasi, bukan URL statis publik.

Uji: AT-06 (hash cocok), uji bahwa penulisan kedua ke jalur yang sama ditolak (FR-039), uji manifest.

### WP-1.6 Orchestrator dan Celery job lifecycle (L)

Memenuhi FR-020, FR-021, FR-025, FR-026; PRD bagian 9.1.

Tugas:
1. Model status `InspectionRun`: `PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`, `ACCESS_RESTRICTED`, `UNSUPPORTED`, `REVIEW_REQUIRED`. Definisikan tabel transisi yang sah secara eksplisit dan uji setiap transisi (PRD: "state transition rinci harus diuji").
2. Orchestrator: pilih adapter berdasar platform, kirim tugas ke antrean yang tepat (browser vs lainnya), catat cakupan diminta, waktu, error, keterbatasan.
3. Idempotensi tugas Celery: tugas diulang (retry) tidak membuat run ganda atau observasi ganda.
4. Penanganan worker mati di tengah jalan: run yang `RUNNING` melewati batas waktu **[Usulan]** ditandai `FAILED` atau `PARTIAL` oleh proses penyapu, bukan dibiarkan menggantung. Batas waktu dibuat konfigurasi, tanpa angka bawaan yang diklaim final (PRD: angka harus diukur).
5. Aturan: tidak pernah memalsukan `COMPLETED` bila ada error yang belum ditangani.
6. Tombol "Inspect Again" membuat `InspectionRun` baru yang merujuk target yang sama (alur B), bukan target baru.

Uji: AT-14 (adapter kehilangan akses atau parser gagal menghasilkan status jelas, bukan nol respons), AT-01.

### WP-1.7 Adapter dataset uji / impor (M)

Memenuhi FR-029, AT-18.

Tugas:
1. Adapter `fixture` yang membaca dataset terstruktur (JSON/CSV sintetis) dan menghasilkan `InspectionResult` sesuai kontrak.
2. Kemampuan mensimulasikan: pertumbuhan komentar antar-run, komentar berubah, komentar hilang pada run parsial, kegagalan akses, parser gagal.
3. Format impor: dokumentasikan skema berkas impor di `docs/`. **[Usulan]** satu berkas per "snapshot" yang mewakili satu run, supaya skenario 4 putaran PRD dapat diputar ulang secara deterministik.
4. Impor dataset sungguhan yang sah memakai jalur yang sama (`source_method` berbeda), tetapi syarat legalitas diverifikasi di luar kode (PRD bagian 13).

### WP-1.8 PoC Playwright pada halaman simulasi (L)

PRD I1: "Browser-assisted proof of concept pada halaman uji yang dikendalikan sendiri."

Tugas:
1. Buat halaman simulasi statis/dinamis (server uji kecil) yang meniru struktur percakapan: reply bertingkat, pagination "muat lebih banyak", konten yang berubah antar kunjungan, halaman error 403/404, halaman parsial.
2. Worker browser: peluncuran Playwright, memakai profil dari `browser-profiles/` (terpisah dari bukti), ekstraksi observasi menggunakan kontrak WP-1.1, screenshot, snapshot DOM relevan sebagai artefak melalui WP-1.5.
3. Penanganan: timeout, halaman gagal dimuat, elemen yang tidak ditemukan, pagination yang terputus (dicatat sebagai `PARTIAL`, FR-026).
4. Tidak ada fitur untuk melewati CAPTCHA atau pembatasan; bila halaman menampilkan tantangan, hasilnya `ACCESS_RESTRICTED`.
5. Pencatatan versi collector (versi kode + versi Playwright/browser) di manifest.

Kriteria selesai: seluruh pengambilan pada halaman simulasi menghasilkan observasi, screenshot, manifest, dan hash yang valid; AT-14 teruji dengan halaman error simulasi.

### WP-1.9 UI target, run, riwayat, dan pesan status (M)

Memenuhi FR-090, FR-095, NFR-08, FR-004 (reinspection).

Tugas:
1. Layar target: tombol "Inspect" dan "Inspect Again", daftar InspectionRun dengan status, cakupan, kendala.
2. Daftar respons mentah per run (belum ada klasifikasi): penulis, waktu publikasi (atau "tidak diketahui"), parent, status rekonsiliasi (NEW/UNCHANGED/MODIFIED/NOT_OBSERVED), tautan ke artefak.
3. Pesan ramah untuk: akses ditolak, pengambilan parsial, data tidak lengkap, kegagalan parser, konteks belum cukup (FR-095).
4. UI membedakan tiga keadaan: **tidak ada data**, **belum diperiksa**, **gagal mengakses data** (NFR-08).
5. Petunjuk kontekstual untuk memulai inspeksi dan reinspection (PRD bagian 12).
6. Tampilkan terpisah "jumlah ditampilkan platform" vs "jumlah unik teramati" (PRD 9.3).

### WP-1.10 Verifikasi hash dan akses bukti (S, P1)

Memenuhi FR-040.

Tugas: tombol/endpoint "verifikasi artefak" yang menghitung ulang SHA-256 dan membandingkan dengan catatan; menampilkan hasil dan menyertakan pernyataan integritas PRD bagian 10 (hash tidak membuktikan keaslian konten platform). Akses dibatasi hak akses.

**Exit criteria I1 (dari PRD):** data respons dapat bertambah antarrun tanpa menggandakan identitas lama; bukti setiap run dapat diverifikasi dan ditelusuri.

**Uji penerimaan I1:** AT-01, AT-02, AT-03, AT-04, AT-05, AT-06, AT-14, AT-18 (bagian inspeksi).

---

## 6. I2 - Contextual Analysis & Network

**Tujuan:** dataset sintetis menghasilkan label dan graf yang dapat diperiksa; tidak muncul penggabungan platform atau vonis otomatis buzzer.

### WP-2.0 Generator dataset sintetis (L)

Memenuhi PRD bagian 16.1.

Tugas:
1. Generator deterministik (seed tetap) untuk: **3 target posting, 50 akun sintetis, sekitar 300 reply/comment, 4 putaran inspeksi**.
2. Skenario yang disimulasikan sesuai PRD: (1) percakapan pro/kontra organik, (2) serangan personal yang bukan koordinasi, (3) pola aktivitas bersama yang sengaja disimulasikan, (4) penambahan, perubahan, dan ketidakmunculan objek antar pemeriksaan.
3. Tambahan kasus tepi: reply "setuju" pada reply tingkat kedua (AT-08), komentar yang mengacu isi video (AT-09), kritik sah vs serangan personal (AT-10), banyak akun stance sama tanpa koordinasi (AT-11), username sama di dua platform (AT-13), actor profile dari sebagian target (AT-17). Lampiran A PRD dipakai persis sebagai kasus uji konteks.
4. Berkas "kunci jawaban" (ground truth) terpisah untuk setiap skenario simulasi, dipakai uji untuk memeriksa bahwa pola yang ditanam terdeteksi sebagai **indikator** (bukan sebagai vonis) dan pola organik tidak.
5. Seluruh data diberi label sintetis jelas; tidak meniru akun atau orang nyata.

Catatan: ukuran dataset adalah target latihan, bukan klaim kecukupan statistik (PRD 16.1).

### WP-2.1 Versi konteks, DatasetVersion, AnalysisRun (M)

Memenuhi FR-014, NFR-01; bagian 8 PRD relasi 5-6.

Tugas:
1. `DatasetVersion`: rujukan himpunan observasi (daftar run/rentang observasi) yang dibekukan sebagai input analisis. **[Usulan]** snapshot sebagai daftar ID observasi tak-berubah plus hash daftar.
2. `AnalysisRun`: menunjuk `DatasetVersion`, versi `IssueContextVersion` dan `TargetContextVersion`, parameter (JSON), versi metode/model, platform scope, waktu, status.
3. Konteks dibekukan per AnalysisRun; revisi konteks tidak mengubah AnalysisRun lama (AT-07 lengkap).
4. Fitur "analisis ulang pada dataset terbaru" membuat `DatasetVersion` dan `AnalysisRun` baru tanpa menghapus yang lama (FR-041, alur B langkah 7).
5. Uji reproducibility: menjalankan ulang AnalysisRun lama dengan dataset, konteks, dan parameter yang sama menghasilkan keluaran identik untuk komponen deterministik (NFR-01).

### WP-2.2 Klasifikasi respons M2 dan review (XL, P1)

Memenuhi FR-050 sampai FR-057; PRD bagian 11.2.

Tugas:
1. Model `ResponseAssessment`: referensi ke observasi, proposition, versi konteks, `AnalysisRun`; dimensi terpisah: `issue_stance` (6 label), `target_alignment`, `expression_sentiment`, `response_character` (multi-label, RC-01..RC-10), `narrative_function`; alasan/dasar yang bisa diperiksa; status review.
2. **Konstruksi konteks percakapan:** untuk tiap reply, rakit rantai parent yang nyata (bukan langsung ke seed) sebagai input klasifier (AT-08).
3. **Antarmuka klasifier (strategy pattern):** `classify(response, parent_chain, proposition, target_context) -> Assessment`. Memungkinkan beberapa implementasi tanpa mengubah model data.
4. **Pemilihan model/penyedia NLP belum diputuskan (PRD).** Rencana: (a) bangun baseline sederhana dan aturan yang dapat diperiksa untuk menguji seluruh alur end-to-end, (b) siapkan harness evaluasi (WP-2.2e) sebelum memilih model, (c) pilihan model dicatat sebagai keputusan di `docs/decisions/` setelah evaluasi. Tidak ada klaim kualitas sebelum evaluasi.
5. Label `UNDETERMINED` dan `NOT_RELEVANT` sebagai hasil yang sah dan didorong; ambang untuk jatuh ke `UNDETERMINED` dibuat konfigurasi (angka belum disepakati).
6. Aturan: tidak ada kesimpulan benar/salah klaim (FR-057); tidak ada fact-check; Target Context Note hanya panduan, bukan paksaan label (FR-016).
7. RC-07 (Intimidation/Threat) selalu menandai "perlu tinjauan manusia".
8. **Review manusia:** koreksi label menghasilkan versi assessment baru dengan jejak (`AuditEvent`), tidak menimpa hasil mesin (FR-055, AT-16).
9. **WP-2.2e Harness evaluasi:** alat untuk memuat set anotasi (pilot 50-100 respons, PRD 16.3), menghitung kesepakatan antar-penilai, precision/recall/F1 per kelas, analisis error untuk sarkasme, parent bertingkat, dan bahasa Indonesia informal. Hasil hanya bersifat pilot.

Uji: AT-08, AT-09, AT-10, AT-16, dan seluruh kasus Lampiran A.

### WP-2.3 Profil aktor M3 (L, P1)

Memenuhi FR-060 sampai FR-065; PRD bagian 11.3.

Tugas:
1. `ActorIssueProfile`: unit = ActorAccount pada satu platform, terikat issue/proposition, periode, `AnalysisRun`, dan **coverage statement** wajib (tidak boleh null).
2. Tujuh dimensi: participation, stance distribution, response character, temporal activity, target concentration, narrative consistency (dalam teks tersedia), activity evolution - masing-masing dihitung hanya bila data cukup; bila tidak cukup, dimensi bernilai "data tidak cukup" bukan nol.
3. Profil Level A (dari respons teramati pada target investigasi) dibangun otomatis; Level B (inspeksi tambahan, alur C, FR-061) memakai InspectionRun tambahan dengan adapter platform yang sama dan selalu memerlukan penetapan isu dan periode.
4. Perbandingan antar-akun menampilkan peringatan bila cakupan tidak sebanding (FR-064).
5. Tidak ada field atau tampilan yang menyiratkan label kepribadian, identitas orang, atau status buzzer (FR-065, dijaga uji nama).

Uji: AT-17.

### WP-2.4 Interaction Network dan Stance Network (L, P1)

Memenuhi FR-070, FR-071, FR-073, FR-074.

Tugas:
1. `GraphProjection` dengan **tepat satu platform scope** (constraint DB dan validasi; AT-13, NFR-06).
2. Interaction Network: node = ActorAccount, edge = relasi yang benar-benar teramati (reply, quote, repost, mention) dari `PostRelation`; tipe edge dan asal tersimpan per edge.
3. Stance Network View: stance sebagai atribut node/edge pada graf yang sama; **stance sama tidak membuat edge** (AT-11).
4. Simpan definisi node/edge, versi dataset, aturan pembobotan, jendela waktu, parameter (FR-074).
5. Metrik struktur (centrality, community detection) via NetworkX dengan label eksplisit "menggambarkan struktur jaringan, bukan pengendali" (PRD 11.4). Seed dan parameter disimpan agar community detection dapat direproduksi; stabilitas diuji (PRD bagian 18 menyebutnya belum diketahui).
6. Batas skala: tidak ada klaim skala; ukur pada dataset sintetis dan catat.

### WP-2.5 Behavioral Coordination Network dan indikator CO-01..06 (XL, P1)

Memenuhi FR-072, FR-075, FR-076, FR-077; PRD bagian 11.4.

Tugas:
1. Graf terpisah dari Interaction Network (model, tabel, dan tampilan berbeda); setiap edge membawa jenis indikator dan nilai terhitung, bukan "interaksi".
2. Implementasi indikator, masing-masing dengan parameter (jendela waktu, bobot, baseline) yang tersimpan di `AnalysisRun`:
   - CO-01 Co-Response
   - CO-02 Temporal Synchronization
   - CO-03 Content Similarity (teks)
   - CO-04 Co-Amplification
   - CO-05 Shared Narrative / URL
   - CO-06 Repeated Participation lintas target (dalam satu platform)
3. **Tidak ada ambang baku (PRD).** Seluruh ambang berupa parameter yang wajib diisi eksplisit per AnalysisRun; tidak ada nilai bawaan yang dipresentasikan sebagai "ambang koordinasi". Dokumentasikan di UI bahwa nilai awal hanya untuk eksplorasi.
4. **Baseline:** hitung indikator juga pada pembanding (mis. permutasi/penugasan acak waktu atau akun pada dataset yang sama **[Usulan]**) agar pengguna dapat melihat seberapa jauh nilai berbeda dari kebetulan. Pilihan metode baseline dicatat sebagai keputusan.
5. Setiap hasil `IndicatorResult` menyertakan penjelasan, daftar bukti pendukung (observasi), dan daftar **hipotesis alternatif** yang harus dipertimbangkan (mobilisasi organik, efek peristiwa eksternal, penyalinan konten publik, bias sampling - PRD 11.5).
6. Indikator dari event yang sama tidak dihitung sebagai bukti independen: tandai korelasi antar-indikator.
7. Kesamaan stance atau intensitas saja tidak boleh memicu hasil koordinasi (FR-075, AT-11); uji negatif pada skenario organik dan serangan personal.
8. Hasil indikator bukan Finding: harus melewati peninjauan manusia (FR-077).

Uji: AT-11, AT-12; uji pada ground truth dataset sintetis (pola ditanam terdeteksi sebagai indikator, pola organik tidak).

### WP-2.6 Finding, confidence, evaluasi bukti M5 (L, P1)

Memenuhi FR-077, FR-078, FR-079, FR-080; PRD bagian 11.5.

Tugas:
1. `Finding`: tertaut ke observasi dan `AnalysisRun`, status peninjauan, confidence (`HIGH`/`MODERATE`/`LOW`/`NOT_ASSESSABLE`) **dengan alasan wajib**, sejarah supersession (`SUPERSEDED`).
2. Evaluasi kualitas bukti pada empat sumbu terpisah: `integrity`, `provenance`, `completeness`, `relevance`; sumbu `integrity` terhubung ke verifikasi hash (WP-1.10), `completeness` terhubung ke metadata cakupan run.
3. Empat tingkat hasil (Observed Evidence, Analytical Classification, Behavioral & Network Pattern, Reviewed Analytical Finding) ditandai jelas pada data dan UI.
4. Temuan baru setelah reinspection dapat menggantikan temuan lama; yang lama tetap dapat diakses (AT-15).
5. **Larangan:** tidak ada Buzzer Score, tidak ada vonis operasi berbayar/aktor pengendali (FR-079). Dijaga dengan uji arsitektur dan tinjauan skema.
6. Alur: indikator, peninjau menulis interpretasi, wajib mengisi pertimbangan hipotesis alternatif sebelum Finding dapat disahkan **[Usulan]** (validasi di layer layanan).

Uji: AT-15, AT-16.

### WP-2.7 UI respons, graf, profil, temuan (XL, P1)

Memenuhi FR-091 sampai FR-094; PRD bagian 12.

Tugas:
1. Daftar respons dengan klasifikasi, status review, dan tautan ke observasi, bukti, serta rantai parent.
2. Graf interaktif memakai Cytoscape.js dengan filter jenis relasi, cakupan waktu, dan atribut stance (FR-092). **Interaction edge dan edge kesamaan perilaku tampil berbeda secara visual dan diberi legenda** (AT-12). Uji performa pada ukuran dataset sintetis; batasi jumlah node yang ditampilkan lewat filter, tanpa klaim skala.
3. Halaman profil aktor terbatas pada isu dan platform; coverage statement tampil di bagian atas.
4. Antarmuka membedakan tiga kategori: **fakta observasi**, **hasil mesin**, **temuan yang telah ditinjau** (FR-094) - mis. lencana dan warna konsisten.
5. Seluruh petunjuk di tabel PRD bagian 12 untuk: melihat respons, Actor Profile, Network, temuan.
6. Tidak ada elemen UI bertema "skor buzzer" atau peringkat "paling mencurigakan".

### WP-2.8 Penelusuran bukti dan AuditEvent (M, P1)

Memenuhi FR-005, bagian 8 PRD (`AuditEvent`), M5.

Tugas:
1. `AuditEvent` untuk perubahan konteks, klasifikasi, review, dan temuan (siapa, kapan, sebelum/sesudah, alasan).
2. Navigasi satu klik dari node/edge/label/Finding menuju observasi dan artefak pendukung (FR-005).
3. Halaman jejak: tampilkan sejarah versi konteks, versi klasifikasi, dan status temuan.

**Exit criteria I2 (dari PRD):** dataset sintetis menghasilkan label dan graf yang dapat diperiksa; tidak muncul penggabungan platform atau vonis otomatis buzzer.

**Uji penerimaan I2:** AT-07, AT-08, AT-09, AT-10, AT-11, AT-12, AT-13, AT-15, AT-16, AT-17.

---

## 7. I3 - Platform Adapters

**Tujuan:** hanya kemampuan platform yang telah diuji dan diizinkan dinyatakan aktif; kegagalan ditandai jelas dan tidak mengubah core data model.

### WP-3.0 Studi feasibility dan izin per platform (M per platform)

Dikerjakan **sebelum** menulis adapter, dan dimulai paralel sejak I1.

Untuk setiap platform (X, Threads, TikTok, Instagram, Facebook), hasilkan satu dokumen `docs/adapters/<platform>-feasibility.md` berisi:
1. **Jalur perolehan yang sah:** apakah ada API resmi, apakah syarat layanan mengizinkan pemeriksaan browser terotorisasi, apakah ada ekspor data yang sah, apakah dataset impor yang sah tersedia.
2. **Kemampuan teruji:** posting, respons, akun; cakupan komentar publik; pagination; perilaku untuk konten yang memerlukan login.
3. **Ketahanan parser:** seberapa sering struktur halaman berubah (diukur dengan pengamatan berulang, bukan diasumsikan).
4. **Batasan:** pembatasan akses, kebutuhan login, jenis objek yang tidak dapat diambil.
5. **Keputusan:** `ACTIVE` (kemampuan tertentu), `LIMITED`, atau `DISABLED`, serta alasan.

Pernyataan eksplisit (PRD bagian 7 dan 13): tidak ada mekanisme untuk melewati CAPTCHA, pembatasan akses, atau larangan platform. Login browser bukan persetujuan untuk pengumpulan otomatis; bila jalur sah tidak ada, adapter melaporkan `ACCESS_RESTRICTED`/`UNSUPPORTED`.

Verifikasi izin adalah keputusan organisasi/pengguna di luar kode; tim developer tidak boleh menyimpulkan legalitas sendiri (PRD bagian 1: batas dokumen).

### WP-3.1 sampai WP-3.5 Adapter per platform (L per platform)

Dikerjakan **satu per satu dan independen**; urutan ditentukan oleh hasil feasibility (WP-3.0). **[Usulan]** mulai dari platform dengan jalur sah paling jelas.

Template tugas per adapter:
1. Implementasi `capabilities()`, `validate_target_url()`, `inspect()` sesuai kontrak WP-1.1.
2. Model data platform-spesifik tetap dipetakan ke skema inti tanpa menambah kolom pada tabel inti (exit criteria: tidak mengubah core data model).
3. Aturan platform (PRD bagian 7):
   - **X:** posting plus lampiran media; reply, quote, repost, mention sejauh teruji.
   - **Threads:** thread dan media; tidak diasumsikan identik dengan X.
   - **TikTok:** video dan caption; komentar dan reply bertingkat; video dipreservasi, tidak ditranskrip.
   - **Instagram:** post, carousel, Reel; komentar dan reply; media dipreservasi, tidak ditafsirkan.
   - **Facebook:** post dan konteks Page/ruang publik yang sah; jenis ruang asal dan pembatasan akses dicatat.
4. Lulus suite kontrak (WP-1.1) dan uji integrasi dengan rekaman respons (fixture hasil tangkapan yang sah, bukan akses langsung di CI).
5. Pengelolaan sesi/cookies sesuai bagian 13: tersimpan hanya di `browser-profiles/`, tidak pernah di Git, log, output AI, atau evidence.
6. Penanganan perubahan struktur halaman: kegagalan parser menghasilkan `PARSE_FAILED`/`PARTIAL`, bukan data kosong (AT-14).
7. Fitur adapter diaktifkan lewat flag per kemampuan; yang belum lulus feasibility tetap nonaktif dan UI menampilkan alasan keterbatasan.
8. Preservasi media asli hanya bila dapat diperoleh dan disimpan secara sah; jika tidak, catat keterbatasan (alur D).

Kriteria selesai per adapter: dokumen feasibility selesai dan disetujui; suite kontrak lulus; kemampuan yang aktif tercantum eksplisit dan sama dengan yang diuji.

### WP-3.6 Pengerasan operasional (M)

Memenuhi PRD bagian 13, NFR-10.

Tugas:
1. Pembatasan percobaan login (bila belum di WP-0.3), TLS/HTTPS di depan aplikasi.
2. Backup lokal terpisah dari penyimpanan utama (PostgreSQL dan `evidence/`), skrip backup, **uji restore terencana** dan didokumentasikan hasilnya (NFR-10). Perangkat dan kapasitas ditentukan berdasar pengukuran pilot (PRD).
3. Kontrol akses file lokal (izin OS) dan audit akses bukti.
4. Prosedur penghapusan/retensi disiapkan sebagai kerangka; durasi angka final **belum ditentukan** dan menunggu keputusan.
5. Pemindaian kebocoran rahasia (cookies/token) pada repo dan log di CI **[Usulan]**.

**Exit criteria I3 (dari PRD):** hanya kemampuan platform yang telah diuji dan diizinkan dinyatakan aktif; kegagalan ditandai jelas dan tidak mengubah core data model.

**Uji penerimaan I3:** AT-13, AT-14 pada tiap adapter aktif.

---

## 8. I4 - Pilot Investigation

**Tujuan:** ada catatan hasil validasi dan daftar perbaikan prioritas yang didasarkan pada pengujian nyata.

### WP-4.1 Persiapan pilot (M)
1. Tetapkan satu investigasi terbatas dan target nyata yang diperoleh secara sah (jalur dari WP-3.0). Tetapkan cakupan, periode, dan platform.
2. Konfirmasi bahwa dasar izin penggunaan data tertulis; konfirmasi kebijakan retensi sementara untuk pilot.
3. Siapkan set anotasi pilot untuk respons nyata (50-100 respons, ideal dua penilai independen - PRD 16.3).
4. Tetapkan metrik pilot yang akan dicatat (tanpa menetapkan "target lulus" yang tidak ada di PRD): kelengkapan pengambilan vs yang ditampilkan platform, kegagalan parser per platform, F1 per kelas, waktu job, ukuran penyimpanan, hasil uji restore.

### WP-4.2 Pelaksanaan pilot dan evaluasi (L)
1. Jalankan alur A, B, C, D pada target nyata, termasuk setidaknya dua kali reinspection pada jarak waktu berbeda.
2. Evaluasi kualitas pengambilan (cakupan, pagination, status parsial), kualitas klasifikasi (F1, kesepakatan, analisis error sarkasme/parent bertingkat/bahasa informal), kualitas graf dan stabilitas community detection, integritas preservasi, kegunaan petunjuk dalam aplikasi.
3. Catat kelemahan nyata **tanpa mengubah baseline secara spekulatif** (PRD). Perubahan baseline hanya lewat keputusan tertulis dengan dasar temuan pilot.
4. Evaluasi apakah indikator koordinasi menghasilkan terlalu banyak positif palsu pada data nyata; parameter hanya disesuaikan sebagai parameter AnalysisRun, bukan ambang baku, kecuali ada keputusan eksplisit.

### WP-4.3 Catatan validasi dan daftar perbaikan (S)
1. Dokumen `docs/pilot/hasil-validasi.md` berisi hasil terukur, temuan kelemahan, dan daftar perbaikan terprioritas.
2. Diskusikan desain laporan **setelah** hasil pilot menunjukkan bentuk data dan temuan (FR-096, Deferred).
3. Perbarui keputusan terbuka (bagian 11 dokumen ini) dengan angka dan keputusan baru bila ada.

**Exit criteria I4 (dari PRD):** ada catatan hasil validasi dan daftar perbaikan prioritas yang didasarkan pada pengujian nyata.

---

## 9. Strategi pengujian

| Lapisan | Isi | Tempat |
|---|---|---|
| Unit | Normalisasi URL, rekonsiliasi, hash/manifest, tabel transisi status, indikator CO | `tests/` per modul |
| Kontrak | Suite adapter yang sama dijalankan ke setiap adapter | `tests/contracts/` |
| Integrasi | Run penuh pada dataset sintetis: inspeksi, ingest, rekonsiliasi, analisis | `tests/integration/` |
| Arsitektur | Batas impor modul, larangan nama "buzzer/bot score", constraint satu-platform per graf | `tests/architecture/` |
| Properti | Idempotensi ingestion, determinisme analisis (NFR-01, NFR-03) | `tests/integration/` |
| End-to-end UI | Alur A sampai D pada halaman simulasi (Playwright) | `tests/e2e/` |
| Evaluasi model | Harness F1/kesepakatan; hasil pilot, bukan gate CI | `tests/evaluation/` |

**Pemetaan AT ke WP (lengkap):**

| AT | Dipenuhi oleh |
|---|---|
| AT-01 | WP-0.4, WP-1.4, WP-1.6 |
| AT-02, AT-03 | WP-1.3, WP-1.4 |
| AT-04, AT-05 | WP-1.4 |
| AT-06 | WP-1.5, WP-1.10 |
| AT-07 | WP-0.4, WP-2.1 |
| AT-08, AT-09, AT-10 | WP-2.0, WP-2.2 |
| AT-11, AT-12 | WP-2.4, WP-2.5, WP-2.7 |
| AT-13 | WP-1.2, WP-2.4, WP-3.1..3.5 |
| AT-14 | WP-1.6, WP-1.8, WP-3.1..3.5 |
| AT-15 | WP-2.6 |
| AT-16 | WP-2.2, WP-2.8 |
| AT-17 | WP-2.3 |
| AT-18 | WP-1.7, WP-1.8 |

**Pemetaan NFR ke WP:** NFR-01 (WP-2.1), NFR-02 (WP-1.5), NFR-03 (WP-1.3), NFR-04 (WP-1.3, WP-1.6), NFR-05 (WP-1.3), NFR-06 (WP-2.4), NFR-07 (WP-1.5), NFR-08 (WP-1.9), NFR-09 (WP-2.2, WP-2.6), NFR-10 (WP-3.6).

**Prinsip pengujian:** CI tidak mengakses platform nyata; semua uji memakai fixture. Uji ke platform nyata hanya manual/terjadwal dalam WP-3.0 dan I4.

## 10. Daftar risiko dan mitigasi dalam rencana

| Risiko | Dampak | Mitigasi dalam rencana |
|---|---|---|
| Akses sah ke satu atau lebih platform tidak tersedia | Adapter tidak bisa aktif | WP-3.0 lebih dulu; adapter boleh `DISABLED`; dataset impor sah sebagai jalur alternatif; core model tetap berfungsi |
| Parser rapuh karena perubahan struktur halaman | Data parsial/salah | Status `PARSE_FAILED`/`PARTIAL`, bukan nol; fixture rekaman; pemantauan kegagalan di pilot |
| Kualitas NLP bahasa Indonesia informal rendah | Klasifikasi tidak dapat dipercaya | Antarmuka klasifier dapat diganti; evaluasi sebelum memilih model; `UNDETERMINED` sebagai hasil sah; review manusia |
| Indikator koordinasi menghasilkan positif palsu | Salah tafsir sebagai vonis | Tanpa ambang baku; baseline; hipotesis alternatif wajib; tidak ada skor; peninjauan manusia |
| Duplikasi identitas karena ID tidak stabil | Hitungan salah, graf salah | Flag `identity_needs_verification`; tidak digabung otomatis |
| Scope creep ke lintas platform | Melanggar baseline | Constraint skema dan uji arsitektur satu-platform |
| Kebocoran cookies/kredensial | Risiko keamanan | Pemisahan `browser-profiles/`, filter evidence, pemindaian rahasia di CI, `.gitignore` |
| Kapasitas penyimpanan tidak diketahui | Evidence memenuhi disk | Pengukuran di pilot; pemantauan ukuran; keputusan kapasitas setelah ukur |
| Dataset sintetis terlalu "bersih" | Lulus uji tetapi gagal di data nyata | Pilot I4 sebagai validasi terpisah; PRD menyatakan lulus MVP bukan validasi ilmiah |
| Desakan memutuskan format laporan terlalu dini | Pekerjaan sia-sia | Folder `reporting/` hanya placeholder sampai I4 selesai |

## 11. Keputusan terbuka yang harus diputuskan (bukan diasumsikan)

| # | Keputusan | Diperlukan sebelum | Cara memutuskan |
|---|---|---|---|
| D-01 | Model/penyedia NLP untuk M2 | Akhir WP-2.2 | Evaluasi harness pada set anotasi pilot |
| D-02 | Ambang dan parameter indikator koordinasi | WP-2.5 (eksplorasi), I4 (evaluasi) | Eksperimen pada sintetis, validasi pada pilot; ditetapkan per AnalysisRun |
| D-03 | Jalur perolehan sah tiap platform | WP-3.1..3.5 | WP-3.0 dan keputusan izin dari pihak berwenang di luar tim |
| D-04 | Retensi dan penghapusan data (durasi) | WP-3.6 (kerangka), I4 (angka) | Keputusan kebijakan |
| D-05 | Kapasitas penyimpanan dan perangkat backup | WP-3.6 | Pengukuran pilot |
| D-06 | Batas waktu job dan jumlah worker | WP-1.6 (konfigurasi), I4 (nilai) | Pengukuran; tidak ada SLA dari PRD |
| D-07 | Metode baseline indikator koordinasi | WP-2.5 | Keputusan tertulis setelah uji pada sintetis |
| D-08 | Desain laporan | Setelah I4 | Diskusi berbasis data pilot |
| D-09 | Penjadwalan otomatis reinspection | Setelah MVP | Hanya pada sumber yang mengizinkan |

## 12. Definisi selesai MVP (cek akhir)

Mengikuti PRD bagian 20; dipakai sebagai daftar periksa demonstrasi pada akhir I2 (dengan adapter uji/dataset):

- [ ] 1. Login; buat investigation, issue, proposition, target, catatan konteks.
- [ ] 2. Pemeriksaan target lewat adapter uji/browser terizin; observasi dan preservasi lokal dengan hash valid.
- [ ] 3. Pemeriksaan ulang target yang sama; komentar baru tersimpan tanpa duplikasi; riwayat lama utuh.
- [ ] 4. Penilaian stance/karakter respons yang dapat direview; penelusuran ke parent dan bukti.
- [ ] 5. Actor-Issue Profile dengan batas cakupan.
- [ ] 6. Graf relasi dan indikator pola yang dibedakan dari observasi langsung.
- [ ] 7. Kasus ambigu, akses gagal, data parsial, dan isolasi identitas lintas platform teruji.
- [ ] 8. Tidak ada vonis otomatis buzzer dan tidak ada analisis semantik isi video/gambar.

Kelulusan MVP fungsional tidak sama dengan kelulusan semua konektor platform atau validasi ilmiah pada data nyata; keduanya dilaporkan terpisah (I3 dan I4).

## 13. Urutan kerja yang disarankan di dalam tiap milestone

**I0:** WP-0.1, WP-0.2, WP-0.3, WP-0.4, lalu WP-0.5 dan WP-0.6 (paralel).

**I1:** WP-1.1, WP-1.2, lalu WP-1.3, WP-1.5, WP-1.7 (paralel), WP-1.4, WP-1.6, WP-1.8, WP-1.9, WP-1.10. Mulai WP-3.0 paralel setelah WP-1.1 stabil.

**I2:** WP-2.0 dan WP-2.1 lebih dulu, lalu WP-2.2, WP-2.3, WP-2.4 (paralel sebagian), WP-2.5, WP-2.6, kemudian WP-2.7 dan WP-2.8 (UI mengikuti kematangan layanan). Demonstrasi MVP (bagian 12).

**I3:** WP-3.0 selesai, adapter dikerjakan bertahap sesuai hasil feasibility, WP-3.6 berjalan paralel.

**I4:** WP-4.1, WP-4.2, WP-4.3.

## 14. Catatan perubahan dokumen

| Versi | Ringkasan |
|---|---|
| v0.1 | Rencana implementasi awal dari `prd-snr.md` v0.1: paket kerja per milestone, pemetaan FR/NFR/AT, strategi uji, risiko, dan keputusan terbuka. |
