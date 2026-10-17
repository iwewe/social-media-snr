"""A3: API anggota investigasi, pengelolaan akun (super admin), dan integritas keanggotaan."""

import json
from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client
from django.utils import timezone
from investigations import services as inv_services
from investigations import team
from investigations.models import Investigation, InvestigationMembership

pytestmark = pytest.mark.django_db
PASSWORD = "Kata-sandi-uji-123!"


def make_user(name, **extra) -> User:
    return User.objects.create_user(name, password=PASSWORD, **extra)


def client_for(user) -> Client:
    c = Client()
    c.force_login(user)
    return c


def post(c, path, data=None):
    return c.post(path, data or {}, content_type="application/json")


@pytest.fixture
def owner() -> User:
    return make_user("pemilik")


@pytest.fixture
def inv(owner):
    return inv_services.create_investigation(user=owner, name="Tim")


@pytest.fixture
def admin() -> User:
    return make_user("admin", is_superuser=True, is_staff=True)


def members_url(inv):
    return f"/api/investigations/{inv.pk}/members/"


def active(inv):
    return list(inv.memberships.filter(revoked_at__isnull=True).values_list("user__username", "role"))


# --- menambah anggota -------------------------------------------------------------------------


def test_owner_adds_a_member_and_the_list_shows_roles_and_who_added(inv, owner) -> None:
    make_user("sari")
    c = client_for(owner)
    res = post(c, members_url(inv), {"username": "sari", "role": "MEMBER"})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "sari" and body["role"] == "MEMBER" and body["added_by"] == "pemilik"
    listing = c.get(members_url(inv)).json()
    assert [(m["username"], m["role"]) for m in listing] == [("pemilik", "OWNER"), ("sari", "MEMBER")]


def test_a_viewer_can_see_the_team_but_not_change_it(inv, owner) -> None:
    viewer = make_user("pembaca")
    team.grant(investigation=inv, user=viewer, role="VIEWER", added_by=owner)
    c = client_for(viewer)
    assert len(c.get(members_url(inv)).json()) == 2
    assert post(c, members_url(inv), {"username": "pemilik", "role": "OWNER"}).status_code == 403


def test_adding_the_same_user_twice_is_a_conflict(inv, owner) -> None:
    make_user("sari")
    c = client_for(owner)
    assert post(c, members_url(inv), {"username": "sari", "role": "VIEWER"}).status_code == 201
    res = post(c, members_url(inv), {"username": "sari", "role": "MEMBER"})
    assert res.status_code == 409 and res.json()["code"] == "already_member"
    assert active(inv).count(("sari", "VIEWER")) == 1


def test_unknown_user_and_inactive_user_are_refused_with_clear_codes(inv, owner) -> None:
    make_user("nonaktif", is_active=False)
    c = client_for(owner)
    res = post(c, members_url(inv), {"username": "tidak-ada", "role": "VIEWER"})
    assert res.status_code == 404 and res.json()["code"] == "user_not_found"
    res = post(c, members_url(inv), {"username": "nonaktif", "role": "VIEWER"})
    assert res.status_code == 400 and res.json()["code"] == "inactive_user"


@pytest.mark.parametrize("body", [{"username": "x"}, {"role": "VIEWER"}, {"username": "x", "role": "ADMIN"},
                                  {"username": "x", "role": "owner"}, {"username": "", "role": "VIEWER"}])
def test_invalid_member_input_is_a_400(inv, owner, body) -> None:
    make_user("x")
    assert post(client_for(owner), members_url(inv), body).status_code == 400


def test_username_is_matched_exactly_not_by_case_or_prefix(inv, owner) -> None:
    make_user("Sari")
    c = client_for(owner)
    assert post(c, members_url(inv), {"username": "sari", "role": "VIEWER"}).status_code == 404
    assert post(c, members_url(inv), {"username": "Sar", "role": "VIEWER"}).status_code == 404


def test_a_superuser_can_add_members_to_any_investigation(inv, admin) -> None:
    make_user("sari")
    assert post(client_for(admin), members_url(inv), {"username": "sari", "role": "MEMBER"}).status_code == 201


# --- peran terakhir dan riwayat ---------------------------------------------------------------


def role_url(inv, user):
    return f"{members_url(inv)}{user.pk}/role/"


