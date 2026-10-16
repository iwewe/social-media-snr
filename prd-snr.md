# SNR - Product Requirements Document (PRD) v0.1

**Status:** Baseline produk dan metodologi disepakati; dokumen ini adalah spesifikasi serah-terima untuk implementasi dan validasi.  
**Tanggal penyusunan:** 16 Oktober 2026  
**Produk:** SNR (nama kerja; kepanjangan/nama formal belum perlu dikunci)  
**Bahasa dokumen:** Indonesia  
**Tim pelaksana:** Satu tim developer terpadu. Dokumen ini tidak membagi peran, jabatan, atau tanggung jawab individu.  
**Rujukan keputusan:** Kesepakatan Technology Architecture v0.5 dan Methodology M1-M5 dalam diskusi perancangan SNR.  
**Batas dokumen:** PRD implementasi, bukan keputusan final mengenai legalitas akses platform, pemilihan model ML tertentu, desain laporan, atau hasil riset empiris.

---

## 0. Cara membaca dokumen ini

Agar tidak terjadi penambahan asumsi atau fitur tanpa persetujuan:

- **Disepakati**: keputusan yang sudah menjadi baseline dan wajib dijaga oleh implementasi.
- **Kebutuhan produk**: perilaku aplikasi yang harus diwujudkan untuk memenuhi baseline tersebut.
- **Perlu validasi**: kelayakan yang belum dibuktikan (misalnya akses data di platform atau mutu klasifikasi pada data nyata).
- **Ditunda / tidak termasuk**: bukan pekerjaan dalam MVP atau memang secara eksplisit dikecualikan.
- **Usulan implementasi**: detail teknis yang membantu developer memulai, tetapi tidak boleh diperlakukan sebagai keputusan produk baru bila belum diuji atau disepakati.

Istilah "buzzer" dalam latar produk merujuk pada objek kajian pengguna. **SNR tidak mengeluarkan vonis otomatis bahwa suatu akun adalah buzzer, bot, akun bayaran, atau operator kampanye.** Temuan yang diperbolehkan berupa respons, pola perilaku, relasi jaringan, indikator koordinasi, dan kesimpulan yang ditinjau serta dibatasi oleh bukti.

## 1. Ringkasan eksekutif

SNR adalah aplikasi investigasi media sosial **berbasis target**. Pengguna memilih posting atau akun tertentu, menentukan isu dan proposisi, lalu memerintahkan sistem melakukan pemeriksaan **on-demand**, bukan pemantauan seluruh media sosial secara kontinu atau real-time. Hasil pemeriksaan disimpan dalam database dan dipreservasi di server lokal. Target yang sama dapat diperiksa kembali (misalnya selang jam, hari, atau minggu) tanpa menghasilkan duplikasi identitas posting/komentar. Observasi baru dihubungkan dengan catatan terdahulu.

Fokus analisis adalah **respons tekstual, hubungan percakapan, aktivitas akun yang relevan, pola waktu, dan jaringan pada satu platform**. Respons pro, kontra, campuran, netral, tidak dapat ditentukan, maupun tidak relevan dinilai relatif terhadap **proposisi isu yang ditetapkan analis**, bukan hanya terhadap sentiment positif/negatif. Analisis mengikuti metodologi M1-M5. Post/video/gambar target dipreservasi sesuai akses yang sah; **isi gambar dan video tidak dianalisis secara semantik**.

Platform yang direncanakan: **X, Threads, TikTok, Instagram, dan Facebook**. Masing-masing memakai adapter pengambilan data tersendiri. Identitas akun, graf, actor profiling, dan analisis koordinasi **terisolasi per platform**; akun bernama sama di dua platform tidak dianggap individu yang sama. Hasil lintas platform tidak digabungkan menjadi satu jaringan atau temuan koordinasi.

Aplikasi menggunakan **Django Authentication**, **PostgreSQL**, **Playwright** untuk lapisan inspeksi browser yang diizinkan, penyimpanan artefak pada **filesystem lokal**, pemrosesan latar dengan **Celery + Valkey**, analisis graf **NetworkX**, dan frontend **React + TypeScript / Cytoscape.js** sebagai baseline teknologi. Pilihan tersebut masih perlu dibuktikan melalui prototipe. **Keycloak tidak digunakan**.

Desain/format laporan akhir **ditunda** hingga tersedia data nyata. Meskipun begitu, keluaran internal, penelusuran bukti, dan kemampuan melihat hasil analisis harus ada supaya aplikasi dapat divalidasi.

## 2. Permasalahan yang hendak diselesaikan

Pengguna mengamati adanya respons terhadap sebuah isu, baik dukungan, kritik, perlawanan narasi, serangan personal, maupun dugaan aktivitas bersama beberapa akun. Pemeriksaan manual per posting sulit mempertahankan riwayat komentar dan perubahan dari waktu ke waktu; daftar akun saja tidak menjelaskan relasi serta pola aktivitasnya.

SNR dibutuhkan untuk:

1. Menjadikan URL posting/akun sebagai awal investigasi yang terkendali.
2. Menyimpan hasil pemeriksaan browser beserta provenance dan bukti preservasi.
3. Memeriksa ulang target yang sama tanpa membuat objek yang sama berulang-ulang.
4. Mengelompokkan respons terhadap isu secara kontekstual, tidak hanya berdasarkan kata positif/negatif.
5. Menjelaskan aktivitas akun pada isu tertentu berdasarkan data yang benar-benar teramati.
6. Menyajikan SNA dan indikator pola koordinasi dengan pemisahan tegas antara interaksi teramati dan kemiripan terhitung.
7. Menyediakan jejak yang memungkinkan hasil pemeriksaan dan analisis diulang dan diverifikasi.

## 3. Tujuan, batas, dan prinsip utama

### 3.1 Tujuan produk (disepakati)

- Mendukung dua pintu masuk investigasi: **target posting** dan **target akun/daftar akun**.
- Mendukung pengumpulan **on-demand** dan pemeriksaan ulang target yang sudah terdaftar.
- Menyediakan alur **observation -> preservation -> reconciliation -> analysis -> review**.
- Mendukung analisis terhadap target pada X, Threads, TikTok, Instagram, dan Facebook melalui modul yang dibedakan.
- Menyatukan skema data inti, tetapi **tidak menyatukan analisis antaraplatform**.
- Membuat hasil analisis dapat ditelusuri ke observasi, metadata, versi konteks, versi analisis, dan bukti.
- Menyediakan **petunjuk penggunaan dalam aplikasi** pada langkah-langkah penting.

### 3.2 Bukan tujuan MVP / secara eksplisit dikecualikan

- Monitoring real-time terus-menerus dan pengumpulan seluruh isi platform secara massal.
- API-first sebagai syarat wajib. API dapat menjadi sumber tambahan yang diizinkan, tetapi bukan lapisan awal wajib.
- Penggabungan identitas akun, profil, graf, atau analisis koordinasi **lintas platform**.
- OCR, speech-to-text, transkripsi, computer vision, face recognition, dan penafsiran semantik gambar/video.
- Mengukur opini masyarakat umum dari sampel reply yang tidak representatif.
- Memberi skor atau vonis otomatis "buzzer", "bot", "dibayar", "operator", atau "afiliasi".
- Menentukan kebenaran faktual klaim sosial/politik hanya dari klasifikasi komentar.
- Profil psikologis, informasi pribadi tersembunyi, atau identifikasi pemilik akun anonim.
- Perancangan tampilan atau format laporan final sebelum data nyata tersedia.
- Keycloak, Neo4j, Kafka, Kubernetes, dan desain microservices sebagai kebutuhan awal.
- Pembagian pekerjaan menjadi jabatan atau peran-peran terpisah di dalam tim developer.

