"""WP-1.2: kerangka EvidenceArtifact (FR-037, FR-038, FR-039; NFR-02)."""

import hashlib
from pathlib import Path

import pytest
from collection import services
from collection.contracts import ArtifactKind, Capability
from collection.errors import AppendOnlyViolation
from collection.models import Post
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, transaction
from investigations import services as inv_services
from investigations.enums import Platform, TargetType
from preservation import storage
from preservation.models import EvidenceArtifact
from preservation.storage import PathNotAllowed, StoredFile

pytestmark = pytest.mark.django_db

SHA = hashlib.sha256(b"x").hexdigest()


@pytest.fixture
def run_x(settings, tmp_path: Path):
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="A")
    target = inv_services.register_target(
        investigation=inv, user=user, platform=Platform.X, target_type=TargetType.POST,
        url="https://x.com/u/status/1",
    )
    return services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_POST])


@pytest.fixture
def run_tt(run_x):
    user = run_x.requested_by
    inv = inv_services.create_investigation(user=user, name="B")
    target = inv_services.register_target(
        investigation=inv, user=user, platform=Platform.TIKTOK, target_type=TargetType.POST,
        url="https://tiktok.com/@u/video/1",
    )
    return services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_POST])


def stored(path: str = "run-1/shot.png") -> StoredFile:
    return StoredFile(relative_path=path, size=1, sha256=SHA)


def test_record_artifact_written_by_storage_and_verify_it(run_x) -> None:
    written = storage.write_new("run-1/capture.html", b"<html>")
    art = EvidenceArtifact.record(
        run=run_x, kind=ArtifactKind.DOM_SNAPSHOT, stored=written, content_type="text/html"
    )
    assert art.sha256 == written.sha256 and art.size_bytes == written.size
    assert storage.verify_stored(art.relative_path, art.sha256)  # NFR-02
    assert run_x.artifacts.count() == 1


def test_uppercase_hash_is_normalised_and_malformed_hash_is_rejected(run_x) -> None:
    art = EvidenceArtifact.record(
        run=run_x, kind="screenshot", stored=StoredFile("a.png", 1, SHA.upper()), content_type="image/png"
    )
    assert art.sha256 == SHA
    for bad in ("xyz", SHA[:-1], SHA + "0", "g" * 64):
        # Hash salah format ditolak DB: IntegrityError (CHECK) atau DataError (varchar(64)).
        with pytest.raises(DatabaseError), transaction.atomic():
            EvidenceArtifact.objects.create(
                run=run_x, kind="screenshot", relative_path=f"bad/{bad[:5]}.png", sha256=bad,
                size_bytes=1, content_type="image/png",
            )


def test_pointer_cannot_leave_the_evidence_root(run_x) -> None:
    for bad in ("../luar.png", "/etc/passwd", "a/../../b", "a//b", ""):
        with pytest.raises(PathNotAllowed):
            EvidenceArtifact.record(
                run=run_x, kind="other", stored=stored(bad), content_type="image/png"
            )
    assert not EvidenceArtifact.objects.exists()


def test_a_path_can_be_recorded_only_once(run_x) -> None:
    EvidenceArtifact.record(run=run_x, kind="screenshot", stored=stored(), content_type="image/png")
    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceArtifact.record(
            run=run_x, kind="screenshot", stored=stored(), content_type="image/png"
        )


def test_artifacts_are_append_only(run_x) -> None:
    art = EvidenceArtifact.record(run=run_x, kind="screenshot", stored=stored(), content_type="image/png")
    art.note = "diubah"
    with pytest.raises(AppendOnlyViolation):
        art.save()
    with pytest.raises(AppendOnlyViolation):
        art.delete()
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        EvidenceArtifact.objects.filter(pk=art.pk).update(sha256="0" * 64)
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        EvidenceArtifact.objects.filter(pk=art.pk)._raw_delete(EvidenceArtifact.objects.db)


def test_invalid_kind_is_rejected_by_the_database(run_x) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceArtifact.objects.create(
            run=run_x, kind="video-ai", relative_path="a.bin", sha256=SHA, size_bytes=1,
            content_type="x/y",
        )


def test_artifact_post_must_share_the_runs_platform(run_x, run_tt) -> None:
    tiktok_post = Post.objects.create(platform="tiktok", external_post_id="t1", first_seen_run=run_tt)
    x_post = Post.objects.create(platform="x", external_post_id="x1", first_seen_run=run_x)
    with pytest.raises(DatabaseError, match="platform lain"), transaction.atomic():
        EvidenceArtifact.record(
            run=run_x, kind="screenshot", stored=stored("p/x.png"), content_type="image/png",
            post=tiktok_post,
        )
    art = EvidenceArtifact.record(
        run=run_x, kind="screenshot", stored=stored("p/y.png"), content_type="image/png", post=x_post
    )
    assert art.post == x_post
