"""Enum kontrak observasi dan adapter (PRD bagian 7.1 dan 9.1)."""

from enum import StrEnum


class SourceObjectType(StrEnum):
    """Jenis objek sumber, dipertahankan sesuai aslinya (PRD bagian 3.1).

    REPLY dan COMMENT dibedakan karena istilah platform berbeda (X membalas, TikTok/Instagram/
    Facebook berkomentar); jenis asli tidak diseragamkan.
    """

    POST = "post"
    REPLY = "reply"
    COMMENT = "comment"
    QUOTE = "quote"
    REPOST = "repost"


class CollectionStatus(StrEnum):
    """Status pengumpulan yang menghasilkan observasi. COMPLETED bukan klaim semua konten
    platform ditemukan; hanya bahwa cakupan yang diminta selesai (PRD bagian 9.1)."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"


class SourceMethod(StrEnum):
    AUTHORIZED_OBSERVATION = "authorized_observation"
    IMPORTED_DATASET = "imported_dataset"
    OFFICIAL_API = "official_api"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class InspectionOutcome(StrEnum):
    """Hasil satu inspeksi dari sudut adapter. Orchestrator memetakannya ke status InspectionRun
    (PRD bagian 9.1); REVIEW_REQUIRED diputuskan orchestrator, bukan adapter."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    UNSUPPORTED = "UNSUPPORTED"


class LimitationCode(StrEnum):
    """Keterbatasan/kegagalan yang dilaporkan secara terstruktur (FR-026).

    Kode `blocking` menghalangi klaim COMPLETED. Kode informasional (artefak tidak tersedia/tidak
    diizinkan disimpan) boleh menyertai hasil COMPLETED (FR-042).
    """

    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    PARSE_FAILED = "PARSE_FAILED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    COMPLETENESS_UNKNOWN = "COMPLETENESS_UNKNOWN"
    MAX_ITEMS_REACHED = "MAX_ITEMS_REACHED"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
    ADAPTER_ERROR = (
        "ADAPTER_ERROR"  # galat tak terduga pada adapter (bug), bukan keterbatasan sumber
    )
    ARTIFACT_NOT_AVAILABLE = "ARTIFACT_NOT_AVAILABLE"
    ARTIFACT_NOT_PERMITTED = "ARTIFACT_NOT_PERMITTED"

    @property
    def blocking(self) -> bool:
        return self not in _INFORMATIONAL


_INFORMATIONAL = frozenset(
    {LimitationCode.ARTIFACT_NOT_AVAILABLE, LimitationCode.ARTIFACT_NOT_PERMITTED}
)


class Capability(StrEnum):
    """Kemampuan yang dapat dinyatakan sebuah adapter (FR-027)."""

    INSPECT_POST = "inspect_post"
    INSPECT_REPLIES = "inspect_replies"
    INSPECT_ACCOUNT = "inspect_account"
    PRESERVE_SCREENSHOT = "preserve_screenshot"
    PRESERVE_DOM = "preserve_dom"
    PRESERVE_MEDIA = "preserve_media"


class CapabilityStatus(StrEnum):
    """Hanya kemampuan yang telah diuji dan diizinkan yang dapat dijalankan (PRD bagian 15, I3)."""

    SUPPORTED = "SUPPORTED"
    LIMITED = "LIMITED"
    UNSUPPORTED = "UNSUPPORTED"
    UNTESTED = "UNTESTED"

    @property
    def runnable(self) -> bool:
        return self in (CapabilityStatus.SUPPORTED, CapabilityStatus.LIMITED)


class ArtifactKind(StrEnum):
    SCREENSHOT = "screenshot"
    DOM_SNAPSHOT = "dom_snapshot"
    RAW_RESPONSE = "raw_response"
    MEDIA = "media"
    OTHER = "other"
    # Hanya dibuat oleh SNR (preservation.manifest). Adapter tidak boleh menghasilkannya.
    MANIFEST = "manifest"