def revoke_url(inv, user):
    return f"{members_url(inv)}{user.pk}/revoke/"


def test_the_last_owner_cannot_be_demoted_or_removed(inv, owner) -> None:
    c = client_for(owner)
    res = post(c, role_url(inv, owner), {"role": "MEMBER"})
    assert res.status_code == 409 and res.json()["code"] == "last_owner"
    res = post(c, revoke_url(inv, owner))
    assert res.status_code == 409 and res.json()["code"] == "last_owner"
    assert active(inv) == [("pemilik", "OWNER")]


def test_with_two_owners_one_may_leave_and_then_the_other_is_protected(inv, owner) -> None:
    second = make_user("pemilik-dua")
    team.grant(investigation=inv, user=second, role="OWNER", added_by=owner)
    assert post(client_for(owner), revoke_url(inv, owner)).status_code == 204  # keluar sendiri
    assert active(inv) == [("pemilik-dua", "OWNER")]
    assert post(client_for(second), revoke_url(inv, second)).status_code == 409


def test_an_admin_cannot_strip_the_last_owner_either(inv, owner, admin) -> None:
    assert post(client_for(admin), revoke_url(inv, owner)).status_code == 409


def test_changing_to_the_same_role_is_a_no_op_without_new_history(inv, owner) -> None:
    viewer = make_user("pembaca")
    team.grant(investigation=inv, user=viewer, role="VIEWER", added_by=owner)
    assert post(client_for(owner), role_url(inv, viewer), {"role": "VIEWER"}).status_code == 200
    assert InvestigationMembership.objects.filter(investigation=inv, user=viewer).count() == 1


def test_role_change_and_removal_keep_the_full_history(inv, owner) -> None:
    sari = make_user("sari")
    c = client_for(owner)
    post(c, members_url(inv), {"username": "sari", "role": "VIEWER"})
    post(c, role_url(inv, sari), {"role": "MEMBER"})
    post(c, revoke_url(inv, sari))
    post(c, members_url(inv), {"username": "sari", "role": "VIEWER"})  # boleh bergabung lagi
    rows = list(InvestigationMembership.objects.filter(user=sari).order_by("id"))
    assert [(r.role, r.revoked_at is not None) for r in rows] == [
        ("VIEWER", True), ("MEMBER", True), ("VIEWER", False)]
    assert rows[1].revoked_by == owner
    assert [m["username"] for m in c.get(members_url(inv)).json()] == ["pemilik", "sari"]


def test_changing_or_revoking_a_non_member_is_a_404_with_a_clear_code(inv, owner) -> None:
    stranger = make_user("asing")
    c = client_for(owner)
    for res in (post(c, role_url(inv, stranger), {"role": "MEMBER"}), post(c, revoke_url(inv, stranger))):
        assert res.status_code == 404 and res.json()["code"] == "not_a_member"
    assert post(c, revoke_url(inv, type("U", (), {"pk": 987654})())).status_code == 404


def test_member_and_viewer_cannot_change_roles(inv, owner) -> None:
    member = make_user("anggota")
    team.grant(investigation=inv, user=member, role="MEMBER", added_by=owner)
    c = client_for(member)
    assert post(c, role_url(inv, owner), {"role": "VIEWER"}).status_code == 403
    assert post(c, revoke_url(inv, owner)).status_code == 403


def test_a_demotion_that_would_leave_no_owner_is_refused_after_a_valid_one(inv, owner) -> None:
    second = make_user("pemilik-dua")
    team.grant(investigation=inv, user=second, role="OWNER", added_by=owner)
    team.change_role(investigation=inv, user=second, role="MEMBER", by=owner)  # sah: masih ada 1 OWNER
    with pytest.raises(team.LastOwner):
        team.change_role(investigation=inv, user=owner, role="MEMBER", by=second)


