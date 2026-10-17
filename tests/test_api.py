"""WP-0.5: API JSON untuk frontend (FR-001, FR-002, FR-003, FR-010..014, FR-016, FR-090)."""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from investigations.models import CollectionTarget, Investigation

pytestmark = pytest.mark.django_db

PASSWORD = "kata-sandi-uji-123"


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("analis", password=PASSWORD)


@pytest.fixture
def api(user: User) -> Client:
    c = Client()
    c.force_login(user)
    return c


def post(client: Client, path: str, data: dict | None = None):
    return client.post(path, data or {}, content_type="application/json")


def make_investigation(api: Client, name: str = "Kebakaran hutan") -> dict:
    res = post(api, "/api/investigations/", {"name": name})
    assert res.status_code == 201, res.content
    return res.json()


def make_issue_with_proposition(api: Client, inv_id: int) -> tuple[dict, dict]:
    issue = post(
        api,
        f"/api/investigations/{inv_id}/issues/",
        {"title": "Tanggung jawab korporasi", "definition": "Konteks awal"},
    ).json()
    prop = post(
        api, f"/api/issues/{issue['id']}/propositions/", {"statement": "Perusahaan perlu diaudit"}
    ).json()
    return issue, prop


# --- Autentikasi ---------------------------------------------------------------------------


def test_anonymous_gets_401_json_on_protected_endpoints() -> None:
    c = Client()
    for path in ["/api/auth/me/", "/api/meta/", "/api/investigations/", "/api/investigations/1/"]:
        res = c.get(path)
        assert res.status_code == 401, path
        assert "json" in res.headers["Content-Type"]


def test_anonymous_cannot_create_anything() -> None:
    c = Client()
    res = post(c, "/api/investigations/", {"name": "x"})
    assert res.status_code == 401
    assert not Investigation.objects.exists()


def test_login_requires_csrf_token(user: User) -> None:
    c = Client(enforce_csrf_checks=True)
    res = post(c, "/api/auth/login/", {"username": "analis", "password": PASSWORD})
    assert res.status_code == 403
    assert "_auth_user_id" not in c.session


