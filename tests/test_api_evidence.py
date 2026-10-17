"""WP-1.10: API verifikasi dan akses isi artefak (FR-040): terautentikasi, hash menjaga, aman."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from evidence_helpers import DOM, SHOT, artifact, disk_path, make_run_with_artifacts, tamper
from preservation.models import ArtifactVerification, EvidenceArtifact
from preservation.storage import write_new

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_registry():
    from collection.orchestrator import registry

    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def api(user) -> Client:
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def run(user, settings, tmp_path):
    return make_run_with_artifacts(user, settings, tmp_path)


def post(c, path):
    return c.post(path, {}, content_type="application/json")


# --- akses ------------------------------------------------------------------------------------


@pytest.mark.parametrize("method,path", [
    ("post", "/api/artifacts/1/verify/"), ("get", "/api/artifacts/1/content/"),
    ("post", "/api/inspections/1/verify-artifacts/"),
])
def test_anonymous_gets_401_and_no_file_access(method, path) -> None:
    res = getattr(Client(), method)(path)
    assert res.status_code in (401, 403) and res.json()["detail"]


def test_unknown_ids_are_404(api) -> None:
    assert post(api, "/api/artifacts/9999/verify/").status_code == 404
    assert api.get("/api/artifacts/9999/content/").status_code == 404
    assert post(api, "/api/inspections/9999/verify-artifacts/").status_code == 404


def test_verification_endpoints_reject_get_and_content_rejects_post(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    assert api.get(f"/api/artifacts/{a.pk}/verify/").status_code == 405
    assert post(api, f"/api/artifacts/{a.pk}/content/").status_code == 405


# --- verifikasi -------------------------------------------------------------------------------


def test_verify_match_reports_hashes_message_and_the_integrity_statement(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    body = post(api, f"/api/artifacts/{a.pk}/verify/").json()
    assert body["result"] == "MATCH" and body["actual_sha256"] == body["expected_sha256"] == a.sha256
    assert body["verified_by"] == "analis" and body["purpose"] == "verify"
    assert body["message"]["code"] == "verification_match" and body["message"]["level"] == "info"
    assert "tidak membuktikan" in body["statement"] and "autentik" in body["statement"]
    # Nilai jalur (bukan hanya nama kunci) tidak boleh muncul di respons mana pun.
    assert a.relative_path not in json.dumps(body) and "captures/" not in json.dumps(body)


def test_verify_tampered_file_is_200_with_an_error_verdict(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    tamper(a, b"diubah")
    res = post(api, f"/api/artifacts/{a.pk}/verify/")
    body = res.json()
    assert res.status_code == 200  # pemeriksaan berhasil menghasilkan putusan
    assert body["result"] == "MISMATCH" and body["message"]["level"] == "error"
    assert body["actual_sha256"] != body["expected_sha256"]


def test_verify_deleted_file(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    disk_path(a).unlink()
    body = post(api, f"/api/artifacts/{a.pk}/verify/").json()
    assert body["result"] == "MISSING" and body["actual_sha256"] is None
    assert body["message"]["code"] == "verification_missing"


def test_verify_run_returns_every_artifact_and_the_manifest_state(api, run) -> None:
    body = post(api, f"/api/inspections/{run.pk}/verify-artifacts/").json()
    assert body["all_match"] is True and body["summary"] == {"MATCH": 3}
    assert len(body["verifications"]) == 3
    assert body["manifest"]["state"] == "CONSISTENT"
    assert body["manifest"]["message"]["code"] == "manifest_consistent"
    assert "tidak membuktikan" in body["statement"]
    paths = [a.relative_path for a in EvidenceArtifact.objects.filter(run=run)]
    assert not any(path in json.dumps(body) for path in paths)
    assert "manifests/" not in json.dumps(body) and "captures/" not in json.dumps(body)


def test_verify_run_reports_a_tampered_artifact(api, run) -> None:
    tamper(artifact(run, "screenshot"), b"palsu")
    body = post(api, f"/api/inspections/{run.pk}/verify-artifacts/").json()
    assert body["all_match"] is False and body["summary"] == {"MATCH": 2, "MISMATCH": 1}


def test_run_detail_shows_the_last_verification_per_artifact(api, run) -> None:
    before = api.get(f"/api/inspections/{run.pk}/").json()["artifacts"]
    assert {a["last_verification"] for a in map(lambda x: {**x, "last_verification": None}, before)} == {None}
    assert all(a["last_verification"] is None for a in before)
    post(api, f"/api/inspections/{run.pk}/verify-artifacts/")
    after = api.get(f"/api/inspections/{run.pk}/").json()["artifacts"]
    assert all(a["last_verification"]["result"] == "MATCH" for a in after)
    assert after[0]["last_verification"]["verified_by"] == "analis"
    assert "relative_path" not in json.dumps(after)
    assert not any(a.relative_path in json.dumps(after) for a in EvidenceArtifact.objects.filter(run=run))


def test_every_verification_is_recorded_per_user(api, run, user) -> None:
    from investigations import team

    other = User.objects.create_user("peninjau", password="x")
    team.grant(investigation=run.target.investigation, user=other, role="VIEWER", added_by=user)
    c2 = Client()
    c2.force_login(other)
    a = artifact(run, "dom_snapshot")
    post(api, f"/api/artifacts/{a.pk}/verify/")
    post(c2, f"/api/artifacts/{a.pk}/verify/")
    assert list(a.verifications.order_by("id").values_list("verified_by__username", flat=True)) == [
        "analis", "peninjau"]


# --- isi artefak ------------------------------------------------------------------------------

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def body_of(res) -> bytes:
    return b"".join(res.streaming_content)


def test_screenshot_is_served_inline_with_protective_headers(api, run) -> None:
    a = artifact(run, "screenshot")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 200 and body_of(res) == SHOT
    assert res["Content-Type"] == "image/png" and res["Content-Disposition"].startswith("inline")
    for key, value in HEADERS.items():
        assert res[key] == value
    assert "sandbox" in res["Content-Security-Policy"] and "default-src 'none'" in res["Content-Security-Policy"]


def test_dom_snapshot_is_always_an_attachment_never_rendered(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 200 and body_of(res) == DOM
    assert res["Content-Type"] == "application/octet-stream"
    assert res["Content-Disposition"].startswith("attachment")
    assert f"snr-dom_snapshot-{a.pk}.html" in res["Content-Disposition"]
    assert res["X-Content-Type-Options"] == "nosniff"


def test_manifest_is_an_attachment(api, run) -> None:
    a = artifact(run, "manifest")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res["Content-Disposition"].startswith("attachment")
    assert json.loads(body_of(res))["inspection_run_id"] == run.run_id


def add_record(run, kind, content_type, body, name):
    stored = write_new(f"captures/{run.run_id}/{name}", [body])
    return EvidenceArtifact.record(run=run, kind=kind, stored=stored, content_type=content_type)


@pytest.mark.parametrize("content_type", ["text/html", "image/svg+xml", "application/javascript",
                                          "text/html; charset=utf-8"])
def test_a_screenshot_with_a_dangerous_declared_type_is_not_rendered_inline(api, run, content_type) -> None:
    a = add_record(run, "screenshot", content_type, b"<script>alert(1)</script>", "x.bin")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 200
    assert res["Content-Disposition"].startswith("attachment")
    assert res["Content-Type"] == "application/octet-stream"


def test_image_type_with_parameters_is_still_inline(api, run) -> None:
    a = add_record(run, "screenshot", "image/png; charset=binary", SHOT, "p.png")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res["Content-Type"] == "image/png" and res["Content-Disposition"].startswith("inline")


def test_non_screenshot_kinds_are_never_inline_even_if_image(api, run) -> None:
    a = add_record(run, "media", "image/png", SHOT, "m.png")
    assert api.get(f"/api/artifacts/{a.pk}/content/")["Content-Disposition"].startswith("attachment")


def test_download_filename_never_uses_stored_names(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    disposition = api.get(f"/api/artifacts/{a.pk}/content/")["Content-Disposition"]
    assert a.relative_path.split("/")[-1] not in disposition


def test_tampered_artifact_is_refused_with_409_and_its_bytes_are_not_sent(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    tamper(a, b"ISI-TERUBAH-JANGAN-DISAJIKAN")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 409 and res.json()["code"] == "artifact_integrity_failed"
    assert b"ISI-TERUBAH" not in res.content
    assert res.json()["verification"]["result"] == "MISMATCH"


def test_missing_artifact_is_refused(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    disk_path(a).unlink()
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 409 and res.json()["verification"]["result"] == "MISSING"


def test_downloads_are_recorded_including_refusals(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    api.get(f"/api/artifacts/{a.pk}/content/")
    tamper(a, b"x")
    api.get(f"/api/artifacts/{a.pk}/content/")
    rows = list(ArtifactVerification.objects.filter(artifact=a).order_by("id"))
    assert [(r.purpose, r.result) for r in rows] == [("download", "MATCH"), ("download", "MISMATCH")]


def test_file_resembling_a_secret_is_never_served_even_with_a_matching_hash(api, run) -> None:
    stored = write_new(f"captures/{run.run_id}/cookies.json", [b'{"sesi": "rahasia"}'])
    a = EvidenceArtifact.record(run=run, kind="other", stored=stored, content_type="application/json")
    res = api.get(f"/api/artifacts/{a.pk}/content/")
    assert res.status_code == 409 and b"rahasia" not in res.content


def test_symlinked_artifact_is_not_served(api, run) -> None:
    a = artifact(run, "dom_snapshot")
    path = disk_path(a)
    copy = path.parent / "identik.html"
    copy.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(copy)
    assert api.get(f"/api/artifacts/{a.pk}/content/").status_code == 409