@pytest.mark.django_db(transaction=True)
def test_two_owners_demoting_each_other_at_once_never_leave_zero_owners() -> None:
    """Kunci per investigasi: dari dua penurunan bersamaan hanya satu yang boleh berhasil."""
    import threading

    owner_a, owner_b = make_user("a"), make_user("b")
    investigation = inv_services.create_investigation(user=owner_a, name="Balapan")
    team.grant(investigation=investigation, user=owner_b, role="OWNER", added_by=owner_a)
    gate, outcomes = threading.Barrier(2), []

    def demote(target, actor):
        try:
            gate.wait(10)
            team.change_role(investigation=investigation, user=target, role="MEMBER", by=actor)
            outcomes.append("ok")
        except team.LastOwner:
            outcomes.append("last_owner")
        finally:
            connection.close()

    threads = [threading.Thread(target=demote, args=(owner_b, owner_a)),
               threading.Thread(target=demote, args=(owner_a, owner_b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sorted(outcomes) == ["last_owner", "ok"], outcomes
    owners = investigation.memberships.filter(role="OWNER", revoked_at__isnull=True).count()
    assert owners == 1


# --- integritas di basis data -----------------------------------------------------------------


def row(inv, owner) -> InvestigationMembership:
    return InvestigationMembership.objects.get(investigation=inv, user=owner)


def exec_sql(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


@pytest.mark.parametrize("sql", [
    "DELETE FROM investigations_investigationmembership WHERE id = %s",
    "UPDATE investigations_investigationmembership SET role = 'VIEWER' WHERE id = %s",
    "UPDATE investigations_investigationmembership SET user_id = added_by_id + 100000 WHERE id = %s",
    "UPDATE investigations_investigationmembership SET created_at = now() WHERE id = %s",
])
def test_database_refuses_deleting_or_rewriting_a_membership(inv, owner, sql) -> None:
    pk = row(inv, owner).pk
    with pytest.raises((DatabaseError, IntegrityError)), transaction.atomic():
        exec_sql(sql, [pk])


def test_database_allows_revoking_once_and_then_freezes_the_row(inv, owner) -> None:
    second = make_user("dua")
    m = team.grant(investigation=inv, user=second, role="VIEWER", added_by=owner)
    InvestigationMembership.objects.filter(pk=m.pk).update(revoked_at=timezone.now(), revoked_by=owner)
    with pytest.raises(DatabaseError), transaction.atomic():
        InvestigationMembership.objects.filter(pk=m.pk).update(revoked_at=timezone.now(), revoked_by=owner)


def test_database_allows_only_one_active_membership_per_user_and_investigation(inv, owner) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        InvestigationMembership.objects.create(investigation=inv, user=owner, role="VIEWER", added_by=owner)


def test_database_requires_revoked_by_together_with_revoked_at(inv, owner) -> None:
    second = make_user("dua")
    with pytest.raises(IntegrityError), transaction.atomic():
        InvestigationMembership.objects.create(
            investigation=inv, user=second, role="VIEWER", added_by=owner, revoked_at=timezone.now())


def test_database_rejects_unknown_roles(inv, owner) -> None:
    second = make_user("dua")
    with pytest.raises(IntegrityError), transaction.atomic():
        InvestigationMembership.objects.create(investigation=inv, user=second, role="ROOT", added_by=owner)


def test_backfill_gives_existing_investigations_an_owner_and_is_idempotent() -> None:
    creator = make_user("lama")
    legacy = Investigation.objects.create(name="Dibuat sebelum A3", created_by=creator)
    assert not InvestigationMembership.objects.filter(investigation=legacy).exists()
    migration = import_module("investigations.migrations.0003_investigation_membership")
    migration.backfill_owners(apps, None)
    migration.backfill_owners(apps, None)
    rows = InvestigationMembership.objects.filter(investigation=legacy)
    assert [(r.user, r.role, r.added_by) for r in rows] == [(creator, "OWNER", creator)]


# --- pengelolaan akun: hanya super admin ------------------------------------------------------

USERS = "/api/users/"


def test_non_superusers_cannot_touch_accounts_not_even_owners(inv, owner) -> None:
    c = client_for(owner)
    other = make_user("lain")
    for res in (c.get(USERS), post(c, USERS, {"username": "baru", "password": PASSWORD}),
                post(c, f"{USERS}{other.pk}/activation/", {"active": False}),
                post(c, f"{USERS}{other.pk}/password/", {"password": PASSWORD})):
        assert res.status_code == 403 and res.json()["code"] == "superuser_required"
    assert not User.objects.filter(username="baru").exists()
    other.refresh_from_db()
    assert other.is_active


def test_anonymous_gets_401_on_account_endpoints() -> None:
    c = Client()
    assert c.get(USERS).status_code in (401, 403)
    assert post(c, USERS, {"username": "a", "password": PASSWORD}).status_code in (401, 403)


def test_superuser_creates_an_account_that_can_log_in_and_sees_nothing_until_added(admin) -> None:
    res = post(client_for(admin), USERS, {"username": "anggota-baru", "password": PASSWORD})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "anggota-baru" and body["is_active"] and not body["is_superuser"]
    assert "password" not in json.dumps(body).lower() and body["active_memberships"] == 0
    fresh = Client()
    login = post(fresh, "/api/auth/login/", {"username": "anggota-baru", "password": PASSWORD})
    assert login.status_code == 200 and login.json()["is_superuser"] is False
    assert fresh.get("/api/investigations/").json() == []


@pytest.mark.parametrize("username", ["Pemilik", "PEMILIK", "pemilik"])
def test_duplicate_usernames_are_refused_regardless_of_case(admin, owner, username) -> None:
    res = post(client_for(admin), USERS, {"username": username, "password": PASSWORD})
    assert res.status_code == 400 and "username" in res.json()


@pytest.mark.parametrize("username", ["ada spasi", "tanda/miring", "", "x" * 151, "a<b>"])
def test_invalid_usernames_are_refused(admin, username) -> None:
    assert post(client_for(admin), USERS, {"username": username, "password": PASSWORD}).status_code == 400


@pytest.mark.parametrize("password", ["123", "password", "12345678", "aaaaaaaa", "abc"])
def test_weak_passwords_are_refused_with_messages(admin, password) -> None:
    res = post(client_for(admin), USERS, {"username": "baru", "password": password})
    assert res.status_code == 400 and res.json()["password"]
    assert not User.objects.filter(username="baru").exists()


def test_password_equal_to_username_is_refused(admin) -> None:
    res = post(client_for(admin), USERS, {"username": "pengguna-baru-1", "password": "pengguna-baru-1"})
    assert res.status_code == 400


def test_account_list_has_membership_counts_and_never_a_password_hash(admin, inv, owner) -> None:
    body = client_for(admin).get(USERS).json()
    by_name = {u["username"]: u for u in body}
    assert by_name["pemilik"]["active_memberships"] == 1 and by_name["admin"]["is_superuser"]
    text = json.dumps(body)
    assert "pbkdf2" not in text and "password" not in text.lower()
    assert set(by_name["pemilik"]) == {"id", "username", "is_active", "is_superuser", "last_login",
                                        "date_joined", "active_memberships"}


def test_deactivating_an_account_blocks_login_and_reactivating_restores_it(admin) -> None:
    member = make_user("anggota")
    c = client_for(admin)
    assert post(c, f"{USERS}{member.pk}/activation/", {"active": False}).json()["is_active"] is False
    assert post(Client(), "/api/auth/login/", {"username": "anggota", "password": PASSWORD}).status_code == 400
    assert post(c, f"{USERS}{member.pk}/activation/", {"active": True}).json()["is_active"] is True
    assert post(Client(), "/api/auth/login/", {"username": "anggota", "password": PASSWORD}).status_code == 200


def test_an_admin_cannot_deactivate_their_own_account(admin) -> None:
    res = post(client_for(admin), f"{USERS}{admin.pk}/activation/", {"active": False})
    assert res.status_code == 400
    admin.refresh_from_db()
    assert admin.is_active


def test_password_reset_replaces_the_old_password(admin) -> None:
    member = make_user("anggota")
    new = "Sandi-baru-yang-panjang-9!"
    assert post(client_for(admin), f"{USERS}{member.pk}/password/", {"password": new}).status_code == 204
    assert post(Client(), "/api/auth/login/", {"username": "anggota", "password": PASSWORD}).status_code == 400
    assert post(Client(), "/api/auth/login/", {"username": "anggota", "password": new}).status_code == 200


def test_password_reset_applies_the_same_strength_rules(admin) -> None:
    member = make_user("anggota")
    res = post(client_for(admin), f"{USERS}{member.pk}/password/", {"password": "123"})
    assert res.status_code == 400
    member.refresh_from_db()
    assert member.check_password(PASSWORD)


def test_unknown_account_ids_are_404(admin) -> None:
    c = client_for(admin)
    assert post(c, f"{USERS}987654/activation/", {"active": False}).status_code == 404
    assert post(c, f"{USERS}987654/password/", {"password": PASSWORD}).status_code == 404