### 3.3 Prinsip pelaksanaan

- **Target-first:** pengumpulan dimulai dari sasaran yang ditentukan, bukan pencarian tanpa batas.
- **Analyst-guided:** isu, proposisi, dan konteks target ditetapkan oleh analis.
- **Source-separated:** tiap platform memiliki adapter, kemampuan, batasan, dan datasetnya sendiri.
- **Observe first, interpret later:** data sumber dan label/kesimpulan tidak dicampur.
- **Append-only evidence:** pemeriksaan baru tidak menimpa preservasi yang sudah ada.
- **Scoped account profiling:** pemeriksaan akun dilakukan terbatas pada isu, periode, dan sumber yang diizinkan.
- **Uncertainty by design:** data kosong atau tidak terlihat tidak otomatis berarti objek tidak ada; kesimpulan boleh "belum cukup bukti".

## 4. Pengguna dan alur produk

SNR digunakan oleh pengguna investigasi yang mengoperasikan satu workspace untuk membuat isu, mendaftarkan target, menjalankan inspeksi, meninjau klasifikasi, menjelajahi jaringan, serta memeriksa bukti. Untuk MVP, pengelolaan akses memakai akun Django biasa; **tidak diperlukan uraian peran tim secara rinci**.

### 4.1 Alur utama A: inspeksi satu posting

1. Pengguna login.
2. Pengguna membuat investigation, issue, dan satu atau lebih proposisi.
3. Pengguna memasukkan URL posting target pada platform tertentu.
4. Pengguna menambahkan **Target Context Note** dan posisi awal target terhadap proposisi bila dapat ditentukan.
5. Pengguna memulai inspection job sesuai akses/sumber yang diizinkan.
6. Sistem mengambil observasi yang tersedia, menyimpan objek terstruktur, membuat artefak preservasi, dan mencatat cakupan serta kendala.
7. Pengguna melihat daftar reply/komentar, waktu publikasi, relasi parent, akun sumber, dan tautan bukti.
8. Sistem menjalankan klasifikasi M2 (dapat ditinjau pengguna), ringkasan aktivitas akun M3, dan pembentukan graf M4.
9. Pengguna meninjau interpretasi serta indikasi; hasil tidak menjadi vonis otomatis.

### 4.2 Alur utama B: reinspection

1. Pengguna membuka target yang telah tersimpan.
2. Pengguna memilih **Inspect Again** sesuai kebutuhan (jam/hari/minggu kemudian, secara manual pada MVP).
3. Sistem membuat **InspectionRun** baru yang merujuk target lama.
4. Hasil dibandingkan dengan observasi sebelumnya menggunakan identitas objek sumber.
5. Objek lama dipertahankan; objek baru dicatat; perubahan dan keterbatasan pengamatan ditandai.
6. Artefak pemeriksaan baru disimpan sebagai preservasi tersendiri.
7. Hasil analisis dapat dijalankan ulang terhadap versi dataset terbaru tanpa menghapus hasil lama.

### 4.3 Alur utama C: pemeriksaan akun terpilih

1. Pengguna menemukan suatu akun dari hasil respons target.
2. Pengguna memilih **Inspect Actor** dan menetapkan isu/proposisi serta periode yang relevan.
3. Sistem memeriksa aktivitas publik relevan yang dapat diakses secara sah pada **platform yang sama**.
4. Observasi tambahan disimpan dan dihubungkan ke akun serta investigation terkait.
5. Sistem memperbarui **Actor-Issue Activity Profile** berdasarkan cakupan data yang dicatat.
6. Profil tidak dianggap gambaran menyeluruh tentang pemilik akun ataupun status buzzer.

### 4.4 Alur utama D: target berupa gambar/video

1. Pengguna mendaftarkan posting/video/Reel sebagai target dan menjelaskan konteks isu melalui catatan analis.
2. Sistem mempreservasi URL, metadata, caption/teks yang tersedia, screenshot, dan media asli **hanya bila dapat diperoleh dan disimpan secara sah**.
3. Sistem menganalisis komentar dan interaksi tekstual yang tersedia.
4. Sistem **tidak** membaca isi gambar/video, membuat transkrip, atau menyimpulkan stance dari isi media.
5. Bila sebuah reply bergantung pada isi media yang tidak ditafsirkan, sistem memungkinkan label `UNDETERMINED`.

## 5. Istilah dan aturan identitas

| Istilah | Definisi operasional |
|---|---|
| Investigation | Wadah aktivitas pemeriksaan dan analisis atas satu ruang masalah. |
| Issue | Topik yang diteliti, misalnya kebakaran hutan dan tanggung jawab korporasi. |
| Proposition | Klaim spesifik yang menjadi acuan klasifikasi pro/kontra. Satu issue dapat memiliki lebih dari satu proposition. |
| Target | URL posting atau akun yang sengaja dipilih pengguna untuk diperiksa. |
| Seed post | Posting yang menjadi titik masuk jaringan percakapan. |
| ActorAccount | Identitas satu akun **pada satu platform**. Tidak disamakan dengan orang tertentu. |
| Post | Objek publikasi pada platform, termasuk video/post/Reel sesuai jenis asli. |
| Response | Reply atau comment terkait suatu target/post; dipertahankan jenis asli dan parent-nya. |
| InspectionRun | Satu pelaksanaan pemeriksaan pada target yang sudah didaftarkan. |
| Observation | Kondisi objek yang berhasil diamati pada pemeriksaan tertentu. |
| EvidenceArtifact | Berkas preservasi dan metadata integritas/provenance-nya. |
| AnalysisRun | Pemrosesan terhadap versi dataset, versi konteks, dan parameter tertentu. |
| Finding | Hasil analisis yang telah ditinjau; berbeda dari observasi dan klasifikasi mesin. |

**Aturan identitas:** objek posting unik pada pasangan `(platform, external_post_id)`; akun unik pada `(platform, external_actor_id)`. Username, nama tampilan, dan URL yang bisa berubah **bukan identitas utama**. Untuk sumber yang tidak menyediakan ID stabil, sistem tidak boleh menciptakan kesan kepastian deduplikasi: tandai kebutuhan verifikasi identitas objek sebelum penggabungan.

## 6. Kebutuhan fungsional rinci

Prioritas: **P0** = wajib untuk alur MVP end-to-end; **P1** = bagian baseline yang masuk setelah fondasi terbukti; **Deferred** = disepakati ditunda. Prioritas merupakan **urutan implementasi dalam PRD**, bukan penambahan cakupan baru.

