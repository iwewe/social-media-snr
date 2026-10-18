"""WP-2.4: Interaction Network + Stance Network View pada AnalysisRun (FR-070/071/073/074; AT-11, AT-13)."""

from datetime import timedelta

import pytest
from collection.contracts import (
    Capability,
    InspectionRequest,
    SourceObjectType,
)
from collection.datasets.dataset import build_result, parse_dataset
from collection.ingestion import ingest_result
from collection.models import ActorAccount, InspectionRun
from collection_helpers import OBSERVED, ingest, new_run, obs, register
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from intelligence import assessment, networks, services
from intelligence.errors import InvalidParameters
from intelligence.m2.example_rules import example_parameters
from intelligence.models import (
    AnalysisRun,
    AnalysisStatus,
    GraphEdge,
    GraphNode,
    GraphProjection,
)
from intelligence.synthetic import generate
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db
POST, REPLY = SourceObjectType.POST, SourceObjectType.REPLY
QUOTE, REPOST = SourceObjectType.QUOTE, SourceObjectType.REPOST
CUES = (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit"])
START = OBSERVED - timedelta(days=10)
END = OBSERVED + timedelta(days=1)


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
def conversation(target, user):
    run = new_run(target, user)
    same = [
        obs(
            run,
            f"s{i}",
            actor=f"same{i}",
            parent="seed",
            text="Justru audit harus dilakukan.",
            published_at=ago(5 - i * 0.1),
        )
        for i in range(1, 7)
    ]
    ingest(
        run,
        [
            obs(
                run,
                "seed",
                kind=POST,
                actor="a0",
                text="Perusahaan tidak perlu diaudit.",
                published_at=ago(9),
            ),
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
                actor="u2",
                parent="seed",
                text="Perusahaan itu tidak perlu diaudit.",
                published_at=ago(2.5),
            ),
            obs(run, "r3", actor="u1", parent="r2", text="Penulis ini bodoh.", published_at=ago(2)),
            obs(
                run,
                "q1",
                kind=QUOTE,
                actor="u3",
                parent=None,
                quoted_post_id="r1",
                text="Setuju sekali!",
                published_at=ago(1.5),
            ),
            obs(
                run,
                "rp1",
                kind=REPOST,
                actor="u2",
                parent=None,
                reposted_post_id="r1",
                text=None,
                published_at=ago(1.2),
            ),
            obs(
                run,
                "r4",
                actor="u4",
                parent="seed",
                mentioned_actor_ids=("u2",),
                text="Apa buktinya?",
                published_at=ago(1),
            ),
            obs(
                run,
                "r5",
                actor="u1",
                parent="r1",
                text="Balas diri sendiri.",
                published_at=ago(0.9),
            ),
            *same,
        ],
    )
    return run


def _dataset(inv, user, runs):
    return services.create_dataset_version(investigation=inv, runs=runs, by=user)


def _m2(inv, user, issue, runs, p1):
    dataset = _dataset(inv, user, runs)
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


def _params(**over):
    base = dict(
        window_start=START,
        window_end=END,
        unknown_time="include",
        relation_types=["reply_to", "quote_of", "repost_of", "mentions"],
        weighting="count",
        resolution=1.0,
        seed=11,
        compute_betweenness=True,
        metrics_max_nodes=1000,
        stability_seeds=0,
    )
    base.update(over)
    return networks.network_parameters(**base)


def _m4(user, dataset, params, *, execute=True, issue=None):
    run = services.create_analysis_run(
        dataset=dataset,
        method="m4-network",
        parameters=params,
        by=user,
        issue_context_version=services.latest_issue_context(issue),
        target_context_versions=services.latest_target_contexts(dataset),
    )
    return services.execute_run(run) if execute else run


@pytest.fixture
def m2run(inv, user, issue, p1, conversation):
    return _m2(inv, user, issue, [conversation], p1)


@pytest.fixture
def graph_run(user, m2run, p1):
    params = _params(source_run=m2run, proposition=p1)
    run = _m4(user, m2run.dataset_version, params)
    assert run.status == AnalysisStatus.COMPLETED, run.error
    return run


