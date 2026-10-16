"""WP-1.5a: penyimpanan artefak, manifest, dan pemulihan (FR-037..FR-039, FR-042; AT-06; NFR-04)."""

import hashlib
import json
import threading
from pathlib import Path

import pytest
from collection import ingestion
from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    ContractViolation,
    Limitation,
    LimitationCode,
)
from collection.ingestion import ingest_result
from collection.models import InspectionRun
from collection.reconciliation import reconcile_run
from collection_helpers import ingest, make_result, new_run, obs, register, replies
from django.contrib.auth.models import User
from django.db import connections
from investigations import services as inv_services
from investigations.enums import Platform
from preservation import manifest as manifest_module
from preservation import storage
from preservation.models import EvidenceArtifact
from preservation.policy import PolicyDecision, UncheckedPolicy
from preservation.service import (
    ArtifactRejected,
    make_artifact_sink,
    persist_run_artifacts,
    verify_run_artifacts,
)
from preservation.storage import ArtifactTooLarge

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
HTML = b"<html><body>Perusahaan tidak perlu diaudit</body></html>"
POLICY = UncheckedPolicy()


@pytest.fixture
def evidence(settings, tmp_path: Path) -> Path:
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    return tmp_path / "evidence"


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def target(user):
    inv = inv_services.create_investigation(user=user, name="A")
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


@pytest.fixture
def run(target, user, evidence) -> InspectionRun:
    return new_run(target, user)


def shot(name="shot.png", data=PNG) -> ArtifactCapture:
    return ArtifactCapture(ArtifactKind.SCREENSHOT, name, data, "image/png")


def dom(name="halaman.html", data=HTML) -> ArtifactCapture:
    return ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, name, data, "text/html")


def files_under(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def prepared(run, artifacts, **kw):
    """Run dengan metadata hasil (coverage dll.) seperti setelah ingestion, tanpa menyimpan artefak."""
    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=artifacts, **kw)
    ingest_result(run, result)
    run.refresh_from_db()
    return result


# =============================== penyimpanan dan manifest ===============================


def test_artifacts_are_stored_by_kind_with_matching_hashes(run, evidence) -> None:
    result = prepared(run, [shot(), dom()])
    report = persist_run_artifacts(run, result, policy=POLICY)

    assert report.ok and report.stored == 3  # 2 artefak + manifest
    rid = run.run_id
    assert (evidence / "screenshots" / rid / "shot.png").read_bytes() == PNG
    assert (evidence / "captures" / rid / "halaman.html").read_bytes() == HTML
    rows = {a.relative_path: a for a in EvidenceArtifact.objects.filter(run=run)}
    assert rows[f"screenshots/{rid}/shot.png"].sha256 == hashlib.sha256(PNG).hexdigest()
    assert rows[f"captures/{rid}/halaman.html"].size_bytes == len(HTML)
    assert verify_run_artifacts(run) == []  # AT-06: hash berkas dan manifest valid


def test_stored_files_are_read_only_and_never_empty_placeholders(run, evidence) -> None:
    result = prepared(run, [shot(), dom()])
    persist_run_artifacts(run, result, policy=POLICY)
    for rel in files_under(evidence):
        assert storage.is_read_only(rel), rel
        assert (evidence / rel).stat().st_size > 0, rel


def test_manifest_contains_the_fields_required_by_the_prd(run, evidence) -> None:
    result = prepared(run, [shot(), dom()])
    report = persist_run_artifacts(run, result, policy=POLICY)
    manifest = json.loads((evidence / report.manifest_path).read_text())

    assert manifest["inspection_run_id"] == run.run_id
    assert manifest["target"]["source_url"] == "https://x.com/u/status/1"
    assert manifest["target"]["platform"] == "x"
    assert manifest["acquisition"]["source_method"] == "synthetic_fixture"
    assert manifest["acquisition"]["collector"] == {"name": "uji", "version": "0.1"}
    assert manifest["status"]["outcome"] == "COMPLETED"
    assert manifest["status"]["coverage"]["pagination_complete"] is True
    assert manifest["generated_at"] and manifest["generator"]["name"] == "snr.preservation"
    listed = {a["relative_path"]: a for a in manifest["artifacts"]}
    assert set(listed) == {
        f"screenshots/{run.run_id}/shot.png", f"captures/{run.run_id}/halaman.html"
    }
    for entry in listed.values():
        assert len(entry["sha256"]) == 64 and entry["size_bytes"] > 0 and entry["stored_at"]
        assert entry["content_type"]
    assert manifest["unavailable"] == []


