"""WP-1.10: verifikasi hash artefak (FR-040, NFR-02): dihitung ulang dari disk, jujur saat gagal."""

import json

import pytest
from collection.models import AppendOnlyViolation
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, connection, transaction
from evidence_helpers import DOM, SHOT, artifact, disk_path, make_run_with_artifacts, tamper
from preservation import verification as v
from preservation.models import ArtifactVerification, EvidenceArtifact, VerificationResult
from preservation.storage import write_new

pytestmark = pytest.mark.django_db
R = VerificationResult


@pytest.fixture(autouse=True)
def _clean_registry():
    from collection.orchestrator import registry

    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def run(user, settings, tmp_path):
    return make_run_with_artifacts(user, settings, tmp_path)


def result_of(a, user):
    return v.verify_artifact(a, user)


# --- hasil dasar ------------------------------------------------------------------------------


def test_untouched_artifacts_match_and_are_recorded(run, user) -> None:
    for kind in ("screenshot", "dom_snapshot", "manifest"):
        row = result_of(artifact(run, kind), user)
        assert row.result == R.MATCH and row.actual_sha256 == row.expected_sha256
        assert row.actual_size == row.expected_size and row.verified_by == user
    assert ArtifactVerification.objects.count() == 3


def test_stored_files_are_what_the_tests_expect(run) -> None:
    assert disk_path(artifact(run, "screenshot")).read_bytes() == SHOT
    assert disk_path(artifact(run, "dom_snapshot")).read_bytes() == DOM