def _edges(run):
    return {
        (e.from_node.actor.external_actor_id, e.to_node.actor.external_actor_id, e.relation_type): e
        for e in run.graph.edges.select_related("from_node__actor", "to_node__actor")
    }


def _nodes(run):
    return {n.actor.external_actor_id: n for n in run.graph.nodes.select_related("actor")}


# --- Interaction Network ---------------------------------------------------------------------


def test_edges_are_exactly_the_observed_relations_with_direction_type_and_origin(graph_run) -> None:
    edges = _edges(graph_run)
    expected = {
        ("u1", "a0", "reply_to"),
        ("u2", "a0", "reply_to"),
        ("u1", "u2", "reply_to"),
        ("u3", "u1", "quote_of"),
        ("u2", "u1", "repost_of"),
        ("u4", "u2", "mentions"),
        ("u4", "a0", "reply_to"),
    } | {(f"same{i}", "a0", "reply_to") for i in range(1, 7)}
    assert set(edges) == expected
    assert all(e.observation_ids for e in edges.values())  # asal tersimpan per edge
    assert graph_run.graph.edge_count == len(expected)


def test_self_interactions_are_excluded_and_counted(graph_run) -> None:
    assert ("u1", "u1", "reply_to") not in _edges(graph_run)
    assert graph_run.graph.exclusions["self_interaction"] == 1


def test_edge_origin_points_to_the_observation_of_the_responding_post(graph_run) -> None:
    from collection.models import PostObservation

    edge = _edges(graph_run)[("u3", "u1", "quote_of")]
    (obs_id,) = edge.observation_ids
    origin = PostObservation.objects.select_related("post", "author").get(pk=obs_id)
    assert origin.post.external_post_id == "q1" and origin.author.external_actor_id == "u3"


def test_AT11_same_stance_accounts_are_nodes_but_never_linked_by_stance(graph_run) -> None:
    nodes = _nodes(graph_run)
    same = {f"same{i}" for i in range(1, 7)}
    assert same <= set(nodes)
    assert all(nodes[a].attributes["stance_summary"] == "PRO" for a in same)
    linked = [k for k in _edges(graph_run) if k[0] in same and k[1] in same]
    assert linked == []
    assert all(nodes[a].metrics["community"] is not None for a in same)


def test_stance_view_adds_attributes_to_nodes_and_edges(graph_run) -> None:
    nodes = _nodes(graph_run)
    assert nodes["u1"].attributes["stance_counts"]["PRO"] == 1  # r1; r3/r5 tak berstance
    assert (
        nodes["u1"].attributes["responses_assessed"] >= 2
        and nodes["u1"].attributes["observations"] >= 3
    )
    assert nodes["u2"].attributes["stance_summary"] == "CONTRA"
    edges = _edges(graph_run)
    assert edges[("u1", "a0", "reply_to")].stance_counts == {"PRO": 1}
    assert edges[("u2", "u1", "repost_of")].stance_counts == {"NOT_ASSESSED": 1}
    assert graph_run.graph.definition["stance_view"] is True
    assert "tidak membuat edge" in graph_run.graph.definition["stance_rule"]


def test_without_a_source_run_the_graph_has_no_stance_attributes(user, m2run) -> None:
    run = _m4(user, m2run.dataset_version, _params())
    assert run.status == AnalysisStatus.COMPLETED, run.error
    assert run.graph.definition["stance_view"] is False
    assert all("stance_counts" not in n.attributes for n in run.graph.nodes.all())
    assert all(e.stance_counts == {"NOT_ASSESSED": e.weight} for e in run.graph.edges.all())


# --- definisi, parameter, metrik tersimpan --------------------------------------------------------


def test_definition_metrics_and_algorithm_parameters_are_stored(graph_run) -> None:
    d, m = graph_run.graph.definition, graph_run.graph.metrics
    assert d["window"]["start"] == START.isoformat() and d["weighting"] == "count"
    assert d["relation_types"] == ["reply_to", "quote_of", "repost_of", "mentions"]
    assert d["parameters"]["seed"] == 11 and d["dataset_version"] == 1
    assert m["algorithm"]["seed"] == 11 and m["algorithm"]["community"] == "louvain"
    assert "bukan penentu pengendali" in m["note"]
    assert graph_run.graph.platform == "x" and graph_run.graph.node_count == len(_nodes(graph_run))


