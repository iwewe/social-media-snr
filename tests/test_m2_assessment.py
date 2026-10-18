"""WP-2.2: penilaian M2 pada dataset beku, rantai induk nyata, tinjauan manusia (FR-050..FR-057)."""

import pytest
from collection.contracts import SourceObjectType
from collection_helpers import ingest, new_run, obs, register
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from intelligence import assessment, methods, services
from intelligence.errors import InvalidParameters
from intelligence.m2 import RulesClassifier
from intelligence.m2.example_rules import example_parameters
from intelligence.models import AnalysisRun, AnalysisStatus, ResponseAssessment
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db
POST = SourceObjectType.POST
CUES = (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit"])


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
    return inv_services.add_proposition(
        issue=issue, user=user, statement="Perusahaan yang diduga terkait perlu diaudit."
    )


@pytest.fixture
def target(inv, user, p1):
    return inv_services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        note="Posting menolak audit.",
        stances={p1: "CONTRA"},
    )


@pytest.fixture
def conversation(target, user):
    """Percakapan Lampiran A dengan balasan bertingkat (c1 -> c2 -> c4)."""
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(run, "seed", kind=POST, actor="a0", text="Perusahaan tidak perlu diaudit."),
            obs(run, "c1", actor="a1", parent="seed", text="Justru audit harus dilakukan."),
            obs(run, "c2", actor="a2", parent="c1", text="Setuju sekali!"),
            obs(run, "c3", actor="a3", parent="seed", text="Penulis ini bodoh."),
            obs(run, "c4", actor="a4", parent="c2", text="Setuju sekali!"),
            obs(run, "c5", actor="a5", parent="seed", text="Awas ya, urusannya bisa panjang."),
            obs(run, "c6", actor="a6", parent=None, parent_unknown=True, text="Setuju sekali!"),
            obs(run, "c7", actor="a7", parent="seed", text=None),
        ],
    )
    return run


def _params(p1):
    return example_parameters({p1.pk: CUES})


def _run_m2(inv, user, issue, runs, p1, *, params=None, execute=True):
    dataset = services.create_dataset_version(investigation=inv, runs=runs, by=user)
    run = services.create_analysis_run(
        dataset=dataset,
        method="m2-rules",
        parameters=params or _params(p1),
        by=user,
        issue_context_version=services.latest_issue_context(issue),
        target_context_versions=services.latest_target_contexts(dataset),
    )
    return services.execute_run(run) if execute else run


def _by_text(run):
    return {
        a.observation.post.external_post_id: a
        for a in assessment.current_assessments(run).select_related("observation__post")
    }