def test_manifest_is_itself_recorded_and_hashed(run, evidence) -> None:
    result = prepared(run, [shot()])
    report = persist_run_artifacts(run, result, policy=POLICY)
    row = EvidenceArtifact.objects.get(kind="manifest")
    assert row.relative_path == report.manifest_path
    body = (evidence / row.relative_path).read_bytes()
    assert hashlib.sha256(body).hexdigest() == row.sha256
    assert row.relative_path.startswith(f"manifests/{run.run_id}/manifest-")


def test_manifest_lists_only_artifacts_that_are_really_stored(run, evidence) -> None:
    class RejectDom:
        def check(self, capture):
            if capture.kind is ArtifactKind.DOM_SNAPSHOT:
                return PolicyDecision(False, "tes", "ditolak")
            return PolicyDecision(True)

    result = prepared(run, [shot(), dom()])
    report = persist_run_artifacts(run, result, policy=RejectDom())
    manifest = json.loads((evidence / report.manifest_path).read_text())
    assert [a["kind"] for a in manifest["artifacts"]] == ["screenshot"]
    assert [u["filename"] for u in manifest["unavailable"]] == ["halaman.html"]


def test_artifacts_of_different_runs_never_collide(target, user, evidence) -> None:
    run_a, run_b = new_run(target, user), new_run(target, user)
    for r, content in ((run_a, b"A" * 10), (run_b, b"B" * 10)):
        persist_run_artifacts(r, prepared(r, [shot("shot.png", content)]), policy=POLICY)
    assert (evidence / "screenshots" / run_a.run_id / "shot.png").read_bytes() == b"A" * 10
    assert (evidence / "screenshots" / run_b.run_id / "shot.png").read_bytes() == b"B" * 10


def test_streamed_artifact_is_stored_and_reproducible(run, evidence) -> None:
    calls = {"n": 0}
    blocks = [b"a" * 1_000_000, b"b" * 1_000_000, b"c" * 1000]

    def factory():
        calls["n"] += 1
        return iter(blocks)

    big = ArtifactCapture(ArtifactKind.MEDIA, "klip.mp4", None, "video/mp4", chunks=factory)
    result = prepared(run, [big])
    report = persist_run_artifacts(run, result, policy=POLICY)
    expected = hashlib.sha256(b"".join(blocks)).hexdigest()
    assert report.ok
    assert EvidenceArtifact.objects.get(kind="media").sha256 == expected
    again = persist_run_artifacts(run, result, policy=POLICY)  # pabrik dipanggil ulang
    assert again.already_stored == 2 and again.stored == 0
    assert calls["n"] >= 2


# =============================== idempoten dan konflik ===============================


def test_persisting_the_same_result_twice_adds_nothing(run, evidence) -> None:
    result = prepared(run, [shot(), dom()])
    first = persist_run_artifacts(run, result, policy=POLICY)
    files, rows = files_under(evidence), EvidenceArtifact.objects.count()
    second = persist_run_artifacts(run, result, policy=POLICY)

    assert second.ok and second.stored == 0 and second.already_stored == 3
    assert files_under(evidence) == files and EvidenceArtifact.objects.count() == rows
    assert second.manifest_path == first.manifest_path  # tidak ada manifest ganda
    assert EvidenceArtifact.objects.filter(kind="manifest").count() == 1


def test_same_path_with_different_content_is_a_conflict_not_an_overwrite(run, evidence) -> None:
    persist_run_artifacts(run, prepared(run, [shot("a.png", b"asli")]), policy=POLICY)
    changed = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=[shot("a.png", b"palsu")])
    report = persist_run_artifacts(run, changed, policy=POLICY)

    assert not report.ok and report.conflicts[0]["filename"] == "a.png"
    assert (evidence / "screenshots" / run.run_id / "a.png").read_bytes() == b"asli"
    assert verify_run_artifacts(run) == []
    state = InspectionRun.objects.get(pk=run.pk).preservation
    assert state["state"] == "FINISHED_WITH_PROBLEMS"


