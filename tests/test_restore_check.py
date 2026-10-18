"""WP-3.6: pemeriksaan hasil restore (NFR-10): jujur saat ada yang hilang, berubah, atau berbeda."""

import json
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from evidence_helpers import artifact, disk_path, make_run_with_artifacts, tamper
from investigations import services as inv_services
from preservation import restore_check as rc
from preservation.models import EvidenceArtifact

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_registry():
    from collection.orchestrator import registry

    yield
    registry.clear()


@pytest.fixture
def world(settings, tmp_path):
    user = User.objects.create_user("analis", password="x")
    run = make_run_with_artifacts(user, settings, tmp_path)
    return user, run


def test_snapshot_counts_domain_models_and_artifacts(world) -> None:
    snap = rc.snapshot()
    assert snap["format"] == 1
    assert snap["counts"]["investigations.Investigation"] == 1
    assert snap["counts"]["preservation.EvidenceArtifact"] == 3
    assert snap["counts"]["auth.User"] == 1
    assert snap["counts"]["audit.AuditEvent"] >= 1  # pendaftaran target tercatat di audit
    assert snap["artifacts"]["count"] == 3 and snap["artifacts"]["total_bytes"] > 0
    assert "sessions.Session" not in snap["counts"]  # bukan data domain


def test_an_untouched_system_verifies_against_its_own_snapshot(world) -> None:
    result = rc.verify(rc.snapshot())
    assert result["ok"] and result["problems"] == [] and result["artifacts_checked"] == 3


def test_a_tampered_evidence_file_fails_the_check(world) -> None:
    _, run = world
    snap = rc.snapshot()
    tamper(artifact(run, "dom_snapshot"), b"<html>diubah</html>")
    result = rc.verify(snap)
    assert not result["ok"]
    assert any("hash tidak cocok" in p for p in result["problems"])


def test_a_missing_evidence_file_fails_the_check(world) -> None:
    _, run = world
    snap = rc.snapshot()
    art = artifact(run, "screenshot")
    path = disk_path(art)
    path.chmod(0o600)
    path.unlink()
    result = rc.verify(snap)
    assert not result["ok"]
    assert any("berkas hilang" in p and art.relative_path in p for p in result["problems"])


def test_different_row_counts_fail_the_check(world) -> None:
    user, _ = world
    snap = rc.snapshot()
    inv_services.create_investigation(user=user, name="Baru setelah snapshot")
    result = rc.verify(snap)
    assert not result["ok"]
    assert any("investigations.Investigation" in p for p in result["problems"])


def test_a_different_artifact_catalog_fails_even_if_counts_match(world) -> None:
    snap = rc.snapshot()
    snap["artifacts"]["catalog_sha256"] = "0" * 64
    result = rc.verify(snap)
    assert not result["ok"] and any("katalog artefak" in p for p in result["problems"])


def test_unknown_snapshot_format_is_rejected(world) -> None:
    result = rc.verify({"format": 99, "counts": {}, "artifacts": {}})
    assert not result["ok"] and "format snapshot" in result["problems"][0]


def test_orphan_files_are_a_warning_not_a_failure(world, settings) -> None:
    snap = rc.snapshot()
    (settings.SNR_EVIDENCE_ROOT / "liar.bin").write_bytes(b"tidak tercatat")
    result = rc.verify(snap)
    assert result["ok"]
    assert any("tidak tercatat" in w for w in result["warnings"])


def test_command_writes_a_snapshot_and_verifies_it(world, tmp_path) -> None:
    out = tmp_path / "snap.json"
    buf = StringIO()
    call_command("restore_check", "snapshot", "--out", str(out), stdout=buf)
    assert json.loads(out.read_text())["artifacts"]["count"] == 3
    call_command("restore_check", "verify", "--expect", str(out), stdout=buf)
    assert "restore lolos: 3 artefak cocok" in buf.getvalue()


def test_command_exits_with_an_error_when_the_restore_is_not_faithful(world, tmp_path) -> None:
    _, run = world
    out = tmp_path / "snap.json"
    call_command("restore_check", "snapshot", "--out", str(out), stdout=StringIO())
    tamper(artifact(run, "dom_snapshot"), b"x")
    err = StringIO()
    with pytest.raises(CommandError, match="restore tidak lolos"):
        call_command("restore_check", "verify", "--expect", str(out), stdout=StringIO(), stderr=err)
    assert "MASALAH:" in err.getvalue()
    assert EvidenceArtifact.objects.count() == 3


ROWS = [("a/1.html", "a" * 64, 10), ("b/2.png", "b" * 64, 20)]


def test_catalog_digest_depends_on_path_hash_and_size_but_not_on_order() -> None:
    base, n, total = rc.catalog_digest(ROWS)
    assert (n, total) == (2, 30)
    assert rc.catalog_digest(reversed(ROWS))[0] == base
    changed_path = [("a/x.html", "a" * 64, 10), ROWS[1]]
    changed_hash = [("a/1.html", "c" * 64, 10), ROWS[1]]
    changed_size = [("a/1.html", "a" * 64, 11), ROWS[1]]
    for rows in (changed_path, changed_hash, changed_size, ROWS[:1]):
        assert rc.catalog_digest(rows)[0] != base


def test_a_model_missing_on_either_side_is_reported(world) -> None:
    snap = rc.snapshot()
    extra = json.loads(json.dumps(snap))
    extra["counts"]["intelligence.Ghost"] = 5  # ada di sumber, tidak ada di hasil restore
    only_source = rc.verify(extra)
    assert not only_source["ok"] and any("intelligence.Ghost" in p for p in only_source["problems"])
    fewer = json.loads(json.dumps(snap))
    del fewer["counts"]["audit.AuditEvent"]  # ada di hasil restore, tidak ada di sumber
    only_result = rc.verify(fewer)
    assert not only_result["ok"] and any("audit.AuditEvent" in p for p in only_result["problems"])


def test_command_prints_orphan_warnings_even_when_the_restore_passes(world, tmp_path, settings) -> None:
    out = tmp_path / "snap.json"
    call_command("restore_check", "snapshot", "--out", str(out), stdout=StringIO())
    (settings.SNR_EVIDENCE_ROOT / "liar.bin").write_bytes(b"x")
    buf = StringIO()
    call_command("restore_check", "verify", "--expect", str(out), stdout=buf)
    assert "PERINGATAN:" in buf.getvalue() and "restore lolos" in buf.getvalue()
