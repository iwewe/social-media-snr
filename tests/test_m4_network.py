"""WP-2.4: Interaction Network, Stance Network View, metrik struktur (FR-070/071/073/074; AT-11)."""

import ast
import inspect
import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from intelligence import m4
from intelligence.m4 import (
    NOT_ASSESSED,
    STRUCTURE_NOTE,
    NetworkParams,
    RelationRecord,
    build_network,
    community_stability,
    rand_index,
    stance_summary,
)

T0 = datetime(2026, 10, 1, tzinfo=UTC)


def params(**over):
    base = dict(
        window_start=T0,
        window_end=T0 + timedelta(days=10),
        unknown_time="include",
        relation_types=("reply_to", "quote_of", "repost_of", "mentions"),
        weighting="count",
        resolution=1.0,
        seed=7,
        compute_betweenness=True,
        metrics_max_nodes=1000,
        stability_seeds=0,
    )
    base.update(over)
    return NetworkParams(**base)


def rel(rid, src, dst, kind="reply_to", *, obs=None, day=1.0, stance=None):
    published = None if day is None else T0 + timedelta(days=day)
    return RelationRecord(rid, kind, src, dst, obs if obs is not None else rid, published, stance)


def net(records, actors=(), attrs=None, **over):
    return build_network(records, actors, attrs or {}, params(**over))


def edge(network, src, dst, kind="reply_to"):
    return next(
        e for e in network.edges if (e.from_actor, e.to_actor, e.relation_type) == (src, dst, kind)
    )


# --- edge: hanya relasi teramati, arah, tipe, asal -------------------------------------------


def test_edges_are_observed_relations_directed_from_author_to_target_with_type_and_origin() -> None:
    n = net(
        [
            rel(1, 10, 20, "reply_to", obs=101),
            rel(2, 10, 20, "quote_of", obs=102),
            rel(3, 30, 10, "repost_of", obs=103),
            rel(4, 10, 40, "mentions", obs=104),
        ]
    )
    assert {(e.from_actor, e.to_actor, e.relation_type) for e in n.edges} == {
        (10, 20, "reply_to"),
        (10, 20, "quote_of"),
        (30, 10, "repost_of"),
        (10, 40, "mentions"),
    }
    assert edge(n, 10, 20, "quote_of").observation_ids == (102,)  # asal tersimpan per edge
    assert edge(n, 30, 10, "repost_of").to_actor == 10 and not any(
        (e.from_actor, e.to_actor) == (20, 10) for e in n.edges
    )  # tidak ada edge balik yang tidak teramati


def test_count_weighting_counts_distinct_observations_and_binary_is_one() -> None:
    records = [rel(1, 10, 20, obs=5), rel(2, 10, 20, obs=6), rel(3, 10, 20, obs=6)]
    assert edge(net(records), 10, 20).weight == 2  # dua observasi berbeda; yang ke-3 duplikat
    assert edge(net(records), 10, 20).observation_ids == (5, 6)
    assert edge(net(records, weighting="binary"), 10, 20).weight == 1


def test_edges_carry_stance_counts_of_the_responses_that_created_them() -> None:
    n = net(
        [
            rel(1, 10, 20, stance="PRO"),
            rel(2, 10, 20, stance="PRO"),
            rel(3, 10, 20, stance="CONTRA"),
            rel(4, 10, 20, kind="repost_of", stance=None),
        ]
    )
    assert edge(n, 10, 20).stance_counts == {"CONTRA": 1, "PRO": 2}
    assert edge(n, 10, 20, "repost_of").stance_counts == {NOT_ASSESSED: 1}


def test_edge_time_span_uses_only_known_times() -> None:
    n = net([rel(1, 10, 20, day=2), rel(2, 10, 20, day=5), rel(3, 10, 20, day=None)])
    e = edge(n, 10, 20)
    assert e.first_published_at == T0 + timedelta(days=2) and e.last_published_at == T0 + timedelta(
        days=5
    )


# --- pengecualian dicatat, tidak hilang diam-diam ---------------------------------------------


def test_exclusions_are_counted_by_reason() -> None:
    n = net(
        [
            rel(1, 10, 20),
            rel(2, None, 20),
            rel(3, 10, None),
            rel(4, 10, 10),
            rel(5, 10, 30, kind="mentions"),
        ],
        relation_types=("reply_to",),
    )
    assert len(n.edges) == 1
    assert n.exclusions == {
        "unknown_actor": 2,
        "self_interaction": 1,
        "relation_type_not_selected": 1,
    }


def test_window_is_start_inclusive_end_exclusive() -> None:
    inside = rel(1, 10, 20, day=0)
    late = rel(2, 11, 21, day=10)
    early = rel(3, 12, 22, day=-1)
    n = net([inside, late, early])
    assert [(e.from_actor, e.to_actor) for e in n.edges] == [(10, 20)]
    assert n.exclusions["outside_window"] == 2


