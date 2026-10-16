"""WP-0.4: model domain, versi konteks, append-only (FR-002/003/010-014/016; AT-01, AT-07)."""

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError
from investigations import services
from investigations.enums import InitialStance, Platform, TargetType
from investigations.errors import DuplicateTarget, InvalidContext, InvalidTargetURL
from investigations.models import (
    CollectionTarget,
    Investigation,
    IssueContextVersion,
    Proposition,
    TargetContextVersion,
    TargetPropositionStance,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user: User) -> Investigation:
    return services.create_investigation(user=user, name="Kebakaran hutan")


@pytest.fixture
def issue(inv: Investigation, user: User):
    return services.create_issue(
        investigation=inv, user=user, title="Tanggung jawab korporasi", definition="Konteks awal"
    )


@pytest.fixture
def p1(issue, user: User) -> Proposition:
    return services.add_proposition(
        issue=issue, user=user, statement="Perusahaan yang diduga terkait perlu diaudit"
    )


def _register(inv: Investigation, user: User, url: str = "https://x.com/u/status/1", **kw):
    return services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url=url,
        **kw,
    )


# --- Investigation / Issue / Proposition ---------------------------------------------------


def test_issue_has_no_stance_field() -> None:
    # M1: issue adalah topik; pro/kontra hanya terhadap proposition.
    from investigations.models import Issue

    names = {f.name for f in Issue._meta.get_fields()}
    assert not names & {"stance", "label", "position"}


def test_create_issue_creates_first_context_version(issue) -> None:
    versions = list(issue.context_versions.all())
    assert [v.version for v in versions] == [1]
    assert versions[0].definition == "Konteks awal"


def test_propositions_are_numbered_per_issue(issue, user: User) -> None:
    a = services.add_proposition(issue=issue, user=user, statement="Klaim satu")
    b = services.add_proposition(issue=issue, user=user, statement="Klaim dua")
    other = services.create_issue(investigation=issue.investigation, user=user, title="Isu lain")
    c = services.add_proposition(issue=other, user=user, statement="Klaim lain")
    assert (a.label, b.label, c.label) == ("P1", "P2", "P1")


def test_issue_can_have_multiple_propositions(issue, user: User) -> None:
    for i in range(3):
        services.add_proposition(issue=issue, user=user, statement=f"Klaim {i}")
    assert issue.propositions.count() == 3


def test_empty_names_are_rejected(inv: Investigation, user: User) -> None:
    with pytest.raises(InvalidContext):
        services.create_investigation(user=user, name="  ")
    with pytest.raises(InvalidContext):
        services.create_issue(investigation=inv, user=user, title="")


def test_proposition_statement_cannot_be_changed(p1: Proposition) -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        Proposition.objects.filter(pk=p1.pk).update(statement="Diubah diam-diam")
    p1.refresh_from_db()
    assert p1.statement.startswith("Perusahaan")


def test_proposition_cannot_be_deleted(p1: Proposition) -> None:
    with pytest.raises((DatabaseError, ProtectedError)), transaction.atomic():
        p1.delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        Proposition.objects.filter(pk=p1.pk)._raw_delete(Proposition.objects.db)  # type: ignore[attr-defined]
    assert Proposition.objects.filter(pk=p1.pk).exists()


def test_proposition_can_be_retired_once_without_changing_content(p1: Proposition) -> None:
    services.retire_proposition(proposition=p1)
    p1.refresh_from_db()
    assert p1.retired_at is not None
    assert p1.statement.startswith("Perusahaan")
    with pytest.raises(InvalidContext):
        services.retire_proposition(proposition=p1)
    with pytest.raises(DatabaseError), transaction.atomic():
        Proposition.objects.filter(pk=p1.pk).update(retired_at=None)


def test_history_is_protected_from_cascading_delete(issue, p1: Proposition) -> None:
    with pytest.raises(ProtectedError):
        issue.investigation.delete()
    with pytest.raises(ProtectedError):
        issue.delete()


# --- Target dan AT-01 ----------------------------------------------------------------------