def test_orphan_file_with_same_content_is_adopted_after_a_crash(run, evidence) -> None:
    """Proses mati antara menulis berkas dan membuat baris DB."""
    rel = f"screenshots/{run.run_id}/shot.png"
    storage.write_new(rel, PNG)  # berkas ada, baris DB belum
    assert not EvidenceArtifact.objects.filter(relative_path=rel).exists()

    report = persist_run_artifacts(run, prepared(run, [shot()]), policy=POLICY)
    assert report.ok and report.adopted == 1
    assert EvidenceArtifact.objects.get(relative_path=rel).sha256 == hashlib.sha256(PNG).hexdigest()
    assert (evidence / rel).read_bytes() == PNG


def test_orphan_file_with_different_content_is_never_adopted_or_overwritten(run, evidence) -> None:
    rel = f"screenshots/{run.run_id}/shot.png"
    storage.write_new(rel, b"isi lain")
    report = persist_run_artifacts(run, prepared(run, [shot()]), policy=POLICY)
    assert not report.ok and report.conflicts
    assert (evidence / rel).read_bytes() == b"isi lain"
    assert not EvidenceArtifact.objects.filter(relative_path=rel).exists()


# =============================== kebijakan ===============================


def test_policy_is_a_required_argument(run) -> None:
    result = prepared(run, [shot()])
    with pytest.raises(TypeError):
        persist_run_artifacts(run, result)  # type: ignore[call-arg]


def test_rejected_artifact_is_recorded_not_stored_and_leaves_no_placeholder(run, evidence) -> None:
    class RejectCookies:
        def check(self, capture):
            if "cookies" in capture.filename:
                return PolicyDecision(False, "nama-berkas-rahasia", "nama berkas menyerupai cookies")
            return PolicyDecision(True)

    result = prepared(run, [shot(), dom("cookies.txt", b"sessionid=abc")])
    report = persist_run_artifacts(run, result, policy=RejectCookies())

    assert report.ok  # penolakan kebijakan bukan kegagalan
    assert report.rejected == [
        {"filename": "cookies.txt", "kind": "dom_snapshot", "rule": "nama-berkas-rahasia",
         "reason": "nama berkas menyerupai cookies"}
    ]
    assert not [f for f in files_under(evidence) if "cookies" in f]
    manifest = json.loads((evidence / report.manifest_path).read_text())
    entry = manifest["unavailable"][0]
    assert (entry["code"], entry["rule"]) == ("ARTIFACT_NOT_PERMITTED", "nama-berkas-rahasia")
    assert "sessionid" not in json.dumps(manifest)  # nilai tidak pernah masuk manifest
    state = InspectionRun.objects.get(pk=run.pk).preservation
    assert state["report"]["rejected"][0]["filename"] == "cookies.txt"


# =============================== kegagalan per artefak ===============================


def test_oversized_artifact_fails_alone_without_leaving_files(run, evidence) -> None:
    result = prepared(run, [shot("kecil.png", b"x" * 5), shot("besar.png", b"y" * 500)])
    report = persist_run_artifacts(run, result, policy=POLICY, max_bytes=100)

    assert not report.ok
    assert report.failed == [{"filename": "besar.png", "kind": "screenshot", "error": "ArtifactTooLarge"}]
    stored = files_under(evidence)
    assert any(p.endswith("kecil.png") for p in stored)
    assert not any("besar" in p or ".tmp-" in p for p in stored)  # tanpa berkas parsial/sementara
    manifest = json.loads((evidence / report.manifest_path).read_text())
    assert manifest["unavailable"][0]["code"] == "ARTIFACT_NOT_AVAILABLE"
    assert manifest["unavailable"][0]["reason"] == "ArtifactTooLarge"


def test_broken_source_stream_fails_alone_and_leaves_nothing(run, evidence) -> None:
    def broken():
        yield b"separuh"
        raise RuntimeError("koneksi sumber putus")

    bad = ArtifactCapture(ArtifactKind.MEDIA, "putus.mp4", None, "video/mp4", chunks=broken)
    result = prepared(run, [shot(), bad])
    report = persist_run_artifacts(run, result, policy=POLICY)

    assert not report.ok and report.failed[0]["filename"] == "putus.mp4"
    assert report.failed[0]["error"] == "RuntimeError"  # hanya jenis galat, bukan pesannya
    assert not any("putus" in p or ".tmp-" in p for p in files_under(evidence))
    assert EvidenceArtifact.objects.filter(kind="screenshot").exists()  # artefak lain tetap tersimpan