def test_unknown_time_policy_is_explicit() -> None:
    records = [rel(1, 10, 20, day=None)]
    assert len(net(records, unknown_time="include").edges) == 1
    excluded = net(records, unknown_time="exclude")
    assert excluded.edges == [] and excluded.exclusions["unknown_time_excluded"] == 1


# --- AT-11: stance sama tidak membuat edge ------------------------------------------------------


def test_AT11_many_accounts_with_the_same_stance_get_no_edges_between_them() -> None:
    actors = range(100, 112)
    attrs = {a: {"stance_counts": {"PRO": 3}, "stance_summary": "PRO"} for a in actors}
    n = net([rel(1, 100, 1)], actors, attrs)  # hanya satu relasi nyata, ke akun lain
    assert len(n.edges) == 1
    same = [e for e in n.edges if e.from_actor in actors and e.to_actor in actors]
    assert same == []
    assert all(n.nodes[a]["stance_summary"] == "PRO" for a in actors)  # stance = atribut
    assert n.metrics["edges"] == 1 and n.metrics["distinct_connected_pairs"] == 1


def test_isolated_accounts_are_nodes_with_their_attributes() -> None:
    n = net([], [5, 6], {5: {"stance_summary": "PRO"}})
    assert set(n.nodes) == {5, 6} and n.nodes[5]["stance_summary"] == "PRO"
    assert n.nodes[6].get("stance_summary") is None
    assert n.nodes[5]["metrics"]["in_degree"] == 0


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({}, "UNDETERMINED"),
        ({"UNDETERMINED": 4, "NOT_RELEVANT": 1}, "UNDETERMINED"),
        ({"PRO": 2}, "PRO"),
        ({"CONTRA": 1, "UNDETERMINED": 3}, "CONTRA"),
        ({"PRO": 1, "CONTRA": 1}, "MIXED"),
        ({"MIXED": 3}, "UNDETERMINED"),
    ],
)
def test_stance_summary_is_an_attribute_rule_not_a_verdict(counts, expected) -> None:
    assert stance_summary(counts) == expected


# --- metrik struktur --------------------------------------------------------------------------


def two_cliques():
    records, rid = [], 0
    for group in ((1, 2, 3, 4), (11, 12, 13, 14)):
        for a in group:
            for b in group:
                if a < b:
                    rid += 1
                    records.append(rel(rid, a, b))
    records.append(rel(900, 4, 11))  # satu jembatan lemah
    return records


def test_degree_and_strength_are_computed_per_node() -> None:
    n = net(
        [rel(1, 10, 20, obs=1), rel(2, 10, 20, obs=2), rel(3, 10, 30, obs=3), rel(4, 20, 10, obs=4)]
    )
    m = n.nodes[10]["metrics"]
    assert (m["out_degree"], m["in_degree"]) == (2, 1)
    assert (m["out_strength"], m["in_strength"]) == (3, 1)
    assert (
        n.metrics["nodes"] == 3 and n.metrics["edges"] == 3
    )  # dua relasi 10->20 menjadi satu edge


def test_communities_separate_two_cliques_and_labels_are_ordered_by_smallest_account() -> None:
    n = net(two_cliques())
    labels = {a: n.nodes[a]["metrics"]["community"] for a in n.nodes}
    assert (
        len({labels[a] for a in (1, 2, 3, 4)}) == 1
        and len({labels[a] for a in (11, 12, 13, 14)}) == 1
    )
    assert labels[1] == 0 and labels[11] == 1  # urutan berdasarkan ID akun terkecil
    d = n.metrics["community_detection"]
    assert (
        d["status"] == "OK"
        and d["communities"] == 2
        and d["sizes"] == [4, 4]
        and d["modularity"] > 0.3
    )


def test_same_seed_and_parameters_reproduce_the_same_structure() -> None:
    a, b = net(two_cliques()), net(two_cliques())
    assert {k: v["metrics"] for k, v in a.nodes.items()} == {
        k: v["metrics"] for k, v in b.nodes.items()
    }
    assert a.metrics == b.metrics


def test_algorithm_parameters_and_the_structure_note_are_stored_with_the_graph() -> None:
    n = net(two_cliques(), resolution=1.5, seed=99)
    alg = n.metrics["algorithm"]
    assert (alg["resolution"], alg["seed"], alg["community"]) == (1.5, 99, "louvain") and alg[
        "networkx"
    ]
    assert n.metrics["note"] == STRUCTURE_NOTE and "bukan penentu pengendali" in STRUCTURE_NOTE
    assert "per_node" not in n.metrics


def test_betweenness_is_optional_and_highest_for_the_bridge_node() -> None:
    chain = [rel(1, 1, 2), rel(2, 2, 3), rel(3, 3, 4)]
    on = net(chain)
    assert on.metrics["betweenness"]["status"] == "OK"
    scores = {a: on.nodes[a]["metrics"]["betweenness"] for a in on.nodes}
    assert max(scores, key=scores.get) in (2, 3) and scores[1] == scores[4] == 0.0
    off = net(chain, compute_betweenness=False)
    assert off.metrics["betweenness"]["status"] == "NOT_REQUESTED"
    assert "betweenness" not in off.nodes[2]["metrics"]


