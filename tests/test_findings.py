"""WP-2.6: Finding, evaluasi bukti, pengesahan, supersession (FR-077..FR-080; AT-15, AT-16; NFR-09)."""

import pytest
from collection.contracts import SourceObjectType
from collection.models import InspectionRun
from collection_helpers import ingest, new_run, obs
from django.apps import apps
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from intelligence import findings as fs
from intelligence.m5 import MODEL_TIERS, ResultTier, tier_of
from intelligence.models import (
    AnalysisStatus,
    Finding,
    FindingIndicator,
    FindingObservation,
    FindingReview,
    FindingRun,
)
from investigations import services as inv_services
from preservation.models import ArtifactVerification, EvidenceArtifact
from test_co_run import params as co_params
from collection_helpers import register
from investigations.enums import Platform
from test_co_run import run_co, secs, small, target  # noqa: F401
from test_m4_run import _dataset, inv, user  # noqa: F401

pytestmark = pytest.mark.django_db
POST, REPOST = SourceObjectType.POST, SourceObjectType.REPOST
ALT = {
    k: {"outcome": "RULED_OUT", "reasoning": f"Dikaji: {k} tidak menjelaskan pola ini."}
    for k in fs.GENERAL_ALTERNATIVES
}
RATING = {
    a: {"level": "ACCEPTABLE", "reason": f"alasan {a}"}
    for a in ("integrity", "provenance", "completeness", "relevance")
}
STATEMENT = (
    "Dua akun membalas tiga posting yang sama dalam waktu berdekatan dengan teks yang hampir sama."
)


@pytest.fixture
def reviewer() -> User:
    return User.objects.create_user("peninjau", password="x")


@pytest.fixture
def co_run(inv, user, small):
    run = run_co(user, _dataset(inv, user, [small]), co_params(permutations=0))
    assert run.status == AnalysisStatus.COMPLETED, run.error
    return run


def _edges(run, *indicators):
    return list(run.coordination.edges.filter(indicator__in=indicators or ["CO-02"]))


def kwargs(inv, user, co_run, **over):
    base = dict(
        investigation=inv,
        analysis_runs=[co_run],
        indicator_edges=_edges(co_run, "CO-02"),
        observation_ids=[],
        title="Pola waktu dan teks serupa",
        statement=STATEMENT,
        interpretation="Indikator waktu dan teks menunjukkan pola bersama pada tiga posting.",
        evidence_ratings=RATING,
        alternatives=ALT,
        confidence="LOW",
        confidence_reason="Data sintetis dan bukti belum independen.",
        by=user,
    )
    base.update(over)
    return base


def draft(inv, user, co_run, **over):
    return fs.draft_finding(**kwargs(inv, user, co_run, **over))


# --- evaluasi kualitas bukti ------------------------------------------------------------------------


def _artifact(run, n, *, verified=None, user=None):
    art = EvidenceArtifact.objects.create(
        run=run,
        kind="screenshot",
        relative_path=f"uji/{run.pk}/{n}.png",
        sha256="a" * 64,
        size_bytes=10,
        content_type="image/png",
    )
    for result in verified or []:
        ArtifactVerification.objects.create(
            artifact=art,
            verified_by=user,
            purpose="verify",
            result=result,
            expected_sha256="a" * 64,
            expected_size=10,
            actual_sha256="a" * 64 if result == "MATCH" else None,
            actual_size=10 if result == "MATCH" else None,
        )
    return art


def test_evidence_axes_are_derived_from_hashes_run_coverage_and_source_method(
    inv, user, co_run
) -> None:
    obs_ids = list(co_run.dataset_version.members.values_list("observation_id", flat=True))
    run = InspectionRun.objects.get(pk=co_run.dataset_version.members.first().observation.run_id)
    none = fs.evaluate_evidence(obs_ids)
    assert none["suggestions"]["integrity"]["level"] == "NOT_ASSESSABLE"
    assert none["suggestions"]["relevance"]["level"] == "NOT_ASSESSABLE"
    assert none["suggestions"]["completeness"]["level"] == "GOOD"  # run selesai, paginasi lengkap
    assert (
        none["suggestions"]["provenance"]["level"] == "NOT_ASSESSABLE"
        and none["facts"]["synthetic"] is True
    )
    first = _artifact(run, 1, verified=["MATCH"], user=user)
    _artifact(run, 2, user=user)
    assert fs.evaluate_evidence(obs_ids)["suggestions"]["integrity"]["level"] == "ACCEPTABLE"
    ArtifactVerification.objects.create(
        artifact=EvidenceArtifact.objects.get(relative_path=f"uji/{run.pk}/2.png"),
        verified_by=user,
        purpose="verify",
        result="MATCH",
        expected_sha256="a" * 64,
        expected_size=10,
        actual_sha256="a" * 64,
        actual_size=10,
    )
    assert fs.evaluate_evidence(obs_ids)["suggestions"]["integrity"]["level"] == "GOOD"
    ArtifactVerification.objects.create(
        artifact=first,
        verified_by=user,
        purpose="verify",
        result="MISMATCH",
        expected_sha256="a" * 64,
        expected_size=10,
        actual_sha256="b" * 64,
        actual_size=11,
    )
    poor = fs.evaluate_evidence(obs_ids)
    assert poor["suggestions"]["integrity"]["level"] == "POOR"  # verifikasi TERAKHIR yang berlaku
    assert (
        poor["facts"]["integrity"]["mismatch"] == 1
        and poor["facts"]["integrity"]["verified_match"] == 1
    )


