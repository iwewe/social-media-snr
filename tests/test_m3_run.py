"""WP-2.3: profil aktor Level A pada AnalysisRun (FR-060..FR-065; AT-17)."""

from datetime import timedelta

import pytest
from collection.contracts import SourceObjectType
from collection.models import ActorAccount, InspectionRun
from collection_helpers import OBSERVED, ingest, new_run, obs, register
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from intelligence import assessment, profiles, services
from intelligence.errors import InvalidParameters
from intelligence.m2.example_rules import example_parameters
from intelligence.models import ActorIssueProfile, AnalysisRun, AnalysisStatus
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db
POST = SourceObjectType.POST
CUES = (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit"])
START = OBSERVED - timedelta(days=10)
END = OBSERVED


def ago(days: float):
    return OBSERVED - timedelta(days=days)


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Investigasi")


@pytest.fixture
def issue(inv, user):
    return inv_services.create_issue(investigation=inv, user=user, title="Kebakaran hutan")


@pytest.fixture
def p1(issue, user):
    return inv_services.add_proposition(issue=issue, user=user, statement="Perlu diaudit.")


@pytest.fixture
def target(inv, user, p1):
    return inv_services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        stances={p1: "CONTRA"},
    )


@pytest.fixture
def other_target(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/2")  # tidak pernah diperiksa


def _complete(run):
    InspectionRun.objects.filter(pk=run.pk).update(status="RUNNING")
    InspectionRun.objects.filter(pk=run.pk).update(status="COMPLETED")
    run.refresh_from_db()


@pytest.fixture
def conversation(target, user):
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(run, "seed", kind=POST, actor="a0", text="Perusahaan tidak perlu diaudit."),
            obs(
                run,
                "r1",
                actor="u1",
                parent="seed",
                text="Justru audit harus dilakukan.",
                published_at=ago(3),
            ),
            obs(
                run,
                "r2",
                actor="u1",
                parent="seed",
                text="Audit harus dilakukan.",
                published_at=ago(2),
            ),
            obs(
                run,
                "r3",
                actor="u1",
                parent="seed",
                text="Penulis ini bodoh.",
                published_at=ago(0.5),
            ),
            obs(
                run,
                "r4",
                actor="u2",
                parent="seed",
                text="Perusahaan itu tidak perlu diaudit.",
                published_at=ago(2.5),
            ),
            obs(
                run,
                "r5",
                actor=None,
                parent="seed",
                identity_needs_verification=True,
                text="Setuju sekali!",
                published_at=ago(1),
            ),
            obs(
                run,
                "r6",
                actor="u3",
                parent="seed",
                text="Justru audit harus dilakukan.",
                published_at=ago(20),
            ),
        ],
    )
    _complete(run)
    return run


def _m2(inv, user, issue, runs, p1):
    dataset = services.create_dataset_version(investigation=inv, runs=runs, by=user)
    run = services.create_analysis_run(
        dataset=dataset,
        method="m2-rules",
        parameters=example_parameters({p1.pk: CUES}),
        by=user,
        issue_context_version=services.latest_issue_context(issue),
        target_context_versions=services.latest_target_contexts(dataset),
    )
    done = services.execute_run(run)
    assert done.status == AnalysisStatus.COMPLETED
    return done


def _params(m2run, p1, **over):
    base = dict(
        source_run=m2run,
        proposition=p1,
        period_start=START,
        period_end=END,
        min_responses=2,
        bucket_hours=24,
        min_active_buckets=2,
        narrative_min_texts=2,
    )
    base.update(over)
    return profiles.m3_parameters(**base)


def _m3(user, m2run, issue, params, *, execute=True):
    dataset = m2run.dataset_version
    run = services.create_analysis_run(
        dataset=dataset,
        method="m3-profile",
        parameters=params,
        by=user,
        issue_context_version=services.latest_issue_context(issue),
        target_context_versions=services.latest_target_contexts(dataset),
    )
    return services.execute_run(run) if execute else run


