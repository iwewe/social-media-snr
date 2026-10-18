"""Perbandingan dua profil akun dengan peringatan cakupan (FR-064). Tanpa skor atau peringkat."""

from typing import Any

from .types import DIMENSIONS, OK


class PlatformMismatch(ValueError):
    """Akun/profil lintas platform tidak dibandingkan (FR-073, FR-081)."""


def _coverage_warnings(label: str, cov: dict[str, Any]) -> list[str]:
    out = []
    if cov.get("partial_coverage"):
        out.append(
            f"{label}: hanya {len(cov['targets_covered'])} dari "
            f"{len(cov['targets_in_investigation'])} target diperiksa"
        )
    if cov.get("incomplete_runs"):
        out.append(f"{label}: ada pemeriksaan yang tidak lengkap (parsial/terbatas)")
    if cov.get("responses_without_known_time"):
        out.append(f"{label}: sebagian respons tanpa waktu publikasi yang diketahui")
    return out


def compare_profiles(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """`a`/`b`: {"coverage": {...}, "dimensions": {...}} sebagaimana tersimpan pada profil."""
    ca, cb = a["coverage"], b["coverage"]
    if ca["platform"] != cb["platform"]:
        raise PlatformMismatch("profil dari platform berbeda tidak dibandingkan")
    warnings = _coverage_warnings("A", ca) + _coverage_warnings("B", cb)
    if set(ca["targets_covered"]) != set(cb["targets_covered"]):
        warnings.append("cakupan target berbeda antara A dan B")
    if ca["period"] != cb["period"]:
        warnings.append("periode berbeda antara A dan B")
    if ca["dataset_version"] != cb["dataset_version"]:
        warnings.append("versi dataset berbeda antara A dan B")
    if ca["proposition_id"] != cb["proposition_id"]:
        warnings.append("proposition berbeda antara A dan B")
    dimensions = {}
    for name in DIMENSIONS:
        da, db = a["dimensions"][name], b["dimensions"][name]
        usable = da["status"] == OK and db["status"] == OK
        dimensions[name] = {"a": da, "b": db, "comparable": usable}
        if not usable:
            warnings.append(f"{name}: data tidak cukup pada salah satu profil; tidak dibandingkan")
    return {"comparable": not warnings, "warnings": warnings, "dimensions": dimensions}