def test_completeness_follows_the_run_coverage_metadata(inv, user, co_run) -> None:
    run = InspectionRun.objects.get(pk=co_run.dataset_version.members.first().observation.run_id)
    obs_ids = list(co_run.dataset_version.members.values_list("observation_id", flat=True))
    InspectionRun.objects.filter(pk=run.pk).update(coverage={**run.coverage, "outcome": "PARTIAL"})
    assert fs.evaluate_evidence(obs_ids)["suggestions"]["completeness"]["level"] == "POOR"
    InspectionRun.objects.filter(pk=run.pk).update(
        coverage={**run.coverage, "pagination_complete": None}
    )
    assert fs.evaluate_evidence(obs_ids)["suggestions"]["completeness"]["level"] == "NOT_ASSESSABLE"


# --- pembuatan temuan -----------------------------------------------------------------------------


def test_a_draft_finding_is_sealed_and_linked_to_observations_runs_and_indicators(
    inv, user, co_run
) -> None:
    f = draft(inv, user, co_run)
    assert (
        f.sealed_at is not None
        and f.platform == "x"
        and fs.finding_status(f) == fs.FindingState.DRAFT
    )
    assert list(f.runs.values_list("analysis_run_id", flat=True)) == [co_run.pk]
    edge_obs = {o for e in _edges(co_run, "CO-02") for o in e.observation_ids}
    assert set(f.observations.values_list("observation_id", flat=True)) == edge_obs
    assert f.indicators.count() == len(_edges(co_run, "CO-02"))
    assert (
        f.synthetic_data is True
        and "Bukan vonis" in f.notice
        and f.independent_evidence_groups is not None
    )
    q = f.evidence_quality
    assert set(q) >= {"integrity", "provenance", "completeness", "relevance", "_facts"}
    assert q["completeness"]["system_suggestion"]["level"] == "GOOD" and q["integrity"]["reason"]


@pytest.mark.parametrize(
    "over",
    [
        {"title": " "},
        {"statement": ""},
        {"interpretation": ""},
        {"confidence_reason": " "},
        {"confidence": "CERTAIN"},
        {"analysis_runs": []},
        {"indicator_edges": [], "observation_ids": []},
        {"alternatives": {"mystery": {"outcome": "RULED_OUT", "reasoning": "x"}}},
        {"evidence_ratings": {k: v for k, v in RATING.items() if k != "relevance"}},
        {"evidence_ratings": {**RATING, "integrity": {"level": "GOOD", "reason": ""}}},
    ],
)
def test_incomplete_or_malformed_findings_are_rejected(inv, user, co_run, over) -> None:
    with pytest.raises(fs.InvalidFinding) as caught:
        draft(inv, user, co_run, **over)
    if "analysis_runs" in over:
        assert "minimal satu AnalysisRun" in str(caught.value)
    assert not Finding.objects.exists()


@pytest.mark.parametrize("field", ["title", "statement", "interpretation", "confidence_reason"])
@pytest.mark.parametrize("term", ["buzzer", "operasi berbayar", "aktor pengendali", "akun bayaran"])
def test_FR079_no_verdict_about_paid_operations_or_controllers(
    inv, user, co_run, field, term
) -> None:
    with pytest.raises(fs.InvalidFinding, match="FR-079"):
        draft(inv, user, co_run, **{field: f"Pola ini jelas milik {term}."})
    assert not Finding.objects.exists()


def test_alternative_reasoning_may_discuss_paid_operations_as_something_ruled_out(
    inv, user, co_run
) -> None:
    alts = {
        **ALT,
        "organic_mobilization": {
            "outcome": "NOT_RULED_OUT",
            "reasoning": "Tidak ada dasar menyimpulkan operasi berbayar.",
        },
    }
    assert draft(inv, user, co_run, alternatives=alts).pk


