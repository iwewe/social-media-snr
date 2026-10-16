"""Penyimpanan artefak hasil inspeksi (WP-1.5a; FR-037, FR-038, FR-039, FR-042; NFR-04).

`persist_run_artifacts` menulis artefak dari `InspectionResult` ke filesystem lokal lewat
`preservation.storage` (satu-satunya jalur tulis, tidak pernah menimpa), mencatatnya di
`EvidenceArtifact`, lalu menulis manifest.

Jaminan:
- WAJIB kebijakan (`ArtifactPolicy`): tanpa nilai bawaan, agar tidak ada jalur yang menyimpan
  artefak tanpa pemeriksaan. Artefak yang ditolak dicatat di manifest dengan identitas aturan
  (bukan isinya) dan TIDAK disimpan, tanpa berkas kosong pengganti (FR-042).
- Idempoten dan tahan terputus: berkas yang sudah tercatat dengan isi sama dilewati; berkas yatim
  (tertulis tetapi baris DB belum dibuat karena proses mati) diadopsi bila hash-nya cocok;
  isi berbeda pada jalur yang sama dilaporkan sebagai konflik dan tidak ditimpa.
- Kegagalan satu artefak (aliran putus, terlalu besar) tidak merusak artefak lain: berkas parsial
  tidak tertinggal (storage menulis lewat berkas sementara) dan kegagalan dicatat.
- `run.preservation` bertanda IN_PROGRESS di awal; bila proses mati, penanda itu tertinggal.
- Serialisasi per run lewat advisory lock PostgreSQL.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    InspectionResult,
    LimitationCode,
)
from collection.models import InspectionRun

from . import manifest as manifest_module
from .models import EvidenceArtifact
from .policy import ArtifactPolicy
from .storage import (
    EvidenceStorageError,
    OverwriteRefused,
    StoredFile,
    resolve_inside_evidence,
    sha256_of,
    write_new,
)

logger = logging.getLogger(__name__)

ADVISORY_NAMESPACE = 0x534E52  # "SNR"
_DIRECTORY_BY_KIND = {ArtifactKind.SCREENSHOT: "screenshots", ArtifactKind.MANIFEST: "manifests"}


class ArtifactRejected(Exception):
    """Hasil/run tidak cocok; ditolak sebelum menulis apa pun."""


@dataclass
class ArtifactReport:
    run_id: int
    received: int = 0
    stored: int = 0
    already_stored: int = 0
    adopted: int = 0
    rejected: list[dict[str, str]] = field(default_factory=list)  # ditolak kebijakan
    failed: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    manifest_path: str | None = None

    @property
    def ok(self) -> bool:
        """True bila tidak ada kegagalan atau konflik. Penolakan kebijakan adalah hasil yang
        diharapkan (dicatat di manifest), bukan kegagalan."""
        return not self.failed and not self.conflicts

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _relative_path(run: InspectionRun, capture: ArtifactCapture) -> str:
    directory = _DIRECTORY_BY_KIND.get(capture.kind, "captures")
    return f"{directory}/{run.run_id}/{capture.filename}"


def _digest(chunks: Any) -> tuple[str, int]:
    sha, size = hashlib.sha256(), 0
    for chunk in chunks:
        sha.update(chunk)
        size += len(chunk)
    return sha.hexdigest(), size


def _record(
    run: InspectionRun, kind: str, stored: StoredFile, content_type: str, note: str
) -> None:
    with transaction.atomic():
        EvidenceArtifact.record(
            run=run, kind=kind, stored=stored, content_type=content_type, note=note
        )


def _persist_one(
    run: InspectionRun,
    kind: str,
    rel: str,
    chunks_factory: Any,
    content_type: str,
    note: str,
    max_bytes: int | None,
    report: ArtifactReport,
    label: str,
) -> bool:
    """Simpan satu berkas. True bila kini tercatat (baru, sudah ada, atau diadopsi)."""
    existing = EvidenceArtifact.objects.filter(relative_path=rel).first()
    if existing is not None:
        digest, _size = _digest(chunks_factory())
        if existing.sha256 == digest and existing.run_id == run.pk:
            report.already_stored += 1
            return True
        report.conflicts.append(
            {"filename": label, "path": rel, "detail": "jalur sudah tercatat dengan isi berbeda"}
        )
        return False
    try:
        stored = write_new(rel, chunks_factory(), max_bytes=max_bytes)
    except OverwriteRefused:
        # Berkas yatim (proses mati sebelum baris DB dibuat): adopsi hanya bila isinya sama.
        digest, size = _digest(chunks_factory())
        if sha256_of(rel) != digest:
            report.conflicts.append(
                {"filename": label, "path": rel, "detail": "berkas ada dengan isi berbeda"}
            )
            return False
        stored = StoredFile(relative_path=rel, size=size, sha256=digest)
        try:
            _record(run, kind, stored, content_type, note)
        except IntegrityError:
            report.failed.append({"filename": label, "kind": kind, "error": "IntegrityError"})
            return False
        report.adopted += 1
        return True
    except EvidenceStorageError as exc:
        report.failed.append({"filename": label, "kind": kind, "error": type(exc).__name__})
        return False
    except Exception as exc:  # noqa: BLE001 - aliran sumber putus, disk penuh, dst.
        logger.exception("Artefak %s gagal disimpan pada run %s", label, run.pk)
        report.failed.append({"filename": label, "kind": kind, "error": type(exc).__name__})
        return False
    try:
        _record(run, kind, stored, content_type, note)
    except IntegrityError:
        report.failed.append({"filename": label, "kind": kind, "error": "IntegrityError"})
        return False
    report.stored += 1
    return True


def _persist_manifest(
    run: InspectionRun, rel: str, body: bytes, digest: str, report: ArtifactReport
) -> bool:
    """Simpan manifest. Nama berkas memuat hash isi kanonik (tanpa `generated_at`), jadi nama yang
    sama berarti isi yang sama walau `generated_at`-nya berbeda; bukan konflik. Batas ukuran artefak
    tidak berlaku untuk manifest."""
    if EvidenceArtifact.objects.filter(
        run=run, relative_path=rel, kind=ArtifactKind.MANIFEST.value
    ).exists():
        report.already_stored += 1
        return True
    try:
        stored = write_new(rel, [body])
    except OverwriteRefused:
        # Manifest yatim: adopsi bila isi kanonik-nya sama (generated_at boleh berbeda).
        try:
            existing = json.loads(resolve_inside_evidence(rel).read_text(encoding="utf-8"))
            same = manifest_module.content_digest(existing) == digest
        except (OSError, ValueError):
            same = False
        if not same:
            report.conflicts.append(
                {"filename": "manifest", "path": rel, "detail": "manifest ada dengan isi berbeda"}
            )
            return False
        stored = StoredFile(
            relative_path=rel,
            size=resolve_inside_evidence(rel).stat().st_size,
            sha256=sha256_of(rel),
        )
        report.adopted += 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Manifest gagal disimpan pada run %s", run.pk)
        report.failed.append(
            {"filename": "manifest", "kind": "manifest", "error": type(exc).__name__}
        )
        return False
    else:
        report.stored += 1
    try:
        _record(run, ArtifactKind.MANIFEST.value, stored, "application/json", "manifest preservasi")
    except IntegrityError:
        report.failed.append(
            {"filename": "manifest", "kind": "manifest", "error": "IntegrityError"}
        )
        return False
    return True


def _set_state(run: InspectionRun, state: dict[str, Any]) -> None:
    InspectionRun.objects.filter(pk=run.pk).update(preservation=state)


def persist_run_artifacts(
    run: InspectionRun,
    result: InspectionResult,
    *,
    policy: ArtifactPolicy,
    max_bytes: int | None = None,
) -> ArtifactReport:
    """Simpan artefak `result` untuk `run` dan tulis manifest. Lihat docstring modul."""
    if result.platform.value != run.target.platform:
        raise ArtifactRejected("Hasil platform lain tidak boleh disimpan pada run ini.")
    if result.inspection_run_id != run.run_id:
        raise ArtifactRejected("inspection_run_id pada hasil tidak cocok dengan run.")
    if max_bytes is None:
        max_bytes = getattr(settings, "SNR_ARTIFACT_MAX_BYTES", None)

    adapter_limitations = [
        lim
        for lim in result.limitations
        if lim.code
        in (LimitationCode.ARTIFACT_NOT_AVAILABLE, LimitationCode.ARTIFACT_NOT_PERMITTED)
    ]
    report = ArtifactReport(run_id=run.pk, received=len(result.artifacts))
    if not result.artifacts and not adapter_limitations:
        return report  # tidak ada yang perlu dipreservasi

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s, %s)", [ADVISORY_NAMESPACE, run.pk % 2**31])
    try:
        run.refresh_from_db()
        _set_state(run, {"state": "IN_PROGRESS", "started_at": timezone.now().isoformat()})

        for capture in result.artifacts:
            decision = policy.check(capture)
            if not decision.allowed:
                report.rejected.append(
                    {
                        "filename": capture.filename,
                        "kind": capture.kind.value,
                        "rule": decision.rule,
                        "reason": decision.reason,
                    }
                )
                continue
            _persist_one(
                run,
                capture.kind.value,
                _relative_path(run, capture),
                capture.iter_chunks,
                capture.content_type,
                capture.note or "",
                max_bytes,
                report,
                capture.filename,
            )

        unavailable = (
            [
                {
                    "filename": r["filename"],
                    "kind": r["kind"],
                    "code": "ARTIFACT_NOT_PERMITTED",
                    "rule": r["rule"],
                    "reason": r["reason"],
                }
                for r in report.rejected
            ]
            + [
                {
                    "filename": f["filename"],
                    "kind": f["kind"],
                    "code": "ARTIFACT_NOT_AVAILABLE",
                    "rule": "storage",
                    "reason": f["error"],
                }
                for f in report.failed
            ]
            + [
                {
                    "filename": c["filename"],
                    "kind": "",
                    "code": "ARTIFACT_CONFLICT",
                    "rule": "conflict",
                    "reason": c["detail"],
                }
                for c in report.conflicts
            ]
        )
        stored_rows = list(
            EvidenceArtifact.objects.filter(run=run).exclude(kind=ArtifactKind.MANIFEST.value)
        )
        manifest = manifest_module.build_manifest(
            run, stored_rows, unavailable, adapter_limitations
        )
        digest = manifest_module.content_digest(manifest)
        rel = f"manifests/{run.run_id}/manifest-{digest[:16]}.json"
        body = manifest_module.serialize(manifest)
        if _persist_manifest(run, rel, body, digest, report):
            report.manifest_path = rel

        state = "FINISHED" if report.ok else "FINISHED_WITH_PROBLEMS"
        _set_state(
            run,
            {"state": state, "finished_at": timezone.now().isoformat(), "report": report.to_dict()},
        )
        return report
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_unlock(%s, %s)", [ADVISORY_NAMESPACE, run.pk % 2**31]
            )


def make_artifact_sink(policy: ArtifactPolicy, max_bytes: int | None = None):
    """Pabrik `artifact_sink` untuk `collection.ingestion.ingest_result` (tanpa impor terbalik)."""

    def sink(run: InspectionRun, result: InspectionResult) -> ArtifactReport:
        return persist_run_artifacts(run, result, policy=policy, max_bytes=max_bytes)

    return sink


def verify_run_artifacts(run: InspectionRun) -> list[dict[str, str]]:
    """Periksa hash seluruh artefak run terhadap berkas di disk (FR-040, AT-06).

    Mengembalikan daftar masalah; kosong berarti semua cocok. Hash hanya membuktikan berkas masih
    sama dengan saat di-hash, bukan keaslian konten platform (PRD bagian 10)."""
    problems = []
    for art in EvidenceArtifact.objects.filter(run=run).order_by("relative_path"):
        try:
            resolve_inside_evidence(art.relative_path)
            actual = sha256_of(art.relative_path)
        except FileNotFoundError:
            problems.append({"path": art.relative_path, "problem": "berkas hilang"})
            continue
        except EvidenceStorageError:
            problems.append({"path": art.relative_path, "problem": "jalur tidak sah"})
            continue
        if actual != art.sha256:
            problems.append({"path": art.relative_path, "problem": "hash tidak cocok"})
    return problems
