"""Satu Post = satu aktivitas: reinspection tanpa aktivitas baru tidak menaikkan hitungan (FR-062).

Observasi tetap dipertahankan sebagai bukti historis, tetapi jumlah respons (M3), pengulangan narasi (M3),
bobot dan stance edge (M4) dihitung per Post (observasi terbarunya). Perubahan teks dilaporkan, bukan
dianggap aktivitas publikasi baru."""

from datetime import timedelta

import pytest
from collection.contracts import SourceObjectType
from collection.models import InspectionRun
from collection_helpers import OBSERVED, ingest, new_run, obs
from django.contrib.auth.models import User
from intelligence import networks, profiles, services
from intelligence.m2.example_rules import example_parameters
from intelligence.methods import REGISTRY
from intelligence.models import AnalysisStatus
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db
POST = SourceObjectType.POST
CUES = (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit"])
START = OBSERVED - timedelta(days=10)
END = OBSERVED + timedelta(days=1)
RELATIONS = ["reply_to", "quote_of", "repost_of", "mentions"]


def ago(days: float):
    return OBSERVED - timedelta(days=days)


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def world(user):
    inv = inv_services.create_investigation(user=user, name="Investigasi")
    issue = inv_services.create_issue(investigation=inv, user=user, title="Kebakaran hutan")
    p1 = inv_services.add_proposition(issue=issue, user=user, statement="Perlu diaudit.")
    target = inv_services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        stances={p1: "CONTRA"},
    )
    return inv, issue, p1, target


def _complete(run):
    InspectionRun.objects.filter(pk=run.pk).update(status="RUNNING")
    InspectionRun.objects.filter(pk=run.pk).update(status="COMPLETED")


def conversation(run, *, edit_r2=False, flip_r2=False, extra=False):
    """Percakapan yang sama pada setiap inspeksi; r2 dapat diedit dan r7 baru dapat muncul."""
    items = [
        obs(run, "seed", kind=POST, actor="a0", text="Perusahaan tidak perlu diaudit."),
        obs(
            run,
            "r1",
            actor="u1",
            parent="seed",
            text="Justru audit harus dilakukan.",
            published_at=ago(5),
        ),
        obs(
            run,
            "r2",
            actor="u1",
            parent="seed",
            text=(
                "Perusahaan itu tidak perlu diaudit."  # suntingan yang membalik stance
                if flip_r2
                else "Audit harus dilakukan, ini versi suntingan."
                if edit_r2
                else "Audit harus dilakukan."
            ),
            published_at=ago(4),
        ),
        obs(run, "r3", actor="u1", parent="seed", text="Penulis ini bodoh.", published_at=ago(3)),
        obs(
            run,
            "r4",
            actor="u2",
            parent="seed",
            text="Perusahaan itu tidak perlu diaudit.",
            published_at=ago(2),
            mentioned_actor_ids=("u1",),
        ),
    ]
    if extra:
        items.append(
            obs(
                run,
                "r7",
                actor="u1",
                parent="seed",
                text="Komentar baru yang lain.",
                published_at=ago(1),
            )
        )
    return items


def analyse(user, world, rounds):
    """`rounds`: daftar kwargs `conversation` per inspeksi; kembalikan (M3, M4, jumlah observasi)."""
    inv, issue, p1, target = world
    runs = []
    for kwargs in rounds:
        run = new_run(target, user)
        ingest(run, conversation(run, **kwargs))
        _complete(run)
        runs.append(run)
    dataset = services.create_dataset_version(investigation=inv, runs=runs, by=user)

    def go(method, params):
        created = services.create_analysis_run(
            dataset=dataset,
            method=method,
            parameters=params,
            by=user,
            issue_context_version=services.latest_issue_context(issue),
            target_context_versions=services.latest_target_contexts(dataset),
        )
        done = services.execute_run(created)
        assert done.status == AnalysisStatus.COMPLETED, done.error
        return done

    m2 = go("m2-rules", example_parameters({p1.pk: CUES}))
    m3 = go(
        "m3-profile",
        profiles.m3_parameters(
            source_run=m2,
            proposition=p1,
            period_start=START,
            period_end=END,
            min_responses=2,
            bucket_hours=24,
            min_active_buckets=2,
            narrative_min_texts=2,
        ),
    )
    m4 = go(
        "m4-network",
        networks.network_parameters(
            window_start=START,
            window_end=END,
            unknown_time="include",
            relation_types=RELATIONS,
            weighting="count",
            resolution=1.0,
            seed=11,
            compute_betweenness=False,
            metrics_max_nodes=1000,
            stability_seeds=0,
            source_run=m2,
            proposition=p1,
        ),
    )
    return m3, m4, dataset.observation_count


def profile(m3, actor):
    return next(
        p for p in m3.profiles.select_related("actor") if p.actor.external_actor_id == actor
    )


def edges(m4):
    return {
        (e.from_node.actor.external_actor_id, e.to_node.actor.external_actor_id, e.relation_type): e
        for e in m4.graph.edges.select_related("from_node__actor", "to_node__actor")
    }


def nodes(m4):
    return {n.actor.external_actor_id: n for n in m4.graph.nodes.select_related("actor")}