def test_links_must_point_to_completed_runs_of_the_same_investigation_and_member_observations(
    inv, user, co_run, target
) -> None:
    other = inv_services.create_investigation(user=user, name="Lain")
    pending = run_co(user, co_run.dataset_version, co_params(), execute=False)
    for bad in ([pending],):
        with pytest.raises(fs.InvalidFinding, match="selesai"):
            draft(inv, user, co_run, analysis_runs=bad, indicator_edges=[], observation_ids=[1])
    with pytest.raises(fs.InvalidFinding, match="investigasi"):
        draft(other, user, co_run)
    with pytest.raises(fs.InvalidFinding, match="anggota dataset"):
        draft(inv, user, co_run, observation_ids=[999_999_999])
    stranger = new_run(target, user)
    ingest(stranger, [obs(stranger, "zz", actor="zz", parent="seed", text="di luar dataset")])
    from collection.models import PostObservation

    outside = PostObservation.objects.get(run=stranger, post__external_post_id="zz")
    with pytest.raises(fs.InvalidFinding, match="anggota dataset"):
        draft(inv, user, co_run, observation_ids=[outside.pk])
    foreign_edges = _edges(run_co(user, co_run.dataset_version, co_params(permutations=0)), "CO-02")
    with pytest.raises(fs.InvalidFinding, match="run indikator"):
        draft(inv, user, co_run, indicator_edges=foreign_edges)


# --- plafon confidence pada layanan -----------------------------------------------------------------


def test_confidence_above_the_policy_ceiling_is_refused_with_the_reasons(inv, user, co_run) -> None:
    with pytest.raises(fs.ConfidenceAboveCeiling) as caught:
        draft(inv, user, co_run, confidence="HIGH")
    text = str(caught.value)
    assert "plafon LOW" in text and "sintetis" in text and "independen" in text
    with pytest.raises(fs.ConfidenceAboveCeiling):
        draft(inv, user, co_run, confidence="MODERATE")
    assert draft(inv, user, co_run, confidence="NOT_ASSESSABLE").confidence == "NOT_ASSESSABLE"


def _non_synthetic(monkeypatch):
    real = fs.evidence_facts

    def facts(ids):
        out = real(ids)
        out["synthetic"] = False
        out["source_methods"] = ["browser_observation"]
        return out

    monkeypatch.setattr(fs, "evidence_facts", facts)


def test_moderate_and_high_become_available_only_when_the_policy_conditions_hold(
    inv, user, co_run, monkeypatch
) -> None:
    _non_synthetic(monkeypatch)
    good = {
        a: {"level": "GOOD", "reason": f"alasan {a}", "override_reason": "diverifikasi manual"}
        for a in RATING
    }
    one_group = fs.draft_finding(
        **kwargs(
            inv,
            user,
            co_run,
            evidence_ratings=good,
            confidence="MODERATE",
            confidence_reason="Satu kelompok bukti; semua hipotesis disingkirkan.",
        )
    )
    assert one_group.synthetic_data is False and one_group.independent_evidence_groups == 1
    stored = one_group.evidence_quality["integrity"]
    assert stored["override_reason"] == "diverifikasi manual" and stored["level"] == "GOOD"
    with pytest.raises(fs.ConfidenceAboveCeiling, match="independen"):
        draft(inv, user, co_run, evidence_ratings=good, confidence="HIGH")
    not_ruled = {
        **ALT,
        "external_event": {"outcome": "NOT_RULED_OUT", "reasoning": "ada peristiwa besar"},
    }
    with pytest.raises(fs.ConfidenceAboveCeiling, match="external_event"):
        draft(inv, user, co_run, evidence_ratings=good, alternatives=not_ruled, confidence="HIGH")


