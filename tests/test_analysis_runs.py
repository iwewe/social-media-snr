"""WP-2.1: DatasetVersion, AnalysisRun, pembekuan konteks, reproduksibilitas (FR-014, FR-041, NFR-01, AT-07)."""

import pytest
from collection.models import PostObservation
from collection_helpers import ingest, new_run, obs, register, replies
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from intelligence import methods, services
from intelligence.digest import digest_ids, digest_json
from intelligence.errors import (
    InvalidParameters,
    InvalidSelection,
    NothingNew,
    UnknownMethod,
)
from intelligence.models import (
    AnalysisRun,
    AnalysisRunTargetContext,
    AnalysisStatus,
    DatasetVersion,
    DatasetVersionObservation,
)
from investigations import services as inv_services
from investigations.enums import Platform

pytestmark = pytest.mark.django_db
PARAMS = {"top_authors": 3}


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Investigasi")


@pytest.fixture
def issue(inv, user):
    return inv_services.create_issue(investigation=inv, user=user, title="Isu", definition="def 1")


@pytest.fixture
def target(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


@pytest.fixture
def run1(target, user):
    run = new_run(target, user)
    ingest(run, replies(run, [f"r{i}" for i in range(7)]))
    return run


def _dataset(inv, runs, user):
    return services.create_dataset_version(investigation=inv, runs=runs, by=user)


def _analysis(dataset, user, issue=None, params=PARAMS):
    return services.create_analysis_run(
        dataset=dataset,
        method="dataset-summary",
        parameters=params,
        by=user,
        issue_context_version=services.latest_issue_context(issue),
        target_context_versions=services.latest_target_contexts(dataset),
    )


def _raw_fails(sql: str, params: list | None = None) -> None:
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
        cur.execute(sql, params or [])


# --- DatasetVersion ----------------------------------------------------------------------------


def test_dataset_version_freezes_observations_with_a_digest(inv, user, run1) -> None:
    ids = sorted(PostObservation.objects.filter(run=run1).values_list("id", flat=True))
    dataset = _dataset(inv, [run1], user)
    assert dataset.number == 1 and dataset.platform == "x" and dataset.sealed_at is not None
    assert dataset.observation_count == len(ids) == 7
    assert dataset.observation_digest == digest_ids(ids)
    assert sorted(dataset.members.values_list("observation_id", flat=True)) == ids
    assert dataset.selection["targets"] == [run1.target_id]
    run2 = new_run(run1.target, user)
    ingest(run2, replies(run2, ["r0", "r1", "x9"]))
    assert _dataset(inv, [run1, run2], user).number == 2


@pytest.mark.parametrize("case", ["empty", "duplicate", "not-ingested", "no-observations"])
def test_invalid_selection_is_rejected(inv, user, run1, case) -> None:
    fresh = new_run(run1.target, user)
    selections = {
        "empty": [],
        "duplicate": [run1, run1],
        "not-ingested": [run1, fresh],
        "no-observations": [_empty_ingested(run1.target, user)],
    }
    with pytest.raises(InvalidSelection):
        _dataset(inv, selections[case], user)
    assert not DatasetVersion.objects.exists()


def _empty_ingested(target, user):
    run = new_run(target, user)
    ingest(run, [], displayed=0)
    return run


def test_selection_never_mixes_platforms_or_investigations(inv, user, run1) -> None:
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/123")
    trun = new_run(tiktok, user)
    ingest(trun, replies(trun, ["t1", "t2"]))
    with pytest.raises(InvalidSelection, match="satu platform"):
        _dataset(inv, [run1, trun], user)
    assert _dataset(inv, [trun], user).platform == "tiktok"
    other = inv_services.create_investigation(user=user, name="Lain")
    with pytest.raises(InvalidSelection, match="investigasi yang sama"):
        _dataset(other, [run1], user)


def test_sealed_dataset_cannot_change_in_any_way(inv, user, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    table = DatasetVersion._meta.db_table
    for sql in (
        f"UPDATE {table} SET note = 'x' WHERE id = %s",
        f"UPDATE {table} SET observation_count = 1 WHERE id = %s",
        f"UPDATE {table} SET sealed_at = now() WHERE id = %s",
        f"DELETE FROM {table} WHERE id = %s",
    ):
        _raw_fails(sql, [dataset.pk])
    member = dataset.members.first()
    _raw_fails("DELETE FROM intelligence_datasetversionobservation WHERE id = %s", [member.pk])
    _raw_fails(
        "UPDATE intelligence_datasetversionobservation SET observation_id = observation_id WHERE id = %s",
        [member.pk],
    )
    run2 = new_run(run1.target, user)
    ingest(run2, replies(run2, ["new1"]))
    new_obs = PostObservation.objects.filter(run=run2).first()
    with pytest.raises(DatabaseError), transaction.atomic():
        DatasetVersionObservation.objects.create(dataset_version=dataset, observation=new_obs)
    dataset.refresh_from_db()
    assert dataset.members.count() == dataset.observation_count == 7


def test_sealing_requires_the_declared_member_count(inv, user, run1) -> None:
    ids = list(PostObservation.objects.filter(run=run1).values_list("id", flat=True))
    draft = DatasetVersion.objects.create(
        investigation=inv,
        platform="x",
        number=9,
        observation_count=3,
        observation_digest=digest_ids(ids[:3]),
        selection={"runs": [], "targets": []},
        created_by=user,
    )
    DatasetVersionObservation.objects.create(dataset_version=draft, observation_id=ids[0])
    with pytest.raises(DatabaseError), transaction.atomic():
        DatasetVersion.objects.filter(pk=draft.pk).update(sealed_at="2026-10-18T00:00:00Z")
    assert DatasetVersion.objects.get(pk=draft.pk).sealed_at is None


def test_dataset_cannot_be_created_already_sealed(inv, user) -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        DatasetVersion.objects.create(
            investigation=inv,
            platform="x",
            number=1,
            observation_count=1,
            observation_digest="0" * 64,
            selection={},
            created_by=user,
            sealed_at="2026-10-18T00:00:00Z",
        )


def test_members_must_share_platform_and_investigation(inv, user, run1) -> None:
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/9")
    trun = new_run(tiktok, user)
    ingest(trun, replies(trun, ["t1"]))
    other_inv = inv_services.create_investigation(user=user, name="Lain")
    other_target = register(other_inv, user, Platform.X, "https://x.com/u/status/77")
    orun = new_run(other_target, user)
    ingest(orun, replies(orun, ["o1"]))
    draft = DatasetVersion.objects.create(
        investigation=inv,
        platform="x",
        number=1,
        observation_count=1,
        observation_digest="0" * 64,
        selection={},
        created_by=user,
    )
    for foreign in (trun, orun):
        obs_id = PostObservation.objects.filter(run=foreign).values_list("id", flat=True)[0]
        with pytest.raises(DatabaseError), transaction.atomic():
            DatasetVersionObservation.objects.create(dataset_version=draft, observation_id=obs_id)


# --- AnalysisRun ---------------------------------------------------------------------------------


def test_run_is_created_pending_with_explicit_frozen_inputs(inv, user, issue, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    run = _analysis(dataset, user, issue)
    assert run.status == AnalysisStatus.PENDING and run.output is None
    assert run.method == "dataset-summary" and run.method_version == "1"
    assert run.parameters == PARAMS and run.parameters_digest == digest_json(PARAMS)
    assert run.issue_context_version.version == 1
    contexts = {c.target_id: c.context_version for c in run.target_contexts.all()}
    assert set(contexts) == {run1.target_id} and contexts[run1.target_id].version == 1


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"top_authors": 3, "extra": 1},
        {"top_authors": "3"},
        {"top_authors": True},
        {"top_authors": -1},
        {"top_authors": 1001},
        {"top": 3},
    ],
)
def test_parameters_are_mandatory_and_validated(inv, user, run1, params) -> None:
    with pytest.raises(InvalidParameters):
        _analysis(_dataset(inv, [run1], user), user, params=params)
    assert not AnalysisRun.objects.exists()