def test_changed_content_with_same_size_is_a_mismatch(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    tamper(a, DOM.replace(b"Balasan", b"Balasen"))  # satu huruf berbeda, ukuran sama
    row = result_of(a, user)
    assert row.result == R.MISMATCH and row.actual_sha256 != row.expected_sha256
    assert row.actual_size == row.expected_size


def test_changed_size_is_a_mismatch(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    tamper(a, DOM + b"tambahan")
    row = result_of(a, user)
    assert row.result == R.MISMATCH and row.actual_size == row.expected_size + 8


def test_recorded_size_that_differs_from_the_file_is_a_mismatch_even_if_the_hash_matches(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    wrong = EvidenceArtifact(run=run, kind=a.kind, relative_path=a.relative_path, sha256=a.sha256,
                             size_bytes=a.size_bytes + 1, content_type=a.content_type)
    inspection = v.inspect_artifact(wrong)
    assert inspection.result == R.MISMATCH and inspection.actual_sha256 == a.sha256


def test_truncated_file_is_a_mismatch(run, user) -> None:
    a = artifact(run, "screenshot")
    tamper(a, b"")
    assert result_of(a, user).result == R.MISMATCH


def test_deleted_file_is_missing_not_a_match(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    disk_path(a).unlink()
    row = result_of(a, user)
    assert row.result == R.MISSING and row.actual_sha256 is None and row.actual_size is None


def test_symlink_in_place_of_the_file_is_unreadable_even_if_content_is_identical(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    copy = path.parent / "salinan-identik.html"
    copy.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(copy)
    assert result_of(a, user).result == R.UNREADABLE


def test_symlinked_directory_component_is_unreadable(run, user, tmp_path, settings) -> None:
    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    folder = path.parent
    moved = tmp_path / "dipindah"
    folder.rename(moved)
    folder.symlink_to(moved)
    assert result_of(a, user).result == R.UNREADABLE


def test_directory_in_place_of_the_file_is_unreadable(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    path.unlink()
    path.mkdir()
    assert result_of(a, user).result == R.UNREADABLE


def test_fifo_in_place_of_the_file_is_unreadable_and_does_not_hang(run, user) -> None:
    import os

    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    path.unlink()
    os.mkfifo(path)
    assert result_of(a, user).result == R.UNREADABLE


def test_directory_failure_does_not_leak_file_descriptors(run, user) -> None:
    import os

    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    path.unlink()
    path.mkdir()
    before = len(os.listdir("/proc/self/fd"))
    for _ in range(20):
        result_of(a, user)
    assert len(os.listdir("/proc/self/fd")) <= before + 1


@pytest.mark.parametrize("bad_path", ["../luar.txt", "/etc/passwd", "a//b", "captures/../../x"])
def test_record_with_a_path_outside_the_evidence_root_is_unreadable(bad_path, run, user) -> None:
    ghost = EvidenceArtifact(run=run, kind="other", relative_path=bad_path, sha256="0" * 64,
                             size_bytes=1, content_type="text/plain")
    assert v.inspect_artifact(ghost).result == R.UNREADABLE


def test_browser_profile_area_is_never_read_as_evidence(run, user, settings) -> None:
    secret = settings.SNR_BROWSER_PROFILES_ROOT / "x" / "Cookies"
    secret.parent.mkdir(parents=True)
    secret.write_bytes(b"sesi-rahasia")
    ghost = EvidenceArtifact(run=run, kind="other", relative_path="../profiles/x/Cookies",
                             sha256="0" * 64, size_bytes=12, content_type="x/y")
    assert v.inspect_artifact(ghost).result == R.UNREADABLE


def test_uppercase_recorded_hash_still_matches(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    a.sha256 = a.sha256.upper()  # tidak disimpan; hanya perbandingan
    inspection = v.inspect_artifact(a)
    try:
        assert inspection.result == R.MATCH
    finally:
        inspection.close()


def test_handle_is_returned_only_on_match_at_position_zero(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    inspection = v.inspect_artifact(a)
    try:
        assert inspection.result == R.MATCH and inspection.handle is not None
        assert inspection.handle.read() == DOM
    finally:
        inspection.close()
    tamper(a, b"lain")
    bad = v.inspect_artifact(a)
    assert bad.result == R.MISMATCH and bad.handle is None


def test_verify_artifact_closes_its_file_handle(run, user) -> None:
    import gc
    import warnings

    a = artifact(run, "dom_snapshot")
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        v.verify_artifact(a, user)
        gc.collect()


# --- riwayat append-only ----------------------------------------------------------------------


def test_history_keeps_both_the_earlier_match_and_the_later_mismatch(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    assert result_of(a, user).result == R.MATCH
    tamper(a, b"diubah")
    assert result_of(a, user).result == R.MISMATCH
    tamper(a, DOM)  # dipulihkan: kejadian ketidakcocokan tetap tercatat
    assert result_of(a, user).result == R.MATCH
    assert list(a.verifications.order_by("id").values_list("result", flat=True)) == [
        "MATCH", "MISMATCH", "MATCH"]


def test_verification_rows_cannot_be_updated_or_deleted(run, user) -> None:
    row = result_of(artifact(run, "dom_snapshot"), user)
    row.result = "MISMATCH"
    with pytest.raises(AppendOnlyViolation):
        row.save()
    with pytest.raises(AppendOnlyViolation):
        row.delete()


def test_database_also_refuses_updates_and_deletes(run, user) -> None:
    row = result_of(artifact(run, "dom_snapshot"), user)
    for sql in ("UPDATE preservation_artifactverification SET result = 'MISSING' WHERE id = %s",
                "DELETE FROM preservation_artifactverification WHERE id = %s"):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [row.pk])


def test_database_rejects_a_match_whose_hashes_differ(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    with pytest.raises(IntegrityError), transaction.atomic():
        ArtifactVerification.objects.create(
            artifact=a, verified_by=user, purpose="verify", result="MATCH",
            expected_sha256=a.sha256, expected_size=a.size_bytes, actual_sha256="f" * 64,
            actual_size=a.size_bytes)


def test_database_rejects_unknown_results(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    with pytest.raises(IntegrityError), transaction.atomic():
        ArtifactVerification.objects.create(
            artifact=a, verified_by=user, purpose="verify", result="OKE",
            expected_sha256=a.sha256, expected_size=a.size_bytes)


def test_recorded_rows_never_contain_the_file_path(run, user) -> None:
    a = artifact(run, "dom_snapshot")
    result_of(a, user)
    names = {f.name for f in ArtifactVerification._meta.get_fields()}
    assert not any("path" in n for n in names)


# --- verifikasi satu run + manifest -----------------------------------------------------------


def test_verify_run_all_match_and_manifest_consistent(run, user) -> None:
    out = v.verify_run(run, user)
    assert out["all_match"] is True and out["summary"] == {"MATCH": 3}
    assert out["manifest"] == {"state": "CONSISTENT", "problems": []}
    assert {x.purpose for x in out["verifications"]} == {"verify_run"}


def test_verify_run_flags_one_tampered_artifact(run, user) -> None:
    tamper(artifact(run, "screenshot"), b"palsu")
    out = v.verify_run(run, user)
    assert out["all_match"] is False and out["summary"] == {"MATCH": 2, "MISMATCH": 1}


def test_tampered_manifest_is_untrusted_and_not_used_as_reference(run, user) -> None:
    tamper(artifact(run, "manifest"), b'{"artifacts": []}')
    out = v.verify_run(run, user)
    assert out["manifest"]["state"] == "UNTRUSTED" and out["all_match"] is False
    assert out["summary"]["MISMATCH"] == 1


def add_manifest(run, body: bytes, name="manifest-baru.json"):
    stored = write_new(f"manifests/{run.run_id}/{name}", [body])
    return EvidenceArtifact.record(run=run, kind="manifest", stored=stored,
                                   content_type="application/json")


def real_manifest(run) -> dict:
    return json.loads(disk_path(artifact(run, "manifest")).read_text())


def test_manifest_with_a_different_hash_is_inconsistent(run, user) -> None:
    m = real_manifest(run)
    m["artifacts"][0]["sha256"] = "0" * 64
    add_manifest(run, json.dumps(m).encode())
    out = v.verify_run(run, user)
    assert out["manifest"]["state"] == "INCONSISTENT"
    assert any("berbeda dari manifest" in p for p in out["manifest"]["problems"])
    assert out["all_match"] is False


def test_manifest_missing_an_artifact_is_inconsistent(run, user) -> None:
    m = real_manifest(run)
    m["artifacts"] = m["artifacts"][:1]
    add_manifest(run, json.dumps(m).encode())
    out = v.verify_run(run, user)
    assert any("tidak tercantum di manifest" in p for p in out["manifest"]["problems"])


def test_manifest_listing_an_unknown_artifact_is_inconsistent(run, user) -> None:
    m = real_manifest(run)
    m["artifacts"].append({**m["artifacts"][0], "relative_path": "captures/lain.bin"})
    add_manifest(run, json.dumps(m).encode())
    out = v.verify_run(run, user)
    assert any("tidak ada di basis data" in p for p in out["manifest"]["problems"])


def test_manifest_for_another_run_is_inconsistent(run, user) -> None:
    m = real_manifest(run)
    m["inspection_run_id"] = "bukan-run-ini"
    add_manifest(run, json.dumps(m).encode())
    assert any("run yang berbeda" in p for p in v.verify_run(run, user)["manifest"]["problems"])


def test_manifest_that_is_not_json_is_inconsistent(run, user) -> None:
    add_manifest(run, b"bukan json")
    assert v.verify_run(run, user)["manifest"]["state"] == "INCONSISTENT"


def test_a_newer_manifest_is_the_one_compared(run, user) -> None:
    m = real_manifest(run)
    add_manifest(run, json.dumps(m).encode(), "manifest-salinan.json")  # isi sama: tetap konsisten
    assert v.verify_run(run, user)["manifest"]["state"] == "CONSISTENT"


def test_run_without_artifacts_has_nothing_to_verify(user, settings, tmp_path) -> None:
    from collection.orchestrator import request_inspection, run_inspection
    from collection_helpers import register
    from investigations import services as inv_services
    from investigations.enums import Platform

    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    (tmp_path / "evidence").mkdir()
    inv = inv_services.create_investigation(user=user, name="Kosong")
    run = request_inspection(target=register(inv, user, Platform.X, "https://x.com/u/status/9"),
                             user=user, enqueue=False)
    run_inspection(run.pk)
    run.refresh_from_db()
    out = v.verify_run(run, user)
    assert out["verifications"] == [] and out["all_match"] is False
    assert out["manifest"]["state"] in ("ABSENT", "CONSISTENT")


# --- fungsi lama (WP-1.5a) kini memakai pemeriksa yang sama --------------------------------------


def test_legacy_run_check_uses_the_same_inspector(run) -> None:
    from preservation.service import verify_run_artifacts

    assert verify_run_artifacts(run) == []
    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    copy = path.parent / "identik.html"
    copy.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(copy)  # isi identik, tetapi jalurnya dibelokkan
    problems = verify_run_artifacts(run)
    assert [p["problem"] for p in problems] == ["jalur tidak sah"]
    tamper(artifact(run, "screenshot"), b"palsu")
    labels = sorted(p["problem"] for p in verify_run_artifacts(run))
    assert labels == ["hash tidak cocok", "jalur tidak sah"]


def test_legacy_run_check_does_not_hang_on_a_fifo(run) -> None:
    import os

    from preservation.service import verify_run_artifacts

    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    path.unlink()
    os.mkfifo(path)
    assert [p["problem"] for p in verify_run_artifacts(run)] == ["jalur tidak sah"]