### 6.1 Workspace, autentikasi, dan petunjuk penggunaan

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-001 | P0 | Login/logout menggunakan Django Authentication, bukan Keycloak. |
| FR-002 | P0 | Pengguna dapat membuat, melihat, dan membuka Investigation. |
| FR-003 | P0 | Investigation menyimpan issue, proposition, target, dan riwayat inspeksi. |
| FR-004 | P0 | Aplikasi menyediakan petunjuk kontekstual untuk pengisian issue, proposition, Target Context Note, menjalankan inspeksi, reinspection, dan memahami label ketidakpastian. |
| FR-005 | P1 | Pengguna dapat menelusuri relasi dari klasifikasi/graf menuju observasi dan bukti yang mendasari. |
| FR-006 | P0 | Data aplikasi tidak dapat diakses tanpa autentikasi; izin dasar memanfaatkan Django Groups/Permissions tanpa merinci pembagian jabatan tim. |

### 6.2 Issue, proposition, dan catatan konteks

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-010 | P0 | Pengguna dapat membuat issue dan satu atau beberapa proposition. |
| FR-011 | P0 | Pengguna dapat menambahkan URL target serta memilih platform yang sesuai. |
| FR-012 | P0 | Pengguna dapat memberi catatan interpretasi target (`Target Context Note`) dalam teks bebas. |
| FR-013 | P0 | Target dapat diberi stance awal terhadap proposition: `PRO`, `CONTRA`, `MIXED`, atau `UNDETERMINED`. |
| FR-014 | P0 | Catatan dan definisi konteks mempunyai versi; revisi tidak menimpa versi yang telah digunakan oleh AnalysisRun lama. |
| FR-015 | P1 | Satu target dapat dihubungkan dengan lebih dari satu proposition dan dinilai berbeda untuk masing-masing. |
| FR-016 | P0 | Catatan target merupakan panduan interpretasi, bukan instruksi agar mesin memaksakan label pada semua reply. |

### 6.3 Inspection Orchestrator dan adapter per platform

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-020 | P0 | Pengguna dapat memulai inspection job untuk target terdaftar secara on-demand. |
| FR-021 | P0 | Setiap InspectionRun mencatat target, waktu, sumber/adapter, cakupan diminta, status, kegagalan, dan keterbatasan. |
| FR-022 | P0 | Sumber inspeksi dan analisis terpisah: browser/adapter menghasilkan observasi, bukan keputusan analitis. |
| FR-023 | P0 | Ada kontrak observasi terstandar yang dapat dipakai oleh seluruh adapter. |
| FR-024 | P0 | Adapter memiliki identitas/platform tersendiri dan tidak mengakses atau menyatukan akun platform lain. |
| FR-025 | P0 | Browser worker hanya menjalankan pengambilan yang diizinkan; autentikasi browser tidak dianggap sebagai izin scraping. |
| FR-026 | P0 | Kegagalan, halaman parsial, keterbatasan akses, atau kemampuan yang tidak didukung dilaporkan eksplisit, bukan dianggap 'tidak ada komentar'. |
| FR-027 | P1 | Adapter menyediakan kemampuan inspeksi posting, respons, dan akun **sejauh akses per platform memungkinkan**. |
| FR-028 | P1 | Pengguna dapat memberikan daftar target akun/posting tanpa mengharuskan inspeksi massal atau streaming kontinu. |
| FR-029 | P0 | Data dapat dimasukkan melalui dataset uji/impor yang sah untuk mengembangkan sistem tanpa tergantung izin platform. |

### 6.4 Penyimpanan, preservasi, dan reinspection

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-030 | P0 | Post dan ActorAccount disimpan menggunakan identitas internal stabil dan kunci unik per platform. |
| FR-031 | P0 | InspectionRun yang berbeda dapat merujuk Post/ActorAccount yang sama. |
| FR-032 | P0 | Observasi baru tidak menggandakan identitas Post/Response yang sama. |
| FR-033 | P0 | Sistem menyimpan kapan konten diterbitkan (bila tersedia) terpisah dari kapan diamati/ditangkap. |
| FR-034 | P0 | Pemeriksaan ulang membuat riwayat observasi baru tanpa menghapus observasi lama. |
| FR-035 | P0 | Rekonsiliasi membedakan minimal objek baru, tak berubah, berubah, dan tidak terlihat pada pemeriksaan tertentu. |
| FR-036 | P0 | Ketiadaan objek dari satu inspeksi tidak otomatis dianggap terhapus oleh penulis atau platform. |
| FR-037 | P0 | Setiap artefak yang benar-benar disimpan mempunyai manifest, timestamp/provenance, dan hash SHA-256. |
| FR-038 | P0 | Artefak preservasi disimpan pada filesystem server lokal; PostgreSQL memuat relasi, metadata, serta path/identitas berkas. |
| FR-039 | P0 | File bukti tidak ditimpa oleh pemeriksaan berikutnya. |
| FR-040 | P1 | Pengguna dapat memverifikasi hash artefak dan membuka rujukan bukti sesuai hak akses. |
| FR-041 | P1 | Analisis ulang terhadap observasi tersimpan tidak memerlukan browser mengambil ulang data yang sama. |
| FR-042 | P0 | Screenshot, media, maupun raw capture hanya disimpan sejauh tersedia dan diperbolehkan; keterbatasan preservasi dicatat. |

### 6.5 Klasifikasi respons (M1-M2)

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-050 | P1 | Reply/comment dinilai dengan referensi kepada proposition, Target Context Note, dan parent conversation yang relevan. |
| FR-051 | P1 | Stance respons memakai label `PRO`, `CONTRA`, `MIXED`, `NEUTRAL`, `UNDETERMINED`, `NOT_RELEVANT`. |
| FR-052 | P1 | Target alignment (mendukung/menentang posting yang dibalas), stance isu, sentimen ekspresi, dan karakter respons disimpan sebagai dimensi berbeda. |
| FR-053 | P1 | Response character dapat multi-label. |
| FR-054 | P1 | Hasil klasifikasi mencantumkan versi konteks, versi metode/model, referensi observasi, dan dasar/alasan yang dapat diperiksa. |
| FR-055 | P1 | Pengguna dapat meninjau atau mengoreksi label; koreksi memiliki jejak perubahan. |
| FR-056 | P1 | Teks ambigu, sarkastis, atau bergantung pada media yang tidak dianalisis boleh berstatus `UNDETERMINED`. |
| FR-057 | P1 | Sistem tidak menyimpulkan benar/salahnya isi klaim dari hasil stance. |

### 6.6 Profil aktivitas akun (M3)

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-060 | P1 | Profil dasar akun dibentuk dari respons akun pada target investigasi yang teramati. |
| FR-061 | P1 | Pengguna dapat meminta perluasan inspeksi akun pada isu, periode, dan platform yang sama, dengan akses yang sah. |
| FR-062 | P1 | Profil merangkum jumlah aktivitas unik, distribusi stance, karakter respons, waktu, konsentrasi target, pola narasi tekstual, dan perubahan sepanjang waktu **jika datanya cukup**. |
| FR-063 | P1 | Setiap profil menjelaskan target, periode, jenis sumber, dan cakupan data; tidak diklaim sebagai seluruh riwayat akun. |
| FR-064 | P1 | Perbandingan antar-akun memperlihatkan keterbatasan jika cakupan pemeriksaannya tidak sebanding. |
| FR-065 | P1 | Profil akun tidak menjadi label kepribadian, identitas individu, atau klasifikasi buzzer permanen. |