def test_storage_size_limit_is_exact(evidence) -> None:
    assert storage.write_new("a/ok.bin", b"x" * 100, max_bytes=100).size == 100
    with pytest.raises(ArtifactTooLarge):
        storage.write_new("a/lebih.bin", b"x" * 101, max_bytes=100)
    assert not [p for p in files_under(evidence) if "lebih" in p or ".tmp-" in p]
    # Dialirkan: batas ditegakkan di tengah aliran.
    with pytest.raises(ArtifactTooLarge):
        storage.write_new("a/aliran.bin", iter([b"x" * 60, b"x" * 60]), max_bytes=100)
    assert not [p for p in files_under(evidence) if "aliran" in p or ".tmp-" in p]


# =============================== keterbatasan dari adapter ===============================


def test_adapter_artifact_limitations_are_preserved_in_a_manifest(run, evidence) -> None:
    lims = [Limitation(LimitationCode.ARTIFACT_NOT_PERMITTED, "media tidak boleh disimpan")]
    result = prepared(run, [], limitations=lims)
    report = persist_run_artifacts(run, result, policy=POLICY)
    manifest = json.loads((evidence / report.manifest_path).read_text())
    assert manifest["artifacts"] == []
    assert manifest["adapter_limitations"] == [
        {"code": "ARTIFACT_NOT_PERMITTED", "message": "media tidak boleh disimpan"}
    ]


def test_nothing_is_written_when_there_is_nothing_to_preserve(run, evidence) -> None:
    report = persist_run_artifacts(run, prepared(run, []), policy=POLICY)
    assert report.received == 0 and report.manifest_path is None
    assert files_under(evidence) == []
    assert InspectionRun.objects.get(pk=run.pk).preservation is None


def test_result_for_another_run_or_platform_is_rejected_before_writing(
    run, target, user, evidence
) -> None:
    other = new_run(target, user)
    with pytest.raises(ArtifactRejected, match="inspection_run_id"):
        persist_run_artifacts(run, make_result(other, [obs(other)], displayed=1, artifacts=[shot()]),
                              policy=POLICY)
    assert files_under(evidence) == []


# =============================== terputus dan pemulihan ===============================


def test_interrupted_persistence_leaves_a_marker_and_can_be_completed(
    monkeypatch, run, evidence
) -> None:
    result = prepared(run, [shot(), dom()])

    def crash(*args, **kwargs):
        raise RuntimeError("proses dimatikan")

    monkeypatch.setattr(manifest_module, "build_manifest", crash)
    with pytest.raises(RuntimeError):
        persist_run_artifacts(run, result, policy=POLICY)
    assert InspectionRun.objects.get(pk=run.pk).preservation["state"] == "IN_PROGRESS"
    assert EvidenceArtifact.objects.filter(run=run).count() == 2  # artefak sudah tercatat, manifest belum
    monkeypatch.undo()

    report = persist_run_artifacts(run, result, policy=POLICY)  # kunci advisory sudah dilepas
    assert report.ok and report.already_stored == 2 and report.stored == 1
    assert InspectionRun.objects.get(pk=run.pk).preservation["state"] == "FINISHED"
    assert EvidenceArtifact.objects.filter(run=run).count() == 3


# =============================== verifikasi ===============================


def test_verification_detects_tampering_and_missing_files(run, evidence) -> None:
    result = prepared(run, [shot(), dom()])
    persist_run_artifacts(run, result, policy=POLICY)
    rid = run.run_id
    tampered = evidence / "screenshots" / rid / "shot.png"
    tampered.chmod(0o640)
    tampered.write_bytes(b"diubah")
    (evidence / "captures" / rid / "halaman.html").chmod(0o640)
    (evidence / "captures" / rid / "halaman.html").unlink()

    problems = {p["path"]: p["problem"] for p in verify_run_artifacts(run)}
    assert problems[f"screenshots/{rid}/shot.png"] == "hash tidak cocok"
    assert problems[f"captures/{rid}/halaman.html"] == "berkas hilang"
    assert len(problems) == 2  # manifest tetap utuh


# =============================== kontrak artefak ===============================


