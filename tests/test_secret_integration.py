"""WP-1.5b: penyaring rahasia terpasang pada penyimpanan artefak, ekspor, dan ingestion."""

import json
import logging
from pathlib import Path

import pytest
from collection.contracts import ArtifactCapture, ArtifactKind
from collection.ingestion import ingest_result
from collection.models import InspectionRun
from collection.reconciliation import reconcile_run
from collection_helpers import make_result, new_run, register, replies
from django.contrib.auth.models import User
from investigations import services as inv_services
from investigations.enums import Platform
from preservation import storage
from preservation.exports import ensure_exportable
from preservation.models import EvidenceArtifact
from preservation.policy import PolicyDecision, UncheckedPolicy
from preservation.secret_filter import SecretFilterPolicy
from preservation.service import (
    make_artifact_sink,
    persist_run_artifacts,
    verify_run_artifacts,
)
from preservation.storage import PathNotAllowed

pytestmark = pytest.mark.django_db

SESSION_VALUE = "a1b2c3d4e5f6g7h8i9"
COOKIE_LINE = f"Set-Cookie: sessionid={SESSION_VALUE}; Path=/; HttpOnly"
JWT = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiJ1c2VyMTIzIn0", "c2lnbmF0dXJl" + "MTIzNDU2"])
SECRETS = (SESSION_VALUE, JWT, "cookies.txt")
CLEAN_HTML = b"<html><body>Perusahaan tidak perlu diaudit. Kami memakai cookies.</body></html>"


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
def run(user, evidence) -> InspectionRun:
    inv = inv_services.create_investigation(user=user, name="A")
    target = register(inv, user, Platform.X, "https://x.com/u/status/1")
    return new_run(target, user)


def artifacts() -> list[ArtifactCapture]:
    return [
        ArtifactCapture(ArtifactKind.SCREENSHOT, "shot.png", b"\x89PNG\r\n" + b"\x00" * 32, "image/png"),
        ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, "halaman.html", CLEAN_HTML, "text/html"),
        ArtifactCapture(ArtifactKind.OTHER, "cookies.txt", f"sessionid={SESSION_VALUE}".encode(), "text/plain"),
        ArtifactCapture(ArtifactKind.RAW_RESPONSE, "respons.txt", f"HTTP/1.1 200 OK\r\n{COOKIE_LINE}\r\n".encode(), "text/plain"),
        ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, "token.html", f"<script>t='{JWT}'</script>".encode(), "text/html"),
    ]


def files_under(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def prepared(run, caps):
    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=caps)
    ingest_result(run, result)
    run.refresh_from_db()
    return result


def everything_stored_as_text(run, evidence: Path, report) -> str:
    """Seluruh jejak yang mungkin bocor: berkas di disk, baris DB, status run, laporan."""
    parts = [str(report.to_dict())]
    parts += [(evidence / f).read_text(errors="replace") for f in files_under(evidence)]
    parts += [f"{a.relative_path} {a.note} {a.content_type}" for a in EvidenceArtifact.objects.all()]
    fresh = InspectionRun.objects.get(pk=run.pk)
    parts += [json.dumps(fresh.preservation), json.dumps(fresh.ingestion), json.dumps(fresh.limitations)]
    return "\n".join(parts)


# =============================== penyaring pada penyimpanan ===============================


def test_secret_artifacts_are_rejected_and_clean_ones_are_stored(run, evidence) -> None:
    result = prepared(run, artifacts())
    report = persist_run_artifacts(run, result, policy=SecretFilterPolicy())

    assert report.ok
    assert {r["filename"] for r in report.rejected} == {"cookies.txt", "respons.txt", "token.html"}
    stored = files_under(evidence)
    assert any(f.endswith("shot.png") for f in stored) and any(f.endswith("halaman.html") for f in stored)
    for rejected in ("cookies.txt", "respons.txt", "token.html"):
        assert not any(rejected in f for f in stored), rejected
    assert verify_run_artifacts(run) == []


