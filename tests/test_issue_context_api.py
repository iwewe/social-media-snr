"""FR-014: konteks isu dapat direvisi lewat API; versi lama tetap tersimpan dan tercatat di audit."""

import json

import pytest
from audit.models import AuditAction, AuditEvent
from django.contrib.auth.models import User
from django.test import Client
from investigations import services as inv_services
from investigations import team
from investigations.enums import Role

pytestmark = pytest.mark.django_db
PW = "Kata-sandi-uji-123!"


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def post(c, path, data):
    return c.post(path, json.dumps(data), content_type="application/json")


@pytest.fixture
def world():
    class W:
        pass

    w = W()
    w.owner = User.objects.create_user("pemilik", password=PW)
    w.member = User.objects.create_user("anggota", password=PW)
    w.viewer = User.objects.create_user("pembaca", password=PW)
    w.outsider = User.objects.create_user("luar", password=PW)
    w.inv = inv_services.create_investigation(user=w.owner, name="Uji")
    for user, role in ((w.member, Role.MEMBER), (w.viewer, Role.VIEWER)):
        team.grant(investigation=w.inv, user=user, role=role, added_by=w.owner)
    w.issue = inv_services.create_issue(
        investigation=w.inv, user=w.owner, title="Isu", definition="Definisi awal."
    )
    w.clients = {n: client_for(getattr(w, n)) for n in ("owner", "member", "viewer", "outsider")}
    w.url = f"/api/issues/{w.issue.pk}/context-versions/"
    return w


def detail_issue(w):
    res = w.clients["owner"].get(f"/api/investigations/{w.inv.pk}/")
    assert res.status_code == 200
    return next(i for i in res.json()["issues"] if i["id"] == w.issue.pk)


def test_member_revises_the_context_and_history_keeps_every_version_newest_first(world) -> None:
    res = post(world.clients["member"], world.url, {"definition": "Definisi kedua."})
    assert res.status_code == 201, res.content[:200]
    body = res.json()
    assert body["context"] == {"version": 2, "definition": "Definisi kedua."}
    history = body["context_history"]
    assert [h["version"] for h in history] == [2, 1]
    assert [h["definition"] for h in history] == ["Definisi kedua.", "Definisi awal."]
    assert history[0]["created_by"] == "anggota" and history[1]["created_by"] == "pemilik"
    post(world.clients["owner"], world.url, {"definition": "Definisi ketiga."})
    again = detail_issue(world)
    assert [h["version"] for h in again["context_history"]] == [3, 2, 1]
    assert again["context"]["definition"] == "Definisi ketiga."


def test_the_revision_is_audited_with_before_and_after(world) -> None:
    post(world.clients["member"], world.url, {"definition": "Definisi kedua."})
    event = AuditEvent.objects.filter(
        action=AuditAction.ISSUE_CONTEXT, subject_id=world.issue.pk, actor=world.member
    ).latest("id")
    assert event.before == {"version": 1, "definition": "Definisi awal."}
    assert event.after == {"version": 2, "definition": "Definisi kedua."}


def test_an_unchanged_definition_is_rejected_and_creates_no_version(world) -> None:
    res = post(world.clients["member"], world.url, {"definition": "Definisi awal."})
    assert res.status_code == 400 and "tidak ada yang direvisi" in res.json()["detail"]
    assert [h["version"] for h in detail_issue(world)["context_history"]] == [1]


def test_whitespace_changes_count_as_a_revision_and_blank_is_allowed(world) -> None:
    assert (
        post(world.clients["member"], world.url, {"definition": "Definisi awal. "}).status_code
        == 201
    )
    cleared = post(world.clients["member"], world.url, {"definition": ""})
    assert cleared.status_code == 201 and cleared.json()["context"]["definition"] == ""


@pytest.mark.parametrize("body", [{}, {"definition": None}])
def test_the_definition_field_is_required(world, body) -> None:
    assert post(world.clients["member"], world.url, body).status_code == 400


def test_only_members_may_revise_and_outsiders_cannot_tell_it_exists(world) -> None:
    body = {"definition": "Dari peran lain."}
    assert post(world.clients["viewer"], world.url, body).status_code == 403
    assert post(world.clients["outsider"], world.url, body).status_code == 404
    assert post(world.clients["owner"], world.url, body).status_code == 201
    assert (
        post(world.clients["member"], "/api/issues/999999/context-versions/", body).status_code
        == 404
    )