@pytest.fixture
def m2run(inv, user, issue, p1, conversation):
    return _m2(inv, user, issue, [conversation], p1)


def _by_actor(run):
    return {p.actor.external_actor_id: p for p in run.profiles.select_related("actor")}


def test_profiles_are_built_per_account_from_observed_responses_only(
    user, issue, p1, m2run
) -> None:
    run = _m3(user, m2run, issue, _params(m2run, p1))
    assert run.status == AnalysisStatus.COMPLETED, run.error
    by = _by_actor(run)
    assert set(by) == {"u1", "u2"}  # u3 di luar periode; respons tanpa akun tidak diprofilkan
    assert run.output["profiles"] == 2 and run.output["responses_profiled"] == 4
    assert run.output["responses_without_author"] == 1
    assert run.output["responses_excluded_outside_period"] == 1
    u1 = by["u1"].dimensions
    assert u1["participation"]["responses"] == 3
    assert u1["participation"]["distinct_parent_posts"] == 1  # ketiganya membalas posting target
    assert u1["stance_distribution"]["counts"]["PRO"] == 2
    assert u1["stance_distribution"]["counts"]["UNDETERMINED"] == 1
    assert u1["response_character"]["counts"]["RC-05"] == 1
    assert [b["responses"] for b in u1["temporal_activity"]["buckets"]] == [1, 1, 1]
    assert u1["activity_evolution"]["active_buckets"] == 3
    assert by["u1"].level == "A" and by["u1"].source_run_id == m2run.pk


def test_dimensions_without_enough_data_say_so_instead_of_reporting_zero(
    user, issue, p1, m2run
) -> None:
    by = _by_actor(_m3(user, m2run, issue, _params(m2run, p1)))
    u2 = by["u2"].dimensions
    assert u2["participation"]["status"] == "OK" and u2["participation"]["responses"] == 1
    for name in (
        "stance_distribution",
        "response_character",
        "temporal_activity",
        "narrative_consistency",
        "activity_evolution",
    ):
        assert u2[name]["status"] == "INSUFFICIENT_DATA", name
    assert by["u1"].dimensions["target_concentration"]["status"] == "INSUFFICIENT_DATA"
    assert "satu target" in by["u1"].dimensions["target_concentration"]["reason"]


def test_AT17_coverage_states_partial_target_coverage_never_a_total_claim(
    user, issue, p1, m2run, target, other_target
) -> None:
    run = _m3(user, m2run, issue, _params(m2run, p1))
    for profile in run.profiles.all():
        cov = profile.coverage
        assert cov["statement"] and "bukan seluruh aktivitas akun" in cov["statement"]
        assert cov["partial_coverage"] is True
        assert cov["targets_covered"] == [target.pk]
        assert cov["targets_in_investigation"] == sorted([target.pk, other_target.pk])
        assert "1 dari 2 target" in cov["statement"]
        assert cov["level"] == "A" and cov["platform"] == "x"
        assert cov["period"]["start"] == START.isoformat()


def test_coverage_is_not_partial_when_every_target_was_inspected(user, issue, p1, m2run) -> None:
    cov = next(iter(_m3(user, m2run, issue, _params(m2run, p1)).profiles.all())).coverage
    assert cov["partial_coverage"] is False and "1 dari 1 target" in cov["statement"]


def test_incomplete_inspections_are_disclosed_in_coverage(
    inv, user, issue, p1, target, conversation
) -> None:
    partial = new_run(target, user)
    ingest(
        partial,
        [
            obs(
                partial,
                "r1",
                actor="u1",
                parent="seed",
                text="Audit harus dilakukan.",
                published_at=ago(1.5),
            )
        ],
        partial=True,
    )
    InspectionRun.objects.filter(pk=partial.pk).update(status="RUNNING")
    InspectionRun.objects.filter(pk=partial.pk).update(status="PARTIAL")
    m2 = _m2(inv, user, issue, [conversation, partial], p1)
    cov = next(iter(_m3(user, m2, issue, _params(m2, p1)).profiles.all())).coverage
    assert cov["incomplete_runs"] == [{"run": partial.pk, "status": "PARTIAL"}]
    assert "tidak lengkap" in cov["statement"] and len(cov["runs_covered"]) == 2