def test_large_graphs_skip_expensive_metrics_but_keep_degrees_and_say_so() -> None:
    n = net(two_cliques(), metrics_max_nodes=5)
    assert n.metrics["community_detection"]["status"] == "SKIPPED_TOO_LARGE"
    assert n.metrics["betweenness"]["status"] == "SKIPPED_TOO_LARGE"
    assert "community" not in n.nodes[1]["metrics"] and n.nodes[1]["metrics"]["out_degree"] >= 1


def test_graph_without_edges_has_singleton_communities_and_no_modularity() -> None:
    n = net([], [1, 2, 3])
    d = n.metrics["community_detection"]
    assert d["communities"] == 3 and d["modularity"] is None and n.metrics["density"] is not None
    assert net([], []).metrics["nodes"] == 0


# --- stabilitas -------------------------------------------------------------------------------


def test_rand_index_known_values() -> None:
    same = {1: 0, 2: 0, 3: 1, 4: 1}
    assert rand_index(same, {1: 5, 2: 5, 3: 9, 4: 9}) == 1.0  # label berbeda, partisi sama
    assert rand_index(same, {1: 0, 2: 1, 3: 0, 4: 1}) == pytest.approx(2 / 6)
    assert rand_index({1: 0}, {1: 7}) == 1.0
    with pytest.raises(ValueError):
        rand_index({1: 0}, {2: 0})


def test_community_stability_reports_agreement_across_seeds() -> None:
    n = net(two_cliques())
    s = community_stability(n, 1.0, list(range(10)))
    assert s["seeds"] == 10 and s["distinct_partitions"] == 1
    assert s["mean_rand_index_vs_first"] == 1.0 and s["min_rand_index_vs_first"] == 1.0
    assert "bukan ukuran kebenaran" in s["note"]
    with pytest.raises(ValueError):
        community_stability(n, 1.0, [1])


def test_stability_detects_an_unstable_partition() -> None:
    # cincin tanpa struktur komunitas jelas: partisi Louvain bergantung pada seed
    ring = [rel(i, i, i % 40 + 1) for i in range(1, 41)]
    s = community_stability(net(ring), 1.0, list(range(30)))
    assert s["distinct_partitions"] > 1 and s["min_rand_index_vs_first"] < 1.0


# --- penjaga nama --------------------------------------------------------------------------------


def test_no_verdict_or_control_vocabulary_in_names() -> None:
    root = pathlib.Path(inspect.getsourcefile(m4)).parent
    for path in root.glob("*.py"):
        names = set()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.FunctionDef | ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.Dict):
                names.update(
                    k.value
                    for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                )
        for word in (
            "buzzer",
            "score",
            "skor",
            "controller",
            "pengendali_",
            "leader",
            "influencer",
            "verdict",
            "vonis",
        ):
            assert not any(word in n.lower() for n in names), (path.name, word)


def test_stability_is_measured_only_when_requested_and_stored_with_the_communities() -> None:
    off = net(two_cliques())
    assert "stability" not in off.metrics["community_detection"]
    on = net(two_cliques(), stability_seeds=6)
    st = on.metrics["community_detection"]["stability"]
    assert (
        st["seeds"] == 6
        and st["distinct_partitions"] == 1
        and st["mean_rand_index_vs_first"] == 1.0
    )
    ring = [rel(i, i, i % 40 + 1) for i in range(1, 41)]
    unstable = net(ring, stability_seeds=30).metrics["community_detection"]["stability"]
    assert unstable["distinct_partitions"] > 1 and unstable["min_rand_index_vs_first"] < 1.0
    assert (
        net(ring, stability_seeds=30).metrics == net(ring, stability_seeds=30).metrics
    )  # terulang


def test_stability_summary_uses_min_mean_and_distinct_counts_of_the_partitions(monkeypatch) -> None:
    from intelligence.m4 import stability

    base = {1: 0, 2: 0, 3: 1, 4: 1}
    half = {1: 0, 2: 1, 3: 0, 4: 1}  # indeks Rand terhadap base = 2/6
    partitions = iter([base, half, base, base])
    monkeypatch.setattr(stability, "_partition", lambda *a, **k: next(partitions))
    s = community_stability(net([rel(1, 1, 2), rel(2, 3, 4)]), 1.0, [1, 2, 3, 4])
    assert s["distinct_partitions"] == 2
    assert s["min_rand_index_vs_first"] == pytest.approx(2 / 6, abs=1e-6)
    assert s["mean_rand_index_vs_first"] == pytest.approx((2 / 6 + 1 + 1) / 3, abs=1e-6)