### 6.7 SNA, indikasi koordinasi, dan evaluasi bukti (M4-M5)

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-070 | P1 | SNR menyediakan Interaction Network berdasarkan relasi yang benar-benar teramati. |
| FR-071 | P1 | SNR menyediakan Stance Network View yang menggunakan stance sebagai atribut, bukan dasar pembentukan relasi otomatis. |
| FR-072 | P1 | SNR dapat membangun Behavioral Coordination Network dari indikator terhitung yang dibedakan jelas dari interaksi langsung. |
| FR-073 | P1 | Semua node, edge, community detection, centrality, dan pengujian pola dilakukan **pada satu platform** per analysis run. |
| FR-074 | P1 | Hasil graf menyimpan definisi node/edge, versi dataset, aturan pembobotan, jendela waktu, dan parameter metode. |
| FR-075 | P1 | Indikator koordinasi dilaporkan terpisah; kesamaan stance atau intensitas respons saja tidak otomatis membentuk dugaan koordinasi. |
| FR-076 | P1 | Sistem mendukung analisis pola co-response, sinkronisasi waktu, kesamaan teks, co-amplification, kesamaan tautan/narasi tekstual, dan pengulangan lintas target sejauh data tersedia. |
| FR-077 | P1 | Hasil indikasi harus memungkinkan pemeriksaan baseline, alternatif penjelasan, dan peninjauan manusia sebelum menjadi Finding. |
| FR-078 | P1 | Confidence dan kualitas bukti disertai alasan, serta opsi `NOT_ASSESSABLE` / bukti tidak cukup. |
| FR-079 | P1 | Sistem tidak memberikan Buzzer Score atau vonis otomatis mengenai operasi berbayar/aktor pengendali. |
| FR-080 | P1 | Setiap Finding tertaut ke observasi dan versi AnalysisRun, dan dapat digantikan oleh temuan baru tanpa menghilangkan sejarah. |
| FR-081 | P1 | SNA dan atribut analisis satu platform tidak digabung dengan data platform lain meskipun issue/proposition bernama sama. |

### 6.8 Penyajian di dalam aplikasi

| ID | Prioritas | Kebutuhan |
|---|---|---|
| FR-090 | P0 | Workspace menunjukkan target terdaftar, status inspeksi, dan riwayat pemeriksaannya. |
| FR-091 | P1 | Pengguna dapat melihat daftar respons berikut classification/review dan tautan observasi/bukti. |
| FR-092 | P1 | Pengguna dapat melihat graf interaktif dan memfilter jenis relasi, cakupan waktu, serta atribut stance. |
| FR-093 | P1 | Pengguna dapat membuka profil aktivitas akun terbatas pada isu dan platform terkait. |
| FR-094 | P1 | Antarmuka membedakan fakta observasi, hasil mesin, dan temuan yang telah ditinjau. |
| FR-095 | P0 | Aplikasi memberi pesan yang mudah dipahami untuk akses ditolak, pengambilan parsial, data tidak lengkap, kegagalan parser, atau konteks yang belum cukup. |
| FR-096 | Deferred | Desain visual laporan, template laporan eksternal, dan format publikasi final; dibahas setelah tersedia data nyata. |

## 7. Aturan khusus kelima platform

| Platform | Objek target | Data respons yang relevan | Batas desain |
|---|---|---|---|
| X | Post, termasuk lampiran media | Reply, quote, repost, mention yang tersedia | Hubungan berdasar kemampuan dan akses X yang benar-benar teruji. |
| Threads | Post/thread dan media | Reply, quote, rangkaian percakapan | Tidak diasumsikan identik dengan model X. |
| TikTok | Video/post dan caption | Comment dan reply/comment bertingkat | Video dipreservasi, tidak ditranskrip atau diinterpretasi. |
| Instagram | Post, carousel, Reel | Comment dan reply yang tersedia | Gambar/Reel dipreservasi, tidak ditafsirkan. |
| Facebook | Post dan konteks Page/ruang publik yang sah | Comment, reply, relasi yang tersedia | Jenis ruang asal dan pembatasan akses dicatat. |

**Status konektor:** daftar ini menyatakan **cakupan desain**, bukan klaim bahwa browser/API saat ini dapat mengambil semua jenis data atau seluruh percakapan di lima platform. Setiap adapter harus melewati feasibility test dan verifikasi izin secara tersendiri. Tidak boleh membuat mekanisme untuk melewati CAPTCHA, pembatasan akses, atau larangan platform.

### 7.1 Kontrak adapter (rancangan logis, bukan API final)

Setiap adapter minimal dapat **menyatakan kemampuan**, memvalidasi jenis URL target, memproses permintaan inspeksi yang diizinkan, mengembalikan observasi ternormalisasi dan metadata cakupan, serta melaporkan kegagalan dengan jelas. Metode pengambilan boleh berbeda per platform: pemeriksaan browser berbantuan, data impor yang sah, dan API resmi opsional. Integrasi API bukan syarat awal.

Data minimal yang diharapkan untuk suatu observasi **jika tersedia**:

```json
{
  "platform": "x",
  "source_object_type": "reply",
  "external_post_id": "sample-reply-id",
  "external_actor_id": "sample-actor-id",
  "parent_post_id": "sample-parent-id",
  "published_at": "2026-10-16T01:30:00Z",
  "observed_at": "2026-10-16T01:32:00Z",
  "text": "Contoh isi respons",
  "inspection_run_id": "sample-run-id",
  "collection_status": "PARTIAL",
  "source_method": "authorized_observation"
}
```

Nilai di atas seluruhnya **contoh sintetis**, bukan format respons resmi platform tertentu.

## 8. Model data domain: entitas dan relasi

Bagian ini menjelaskan kebutuhan logis, **bukan** skema SQL final. Penamaan tabel dapat disesuaikan tanpa mengubah makna.

| Entitas | Tanggung jawab dan hubungan |
|---|---|
| `Investigation` | Wadah investigasi dan daftar target/analisis. |
| `Issue` | Definisi topik investigasi. |
| `Proposition` | Klaim spesifik yang dianalisis; terhubung ke Issue. |
| `IssueContextVersion` | Versi definisi dan arahan konteks analisis. |
| `CollectionTarget` | Sasaran URL post atau akun; satu target dapat memiliki banyak InspectionRun. |
| `TargetContextVersion` | Catatan interpretasi target, posisi awal, dan versioning. |
| `InspectionRun` | Eksekusi satu pemeriksaan; cakupan, waktu, status, sumber, error. |
| `ActorAccount` | Akun dengan identitas unik pada satu platform. |
| `Post` | Identitas tetap posting/komentar/media pada satu platform. |
| `PostRelation` | Relasi reply, quote, repost, mention, atau tipe sumber lain; sumber relasinya dicatat. |
| `PostObservation` | Kondisi Post pada suatu InspectionRun; timestamp dan metadata. |
| `EvidenceArtifact` | Artefak lokal, path/ID berkas, tipe, hash, manifest, provenance. |
| `DatasetVersion` | Rujukan himpunan observasi yang menjadi input analisis. |
| `AnalysisRun` | Versi konteks, parameter, metode/model, waktu, sumber dataset. |
| `ResponseAssessment` | Label M2, alasan, status review, referensi posting dan proposition. |
| `ActorIssueProfile` | Ringkasan M3 spesifik akun, issue/proposition, periode, cakupan dan AnalysisRun. |
| `GraphProjection` | Definisi dan hasil jaringan pada satu platform serta AnalysisRun. |
| `IndicatorResult` | Nilai dan penjelasan indikator perilaku/koordinasi terhitung. |
| `Finding` | Interpretasi yang telah ditinjau, tingkat confidence, bukti, dan status historisnya. |
| `AuditEvent` | Rekaman perubahan konteks, klasifikasi, dan temuan yang relevan. |

