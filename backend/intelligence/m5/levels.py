"""Tingkat, sumbu, dan hipotesis alternatif M5 (WP-2.6; PRD 11.5; FR-077..FR-080). Murni."""

from enum import IntEnum, StrEnum


class ResultTier(IntEnum):
    """Empat tingkat hasil (PRD 11.5). Tingkat 4 hanya untuk hasil yang sudah ditinjau manusia."""

    OBSERVED_EVIDENCE = 1
    ANALYTICAL_CLASSIFICATION = 2
    BEHAVIORAL_NETWORK_PATTERN = 3
    REVIEWED_ANALYTICAL_FINDING = 4


class Confidence(StrEnum):
    """Analytical confidence; BUKAN probabilitas bahwa akun adalah buzzer."""

    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class QualityLevel(StrEnum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class AlternativeOutcome(StrEnum):
    RULED_OUT = "RULED_OUT"
    NOT_RULED_OUT = "NOT_RULED_OUT"
    CANNOT_ASSESS = "CANNOT_ASSESS"


AXES = ("integrity", "provenance", "completeness", "relevance")
# Empat hipotesis alternatif yang wajib dipertimbangkan (PRD 11.5).
GENERAL_ALTERNATIVES = (
    "organic_mobilization",
    "external_event",
    "public_content_copying",
    "sampling_bias",
)
ALTERNATIVE_TITLES = {
    "organic_mobilization": "mobilisasi organik",
    "external_event": "efek berita atau peristiwa eksternal",
    "public_content_copying": "penyalinan konten publik tanpa pengaturan bersama",
    "sampling_bias": "bias sampling atau observasi",
}
QUALITY_RANK = {QualityLevel.POOR: 1, QualityLevel.ACCEPTABLE: 2, QualityLevel.GOOD: 3}
CONFIDENCE_RANK = {Confidence.LOW: 1, Confidence.MODERATE: 2, Confidence.HIGH: 3}