def test_profiles_follow_human_review_and_a_changed_assessment_set_blocks_stale_runs(
    inv, user, issue, p1, m2run
) -> None:
    stale = _params(m2run, p1)
    row = next(
        a
        for a in assessment.current_assessments(m2run).select_related("observation__post")
        if a.observation.post.external_post_id == "r3"
    )
    assessment.review_assessment(
        assessment=row, by=user, reason="Ada stance tersirat.", issue_stance="CONTRA"
    )
    failed = _m3(user, m2run, issue, stale)  # parameter dibuat sebelum tinjauan
    assert failed.status == AnalysisStatus.FAILED and "penilaian M2 berubah" in failed.error
    assert not ActorIssueProfile.objects.filter(analysis_run=failed).exists()
    fresh = _m3(user, m2run, issue, _params(m2run, p1))
    assert _by_actor(fresh)["u1"].dimensions["stance_distribution"]["counts"]["CONTRA"] == 1


def test_same_inputs_give_identical_profiles(user, issue, p1, m2run) -> None:
    a = _m3(user, m2run, issue, _params(m2run, p1))
    b = _m3(user, m2run, issue, _params(m2run, p1))
    assert (
        a.output["profiles_digest"] == b.output["profiles_digest"]
        and a.output_digest == b.output_digest
    )


def test_period_filter_excludes_late_responses_but_keeps_unknown_times(
    user, issue, p1, m2run
) -> None:
    narrow = _params(m2run, p1, period_start=ago(2.2), period_end=ago(0.2))
    by = _by_actor(_m3(user, m2run, issue, narrow))
    assert (
        by["u1"].dimensions["participation"]["responses"] == 2
    )  # hari -2 dan -0,5; hari -3 di luar
    assert "u2" not in by  # hari -2,5 di luar


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("min_responses"),
        lambda p: p.update(extra=1),
        lambda p: p.update(min_responses=0),
        lambda p: p.update(min_responses=True),
        lambda p: p.update(bucket_hours=0),
        lambda p: p.update(min_active_buckets=1),
        lambda p: p.update(narrative_min_texts=1),
        lambda p: p.update(period_start="2026-10-01T00:00:00"),  # tanpa zona waktu
        lambda p: p.update(period_start="bukan-waktu"),
        lambda p: p.update(period_end=p["period_start"]),
        lambda p: p.update(assessments_digest="xyz"),
    ],
)
def test_parameters_are_validated_strictly(user, issue, p1, m2run, mutate) -> None:
    params = _params(m2run, p1)
    mutate(params)
    with pytest.raises(InvalidParameters):
        _m3(user, m2run, issue, params, execute=False)


def test_source_run_must_be_a_completed_m2_run_on_the_same_dataset(
    inv, user, issue, p1, target, m2run
) -> None:
    dataset = m2run.dataset_version

    def make(method, parameters):
        return services.create_analysis_run(
            dataset=dataset,
            method=method,
            parameters=parameters,
            by=user,
            issue_context_version=None,
            target_context_versions=services.latest_target_contexts(dataset),
        )

    def failed_with(source, fragment):
        params = _params(m2run, p1)
        params["source_run"] = source.pk
        params["assessments_digest"] = profiles.digest_ids(
            []
        )  # lolos pemeriksaan hash: tak ada penilaian
        run = _m3(user, m2run, issue, params)
        assert run.status == AnalysisStatus.FAILED and fragment in run.error, run.error

    # selesai TETAPI bukan M2: hanya pemeriksaan metode yang dapat menolaknya
    completed_summary = services.execute_run(make("dataset-summary", {"top_authors": 1}))
    assert completed_summary.status == AnalysisStatus.COMPLETED
    failed_with(completed_summary, "run M2 selesai")
    # M2 TETAPI belum selesai: hanya pemeriksaan status yang dapat menolaknya
    unfinished_m2 = make("m2-rules", example_parameters({p1.pk: CUES}))
    failed_with(unfinished_m2, "run M2 selesai")
    # M2 selesai pada dataset LAIN
    second = new_run(target, user)
    ingest(second, [obs(second, "x1", actor="u9", parent="seed", text="halo")])
    _complete(second)
    other_dataset_m2 = _m2(inv, user, issue, [second], p1)
    foreign = _params(m2run, p1)
    foreign["source_run"] = other_dataset_m2.pk
    foreign["assessments_digest"] = _params(other_dataset_m2, p1)["assessments_digest"]
    failed = _m3(user, m2run, issue, foreign)
    assert failed.status == AnalysisStatus.FAILED and "dataset yang sama" in failed.error
    ghost = _params(m2run, p1)
    ghost["source_run"] = 999999
    assert _m3(user, m2run, issue, ghost).status == AnalysisStatus.FAILED


