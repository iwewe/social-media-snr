"""Verifikasi integritas artefak bukti (WP-1.10; FR-040, NFR-02; PRD bagian 10).

Pernyataan integritas yang boleh dibuat (PRD 10): hash memeriksa apakah berkas yang tersimpan masih
sama dengan saat di-hash. Hash TIDAK membuktikan konten platform autentik, lengkap, atau benar
secara faktual.

Prinsip:
- Dihitung ULANG dari berkas pada disk; catatan basis data hanya pembanding.
- Hasil dibedakan: MATCH, MISMATCH (isi/ukuran berbeda), MISSING (berkas hilang), UNREADABLE
  (jalur tidak sah, symlink, atau tidak dapat dibaca). Kegagalan tidak pernah disamarkan jadi MATCH.
- Berkas dibuka SATU kali: hash dan (untuk unduhan) aliran isi memakai deskriptor yang sama, jadi
  penggantian jalur di antara pemeriksaan dan pembacaan tidak berpengaruh.
- Setiap verifikasi dicatat append-only (siapa, kapan, hasil), termasuk yang gagal: ketidakcocokan
  adalah kejadian yang harus tetap terlihat. Jalur berkas tidak pernah dicatat atau dilaporkan.
"""

import hashlib
import json
import logging
import os
import stat
from dataclasses import dataclass
from typing import IO, Any

from django.contrib.auth.models import AbstractBaseUser

from collection.models import InspectionRun

from .models import ArtifactVerification, EvidenceArtifact, VerificationResult
from .storage import CHUNK_SIZE, PathNotAllowed, evidence_root, resolve_inside_evidence

logger = logging.getLogger(__name__)

INTEGRITY_STATEMENT = (
    "Hash memeriksa apakah berkas yang tersimpan masih sama dengan saat di-hash. Hash tidak "
    "membuktikan bahwa konten platform autentik, lengkap, atau benar secara faktual."
)


@dataclass
class Inspection:
    """Hasil memeriksa satu artefak. `handle` (hanya bila MATCH) terbuka di posisi 0; penerima
    wajib menutupnya."""

    result: str
    actual_sha256: str | None = None
    actual_size: int | None = None
    handle: IO[bytes] | None = None

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def _has_symlink(relative_path: str) -> bool:
    """True bila ada komponen jalur di bawah akar evidence yang berupa symlink."""
    current = evidence_root()
    for part in relative_path.split("/"):
        current = current / part
        if current.is_symlink():
            return True
    return False


def inspect_artifact(artifact: EvidenceArtifact) -> Inspection:
    """Hitung ulang SHA-256 dan ukuran dari berkas pada disk, lalu bandingkan dengan catatan."""
    try:
        path = resolve_inside_evidence(artifact.relative_path)
        if _has_symlink(artifact.relative_path):
            return Inspection(VerificationResult.UNREADABLE)
        # O_NONBLOCK: membuka FIFO tidak menggantung menunggu penulis; O_NOFOLLOW: tolak symlink.
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except FileNotFoundError:
        return Inspection(VerificationResult.MISSING)
    except (PathNotAllowed, OSError, ValueError):
        return Inspection(VerificationResult.UNREADABLE)

    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):  # direktori, FIFO, perangkat: bukan berkas bukti
            os.close(fd)
            return Inspection(VerificationResult.UNREADABLE)
        handle = os.fdopen(fd, "rb")
    except OSError:
        os.close(fd)
        return Inspection(VerificationResult.UNREADABLE)
    try:
        size = info.st_size
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    except OSError:
        handle.close()
        return Inspection(VerificationResult.UNREADABLE)
    actual = digest.hexdigest()
    if actual == artifact.sha256.lower() and size == artifact.size_bytes:
        handle.seek(0)
        return Inspection(VerificationResult.MATCH, actual, size, handle)
    handle.close()
    return Inspection(VerificationResult.MISMATCH, actual, size)