def test_adapters_cannot_produce_manifest_artifacts() -> None:
    with pytest.raises(ContractViolation, match="manifest"):
        ArtifactCapture(ArtifactKind.MANIFEST, "m.json", b"{}", "application/json")


def test_artifact_needs_exactly_one_of_content_or_chunks() -> None:
    with pytest.raises(ContractViolation, match="tepat satu"):
        ArtifactCapture(ArtifactKind.OTHER, "a", None, "x/y")
    with pytest.raises(ContractViolation, match="tepat satu"):
        ArtifactCapture(ArtifactKind.OTHER, "a", b"x", "x/y", chunks=lambda: [b"x"])


def test_iter_chunks_for_bytes_empty_and_factory() -> None:
    assert list(ArtifactCapture(ArtifactKind.OTHER, "a", b"abc", "x/y").iter_chunks()) == [b"abc"]
    assert list(ArtifactCapture(ArtifactKind.OTHER, "a", b"", "x/y").iter_chunks()) == []
    factory = ArtifactCapture(ArtifactKind.OTHER, "a", None, "x/y", chunks=lambda: iter([b"1", b"2"]))
    assert list(factory.iter_chunks()) == list(factory.iter_chunks()) == [b"1", b"2"]


# =============================== integrasi dengan ingestion ===============================


def test_ingestion_with_a_sink_stores_artifacts_and_clears_the_notice(run, evidence) -> None:
    result = make_result(run, replies(run, ["r1", "r2"]), displayed=2, artifacts=[shot(), dom()])
    report = ingest_result(run, result, artifact_sink=make_artifact_sink(POLICY))

    assert report.ok and report.artifacts["stored"] == 3
    assert "ARTIFACTS_NOT_PERSISTED" not in report.problem_codes()
    assert EvidenceArtifact.objects.filter(run=run).count() == 3
    run.refresh_from_db()
    assert run.ingestion["state"] == "FINISHED" and run.preservation["state"] == "FINISHED"


def test_ingestion_without_a_sink_never_drops_artifacts_silently(run, evidence) -> None:
    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=[shot()])
    report = ingest_result(run, result)
    assert "ARTIFACTS_NOT_PERSISTED" in report.problem_codes() and not report.ok
    assert files_under(evidence) == [] and not EvidenceArtifact.objects.exists()


def test_a_crashing_sink_does_not_break_ingestion(run, evidence) -> None:
    def boom(run, result):
        raise RuntimeError("disk penuh")

    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=[shot()])
    report = ingest_result(run, result, artifact_sink=boom)
    assert report.problem_codes() == {"ARTIFACT_PERSISTENCE_FAILED"}
    assert report.observations_created == 1  # observasi tetap tersimpan


def test_artifact_problems_are_reported_but_do_not_block_reconciliation(run, evidence) -> None:
    class RejectAll:
        def check(self, capture):
            return PolicyDecision(False, "tes", "ditolak")

    # Konflik jalur: berkas yatim berisi lain -> persistence bermasalah
    storage.write_new(f"screenshots/{run.run_id}/shot.png", b"isi lain")
    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=[shot()])
    report = ingest_result(run, result, artifact_sink=make_artifact_sink(POLICY))
    assert "ARTIFACT_PERSISTENCE_PROBLEMS" in report.problem_codes()
    assert reconcile_run(run).done  # kelengkapan observasi tidak terpengaruh artefak
    _ = RejectAll


# =============================== balapan ===============================


@pytest.mark.django_db(transaction=True)
def test_concurrent_persistence_of_one_run_stores_each_artifact_once(settings, tmp_path, user) -> None:
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    inv = inv_services.create_investigation(user=user, name="A")
    target = register(inv, user, Platform.X, "https://x.com/u/status/1")
    run = new_run(target, user)
    result = prepared(run, [shot(), dom()])
    reports, errors = [], []
    barrier = threading.Barrier(3)

    def worker() -> None:
        try:
            barrier.wait()
            reports.append(persist_run_artifacts(InspectionRun.objects.get(pk=run.pk), result, policy=POLICY))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not errors, errors
    assert all(r.ok for r in reports)
    assert sum(r.stored for r in reports) == 3  # 2 artefak + manifest, masing-masing tepat sekali
    assert EvidenceArtifact.objects.filter(run=run).count() == 3
    assert len([p for p in (tmp_path / "evidence").rglob("*") if p.is_file()]) == 3
    _ = ingest, replies
