"""Pemeriksaan hasil backup/restore (WP-3.6; NFR-10).

`snapshot()` merekam jumlah baris model domain dan ringkasan artefak bukti dari sistem sumber.
`verify(expected)` dijalankan pada sistem hasil restore: jumlah baris dan katalog artefak harus
sama, dan SETIAP berkas bukti dihitung ulang hash dan ukurannya terhadap catatan basis data.
Berkas di disk yang tidak tercatat hanya dilaporkan sebagai peringatan (bukan kegagalan).

Hash membuktikan berkas sama dengan saat dicatat, bukan keaslian konten platform (PRD bagian 10).
"""

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.apps import apps

from .models import EvidenceArtifact, VerificationResult
from .storage import evidence_root
from .verification import inspect_artifact

DOMAIN_APPS = frozenset({"investigations", "collection", "preservation", "intelligence", "audit"})
EXTRA_MODELS = frozenset({"auth.User", "auth.Group"})
FORMAT = 1


def _counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in apps.get_models():
        label = model._meta.label
        if model._meta.app_label in DOMAIN_APPS or label in EXTRA_MODELS:
            counts[label] = model._default_manager.count()
    return dict(sorted(counts.items()))


def catalog_digest(rows: Iterable[tuple[str, str, int]]) -> tuple[str, int, int]:
    """(digest katalog, jumlah, total byte): hash atas (jalur, sha256, ukuran) terurut."""
    digest = hashlib.sha256()
    total = 0
    n = 0
    for path, sha, size in sorted(rows):
        digest.update(f"{path}\0{sha}\0{size}\n".encode())
        total += size
        n += 1
    return digest.hexdigest(), n, total


def _artifact_digest() -> tuple[str, int, int]:
    rows = EvidenceArtifact.objects.values_list("relative_path", "sha256", "size_bytes")
    return catalog_digest(rows)


def snapshot() -> dict[str, Any]:
    catalog, n, total = _artifact_digest()
    return {
        "format": FORMAT,
        "counts": _counts(),
        "artifacts": {"count": n, "total_bytes": total, "catalog_sha256": catalog},
    }


def _files_on_disk() -> set[str]:
    root = evidence_root()
    if not root.exists():
        return set()
    found: set[str] = set()
    for base, _dirs, files in os.walk(root):
        for name in files:
            found.add(Path(base, name).relative_to(root).as_posix())
    return found


def verify(expected: dict[str, Any]) -> dict[str, Any]:
    """Bandingkan sistem saat ini dengan `expected` (hasil `snapshot()` sumber)."""
    problems: list[str] = []
    warnings: list[str] = []
    if expected.get("format") != FORMAT:
        problems.append(f"format snapshot tidak dikenal: {expected.get('format')!r}")
        return {"ok": False, "problems": problems, "warnings": warnings, "artifacts_checked": 0}

    now = snapshot()
    for label in sorted(set(expected["counts"]) | set(now["counts"])):
        want, have = expected["counts"].get(label), now["counts"].get(label)
        if want != have:
            problems.append(f"jumlah baris {label}: diharapkan {want}, ditemukan {have}")
    if expected["artifacts"]["catalog_sha256"] != now["artifacts"]["catalog_sha256"]:
        problems.append("katalog artefak berbeda dari sumber (jalur, hash, atau ukuran)")

    checked = 0
    bad: dict[str, str] = {
        VerificationResult.MISMATCH: "hash tidak cocok",
        VerificationResult.MISSING: "berkas hilang",
        VerificationResult.UNREADABLE: "jalur tidak sah atau bukan berkas biasa",
    }
    for art in EvidenceArtifact.objects.order_by("relative_path"):
        inspection = inspect_artifact(art)
        inspection.close()
        checked += 1
        if inspection.result != VerificationResult.MATCH:
            problems.append(f"artefak {art.relative_path}: {bad[inspection.result]}")

    recorded = set(EvidenceArtifact.objects.values_list("relative_path", flat=True))
    orphans = sorted(_files_on_disk() - recorded)
    if orphans:
        warnings.append(
            f"{len(orphans)} berkas di disk tidak tercatat di basis data (contoh: {orphans[0]})"
        )
    return {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "artifacts_checked": checked,
    }
