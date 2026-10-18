"""A3: otorisasi per investigasi (ADR 0021): peran, 404 untuk non-anggota, matriks endpoint."""

import ast
import json
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.contrib.auth.models import User
from django.test import Client
from evidence_helpers import artifact, make_run_with_artifacts
from investigations import services as inv_services
from investigations import team
from investigations.access import RANK, effective_role
from investigations.enums import Role
from investigations.models import InvestigationMembership

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_registry():
    from collection.orchestrator import registry

    yield
    registry.clear()


def make_user(name: str, **extra) -> User:
    return User.objects.create_user(name, password="Kata-sandi-uji-123!", **extra)


def client_for(user: User) -> Client:
    c = Client()
    c.force_login(user)
    return c


def post(c, path, data=None):
    return c.post(path, data or {}, content_type="application/json")


class World:
    """Satu investigasi dengan run berartefak dan satu pengguna per peran."""

    def __init__(self, settings, tmp_path) -> None:
        self.owner = make_user("pemilik")
        self.run = make_run_with_artifacts(self.owner, settings, tmp_path)
        self.inv = self.run.target.investigation
        self.target = self.run.target
        self.member = make_user("anggota")
        self.viewer = make_user("pembaca")
        self.outsider = make_user("orang-luar")
        self.admin = make_user("admin", is_superuser=True, is_staff=True)
        for user, role in ((self.member, Role.MEMBER), (self.viewer, Role.VIEWER)):
            team.grant(investigation=self.inv, user=user, role=role, added_by=self.owner)
        owner_client = client_for(self.owner)
        issue = post(
            owner_client, f"/api/investigations/{self.inv.pk}/issues/", {"title": "Isu"}
        ).json()
        self.issue_id = issue["id"]
        self.artifact_id = artifact(self.run, "dom_snapshot").pk
        self.clients = {
            "owner": owner_client,
            "member": client_for(self.member),
            "viewer": client_for(self.viewer),
            "outsider": client_for(self.outsider),
            "admin": client_for(self.admin),
        }


@pytest.fixture
def world(settings, tmp_path) -> World:
    return World(settings, tmp_path)


# --- matriks endpoint x peran -----------------------------------------------------------------
# (nama, metode, jalur, isi, peran minimum). Isi dibuat per pemanggilan agar tidak bentrok.


def endpoints(w: World):
    inv, tid, rid = w.inv.pk, w.target.pk, w.run.pk
    return [
        ("investigasi: detail", "get", f"/api/investigations/{inv}/", None, Role.VIEWER),
        (
            "issue: buat",
            "post",
            f"/api/investigations/{inv}/issues/",
            lambda: {"title": f"I{next(_n)}"},
            Role.MEMBER,
        ),
        (
            "proposition: buat",
            "post",
            f"/api/issues/{w.issue_id}/propositions/",
            lambda: {"statement": f"P{next(_n)}"},
            Role.MEMBER,
        ),
        (
            "target: daftar",
            "post",
            f"/api/investigations/{inv}/targets/",
            lambda: {
                "platform": "x",
                "target_type": "post",
                "url": f"https://x.com/u/status/{900 + next(_n)}",
            },
            Role.MEMBER,
        ),
        (
            "konteks target: revisi",
            "post",
            f"/api/targets/{tid}/context-versions/",
            lambda: {"note": f"c{next(_n)}"},
            Role.MEMBER,
        ),
        ("inspeksi: riwayat", "get", f"/api/targets/{tid}/inspections/", None, Role.VIEWER),
        ("inspeksi: jalankan", "post", f"/api/targets/{tid}/inspections/", lambda: {}, Role.MEMBER),
        ("run: detail", "get", f"/api/inspections/{rid}/", None, Role.VIEWER),
        ("run: respons mentah", "get", f"/api/inspections/{rid}/observations/", None, Role.VIEWER),
        (
            "run: akui tinjauan",
            "post",
            f"/api/inspections/{rid}/acknowledge-review/",
            lambda: {},
            Role.MEMBER,
        ),
        (
            "run: verifikasi semua artefak",
            "post",
            f"/api/inspections/{rid}/verify-artifacts/",
            lambda: {},
            Role.VIEWER,
        ),
        (
            "artefak: verifikasi",
            "post",
            f"/api/artifacts/{w.artifact_id}/verify/",
            lambda: {},
            Role.VIEWER,
        ),
        ("artefak: isi", "get", f"/api/artifacts/{w.artifact_id}/content/", None, Role.VIEWER),
        ("anggota: daftar", "get", f"/api/investigations/{inv}/members/", None, Role.VIEWER),
        (
            "anggota: tambah",
            "post",
            f"/api/investigations/{inv}/members/",
            lambda: {"username": "tidak-ada", "role": "VIEWER"},
            Role.OWNER,
        ),
        (
            "anggota: ubah peran",
            "post",
            f"/api/investigations/{inv}/members/{w.viewer.pk}/role/",
            lambda: {"role": "VIEWER"},
            Role.OWNER,
        ),
        (
            "anggota: cabut",
            "post",
            f"/api/investigations/{inv}/members/{w.outsider.pk}/revoke/",
            lambda: {},
            Role.OWNER,
        ),
    ]