def test_login_logout_flow_with_csrf(user: User) -> None:
    c = Client(enforce_csrf_checks=True)
    assert c.get("/api/auth/csrf/").status_code == 200
    token = c.cookies["csrftoken"].value

    res = c.post(
        "/api/auth/login/",
        {"username": "analis", "password": PASSWORD},
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert res.status_code == 200
    assert res.json() == {"username": "analis", "is_staff": False, "is_superuser": False}
    assert "password" not in res.content.decode().lower()
    assert c.get("/api/auth/me/").json()["username"] == "analis"

    token = c.cookies["csrftoken"].value  # dirotasi saat login
    logout = c.post(
        "/api/auth/logout/", {}, content_type="application/json", headers={"X-CSRFToken": token}
    )
    assert logout.status_code == 204
    assert c.get("/api/auth/me/").status_code == 401


def test_wrong_password_is_400_without_detail_leak(user: User) -> None:
    c = Client()
    res = post(c, "/api/auth/login/", {"username": "analis", "password": "salah"})
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_credentials"
    assert "analis" not in res.json()["detail"]  # tidak membocorkan keberadaan akun


def test_login_is_locked_after_repeated_failures(user: User) -> None:
    from django.conf import settings

    c = Client()
    for _ in range(settings.AXES_FAILURE_LIMIT):
        post(c, "/api/auth/login/", {"username": "analis", "password": "salah"})
    res = post(c, "/api/auth/login/", {"username": "analis", "password": PASSWORD})
    assert res.status_code == 429
    assert res.json()["code"] == "locked_out"
    assert c.get("/api/auth/me/").status_code == 401


def test_authenticated_post_requires_csrf(user: User) -> None:
    c = Client(enforce_csrf_checks=True)
    c.force_login(user)
    res = post(c, "/api/investigations/", {"name": "tanpa csrf"})
    assert res.status_code == 403
    assert not Investigation.objects.exists()


def test_meta_lists_valid_choices(api: Client) -> None:
    meta = api.get("/api/meta/").json()
    assert [p["value"] for p in meta["platforms"]] == [
        "x",
        "threads",
        "tiktok",
        "instagram",
        "facebook",
    ]
    assert [s["value"] for s in meta["initial_stances"]] == [
        "PRO",
        "CONTRA",
        "MIXED",
        "UNDETERMINED",
    ]


# --- Investigasi, issue, proposition -------------------------------------------------------


def test_create_and_list_investigation(api: Client) -> None:
    inv = make_investigation(api)
    assert inv["name"] == "Kebakaran hutan"
    rows = api.get("/api/investigations/").json()
    assert [r["id"] for r in rows] == [inv["id"]]
    assert rows[0]["issue_count"] == 0
    assert rows[0]["created_by"] == "analis"


def test_blank_name_is_rejected(api: Client) -> None:
    assert post(api, "/api/investigations/", {"name": "  "}).status_code == 400
    assert not Investigation.objects.exists()


def test_issue_and_propositions_appear_in_detail(api: Client) -> None:
    inv = make_investigation(api)
    issue, p1 = make_issue_with_proposition(api, inv["id"])
    p2 = post(api, f"/api/issues/{issue['id']}/propositions/", {"statement": "Klaim kedua"}).json()
    assert (p1["label"], p2["label"]) == ("P1", "P2")

    detail = api.get(f"/api/investigations/{inv['id']}/").json()
    got = detail["issues"][0]
    assert got["context"] == {"version": 1, "definition": "Konteks awal"}
    assert [p["label"] for p in got["propositions"]] == ["P1", "P2"]
    assert "stance" not in got  # issue tidak punya stance (M1)


def test_unknown_investigation_is_404_with_indonesian_message(api: Client) -> None:
    res = api.get("/api/investigations/999999/")
    assert res.status_code == 404
    assert res.json() == {"detail": "Data tidak ditemukan.", "code": "not_found"}
    assert "Investigation" not in res.content.decode()  # tidak membocorkan nama model


def test_unknown_issue_and_target_are_404(api: Client) -> None:
    assert post(api, "/api/issues/999999/propositions/", {"statement": "x"}).status_code == 404
    assert post(api, "/api/targets/999999/context-versions/", {"note": "x"}).status_code == 404


# --- Target dan konteks --------------------------------------------------------------------


def target_payload(**kw) -> dict:
    return {
        "platform": "x",
        "target_type": "post",
        "url": "https://x.com/u/status/1",
        "note": "Posting menyatakan perusahaan tidak perlu diaudit",
        **kw,
    }


def test_register_target_with_note_and_stance(api: Client) -> None:
    inv = make_investigation(api)
    _issue, p1 = make_issue_with_proposition(api, inv["id"])
    res = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(stances=[{"proposition": p1["id"], "stance": "CONTRA"}]),
    )
    assert res.status_code == 201, res.content
    target = res.json()
    assert target["context"]["version"] == 1
    assert target["context"]["stances"][0]["stance"] == "CONTRA"
    assert target["context"]["stances"][0]["label"] == "P1"
    assert target["latest_inspection"] is None  # belum pernah diperiksa (bukan "kosong")

    detail = api.get(f"/api/investigations/{inv['id']}/").json()
    assert [t["id"] for t in detail["targets"]] == [target["id"]]