def test_no_secret_value_reaches_disk_database_report_or_logs(run, evidence, caplog) -> None:
    result = prepared(run, artifacts())
    with caplog.at_level(logging.DEBUG):
        report = persist_run_artifacts(run, result, policy=SecretFilterPolicy())
    blob = everything_stored_as_text(run, evidence, report) + caplog.text
    for secret in (SESSION_VALUE, JWT):
        assert secret not in blob, "nilai rahasia bocor"
    manifest = json.loads((evidence / report.manifest_path).read_text())
    rules = {u["rule"] for u in manifest["unavailable"]}
    assert rules == {"name:cookies", "content:cookie-header", "content:jwt"}
    assert all(u["code"] == "ARTIFACT_NOT_PERMITTED" for u in manifest["unavailable"])


def test_the_manifest_itself_passes_the_secret_filter(run, evidence) -> None:
    result = prepared(run, artifacts())
    report = persist_run_artifacts(run, result, policy=SecretFilterPolicy())
    body = (evidence / report.manifest_path).read_bytes()
    manifest_as_dom = ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, "m.json", body, "application/json")
    assert SecretFilterPolicy().check(manifest_as_dom).allowed


def test_rejections_are_stable_across_repeated_persistence(run, evidence) -> None:
    result = prepared(run, artifacts())
    first = persist_run_artifacts(run, result, policy=SecretFilterPolicy())
    files = files_under(evidence)
    second = persist_run_artifacts(run, result, policy=SecretFilterPolicy())
    assert files_under(evidence) == files and second.manifest_path == first.manifest_path
    assert second.rejected == first.rejected


# =============================== sink bawaan ===============================


def test_default_sink_uses_the_secret_filter(run, evidence) -> None:
    result = prepared(run, artifacts())
    report = make_artifact_sink()(run, result)
    assert {r["rule"] for r in report.rejected} == {"name:cookies", "content:cookie-header", "content:jwt"}


def test_ingestion_with_the_default_sink_reports_ok_despite_rejections(run, evidence) -> None:
    result = make_result(run, replies(run, ["r1"]), displayed=1, artifacts=artifacts())
    report = ingest_result(run, result, artifact_sink=make_artifact_sink())
    assert report.ok  # penolakan adalah hasil yang diharapkan, bukan kegagalan
    assert len(report.artifacts["rejected"]) == 3
    assert reconcile_run(run).done


def test_unchecked_policy_remains_available_only_when_passed_explicitly(run, evidence) -> None:
    result = prepared(run, artifacts())
    report = make_artifact_sink(UncheckedPolicy())(run, result)
    assert report.rejected == []  # tidak aman: terbukti hanya jika dipilih eksplisit


# =============================== gagal tertutup pada layanan ===============================


def test_a_crashing_policy_rejects_the_artifact_instead_of_storing_it(run, evidence) -> None:
    class Crashing:
        def check(self, capture):
            if capture.filename == "halaman.html":
                raise RuntimeError("bug pada kebijakan")
            return PolicyDecision(True)

    caps = [artifacts()[0], artifacts()[1]]
    report = persist_run_artifacts(run, prepared(run, caps), policy=Crashing())

    assert [r["rule"] for r in report.rejected] == ["policy-error"]
    assert not any("halaman" in f for f in files_under(evidence))  # tidak disimpan
    assert any("shot.png" in f for f in files_under(evidence))  # yang lain tetap diproses
    assert report.ok


# =============================== ekspor ===============================


def test_export_refuses_secret_looking_files_even_inside_the_evidence_root(evidence) -> None:
    planted = evidence / "captures" / "run-x" / "cookies.txt"
    planted.parent.mkdir(parents=True)
    planted.write_text("sessionid=abc")
    with pytest.raises(PathNotAllowed, match="menyerupai rahasia"):
        ensure_exportable(planted)

    fine = evidence / "captures" / "run-x" / "halaman.html"
    fine.write_text("<p>halo</p>")
    assert ensure_exportable(fine) == fine.resolve()


def test_secret_named_file_cannot_be_exported_but_storage_rules_still_hold(evidence) -> None:
    storage.write_new("captures/run-y/har-export.har", b"{}")  # storage netral terhadap isi
    with pytest.raises(PathNotAllowed):
        ensure_exportable(evidence / "captures" / "run-y" / "har-export.har")
