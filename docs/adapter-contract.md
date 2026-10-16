# Kontrak adapter (WP-1.1)

Panduan singkat untuk menulis adapter. Alasan keputusan ada di
[ADR 0006](decisions/0006-kontrak-observasi-dan-adapter.md); sumber kode di
`backend/collection/contracts/`.

## Menulis adapter

```python
from collection.contracts import Adapter, Capabilities, InspectionRequest, InspectionResult, TargetUrlInfo

class MyAdapter(Adapter):
    platform = Platform.X
    collector = CollectorInfo("nama-collector", "versi")

    def capabilities(self) -> Capabilities: ...                # murni, tanpa jaringan
    def validate_target_url(self, url: str) -> TargetUrlInfo: ...  # murni; raise InvalidTargetURL
    def collect(self, request: InspectionRequest) -> InspectionResult: ...
```

- Implementasikan `collect`, **jangan** menimpa `inspect`: `inspect` menegakkan gerbang kemampuan.
- Nyatakan **setiap** `Capability` secara eksplisit. Yang belum teruji: `UNTESTED` beserta alasannya.
- Laporkan keterbatasan lewat `InspectionResult`, bukan dengan hasil kosong:

| Situasi | `outcome` | Syarat |
|---|---|---|
| Semua yang diminta terbaca, paginasi lengkap | `COMPLETED` | `pagination_complete=True`, tanpa keterbatasan yang menghalangi |
| Sebagian terbaca | `PARTIAL` | minimal satu keterbatasan; observasi bertanda `PARTIAL` |
| Login/akses ditolak | `ACCESS_RESTRICTED` | tanpa observasi; limitation `ACCESS_RESTRICTED`/`AUTH_REQUIRED` |
| Parser gagal | `FAILED` | tanpa observasi; limitation `PARSE_FAILED` |
| Kemampuan tidak aktif | `UNSUPPORTED` | otomatis dari `inspect` |
| Post memang tanpa balasan | `COMPLETED` | `platform_displayed_count=0`, tetap sertakan objek targetnya |

- Waktu publikasi tidak diketahui: `published_at=None`. **Jangan** memakai waktu pengambilan.
- ID stabil tidak tersedia: `external_*_id=None` dan `identity_needs_verification=True`.
- Galat yang tidak terduga (bug) biarkan merambat; orchestrator menandai run `FAILED`.
- Jangan melewati CAPTCHA atau pembatasan akses (PRD bagian 7 dan 13).

## Mendaftarkan adapter ke suite kontrak

Tambahkan `ContractHarness` di `tests/contracts/harnesses.py` (fixture rekaman, tanpa jaringan), lalu
masukkan ke `HARNESSES`. Suite yang sama dijalankan terhadap semua adapter (`pytest tests/contracts`).
Skenario wajib: `complete`, `partial`, `access_restricted`, `parse_failure`; opsional: `empty_post`,
`identity_missing`.