def test_two_independent_evidence_groups_allow_high_when_everything_else_is_good(
    inv, user, target, monkeypatch
) -> None:
    run = new_run(target, user)
    items = [
        obs(run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-4000)),
        obs(run, "pa", actor="a0", parent="seed", text="induk A", published_at=secs(-3000)),
        obs(run, "o1", kind=POST, actor="a0", text="objek", published_at=secs(-2900)),
        obs(
            run,
            "ru1",
            actor="u1",
            parent="pa",
            text="balasan satu cukup panjang",
            published_at=secs(0),
        ),
        obs(
            run,
            "ru2",
            actor="u2",
            parent="pa",
            text="balasan dua berbeda isi sama sekali",
            published_at=secs(20),
        ),
        obs(
            run,
            "x1",
            kind=REPOST,
            actor="u1",
            parent=None,
            reposted_post_id="o1",
            text=None,
            published_at=secs(40),
        ),
        obs(
            run,
            "x2",
            kind=REPOST,
            actor="u2",
            parent=None,
            reposted_post_id="o1",
            text=None,
            published_at=secs(70),
        ),
    ]
    ingest(run, items)
    co = run_co(user, _dataset(target.investigation, user, [run]), co_params(permutations=0))
    assert co.status == AnalysisStatus.COMPLETED, co.error
    edges = list(co.coordination.edges.filter(indicator__in=["CO-02", "CO-04"]))
    summary = next(iter(co.coordination.pair_summary.values()))
    assert len(summary["independent_evidence_groups"]) == 2
    _non_synthetic(monkeypatch)
    good = {
        a: {"level": "GOOD", "reason": f"alasan {a}", "override_reason": "diverifikasi manual"}
        for a in RATING
    }
    f = fs.draft_finding(
        **kwargs(
            target.investigation,
            user,
            co,
            indicator_edges=edges,
            evidence_ratings=good,
            confidence="HIGH",
            confidence_reason="Dua kelompok bukti independen, bukti baik, semua alternatif disingkirkan.",
        )
    )
    assert f.confidence == "HIGH" and f.independent_evidence_groups == 2


def _pair_world(inv, user, target):
    """u1-u2: dua kelompok bukti (balasan serentak + repost); u1-u3: satu kelompok (balasan serentak)."""
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(
                run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-4000)
            ),
            obs(run, "pa", actor="a0", parent="seed", text="induk A", published_at=secs(-3000)),
            obs(run, "o1", kind=POST, actor="a0", text="objek", published_at=secs(-2900)),
            obs(
                run,
                "ru1",
                actor="u1",
                parent="pa",
                text="balasan satu cukup panjang",
                published_at=secs(0),
            ),
            obs(
                run,
                "ru2",
                actor="u2",
                parent="pa",
                text="balasan dua berbeda isi sama sekali",
                published_at=secs(20),
            ),
            obs(
                run,
                "ru3",
                actor="u3",
                parent="pa",
                text="balasan tiga lain lagi isinya",
                published_at=secs(40),
            ),
            obs(
                run,
                "x1",
                kind=REPOST,
                actor="u1",
                parent=None,
                reposted_post_id="o1",
                text=None,
                published_at=secs(60),
            ),
            obs(
                run,
                "x2",
                kind=REPOST,
                actor="u2",
                parent=None,
                reposted_post_id="o1",
                text=None,
                published_at=secs(80),
            ),
        ],
    )
    co = run_co(user, _dataset(target.investigation, user, [run]), co_params(permutations=0))
    assert co.status == AnalysisStatus.COMPLETED, co.error
    return co


def test_with_several_pairs_the_smallest_number_of_independent_groups_counts(
    inv, user, target
) -> None:
    co = _pair_world(inv, user, target)
    by_pair = {
        k: len(v["independent_evidence_groups"]) for k, v in co.coordination.pair_summary.items()
    }
    assert (
        sorted(by_pair.values())[-1] == 2 and min(by_pair.values()) == 1
    )  # ada pasangan 2 kelompok dan 1 kelompok
    two = list(co.coordination.edges.filter(indicator="CO-04"))
    one = [
        e
        for e in co.coordination.edges.filter(indicator="CO-02")
        if e.network.pair_summary[f"{e.actor_a_id}-{e.actor_b_id}"][
            "independent_evidence_groups"
        ].__len__()
        == 1
    ]
    assert two and one
    f = draft(inv, user, co, indicator_edges=[*two, *one])
    assert f.independent_evidence_groups == 1  # konservatif: yang TERKECIL
    only_two = draft(inv, user, co, indicator_edges=two)
    assert only_two.independent_evidence_groups == 2


def test_a_finding_without_indicators_has_unknown_independent_groups(inv, user, co_run) -> None:
    member = co_run.dataset_version.members.first().observation_id
    f = draft(inv, user, co_run, indicator_edges=[], observation_ids=[member])
    assert f.independent_evidence_groups is None and f.indicators.count() == 0


