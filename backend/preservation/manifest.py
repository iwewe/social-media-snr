"""Manifest preservasi per capture (PRD bagian 10; FR-037).

Memuat: inspection_run_id, target dan URL sumber, waktu, cara perolehan, status/cakupan, versi
collector, dan daftar artefak yang BENAR-BENAR tersimpan (dengan SHA-256). Artefak yang tidak
tersimpan (ditolak kebijakan, gagal, konflik) dicatat terpisah di `unavailable` beserta alasannya;
tidak pernah dibuat berkas kosong sebagai pengganti (FR-042).

Manifest sendiri disimpan sebagai artefak (jenis `manifest`) dan di-hash. Nama berkasnya memuat
hash isi kanonik (tanpa `generated_at`), sehingga isi yang sama tidak menghasilkan berkas ganda
dan perubahan isi menghasilkan manifest baru tanpa menimpa yang lama.
"""

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from django.utils import timezone

from collection.contracts import Limitation
from collection.models import InspectionRun

from .models import EvidenceArtifact

MANIFEST_SCHEMA_VERSION = 1
GENERATOR = {"name": "snr.preservation", "manifest_schema": MANIFEST_SCHEMA_VERSION}


def build_manifest(
    run: InspectionRun,
    artifacts: Iterable[EvidenceArtifact],
    unavailable: list[dict[str, Any]],
    adapter_limitations: Iterable[Limitation],
) -> dict[str, Any]:
    target = run.target
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "inspection_run_id": run.run_id,
        "run_sequence": run.sequence,
        "target": {
            "id": target.pk,
            "platform": target.platform,
            "target_type": target.target_type,
            "source_url": target.normalized_url,
        },
        "acquisition": {
            "source_method": run.source_method,
            "collector": {"name": run.collector_name, "version": run.collector_version},
        },
        "status": {
            "outcome": (run.coverage or {}).get("outcome"),
            "coverage": run.coverage,
        },
        "artifacts": [
            {
                "kind": a.kind,
                "relative_path": a.relative_path,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
                "content_type": a.content_type,
                "note": a.note,
                "stored_at": a.stored_at.isoformat(),
            }
            for a in sorted(artifacts, key=lambda a: a.relative_path)
        ],
        "unavailable": sorted(
            unavailable, key=lambda u: (u.get("filename", ""), u.get("rule", ""))
        ),
        "adapter_limitations": [
            {"code": lim.code.value, "message": lim.message} for lim in adapter_limitations
        ],
        "generator": GENERATOR,
        "generated_at": timezone.now().isoformat(),
    }


def content_digest(manifest: dict[str, Any]) -> str:
    """Hash isi kanonik (tanpa `generated_at`) untuk penamaan berkas."""
    body = {k: v for k, v in manifest.items() if k != "generated_at"}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