**Relasi identitas yang harus dijaga:**

1. `CollectionTarget -> InspectionRun` adalah one-to-many; pemeriksaan ulang menambah run, bukan target baru.
2. `Post -> PostObservation` adalah one-to-many; konten lama tidak ditimpa tanpa jejak.
3. `Post` dapat muncul dalam beberapa Investigation melalui keterkaitan dataset/target, bukan diduplikasi sebagai identitas objek baru.
4. `ActorAccount` hanya berlaku pada satu platform. Cross-platform identity matching **tidak ada**.
5. `ResponseAssessment` selalu merujuk proposition dan versi konteks tertentu.
6. `AnalysisRun` selalu merujuk sumber dataset dan parameter analisis.
7. `GraphProjection` memiliki **tepat satu platform scope** pada satu run.
8. `Finding` mempunyai referensi bukti, status peninjauan, dan sejarah supersession/revisi.

## 9. Inspection lifecycle dan rekonsiliasi

### 9.1 Status minimum yang diperlukan

- `PENDING`: job sudah terdaftar, belum diproses.
- `RUNNING`: inspeksi sedang berjalan.
- `COMPLETED`: pekerjaan sesuai cakupan yang ditetapkan selesai; **bukan** klaim semua konten platform berhasil ditemukan.
- `PARTIAL`: hanya sebagian ruang lingkup berhasil diamati.
- `FAILED`: tidak menghasilkan penyelesaian yang sah.
- `ACCESS_RESTRICTED` / `UNSUPPORTED`: kemampuan/akses tidak tersedia; boleh menjadi alasan status kegagalan/parsial, bukan diam-diam dianggap data kosong.
- `REVIEW_REQUIRED`: hasil perlu dilihat manusia bila terdapat ambiguitas atau masalah kualitas.

State transition rinci adalah detail implementasi yang harus diuji; jangan memalsukan status sukses saat masih ada error yang belum ditangani.

### 9.2 Rekonsiliasi dua pemeriksaan

Untuk objek yang muncul dalam run baru, cocokkan berdasarkan ID stabil sumber bila ada:

- **NEW:** identitas sumber belum tercatat.
- **UNCHANGED:** identitas ditemukan dan tidak ada perubahan relevan yang teramati.
- **MODIFIED:** identitas sama, ada atribut yang terlihat berubah; simpan observasi baru.
- **NOT_OBSERVED:** sebelumnya pernah terlihat tetapi tidak muncul dalam run baru; bukan bukti penghapusan.
- **CONFIRMED_UNAVAILABLE:** hanya digunakan apabila ada bukti memadai terkait ketidaktersediaan, bukan sekadar absen pada daftar parsial.

**Aturan wajib:** jika run kedua menemukan 20 reply yang telah dicatat dan 5 reply baru, jumlah identitas reply setelah rekonsiliasi bertambah **5**, bukan 25. Meski jumlah reply berubah, observasi lama dan bukti masing-masing run tetap tersedia.

### 9.3 Waktu dan hitungan

- Simpan `published_at` terpisah dari `observed_at` dan `captured_at` bila sumber mendukung.
- Bedakan **jumlah komentar yang ditampilkan platform** dengan **jumlah komentar unik teramati dalam dataset**.
- Jika waktu publikasi tidak tersedia, tandai tidak diketahui; jangan menjadikan waktu pengambilan otomatis sebagai waktu publikasi.
- Ketidaklengkapan pagination/urutan/percakapan harus tercatat di metadata cakupan.

## 10. Preservasi lokal dan integritas

Penyimpanan berkas dilakukan di **filesystem server lokal**. PostgreSQL memuat indeks objek, metadata, relasi, dan pointer berkas. Tidak diperlukan layanan object storage cloud.

Contoh struktur logis (bukan path mutlak yang harus diikuti):

```text
/srv/snr/
  data/postgres/
  evidence/captures/
  evidence/screenshots/
  evidence/manifests/
  exports/
  browser-profiles/
  backups/
```

**Wajib:**

- Capture mempunyai `inspection_run_id`, target dan URL sumber, timestamp, cara perolehan, status/cakupan, versi collector, serta daftar artefak yang benar-benar tersedia.
- Setiap artefak tersimpan memiliki hash SHA-256 dan catatan manifest yang bisa diverifikasi.
- Pemeriksaan baru tidak menimpa berkas lama.
- Tidak menyimpan file yang tidak tersedia/izin simpan tidak ada; tandai keterbatasannya.
- Screenshot dan DOM/teks yang relevan disimpan hanya bila diperbolehkan; jangan memasukkan cookies atau kredensial ke arsip bukti.
- Browser profile/sesi disimpan terpisah dari evidence dan tidak diekspor sebagai artefak investigasi.
- Akses file bukti dibatasi melalui autentikasi dan hak akses aplikasi/server.
- Backup lokal yang terpisah dari penyimpanan utama dan verifikasi restore diperlakukan sebagai kebutuhan operasional; rincian perangkat/kapasitas belum ditentukan.

**Pernyataan integritas yang boleh dibuat:** hash memeriksa apakah berkas yang tersimpan masih sama dengan saat di-hash; hash **tidak membuktikan** konten platform autentik, lengkap, atau benar secara faktual.

## 11. Metodologi terintegrasi dalam aplikasi

### 11.1 M1 - Issue Framing & Target Context

1. Issue adalah topik; tidak diberi label pro/kontra secara langsung.
2. Pro/kontra dinilai terhadap **proposition** yang spesifik.
3. Satu issue dapat memiliki lebih dari satu proposition.
4. Target Context Note adalah interpretasi versi tertentu oleh analis, termasuk bila target adalah video/gambar.
5. Definisi konteks dibekukan per AnalysisRun; revisi konteks membuat versi baru.

### 11.2 M2 - Response & Stance Intelligence

Dimensi terpisah:

- `issue_stance`: `PRO`, `CONTRA`, `MIXED`, `NEUTRAL`, `UNDETERMINED`, `NOT_RELEVANT`.
- `target_alignment`: mendukung/menentang/tidak jelas terhadap **posting yang langsung dibalas**, bukan otomatis seed awal.
- `expression_sentiment`: nada emosional jika dapat dinilai; tidak menggantikan stance.
- `response_character`: multi-label.
- `narrative_function`: fungsi respons terhadap pembahasan isu (deskriptif, bukan pembuktian manipulasi).

Taksonomi awal karakter respons M2:

| Kode | Label |
|---|---|
| RC-01 | Support / Affirmation |
| RC-02 | Substantive Criticism |
| RC-03 | Counterargument |
| RC-04 | Information Request |
| RC-05 | Personal Attack |
| RC-06 | Ridicule / Mockery |
| RC-07 | Intimidation / Threat (perlu tinjauan manusia) |
| RC-08 | Topic Diversion |
| RC-09 | Promotional / Spam |
| RC-10 | Other / Unclear |

Fungsi naratif awal yang telah dibahas: reinforcement, evidence contestation, counter-framing, source delegitimization, topic redirection, dan discussion suppression. Kategori ini masih **taksonomi kerja** yang harus dievaluasi pada data nyata.

**Aturan konteks:** komentar "setuju" terhadap reply tingkat kedua tidak otomatis mendukung seed; perlu membaca parent yang sesungguhnya. "Marah" pada kebakaran hutan tidak otomatis kontra pada tuntutan audit. M1-M2 tidak melakukan fact-check atas kebenaran klaim.

### 11.3 M3 - Actor Behavior Analysis

Unit analisis = **akun pada suatu platform**, bukan individu.

Tujuh dimensi yang telah disepakati:

1. Participation.
2. Stance distribution.
3. Response character.
4. Temporal activity.
5. Target concentration.
6. Narrative consistency dalam teks yang tersedia.
7. Activity evolution.

Profil Level A hanya menggunakan respons yang terobservasi dalam target investigasi. Profil Level B merupakan **inspeksi tambahan opsional** terhadap aktivitas publik terkait isu, periode, dan platform yang sama. Seluruh profil menyertakan coverage statement. Tidak boleh menyimpulkan pandangan permanen pemilik akun atau menyebut status buzzer.

### 11.4 M4 - Social Network & Coordination Analysis

Tiga representasi analisis:

- **Interaction Network:** relasi reply, quote, repost, mention yang benar-benar diobservasi.
- **Stance Network View:** atribut posisi isu diterapkan pada graf; stance sama **tidak menciptakan edge otomatis**.
- **Behavioral Coordination Network:** hubungan terhitung dari kemiripan atau pengulangan perilaku, dipisahkan jelas dari interaksi langsung.

Indikator awal:

| Kode | Indikator |
|---|---|
| CO-01 | Co-Response |
| CO-02 | Temporal Synchronization |
| CO-03 | Content Similarity (teks) |
| CO-04 | Co-Amplification |
| CO-05 | Shared Narrative / URL (berbasis teks/tautan yang tersedia) |
| CO-06 | Repeated Participation lintas target dalam platform yang sama |

Parameter, jendela waktu, bobot, dan baseline merupakan bagian dari AnalysisRun; **belum ada angka ambang baku yang disepakati**. Kesamaan waktu atau teks saja tidak membuktikan koordinasi. Community detection dan centrality menggambarkan struktur jaringan, bukan menentukan pengendali.

**Platform isolation wajib:** analisis dibuat dan dibandingkan dalam ruang satu platform. Tidak ada pencocokan identitas, edge, community, atau inferensi koordinasi lintas platform. Definisi isu boleh sama sebagai kerangka, tetapi dataset dan temuannya tetap terpisah.

### 11.5 M5 - Evidence Evaluation & Analytical Confidence

Tingkat hasil:

1. Observed Evidence.
2. Analytical Classification.
3. Behavioral & Network Pattern.
4. Reviewed Analytical Finding.

Kualitas bukti dievaluasi melalui `integrity`, `provenance`, `completeness`, dan `relevance` secara terpisah. Analytical confidence menggunakan `HIGH`, `MODERATE`, `LOW`, atau `NOT_ASSESSABLE` **dengan alasan**. Confidence bukan probabilitas bahwa akun adalah buzzer.

Hipotesis alternatif yang harus dipertimbangkan sebelum menyebut indikasi koordinasi: mobilisasi organik, efek berita/peristiwa eksternal, penyalinan konten publik tanpa pengaturan bersama, serta bias sampling/observasi. Indikator dari event yang sama tidak otomatis dianggap bukti independen.

Temuan dapat memiliki status historis `SUPERSEDED` ketika dataset atau analisis yang lebih baru menggantikannya. Hasil lama tetap dapat ditinjau.

## 12. Petunjuk penggunaan dalam aplikasi

Petunjuk bukan dokumen manual eksternal saja; harus tersedia ketika pengguna membutuhkan konteks.

| Lokasi aplikasi | Petunjuk minimum |
|---|---|
| Membuat Issue | Bedakan topik isu dari proposition yang dapat diuji. |
| Mengisi Target Note | Jelaskan interpretasi target; jangan menulis perintah agar semua kritik diberi label buzzer. |
| Memulai inspeksi | Jelaskan cakupan, batas akses, dan kemungkinan hasil parsial. |
| Reinspection | Jelaskan bahwa objek lama tidak digandakan dan perubahan ditinjau berdasarkan data baru. |
| Melihat respons | Jelaskan stance isu vs alignment terhadap posting yang dibalas. |
| Melihat Actor Profile | Jelaskan profil hanya berlaku bagi sampel, platform, isu, dan periode yang diperiksa. |
| Melihat Network | Bedakan edge interaksi nyata dan kesamaan perilaku terhitung. |
| Melihat temuan | Jelaskan evidence, uncertainty, confidence, dan belum cukup bukti. |

Redaksi akhir teks bantuan boleh dipoles tim developer tanpa mengubah makna metodologi yang disepakati.

## 13. Pengamanan dan batas akses

- Aplikasi menggunakan autentikasi Django dan izin dasar; tidak menggunakan Keycloak.
- Tindak lanjut berupa pembatasan percobaan login, TLS/HTTPS, pengendalian akses file lokal, dan pemisahan sesi browser dari bukti.
- Cookies/session merupakan kredensial rahasia; tidak dimasukkan ke Git, log, output AI, atau evidence package.
- Login browser **bukan** persetujuan untuk mengumpulkan konten secara otomatis. Tiap platform memerlukan verifikasi jalur perolehan yang sah; jika akses tidak tersedia, adapter melaporkan keterbatasan dan tidak mem-bypass kontrol.
- Tidak mengotomasi identifikasi pemilik anonim, pengumpulan data privat, atau penargetan orang berdasarkan pendapat.
- Profil dan temuan individual diberi akses terbatas, dengan pencatatan perubahan dan peninjauan manusia.
- Kebijakan retensi/penghapusan mengikuti dasar penggunaan dan izin data; durasi angka final **belum ditentukan** dalam diskusi.
- Artefak lokal, database, dan backup perlu prosedur pemulihan; kebutuhan kapasitas diputuskan berdasarkan pengukuran pilot.

## 14. Kebutuhan nonfungsional