def test_a_finding_cannot_mix_platforms(inv, user, co_run) -> None:
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/55")
    trun = new_run(tiktok, user)
    ingest(
        trun,
        [
            obs(trun, "root", kind=POST, actor="t0", text="video", published_at=secs(-100)),
            obs(
                trun,
                "c1",
                kind=SourceObjectType.COMMENT,
                actor="t1",
                parent="root",
                text="komentar cukup panjang satu",
                published_at=secs(5),
            ),
        ],
    )
    tt = run_co(user, _dataset(inv, user, [trun]), co_params(permutations=0))
    assert tt.status == AnalysisStatus.COMPLETED, tt.error
    member = tt.dataset_version.members.first().observation_id
    with pytest.raises(fs.InvalidFinding, match="satu platform"):
        draft(
            inv,
            user,
            co_run,
            analysis_runs=[co_run, tt],
            indicator_edges=[],
            observation_ids=[member],
        )


# --- pengesahan -----------------------------------------------------------------------------------


def test_endorsement_requires_every_alternative_to_be_considered_at_service_and_database(
    inv, user, reviewer, co_run
) -> None:
    incomplete = {k: v for k, v in ALT.items() if k != "sampling_bias"}
    f = draft(inv, user, co_run, alternatives=incomplete)
    with pytest.raises(fs.InvalidFinding, match="sampling_bias"):
        fs.endorse_finding(finding=f, by=reviewer, note="setuju")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=f, action="ENDORSE", reviewer=reviewer, note="lolos jalur belakang"
        )
    assert not f.reviews.exists()


def test_the_review_flow_draft_endorsed_withdrawn(inv, user, reviewer, co_run) -> None:
    f = draft(inv, user, co_run)
    assert fs.finding_status(f) == fs.FindingState.DRAFT and fs.current_findings(inv) == []
    with pytest.raises(fs.InvalidFinding, match="catatan"):
        fs.endorse_finding(finding=f, by=reviewer, note=" ")
    review = fs.endorse_finding(finding=f, by=reviewer, note="Bukti dan alternatif telah ditinjau.")
    assert review.reviewer == reviewer and fs.finding_status(f) == fs.FindingState.ENDORSED
    assert fs.current_findings(inv) == [f]
    with pytest.raises(fs.InvalidFinding, match="DRAFT"):
        fs.endorse_finding(finding=f, by=reviewer, note="lagi")
    fs.withdraw_finding(finding=f, by=reviewer, note="Ditemukan kesalahan sampel.")
    f = Finding.objects.get(pk=f.pk)
    assert fs.finding_status(f) == fs.FindingState.WITHDRAWN and fs.current_findings(inv) == []
    with pytest.raises(fs.InvalidFinding, match="sudah ditarik"):
        fs.withdraw_finding(finding=f, by=reviewer, note="lagi")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=f, action="ENDORSE", reviewer=reviewer, note="setelah ditarik"
        )


def test_a_draft_can_be_withdrawn_without_endorsement(inv, user, reviewer, co_run) -> None:
    f = draft(inv, user, co_run)
    fs.withdraw_finding(finding=f, by=reviewer, note="Tidak jadi dipakai.")
    assert fs.finding_status(Finding.objects.get(pk=f.pk)) == fs.FindingState.WITHDRAWN


# --- AT-15: supersession setelah reinspection --------------------------------------------------------------


def test_AT15_a_new_finding_supersedes_the_old_one_which_stays_fully_accessible(
    inv, user, reviewer, co_run, small, target
) -> None:
    old = draft(inv, user, co_run)
    fs.endorse_finding(finding=old, by=reviewer, note="Disahkan.")
    again = new_run(target, user)
    ingest(
        again,
        [
            obs(
                again,
                "late",
                actor="u9",
                parent="seed",
                text="balasan pada pemeriksaan ulang",
                published_at=secs(70_000),
            )
        ],
    )
    new_co = run_co(user, _dataset(inv, user, [small, again]), co_params(permutations=0))
    new = fs.revise_finding(
        previous=old,
        **{
            k: v
            for k, v in kwargs(inv, user, new_co, indicator_edges=_edges(new_co, "CO-02")).items()
            if k != "investigation"
        },
    )
    assert new.supersedes_id == old.pk and fs.finding_status(new) == fs.FindingState.DRAFT
    assert (
        fs.finding_status(Finding.objects.get(pk=old.pk)) == fs.FindingState.ENDORSED
    )  # penerus belum disahkan
    fs.endorse_finding(finding=new, by=reviewer, note="Penerus disahkan.")
    old = Finding.objects.get(pk=old.pk)
    assert fs.finding_status(old) == fs.FindingState.SUPERSEDED
    assert fs.current_findings(inv) == [Finding.objects.get(pk=new.pk)]
    assert [x.pk for x in fs.finding_history(new)] == [old.pk, new.pk]
    # yang lama tetap utuh dan terlacak: isi, tautan, AnalysisRun lama
    assert old.statement == STATEMENT and old.runs.count() == 1 and old.observations.exists()
    co_run.refresh_from_db()
    assert co_run.status == AnalysisStatus.COMPLETED and co_run.output_digest
    assert list(old.runs.values_list("analysis_run_id", flat=True)) == [co_run.pk]
    assert list(new.runs.values_list("analysis_run_id", flat=True)) == [new_co.pk]


