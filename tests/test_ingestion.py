"""WP-1.3: ingestion idempoten (FR-032; NFR-03, NFR-04, NFR-05; AT-02, AT-03; FR-026)."""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from collection import ingestion, services
from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    Capability,
    CollectionStatus,
    CollectorInfo,
    Coverage,
    InspectionOutcome,
    InspectionResult,
    Limitation,
    LimitationCode,
    Observation,
    SourceMethod,
    SourceObjectType,
)
from collection.ingestion import IngestionRejected, ingest_result
from collection.models import (
    ActorAccount,
    IdentityStatus,
    InspectionRun,
    Post,
    PostObservation,
    PostRelation,
)
from django.contrib.auth.models import User
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db

OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
O = InspectionOutcome  # noqa: E741
CAPS = [Capability.INSPECT_POST, Capability.INSPECT_REPLIES]


# --- fabrikasi --------------------------------------------------------------------------------


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Investigasi")


def register(inv, user, platform, url):
    return inv_services.register_target(
        investigation=inv, user=user, platform=platform, target_type=TargetType.POST, url=url
    )


@pytest.fixture
def target_x(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


def new_run(target, user) -> InspectionRun:
    return services.create_inspection_run(target=target, user=user, requested=CAPS)


@pytest.fixture
def run1(target_x, user) -> InspectionRun:
    return new_run(target_x, user)


def obs(run, post_id="r1", *, kind=SourceObjectType.REPLY, actor="a1", parent="root",
        text="isi", ago=10, status=CollectionStatus.COMPLETED, **kw) -> Observation:
    if kind in (SourceObjectType.POST,):
        parent = None
    fields = dict(
        platform=Platform(run.target.platform),
        source_object_type=kind,
        inspection_run_id=run.run_id,
        observed_at=OBSERVED,
        collection_status=status,
        source_method=SourceMethod.SYNTHETIC_FIXTURE,
        external_post_id=post_id,
        external_actor_id=actor,
        parent_post_id=parent,
        published_at=OBSERVED - timedelta(minutes=ago),
        text=text,
    )
    fields.update(kw)
    return Observation(**fields)


def make_result(run, observations=(), outcome=O.COMPLETED, displayed=None, limitations=(),
                artifacts=(), complete=True) -> InspectionResult:
    return InspectionResult(
        platform=Platform(run.target.platform),
        inspection_run_id=run.run_id,
        outcome=outcome,
        collector=CollectorInfo("uji", "0.1"),
        coverage=Coverage((Capability.INSPECT_REPLIES,), complete, displayed),
        observations=tuple(observations),
        limitations=tuple(limitations),
        artifacts=tuple(artifacts),
    )


def replies(run, ids, **kw) -> list[Observation]:
    return [obs(run, i, actor=f"actor-{n % 5}", text=f"balasan {i}", **kw) for n, i in enumerate(ids)]


def counts() -> dict[str, int]:
    return {
        "post": Post.objects.count(),
        "actor": ActorAccount.objects.count(),
        "observation": PostObservation.objects.count(),
        "relation": PostRelation.objects.count(),
    }


# --- penulisan dasar --------------------------------------------------------------------------


def test_ingest_creates_identities_observations_and_relations(run1) -> None:
    result = make_result(run1, [obs(run1, "r1", mentioned_actor_ids=("m1",)), obs(run1, "r2")],
                         displayed=2)
    report = ingest_result(run1, result)

    assert report.ok, report
    assert report.observations_created == 2
    assert Post.objects.filter(external_post_id__in=["r1", "r2"]).count() == 2
    assert Post.objects.filter(external_post_id="root").exists()  # induk yang hanya dirujuk
    assert ActorAccount.objects.filter(external_actor_id__in=["a1", "m1"]).count() == 2
    assert PostRelation.objects.filter(relation_type="reply_to").count() == 2
    assert PostRelation.objects.filter(relation_type="mentions").count() == 1


def test_provenance_is_recorded_on_every_row(run1) -> None:
    """NFR-05: setiap observasi dan identitas membawa run asalnya; run membawa sumbernya."""
    ingest_result(run1, make_result(run1, [obs(run1, "r1")], displayed=1))
    o = PostObservation.objects.get()
    assert o.run_id == run1.pk
    assert o.post.first_seen_run_id == run1.pk
    assert o.author.first_seen_run_id == run1.pk
    run1.refresh_from_db()
    assert (run1.collector_name, run1.collector_version) == ("uji", "0.1")
    assert run1.source_method == "synthetic_fixture"


def test_displayed_and_observed_counts_are_stored_separately(run1) -> None:
    """PRD bagian 9.3: jumlah yang ditampilkan platform bukan jumlah unik teramati."""
    result = make_result(run1, replies(run1, ["r1", "r2", "r3"]), displayed=50)
    report = ingest_result(run1, result)
    run1.refresh_from_db()
    assert run1.coverage["platform_displayed_count"] == 50
    assert run1.coverage["observed_reply_count"] == 3
    assert (report.platform_displayed_count, report.observed_reply_count) == (50, 3)


def test_limitations_and_coverage_are_persisted_for_partial_results(run1) -> None:
    lim = Limitation(LimitationCode.PAGINATION_INCOMPLETE, "halaman berikutnya gagal", Capability.INSPECT_REPLIES)
    result = make_result(
        run1, [obs(run1, "r1", status=CollectionStatus.PARTIAL)], O.PARTIAL, displayed=40,
        limitations=[lim], complete=False,
    )
    ingest_result(run1, result)
    run1.refresh_from_db()
    assert run1.limitations == [
        {"code": "PAGINATION_INCOMPLETE", "message": "halaman berikutnya gagal", "capability": "inspect_replies"}
    ]
    assert run1.coverage["pagination_complete"] is False
    assert PostObservation.objects.get().collection_status == "PARTIAL"


@pytest.mark.parametrize(
    ("outcome", "code"),
    [(O.ACCESS_RESTRICTED, LimitationCode.ACCESS_RESTRICTED), (O.FAILED, LimitationCode.PARSE_FAILED),
     (O.UNSUPPORTED, LimitationCode.UNSUPPORTED)],
)
def test_failure_results_are_recorded_not_dropped(run1, outcome, code) -> None:
    """FR-026, AT-14: kegagalan tercatat eksplisit, bukan 'nol respons'."""
    result = make_result(run1, [], outcome, limitations=[Limitation(code, "alasan")], complete=None)
    report = ingest_result(run1, result)
    assert report.ok and report.observations_created == 0
    run1.refresh_from_db()
    assert run1.limitations[0]["code"] == code.value
    assert run1.coverage["outcome"] == outcome.value
    assert counts() == {"post": 0, "actor": 0, "observation": 0, "relation": 0}


def test_genuinely_empty_post_is_recorded_with_platform_zero(run1) -> None:
    report = ingest_result(run1, make_result(run1, [], displayed=0))
    run1.refresh_from_db()
    assert report.ok and run1.coverage["platform_displayed_count"] == 0


# --- idempotensi (NFR-03) ---------------------------------------------------------------------


def test_reingesting_the_same_result_adds_nothing(run1) -> None:
    result = make_result(
        run1,
        [obs(run1, "r1", mentioned_actor_ids=("m1",)), obs(run1, "r2", parent="r1"),
         obs(run1, "q1", kind=SourceObjectType.QUOTE, parent=None, quoted_post_id="r1")],
        displayed=3,
    )
    first = ingest_result(run1, result)
    before = counts()
    second = ingest_result(run1, result)

    assert first.ok and second.ok, (first, second)
    assert counts() == before  # tidak ada baris baru di tabel mana pun
    assert second.observations_created == 0
    assert second.observations_duplicate == 3
    assert (second.posts_created, second.actors_created, second.relations_created) == (0, 0, 0)


def test_reingest_many_times_is_stable(run1) -> None:
    result = make_result(run1, replies(run1, [f"r{i}" for i in range(30)]), displayed=30)
    ingest_result(run1, result, batch_size=7)
    before = counts()
    for _ in range(3):
        assert ingest_result(run1, result, batch_size=11).ok
    assert counts() == before


# --- reinspection: AT-02, AT-03 ---------------------------------------------------------------


def test_AT02_AT03_second_run_adds_only_new_identities(target_x, user, run1) -> None:
    old = [f"r{i}" for i in range(20)]
    ingest_result(run1, make_result(run1, replies(run1, old), displayed=20))
    assert Post.objects.count() == 21  # 20 reply + 1 induk (root)

    run2 = new_run(target_x, user)
    new = [f"n{i}" for i in range(5)]
    report = ingest_result(run2, make_result(run2, replies(run2, old + new), displayed=25))

    assert report.ok
    assert Post.objects.count() == 26  # +5, bukan +25 (PRD bagian 9.2)
    assert report.posts_created == 5
    assert PostObservation.objects.filter(run=run1).count() == 20  # run lama utuh
    assert PostObservation.objects.filter(run=run2).count() == 25
    assert ActorAccount.objects.count() == 5  # penulis dipakai ulang


def test_edited_content_creates_a_new_observation_and_keeps_the_old(target_x, user, run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", text="versi awal")], displayed=1))
    run2 = new_run(target_x, user)
    ingest_result(run2, make_result(run2, [obs(run2, "r1", text="versi diedit")], displayed=1))

    assert Post.objects.filter(external_post_id="r1").count() == 1
    texts = list(
        PostObservation.objects.filter(post__external_post_id="r1")
        .order_by("run__sequence").values_list("text", flat=True)
    )
    assert texts == ["versi awal", "versi diedit"]


def test_object_missing_from_a_later_run_is_not_deleted(target_x, user, run1) -> None:
    ingest_result(run1, make_result(run1, replies(run1, ["r1", "r2"]), displayed=2))
    run2 = new_run(target_x, user)
    ingest_result(run2, make_result(run2, replies(run2, ["r1"]), displayed=1))
    assert Post.objects.filter(external_post_id="r2").exists()
    assert PostObservation.objects.filter(post__external_post_id="r2").count() == 1


# --- konflik: tidak pernah menimpa ------------------------------------------------------------


def test_conflicting_content_on_the_same_run_is_reported_and_not_overwritten(run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", text="asli")], displayed=1))
    conflicting = make_result(run1, [obs(run1, "r1", text="berbeda")], displayed=1)
    report = ingest_result(run1, conflicting)

    assert not report.ok
    assert "OBSERVATION_CONFLICT" in report.problem_codes()
    assert PostObservation.objects.get().text == "asli"


def test_conflicting_parent_on_the_same_run_is_reported(run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", parent="root")], displayed=1))
    # Observasi identik kecuali induk: konten sama, relasi berbeda.
    report = ingest_result(run1, make_result(run1, [obs(run1, "r1", parent="lain")], displayed=1))
    assert "RELATION_CONFLICT" in report.problem_codes()
    assert PostRelation.objects.get(relation_type="reply_to").to_post.external_post_id == "root"


def test_conflicting_run_metadata_is_not_overwritten(run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1")], displayed=1))
    different = make_result(run1, [obs(run1, "r1")], displayed=999)
    report = ingest_result(run1, different)
    run1.refresh_from_db()
    assert "METADATA_CONFLICT" in report.problem_codes()
    assert run1.coverage["platform_displayed_count"] == 1


# --- identitas: kandidat, penanda, referensi --------------------------------------------------


def candidate(run, text="Bagus!", handle="@anon") -> Observation:
    return obs(run, None, actor=None, parent="root", text=text, actor_handle=handle,
               identity_needs_verification=True)


def test_objects_without_id_become_unverified_candidates_never_merged(run1) -> None:
    result = make_result(run1, [candidate(run1), candidate(run1)], displayed=2)
    report = ingest_result(run1, result)

    assert report.candidates_created == 2
    candidates = Post.objects.filter(external_post_id__isnull=True)
    assert candidates.count() == 2  # dua objek serupa tetap dua baris
    assert set(candidates.values_list("identity_status", flat=True)) == {IdentityStatus.NEEDS_VERIFICATION}
    assert Post.objects.verified().filter(external_post_id__isnull=True).count() == 0
    assert PostObservation.objects.filter(author__isnull=True).count() == 2  # penulis tak diketahui
    assert ActorAccount.objects.count() == 0  # tidak ada baris aktor tanpa ID


def test_candidates_are_idempotent_within_a_run(run1) -> None:
    result = make_result(run1, [candidate(run1), candidate(run1), candidate(run1, text="Lain")], displayed=3)
    ingest_result(run1, result)
    before = counts()
    report = ingest_result(run1, result)
    assert report.ok and counts() == before
    assert report.observations_duplicate == 3


def test_candidates_are_not_matched_across_runs(target_x, user, run1) -> None:
    """Tanpa ID tidak ada kunci aman: tiap run membuat kandidat baru (lihat ADR 0007/0008)."""
    ingest_result(run1, make_result(run1, [candidate(run1)], displayed=1))
    run2 = new_run(target_x, user)
    ingest_result(run2, make_result(run2, [candidate(run2)], displayed=1))
    assert Post.objects.filter(external_post_id__isnull=True).count() == 2


def test_flagged_observation_creates_unverified_identities_but_keeps_existing_ones(
    target_x, user, run1
) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", actor="a1")], displayed=1))
    run2 = new_run(target_x, user)
    flagged = [
        obs(run2, "r1", actor="a1", identity_needs_verification=True),  # sudah ada: tetap VERIFIED
        obs(run2, "r2", actor="a2", identity_needs_verification=True),  # baru: perlu verifikasi
    ]
    ingest_result(run2, make_result(run2, flagged, displayed=2))
    status = lambda model, field, value: model.objects.get(**{field: value}).identity_status  # noqa: E731
    assert status(Post, "external_post_id", "r1") == IdentityStatus.VERIFIED
    assert status(Post, "external_post_id", "r2") == IdentityStatus.NEEDS_VERIFICATION
    assert status(ActorAccount, "external_actor_id", "a2") == IdentityStatus.NEEDS_VERIFICATION


def test_referenced_parent_gets_an_identity_but_no_observation(run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", parent="induk-tak-teramati")], displayed=1))
    parent = Post.objects.get(external_post_id="induk-tak-teramati")
    assert parent.identity_status == IdentityStatus.VERIFIED
    assert not parent.observations.exists()
    assert PostRelation.objects.get().to_post == parent


def test_unknown_parent_creates_no_relation(run1) -> None:
    o = obs(run1, "r1", parent=None, parent_unknown=True)
    ingest_result(run1, make_result(run1, [o], displayed=1))
    assert PostObservation.objects.get().parent_unknown is True
    assert PostRelation.objects.count() == 0


def test_quote_repost_and_mentions_are_recorded(run1) -> None:
    items = [
        obs(run1, "q1", kind=SourceObjectType.QUOTE, parent=None, quoted_post_id="orig"),
        obs(run1, "rp1", kind=SourceObjectType.REPOST, parent=None, reposted_post_id="orig"),
        obs(run1, "m1", kind=SourceObjectType.POST, mentioned_actor_ids=("x", "y", "x")),
    ]
    ingest_result(run1, make_result(run1, items, displayed=3))
    kinds = Counter_(PostRelation.objects.values_list("relation_type", flat=True))
    assert kinds == {"quote_of": 1, "repost_of": 1, "mentions": 2}  # penyebutan ganda disatukan


def Counter_(values):  # noqa: N802 - pembantu lokal
    from collections import Counter

    return dict(Counter(values))


# --- penolakan sebelum menulis ----------------------------------------------------------------


def test_result_of_another_platform_is_rejected_before_writing(run1, inv, user) -> None:
    tt = register(inv, user, Platform.TIKTOK, "https://tiktok.com/@u/video/1")
    run_tt = new_run(tt, user)
    foreign = make_result(run_tt, [obs(run_tt, "t1")], displayed=1)
    with pytest.raises(IngestionRejected, match="platform"):
        ingest_result(run1, foreign)
    assert counts() == {"post": 0, "actor": 0, "observation": 0, "relation": 0}


def test_result_of_another_run_is_rejected(target_x, user, run1) -> None:
    run2 = new_run(target_x, user)
    with pytest.raises(IngestionRejected, match="inspection_run_id"):
        ingest_result(run1, make_result(run2, [obs(run2, "r1")], displayed=1))
    assert counts()["observation"] == 0


@pytest.mark.parametrize("kwargs", [{"batch_size": 0}, {"batch_size": -1}, {"max_failed_batches": 0}])
def test_invalid_parameters_are_rejected(run1, kwargs) -> None:
    with pytest.raises(IngestionRejected):
        ingest_result(run1, make_result(run1, [], displayed=0), **kwargs)


def test_artifacts_are_never_dropped_silently(run1) -> None:
    shot = ArtifactCapture(ArtifactKind.SCREENSHOT, "a.png", b"x", "image/png")
    report = ingest_result(run1, make_result(run1, [obs(run1, "r1")], displayed=1, artifacts=[shot]))
    assert "ARTIFACTS_NOT_PERSISTED" in report.problem_codes()
    assert not report.ok  # pemanggil harus tahu ada yang belum tersimpan


# --- kegagalan sebagian (NFR-04) --------------------------------------------------------------


def fail_on_call(monkeypatch, name: str, n: int) -> None:
    real = getattr(ingestion, name)
    state = {"calls": 0}

    def wrapper(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] == n:
            raise RuntimeError("gangguan simulasi")
        return real(*args, **kwargs)

    monkeypatch.setattr(ingestion, name, wrapper)


def test_failed_batch_is_rolled_back_whole_and_marked_while_others_survive(
    monkeypatch, target_x, user, run1
) -> None:
    ids = [f"r{i}" for i in range(30)]
    # Data run sebelumnya harus tetap utuh.
    ingest_result(run1, make_result(run1, replies(run1, ["lama"]), displayed=1))
    before = counts()

    run2 = new_run(target_x, user)
    result = make_result(run2, replies(run2, ids), displayed=30)
    fail_on_call(monkeypatch, "_write_relations", 2)  # batch ke-2 dari 3
    report = ingest_result(run2, result, batch_size=10)

    assert not report.ok
    assert [(f.batch_index, f.first_observation, f.last_observation) for f in report.failed_batches] == [(1, 10, 19)]
    assert "gangguan simulasi" in report.failed_batches[0].error
    # Batch 1 dan 3 tersimpan; batch 2 tidak meninggalkan baris setengah jadi.
    stored = set(PostObservation.objects.filter(run=run2).values_list("post__external_post_id", flat=True))
    assert stored == set(ids[:10] + ids[20:])
    assert not Post.objects.filter(external_post_id__in=ids[10:20]).exists()
    assert report.observations_created == 20
    # Run sebelumnya tidak tersentuh.
    assert PostObservation.objects.filter(run=run1).count() == 1
    assert counts()["observation"] == before["observation"] + 20


def test_rerunning_ingestion_completes_what_a_failed_batch_left_behind(
    monkeypatch, target_x, user
) -> None:
    ids = [f"r{i}" for i in range(30)]
    run_a, run_b = new_run(target_x, user), new_run(target_x, user)

    # Acuan: ingestion tanpa gangguan pada run_a.
    ingest_result(run_a, make_result(run_a, replies(run_a, ids), displayed=30), batch_size=10)

    result_b = make_result(run_b, replies(run_b, ids), displayed=30)
    fail_on_call(monkeypatch, "_write_relations", 2)
    broken = ingest_result(run_b, result_b, batch_size=10)
    assert not broken.ok
    monkeypatch.undo()

    resumed = ingest_result(run_b, result_b, batch_size=10)  # jalankan ulang yang sama
    assert resumed.ok, resumed
    assert resumed.observations_created == 10  # hanya batch yang tertinggal
    assert resumed.observations_duplicate == 20
    for run in (run_a, run_b):
        assert PostObservation.objects.filter(run=run).count() == 30
        assert PostRelation.objects.filter(run=run).count() == 30


def test_ingestion_stops_after_too_many_failed_batches(monkeypatch, run1) -> None:
    real = ingestion._ingest_batch

    def always_fail(*args, **kwargs):
        raise RuntimeError("database mati")

    monkeypatch.setattr(ingestion, "_ingest_batch", always_fail)
    result = make_result(run1, replies(run1, [f"r{i}" for i in range(50)]), displayed=50)
    report = ingest_result(run1, result, batch_size=5, max_failed_batches=3)
    monkeypatch.setattr(ingestion, "_ingest_batch", real)

    assert len(report.failed_batches) == 3
    assert report.batches == 3  # tidak menghabiskan 10 batch
    assert "INGESTION_ABORTED" in report.problem_codes()
    assert counts()["observation"] == 0


def test_failed_batch_does_not_leak_partial_counts(monkeypatch, run1) -> None:
    fail_on_call(monkeypatch, "_write_relations", 1)
    report = ingest_result(run1, make_result(run1, replies(run1, ["r1", "r2"]), displayed=2))
    assert report.observations_created == 0 and report.posts_created == 0
    assert counts() == {"post": 0, "actor": 0, "observation": 0, "relation": 0}


# --- balapan, skala, dan biaya query ----------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_ingestion_of_overlapping_posts_creates_each_identity_once(target_x, user) -> None:
    ids = [f"shared-{i}" for i in range(60)]
    run_a, run_b = new_run(target_x, user), new_run(target_x, user)
    results = {
        run_a.pk: (run_a, make_result(run_a, replies(run_a, ids), displayed=60)),
        run_b.pk: (run_b, make_result(run_b, replies(run_b, ids), displayed=60)),
    }
    reports, errors = {}, []
    barrier = threading.Barrier(2)

    def worker(pk: int) -> None:
        run, result = results[pk]
        try:
            barrier.wait()
            reports[pk] = ingest_result(run, result, batch_size=10)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(pk,)) for pk in results]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not errors, errors
    assert all(r.ok for r in reports.values()), reports
    assert Post.objects.count() == 61  # 60 reply + 1 induk, masing-masing tepat sekali
    assert sum(r.posts_created for r in reports.values()) == 61  # tidak ada yang dihitung dua kali
    assert PostObservation.objects.count() == 120
    assert PostRelation.objects.count() == 120


def test_query_count_grows_linearly_with_batches_not_with_rows(target_x, user) -> None:
    def queries_for(n: int) -> int:
        run = new_run(target_x, user)
        result = make_result(run, replies(run, [f"b{n}-{i}" for i in range(n)]), displayed=n)
        with CaptureQueriesContext(connection) as ctx:
            assert ingest_result(run, result, batch_size=100).ok
        return len(ctx)

    q100, q400 = queries_for(100), queries_for(400)
    assert q100 <= 40, q100
    assert q400 <= 4 * q100, (q100, q400)  # tidak ada N+1


def test_large_result_is_ingested_correctly_and_quickly(run1) -> None:
    n = 2000
    ids = [f"big-{i}" for i in range(n)]
    result = make_result(run1, replies(run1, ids), displayed=n)
    started = time.perf_counter()
    report = ingest_result(run1, result, batch_size=500)
    elapsed = time.perf_counter() - started

    assert report.ok and report.observations_created == n
    assert PostObservation.objects.filter(run=run1).count() == n
    assert Post.objects.count() == n + 1
    assert elapsed < 60, f"ingestion {n} observasi memakan {elapsed:.1f}s"


# --- status ingestion pada run (mengenali ingestion yang terputus) -----------------------------


def test_run_that_was_never_ingested_has_no_ingestion_state(run1) -> None:
    run1.refresh_from_db()
    assert run1.ingestion is None


def test_successful_ingestion_is_recorded_on_the_run(run1) -> None:
    import json

    report = ingest_result(run1, make_result(run1, replies(run1, ["r1", "r2"]), displayed=2))
    run1.refresh_from_db()
    assert run1.ingestion["state"] == "FINISHED"
    assert run1.ingestion["report"]["observations_created"] == 2
    assert run1.ingestion["report"]["ok"] is True
    assert report.to_dict() == run1.ingestion["report"]
    json.dumps(run1.ingestion)  # dapat diserialisasi


def test_ingestion_with_problems_is_recorded_with_details(monkeypatch, target_x, user, run1) -> None:
    run2 = new_run(target_x, user)
    fail_on_call(monkeypatch, "_write_relations", 1)
    ingest_result(run2, make_result(run2, replies(run2, ["r1", "r2"]), displayed=2), batch_size=1)
    run2.refresh_from_db()
    assert run2.ingestion["state"] == "FINISHED_WITH_PROBLEMS"
    failed = run2.ingestion["report"]["failed_batches"]
    assert [f["batch_index"] for f in failed] == [0]
    assert "gangguan simulasi" in failed[0]["error"]


def test_conflict_is_recorded_as_finished_with_problems(run1) -> None:
    ingest_result(run1, make_result(run1, [obs(run1, "r1", text="asli")], displayed=1))
    ingest_result(run1, make_result(run1, [obs(run1, "r1", text="berbeda")], displayed=1))
    run1.refresh_from_db()
    assert run1.ingestion["state"] == "FINISHED_WITH_PROBLEMS"
    assert run1.ingestion["report"]["problems"][0]["code"] == "OBSERVATION_CONFLICT"


def test_interrupted_ingestion_leaves_an_in_progress_marker(monkeypatch, run1) -> None:
    """Proses mati sebelum selesai: tanpa penanda, run tampak lengkap padahal belum."""
    def crash(*args, **kwargs):
        raise RuntimeError("proses dimatikan")

    monkeypatch.setattr(ingestion, "_chunks", crash)
    with pytest.raises(RuntimeError, match="dimatikan"):
        ingest_result(run1, make_result(run1, replies(run1, ["r1"]), displayed=1))
    run1.refresh_from_db()
    assert run1.ingestion["state"] == "IN_PROGRESS"
    assert "started_at" in run1.ingestion
    assert run1.coverage is not None  # metadata sudah tercatat: inilah yang menyesatkan tanpa penanda


def test_reingest_after_interruption_finishes_and_clears_the_marker(monkeypatch, run1) -> None:
    result = make_result(run1, replies(run1, ["r1", "r2"]), displayed=2)
    real = ingestion._chunks
    monkeypatch.setattr(ingestion, "_chunks", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        ingest_result(run1, result)
    monkeypatch.setattr(ingestion, "_chunks", real)

    assert ingest_result(run1, result).ok
    run1.refresh_from_db()
    assert run1.ingestion["state"] == "FINISHED"


# --- WP-1.4: hash isi dan pernyataan ketidaktersediaan ----------------------------------------


def test_every_observation_row_stores_a_versioned_content_hash(run1) -> None:
    from collection.content import CONTENT_HASH_VERSION

    ingest_result(run1, make_result(run1, [obs(run1, "r1"), obs(run1, "r2", text=None)], displayed=2))
    for row in PostObservation.objects.all():
        assert len(row.content_hash) == 64 and row.content_hash_version == CONTENT_HASH_VERSION


def test_confirmed_unavailable_statements_are_persisted_on_the_run(run1) -> None:
    from collection.contracts import UnavailableObject

    result = InspectionResult(
        platform=Platform.X, inspection_run_id=run1.run_id, outcome=O.COMPLETED,
        collector=CollectorInfo("uji", "0.1"),
        coverage=Coverage((Capability.INSPECT_REPLIES,), True, 1),
        observations=(obs(run1, "r1"),),
        confirmed_unavailable=(UnavailableObject("r9", "komentar dihapus"),),
    )
    assert ingest_result(run1, result).ok
    run1.refresh_from_db()
    assert run1.coverage["confirmed_unavailable"] == [
        {"external_post_id": "r9", "evidence": "komentar dihapus"}
    ]