def test_run_assesses_every_response_with_the_real_parent_chain(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    assert run.status == AnalysisStatus.COMPLETED
    rows = _by_text(run)
    assert set(rows) == {"c1", "c2", "c3", "c4", "c5", "c6", "c7"}  # seed bukan respons
    c1, c2, c4 = rows["c1"], rows["c2"], rows["c4"]
    assert (c1.issue_stance, c1.target_alignment) == ("PRO", "OPPOSE")  # seed kontra (konteks beku)
    assert (c2.issue_stance, c2.target_alignment) == (
        "PRO",
        "SUPPORT",
    )  # AT-08: mengikuti c1, bukan seed
    assert (c4.issue_stance, c4.target_alignment) == (
        "PRO",
        "SUPPORT",
    )  # bertingkat: c4 -> c2 -> c1
    assert c2.basis["evidence"]["parent_observation_ids"][0] == c1.observation_id
    assert len(c4.basis["evidence"]["parent_observation_ids"]) == 3
    assert c2.basis["evidence"]["parent_stance_used"] == "PRO"
    assert c1.basis["evidence"]["parent_stance_used"] == "CONTRA"


def test_unknown_parent_and_missing_text_are_undetermined_not_guessed(
    inv, user, issue, p1, conversation
) -> None:
    rows = _by_text(_run_m2(inv, user, issue, [conversation], p1))
    c6, c7 = rows["c6"], rows["c7"]
    assert c6.issue_stance == "UNDETERMINED" and c6.basis["evidence"]["parent_unknown"] is True
    assert c7.issue_stance == "UNDETERMINED" and "text_unavailable" in c7.basis["rules"]
    c3 = rows["c3"]
    assert c3.issue_stance == "UNDETERMINED" and c3.response_character == ["RC-05"]


def test_intimidation_is_flagged_for_human_review_and_nothing_else_is(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    flagged = [a for a in assessment.current_assessments(run) if a.needs_human_review]
    assert [a.response_character for a in flagged] == [["RC-07"]]
    assert run.output["needs_human_review"] == 1


def test_narrative_function_is_not_claimed_by_the_baseline_and_output_has_no_verdict(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    assert all(a.narrative_function is None for a in assessment.current_assessments(run))
    assert set(run.output) == {
        "assessments",
        "responses_assessed",
        "observations_not_responses",
        "proposition_ids",
        "by_stance",
        "by_alignment",
        "by_character",
        "needs_human_review",
        "assessments_digest",
    }
    assert run.output["assessments"] == 7 and run.output["observations_not_responses"] == 1


def test_AT07_target_context_is_frozen_per_run(inv, user, issue, p1, target, conversation) -> None:
    first = _run_m2(inv, user, issue, [conversation], p1)
    inv_services.revise_target_context(
        target=target, user=user, note="Revisi: sebenarnya mendukung audit.", stances={p1: "PRO"}
    )
    second = _run_m2(inv, user, issue, [conversation], p1)
    assert _by_text(first)["c1"].target_alignment == "OPPOSE"  # run lama tetap memakai CONTRA
    assert _by_text(second)["c1"].target_alignment == "SUPPORT"  # run baru memakai PRO
    assert _by_text(first)["c1"].issue_stance == _by_text(second)["c1"].issue_stance == "PRO"


def test_same_frozen_inputs_give_identical_assessments(inv, user, issue, p1, conversation) -> None:
    a = _run_m2(inv, user, issue, [conversation], p1)
    b = _run_m2(inv, user, issue, [conversation], p1)
    assert a.output["assessments_digest"] == b.output["assessments_digest"]
    assert a.output_digest == b.output_digest


def test_failed_method_leaves_no_assessment_rows(
    inv, user, issue, p1, conversation, monkeypatch
) -> None:
    real = RulesClassifier.classify
    calls = {"n": 0}

    def flaky(self, item):
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("rusak di tengah")
        return real(self, item)

    monkeypatch.setattr(RulesClassifier, "classify", flaky)
    run = _run_m2(inv, user, issue, [conversation], p1)
    assert run.status == AnalysisStatus.FAILED and "rusak di tengah" in run.error
    assert not ResponseAssessment.objects.exists()


def test_invalid_parameters_are_rejected_and_unknown_proposition_fails_the_run(
    inv, user, issue, p1, conversation
) -> None:
    dataset = services.create_dataset_version(investigation=inv, runs=[conversation], by=user)
    bad = _params(p1)
    bad.pop("min_matches")
    with pytest.raises(InvalidParameters):
        services.create_analysis_run(
            dataset=dataset,
            method="m2-rules",
            parameters=bad,
            by=user,
            issue_context_version=None,
            target_context_versions=services.latest_target_contexts(dataset),
        )
    ghost = example_parameters({999999: CUES})
    run = _run_m2(inv, user, issue, [conversation], p1, params=ghost)
    assert run.status == AnalysisStatus.FAILED and "999999" in run.error
    assert not ResponseAssessment.objects.exists()


# --- penjaga database ---------------------------------------------------------------------------


def _row(run, observation, proposition, **over):
    fields = dict(
        analysis_run=run,
        observation=observation,
        proposition=proposition,
        issue_stance="UNDETERMINED",
        target_alignment="UNCLEAR",
        response_character=["RC-10"],
        basis={},
        source="MACHINE",
    )
    fields.update(over)
    return ResponseAssessment(**fields)


def test_machine_rows_only_while_running_and_only_for_m2_runs(
    inv, user, issue, p1, conversation
) -> None:
    done = _run_m2(inv, user, issue, [conversation], p1)
    # observasi yang BELUM punya penilaian (posting target), agar yang menolak benar-benar trigger,
    # bukan constraint unik
    unassessed = done.dataset_version.members.filter(observation__source_object_type="post").first()
    existing = unassessed
    with pytest.raises(DatabaseError), transaction.atomic():
        _row(done, unassessed.observation, p1, source="MACHINE").save()  # run sudah COMPLETED
    dataset = done.dataset_version
    summary = services.create_analysis_run(
        dataset=dataset,
        method="dataset-summary",
        parameters={"top_authors": 1},
        by=user,
        issue_context_version=None,
        target_context_versions=services.latest_target_contexts(dataset),
    )
    AnalysisRun.objects.filter(pk=summary.pk).update(status=AnalysisStatus.RUNNING)
    with pytest.raises(DatabaseError), transaction.atomic():
        _row(summary, existing.observation, p1).save()  # bukan metode M2


def test_rows_must_belong_to_the_frozen_dataset_and_investigation(
    inv, user, issue, p1, target, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1, execute=False)
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    outside = new_run(target, user)
    ingest(outside, [obs(outside, "luar", actor="z1", parent="seed", text="di luar dataset")])
    from collection.models import PostObservation

    stray = PostObservation.objects.filter(run=outside, post__external_post_id="luar").get()
    with pytest.raises(DatabaseError), transaction.atomic():
        _row(run, stray, p1).save()
    other = inv_services.create_investigation(user=user, name="Lain")
    other_issue = inv_services.create_issue(investigation=other, user=user, title="Isu lain")
    foreign = inv_services.add_proposition(issue=other_issue, user=user, statement="Klaim lain")
    member = run.dataset_version.members.first().observation
    with pytest.raises(DatabaseError), transaction.atomic():
        _row(run, member, foreign).save()


def test_assessments_are_append_only_at_the_database(inv, user, issue, p1, conversation) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    pk = run.assessments.first().pk
    for sql in (
        "UPDATE intelligence_responseassessment SET issue_stance = 'PRO' WHERE id = %s",
        "UPDATE intelligence_responseassessment SET basis = '{}'::jsonb WHERE id = %s",
        "DELETE FROM intelligence_responseassessment WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [pk])


def test_labels_and_source_consistency_are_enforced(inv, user, issue, p1, conversation) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1, execute=False)
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    member = run.dataset_version.members.first().observation
    for over in (
        {"issue_stance": "BUZZER"},
        {"target_alignment": "MAYBE"},
        {"expression_sentiment": "ANGRY"},
        {"narrative_function": "manipulasi"},
        {"reviewed_by": user},  # mesin tidak boleh bertanda peninjau
        {"source": "HUMAN"},  # manusia wajib punya penggantian, peninjau, dan alasan
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            _row(run, member, p1, **over).save()


# --- tinjauan manusia ---------------------------------------------------------------------------


def test_AT16_review_creates_a_traceable_new_version_and_keeps_the_machine_result(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    original = _by_text(run)["c5"]
    reviewer = User.objects.create_user("peninjau", password="x")
    reviewed = assessment.review_assessment(
        assessment=original,
        by=reviewer,
        reason="Hanya sindiran, bukan ancaman.",
        response_character=["RC-06"],
        target_alignment="UNCLEAR",
    )
    assert reviewed.source == "HUMAN" and reviewed.supersedes_id == original.pk
    assert reviewed.reviewed_by == reviewer and reviewed.review_reason.startswith("Hanya sindiran")
    assert reviewed.response_character == ["RC-06"] and reviewed.needs_human_review is False
    assert reviewed.basis["changed"]["response_character"] == [["RC-07"], ["RC-06"]]
    assert reviewed.basis["evidence"] == original.basis["evidence"]  # rujukan bukti terbawa
    original.refresh_from_db()
    assert original.response_character == ["RC-07"] and original.source == "MACHINE"
    assert [a.pk for a in assessment.assessment_history(reviewed)] == [original.pk, reviewed.pk]
    current = {a.pk for a in assessment.current_assessments(run)}
    assert reviewed.pk in current and original.pk not in current
    assert run.assessments.count() == 8  # 7 mesin + 1 manusia (riwayat tidak hilang)


def test_review_chain_continues_and_old_versions_cannot_be_reviewed_again(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    first = _by_text(run)["c3"]
    second = assessment.review_assessment(
        assessment=first, by=user, reason="Ada stance tersirat.", issue_stance="PRO"
    )
    with pytest.raises(assessment.AlreadyReviewed):
        assessment.review_assessment(
            assessment=first, by=user, reason="lagi", issue_stance="CONTRA"
        )
    third = assessment.review_assessment(
        assessment=second, by=user, reason="Dikoreksi lagi.", issue_stance="MIXED"
    )
    assert [a.issue_stance for a in assessment.assessment_history(third)] == [
        "UNDETERMINED",
        "PRO",
        "MIXED",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"reason": "  ", "issue_stance": "PRO"},
        {"reason": "x"},  # tidak ada perubahan
        {"reason": "x", "issue_stance": "UNDETERMINED"},  # sama dengan nilai sekarang
        {"reason": "x", "issue_stance": "BUZZER"},
        {"reason": "x", "response_character": []},
        {"reason": "x", "response_character": ["RC-99"]},
        {"reason": "x", "expression_sentiment": "ANGRY"},
        {"reason": "x", "narrative_function": "propaganda"},
    ],
)
def test_invalid_reviews_are_rejected(inv, user, issue, p1, conversation, kwargs) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    with pytest.raises(assessment.InvalidReview):
        assessment.review_assessment(assessment=_by_text(run)["c3"], by=user, **kwargs)
    assert run.assessments.count() == 7


def test_review_can_clear_optional_dimensions_and_needs_a_completed_run(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    emotional = assessment.review_assessment(
        assessment=_by_text(run)["c3"],
        by=user,
        reason="Nadanya negatif.",
        expression_sentiment="NEGATIVE",
    )
    assert emotional.expression_sentiment == "NEGATIVE"
    cleared = assessment.review_assessment(
        assessment=emotional, by=user, reason="Tidak jelas nadanya.", expression_sentiment=None
    )
    assert cleared.expression_sentiment is None
    pending = _run_m2(inv, user, issue, [conversation], p1, execute=False)
    with pytest.raises(assessment.InvalidReview, match="run selesai"):
        assessment.review_assessment(
            assessment=ResponseAssessment(analysis_run=pending),
            by=user,
            reason="x",
            issue_stance="PRO",
        )


def test_review_rows_must_replace_the_same_response(inv, user, issue, p1, conversation) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1)
    rows = _by_text(run)
    with pytest.raises(DatabaseError), transaction.atomic():
        ResponseAssessment.objects.create(
            analysis_run=run,
            observation=rows["c1"].observation,
            proposition=p1,
            issue_stance="PRO",
            target_alignment="OPPOSE",
            response_character=["RC-03"],
            basis={},
            source="HUMAN",
            supersedes=rows["c3"],
            reviewed_by=user,
            review_reason="salah sasaran",
        )


def test_guard_function_does_not_freeze_a_seqscan_plan() -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT proconfig FROM pg_proc WHERE proname = 'snr_assessment_guard'")
        (config,) = cur.fetchone()
    assert "enable_seqscan=off" in config


# --- rantai percakapan dan batas penjaga lanjutan ------------------------------------------------


def test_parent_comes_from_the_same_run_when_the_post_was_observed_twice(
    inv, user, issue, p1, target, conversation
) -> None:
    second = new_run(target, user)
    ingest(
        second,
        [
            obs(second, "seed", kind=POST, actor="a0", text="Perusahaan tidak perlu diaudit."),
            obs(
                second, "c1", actor="a1", parent="seed", text="Sudah lengkap, tidak perlu diaudit."
            ),
            obs(second, "c9", actor="a9", parent="c1", text="Setuju sekali!"),
        ],
    )
    run = _run_m2(inv, user, issue, [conversation, second], p1)
    from collection.models import PostObservation

    first_c1 = PostObservation.objects.get(run=conversation, post__external_post_id="c1")
    second_c1 = PostObservation.objects.get(run=second, post__external_post_id="c1")
    rows = {
        (a.observation.run_id, a.observation.post.external_post_id): a
        for a in assessment.current_assessments(run).select_related("observation__post")
    }
    c2 = rows[(conversation.pk, "c2")]
    c9 = rows[(second.pk, "c9")]
    assert (
        c2.basis["evidence"]["parent_observation_ids"][0] == first_c1.pk
    )  # bukan observasi terbaru
    assert c9.basis["evidence"]["parent_observation_ids"][0] == second_c1.pk
    assert (c2.issue_stance, c9.issue_stance) == (
        "PRO",
        "CONTRA",
    )  # tiap balasan mengikuti induknya


def test_relation_cycles_stop_and_are_marked_untraceable(inv, user, conversation) -> None:
    from collection.models import PostObservation
    from intelligence.conversation import ConversationIndex

    other = new_run(conversation.target, user)
    ingest(
        other,
        [
            obs(other, "c1", actor="a1", parent="c2", text="x"),
            obs(other, "c2", actor="a2", parent="c1", text="y"),
        ],
    )
    ids = list(PostObservation.objects.filter(run=other).values_list("id", flat=True))
    chain = ConversationIndex(ids).chain(
        PostObservation.objects.get(run=other, post__external_post_id="c1").pk
    )
    assert chain.parent_unknown is True and len(chain.parents) == 1  # berhenti di lingkaran


def test_human_rows_are_refused_while_the_run_is_still_running(
    inv, user, issue, p1, conversation
) -> None:
    run = _run_m2(inv, user, issue, [conversation], p1, execute=False)
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    member = run.dataset_version.members.first().observation
    machine = _row(run, member, p1)
    machine.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        ResponseAssessment.objects.create(
            analysis_run=run,
            observation=member,
            proposition=p1,
            issue_stance="PRO",
            target_alignment="OPPOSE",
            response_character=["RC-03"],
            basis={},
            source="HUMAN",
            supersedes=machine,
            reviewed_by=user,
            review_reason="terlalu dini",
        )


def test_a_review_must_stay_within_the_same_run_and_proposition(
    inv, user, issue, p1, conversation
) -> None:
    second_prop = inv_services.add_proposition(issue=issue, user=user, statement="Klaim kedua.")
    params = example_parameters({p1.pk: CUES, second_prop.pk: CUES})
    first = _run_m2(inv, user, issue, [conversation], p1, params=params)
    other_run = _run_m2(inv, user, issue, [conversation], p1, params=params)
    base = assessment.current_assessments(first).filter(proposition=p1).first()
    sibling = (
        assessment.current_assessments(first)
        .filter(proposition=second_prop, observation=base.observation)
        .first()
    )
    foreign = (
        assessment.current_assessments(other_run)
        .filter(proposition=p1, observation=base.observation)
        .first()
    )
    for predecessor, run, prop in ((sibling, first, p1), (foreign, first, p1)):
        with pytest.raises(DatabaseError), transaction.atomic():
            ResponseAssessment.objects.create(
                analysis_run=run,
                observation=base.observation,
                proposition=prop,
                issue_stance="PRO",
                target_alignment="OPPOSE",
                response_character=["RC-03"],
                basis={},
                source="HUMAN",
                supersedes=predecessor,
                reviewed_by=user,
                review_reason="salah sasaran",
            )