def test_supersession_rules(inv, user, reviewer, co_run) -> None:
    old = draft(inv, user, co_run)
    first = fs.revise_finding(
        previous=old, **{k: v for k, v in kwargs(inv, user, co_run).items() if k != "investigation"}
    )
    with pytest.raises(fs.InvalidFinding, match="penerus"):
        fs.revise_finding(
            previous=Finding.objects.get(pk=old.pk),
            **{k: v for k, v in kwargs(inv, user, co_run).items() if k != "investigation"},
        )
    fs.withdraw_finding(finding=first, by=reviewer, note="ditarik")
    with pytest.raises(fs.InvalidFinding, match="ditarik"):
        fs.revise_finding(
            previous=Finding.objects.get(pk=first.pk),
            **{k: v for k, v in kwargs(inv, user, co_run).items() if k != "investigation"},
        )
    other = inv_services.create_investigation(user=user, name="Lain")
    with (
        pytest.raises(DatabaseError),
        transaction.atomic(),
    ):  # jalur belakang: penerus lintas investigasi
        Finding.objects.create(
            investigation=other,
            platform="x",
            title="t",
            statement="s",
            interpretation="i",
            confidence="LOW",
            confidence_reason="r",
            evidence_quality={},
            alternatives={},
            notice="n",
            supersedes=old,
            created_by=user,
        )


# --- empat tingkat hasil -------------------------------------------------------------------------------------


def test_every_result_model_is_classified_into_one_of_the_four_tiers() -> None:
    labels = {m._meta.label for m in apps.get_models() if m._meta.app_label == "intelligence"}
    assert labels <= set(MODEL_TIERS), sorted(
        labels - set(MODEL_TIERS)
    )  # model baru wajib diklasifikasikan
    assert {"collection.PostObservation", "preservation.EvidenceArtifact"} <= set(MODEL_TIERS)
    assert tier_of(Finding._meta.label) is ResultTier.REVIEWED_ANALYTICAL_FINDING
    tiers = {label: t for label, t in MODEL_TIERS.items() if t is not None}
    assert set(tiers.values()) == set(ResultTier)
    for label in MODEL_TIERS:
        apps.get_model(label)  # setiap label menunjuk model nyata


# --- penjaga basis data ------------------------------------------------------------------------------------------


