"""Adapter platform I3 yang DINONAKTIFKAN sampai izin dan kelayakan diputuskan (WP-3.1 s.d. 3.5).

Setiap adapter di sini memberi dua hal yang sudah dapat dipakai tanpa akses ke platform:
1. `validate_target_url`: struktur URL spesifik platform (posting vs akun, ID stabil bila ada
   pada URL), murni dan tanpa jaringan.
2. `capabilities`: SETIAP kemampuan dinyatakan `UNTESTED` beserta alasan yang menunjuk dokumen
   kelayakan (`docs/adapters/`). Gerbang `Adapter.inspect` karenanya selalu menjawab
   `UNSUPPORTED` dengan alasan itu; `collect` tidak pernah dapat dijangkau dan sengaja gagal
   bila dipanggil langsung.

Tidak ada kode pengambilan data, tidak ada jalur melewati CAPTCHA/pembatasan akses (PRD bagian 7
dan 13). Mengaktifkan satu kemampuan membutuhkan keputusan organisasi, akses yang sah, fixture
rekaman yang sah, dan lulus suite kontrak (lihat docs/adapters/README.md); sampai itu terpenuhi
kelas ini tidak boleh dilonggarkan.
"""

import re
from typing import ClassVar
from urllib.parse import urlsplit

from collection.contracts import (
    Adapter,
    Capabilities,
    Capability,
    CapabilityDeclaration,
    CapabilityStatus,
    ContractViolation,
    InspectionRequest,
    InspectionResult,
    TargetUrlInfo,
)
from investigations.enums import TargetType
from investigations.errors import InvalidTargetURL
from investigations.target_urls import normalize_target_url


class TargetPattern:
    """Pola jalur(+query) untuk satu jenis target. Grup `id` (bila ada) = ID stabil dari URL."""

    def __init__(
        self,
        target_type: TargetType,
        regex: str,
        *,
        stable_id: bool = False,
        hosts: tuple[str, ...] | None = None,
    ) -> None:
        self.target_type = target_type
        self.hosts = hosts  # None = host utama platform; diisi = hanya host tautan pendek ini
        self.regex = re.compile(regex)
        self.stable_id = (
            stable_id  # True hanya bila grup `id` adalah ID yang sama dengan ID platform
        )


class PendingPermissionAdapter(Adapter):
    feasibility_doc: ClassVar[str]
    patterns: ClassVar[tuple[TargetPattern, ...]]
    reserved_accounts: ClassVar[frozenset[str]] = frozenset()
    # Host tautan pendek: jenis dan ID target tidak dapat diturunkan tanpa jaringan.
    short_hosts: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def disabled_reason(cls) -> str:
        return (
            f"pengambilan otomatis {cls.platform.value} dinonaktifkan: menunggu keputusan "
            f"organisasi dan akses yang sah ({cls.feasibility_doc})"
        )

    def capabilities(self) -> Capabilities:
        reason = self.disabled_reason()
        return Capabilities(
            platform=self.platform,
            declarations={
                cap: CapabilityDeclaration(CapabilityStatus.UNTESTED, reason) for cap in Capability
            },
        )

    def validate_target_url(self, url: str) -> TargetUrlInfo:
        normalized = normalize_target_url(self.platform, url)  # raise InvalidTargetURL
        parts = urlsplit(normalized)
        subject = parts.path + (f"?{parts.query}" if parts.query else "")
        host = parts.hostname or ""
        for pattern in self.patterns:
            if host in self.short_hosts:
                if pattern.hosts is None or host not in pattern.hosts:
                    continue
            elif pattern.hosts is not None:
                continue
            match = pattern.regex.fullmatch(subject)
            if match is None:
                continue
            if pattern.target_type is TargetType.ACCOUNT and (
                match.groupdict().get("name", "").lower() in self.reserved_accounts
            ):
                continue
            external_id = match.groupdict().get("id") if pattern.stable_id else None
            return TargetUrlInfo(self.platform, pattern.target_type, normalized, external_id)
        raise InvalidTargetURL(f"URL bukan posting atau akun {self.platform.value} yang dikenali.")

    def collect(self, request: InspectionRequest) -> InspectionResult:
        raise ContractViolation(
            f"adapter {self.platform.value} dinonaktifkan; "
            "gerbang kemampuan seharusnya menolak lebih dulu"
        )