def test_duplicate_target_returns_409_with_existing_id(api: Client) -> None:
    inv = make_investigation(api)
    first = post(api, f"/api/investigations/{inv['id']}/targets/", target_payload()).json()
    res = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(url="https://twitter.com/u/status/1/?s=20"),
    )
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_target"
    assert res.json()["existing_id"] == first["id"]
    assert CollectionTarget.objects.count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": "https://tiktok.com/@u/video/1"},  # domain tidak cocok dengan platform
        {"url": "javascript:alert(1)"},
        {"url": ""},
        {"platform": "myspace"},
        {"target_type": "video"},
    ],
)
def test_invalid_target_is_400_and_not_saved(api: Client, overrides: dict) -> None:
    inv = make_investigation(api)
    res = post(api, f"/api/investigations/{inv['id']}/targets/", target_payload(**overrides))
    assert res.status_code == 400
    assert not CollectionTarget.objects.exists()


def test_invalid_stance_is_rejected(api: Client) -> None:
    inv = make_investigation(api)
    _issue, p1 = make_issue_with_proposition(api, inv["id"])
    for bad in ("NEUTRAL", "pro", "NOT_RELEVANT"):
        res = post(
            api,
            f"/api/investigations/{inv['id']}/targets/",
            target_payload(stances=[{"proposition": p1["id"], "stance": bad}]),
        )
        assert res.status_code == 400, bad
    assert not CollectionTarget.objects.exists()


def test_stance_for_proposition_of_other_investigation_is_rejected(api: Client) -> None:
    inv = make_investigation(api)
    other = make_investigation(api, "Investigasi lain")
    _issue, foreign = make_issue_with_proposition(api, other["id"])
    res = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(stances=[{"proposition": foreign["id"], "stance": "PRO"}]),
    )
    assert res.status_code == 400
    assert not CollectionTarget.objects.exists()


def test_unknown_proposition_is_400(api: Client) -> None:
    inv = make_investigation(api)
    res = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(stances=[{"proposition": 999999, "stance": "PRO"}]),
    )
    assert res.status_code == 400


def test_note_is_stored_verbatim(api: Client) -> None:
    inv = make_investigation(api)
    note = "  Jangan beri label buzzer pada semua kritik.\n\nBaris kedua  "
    target = post(api, f"/api/investigations/{inv['id']}/targets/", target_payload(note=note)).json()
    assert target["context"]["note"] == note


def test_revising_note_keeps_history_and_previous_stance(api: Client) -> None:
    inv = make_investigation(api)
    _issue, p1 = make_issue_with_proposition(api, inv["id"])
    target = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(note="Catatan awal", stances=[{"proposition": p1["id"], "stance": "CONTRA"}]),
    ).json()

    res = post(api, f"/api/targets/{target['id']}/context-versions/", {"note": "Catatan revisi"})
    assert res.status_code == 201, res.content
    revised = res.json()
    assert revised["context"]["version"] == 2
    assert revised["context"]["note"] == "Catatan revisi"
    assert revised["context"]["stances"][0]["stance"] == "CONTRA"  # dibawa dari versi 1
    assert [v["version"] for v in revised["context_history"]] == [2, 1]
    assert revised["context_history"][1]["note"] == "Catatan awal"  # versi lama utuh


def test_revision_with_empty_stances_clears_only_new_version(api: Client) -> None:
    inv = make_investigation(api)
    _issue, p1 = make_issue_with_proposition(api, inv["id"])
    target = post(
        api,
        f"/api/investigations/{inv['id']}/targets/",
        target_payload(stances=[{"proposition": p1["id"], "stance": "PRO"}]),
    ).json()
    revised = post(
        api, f"/api/targets/{target['id']}/context-versions/", {"note": "x", "stances": []}
    ).json()
    assert revised["context"]["stances"] == []
    assert len(revised["context_history"][1]["stances"]) == 1


def test_responses_do_not_expose_internal_fields(api: Client) -> None:
    inv = make_investigation(api)
    target = post(api, f"/api/investigations/{inv['id']}/targets/", target_payload()).json()
    blob = str(api.get(f"/api/investigations/{inv['id']}/").json()) + str(target)
    for forbidden in ("password", "session", "secret"):
        assert forbidden not in blob.lower()
