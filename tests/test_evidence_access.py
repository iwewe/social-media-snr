"""WP-3.6b: riwayat akses bukti (siapa membuka/memverifikasi, kapan, untuk apa, hasilnya)."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from evidence_helpers import artifact, make_run_with_artifacts, tamper
from investigations import services as inv_services
from investigations import team
from investigations.enums import Role

pytestmark = pytest.mark.django_db
PW = "Kata-sandi-uji-123!"


@pytest.fixture(autouse=True)
def _clean_registry():
    from collection.orchestrator import registry

    yield
    registry.clear()


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def post(c, path):
    return c.post(path, json.dumps({}), content_type="application/json")


@pytest.fixture
def world(settings, tmp_path):
    class W:
        pass

    w = W()
    w.owner = User.objects.create_user("pemilik", password=PW)
    w.viewer = User.objects.create_user("pembaca", password=PW)
    w.outsider = User.objects.create_user("luar", password=PW)
    w.run = make_run_with_artifacts(w.owner, settings, tmp_path)
    w.inv = w.run.target.investigation
    team.grant(investigation=w.inv, user=w.viewer, role=Role.VIEWER, added_by=w.owner)
    w.clients = {"owner": client_for(w.owner), "viewer": client_for(w.viewer)}
    w.url = f"/api/investigations/{w.inv.pk}/evidence-access/"
    return w


def listing(w, who="owner", status=200, **params):
    res = w.clients[who].get(w.url, params)
    assert res.status_code == status, res.content[:200]
    return res.json()


def test_downloads_and_verifications_are_listed_with_user_purpose_and_result(world) -> None:
    w = world
    shot = artifact(w.run, "screenshot")
    assert w.clients["viewer"].get(f"/api/artifacts/{shot.pk}/content/").status_code == 200
    assert post(w.clients["owner"], f"/api/artifacts/{shot.pk}/verify/").status_code == 200
    assert (
        post(w.clients["viewer"], f"/api/inspections/{w.run.pk}/verify-artifacts/").status_code
        == 200
    )
    data = listing(w)
    rows = data["results"]
    assert data["count"] == len(rows) == 5  # 1 unduh + 1 verifikasi + 3 artefak pada verifikasi run
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    purposes = {r["purpose"] for r in rows}
    assert purposes == {"download", "verify", "verify_run"}
    download = next(r for r in rows if r["purpose"] == "download")
    assert download["user"] == "pembaca" and download["result"] == "MATCH"
    assert download["artifact"] == {
        "id": shot.pk,
        "kind": "screenshot",
        "run_id": w.run.pk,
        "run_sequence": w.run.sequence,
    }
    assert download["purpose_label"] == "Unduh isi artefak"
    assert "hanya dapat bertambah" in data["notice"]


def test_filters_by_purpose_result_user_and_artifact(world) -> None:
    w = world
    shot, dom = artifact(w.run, "screenshot"), artifact(w.run, "dom_snapshot")
    post(w.clients["owner"], f"/api/artifacts/{shot.pk}/verify/")
    w.clients["viewer"].get(f"/api/artifacts/{dom.pk}/content/")
    tamper(dom, b"<html>diubah</html>")
    post(w.clients["owner"], f"/api/artifacts/{dom.pk}/verify/")
    assert {r["purpose"] for r in listing(w, purpose="download")["results"]} == {"download"}
    bad = listing(w, result="MISMATCH")["results"]
    assert len(bad) == 1 and bad[0]["artifact"]["id"] == dom.pk and bad[0]["user"] == "pemilik"
    assert bad[0]["result"] == "MISMATCH"
    assert {r["result"] for r in listing(w, purpose="download")["results"]} == {"MATCH"}
    assert {r["user"] for r in listing(w, user="pembaca")["results"]} == {"pembaca"}
    assert {r["artifact"]["id"] for r in listing(w, artifact=shot.pk)["results"]} == {shot.pk}
    listing(w, status=400, purpose="tidak-ada")


def test_pagination(world) -> None:
    w = world
    shot = artifact(w.run, "screenshot")
    for _ in range(3):
        post(w.clients["owner"], f"/api/artifacts/{shot.pk}/verify/")
    first = listing(w, page_size=2)
    assert first["count"] == 3 and len(first["results"]) == 2
    second = listing(w, page_size=2, page=2)["results"]
    assert len(second) == 1 and second[0]["id"] < first["results"][-1]["id"]


def test_access_to_another_investigation_is_not_listed_here(world, settings, tmp_path) -> None:
    w = world
    other_inv = inv_services.create_investigation(user=w.owner, name="Lain")
    assert listing(w, who="owner")["count"] == 0
    shot = artifact(w.run, "screenshot")
    post(w.clients["owner"], f"/api/artifacts/{shot.pk}/verify/")
    assert listing(w)["count"] == 1
    other = w.clients["owner"].get(f"/api/investigations/{other_inv.pk}/evidence-access/").json()
    assert other["count"] == 0


def test_outsider_gets_404_and_no_file_path_is_ever_exposed(world) -> None:
    w = world
    shot = artifact(w.run, "screenshot")
    post(w.clients["owner"], f"/api/artifacts/{shot.pk}/verify/")
    assert client_for(w.outsider).get(w.url).status_code == 404
    body = json.dumps(listing(w))
    assert shot.relative_path not in body and "relative_path" not in body and "sha256" not in body