def test_failed_method_leaves_no_profile_rows(user, issue, p1, m2run, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("rusak")

    monkeypatch.setattr(profiles, "build_dimensions", boom)
    run = _m3(user, m2run, issue, _params(m2run, p1))
    assert run.status == AnalysisStatus.FAILED and not ActorIssueProfile.objects.exists()


# --- penjaga database -------------------------------------------------------------------------


def _insert(run, m2run, p1, actor, **over):
    fields = dict(
        analysis_run=run,
        source_run=m2run,
        actor=actor,
        proposition=p1,
        level="A",
        period_start=START,
        period_end=END,
        dimensions={},
        coverage={"statement": "x", "targets_covered": []},
    )
    fields.update(over)
    return ActorIssueProfile(**fields)


def _pending_m3(user, m2run, issue, p1):
    run = _m3(user, m2run, issue, _params(m2run, p1), execute=False)
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    return run


def _fresh_actor():
    """Akun yang belum punya profil pada run mana pun (u3: di luar periode), agar yang menolak
    benar-benar trigger, bukan constraint unik."""
    return ActorAccount.objects.get(platform="x", external_actor_id="u3")


def _running(user, m2run, issue, p1, method="m3-profile"):
    dataset = m2run.dataset_version
    if method == "m3-profile":
        return _pending_m3(user, m2run, issue, p1)
    run = services.create_analysis_run(
        dataset=dataset,
        method=method,
        parameters={"top_authors": 1},
        by=user,
        issue_context_version=None,
        target_context_versions=services.latest_target_contexts(dataset),
    )
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    return run


def test_profiles_are_refused_when_the_run_is_not_running(user, issue, p1, m2run) -> None:
    done = _m3(user, m2run, issue, _params(m2run, p1))  # COMPLETED
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(done, m2run, p1, _fresh_actor()).save()
    pending = _m3(user, m2run, issue, _params(m2run, p1), execute=False)  # PENDING
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(pending, m2run, p1, _fresh_actor()).save()


def test_profiles_are_refused_for_a_running_run_of_another_method(user, issue, p1, m2run) -> None:
    other = _running(user, m2run, issue, p1, method="dataset-summary")  # RUNNING tetapi bukan M3
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(other, m2run, p1, _fresh_actor()).save()
    ok = _running(user, m2run, issue, p1)
    _insert(ok, m2run, p1, _fresh_actor()).save()  # kontrol: run M3 RUNNING menerimanya


def test_profile_rows_are_append_only(user, issue, p1, m2run) -> None:
    pk = _m3(user, m2run, issue, _params(m2run, p1)).profiles.first().pk
    for sql in (
        "UPDATE intelligence_actorissueprofile SET level = 'A' WHERE id = %s",
        "UPDATE intelligence_actorissueprofile SET coverage = '{}'::jsonb WHERE id = %s",
        "DELETE FROM intelligence_actorissueprofile WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [pk])


@pytest.mark.parametrize(
    "coverage",
    [
        {},
        {"targets_covered": []},
        {"statement": "", "targets_covered": []},
        {"statement": "x"},
        {"statement": "x", "targets_covered": "bukan daftar"},
        [],
        "teks",
    ],
)
def test_coverage_statement_is_mandatory_at_the_database(user, issue, p1, m2run, coverage) -> None:
    run = _pending_m3(user, m2run, issue, p1)
    actor = ActorAccount.objects.filter(platform="x").first()
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, p1, actor, coverage=coverage).save()


def test_level_b_does_not_exist_and_dimensions_must_be_an_object(user, issue, p1, m2run) -> None:
    run = _pending_m3(user, m2run, issue, p1)
    actor = ActorAccount.objects.filter(platform="x").first()
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, p1, actor, level="B").save()
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, p1, actor, dimensions=[]).save()