_n = iter(range(1, 10_000))
ROLES = ["viewer", "member", "owner", "admin", "outsider"]
EFFECTIVE = {"viewer": 1, "member": 2, "owner": 3, "admin": 99, "outsider": 0}


def call(client, method, path, body):
    if method == "get":
        return client.get(path)
    return post(client, path, body() if body else {})


def test_every_endpoint_enforces_its_minimum_role(world) -> None:
    checked = 0
    for name, method, path, body, minimum in endpoints(world):
        for role in ROLES:
            res = call(world.clients[role], method, path, body)
            allowed = EFFECTIVE[role] >= RANK[minimum]
            if role == "outsider":
                assert res.status_code == 404, (name, role, res.status_code, res.content[:120])
                assert res.json()["code"] == "not_found", (name, role)
            elif not allowed:
                assert res.status_code == 403, (name, role, res.status_code, res.content[:120])
                assert res.json()["code"] == "insufficient_role", (name, role)
            else:
                assert res.status_code not in (401, 403, 404) or name in (
                    "anggota: tambah",
                    "anggota: cabut",
                ), (name, role, res.status_code, res.content[:160])
            checked += 1
    assert checked == len(endpoints(world)) * len(ROLES)


def test_allowed_roles_reach_the_real_handler_not_just_pass_the_gate(world) -> None:
    owner = world.clients["owner"]
    assert owner.get(f"/api/investigations/{world.inv.pk}/").json()["name"] == "Bukti"
    assert owner.get(f"/api/inspections/{world.run.pk}/").json()["status"] == "COMPLETED"
    assert post(owner, f"/api/artifacts/{world.artifact_id}/verify/").json()["result"] == "MATCH"
    res = post(world.clients["member"], f"/api/inspections/{world.run.pk}/acknowledge-review/")
    assert res.status_code == 409 and res.json()["code"] == "not_awaiting_review"