def test_unknown_method_and_incomplete_context_map_are_rejected(inv, user, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    with pytest.raises(UnknownMethod):
        services.create_analysis_run(
            dataset=dataset,
            method="buzzer-score",
            parameters={},
            by=user,
            issue_context_version=None,
            target_context_versions={},
        )
    with pytest.raises(InvalidSelection, match="setiap target"):
        services.create_analysis_run(
            dataset=dataset,
            method="dataset-summary",
            parameters=PARAMS,
            by=user,
            issue_context_version=None,
            target_context_versions={},
        )


def test_context_may_be_explicitly_absent(inv, user, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    run = services.create_analysis_run(
        dataset=dataset,
        method="dataset-summary",
        parameters=PARAMS,
        by=user,
        issue_context_version=None,
        target_context_versions={run1.target_id: None},
    )
    done = services.execute_run(run)
    assert done.output["issue_context_version"] is None
    assert done.output["target_context_versions"] == {str(run1.target_id): None}


def test_execution_lifecycle_and_summary_content(inv, user, issue, run1) -> None:
    run = _analysis(_dataset(inv, [run1], user), user, issue)
    done = services.execute_run(run)
    assert done.status == AnalysisStatus.COMPLETED
    assert done.started_at and done.finished_at and done.finished_at >= done.started_at
    assert done.output_digest == digest_json(done.output)
    out = done.output
    assert out["platform"] == "x" and out["observations"] == 7 and out["runs"] == 1
    assert out["posts"] == 7 and out["issue_context_version"] == 1
    assert out["target_context_versions"] == {str(run1.target_id): 1}
    assert out["by_type"] == {"reply": 7} and out["observations_without_author"] == 0
    # 7 balasan, penulis actor-0..4 secara bergilir: actor-0 dan actor-1 masing-masing 2 kali
    counts = sorted((a["observations"] for a in out["top_authors"]), reverse=True)
    assert counts == [2, 2, 1] and len(out["top_authors"]) == 3
    ids = [a["actor_id"] for a in out["top_authors"][:2]]
    assert ids == sorted(ids)  # seri diputus berdasarkan id, deterministik
    with pytest.raises(InvalidSelection, match="sudah dijalankan"):
        services.execute_run(run)


def test_failure_is_recorded_not_hidden(inv, user, run1, monkeypatch) -> None:
    def boom(frozen, parameters):
        raise RuntimeError("rusak")

    monkeypatch.setitem(
        methods.REGISTRY,
        "dataset-summary",
        methods.Method("dataset-summary", "1", methods._validate_summary, boom),
    )
    done = services.execute_run(_analysis(_dataset(inv, [run1], user), user))
    assert done.status == AnalysisStatus.FAILED and done.output is None
    assert "RuntimeError" in done.error and done.output_digest == ""


def test_AT07_context_revision_and_new_data_never_change_an_old_run(inv, user, issue, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    first = services.execute_run(_analysis(dataset, user, issue))
    inv_services.revise_issue_context(issue=issue, user=user, definition="def 2")
    inv_services.revise_target_context(target=run1.target, user=user, note="catatan baru")
    run2 = new_run(run1.target, user)
    ingest(run2, replies(run2, ["baru1", "baru2"]))
    first.refresh_from_db()
    assert first.issue_context_version.version == 1
    assert first.target_contexts.get().context_version.version == 1
    assert dataset.members.count() == 7
    # NFR-01: masukan sama -> keluaran identik, walau konteks dan data sudah berubah
    again = services.create_analysis_run(
        dataset=dataset,
        method="dataset-summary",
        parameters=PARAMS,
        by=user,
        issue_context_version=first.issue_context_version,
        target_context_versions={
            c.target_id: c.context_version for c in first.target_contexts.all()
        },
    )
    again = services.execute_run(again)
    assert again.output == first.output and again.output_digest == first.output_digest


# --- penjaga database untuk AnalysisRun -----------------------------------------------------


def test_run_inputs_are_locked_and_status_moves_forward_only(inv, user, issue, run1) -> None:
    table = AnalysisRun._meta.db_table
    run = _analysis(_dataset(inv, [run1], user), user, issue)
    # Tiap pengubahan masukan disertai transisi status yang SAH, agar yang diuji benar-benar kunci
    # kolom (bukan penjaga transisi atau check constraint yang kebetulan menolaknya juga).
    for column_change in (
        "parameters = '{\"top_authors\": 9}'::jsonb",
        "method = 'lain'",
        "method_version = '9'",
        "parameters_digest = repeat('b', 64)",
        "issue_context_version_id = NULL",
        "previous_run_id = id",
        "created_at = now() + interval '1 day'",
    ):
        _raw_fails(
            f"UPDATE {table} SET status = 'RUNNING', {column_change} WHERE id = %s", [run.pk]
        )
    # PENDING tidak boleh langsung COMPLETED, walau keluaran lengkap (check constraint terpenuhi)
    _raw_fails(
        f"UPDATE {table} SET status = 'COMPLETED', output = '{{}}'::jsonb, "
        "output_digest = repeat('a', 64) WHERE id = %s",
        [run.pk],
    )
    _raw_fails(f"DELETE FROM {table} WHERE id = %s", [run.pk])
    done = services.execute_run(run)
    for sql in (
        f"UPDATE {table} SET status = 'RUNNING' WHERE id = %s",
        f"UPDATE {table} SET status = 'FAILED', output = NULL, output_digest = '' WHERE id = %s",
        f"UPDATE {table} SET status = 'COMPLETED', output = '{{}}'::jsonb, "
        "output_digest = repeat('c', 64) WHERE id = %s",
    ):
        _raw_fails(sql, [done.pk])
    done.refresh_from_db()
    assert done.status == AnalysisStatus.COMPLETED


def test_output_exists_only_when_completed(inv, user, run1) -> None:
    run = _analysis(_dataset(inv, [run1], user), user)
    with pytest.raises(DatabaseError), transaction.atomic():
        AnalysisRun.objects.filter(pk=run.pk).update(
            status=AnalysisStatus.RUNNING, output={"x": 1}, output_digest="a" * 64
        )


def test_run_requires_a_sealed_dataset_of_the_same_investigation(inv, user, issue, run1) -> None:
    draft = DatasetVersion.objects.create(
        investigation=inv,
        platform="x",
        number=5,
        observation_count=1,
        observation_digest="0" * 64,
        selection={"runs": [], "targets": []},
        created_by=user,
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        _analysis(draft, user)
    other = inv_services.create_investigation(user=user, name="Lain")
    other_issue = inv_services.create_issue(investigation=other, user=user, title="Isu lain")
    dataset = _dataset(inv, [run1], user)
    with pytest.raises(DatabaseError), transaction.atomic():
        AnalysisRun.objects.create(
            public_id="00000000-0000-0000-0000-000000000001",
            investigation=other,
            dataset_version=dataset,
            method="dataset-summary",
            method_version="1",
            parameters=PARAMS,
            parameters_digest=digest_json(PARAMS),
            created_by=user,
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        AnalysisRun.objects.create(
            public_id="00000000-0000-0000-0000-000000000002",
            investigation=inv,
            dataset_version=dataset,
            issue_context_version=other_issue.context_versions.first(),
            method="dataset-summary",
            method_version="1",
            parameters=PARAMS,
            parameters_digest=digest_json(PARAMS),
            created_by=user,
        )


def test_target_context_rows_are_guarded(inv, user, run1) -> None:
    dataset = _dataset(inv, [run1], user)
    run = _analysis(dataset, user)
    row = run.target_contexts.get()
    _raw_fails("DELETE FROM intelligence_analysisruntargetcontext WHERE id = %s", [row.pk])
    other = register(inv, user, Platform.X, "https://x.com/u/status/2")
    other_ctx = other.context_versions.first()
    started = services.execute_run(_analysis(dataset, user))
    with pytest.raises(DatabaseError), transaction.atomic():  # setelah run dimulai
        AnalysisRunTargetContext.objects.create(
            run=started, target=other, context_version=other_ctx
        )
    fresh = _analysis(dataset, user)
    with pytest.raises(DatabaseError), transaction.atomic():  # versi konteks milik target lain
        AnalysisRunTargetContext.objects.create(
            run=fresh, target=other, context_version=row.context_version
        )
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/5")
    with pytest.raises(DatabaseError), transaction.atomic():  # platform target beda dari dataset
        AnalysisRunTargetContext.objects.create(run=fresh, target=tiktok, context_version=None)


# --- analisis ulang ------------------------------------------------------------------------------


def test_reanalysis_creates_new_dataset_and_run_and_leaves_the_old_untouched(
    inv, user, issue, run1
) -> None:
    first = services.execute_run(_analysis(_dataset(inv, [run1], user), user, issue))
    with pytest.raises(NothingNew):
        services.reanalyze(first, by=user)
    assert (
        DatasetVersion.objects.count() == 1
    )  # tidak ada dataset/run yatim bila tidak ada data baru
    assert AnalysisRun.objects.count() == 1
    inv_services.revise_issue_context(issue=issue, user=user, definition="def 2")
    run2 = new_run(run1.target, user)
    ingest(run2, replies(run2, ["r0", "baru1", "baru2"]))
    second = services.reanalyze(first, by=user)
    assert second.previous_run_id == first.pk and second.status == AnalysisStatus.PENDING
    assert second.dataset_version_id != first.dataset_version_id
    assert second.parameters == first.parameters and second.method == first.method
    assert (
        second.issue_context_version_id == first.issue_context_version_id
    )  # konteks lama dipertahankan
    done = services.execute_run(second)
    assert done.output["observations"] == 10 and done.output["posts"] == 9
    assert done.output["runs"] == 2
    first.refresh_from_db()
    assert first.status == AnalysisStatus.COMPLETED and first.output["observations"] == 7


def test_reanalysis_can_opt_into_latest_context(inv, user, issue, run1) -> None:
    first = services.execute_run(_analysis(_dataset(inv, [run1], user), user, issue))
    inv_services.revise_issue_context(issue=issue, user=user, definition="def 2")
    inv_services.revise_target_context(target=run1.target, user=user, note="baru")
    run2 = new_run(run1.target, user)
    ingest(run2, replies(run2, ["baru1"]))
    second = services.reanalyze(first, by=user, use_latest_context=True)
    assert second.issue_context_version.version == 2
    assert second.target_contexts.get().context_version.version == 2
    assert first.issue_context_version.version == 1


# --- stabilitas rencana trigger (ADR 0020) ----------------------------------------------------


def test_guard_functions_do_not_freeze_a_seqscan_plan() -> None:
    names = [
        "snr_dataset_version_guard",
        "snr_dataset_member_guard",
        "snr_analysis_run_guard",
        "snr_analysis_target_context_guard",
    ]
    with connection.cursor() as cur:
        cur.execute("SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(%s)", [names])
        found = dict(cur.fetchall())
    assert set(found) == set(names)
    assert all("enable_seqscan=off" in (cfg or []) for cfg in found.values())


def test_summary_counts_posts_runs_and_unknown_authors_separately(inv, user, run1) -> None:
    run2 = new_run(run1.target, user)
    ingest(run2, [obs(run2, "r0"), obs(run2, "u1", actor=None, identity_needs_verification=True)])
    out = services.execute_run(_analysis(_dataset(inv, [run1, run2], user), user)).output
    assert (out["observations"], out["posts"], out["runs"]) == (9, 8, 2)
    assert out["observations_without_author"] == 1 and out["by_type"] == {"reply": 9}


def test_sealing_cannot_smuggle_other_changes(inv, user, run1) -> None:
    ids = list(PostObservation.objects.filter(run=run1).values_list("id", flat=True))[:2]
    draft = DatasetVersion.objects.create(
        investigation=inv,
        platform="x",
        number=3,
        observation_count=2,
        observation_digest=digest_ids(ids),
        selection={"runs": [], "targets": []},
        created_by=user,
    )
    for i in ids:
        DatasetVersionObservation.objects.create(dataset_version=draft, observation_id=i)
    for change in ({"note": "diselundupkan"}, {"observation_digest": "f" * 64}, {"number": 4}):
        with pytest.raises(DatabaseError), transaction.atomic():
            DatasetVersion.objects.filter(pk=draft.pk).update(
                sealed_at="2026-10-18T00:00:00Z", **change
            )
    DatasetVersion.objects.filter(pk=draft.pk).update(sealed_at="2026-10-18T00:00:00Z")
    assert DatasetVersion.objects.get(pk=draft.pk).sealed_at is not None


def test_run_must_start_pending_and_previous_run_stays_in_the_investigation(
    inv, user, run1
) -> None:
    dataset = _dataset(inv, [run1], user)
    common = dict(
        investigation=inv,
        dataset_version=dataset,
        method="dataset-summary",
        method_version="1",
        parameters=PARAMS,
        parameters_digest=digest_json(PARAMS),
        created_by=user,
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        AnalysisRun.objects.create(
            public_id="00000000-0000-0000-0000-000000000003", status="RUNNING", **common
        )
    other = inv_services.create_investigation(user=user, name="Lain")
    other_target = register(other, user, Platform.X, "https://x.com/u/status/88")
    orun = new_run(other_target, user)
    ingest(orun, replies(orun, ["o1"]))
    foreign = services.execute_run(_analysis(_dataset(other, [orun], user), user))
    with pytest.raises(DatabaseError), transaction.atomic():
        AnalysisRun.objects.create(
            public_id="00000000-0000-0000-0000-000000000004", previous_run=foreign, **common
        )