def test_accounts_of_another_platform_never_enter_a_profile(inv, user, issue, p1, m2run) -> None:
    run = _pending_m3(user, m2run, issue, p1)
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/9")
    trun = new_run(tiktok, user)
    ingest(trun, [obs(trun, "t1", actor="tt-1", parent="tiktok-root", text="halo")])
    foreign = ActorAccount.objects.get(platform="tiktok", external_actor_id="tt-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, p1, foreign).save()


def test_one_profile_per_account_and_run(user, issue, p1, m2run) -> None:
    run = _pending_m3(user, m2run, issue, p1)
    actor = _fresh_actor()
    _insert(run, m2run, p1, actor).save()
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, p1, actor).save()


def test_source_run_must_be_a_completed_m2_run_on_the_same_dataset_at_the_database(
    inv, user, issue, p1, target, m2run
) -> None:
    run = _running(user, m2run, issue, p1)
    dataset = m2run.dataset_version
    # (a) selesai tetapi BUKAN M2
    summary = services.create_analysis_run(
        dataset=dataset,
        method="dataset-summary",
        parameters={"top_authors": 1},
        by=user,
        issue_context_version=None,
        target_context_versions=services.latest_target_contexts(dataset),
    )
    completed_summary = services.execute_run(summary)
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, completed_summary, p1, _fresh_actor()).save()
    # (b) M2 tetapi BELUM selesai
    unfinished = services.create_analysis_run(
        dataset=dataset,
        method="m2-rules",
        parameters=example_parameters({p1.pk: CUES}),
        by=user,
        issue_context_version=None,
        target_context_versions=services.latest_target_contexts(dataset),
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, unfinished, p1, _fresh_actor()).save()
    # (c) M2 selesai pada dataset LAIN
    second = new_run(target, user)
    ingest(second, [obs(second, "x1", actor="u9", parent="seed", text="halo")])
    _complete(second)
    foreign = _m2(inv, user, issue, [second], p1)
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, foreign, p1, _fresh_actor()).save()
    _insert(run, m2run, p1, _fresh_actor()).save()  # kontrol: sumber yang sah diterima


def test_proposition_must_belong_to_the_runs_investigation(user, issue, p1, m2run) -> None:
    run = _running(user, m2run, issue, p1)
    other = inv_services.create_investigation(user=user, name="Lain")
    other_issue = inv_services.create_issue(investigation=other, user=user, title="Isu lain")
    foreign = inv_services.add_proposition(issue=other_issue, user=user, statement="Klaim lain")
    with pytest.raises(DatabaseError), transaction.atomic():
        _insert(run, m2run, foreign, _fresh_actor()).save()


def test_guard_function_does_not_freeze_a_seqscan_plan() -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT proconfig FROM pg_proc WHERE proname = 'snr_profile_guard'")
        (config,) = cur.fetchone()
    assert "enable_seqscan=off" in config


def test_FR065_profile_model_has_no_verdict_or_personality_fields() -> None:
    names = {f.name for f in ActorIssueProfile._meta.get_fields()}
    for word in (
        "buzzer",
        "score",
        "skor",
        "personality",
        "kepribadian",
        "verdict",
        "vonis",
        "label",
    ):
        assert not any(word in n for n in names), (word, names)
