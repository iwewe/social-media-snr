"""Kebijakan confidence, saran kualitas bukti, dan penjaga kosakata vonis (WP-2.6). Murni.

Aturan di sini adalah KEBIJAKAN ANALITIK yang eksplisit dan dapat diperiksa, bukan ambang kebenaran
dan bukan probabilitas. Plafon confidence membatasi klaim berdasarkan kualitas bukti, status
hipotesis alternatif, dan jumlah bukti yang benar-benar independen; peninjau tetap dapat memilih
lebih rendah, atau NOT_ASSESSABLE (selalu diperbolehkan, dengan alasan).
"""

import pathlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .levels import (
    AXES,
    CONFIDENCE_RANK,
    GENERAL_ALTERNATIVES,
    QUALITY_RANK,
    AlternativeOutcome,
    Confidence,
    QualityLevel,
)

# --- larangan vonis (FR-079) -------------------------------------------------------------------


def _load_terms() -> list[str]:
    path = pathlib.Path(__file__).with_name("verdict_terms.txt")
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


_FORBIDDEN_RE = re.compile(r"(?<!\w)(" + "|".join(_load_terms()) + r")(?!\w)", re.IGNORECASE)


class VerdictLanguage(ValueError):
    """Teks memuat istilah vonis tentang operasi berbayar/aktor pengendali."""


def check_no_verdict(field: str, text: str) -> None:
    found = _FORBIDDEN_RE.search(text or "")
    if found:
        raise VerdictLanguage(
            f"{field} memuat istilah vonis ('{found.group(0)}'); Finding hanya menggambarkan pola "
            "terobservasi, bukan menyimpulkan operasi berbayar atau aktor pengendali (FR-079)"
        )


# --- plafon confidence ---------------------------------------------------------------------------


def alternatives_complete(alternatives: Mapping[str, Any]) -> list[str]:
    """Kunci hipotesis wajib yang belum lengkap (kosong = lengkap)."""
    missing = []
    for key in GENERAL_ALTERNATIVES:
        item = alternatives.get(key)
        valid = (
            isinstance(item, Mapping)
            and item.get("outcome") in {o.value for o in AlternativeOutcome}
            and isinstance(item.get("reasoning"), str)
            and item["reasoning"].strip()
        )
        if not valid:
            missing.append(key)
    return missing


def confidence_ceiling(
    axes: Mapping[str, QualityLevel],
    alternatives: Mapping[str, Any],
    independent_groups: int | None,
    *,
    synthetic: bool = False,
) -> tuple[Confidence, list[str]]:
    """Plafon tertinggi yang boleh dipilih (HIGH/MODERATE/LOW) beserta alasannya."""
    ceiling = Confidence.HIGH
    reasons: list[str] = []

    def cap(level: Confidence, reason: str) -> None:
        nonlocal ceiling
        reasons.append(reason)
        if CONFIDENCE_RANK[level] < CONFIDENCE_RANK[ceiling]:
            ceiling = level

    if synthetic:
        cap(
            Confidence.LOW,
            "data sintetis: temuan hanya untuk menguji alur, bukan pengamatan platform",
        )
    for axis in AXES:
        level = axes.get(axis, QualityLevel.NOT_ASSESSABLE)
        if level in (QualityLevel.POOR, QualityLevel.NOT_ASSESSABLE):
            cap(Confidence.LOW, f"sumbu bukti '{axis}' bernilai {level.value}")
    for key in GENERAL_ALTERNATIVES:
        item = alternatives.get(key)
        outcome = item.get("outcome") if isinstance(item, Mapping) else None
        if outcome == AlternativeOutcome.NOT_RULED_OUT:
            cap(Confidence.MODERATE, f"hipotesis alternatif '{key}' belum dapat disingkirkan")
        elif outcome != AlternativeOutcome.RULED_OUT:
            cap(
                Confidence.LOW,
                f"hipotesis alternatif '{key}' belum dinilai (atau tidak dapat dinilai)",
            )
    if independent_groups is None or independent_groups < 2:
        cap(Confidence.MODERATE, "bukti independen kurang dari dua kelompok")
    return ceiling, reasons


def confidence_allowed(
    chosen: Confidence,
    axes: Mapping[str, QualityLevel],
    alternatives: Mapping[str, Any],
    independent_groups: int | None,
    *,
    synthetic: bool = False,
) -> tuple[bool, Confidence, list[str]]:
    ceiling, reasons = confidence_ceiling(
        axes, alternatives, independent_groups, synthetic=synthetic
    )
    if chosen is Confidence.NOT_ASSESSABLE:
        return True, ceiling, reasons
    return CONFIDENCE_RANK[chosen] <= CONFIDENCE_RANK[ceiling], ceiling, reasons


