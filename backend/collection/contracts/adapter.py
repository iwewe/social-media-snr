"""Antarmuka adapter per platform (PRD bagian 7.1; FR-022, FR-024, FR-026, FR-027).

Subkelas mengimplementasikan `capabilities`, `validate_target_url`, dan `collect`. `inspect` adalah
pintu masuk publik dan TIDAK boleh ditimpa: ia menegakkan gerbang kemampuan dan memeriksa hasil,
sehingga kemampuan yang belum teruji tidak pernah berjalan diam-diam dan hasil kosong tidak pernah
menyamar sebagai sukses.

Galat tak terduga (bug, bukan keterbatasan sumber) dibiarkan merambat ke orchestrator, yang
menandai run sebagai FAILED. Keterbatasan yang diharapkan dilaporkan lewat `InspectionResult`.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from investigations.enums import Platform

from .enums import Capability, CapabilityStatus, InspectionOutcome, LimitationCode
from .errors import ContractViolation
from .result import (
    CollectorInfo,
    Coverage,
    InspectionRequest,
    InspectionResult,
    Limitation,
)
from .target import TargetUrlInfo


@dataclass(frozen=True)
class CapabilityDeclaration:
    status: CapabilityStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status is not CapabilityStatus.SUPPORTED and not (self.reason or "").strip():
            raise ContractViolation(
                "Kemampuan yang tidak SUPPORTED wajib disertai alasan "
                "(batas akses, belum diuji, dst.)."
            )


@dataclass(frozen=True)
class Capabilities:
    """Pernyataan kemampuan adapter. Setiap anggota Capability wajib dinyatakan eksplisit:
    kemampuan yang terlewat tidak boleh dianggap didukung maupun tidak didukung."""

    platform: Platform
    declarations: Mapping[Capability, CapabilityDeclaration]

    def __post_init__(self) -> None:
        missing = set(Capability) - set(self.declarations)
        if missing:
            raise ContractViolation(
                f"Kemampuan belum dinyatakan: {sorted(c.value for c in missing)}."
            )
        object.__setattr__(self, "declarations", MappingProxyType(dict(self.declarations)))

    def status(self, capability: Capability) -> CapabilityStatus:
        return self.declarations[capability].status

    def runnable(self, capability: Capability) -> bool:
        return self.status(capability).runnable


class Adapter(ABC):
    platform: ClassVar[Platform]
    collector: ClassVar[CollectorInfo]

    @abstractmethod
    def capabilities(self) -> Capabilities:
        """Kemampuan saat ini. Murni dan tanpa jaringan."""

    @abstractmethod
    def validate_target_url(self, url: str) -> TargetUrlInfo:
        """Validasi struktur URL target untuk platform ini. Murni, tanpa jaringan.

        Raise InvalidTargetURL untuk URL platform lain atau yang tidak dikenali.
        """

    @abstractmethod
    def collect(self, request: InspectionRequest) -> InspectionResult:
        """Lakukan pengambilan data untuk kemampuan yang sudah lolos gerbang."""

    def inspect(self, request: InspectionRequest) -> InspectionResult:
        if request.platform != self.platform:
            raise ContractViolation(
                f"Adapter {self.platform.value} menerima permintaan untuk {request.platform.value}."
            )
        capabilities = self.capabilities()
        blocked = [c for c in request.requested if not capabilities.runnable(c)]
        if blocked:
            return self._unsupported(request, capabilities, blocked)

        result = self.collect(request)
        if (
            result.platform != self.platform
            or result.inspection_run_id != request.inspection_run_id
        ):
            raise ContractViolation("Hasil tidak cocok dengan platform atau run permintaan.")
        return result

    def _unsupported(
        self, request: InspectionRequest, capabilities: Capabilities, blocked: list[Capability]
    ) -> InspectionResult:
        limitations = tuple(
            Limitation(
                LimitationCode.UNSUPPORTED,
                f"{c.value}: {capabilities.declarations[c].status.value}"
                f" - {capabilities.declarations[c].reason or 'tanpa alasan'}",
                capability=c,
            )
            for c in blocked
        )
        return InspectionResult(
            platform=self.platform,
            inspection_run_id=request.inspection_run_id,
            outcome=InspectionOutcome.UNSUPPORTED,
            collector=self.collector,
            coverage=Coverage(scope=request.requested, pagination_complete=None),
            limitations=limitations,
        )