def test_the_endpoint_table_covers_every_object_endpoint() -> None:
    """Pengaman: endpoint baru yang memakai id objek harus ditambahkan ke matriks di atas."""
    from api.urls import urlpatterns

    object_routes = {str(p.pattern) for p in urlpatterns if "<int:" in str(p.pattern)}
    covered = {
        "investigations/<int:pk>/",
        "investigations/<int:pk>/issues/",
        "issues/<int:pk>/propositions/",
        "investigations/<int:pk>/targets/",
        "targets/<int:pk>/context-versions/",
        "targets/<int:pk>/inspections/",
        "inspections/<int:pk>/",
        "inspections/<int:pk>/observations/",
        "inspections/<int:pk>/acknowledge-review/",
        "inspections/<int:pk>/verify-artifacts/",
        "artifacts/<int:pk>/verify/",
        "artifacts/<int:pk>/content/",
        "investigations/<int:pk>/members/",
        "investigations/<int:pk>/members/<int:user_id>/role/",
        "investigations/<int:pk>/members/<int:user_id>/revoke/",
        # pengelolaan akun: khusus super admin, diuji di bagian akun pengguna
        "users/<int:pk>/activation/",
        "users/<int:pk>/password/",
        # API analisis (WP-2.7a): matriksnya di tests/test_api_analysis.py
        "investigations/<int:pk>/analysis-runs/",
        "analysis-runs/<int:pk>/",
        "analysis-runs/<int:pk>/responses/",
        "assessments/<int:pk>/history/",
        "assessments/<int:pk>/review/",
        "analysis-runs/<int:pk>/graph/",
        "analysis-runs/<int:pk>/coordination/",
        "analysis-runs/<int:pk>/profiles/",
        "profiles/<int:pk>/",
        "investigations/<int:pk>/findings/",
        "investigations/<int:pk>/findings/evidence/",
        "findings/<int:pk>/",
        "findings/<int:pk>/revise/",
        "findings/<int:pk>/endorse/",
        "findings/<int:pk>/withdraw/",
        "observations/<int:pk>/",
    }
    assert object_routes == covered, object_routes ^ covered


# --- keberadaan tidak bocor -------------------------------------------------------------------


def test_outsider_cannot_tell_an_existing_investigation_from_a_missing_one(world) -> None:
    out = world.clients["outsider"]
    for real, fake in (
        (f"/api/investigations/{world.inv.pk}/", "/api/investigations/987654/"),
        (f"/api/targets/{world.target.pk}/inspections/", "/api/targets/987654/inspections/"),
        (f"/api/inspections/{world.run.pk}/", "/api/inspections/987654/"),
        (f"/api/artifacts/{world.artifact_id}/content/", "/api/artifacts/987654/content/"),
    ):
        a, b = out.get(real), out.get(fake)
        assert (a.status_code, a.content) == (b.status_code, b.content), real


def test_investigation_list_shows_only_what_the_user_may_see(world) -> None:
    other_owner = make_user("pemilik-lain")
    inv_services.create_investigation(user=other_owner, name="Rahasia pihak lain")
    names = lambda c: sorted(i["name"] for i in c.get("/api/investigations/").json())  # noqa: E731
    assert names(world.clients["owner"]) == ["Bukti"]
    assert names(world.clients["viewer"]) == ["Bukti"]
    assert names(world.clients["outsider"]) == []
    assert names(client_for(other_owner)) == ["Rahasia pihak lain"]
    assert names(world.clients["admin"]) == ["Bukti", "Rahasia pihak lain"]


def test_summaries_carry_my_role_and_member_count(world) -> None:
    for role, expected in (
        ("owner", "OWNER"),
        ("member", "MEMBER"),
        ("viewer", "VIEWER"),
        ("admin", "ADMIN"),
    ):
        row = world.clients[role].get("/api/investigations/").json()[0]
        assert row["my_role"] == expected and row["member_count"] == 3, role
        assert (
            world.clients[role].get(f"/api/investigations/{world.inv.pk}/").json()["my_role"]
            == expected
        )


def test_creator_becomes_owner_and_the_creation_response_says_so() -> None:
    user = make_user("pencipta")
    res = post(client_for(user), "/api/investigations/", {"name": "Baru"})
    body = res.json()
    assert res.status_code == 201 and body["my_role"] == "OWNER" and body["member_count"] == 1
    inv = InvestigationMembership.objects.get(investigation_id=body["id"])
    assert (inv.user, inv.role, inv.added_by, inv.revoked_at) == (user, "OWNER", user, None)