# --- saran kualitas bukti dari fakta sistem ------------------------------------------------------

_BAD_OUTCOMES = {"FAILED", "ACCESS_RESTRICTED", "UNSUPPORTED", "PARTIAL"}


def suggest_integrity(facts: Mapping[str, int]) -> tuple[QualityLevel, str]:
    total = facts["artifacts"]
    if total == 0:
        return QualityLevel.NOT_ASSESSABLE, "tidak ada artefak preservasi pada pemeriksaan terkait"
    problems = facts["mismatch"] + facts["missing"] + facts["unreadable"]
    if problems:
        return QualityLevel.POOR, f"{problems} artefak gagal verifikasi hash terakhir"
    if facts["verified_match"] == total:
        return (
            QualityLevel.GOOD,
            "semua artefak cocok pada verifikasi hash terakhir (bukan bukti keaslian)",
        )
    if facts["verified_match"] == 0:
        return QualityLevel.NOT_ASSESSABLE, "artefak belum pernah diverifikasi"
    return QualityLevel.ACCEPTABLE, "sebagian artefak sudah diverifikasi dan cocok"


def suggest_completeness(runs: Sequence[Mapping[str, Any]]) -> tuple[QualityLevel, str]:
    if not runs:
        return QualityLevel.NOT_ASSESSABLE, "tidak ada metadata pemeriksaan"
    if any(r["outcome"] in _BAD_OUTCOMES for r in runs):
        return QualityLevel.POOR, "ada pemeriksaan parsial, gagal, atau terbatas akses"
    if any(r["pagination_complete"] is None for r in runs):
        return (
            QualityLevel.NOT_ASSESSABLE,
            "kelengkapan paginasi tidak diketahui pada sebagian pemeriksaan",
        )
    if any(r["pagination_complete"] is False for r in runs):
        return QualityLevel.POOR, "paginasi tidak lengkap pada sebagian pemeriksaan"
    if any(r["limitations"] for r in runs):
        return QualityLevel.ACCEPTABLE, "ada keterbatasan yang dicatat pada pemeriksaan"
    return QualityLevel.GOOD, "semua pemeriksaan selesai dengan paginasi lengkap tanpa keterbatasan"


def suggest_provenance(methods: Sequence[str]) -> tuple[QualityLevel, str]:
    ms = set(methods)
    if not ms:
        return QualityLevel.NOT_ASSESSABLE, "metode sumber tidak tercatat"
    if ms == {"synthetic_fixture"}:
        return QualityLevel.NOT_ASSESSABLE, "data sintetis: bukan pengamatan platform"
    if "synthetic_fixture" in ms:
        return QualityLevel.POOR, "data sintetis tercampur dengan sumber lain"
    if "imported_dataset" in ms:
        return QualityLevel.ACCEPTABLE, "dataset impor; keabsahan sumber diverifikasi di luar kode"
    return QualityLevel.GOOD, "dikumpulkan lewat metode pengumpulan tercatat"


def validate_axes(
    ratings: Mapping[str, Mapping[str, Any]], suggestions: Mapping[str, tuple[QualityLevel, str]]
) -> dict[str, QualityLevel]:
    """Periksa penilaian peninjau per sumbu; kembalikan tingkat yang dipakai. Raise ValueError."""
    if set(ratings) != set(AXES):
        raise ValueError(f"penilaian bukti wajib tepat untuk sumbu {list(AXES)}")
    chosen: dict[str, QualityLevel] = {}
    for axis in AXES:
        item = ratings[axis]
        try:
            level = QualityLevel(str(item.get("level")))
        except ValueError:
            raise ValueError(f"sumbu {axis}: level tidak sah") from None
        if not str(item.get("reason", "")).strip():
            raise ValueError(f"sumbu {axis}: alasan wajib diisi")
        suggested = suggestions.get(axis)
        if (
            suggested
            and suggested[0] is not QualityLevel.NOT_ASSESSABLE
            and level is not QualityLevel.NOT_ASSESSABLE
            and QUALITY_RANK[level] > QUALITY_RANK[suggested[0]]
            and not str(item.get("override_reason", "")).strip()
        ):
            raise ValueError(
                f"sumbu {axis}: level {level.value} lebih baik daripada saran sistem "
                f"{suggested[0].value} ({suggested[1]}); isi override_reason"
            )
        chosen[axis] = level
    return chosen