| ID | Kebutuhan | Cara memverifikasi |
|---|---|---|
| NFR-01 | **Reproducibility** | AnalysisRun lama dapat dihubungkan ke dataset, konteks, dan parameter asalnya. |
| NFR-02 | **Integrity** | Hash setiap artefak uji sesuai dengan berkas tersimpan. |
| NFR-03 | **Idempotent ingestion** | Pengambilan ulang ID objek yang sama tidak menambah Post/ActorAccount duplikat. |
| NFR-04 | **Partial-failure safety** | Job gagal/parsial tidak merusak observasi yang telah tervalidasi. |
| NFR-05 | **Data provenance** | Setiap observasi memiliki sumber dan pemeriksaan asal. |
| NFR-06 | **Isolation** | Node, edge, dan profil di satu platform tidak tergabung dengan platform lain. |
| NFR-07 | **Local-first preservation** | Artefak tersimpan dan dapat diverifikasi pada filesystem lokal. |
| NFR-08 | **Usable uncertainty** | UI dapat membedakan tidak ada data, belum diperiksa, dan gagal mengakses data. |
| NFR-09 | **No forced conclusions** | Klasifikasi/temuan mendukung status tidak dapat dinilai dan peninjauan manusia. |
| NFR-10 | **Recoverability** | Backup dapat dipulihkan dalam uji restore yang direncanakan. |

Tidak ada target SLA, jumlah worker, lama job maksimum, RAM minimum, maupun angka performa produksi yang pernah disepakati. Angka-angka tersebut **harus diukur**, bukan direka dalam PRD.

## 15. Milestone implementasi

Urutan disepakati sebagai pendekatan bertahap, **bukan komitmen tanggal**. Prefix `I` dipakai untuk milestone implementasi agar tidak tertukar dengan metodologi `M1-M5`.

### I0 - Repository Bootstrap

- Struktur repo backend, frontend, adapter, worker, test, deployment.
- Django Authentication dan PostgreSQL.
- Docker Compose untuk lingkungan MVP.
- Halaman workspace awal dan kemampuan membuat investigation, issue, proposition, target, Target Context Note.
- Jalur filesystem lokal untuk preservasi dan pemisahan sesi browser.

**Exit criteria:** aplikasi dasar dapat dijalankan; pengguna bisa login, membuat investigasi, mengisi target dan konteks, serta melihat catatan tersimpan.

### I1 - Inspection, Preservation & Reinspection

- Kontrak observasi dan adapter test/dataset uji.
- Browser-assisted proof of concept pada halaman uji yang dikendalikan sendiri.
- InspectionRun, Post/ActorAccount, PostObservation, EvidenceArtifact.
- Screenshot/snapshot yang diizinkan, manifest, SHA-256.
- Rekonsiliasi satu target melalui beberapa pemeriksaan tanpa duplikasi.

**Exit criteria:** data respons dapat bertambah antarrun tanpa menggandakan identitas lama; bukti setiap run dapat diverifikasi dan ditelusuri.

### I2 - Contextual Analysis & Network

- Implementasi baseline M1-M5 menggunakan dataset uji.
- Klasifikasi M2; versi konteks dan review.
- Profil aktivitas M3 yang berbatas cakupan.
- Interaction/Stance/Coordination Network yang terpisah.
- Traceability hasil ke data dan bukti.

**Exit criteria:** dataset sintetis menghasilkan label dan graf yang dapat diperiksa; tidak muncul penggabungan platform atau vonis otomatis buzzer.

### I3 - Platform Adapters

- Implementasi adapter X, Threads, TikTok, Instagram, Facebook **secara bertahap dan independen**.
- Uji kemampuan/izin setiap adapter sebelum mengaktifkan fitur yang terkait.
- Sumber alternatif berupa dataset impor yang sah dan API opsional apabila tersedia.

**Exit criteria:** hanya kemampuan platform yang telah diuji dan diizinkan dinyatakan aktif; kegagalan ditandai jelas dan tidak mengubah core data model.

### I4 - Pilot Investigation

- Uji investigasi terbatas menggunakan data nyata yang diperoleh secara sah.
- Evaluasi kualitas pengambilan, klasifikasi, graf, preservasi, dan petunjuk penggunaan.
- Temukan kelemahan nyata tanpa mengubah baseline secara spekulatif.
- Bahas desain laporan **setelah** hasil pilot memperlihatkan bentuk data dan temuan yang tersedia.

**Exit criteria:** ada catatan hasil validasi dan daftar perbaikan prioritas yang didasarkan pada pengujian nyata.

## 16. Rencana validasi dan acceptance tests

### 16.1 Dataset sintetis

Rancangan awal yang telah dibahas: **3 target posting, 50 akun sintetis, sekitar 300 reply/comment, dan 4 putaran inspeksi**, dengan skenario:

1. Percakapan pro/kontra organik.
2. Serangan personal yang tidak disusun sebagai koordinasi.
3. Pola aktivitas bersama yang sengaja disimulasikan.
4. Penambahan, perubahan, dan ketidakmunculan objek pada pemeriksaan berbeda.

Ukuran dataset ini adalah **target latihan awal**, bukan klaim cukup secara statistik atau representatif terhadap platform nyata.

### 16.2 Kasus uji penerimaan

| Test ID | Kondisi uji | Hasil yang diharapkan |
|---|---|---|
| AT-01 | URL target yang sama diinspeksi beberapa kali | Tetap satu CollectionTarget; InspectionRun bertambah. |
| AT-02 | Komentar lama muncul ulang | Tidak ada duplikasi Post/Response. |
| AT-03 | Terdapat komentar baru | Hanya ID sumber baru yang menjadi objek Post baru. |
| AT-04 | Komentar tidak terlihat pada inspeksi parsial | Ditandai NOT_OBSERVED, bukan otomatis DELETED. |
| AT-05 | Konten berubah pada ID yang sama | Observasi baru dibuat dan sejarah lama tetap tersedia. |
| AT-06 | Artefak screenshot/manifest tersimpan | Verifikasi SHA-256 berhasil. |
| AT-07 | Catatan konteks diedit | Versi konteks baru; analysis run lama tidak tertimpa. |
| AT-08 | Reply "setuju" pada reply tingkat kedua | Parent yang benar dipertimbangkan sebelum stance ditetapkan. |
| AT-09 | Komentar ambigu/mengacu pada isi video | UNDETERMINED dimungkinkan; tidak ada interpretasi semantik video. |
| AT-10 | Kritik yang sah vs serangan personal | Klasifikasi karakter terpisah dari stance. |
| AT-11 | Banyak akun memiliki stance sama | Tidak otomatis terbentuk edge koordinasi. |
| AT-12 | Edge berdasarkan interaksi vs kesamaan terhitung | Jenis edge/asalnya dapat dibedakan dan diperiksa. |
| AT-13 | Username sama pada X dan TikTok | Akun, graf, dan profil tidak digabung. |
| AT-14 | Adapter kehilangan akses / parser gagal | Status jelas dan tidak dianggap nol respons. |
| AT-15 | Temuan baru setelah reinspection | Data/AnalysisRun lama masih dapat diakses; temuan dapat SUPERSEDED. |
| AT-16 | Pengguna meninjau klasifikasi | Perubahan dan rujukan bukti tercatat. |
| AT-17 | Actor profile hanya dari sebagian target | Cakupan dan keterbatasan tertulis, bukan klaim total aktivitas. |
| AT-18 | Menjalankan tanpa platform eksternal | Uji end-to-end pada halaman simulasi atau impor dataset sah tetap berjalan. |

### 16.3 Evaluasi model klasifikasi

