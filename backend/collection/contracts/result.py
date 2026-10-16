"""Permintaan dan hasil inspeksi (PRD bagian 7.1, 9.1; FR-021, FR-026).

Invarian utama yang ditegakkan saat objek dibangun (bukan oleh konvensi):
- COMPLETED hanya bila pagination dinyatakan lengkap dan tidak ada keterbatasan yang menghalangi.
- PARTIAL wajib menjelaskan sebabnya.
- FAILED/ACCESS_RESTRICTED/UNSUPPORTED tidak membawa observasi dan wajib punya keterbatasan yang
  sesuai: kegagalan tidak pernah menyamar sebagai "tidak ada komentar" (FR-026, AT-14).
- Hasil kosong yang COMPLETED hanya sah bila platform sendiri menyatakan nol (jumlah tampil = 0).
- Observasi tidak boleh dari platform atau run lain (FR-024, NFR-06).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from investigations.enums import Platform, TargetType

from .enums import (
    ArtifactKind,
    Capability,
    CollectionStatus,
    InspectionOutcome,
    LimitationCode,
)
from .errors import ContractViolation
from .observation import Observation


def _tuple[T](items: Iterable[T]) -> tuple[T, ...]:
    return tuple(items)


@dataclass(frozen=True)
class CollectorInfo:
    """Identitas collector; dicatat di manifest preservasi (PRD bagian 10)."""

    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ContractViolation("CollectorInfo.name dan version wajib diisi.")


@dataclass(frozen=True)
class InspectionRequest:
    inspection_run_id: str
    platform: Platform
    target_url: str
    target_type: TargetType
    requested: tuple[Capability, ...]
    target_external_id: str | None = None
    max_items: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested", _tuple(self.requested))
        if not self.inspection_run_id.strip():
            raise ContractViolation("inspection_run_id wajib diisi.")
        if not self.requested:
            raise ContractViolation("Permintaan inspeksi harus meminta setidaknya satu kemampuan.")
        if len(set(self.requested)) != len(self.requested):
            raise ContractViolation("Kemampuan yang diminta tidak boleh ganda.")
        if self.max_items is not None and self.max_items <= 0:
            raise ContractViolation("max_items harus positif atau None.")


@dataclass(frozen=True)
class Limitation:
    code: LimitationCode
    message: str
    capability: Capability | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, LimitationCode):
            raise ContractViolation("Limitation.code harus LimitationCode.")
        if not self.message.strip():
            raise ContractViolation("Limitation.message wajib diisi (alasan harus dapat dibaca).")


@dataclass(frozen=True)
class Coverage:
    """Metadata cakupan (PRD bagian 9.3): jumlah yang ditampilkan platform dan kelengkapan paginasi
    dibedakan dari jumlah unik yang teramati."""

    scope: tuple[Capability, ...]
    # True hanya bila adapter yakin seluruh halaman/paginasi yang tersedia sudah dibaca.
    # None = tidak diketahui; tidak boleh dianggap lengkap.
    pagination_complete: bool | None
    # Jumlah komentar/reply yang DITAMPILKAN platform, bila tersedia. Bukan jumlah teramati.
    platform_displayed_count: int | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", _tuple(self.scope))
        object.__setattr__(self, "notes", _tuple(self.notes))
        if self.platform_displayed_count is not None and self.platform_displayed_count < 0:
            raise ContractViolation("platform_displayed_count tidak boleh negatif.")


@dataclass(frozen=True)
class ArtifactCapture:
    """Artefak mentah dari adapter (screenshot, DOM, dst.). Disimpan lewat preservation.storage
    (WP-1.5); adapter tidak menulis ke disk sendiri.

    Isi diberikan sebagai `content` (bytes) ATAU `chunks` (pabrik yang menghasilkan iterable bytes
    baru pada tiap panggilan, untuk berkas besar). Pabrik dipanggil ulang saat ingestion
    diulang, jadi harus dapat menghasilkan isi yang sama lagi.
    """

    kind: ArtifactKind
    filename: str
    content: bytes | None
    content_type: str
    note: str | None = None
    chunks: Callable[[], Iterable[bytes]] | None = None

    def __post_init__(self) -> None:
        name = self.filename
        if not name or "/" in name or "\\" in name or name in (".", "..") or "\x00" in name:
            raise ContractViolation("filename artefak harus nama berkas sederhana tanpa direktori.")
        if not self.content_type.strip():
            raise ContractViolation("content_type artefak wajib diisi.")
        if self.kind is ArtifactKind.MANIFEST:
            raise ContractViolation("Adapter tidak boleh menghasilkan artefak jenis manifest.")
        if (self.content is None) == (self.chunks is None):
            raise ContractViolation("Artefak harus memiliki tepat satu dari content atau chunks.")

    def iter_chunks(self) -> Iterable[bytes]:
        """Isi sebagai aliran bytes; dapat dipanggil berulang."""
        if self.content is not None:
            return [self.content] if self.content else []
        assert self.chunks is not None
        return self.chunks()


@dataclass(frozen=True)
class UnavailableObject:
    """Pernyataan EKSPLISIT adapter bahwa sebuah objek tidak tersedia (mis. halaman objeknya
    mengembalikan 'dihapus'/404). Bukan hasil dari absennya objek pada sebuah daftar: itu hanya
    NOT_OBSERVED (PRD bagian 9.2). `evidence` menjelaskan apa yang diamati."""

    external_post_id: str
    evidence: str

    def __post_init__(self) -> None:
        if (
            not self.external_post_id.strip()
            or self.external_post_id != self.external_post_id.strip()
        ):
            raise ContractViolation(
                "external_post_id objek tidak tersedia harus string tidak kosong."
            )
        if not self.evidence.strip():
            raise ContractViolation("evidence ketidaktersediaan wajib diisi.")


@dataclass(frozen=True)
class InspectionResult:
    platform: Platform
    inspection_run_id: str
    outcome: InspectionOutcome
    collector: CollectorInfo
    coverage: Coverage
    observations: tuple[Observation, ...] = ()
    limitations: tuple[Limitation, ...] = ()
    artifacts: tuple[ArtifactCapture, ...] = field(default=())
    # Hanya untuk hasil COMPLETED: objek yang adapter nyatakan tidak tersedia secara eksplisit.
    confirmed_unavailable: tuple[UnavailableObject, ...] = field(default=())

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "confirmed_unavailable", _tuple(self.confirmed_unavailable))
        set_(self, "observations", _tuple(self.observations))
        set_(self, "limitations", _tuple(self.limitations))
        set_(self, "artifacts", _tuple(self.artifacts))
        if not isinstance(self.outcome, InspectionOutcome):
            raise ContractViolation("outcome harus InspectionOutcome.")
        if not self.inspection_run_id.strip():
            raise ContractViolation("inspection_run_id wajib diisi.")

        expected_status = (
            CollectionStatus.COMPLETED
            if self.outcome is InspectionOutcome.COMPLETED
            else CollectionStatus.PARTIAL
        )
        seen: set[str] = set()
        for obs in self.observations:
            if obs.platform != self.platform:
                raise ContractViolation(
                    f"Observasi dari platform {obs.platform.value} pada hasil "
                    f"{self.platform.value}: "
                    "adapter tidak boleh mengembalikan data platform lain."
                )
            if obs.inspection_run_id != self.inspection_run_id:
                raise ContractViolation("Observasi merujuk inspection_run_id yang berbeda.")
            if obs.collection_status is not expected_status:
                raise ContractViolation(
                    f"collection_status observasi ({obs.collection_status.value}) tidak sesuai "
                    f"dengan hasil {self.outcome.value}."
                )
            if obs.external_post_id is not None:
                if obs.external_post_id in seen:
                    raise ContractViolation(
                        f"external_post_id ganda dalam satu hasil: {obs.external_post_id}. "
                        "Adapter harus menyatukan objek yang sama dalam satu inspeksi."
                    )
                seen.add(obs.external_post_id)

        if self.confirmed_unavailable:
            if self.outcome is not InspectionOutcome.COMPLETED:
                raise ContractViolation(
                    "confirmed_unavailable hanya boleh pada hasil COMPLETED: ketidaktersediaan "
                    "memerlukan cakupan yang lengkap (PRD bagian 9.2)."
                )
            ids = [u.external_post_id for u in self.confirmed_unavailable]
            if len(set(ids)) != len(ids):
                raise ContractViolation("confirmed_unavailable memuat external_post_id ganda.")
            if set(ids) & seen:
                raise ContractViolation(
                    "Objek tidak boleh sekaligus teramati dan dinyatakan tidak tersedia."
                )

        names = [a.filename for a in self.artifacts]
        if len(set(names)) != len(names):
            raise ContractViolation("Nama berkas artefak harus unik dalam satu hasil.")

        codes = {lim.code for lim in self.limitations}
        blocking = [lim for lim in self.limitations if lim.code.blocking]
        outcome = self.outcome

        if outcome is InspectionOutcome.COMPLETED:
            if blocking:
                raise ContractViolation(
                    "COMPLETED tidak boleh disertai keterbatasan yang menghalangi: "
                    f"{sorted(c.value for c in codes if c.blocking)}."
                )
            if self.coverage.pagination_complete is not True:
                raise ContractViolation(
                    "COMPLETED mensyaratkan pagination_complete=True; kelengkapan yang tidak "
                    "diketahui harus dilaporkan sebagai PARTIAL."
                )
            if not self.observations and self.coverage.platform_displayed_count != 0:
                raise ContractViolation(
                    "Hasil kosong tidak boleh COMPLETED kecuali platform menyatakan jumlah 0; "
                    "kegagalan mengambil data harus dilaporkan sebagai FAILED/PARTIAL (FR-026)."
                )
        elif outcome is InspectionOutcome.PARTIAL:
            if not self.limitations:
                raise ContractViolation("PARTIAL wajib menjelaskan sebabnya lewat limitations.")
            if not blocking and self.coverage.pagination_complete is True:
                raise ContractViolation(
                    "PARTIAL tanpa sebab yang membatasi: hanya ada keterbatasan informasional dan "
                    "pagination lengkap; seharusnya COMPLETED."
                )
        else:
            if self.observations:
                raise ContractViolation(
                    f"{outcome.value} tidak boleh membawa observasi; data sebagian dilaporkan "
                    "sebagai PARTIAL."
                )
            if outcome is InspectionOutcome.ACCESS_RESTRICTED and not (
                codes & {LimitationCode.ACCESS_RESTRICTED, LimitationCode.AUTH_REQUIRED}
            ):
                raise ContractViolation(
                    "ACCESS_RESTRICTED wajib disertai limitation ACCESS_RESTRICTED "
                    "atau AUTH_REQUIRED."
                )
            if outcome is InspectionOutcome.UNSUPPORTED and LimitationCode.UNSUPPORTED not in codes:
                raise ContractViolation("UNSUPPORTED wajib disertai limitation UNSUPPORTED.")
            if outcome is InspectionOutcome.FAILED and not blocking:
                raise ContractViolation(
                    "FAILED wajib disertai limitation yang menjelaskan kegagalan."
                )

    @property
    def observed_reply_count(self) -> int:
        """Jumlah reply/comment UNIK teramati (bukan jumlah yang ditampilkan platform)."""
        return len(
            {
                o.external_post_id
                for o in self.observations
                if o.source_object_type.value in ("reply", "comment") and o.external_post_id
            }
        )