@pytest.mark.parametrize("repeats", [1, 3])
def test_reinspection_without_new_activity_does_not_raise_activity_counts(
    user, world, repeats
) -> None:
    m3, m4, observations = analyse(user, world, [{}] * repeats)
    u1 = profile(m3, "u1").dimensions
    assert u1["participation"]["responses"] == 3
    assert u1["participation"]["observations"] == 3 * repeats  # riwayat dilaporkan terpisah
    assert len(profile(m3, "u1").coverage["runs_covered"]) == repeats  # semua pemeriksaan tercatat
    assert u1["participation"]["responses_with_changed_text"] == 0
    assert u1["stance_distribution"]["counts"]["PRO"] == 2
    assert u1["stance_distribution"]["counts"]["UNDETERMINED"] == 1
    narrative = u1["narrative_consistency"]
    assert narrative["texts_considered"] == 3 and narrative["texts_in_repeated_groups"] == 0
    assert u1["temporal_activity"]["responses_placed"] == 3
    assert u1["target_concentration"]["status"] == "INSUFFICIENT_DATA"  # satu target
    assert m3.output["responses_profiled"] == 4  # u1: 3, u2: 1
    assert m3.output["observations_collapsed_into_unique_posts"] == 4 * (repeats - 1)

    e = edges(m4)
    reply = e[("u1", "a0", "reply_to")]
    assert reply.weight == 3 and len(reply.observation_ids) == 3
    assert reply.stance_counts == {"PRO": 2, "UNDETERMINED": 1}
    assert e[("u2", "u1", "mentions")].weight == 1
    n = nodes(m4)
    assert n["u1"].attributes["posts"] == 3 and n["u1"].attributes["observations"] == 3 * repeats
    assert n["u1"].attributes["responses_assessed"] == 3
    assert n["u1"].attributes["stance_counts"] == {"PRO": 2, "UNDETERMINED": 1}
    assert observations == 5 * repeats  # semua observasi tetap tersimpan sebagai bukti


def test_activity_numbers_are_identical_for_one_and_for_many_identical_inspections(
    user, world
) -> None:
    one = analyse(user, world, [{}])
    _, issue, p1, target = world
    # inspeksi pertama sudah ada pada target yang sama: bangun dunia kedua di investigasi lain
    inv2 = inv_services.create_investigation(user=user, name="Investigasi lain")
    issue2 = inv_services.create_issue(investigation=inv2, user=user, title="Isu")
    p2 = inv_services.add_proposition(issue=issue2, user=user, statement="Perlu diaudit.")
    target2 = inv_services.register_target(
        investigation=inv2,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        stances={p2: "CONTRA"},
    )
    many = analyse(user, (inv2, issue2, p2, target2), [{}] * 4)

    def activity(result):
        m3, m4, _ = result
        dims = profile(m3, "u1").dimensions
        keep = (
            "stance_distribution",
            "response_character",
            "temporal_activity",
            "narrative_consistency",
        )
        return (
            {k: dims[k] for k in keep},
            dims["participation"]["responses"],
            {k: (v.weight, v.stance_counts) for k, v in edges(m4).items()},
        )

    assert activity(one) == activity(many)


def test_edited_text_is_reported_but_is_not_new_activity(user, world) -> None:
    m3, _, _ = analyse(user, world, [{}, {"edit_r2": True}])
    u1 = profile(m3, "u1").dimensions
    assert u1["participation"]["responses"] == 3
    assert u1["participation"]["responses_with_changed_text"] == 1
    assert u1["participation"]["observations"] == 6
    assert u1["narrative_consistency"]["texts_considered"] == 3  # teks terbaru, bukan keduanya


def test_a_genuinely_new_comment_in_a_later_inspection_adds_exactly_one_activity(
    user, world
) -> None:
    m3, m4, _ = analyse(user, world, [{}, {"extra": True}])
    u1 = profile(m3, "u1").dimensions
    assert u1["participation"]["responses"] == 4
    assert u1["participation"]["observations"] == 7  # r1..r3 dua kali + r7 sekali
    assert edges(m4)[("u1", "a0", "reply_to")].weight == 4
    assert nodes(m4)["u1"].attributes["posts"] == 4


def test_superseded_relations_are_reported_as_exclusions_not_silently_dropped(user, world) -> None:
    _, m4, _ = analyse(user, world, [{}, {}, {}])
    # per inspeksi: 4 balasan ke seed + 1 mention (r4) = 5 relasi; dua inspeksi lama = 10 relasi digantikan
    assert m4.graph.exclusions["relation_from_superseded_observation"] == 10


def test_definition_states_the_unit_and_methods_were_versioned(user, world) -> None:
    m3, m4, _ = analyse(user, world, [{}])
    assert "satu Post" in m4.graph.definition["weight_rule"]
    assert "satu Post = satu respons" in profile(m3, "u1").dimensions["participation"]["unit"]
    assert REGISTRY["m3-profile"].version == "2" and REGISTRY["m4-network"].version == "2"
    assert m3.method_version == "2" and m4.method_version == "2"


def test_the_latest_observation_of_a_post_decides_its_stance_in_profile_and_graph(
    user, world
) -> None:
    m3, m4, _ = analyse(user, world, [{}, {"flip_r2": True}])
    expected = {"PRO": 1, "CONTRA": 1, "UNDETERMINED": 1}  # r2 kini CONTRA; versi lama tidak ikut
    u1 = profile(m3, "u1").dimensions
    assert u1["participation"]["responses"] == 3 and u1["participation"]["observations"] == 6
    assert u1["stance_distribution"]["counts"]["PRO"] == 1
    assert u1["stance_distribution"]["counts"]["CONTRA"] == 1
    assert edges(m4)[("u1", "a0", "reply_to")].stance_counts == expected
    assert nodes(m4)["u1"].attributes["stance_counts"] == expected
