# 0011 - Penyaring rahasia untuk artefak preservasi

- **Status:** diterima (implementasi WP-1.5b). Pendekatan heuristik; false negative dan false positive diketahui.
- **Tanggal:** 2026-10-17

## Konteks

PRD bagian 10 dan 13: cookies/sesi/token adalah kredensial rahasia dan tidak boleh masuk arsip bukti,
Git, log, maupun keluaran AI; sesi browser terpisah dari bukti. WP-1.5a menyediakan penyimpanan artefak
dengan kebijakan wajib; PR ini menyediakan kebijakan produksinya.

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Menolak, bukan menyunting | Artefak yang menyerupai/memuat kredensial **tidak disimpan**; dicatat di manifest sebagai identitas aturan dan posisi byte | Menyunting mengubah bukti. Nilai maupun cuplikan tidak pernah dicatat (disimpan, dilog, atau dilaporkan). |
| Gagal tertutup | Pemindaian tidak selesai (`scan-error`) atau kebijakan melempar galat (`policy-error`) = artefak ditolak | Yang tidak dapat dipastikan aman dianggap tidak aman. Pesan galat tidak diteruskan (dapat memuat isi). |
| Aturan nama | `cookies*`, `storage_state*`, `*.har`, kunci/sertifikat (`*.pem`, `*.key`, `*.p12`, `id_rsa`, ...), `.env*`, nama dasar `passwords`/`secrets`/`credentials` (opsional satu ekstensi), `*.secret/credentials/token.<cfg>`, basis data profil browser (`Login Data`, `key4.db`, `logins.json`, ...) | Nama dinormalisasi NFKC. Diperketat setelah menemukan false positive (`password-reset.html`). `cookie-banner.png` (tangkapan spanduk) tetap sah. |
| Tipe konten | HAR, PEM, PKCS#12, SQLite ditolak untuk semua jenis | Wadah kredensial/profil. |
| Aturan isi | Blok kunci privat; header `Authorization`; header `Cookie`/`Set-Cookie` berisi nilai; JWT; cookie sesi dikenal; kredensial di URL; parameter token (`access_token`, ...); penugasan rahasia (`client_secret`, `password`, ...); token penyedia (AWS, GitHub, Slack, Google, Stripe) | Setiap aturan punya contoh positif dan korpus negatif di tes (spanduk cookie, "authorization required", `input type=password`, meta `csrf-token`, URL berparameter biasa, dll.). |
| Yang dipindai | Teks: `text/*`, JSON/XML/JS/YAML dst., dan jenis `dom_snapshot`/`raw_response` kecuali bertipe gambar/video/audio/font; `note` artefak juga | Gambar/media tidak dipindai sebagai teks (batas diketahui). |
| Aliran | Pemindaian per potongan dengan jendela tumpang-tindih 4 KiB; UTF-16 ber-BOM didekode inkremental | Kredensial yang terbelah di batas potongan terdeteksi; berkas besar tidak dimuat seluruhnya. |
| Kebijakan bawaan | `make_artifact_sink()` tanpa argumen memakai `SecretFilterPolicy`; `persist_run_artifacts` tetap mewajibkan kebijakan eksplisit; `UncheckedPolicy` hanya dapat dirujuk dari modul kebijakan (uji arsitektur) | Jalur yang aman adalah jalur bawaan. |
| Ekspor | `ensure_exportable` juga menolak nama berkas menyerupai rahasia | Pertahanan berlapis bila ada berkas yang ditaruh manual di akar evidence. |
| Nilai uji | Rahasia palsu di tes disusun saat runtime dari potongan kecil | Agar repositori tidak memuat pola kredensial utuh (pemindai rahasia GitHub dan hook `detect-private-key`). |

## Temuan saat pengerjaan

- **ReDoS nyata:** pola `cookie-header` memakai `\\s*` setelah jangkar yang cocok di setiap baris baru;
  100.000 baris kosong memakan **232 detik** (kuadratik). Penyaring yang melindungi dapat dilumpuhkan oleh
  berkas jahat. Diperbaiki dengan spasi horizontal saja (`[ \\t]*`); kini kasus itu < 1 detik, dan 15
  bentuk payload jahat diuji dengan batas waktu. Python `re` tidak punya batas waktu eksekusi, jadi
  keamanan bergantung pada rancangan pola; setiap pola baru harus diuji dengan payload jahat.
- Satu mutasi (pengecualian media dicabut) awalnya lolos karena sampel tes saya tidak membedakannya;
  kini ada tes untuk `raw_response`/`dom_snapshot` bertipe gambar.

## Keterbatasan dan hal terbuka

- **False negative (pasti ada):** kredensial dalam piksel/metadata gambar, audio, video; terkompresi
  (gzip), di-Base64, di-URL-encode, UTF-32, atau diobfuskasi (dipecah antar-tag/entitas HTML); token tanpa
  awalan atau kata kunci yang dikenal; token pendek. CSRF token pada formulir tidak ditandai.
- **False positive (mungkin):** konten sah yang memuat string menyerupai kredensial (mis. kiriman yang
  mengutip JWT atau kunci bocor, dokumentasi berisi `Authorization: Bearer ...`). Artefaknya ditolak dan
  dicatat; **belum ada jalur tinjauan manual/karantina atau allowlist**, sehingga bukti sah dapat hilang.
  Angka false positive pada halaman nyata belum diukur: tugas pilot (I4).
- Ambang dan daftar aturan tetap (tanpa konfigurasi). Penyetelan menunggu data nyata.
- Kinerja: sekitar 9 MB teks biasa dipindai dalam sekitar 3 detik pada VM dev (kurang lebih 3 MB/detik,
  10 aturan regex per jendela). Pada batas 512 MiB per artefak itu berarti menit, bukan detik.
  Optimasi (mis. pra-saring kata kunci, atau RE2) belum dilakukan.
- Konten artefak berbentuk `bytes` yang sangat besar dipindai sebagai satu jendela (memori = ukuran isi).
- BOM UTF-16 yang terbelah di antara dua potongan pertama tidak dikenali.
- Penyaring ini tidak menggantikan pemisahan sesi browser dari bukti (WP-0.6) maupun kehati-hatian
  adapter: adapter sebaiknya tidak menangkap header/cookies sejak awal.