def test_community_stability_across_seeds_is_stored_when_requested(user, m2run) -> None:
    run = _m4(user, m2run.dataset_version, _params(stability_seeds=8))
    assert run.status == AnalysisStatus.COMPLETED, run.error
    st = run.graph.metrics["community_detection"]["stability"]
    assert st["seeds"] == 8 and 1 <= st["distinct_partitions"] <= 8
    assert 0.0 <= st["min_rand_index_vs_first"] <= st["mean_rand_index_vs_first"] <= 1.0
    assert run.output["community_detection"]["stability"] == st
    assert (
        "stability"
        not in _m4(user, m2run.dataset_version, _params()).graph.metrics["community_detection"]
    )


def test_same_parameters_and_seed_reproduce_the_same_graph(user, m2run, p1) -> None:
    params = _params(source_run=m2run, proposition=p1)
    a = _m4(user, m2run.dataset_version, params)
    b = _m4(user, m2run.dataset_version, params)
    assert (
        a.output["graph_digest"] == b.output["graph_digest"] and a.output_digest == b.output_digest
    )


def test_relation_type_selection_and_binary_weighting(user, m2run) -> None:
    only_quotes = _m4(user, m2run.dataset_version, _params(relation_types=["quote_of"]))
    assert set(_edges(only_quotes)) == {("u3", "u1", "quote_of")}
    assert only_quotes.graph.exclusions["relation_type_not_selected"] > 0
    binary = _m4(user, m2run.dataset_version, _params(weighting="binary"))
    assert {e.weight for e in binary.graph.edges.all()} == {1}


def test_window_and_unknown_time_policy_are_applied(user, m2run) -> None:
    narrow = _m4(user, m2run.dataset_version, _params(window_start=ago(2.6), window_end=ago(1.9)))
    assert set(_edges(narrow)) == {("u2", "a0", "reply_to"), ("u1", "u2", "reply_to")}
    assert narrow.graph.exclusions["outside_window"] > 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("seed"),
        lambda p: p.update(extra=1),
        lambda p: p.update(seed=-1),
        lambda p: p.update(seed=True),
        lambda p: p.update(resolution=0),
        lambda p: p.update(resolution=11),
        lambda p: p.update(weighting="berat"),
        lambda p: p.update(unknown_time="mungkin"),
        lambda p: p.update(relation_types=[]),
        lambda p: p.update(relation_types=["follows"]),
        lambda p: p.update(relation_types=["reply_to", "reply_to"]),
        lambda p: p.update(compute_betweenness="ya"),
        lambda p: p.update(metrics_max_nodes=0),
        lambda p: p.update(window_start="2026-10-01T00:00:00"),
        lambda p: p.update(window_end=p["window_start"]),
        lambda p: p.update(source_run=5),  # sebagian terisi saja
        lambda p: p.update(assessments_digest="a" * 64),  # hanya hash
        lambda p: p.update(proposition_id=3),  # hanya proposition
        lambda p: p.update(stability_seeds=1),
        lambda p: p.update(stability_seeds=101),
        lambda p: p.update(stability_seeds=True),
        lambda p: p.update(stability_seeds=2.5),
        lambda p: p.update(source_run=5, assessments_digest="xyz", proposition_id=1),
    ],
)
def test_parameters_are_validated_strictly(user, m2run, mutate) -> None:
    params = _params()
    mutate(params)
    with pytest.raises(InvalidParameters):
        _m4(user, m2run.dataset_version, params, execute=False)


