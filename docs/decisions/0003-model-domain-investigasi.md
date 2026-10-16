# 0003 - Model domain investigasi dan versi konteks

- **Status:** diterima (implementasi WP-0.4; poin bertanda *terbuka* menunggu keputusan)
- **Tanggal:** 2026-10-16

## Konteks

PRD bagian 8 dan 11.1 (M1) serta FR-002/003/010-016 menetapkan Investigation, Issue, Proposition,
CollectionTarget, dan versi konteks yang tidak menimpa versi lama (FR-014, AT-07).

## Keputusan

| Topik | Keputusan | Alasan |
|---|---|---|
| Penghapusan | Semua FK `PROTECT`; tidak ada UI hapus | Riwayat tidak boleh hilang beruntun. Kebijakan retensi belum ditentukan (PRD bagian 13). |
| Append-only | Tabel versi (konteks issue, konteks target, stance target) dijaga **trigger PostgreSQL**, bukan hanya kode | `queryset.update()`/`delete()` dan SQL langsung ikut ditolak. Diuji. |
| Proposition | Isi tidak dapat diubah (trigger). Koreksi = proposition baru, yang lama `retired_at` (sekali) | Penilaian respons akan merujuk proposition tertentu (relasi 5, PRD bagian 8); isinya harus stabil. |
| Nomor proposition | `P1`, `P2`, ... per issue, diberi di bawah kunci baris | Sesuai Lampiran A PRD. |
| Issue | Tidak punya field stance | M1: pro/kontra hanya terhadap proposition. |
| Stance awal target | Tabel terpisah per (versi konteks, proposition); hanya `PRO/CONTRA/MIXED/UNDETERMINED` (DB check) | FR-013 dan FR-015 (struktur sudah mendukung banyak proposition). `NEUTRAL`/`NOT_RELEVANT` adalah label respons M2. |
| Versi | Nomor versi dari `max+1` di bawah `select_for_update`; unique `(induk, version)` sebagai pengaman | Mencegah versi ganda saat revisi bersamaan. |
| Revisi tanpa stance | Stance versi sebelumnya dibawa; `{}` eksplisit = tanpa stance | Revisi catatan tidak diam-diam menghapus posisi awal. |
| URL target | Dinormalisasi (skema, host, `www`/`m`, alias `twitter.com→x.com`, `threads.net→threads.com`, parameter pelacakan, slash, fragmen); domain wajib cocok dengan platform; kredensial/port non-standar ditolak | Mencegah target ganda (AT-01) dan salah pilih platform. URL asli tetap disimpan. |
| Admin Django | Hanya baca | Pembuatan lewat `services` agar versi dan validasi selalu berjalan. |

## Keterbatasan dan hal terbuka

- **Terbuka:** semua pengguna terautentikasi melihat semua investigasi (PRD: satu workspace, FR-006).
  Belum ada izin per investigasi; perlu keputusan bila dibutuhkan.
- Normalisasi URL **bukan** identitas objek. Identitas Post/ActorAccount berasal dari ID stabil sumber
  (PRD bagian 5). Dua URL berbeda yang menunjuk objek sama (mis. huruf besar/kecil pada username,
  tautan pendek `vt.tiktok.com`) masih bisa menjadi dua target; aturan per platform ada di adapter (I3).
- Trigger tidak memblokir `TRUNCATE`, dan pemilik database/superuser masih dapat menghapus trigger.
  Ini penjagaan terhadap kesalahan dan perubahan tak sengaja, bukan terhadap administrator DB.
- `AuditEvent` (siapa mengubah apa) baru ada pada WP-2.8; sampai saat itu hanya `created_by`/`created_at`.
- Belum ada UI; tampilan dan formulir ada pada WP-0.5.