def test_sealed_findings_and_their_links_are_immutable(inv, user, co_run) -> None:
    f = draft(inv, user, co_run)
    for sql in (
        "UPDATE intelligence_finding SET title = 'x' WHERE id = %s",
        "UPDATE intelligence_finding SET confidence = 'HIGH' WHERE id = %s",
        "UPDATE intelligence_finding SET sealed_at = now() WHERE id = %s",
        "DELETE FROM intelligence_finding WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [f.pk])
    for table, row in (
        ("intelligence_findingrun", f.runs.first()),
        ("intelligence_findingobservation", f.observations.first()),
        ("intelligence_findingindicator", f.indicators.first()),
    ):
        for sql in (
            f"UPDATE {table} SET id = id WHERE id = %s",
            f"DELETE FROM {table} WHERE id = %s",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute(sql, [row.pk])
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingObservation.objects.create(
            finding=f, observation=co_run.dataset_version.members.last().observation
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingRun.objects.create(finding=f, analysis_run=co_run)


def _unsealed(inv, user, **over):
    fields = dict(
        investigation=inv,
        platform="x",
        title="t",
        statement="s",
        interpretation="i",
        confidence="LOW",
        confidence_reason="r",
        evidence_quality={a: {} for a in RATING},
        alternatives={},
        notice="n",
        created_by=user,
    )
    fields.update(over)
    return Finding.objects.create(**fields)


def test_sealing_requires_links_and_the_evidence_structure(inv, user, co_run) -> None:
    bare = _unsealed(inv, user)
    with pytest.raises(DatabaseError), transaction.atomic():
        Finding.objects.filter(pk=bare.pk).update(sealed_at="2026-10-18T00:00:00Z")  # tanpa tautan
    with pytest.raises(DatabaseError), transaction.atomic():
        _unsealed(inv, user, sealed_at="2026-10-18T00:00:00Z")  # dibuat sudah tersegel
    thin = _unsealed(inv, user, evidence_quality={"integrity": {}})
    FindingRun.objects.create(finding=thin, analysis_run=co_run)
    FindingObservation.objects.create(
        finding=thin, observation=co_run.dataset_version.members.first().observation
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        Finding.objects.filter(pk=thin.pk).update(
            sealed_at="2026-10-18T00:00:00Z"
        )  # empat sumbu tak lengkap
    ok = _unsealed(inv, user)
    FindingRun.objects.create(finding=ok, analysis_run=co_run)
    FindingObservation.objects.create(
        finding=ok, observation=co_run.dataset_version.members.first().observation
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        Finding.objects.filter(pk=ok.pk).update(
            sealed_at="2026-10-18T00:00:00Z", title="diselundupkan"
        )
    Finding.objects.filter(pk=ok.pk).update(sealed_at="2026-10-18T00:00:00Z")
    assert Finding.objects.get(pk=ok.pk).sealed_at is not None


def test_link_guards_enforce_same_investigation_platform_run_state_and_membership(
    inv, user, co_run, target
) -> None:
    other = inv_services.create_investigation(user=user, name="Lain")
    f = _unsealed(inv, user)
    wrong_platform = _unsealed(inv, user, platform="tiktok")
    wrong_inv = _unsealed(other, user)
    pending = run_co(user, co_run.dataset_version, co_params(), execute=False)
    for finding, run in ((wrong_platform, co_run), (wrong_inv, co_run), (f, pending)):
        with pytest.raises(DatabaseError), transaction.atomic():
            FindingRun.objects.create(finding=finding, analysis_run=run)
    member = co_run.dataset_version.members.first().observation
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingObservation.objects.create(finding=f, observation=member)  # run belum ditautkan
    FindingRun.objects.create(finding=f, analysis_run=co_run)
    FindingObservation.objects.create(finding=f, observation=member)
    stranger = new_run(target, user)
    ingest(stranger, [obs(stranger, "yy", actor="yy", parent="seed", text="di luar dataset")])
    from collection.models import PostObservation

    with pytest.raises(DatabaseError), transaction.atomic():
        FindingObservation.objects.create(
            finding=f,
            observation=PostObservation.objects.get(run=stranger, post__external_post_id="yy"),
        )
    edge = co_run.coordination.edges.first()
    unlinked = _unsealed(inv, user)
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingIndicator.objects.create(
            finding=unlinked, edge=edge
        )  # run indikator belum ditautkan
    FindingIndicator.objects.create(finding=f, edge=edge)


def test_text_and_confidence_constraints_at_the_database(inv, user) -> None:
    for over in (
        {"confidence": "CERTAIN"},
        {"title": ""},
        {"statement": ""},
        {"interpretation": ""},
        {"confidence_reason": ""},
        {"platform": "myspace"},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            _unsealed(inv, user, **over)


def test_reviews_are_append_only_unique_per_action_and_require_a_note(
    inv, user, reviewer, co_run
) -> None:
    f = draft(inv, user, co_run)
    review = fs.endorse_finding(finding=f, by=reviewer, note="ok")
    for sql in (
        "UPDATE intelligence_findingreview SET note = 'x' WHERE id = %s",
        "DELETE FROM intelligence_findingreview WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [review.pk])
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(finding=f, action="ENDORSE", reviewer=reviewer, note="ganda")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(finding=f, action="WITHDRAW", reviewer=reviewer, note="")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(finding=f, action="DELETE", reviewer=reviewer, note="x")
    unsealed = _unsealed(inv, user)
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=unsealed, action="WITHDRAW", reviewer=reviewer, note="belum tersegel"
        )


def _sealed(inv, user, co_run, **over):
    """Temuan tersegel lewat jalur ORM langsung (melewati layanan) agar yang menolak adalah trigger."""
    f = _unsealed(inv, user, **over)
    FindingRun.objects.create(finding=f, analysis_run=co_run)
    FindingObservation.objects.create(
        finding=f, observation=co_run.dataset_version.members.first().observation
    )
    Finding.objects.filter(pk=f.pk).update(sealed_at="2026-10-18T00:00:00Z")
    return Finding.objects.get(pk=f.pk)


def test_each_supersession_condition_is_enforced_by_the_database_on_its_own(
    inv, user, co_run
) -> None:
    sealed = _sealed(inv, user, co_run)
    unsealed = _unsealed(inv, user)
    other = inv_services.create_investigation(user=user, name="Lain")
    with pytest.raises(DatabaseError), transaction.atomic():
        _unsealed(inv, user, supersedes=unsealed)  # predesesor belum tersegel
    with pytest.raises(DatabaseError), transaction.atomic():
        _unsealed(other, user, supersedes=sealed)  # lintas investigasi (platform sama)
    with pytest.raises(DatabaseError), transaction.atomic():
        _unsealed(
            inv, user, platform="tiktok", supersedes=sealed
        )  # lintas platform (investigasi sama)
    assert (
        _unsealed(inv, user, supersedes=sealed).supersedes_id == sealed.pk
    )  # kontrol: syarat terpenuhi


def test_links_cannot_be_added_to_a_sealed_finding_even_when_otherwise_valid(
    inv, user, co_run
) -> None:
    sealed = _sealed(inv, user, co_run)
    spare = run_co(user, co_run.dataset_version, co_params(permutations=0))
    assert spare.status == AnalysisStatus.COMPLETED
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingRun.objects.create(
            finding=sealed, analysis_run=spare
        )  # sah, tetapi temuan sudah tersegel
    fresh = _unsealed(inv, user)
    FindingRun.objects.create(
        finding=fresh, analysis_run=spare
    )  # kontrol: sebelum disegel diterima


@pytest.mark.parametrize(
    "alternatives",
    [
        {k: v for k, v in ALT.items() if k != "sampling_bias"},  # kunci hilang
        {**ALT, "sampling_bias": {"outcome": "MAYBE", "reasoning": "alasan"}},  # hasil tidak sah
        {**ALT, "sampling_bias": {"outcome": "RULED_OUT", "reasoning": "   "}},  # alasan kosong
        {**ALT, "sampling_bias": {"outcome": "RULED_OUT"}},  # alasan tidak ada
        {**ALT, "sampling_bias": {"reasoning": "alasan"}},  # hasil tidak ada
        {},
    ],
)
def test_the_database_alone_refuses_endorsement_without_complete_alternatives(
    inv, user, reviewer, co_run, alternatives
) -> None:
    f = _sealed(inv, user, co_run, alternatives=alternatives)
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=f, action="ENDORSE", reviewer=reviewer, note="langsung ke basis data"
        )
    complete = _sealed(inv, user, co_run, alternatives=ALT)
    assert FindingReview.objects.create(
        finding=complete, action="ENDORSE", reviewer=reviewer, note="lengkap"
    ).pk


def test_a_finding_withdrawn_before_any_endorsement_cannot_be_endorsed_afterwards(
    inv, user, reviewer, co_run
) -> None:
    f = draft(inv, user, co_run)
    fs.withdraw_finding(finding=f, by=reviewer, note="ditarik sebelum disahkan")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=f, action="ENDORSE", reviewer=reviewer, note="setelah ditarik"
        )


def test_an_endorsed_successor_blocks_endorsing_the_superseded_finding(
    inv, user, reviewer, co_run
) -> None:
    old = draft(inv, user, co_run)
    new = fs.revise_finding(
        previous=old, **{k: v for k, v in kwargs(inv, user, co_run).items() if k != "investigation"}
    )
    fs.endorse_finding(finding=new, by=reviewer, note="penerus disahkan lebih dulu")
    with pytest.raises(DatabaseError), transaction.atomic():
        FindingReview.objects.create(
            finding=old, action="ENDORSE", reviewer=reviewer, note="terlambat"
        )


def test_guard_functions_do_not_freeze_a_seqscan_plan() -> None:
    names = [
        "snr_finding_guard",
        "snr_finding_run_guard",
        "snr_finding_observation_guard",
        "snr_finding_indicator_guard",
        "snr_finding_review_guard",
    ]
    with connection.cursor() as cur:
        cur.execute("SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(%s)", [names])
        found = dict(cur.fetchall())
    assert set(found) == set(names) and all("enable_seqscan=off" in c for c in found.values())


def test_FR079_no_score_or_verdict_fields_exist_on_findings() -> None:
    names = {
        f.name
        for m in (Finding, FindingReview, FindingRun, FindingObservation, FindingIndicator)
        for f in m._meta.get_fields()
    }
    for word in (
        "buzzer",
        "score",
        "skor",
        "verdict",
        "vonis",
        "probab",
        "controller",
        "pengendali",
    ):
        assert not any(word in n for n in names), word


def test_finding_confidence_is_never_a_probability_of_being_a_buzzer(inv, user, co_run) -> None:
    f = draft(inv, user, co_run)
    assert (
        f.confidence in {"HIGH", "MODERATE", "LOW", "NOT_ASSESSABLE"}
        and "bukan probabilitas" in f.notice.lower()
    )
    assert "confidence_reason" in {x.name for x in Finding._meta.get_fields()}