def test_a_changed_assessment_set_blocks_a_stale_graph_run(user, m2run, p1) -> None:
    stale = _params(source_run=m2run, proposition=p1)
    row = next(
        a
        for a in assessment.current_assessments(m2run).select_related("observation__post")
        if a.observation.post.external_post_id == "r3"
    )
    assessment.review_assessment(
        assessment=row, by=user, reason="Ada stance.", issue_stance="CONTRA"
    )
    failed = _m4(user, m2run.dataset_version, stale)
    assert failed.status == AnalysisStatus.FAILED and "penilaian M2 berubah" in failed.error
    assert not GraphProjection.objects.exists()


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

    def failed_with(source, digest=None):
        params = _params(source_run=m2run, proposition=p1)
        params["source_run"] = source.pk
        params["assessments_digest"] = digest or networks.digest_ids([])
        run = _m4(user, dataset, params)
        assert run.status == AnalysisStatus.FAILED and "run M2 selesai" in run.error, run.error

    # selesai TETAPI bukan M2: hanya pemeriksaan metode yang dapat menolaknya
    failed_with(services.execute_run(make("dataset-summary", {"top_authors": 1})))
    # M2 TETAPI belum selesai: hanya pemeriksaan status yang dapat menolaknya
    failed_with(make("m2-rules", example_parameters({p1.pk: CUES})))
    # M2 selesai pada dataset LAIN
    second = new_run(target, user)
    ingest(second, [obs(second, "x1", actor="u9", parent="seed", text="halo")])
    other_m2 = _m2(inv, user, issue, [second], p1)
    other_digest = _params(source_run=other_m2, proposition=p1)["assessments_digest"]
    failed_with(other_m2, other_digest)


def test_a_parent_observed_only_in_another_run_still_gives_the_target_account(
    inv, user, target, conversation
) -> None:
    later = new_run(target, user)
    ingest(
        later,
        [obs(later, "n1", actor="u7", parent="r2", text="balasan baru", published_at=ago(0.3))],
    )
    run = _m4(user, _dataset(inv, user, [conversation, later]), _params())
    assert run.status == AnalysisStatus.COMPLETED, run.error
    assert ("u7", "u2", "reply_to") in _edges(run)  # u2 menulis r2, yang hanya teramati pada run 1