def test_register_target_creates_first_context_version(inv: Investigation, user: User) -> None:
    target = _register(inv, user, note="Posting ini menolak audit")
    assert target.context_versions.count() == 1
    v1 = target.context_versions.get()
    assert (v1.version, v1.note) == (1, "Posting ini menolak audit")


def test_AT01_same_url_is_one_target(inv: Investigation, user: User) -> None:
    first = _register(inv, user, url="https://x.com/u/status/1")
    variants = [
        "https://x.com/u/status/1/",
        "http://www.x.com/u/status/1",
        "https://twitter.com/u/status/1?s=20",
        "https://x.com/u/status/1#x",
    ]
    for variant in variants:
        with pytest.raises(DuplicateTarget) as exc:
            _register(inv, user, url=variant)
        assert exc.value.existing_id == first.pk
    assert CollectionTarget.objects.filter(investigation=inv).count() == 1


def test_same_url_is_allowed_in_another_investigation(inv: Investigation, user: User) -> None:
    other = services.create_investigation(user=user, name="Investigasi lain")
    _register(inv, user)
    _register(other, user)
    assert CollectionTarget.objects.count() == 2


def test_same_path_on_other_platform_is_a_different_target(inv: Investigation, user: User) -> None:
    _register(inv, user, url="https://x.com/u/status/1")
    services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.THREADS,
        target_type=TargetType.POST,
        url="https://threads.com/u/status/1",
    )
    assert CollectionTarget.objects.count() == 2


def test_wrong_domain_for_platform_is_rejected_and_nothing_is_saved(
    inv: Investigation, user: User
) -> None:
    with pytest.raises(InvalidTargetURL):
        _register(inv, user, url="https://tiktok.com/@u/video/1")
    assert not CollectionTarget.objects.exists()


def test_original_url_is_kept_as_entered(inv: Investigation, user: User) -> None:
    target = _register(inv, user, url="  https://twitter.com/u/status/1?s=20  ")
    assert target.url == "https://twitter.com/u/status/1?s=20"
    assert target.normalized_url == "https://x.com/u/status/1"


def test_invalid_target_type_is_rejected(inv: Investigation, user: User) -> None:
    with pytest.raises(InvalidContext):
        services.register_target(
            investigation=inv, user=user, platform=Platform.X, target_type="video",
            url="https://x.com/u/status/1",
        )


# --- Stance awal (FR-013, FR-015) ----------------------------------------------------------


def test_initial_stance_is_stored_per_proposition(inv: Investigation, issue, p1, user: User) -> None:
    p2 = services.add_proposition(issue=issue, user=user, statement="Klaim kedua")
    target = _register(inv, user, stances={p1: InitialStance.CONTRA, p2: InitialStance.MIXED})
    got = {s.proposition_id: s.stance for s in target.context_versions.get().stances.all()}
    assert got == {p1.pk: "CONTRA", p2.pk: "MIXED"}


def test_only_four_stances_allowed_for_target(inv: Investigation, p1, user: User) -> None:
    # NEUTRAL/NOT_RELEVANT adalah label respons (M2), bukan posisi awal target.
    for bad in ("NEUTRAL", "NOT_RELEVANT", "pro", ""):
        with pytest.raises(InvalidContext):
            _register(inv, user, url=f"https://x.com/u/status/{abs(hash(bad))}", stances={p1: bad})


def test_db_rejects_invalid_stance_even_bypassing_services(inv: Investigation, p1, user: User) -> None:
    target = _register(inv, user)
    version = target.context_versions.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        TargetPropositionStance.objects.create(context_version=version, proposition=p1, stance="NEUTRAL")


def test_proposition_from_another_investigation_is_rejected(
    inv: Investigation, user: User
) -> None:
    other = services.create_investigation(user=user, name="Lain")
    other_issue = services.create_issue(investigation=other, user=user, title="Isu")
    foreign = services.add_proposition(issue=other_issue, user=user, statement="Klaim asing")
    with pytest.raises(InvalidContext):
        _register(inv, user, stances={foreign: InitialStance.PRO})
    assert not CollectionTarget.objects.exists()


