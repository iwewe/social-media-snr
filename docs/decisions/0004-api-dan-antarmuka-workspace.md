# 0004 - API untuk frontend dan antarmuka workspace awal

- **Status:** diterima (implementasi WP-0.5)
- **Tanggal:** 2026-10-16

## Konteks

Rencana WP-0.5 menetapkan frontend React + TypeScript yang berbicara dengan Django memakai sesi
(CSRF, cookie sesi). PRD tidak menetapkan pustaka API.

## Keputusan

| Topik | Keputusan | Catatan |
|---|---|---|
| Pustaka API | Django REST Framework | **Asumsi**: direkomendasikan di percakapan dan tidak ditolak; belum ada keputusan eksplisit. Dapat diganti. |
| Autentikasi | Sesi Django + CSRF (`X-CSRFToken`); tanpa token/JWT; tidak ada kredensial di `localStorage` | Diuji di E2E. |
| Anonim di API | 401 JSON, bukan redirect | View API dikecualikan dari `LoginRequiredMiddleware` dan dilindungi `IsAuthenticated` (bawaan). Tes enumerasi URL dibuat membedakan path `/api/`. |
| Endpoint publik | Hanya `/api/auth/csrf/` dan `/api/auth/login/` | Daftar putih eksplisit di tes. |
| Lockout login | `django-axes` juga untuk API; respons 429 JSON | `HttpRequest` asli harus diberikan ke `authenticate()`; objek `Request` DRF tidak terlihat oleh `AxesMiddleware`. |
| Galat | Galat domain menjadi 400/409 JSON berpesan Indonesia; 404 tidak membocorkan nama model | `DuplicateTarget` menjadi 409 dengan `existing_id`. |
| Same-origin | Dev: proxy Vite `/api` ke Django, `changeOrigin` mati | Cookie sesi/CSRF bekerja tanpa CORS. |
| Petunjuk | Satu berkas teks (`helpTexts.ts`) dan komponen `ContextHelp`; tes memeriksa isi kunci per PRD bagian 12 | Redaksi boleh dipoles tanpa mengubah makna. |
| Status inspeksi | `latest_inspection: null` = "Belum diperiksa" | InspectionRun belum ada (WP-1.2). |
| Routing/tes | `react-router-dom`, Vitest + Testing Library | |
| E2E | Playwright di container `worker-browser`, **database terpisah** (`snr_e2e`) dan container sementara, dibersihkan otomatis (`make e2e`) | Versi konteks append-only tidak bisa dihapus, jadi data uji tidak boleh masuk database dev. |

## Keterbatasan dan hal terbuka

- Cara melayani build frontend di produksi (di belakang proxy/HTTPS) belum diputuskan; ditunda ke WP-3.6.
- `make e2e` belum dijalankan di CI (butuh stack Docker penuh).
- Belum ada UI untuk merevisi definisi issue atau menonaktifkan proposition (endpoint pun belum ada).
- Popover petunjuk tidak menutup otomatis saat klik di luar; beberapa dapat terbuka bersamaan.
- Daftar investigasi belum berpaginasi; API belum diberi versi.
- Aksesibilitas (pembaca layar, kontras) belum diaudit, hanya nama aksesibel dan peran dasar.
- Semua pengguna terautentikasi melihat semua investigasi (lihat ADR 0003).
