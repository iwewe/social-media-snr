# 0031 - API analisis I2: respons, graf, indikator, profil, temuan, jejak bukti

- **Status:** diterima (WP-2.7a; FR-091..FR-094, FR-005; AT-12, AT-15, AT-16). Antarmuka React (WP-2.7b) dibangun di atas API ini pada PR terpisah.
- **Tanggal:** 2026-10-18

## Konteks

Hasil I2 (klasifikasi M2, profil M3, graf M4, indikator koordinasi, temuan M5) baru dapat diakses lewat layanan Python. UI membutuhkan API baca yang
aman, dan beberapa aksi tulis (tinjauan klasifikasi, pembuatan, pengesahan, dan penarikan temuan). WP-2.7 dipecah dua PR agar tidak ada PR bertumpuk: API
dulu (PR ini), lalu UI.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Otorisasi | Semua objek diambil lewat `api/access.py` (`analysis_run_for`, `assessment_for`, `profile_for`, `finding_for`, `observation_for`): non-anggota 404 identik dengan id tak ada, peran kurang 403. Baca = VIEWER; menulis (tinjau klasifikasi, buat/revisi/sahkan/tarik temuan, saran bukti) = MEMBER. Tes keamanan arsitektur kini melarang `get_object_or_404` langsung untuk model analisis dan matriks endpoint x peran mencakup semua 16 rute baru. | ADR 0021/0022. |
| Rute | `investigations/{id}/analysis-runs/`, `analysis-runs/{id}/` (+ `responses/`, `graph/`, `coordination/`, `profiles/`), `assessments/{id}/review|history/`, `profiles/{id}/`, `investigations/{id}/findings/` (+ `evidence/`), `findings/{id}/` (+ `revise|endorse|withdraw/`), `observations/{id}/`. | Satu rute per sumber daya yang dibutuhkan UI. |
| Tingkat dan kategori | Setiap payload memuat `tier` (1-4), `tier_label`, `category` (`observed_fact`, `machine_result`, `human_reviewed`, `reviewed_finding`) dan labelnya, agar UI membedakan fakta observasi, hasil mesin, koreksi manusia, dan temuan yang ditinjau (FR-094) tanpa menebak. | PRD 11.5, FR-094. |
| Respons | Daftar berhalaman (maks 200) dengan filter stance, alignment, karakter RC, asal (mesin/manusia), perlu-tinjauan, dan akun. Tiap baris: label lima dimensi, dasar (cue cocok, aturan), rantai induk nyata dengan stance induk, status/riwayat tinjauan, artefak terkait, dan tautan observasi. | FR-091, FR-050..056. |
| Tinjauan klasifikasi | `POST assessments/{id}/review/` membuat baris HUMAN yang menggantikan; hasil mesin tidak ditimpa; versi lama yang ditinjau lagi = 409 `already_reviewed`; riwayat lewat `history/`. | AT-16. |
| Graf | Satu payload (node, edge, atribut stance, metrik struktur, definisi, pengecualian) dengan filter jenis relasi, rentang waktu, atribut stance, dan `max_nodes` (bawaan 300; node dipertahankan menurut kekuatan tautan, `truncated` dan `total_nodes` dilaporkan). Edge diberi `kind: interaction`. | FR-092, AT-12; tanpa klaim skala. |
| Indikator | Endpoint terpisah; baris diberi `kind: behavioral_similarity`, memuat nilai, dukungan, penjelasan, baseline, indikator yang berbagi bukti, hipotesis alternatif, dan ID observasi bukti; catatan "indikator, bukan temuan" di setiap respons. | AT-12, FR-075/077. |
| Profil | Daftar menampilkan cakupan (pernyataan dan `partial_coverage`) lebih dulu; detail memuat tujuh dimensi dan cakupan lengkap. | FR-093, AT-17. |
| Temuan | Daftar, detail (isi, kualitas bukti, alternatif, sejarah, tinjauan, tautan), pembuatan (validasi layanan: plafon confidence, larangan vonis, alternatif), revisi (supersession), pengesahan, penarikan. Id run/indikator asing dalam body = 400 `invalid_finding` (tidak membocorkan keberadaan objek); campuran id sah dan asing ditolak, tidak diabaikan diam-diam. `evidence/` memberi saran sumbu bukti dari fakta sistem. | FR-077..080. |
| Jejak bukti | `observations/{id}/`: observasi, rantai induk, run, artefak (hasil verifikasi hash terakhir), klasifikasi yang berlaku, dan temuan yang merujuknya. | FR-005 (dasar WP-2.8). |
| Galat | `wrong_analysis_method` 409, `already_reviewed` 409, `confidence_above_ceiling` 400, `invalid_finding` 400, `invalid_review` 400, galat analisis lain 400 dengan nama kelasnya. | Pesan jelas untuk UI (FR-095). |
| Penjaga nama | Tes memeriksa semua payload: tidak ada kunci skor, peringkat, suspicious/mencurigakan, buzzer, vonis, atau probabilitas. | FR-079, rencana WP-2.7 butir 6. |
| Operator | `manage.py run_analyses` menjalankan M2, M3, M4, dan indikator (nilai CONTOH, wajib `--exploratory`, cue pro/kontra ditulis analis) untuk dev, demo, dan E2E; analisis belum dapat dipicu dari UI. | Tanpa data analisis, UI tak dapat didemonstrasikan; parameter tetap tersimpan eksplisit di run. |

## Temuan selama pengerjaan

- **Bug DRF**: `BooleanField` yang parameternya tidak dikirim (query/HTML) bernilai `False`, bukan "tidak ada". Akibatnya filter `needs_review=false` aktif tanpa diminta dan
  satu respons (yang perlu ditinjau) hilang dari daftar; hal sama pada `beyond_baseline` dan `include_unknown_time`. Diperbaiki dengan `allow_null=True` dan dijaga oleh tes
  khusus pada ketiga serializer.
- Mutasi menutup celah tes: filter karakter yang tak benar-benar menyaring, kategori koreksi manusia pada daftar, batas pemotongan graf, filter akun indikator hanya sebagai pihak A,
  dan id asing yang diabaikan bila bercampur dengan id sah.

## Batas yang diketahui

- Analisis belum dapat dipicu atau dikonfigurasi dari UI/API; hanya lewat layanan/`run_analyses`.
- Daftar respons membangun indeks percakapan seluruh dataset pada setiap permintaan (cukup untuk MVP; belum diukur untuk dataset besar). Graf dan indikator memuat seluruh baris ke memori sebelum difilter.
- Pembuatan temuan lewat API menerima struktur JSON besar (penilaian bukti dan alternatif); formulir UI-nya belum ada.
- Peninjau dan pembuat dapat orang yang sama; belum ada aturan dua-mata; `AuditEvent` umum menunggu WP-2.8.
- Jejak observasi baru menyediakan satu tingkat navigasi; halaman jejak lengkap (versi konteks, versi klasifikasi, status temuan) adalah WP-2.8.

## Pengujian

`tests/test_api_analysis.py` (28; dunia uji dibangun sekali per modul dalam satu transaksi): matriks otorisasi 17 entri x 5 peran, kelengkapan matriks terhadap rute, filter dan paginasi,
alur tinjauan dan temuan, AT-12 (edge interaksi vs kesamaan), jejak observasi, penjaga nama dan kategori, serta kuirk boolean DRF. `tests/test_run_analyses.py` (3). Mutasi
`wp27a_api.py`: 43/43 tertangkap (satu pola awal salah format diperbaiki; lima yang lolos pada putaran pertama ditutup dengan tes).