Pilot anotasi yang pernah diusulkan: sekitar **50-100 respons** dengan kategori beragam, dinilai secara independen oleh dua penilai bila memungkinkan; ukur kesepakatan label, precision/recall/F1 per kelas, serta analisis error pada sarkasme, parent bertingkat, dan bahasa informal Indonesia. Angka tersebut adalah **pilot**, bukan hasil uji atau kualitas model yang sudah terbukti. Model/penyedia NLP spesifik **belum diputuskan**.

## 17. Struktur repository awal (usulan implementasi)

```text
snr/
  backend/
    accounts/
    investigations/
    collection/
      orchestrator/
      contracts/
      adapters/
        x/
        threads/
        tiktok/
        instagram/
        facebook/
      reconciliation/
    preservation/
    intelligence/
      narrative/
      stance/
      actors/
      network/
    reporting/             # placeholder; desain laporan ditunda
  workers/
    browser/
    analysis/
  frontend/
  tests/
    fixtures/
    contracts/
    integration/
  deployment/
  docs/
  compose.yaml
```

Folder tidak mengharuskan container/service terpisah per platform. Modular monolith + worker terpisah tetap pendekatan awal.

## 18. Risiko, dependensi, dan pembatas yang harus diverifikasi

| Area | Fakta yang telah disepakati | Belum diketahui / perlu dibuktikan |
|---|---|---|
| Akses X/Threads/TikTok/Instagram/Facebook | Browser-assisted, on-demand, adapter spesifik | Jalur pengambilan yang diizinkan, cakupan komentar publik, login, pagination, serta ketahanan parser pada tiap platform. |
| Browser profiles | Sesi login dapat digunakan bila sah dan aman | Cara pengelolaan sesi operasional tiap platform; tidak diasumsikan cookies selalu berlaku. |
| Video/gambar | Preservasi pasif saja | Apakah file media asli dapat disimpan; jika tidak, batas screenshot/metadata. |
| NLP | Analisis teks dan konteks; dukung bahasa Indonesia informal | Model, evaluasi, kebutuhan CPU/RAM, serta ambang confidence yang layak. |
| SNA | NetworkX sebagai baseline | Skala praktis, stabilitas community detection, kualitas baseline koordinasi. |
| Penyimpanan | Local filesystem + PostgreSQL | Kapasitas, skema backup, retensi, prosedur restore, hak akses fisik/server. |
| Operasional | On-demand, reinspection manual | Otomatisasi jadwal jam/hari/minggu adalah opsi setelah MVP dan hanya pada sumber yang mengizinkan. |
| Laporan | Ditunda | Bentuk keluaran final diputuskan setelah ada data nyata. |

**Tidak boleh menyatakan sebuah platform mendukung pengambilan lengkap atau suatu metrik akurat sebelum pengujian nyata.** Jika sebuah kemampuan tidak tersedia, produk harus menampilkan status keterbatasan sumber alih-alih mengarang hasil.

## 19. Daftar keputusan yang harus dipertahankan (baseline lock)

1. Target-based; on-demand; tidak continuous monitoring.
2. Browser inspection sebagai pintu awal, dengan jalur data berizin; API tidak wajib.
3. Per platform adapter terpisah; analisis dan identitas **tidak cross-platform**.
4. Satu posting/akun adalah identitas stabil, dengan banyak observation dan inspection run.
5. Database dan preservasi lokal merupakan dua fungsi berbeda.
6. Multimedia hanya dipreservasi; tidak ditafsirkan secara semantik.
7. Catatan konteks analis dan proposition memandu klasifikasi respons.
8. Stance, alignment, sentiment, response character, narrative function, dan indikator koordinasi adalah dimensi berbeda.
9. Actor profile terikat isu, proposisi, periode, dataset, dan platform.
10. Graf interaksi dan graf kemiripan perilaku dipisahkan.
11. Tidak ada Buzzer Score/vonis koordinasi otomatis.
12. Temuan dan confidence harus terhubung ke evidence dan versioning.
13. Django Authentication, PostgreSQL, filesystem lokal, Playwright, Celery/Valkey, NetworkX, React/Cytoscape.js sebagai baseline ringan; tanpa Keycloak.
14. Petunjuk penggunaan tersedia dalam aplikasi.
15. Desain laporan final ditunda sampai ada hasil data nyata.
16. Satu tim developer terpadu; peran internal tidak dirinci dalam PRD ini.

## 20. Definisi selesai untuk rilis awal

**SNR MVP dinyatakan terbukti secara fungsional** hanya jika tim developer dapat memperagakan rangkaian berikut dengan dataset uji yang dikendalikan:

1. Login dan pembuatan investigation, issue, proposition, serta target dan catatan konteks.
2. Pemeriksaan target melalui adapter uji/browser yang diizinkan, menghasilkan observasi dan preservasi lokal yang hash-nya valid.
3. Pemeriksaan ulang target yang sama, dengan komentar baru tersimpan tanpa duplikasi dan dengan riwayat lama tetap tersedia.
4. Pembuatan penilaian stance/karakter respons yang dapat direview, serta penelusuran ke parent dan bukti.
5. Pembuatan Actor-Issue Profile dengan batas cakupan.
6. Pembuatan graf relasi dan indikator pola yang dibedakan dari observasi langsung.
7. Pemeriksaan kasus ambigu, akses gagal, data parsial, dan isolasi identitas lintas platform.
8. Tidak ada vonis otomatis buzzer ataupun analisis semantik isi video/gambar.

Kelulusan MVP fungsional **tidak sama** dengan kelulusan semua konektor platform atau validasi ilmiah pada data nyata. Keduanya adalah tahap lanjutan yang harus dilaporkan sesuai hasil pengujian.

---

## Lampiran A. Contoh kasus uji kontekstual (sintetis)

- **Issue:** kebakaran hutan dan pertanggungjawaban korporasi.
- **P1:** perusahaan yang diduga terkait kebakaran hutan perlu diaudit.
- **Target:** posting yang menyatakan secara eksplisit "Perusahaan tidak perlu diaudit"; interpretasi target `CONTRA P1`.
- **Reply 1:** "Justru audit harus dilakukan." -> `PRO P1`, menentang target.
- **Reply 2** (kepada Reply 1): "Setuju sekali!" -> kemungkinan `PRO P1` bila parent diketahui dengan cukup jelas; bukan dukungan kepada target awal.
- **Reply 3:** "Penulis ini bodoh." -> serangan personal, tetapi stance terhadap P1 `UNDETERMINED`.
- **Reply 4:** "Apa bukti keterlibatannya?" -> permintaan bukti, stance belum tentu kontra audit.
- **Reply 5:** "Saya marah melihat kebakaran ini." -> sentimen negatif terhadap kebakaran; stance terhadap P1 belum dapat ditentukan.

**Catatan:** semua contoh adalah buatan untuk menguji aturan, bukan observasi nyata, bukti koordinasi, atau klaim tentang pihak tertentu.

## Lampiran B. Catatan perubahan dokumen

| Versi | Ringkasan |
|---|---|
| v0.1 | Penyatuan baseline teknologi v0.5 dan metodologi M1-M5 menjadi PRD implementasi; mengunci isolasi per platform; petunjuk aplikasi wajib; desain laporan ditunda. |