def test_superuser_is_admin_everywhere_without_being_a_member(world) -> None:
    assert effective_role(world.admin, world.inv) == "ADMIN"
    assert not InvestigationMembership.objects.filter(user=world.admin).exists()
    assert (
        post(
            world.clients["admin"],
            f"/api/investigations/{world.inv.pk}/issues/",
            {"title": "Dari admin"},
        ).status_code
        == 201
    )


def test_me_endpoint_reports_superuser_flag(world) -> None:
    assert world.clients["admin"].get("/api/auth/me/").json()["is_superuser"] is True
    assert world.clients["viewer"].get("/api/auth/me/").json()["is_superuser"] is False


# --- perubahan peran dan pencabutan berlaku seketika ------------------------------------------


def test_revoked_member_loses_access_immediately_but_history_remains(world) -> None:
    c = world.clients["member"]
    assert c.get(f"/api/investigations/{world.inv.pk}/").status_code == 200
    assert (
        post(
            world.clients["owner"],
            f"/api/investigations/{world.inv.pk}/members/{world.member.pk}/revoke/",
        ).status_code
        == 204
    )
    assert c.get(f"/api/investigations/{world.inv.pk}/").status_code == 404
    assert c.get("/api/investigations/").json() == []
    rows = InvestigationMembership.objects.filter(investigation=world.inv, user=world.member)
    assert (
        rows.count() == 1
        and rows.get().revoked_by == world.owner
        and rows.get().revoked_at is not None
    )


def test_promoting_a_viewer_takes_effect_immediately(world) -> None:
    c = world.clients["viewer"]
    path = f"/api/investigations/{world.inv.pk}/issues/"
    assert post(c, path, {"title": "x"}).status_code == 403
    res = post(
        world.clients["owner"],
        f"/api/investigations/{world.inv.pk}/members/{world.viewer.pk}/role/",
        {"role": "MEMBER"},
    )
    assert res.status_code == 200 and res.json()["role"] == "MEMBER"
    assert post(c, path, {"title": "y"}).status_code == 201
    assert (
        InvestigationMembership.objects.filter(investigation=world.inv, user=world.viewer).count()
        == 2
    )  # riwayat


def test_deactivated_account_cannot_use_an_existing_session(world) -> None:
    world.member.is_active = False
    world.member.save()
    assert world.clients["member"].get("/api/investigations/").status_code in (401, 403)


# --- larangan akses langsung lewat get_object_or_404 ------------------------------------------

PROTECTED = {
    "Investigation",
    "Issue",
    "CollectionTarget",
    "InspectionRun",
    "EvidenceArtifact",
    "Proposition",
    "AnalysisRun",
    "ResponseAssessment",
    "ActorIssueProfile",
    "Finding",
    "PostObservation",
}


def test_views_never_fetch_protected_objects_without_authorization() -> None:
    """Statis: `api/views.py` hanya boleh memakai get_object_or_404 untuk model non-investigasi."""
    source = (Path(dj_settings.BASE_DIR) / "api" / "views.py").read_text()
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "get_object_or_404":
            names = {n.id for n in ast.walk(node.args[0]) if isinstance(n, ast.Name)} | {
                n.attr for n in ast.walk(node.args[0]) if isinstance(n, ast.Attribute)
            }
            if names & PROTECTED:
                offenders.append(ast.unparse(node)[:80])
    assert offenders == []


def test_the_static_check_detects_a_violation() -> None:
    tree = ast.parse("x = get_object_or_404(InspectionRun, pk=1)")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert {n.id for n in ast.walk(call.args[0]) if isinstance(n, ast.Name)} & PROTECTED


def test_run_detail_reports_the_callers_role_for_the_ui(world) -> None:
    for who, expected in (
        ("owner", "OWNER"),
        ("member", "MEMBER"),
        ("viewer", "VIEWER"),
        ("admin", "ADMIN"),
    ):
        body = world.clients[who].get(f"/api/inspections/{world.run.pk}/").json()
        assert body["my_role"] == expected, who