def test_retired_proposition_cannot_be_used_for_new_stance(inv: Investigation, p1, user: User) -> None:
    services.retire_proposition(proposition=p1)
    with pytest.raises(InvalidContext):
        _register(inv, user, stances={p1: InitialStance.PRO})


# --- Versi konteks dan AT-07 ---------------------------------------------------------------


def test_AT07_revising_target_note_creates_new_version_and_keeps_old(
    inv: Investigation, p1, user: User
) -> None:
    target = _register(inv, user, note="Catatan awal", stances={p1: InitialStance.CONTRA})
    v1 = target.context_versions.get()

    v2 = services.revise_target_context(target=target, user=user, note="Catatan revisi")
    assert v2.version == 2

    v1.refresh_from_db()
    assert (v1.version, v1.note) == (1, "Catatan awal")
    assert [v.version for v in target.context_versions.all()] == [2, 1]


def test_revision_without_stances_carries_previous_stances_forward(
    inv: Investigation, p1, user: User
) -> None:
    target = _register(inv, user, stances={p1: InitialStance.CONTRA})
    v2 = services.revise_target_context(target=target, user=user, note="Revisi")
    assert [(s.proposition_id, s.stance) for s in v2.stances.all()] == [(p1.pk, "CONTRA")]


def test_revision_with_explicit_empty_stances_clears_them(inv: Investigation, p1, user: User) -> None:
    target = _register(inv, user, stances={p1: InitialStance.CONTRA})
    v2 = services.revise_target_context(target=target, user=user, note="Revisi", stances={})
    assert v2.stances.count() == 0
    # Versi 1 tetap utuh.
    assert target.context_versions.get(version=1).stances.count() == 1


def test_revision_can_change_stance_without_touching_old_version(
    inv: Investigation, p1, user: User
) -> None:
    target = _register(inv, user, stances={p1: InitialStance.CONTRA})
    services.revise_target_context(
        target=target, user=user, note="Revisi", stances={p1: InitialStance.MIXED}
    )
    assert target.context_versions.get(version=1).stances.get().stance == "CONTRA"
    assert target.context_versions.get(version=2).stances.get().stance == "MIXED"


def test_note_is_stored_verbatim_as_guidance(inv: Investigation, user: User) -> None:
    # FR-016: catatan adalah panduan analis; tidak diubah/ditafsirkan sistem.
    text = "  Jangan beri label buzzer pada semua kritik.\n\nBaris kedua  "
    target = _register(inv, user, note=text)
    assert target.context_versions.get().note == text


def test_issue_context_revision_keeps_old_version(issue, user: User) -> None:
    v2 = services.revise_issue_context(issue=issue, user=user, definition="Definisi baru")
    assert v2.version == 2
    assert issue.context_versions.get(version=1).definition == "Konteks awal"


# --- Append-only dijaga database -----------------------------------------------------------


def test_context_versions_cannot_be_updated_or_deleted_even_via_queryset(
    inv: Investigation, issue, p1, user: User
) -> None:
    target = _register(inv, user, note="Asli", stances={p1: InitialStance.PRO})
    tv = target.context_versions.get()
    iv = issue.context_versions.get()
    stance = tv.stances.get()

    for qs, change in [
        (TargetContextVersion.objects.filter(pk=tv.pk), {"note": "Diubah"}),
        (IssueContextVersion.objects.filter(pk=iv.pk), {"definition": "Diubah"}),
        (TargetPropositionStance.objects.filter(pk=stance.pk), {"stance": "CONTRA"}),
    ]:
        with pytest.raises(DatabaseError), transaction.atomic():
            qs.update(**change)
        with pytest.raises(DatabaseError), transaction.atomic():
            qs._raw_delete(qs.db)  # type: ignore[attr-defined]

    tv.refresh_from_db()
    iv.refresh_from_db()
    stance.refresh_from_db()
    assert (tv.note, iv.definition, stance.stance) == ("Asli", "Konteks awal", "PRO")


def test_duplicate_version_number_is_rejected_by_database(inv: Investigation, user: User) -> None:
    target = _register(inv, user)
    with pytest.raises(IntegrityError), transaction.atomic():
        TargetContextVersion.objects.create(target=target, version=1, note="ganda", created_by=user)
