"""Pembantu tes WP-1.10: run nyata dengan artefak (screenshot + DOM + manifest), tanpa jaringan."""

import json
from pathlib import Path

from collection.datasets import register_fixture_adapters
from collection.models import InspectionRun
from collection.orchestrator import registry, request_inspection, run_inspection
from collection_helpers import register
from investigations import services as inv_services
from investigations.enums import Platform
from preservation.models import EvidenceArtifact
from preservation.storage import resolve_inside_evidence

SHOT = b"PNG-palsu-untuk-uji"  # ASCII: data sampel disimpan sebagai UTF-8
DOM = b"<html><body><p>Balasan sintetis</p></body></html>"
URL = "https://x.com/u/status/5"


def write_dataset(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bukti.json").write_text(json.dumps({
        "schema_version": 1, "name": "bukti", "platform": "x", "target_url": URL,
        "source_method": "synthetic_fixture",
        "snapshots": [{
            "observed_at": "2026-10-16T01:00:00Z", "outcome": "COMPLETED",
            "pagination_complete": True, "displayed_count": 1,
            "observations": [
                {"type": "post", "id": "5", "actor": "a1", "text": "awal"},
                {"type": "reply", "id": "6", "actor": "a2", "parent": "5", "text": "balasan"},
            ],
            "artifacts": [
                {"kind": "screenshot", "filename": "layar.png", "content_type": "image/png",
                 "text": SHOT.decode()},
                {"kind": "dom_snapshot", "filename": "dom.html", "content_type": "text/html",
                 "text": DOM.decode()},
            ],
        }],
    }))


def make_run_with_artifacts(user, settings, tmp_path: Path) -> InspectionRun:
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir(exist_ok=True)
    write_dataset(tmp_path / "ds")
    registry.clear()
    register_fixture_adapters(registry, tmp_path / "ds")
    inv = inv_services.create_investigation(user=user, name="Bukti")
    target = register(inv, user, Platform.X, URL)
    run = request_inspection(target=target, user=user, enqueue=False)
    run_inspection(run.pk)
    run.refresh_from_db()
    assert EvidenceArtifact.objects.filter(run=run).count() == 3, "screenshot + dom + manifest"
    return run


def artifact(run: InspectionRun, kind: str) -> EvidenceArtifact:
    return EvidenceArtifact.objects.filter(run=run, kind=kind).order_by("-id").first()  # type: ignore[return-value]


def disk_path(a: EvidenceArtifact) -> Path:
    return resolve_inside_evidence(a.relative_path)


def tamper(a: EvidenceArtifact, content: bytes) -> None:
    path = disk_path(a)
    path.chmod(0o644)
    path.write_bytes(content)
