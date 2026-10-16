"""WP-1.2: model inti pengumpulan data (FR-030, FR-031, FR-033; NFR-03, NFR-05, NFR-06; AT-13)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from collection import services
from collection.contracts import Capability, ContractViolation
from collection.errors import AppendOnlyViolation
from collection.models import (
    ActorAccount,
    IdentityStatus,
    InspectionRun,
    Post,
    PostObservation,
    PostRelation,
    RelationType,
    RunStatus,
)
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db

OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
PUBLISHED = datetime(2026, 10, 16, 1, 30, tzinfo=UTC)
CAPS = [Capability.INSPECT_POST, Capability.INSPECT_REPLIES]


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Investigasi A")


def register(inv, user, platform, url):
    return inv_services.register_target(
        investigation=inv, user=user, platform=platform, target_type=TargetType.POST, url=url
    )


@pytest.fixture
def target_x(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


@pytest.fixture
def target_tt(inv, user):
    return register(inv, user, Platform.TIKTOK, "https://tiktok.com/@u/video/1")


@pytest.fixture
def run_x(target_x, user) -> InspectionRun:
    return services.create_inspection_run(target=target_x, user=user, requested=CAPS)


@pytest.fixture
def run_tt(target_tt, user) -> InspectionRun:
    return services.create_inspection_run(target=target_tt, user=user, requested=CAPS)


def make_post(run, external="p1", **kw) -> Post:
    return Post.objects.create(
        platform=kw.pop("platform", run.target.platform),
        external_post_id=external,
        first_seen_run=run,
        **kw,
    )


def make_actor(run, external="a1", **kw) -> ActorAccount:
    return ActorAccount.objects.create(
        platform=kw.pop("platform", run.target.platform),
        external_actor_id=external,
        first_seen_run=run,
        **kw,
    )


def observe(post, run, **kw) -> PostObservation:
    defaults = dict(
        source_object_type="reply", collection_status="COMPLETED", observed_at=OBSERVED
    )
    defaults.update(kw)
    return PostObservation.objects.create(post=post, run=run, **defaults)


@contextmanager
def rejected(match: str | None = None) -> Iterator[None]:
    """Harapkan galat DB. pytest.raises di luar dan atomic di dalam: savepoint di-rollback saat
    galat sehingga transaksi tes tetap dapat dipakai."""
    with pytest.raises(DatabaseError, match=match), transaction.atomic():
        yield


# =============================== InspectionRun ===============================


def test_reinspection_adds_runs_not_targets(target_x, user) -> None:
    from investigations.models import CollectionTarget

    runs = [services.create_inspection_run(target=target_x, user=user, requested=CAPS) for _ in range(3)]
    assert [r.sequence for r in runs] == [1, 2, 3]
    assert CollectionTarget.objects.count() == 1  # AT-01: target tetap satu
    assert InspectionRun.objects.filter(target=target_x).count() == 3


def test_sequence_is_independent_per_target(target_x, target_tt, user) -> None:
    a = services.create_inspection_run(target=target_x, user=user, requested=CAPS)
    b = services.create_inspection_run(target=target_tt, user=user, requested=CAPS)
    assert (a.sequence, b.sequence) == (1, 1)


def test_run_has_public_uuid_used_as_contract_run_id(run_x) -> None:
    assert uuid.UUID(run_x.run_id) == run_x.public_id
    assert run_x.status == RunStatus.PENDING
    assert run_x.requested == ["inspect_post", "inspect_replies"]


@pytest.mark.parametrize("bad", [[], ["inspect_post", "inspect_post"], ["terbang"]])
def test_invalid_requested_capabilities_are_rejected(target_x, user, bad) -> None:
    with pytest.raises(ContractViolation):
        services.create_inspection_run(target=target_x, user=user, requested=bad)
    assert not InspectionRun.objects.exists()


def test_status_and_outcome_fields_can_be_updated_as_the_run_progresses(run_x) -> None:
    InspectionRun.objects.filter(pk=run_x.pk).update(
        status=RunStatus.RUNNING, started_at=OBSERVED, collector_name="fake", source_method="synthetic_fixture"
    )
    InspectionRun.objects.filter(pk=run_x.pk).update(
        status=RunStatus.PARTIAL, finished_at=OBSERVED + timedelta(minutes=1),
        limitations=[{"code": "PAGINATION_INCOMPLETE", "message": "x"}], coverage={"complete": False},
    )
    run_x.refresh_from_db()
    assert run_x.status == RunStatus.PARTIAL
    assert run_x.limitations[0]["code"] == "PAGINATION_INCOMPLETE"


@pytest.mark.parametrize(
    "change",
    [
        {"public_id": uuid.uuid4()},
        {"sequence": 99},
        {"requested": ["inspect_post"]},
        {"created_at": OBSERVED},
    ],
)
def test_run_identity_columns_cannot_be_changed(run_x, change) -> None:
    with rejected("identitas InspectionRun"):
        InspectionRun.objects.filter(pk=run_x.pk).update(**change)


def test_run_target_and_requester_cannot_be_changed(run_x, target_tt, user) -> None:
    other = User.objects.create_user("lain", password="x")
    with rejected("identitas InspectionRun"):
        InspectionRun.objects.filter(pk=run_x.pk).update(target=target_tt)
    with rejected("identitas InspectionRun"):
        InspectionRun.objects.filter(pk=run_x.pk).update(requested_by=other)


def test_run_cannot_be_deleted(run_x) -> None:
    with rejected("tidak dapat dihapus"):
        run_x.delete()


def test_run_with_invalid_status_is_rejected_by_the_database(run_x) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        InspectionRun.objects.filter(pk=run_x.pk).update(status="BERHASIL")


def test_finished_before_started_is_rejected(run_x) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        InspectionRun.objects.filter(pk=run_x.pk).update(
            started_at=OBSERVED, finished_at=OBSERVED - timedelta(seconds=1)
        )


def test_duplicate_sequence_is_rejected_by_the_database(run_x, user) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        InspectionRun.objects.create(
            target=run_x.target, sequence=1, requested=["inspect_post"], requested_by=user
        )


# =============================== identitas ===============================


def test_same_external_id_on_two_platforms_is_two_objects(run_x, run_tt) -> None:
    """AT-13: ID/username yang sama pada X dan TikTok tidak digabung."""
    px, pt = make_post(run_x, "123"), make_post(run_tt, "123")
    ax, at = make_actor(run_x, "alice"), make_actor(run_tt, "alice")
    assert px.pk != pt.pk and ax.pk != at.pk
    assert Post.objects.filter(external_post_id="123").count() == 2
    assert {p.platform for p in Post.objects.all()} == {"x", "tiktok"}


def test_same_external_id_on_same_platform_is_rejected(run_x) -> None:
    make_post(run_x, "123")
    make_actor(run_x, "alice")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_post(run_x, "123")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_actor(run_x, "alice")


def test_verified_identity_requires_an_external_id(run_x) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_post(run_x, None)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_actor(run_x, None)


def test_candidates_without_id_are_never_merged_and_are_excluded_from_verified(run_x) -> None:
    a = make_post(run_x, None, identity_status=IdentityStatus.NEEDS_VERIFICATION)
    b = make_post(run_x, None, identity_status=IdentityStatus.NEEDS_VERIFICATION)
    ok = make_post(run_x, "p1")
    assert a.pk != b.pk  # dua kandidat tanpa ID tetap dua baris
    assert list(Post.objects.verified()) == [ok]
    assert Post.objects.count() == 3


def test_id_may_be_assigned_once_to_a_candidate_but_never_changed(run_x) -> None:
    cand = make_post(run_x, None, identity_status=IdentityStatus.NEEDS_VERIFICATION)
    Post.objects.filter(pk=cand.pk).update(
        external_post_id="777", identity_status=IdentityStatus.VERIFIED
    )
    cand.refresh_from_db()
    assert (cand.external_post_id, cand.identity_status) == ("777", "VERIFIED")
    with rejected("ID sumber tidak dapat diubah"):
        Post.objects.filter(pk=cand.pk).update(external_post_id="888")


def test_identity_provenance_platform_and_verification_are_immutable(run_x, run_tt) -> None:
    post = make_post(run_x, "p1")
    actor = make_actor(run_x, "a1")
    with rejected("platform identitas"):
        Post.objects.filter(pk=post.pk).update(platform="tiktok")
    with rejected("provenance"):
        Post.objects.filter(pk=post.pk).update(first_seen_run=run_tt)
    with rejected("tidak dapat dicabut"):
        ActorAccount.objects.filter(pk=actor.pk).update(
            identity_status=IdentityStatus.NEEDS_VERIFICATION
        )


def test_identity_cannot_be_deleted(run_x) -> None:
    post = make_post(run_x, "p1")
    with rejected("tidak dapat dihapus"):
        post.delete()


def test_identity_cannot_be_created_on_a_run_of_another_platform(run_x) -> None:
    with rejected("tidak boleh dibuat pada run platform"):
        Post.objects.create(platform="tiktok", external_post_id="1", first_seen_run=run_x)
    with rejected("tidak boleh dibuat pada run platform"):
        ActorAccount.objects.create(platform="tiktok", external_actor_id="1", first_seen_run=run_x)


def test_identity_has_provenance_run(run_x) -> None:
    assert make_post(run_x, "p1").first_seen_run_id == run_x.pk  # NFR-05


# =============================== PostObservation ===============================


def test_reinspection_appends_an_observation_without_touching_the_old_one(
    target_x, run_x, user
) -> None:
    post = make_post(run_x, "p1")
    first = observe(post, run_x, text="versi awal", published_at=PUBLISHED)
    run2 = services.create_inspection_run(target=target_x, user=user, requested=CAPS)
    second = observe(post, run2, text="versi diedit", published_at=PUBLISHED,
                     observed_at=OBSERVED + timedelta(hours=1))

    assert Post.objects.count() == 1  # NFR-03: identitas tidak digandakan
    assert post.observations.count() == 2
    first.refresh_from_db()
    assert first.text == "versi awal"  # observasi lama utuh
    assert second.text == "versi diedit"


def test_one_observation_per_post_per_run(run_x) -> None:
    post = make_post(run_x, "p1")
    observe(post, run_x)
    with pytest.raises(IntegrityError), transaction.atomic():
        observe(post, run_x)


def test_observations_are_append_only_in_code_and_in_the_database(run_x) -> None:
    post = make_post(run_x, "p1")
    obs = observe(post, run_x, text="asli")
    obs.text = "diubah"
    with pytest.raises(AppendOnlyViolation):
        obs.save()
    with pytest.raises(AppendOnlyViolation):
        obs.delete()
    with rejected("append-only"):
        PostObservation.objects.filter(pk=obs.pk).update(text="diubah")
    with rejected("append-only"):
        PostObservation.objects.filter(pk=obs.pk)._raw_delete(PostObservation.objects.db)
    assert PostObservation.objects.get(pk=obs.pk).text == "asli"


def test_published_at_is_separate_from_observed_and_captured_times(run_x) -> None:
    post = make_post(run_x, "p1")
    obs = observe(post, run_x, published_at=PUBLISHED, captured_at=OBSERVED + timedelta(seconds=3))
    assert len({obs.published_at, obs.observed_at, obs.captured_at}) == 3


def test_unknown_values_stay_null(run_x) -> None:
    post = make_post(run_x, "p1")
    obs = observe(post, run_x)
    assert (obs.published_at, obs.captured_at, obs.text, obs.author) == (None, None, None, None)


def test_none_text_and_empty_text_are_different(run_x) -> None:
    a, b = make_post(run_x, "a"), make_post(run_x, "b")
    assert observe(a, run_x, text=None).text is None
    assert observe(b, run_x, text="").text == ""


def test_published_equal_to_observed_is_rejected_by_the_database(run_x) -> None:
    post = make_post(run_x, "p1")
    with pytest.raises(IntegrityError), transaction.atomic():
        observe(post, run_x, published_at=OBSERVED)


def test_published_in_the_future_is_rejected_by_the_database(run_x) -> None:
    post = make_post(run_x, "p1")
    with pytest.raises(IntegrityError), transaction.atomic():
        observe(post, run_x, published_at=OBSERVED + timedelta(minutes=1))


def test_invalid_enum_values_are_rejected_by_the_database(run_x) -> None:
    post = make_post(run_x, "p1")
    with pytest.raises(IntegrityError), transaction.atomic():
        observe(post, run_x, source_object_type="story")
    with pytest.raises(IntegrityError), transaction.atomic():
        observe(post, run_x, collection_status="DONE")


def test_observation_cannot_cross_platforms(run_x, run_tt) -> None:
    """Isolasi platform dijaga DB: post/penulis platform lain pada run ini ditolak (NFR-06)."""
    tiktok_post, tiktok_actor = make_post(run_tt, "t1"), make_actor(run_tt, "t-actor")
    x_post, x_actor = make_post(run_x, "x1"), make_actor(run_x, "x-actor")
    with rejected("observasi post platform"):
        observe(tiktok_post, run_x)
    with rejected("penulis platform"):
        observe(x_post, run_x, author=tiktok_actor)
    assert observe(x_post, run_x, author=x_actor).author_id == x_actor.pk


# =============================== PostRelation ===============================


def relate(run, a, kind, to_post=None, to_actor=None) -> PostRelation:
    return PostRelation.objects.create(
        run=run, from_post=a, relation_type=kind, to_post=to_post, to_actor=to_actor
    )


def test_reply_relation_and_mention_relation(run_x) -> None:
    parent, reply = make_post(run_x, "p0"), make_post(run_x, "p1")
    actor = make_actor(run_x, "a1")
    assert relate(run_x, reply, RelationType.REPLY_TO, to_post=parent).to_post == parent
    assert relate(run_x, reply, RelationType.MENTIONS, to_actor=actor).to_actor == actor


@pytest.mark.parametrize("kind", ["reply_to", "quote_of", "repost_of"])
def test_post_relations_need_a_target_post_and_no_actor(run_x, kind) -> None:
    a, b = make_post(run_x, "a"), make_post(run_x, "b")
    actor = make_actor(run_x, "x")
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, kind, to_actor=actor)
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, kind)
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, kind, to_post=b, to_actor=actor)


def test_mention_needs_an_actor_and_no_post(run_x) -> None:
    a, b = make_post(run_x, "a"), make_post(run_x, "b")
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, "mentions", to_post=b)


def test_relation_to_itself_and_unknown_types_are_rejected(run_x) -> None:
    a = make_post(run_x, "a")
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, "reply_to", to_post=a)
    b = make_post(run_x, "b")
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, "friend_of", to_post=b)


def test_a_reply_has_a_single_parent_per_run(run_x) -> None:
    reply, p1, p2 = make_post(run_x, "r"), make_post(run_x, "p1"), make_post(run_x, "p2")
    relate(run_x, reply, "reply_to", to_post=p1)
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, reply, "reply_to", to_post=p2)


def test_duplicate_relation_in_one_run_is_rejected(run_x) -> None:
    a, b = make_post(run_x, "a"), make_post(run_x, "b")
    relate(run_x, a, "quote_of", to_post=b)
    with pytest.raises(IntegrityError), transaction.atomic():
        relate(run_x, a, "quote_of", to_post=b)


def test_relation_history_is_kept_per_run_including_parent_changes(target_x, run_x, user) -> None:
    reply, p1, p2 = make_post(run_x, "r"), make_post(run_x, "p1"), make_post(run_x, "p2")
    relate(run_x, reply, "reply_to", to_post=p1)
    run2 = services.create_inspection_run(target=target_x, user=user, requested=CAPS)
    relate(run2, reply, "reply_to", to_post=p2)  # induk teramati berbeda pada run berikutnya
    history = list(PostRelation.objects.filter(from_post=reply).order_by("run__sequence"))
    assert [r.to_post_id for r in history] == [p1.pk, p2.pk]


def test_relations_cannot_cross_platforms(run_x, run_tt) -> None:
    x_post, x_actor = make_post(run_x, "x1"), make_actor(run_x, "xa")
    tt_post, tt_actor = make_post(run_tt, "t1"), make_actor(run_tt, "ta")
    with rejected("relasi dari post platform lain"):
        relate(run_x, tt_post, "reply_to", to_post=x_post)
    with rejected("relasi ke post platform lain"):
        relate(run_x, x_post, "reply_to", to_post=tt_post)
    with rejected("relasi ke akun platform lain"):
        relate(run_x, x_post, "mentions", to_actor=tt_actor)
    assert relate(run_x, x_post, "mentions", to_actor=x_actor)


def test_relations_are_append_only(run_x) -> None:
    a, b = make_post(run_x, "a"), make_post(run_x, "b")
    rel = relate(run_x, a, "quote_of", to_post=b)
    with pytest.raises(AppendOnlyViolation):
        rel.delete()
    with rejected("append-only"):
        PostRelation.objects.filter(pk=rel.pk).update(relation_type="repost_of")


# =============================== keterkaitan investigasi ===============================


def test_one_post_can_appear_in_several_investigations_without_duplication(user) -> None:
    """PRD bagian 8, relasi 3: lewat run -> target -> investigasi, bukan duplikasi identitas."""
    inv_a = inv_services.create_investigation(user=user, name="A")
    inv_b = inv_services.create_investigation(user=user, name="B")
    inv_c = inv_services.create_investigation(user=user, name="C")
    ta = register(inv_a, user, Platform.X, "https://x.com/u/status/1")
    tb = register(inv_b, user, Platform.X, "https://x.com/v/status/2")
    run_a = services.create_inspection_run(target=ta, user=user, requested=CAPS)
    run_b = services.create_inspection_run(target=tb, user=user, requested=CAPS)

    shared = make_post(run_a, "shared-reply")
    observe(shared, run_a)
    observe(shared, run_b)  # percakapan lain memuat reply yang sama

    assert Post.objects.count() == 1
    assert list(Post.objects.observed_in_investigation(inv_a)) == [shared]
    assert list(Post.objects.observed_in_investigation(inv_b)) == [shared]
    assert list(Post.objects.observed_in_investigation(inv_c)) == []


def test_observed_in_investigation_does_not_return_duplicates(target_x, run_x, user, inv) -> None:
    post = make_post(run_x, "p1")
    observe(post, run_x)
    run2 = services.create_inspection_run(target=target_x, user=user, requested=CAPS)
    observe(post, run2, observed_at=OBSERVED + timedelta(hours=1))
    assert Post.objects.observed_in_investigation(inv).count() == 1


# =============================== proteksi dan indeks ===============================


def test_history_cannot_be_removed_through_protected_foreign_keys(run_x) -> None:
    post = make_post(run_x, "p1")
    observe(post, run_x)
    with pytest.raises((ProtectedError, DatabaseError)), transaction.atomic():
        run_x.target.delete()


def _indexes(table: str) -> set[tuple[str, ...]]:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return {tuple(c["columns"]) for c in constraints.values() if c["index"] or c["unique"]}


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("collection_postobservation", ("run_id", "source_object_type")),
        ("collection_postobservation", ("author_id", "run_id")),
        ("collection_postobservation", ("post_id", "observed_at")),
        ("collection_postobservation", ("post_id", "run_id")),
        ("collection_postrelation", ("run_id", "relation_type")),
        ("collection_postrelation", ("to_post_id", "relation_type")),
        ("collection_postrelation", ("from_post_id", "relation_type")),
        ("collection_inspectionrun", ("target_id", "sequence")),
        ("collection_post", ("platform", "external_post_id")),
        ("collection_actoraccount", ("platform", "external_actor_id")),
    ],
)
def test_expected_indexes_exist(table: str, columns: tuple[str, ...]) -> None:
    assert columns in _indexes(table), f"indeks {columns} tidak ada pada {table}"