def record(
    artifact: EvidenceArtifact,
    user: AbstractBaseUser,
    inspection: Inspection,
    purpose: str,
) -> ArtifactVerification:
    row = ArtifactVerification.objects.create(
        artifact=artifact,
        verified_by=user,  # type: ignore[misc]
        purpose=purpose,
        result=inspection.result,
        expected_sha256=artifact.sha256,
        expected_size=artifact.size_bytes,
        actual_sha256=inspection.actual_sha256,
        actual_size=inspection.actual_size,
    )
    if inspection.result != VerificationResult.MATCH:
        # Tanpa jalur berkas: hanya identitas catatan.
        logger.warning(
            "Verifikasi artefak %s (%s) menghasilkan %s oleh %s",
            artifact.pk,
            artifact.kind,
            inspection.result,
            user.get_username(),
        )
    return row


def verify_artifact(
    artifact: EvidenceArtifact, user: AbstractBaseUser, *, purpose: str = "verify"
) -> ArtifactVerification:
    inspection = inspect_artifact(artifact)
    try:
        return record(artifact, user, inspection, purpose)
    finally:
        inspection.close()


def _manifest_artifacts(run: InspectionRun) -> list[EvidenceArtifact]:
    return list(EvidenceArtifact.objects.filter(run=run, kind="manifest").order_by("-id"))


def check_manifest(run: InspectionRun, manifest_verification: str | None) -> dict[str, Any]:
    """Bandingkan manifest terbaru run dengan catatan artefak di basis data.

    Manifest sendiri harus lebih dulu MATCH; bila tidak, isinya tidak dipercaya. Perbedaan
    dilaporkan sebagai daftar ID artefak/jenis (bukan jalur berkas)."""
    manifests = _manifest_artifacts(run)
    if not manifests:
        return {"state": "ABSENT", "problems": []}
    if manifest_verification != VerificationResult.MATCH:
        return {"state": "UNTRUSTED", "problems": ["manifest tidak lolos verifikasi hash"]}
    latest = manifests[0]
    inspection = inspect_artifact(latest)
    try:
        if inspection.handle is None:
            return {"state": "UNTRUSTED", "problems": ["manifest tidak dapat dibaca"]}
        try:
            data = json.loads(inspection.handle.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"state": "INCONSISTENT", "problems": ["manifest bukan JSON yang sah"]}
    finally:
        inspection.close()

    problems: list[str] = []
    if data.get("inspection_run_id") != run.run_id:
        problems.append("manifest merujuk run yang berbeda")
    listed = {a.get("relative_path"): a for a in data.get("artifacts", []) if isinstance(a, dict)}
    stored = EvidenceArtifact.objects.filter(run=run).exclude(kind="manifest")
    rows = {a.relative_path: a for a in stored}
    for path, row in rows.items():
        entry = listed.get(path)
        if entry is None:
            problems.append(f"artefak #{row.pk} ({row.kind}) tidak tercantum di manifest")
        elif entry.get("sha256") != row.sha256 or entry.get("size_bytes") != row.size_bytes:
            problems.append(f"artefak #{row.pk} ({row.kind}) berbeda dari manifest")
    if listed.keys() - rows.keys():
        problems.append("manifest memuat artefak yang tidak ada di basis data")
    return {"state": "CONSISTENT" if not problems else "INCONSISTENT", "problems": problems}


def verify_run(run: InspectionRun, user: AbstractBaseUser) -> dict[str, Any]:
    """Verifikasi semua artefak run (termasuk manifest) dan konsistensi manifest."""
    rows = list(EvidenceArtifact.objects.filter(run=run).order_by("id"))
    verifications = [verify_artifact(a, user, purpose="verify_run") for a in rows]
    manifest_ids = {a.pk for a in rows if a.kind == "manifest"}
    latest_manifest = max(manifest_ids, default=None)
    manifest_result = next(
        (v.result for v in verifications if v.artifact_id == latest_manifest), None
    )
    summary: dict[str, int] = {}
    for v in verifications:
        summary[v.result] = summary.get(v.result, 0) + 1
    manifest = check_manifest(run, manifest_result)
    all_match = bool(verifications) and set(summary) == {VerificationResult.MATCH}
    return {
        "verifications": verifications,
        "summary": summary,
        "manifest": manifest,
        "all_match": all_match and manifest["state"] in ("CONSISTENT", "ABSENT"),
    }