def test_failed_method_leaves_no_graph_rows(user, m2run, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("rusak")

    monkeypatch.setattr(networks, "build_network", boom)
    run = _m4(user, m2run.dataset_version, _params())
    assert run.status == AnalysisStatus.FAILED
    assert not GraphProjection.objects.exists() and not GraphNode.objects.exists()


# --- satu platform per graf (AT-13) -------------------------------------------------------------


def test_AT13_each_graph_has_exactly_one_platform_and_never_mixes_actors(
    inv, user, target, conversation
) -> None:
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/9")
    trun = new_run(tiktok, user)
    ingest(
        trun,
        [
            obs(trun, "tt-root", kind=POST, actor="tt-0", text="video"),
            obs(
                trun,
                "tt1",
                kind=SourceObjectType.COMMENT,
                actor="u1",
                parent="tt-root",
                text="komentar",
            ),
        ],
    )
    x_graph = _m4(user, _dataset(inv, user, [conversation]), _params())
    tt_graph = _m4(user, _dataset(inv, user, [trun]), _params())
    assert x_graph.graph.platform == "x" and tt_graph.graph.platform == "tiktok"
    x_actors = {n.actor_id for n in x_graph.graph.nodes.all()}
    tt_actors = {n.actor_id for n in tt_graph.graph.nodes.all()}
    assert not x_actors & tt_actors  # "u1" ada di kedua platform sebagai akun BERBEDA
    assert {ActorAccount.objects.get(pk=a).platform for a in x_actors} == {"x"}
    assert {ActorAccount.objects.get(pk=a).platform for a in tt_actors} == {"tiktok"}


# --- penjaga database -------------------------------------------------------------------------


def _running_run(user, m2run, method="m4-network", params=None):
    dataset = m2run.dataset_version
    if method == "m4-network":
        run = _m4(user, dataset, params or _params(), execute=False)
    else:
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


def _projection(run, **over):
    fields = dict(
        analysis_run=run,
        platform="x",
        definition={},
        metrics={},
        exclusions={},
        node_count=0,
        edge_count=0,
    )
    fields.update(over)
    return GraphProjection(**fields)


def test_projection_requires_a_running_m4_run_and_the_datasets_platform(
    user, m2run, graph_run
) -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        _projection(graph_run).save()  # run sudah COMPLETED (dan sudah punya graf)
    pending = _m4(user, m2run.dataset_version, _params(), execute=False)
    with pytest.raises(DatabaseError), transaction.atomic():
        _projection(pending).save()  # PENDING
    other_method = _running_run(user, m2run, method="dataset-summary")
    with pytest.raises(DatabaseError), transaction.atomic():
        _projection(other_method).save()  # RUNNING tetapi bukan M4
    ok = _running_run(user, m2run)
    with pytest.raises(DatabaseError), transaction.atomic():
        _projection(ok, platform="tiktok").save()  # platform tidak sama dengan dataset
    _projection(ok).save()  # kontrol


def test_nodes_must_share_the_graphs_platform_and_edges_must_stay_inside_the_graph(
    inv, user, m2run
) -> None:
    run = _running_run(user, m2run)
    projection = _projection(run)
    projection.save()
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/7")
    trun = new_run(tiktok, user)
    ingest(trun, [obs(trun, "t1", actor="tt-1", parent="tt-root", text="halo")])
    foreign = ActorAccount.objects.get(platform="tiktok", external_actor_id="tt-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphNode(projection=projection, actor=foreign, attributes={}, metrics={}).save()
    own = ActorAccount.objects.filter(platform="x")
    a = GraphNode.objects.create(projection=projection, actor=own[0], attributes={}, metrics={})
    b = GraphNode.objects.create(projection=projection, actor=own[1], attributes={}, metrics={})
    # graf kedua (run M4 lain) dengan node sendiri
    run2 = _running_run(user, m2run)
    projection2 = _projection(run2)
    projection2.save()
    c = GraphNode.objects.create(projection=projection2, actor=own[2], attributes={}, metrics={})
    base = dict(relation_type="reply_to", weight=1, observation_ids=[1], stance_counts={})
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphEdge(
            projection=projection, from_node=a, to_node=c, **base
        ).save()  # tujuan di graf lain
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphEdge(projection=projection, from_node=c, to_node=b, **base).save()  # asal di graf lain
    GraphEdge(projection=projection, from_node=a, to_node=b, **base).save()  # kontrol


def test_graph_rows_cannot_be_written_after_the_run_finishes(user, target, graph_run) -> None:
    # akun yang BELUM menjadi node pada graf ini, agar yang menolak trigger, bukan constraint unik
    later = new_run(target, user)
    ingest(later, [obs(later, "z1", actor="zz", parent="seed", text="baru")])
    fresh = ActorAccount.objects.get(platform="x", external_actor_id="zz")
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphNode(projection=graph_run.graph, actor=fresh, attributes={}, metrics={}).save()
    node = graph_run.graph.nodes.first()
    other = graph_run.graph.nodes.exclude(pk=node.pk).first()
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphEdge(
            projection=graph_run.graph,
            from_node=node,
            to_node=other,
            relation_type="mentions",
            weight=1,
            observation_ids=[1],
            stance_counts={},
        ).save()


def test_graph_tables_are_append_only(graph_run) -> None:
    ids = {
        "intelligence_graphprojection": graph_run.graph.pk,
        "intelligence_graphnode": graph_run.graph.nodes.first().pk,
        "intelligence_graphedge": graph_run.graph.edges.first().pk,
    }
    for table, pk in ids.items():
        for sql in (
            f"UPDATE {table} SET id = id WHERE id = %s",
            f"DELETE FROM {table} WHERE id = %s",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute(sql, [pk])


def test_edge_constraints_reject_self_loops_duplicates_unknown_types_and_zero_weight(
    user, m2run
) -> None:
    run = _running_run(user, m2run)
    projection = _projection(run)
    projection.save()
    own = ActorAccount.objects.filter(platform="x")
    a = GraphNode.objects.create(projection=projection, actor=own[0], attributes={}, metrics={})
    b = GraphNode.objects.create(projection=projection, actor=own[1], attributes={}, metrics={})
    base = dict(
        projection=projection,
        relation_type="reply_to",
        weight=1,
        observation_ids=[1],
        stance_counts={},
    )
    for over in (
        {"from_node": a, "to_node": a},
        {"from_node": a, "to_node": b, "relation_type": "follows"},
        {"from_node": a, "to_node": b, "weight": 0},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            GraphEdge(**{**base, **over}).save()
    GraphEdge(**base, from_node=a, to_node=b).save()
    with pytest.raises(DatabaseError), transaction.atomic():
        GraphEdge(**base, from_node=a, to_node=b).save()  # ganda


def test_one_graph_per_run(user, m2run, graph_run) -> None:
    assert GraphProjection.objects.filter(analysis_run=graph_run).count() == 1


def test_guard_functions_do_not_freeze_a_seqscan_plan() -> None:
    names = ["snr_graph_projection_guard", "snr_graph_node_guard", "snr_graph_edge_guard"]
    with connection.cursor() as cur:
        cur.execute("SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(%s)", [names])
        found = dict(cur.fetchall())
    assert set(found) == set(names) and all("enable_seqscan=off" in c for c in found.values())


def test_models_have_no_verdict_or_control_fields() -> None:
    for model in (GraphProjection, GraphNode, GraphEdge):
        names = {f.name for f in model._meta.get_fields()}
        for word in (
            "buzzer",
            "score",
            "skor",
            "controller",
            "leader",
            "influencer",
            "verdict",
            "vonis",
        ):
            assert not any(word in n for n in names), (model.__name__, word)


# --- ujung ke ujung pada dataset sintetis WP-2.0 --------------------------------------------------


def _ingest_bundle(inv, user, bundle):
    runs_by_platform: dict[str, list[InspectionRun]] = {}
    for name, raw in sorted(bundle.datasets.items()):
        dataset = parse_dataset(raw, label=name)
        target = register(inv, user, Platform(dataset.platform.value), raw["target_url"])
        for index in range(len(dataset.snapshots)):
            run = new_run(target, user)
            request = InspectionRequest(
                inspection_run_id=run.run_id,
                platform=dataset.platform,
                target_url=raw["target_url"],
                target_type=TargetType.POST,
                requested=(Capability.INSPECT_POST, Capability.INSPECT_REPLIES),
            )
            ingest_result(run, build_result(dataset, index, request))
            run.refresh_from_db()
            runs_by_platform.setdefault(dataset.platform.value, []).append(run)
    return runs_by_platform


def test_synthetic_dataset_end_to_end_keeps_platforms_apart_and_hides_no_coordination_edges(
    inv, user
) -> None:
    bundle = generate()
    runs = _ingest_bundle(inv, user, bundle)
    window = dict(
        window_start=OBSERVED - timedelta(days=30), window_end=OBSERVED + timedelta(days=30)
    )
    params = _params(**window)
    x = _m4(user, _dataset(inv, user, runs["x"]), params)
    tt = _m4(user, _dataset(inv, user, runs["tiktok"]), params)
    assert x.status == tt.status == AnalysisStatus.COMPLETED, (x.error, tt.error)
    assert x.graph.platform == "x" and tt.graph.platform == "tiktok"
    x_ids = set(x.graph.nodes.values_list("actor__external_actor_id", flat=True))
    tt_ids = set(tt.graph.nodes.values_list("actor__external_actor_id", flat=True))
    assert x.graph.node_count >= 50 and not {a for a in x_ids if a.startswith("tt-")}
    assert all(a.startswith("tt-") for a in tt_ids)
    # kelompok yang ditanam hanya membalas posting yang sama: interaksi langsung tidak mengungkap pola,
    # sehingga tidak ada edge antar-anggota (pola koordinasi menunggu indikator CO di WP-2.5)
    group = set(bundle.ground_truth["accounts"]["planted_group_K"])
    inside = [k for k in _edges(x) if k[0] in group and k[1] in group]
    assert inside == []
    assert x.graph.metrics["community_detection"]["status"] == "OK"
    again = _m4(user, _dataset(inv, user, runs["x"]), params)
    assert again.output["graph_digest"] == x.output["graph_digest"]
