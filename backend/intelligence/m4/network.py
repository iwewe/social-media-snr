"""Interaction Network + Stance Network View + metrik struktur (WP-2.4; FR-070/071/073/074).

Aturan:
- Node = akun pada SATU platform; edge = relasi yang BENAR-BENAR teramati (reply/quote/repost/
  mention), arah dari penulis ke akun yang dituju; tipe dan asal (ID observasi) tersimpan per edge.
- Stance hanyalah ATRIBUT node/edge. Stance yang sama TIDAK membuat edge.
- Metrik (derajat, betweenness, komunitas Louvain) menggambarkan struktur; bukan penentu
  pengendali. Seed dan parameter disimpan agar komunitas dapat direproduksi; label komunitas
  diurutkan deterministik.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import networkx as nx

from .types import (
    NOT_ASSESSED,
    STRUCTURE_NOTE,
    Edge,
    Network,
    NetworkParams,
    RelationRecord,
)


def _in_window(record: RelationRecord, params: NetworkParams) -> str | None:
    """None = ikut; selain itu alasan pengecualian."""
    if record.published_at is None:
        return None if params.unknown_time == "include" else "unknown_time_excluded"
    if params.window_start <= record.published_at < params.window_end:
        return None
    return "outside_window"


def stance_summary(counts: Mapping[str, int]) -> str:
    """Ringkasan ATRIBUT dari hitungan stance respons akun; bukan label akun.

    Hanya PRO/CONTRA yang menentukan; keduanya ada -> MIXED; tak ada -> UNDETERMINED.
    """
    pro, contra = counts.get("PRO", 0), counts.get("CONTRA", 0)
    if pro and contra:
        return "MIXED"
    if pro:
        return "PRO"
    if contra:
        return "CONTRA"
    return "UNDETERMINED"


def build_network(
    records: Sequence[RelationRecord],
    actors: Iterable[int],
    node_attributes: Mapping[int, Mapping[str, Any]],
    params: NetworkParams,
) -> Network:
    exclusions: Counter = Counter()
    grouped: dict[tuple[int, int, str], list[RelationRecord]] = {}
    endpoints: set[int] = set(actors)
    for record in records:
        if record.relation_type not in params.relation_types:
            exclusions["relation_type_not_selected"] += 1
            continue
        if record.from_actor is None or record.to_actor is None:
            exclusions["unknown_actor"] += 1
            continue
        if record.from_actor == record.to_actor:
            exclusions["self_interaction"] += 1
            continue
        reason = _in_window(record, params)
        if reason:
            exclusions[reason] += 1
            continue
        grouped.setdefault((record.from_actor, record.to_actor, record.relation_type), []).append(
            record
        )
        endpoints.update((record.from_actor, record.to_actor))
    edges = []
    for (src, dst, kind), group in sorted(grouped.items()):
        observation_ids = sorted({r.from_observation_id for r in group})
        times = [r.published_at for r in group if r.published_at is not None]
        edges.append(
            Edge(
                from_actor=src,
                to_actor=dst,
                relation_type=kind,
                weight=len(observation_ids) if params.weighting == "count" else 1,
                observation_ids=tuple(observation_ids),
                stance_counts=dict(
                    sorted(Counter(r.stance or NOT_ASSESSED for r in group).items())
                ),
                first_published_at=min(times) if times else None,
                last_published_at=max(times) if times else None,
            )
        )
    nodes = {actor: dict(node_attributes.get(actor, {})) for actor in sorted(endpoints)}
    network = Network(nodes=nodes, edges=edges, exclusions=exclusions)
    network.metrics = compute_metrics(network, params)
    for actor, per_node in network.metrics.pop("per_node").items():
        network.nodes[actor]["metrics"] = per_node
    return network


def _partition(
    nodes: Iterable[int], weights: Mapping[tuple[int, int], int], resolution: float, seed: int
) -> dict[int, int]:
    """Komunitas Louvain; label diurutkan menurut ID akun terkecil agar stabil antar-proses."""
    graph: nx.Graph[int] = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    for (a, b), w in sorted(weights.items()):
        graph.add_edge(a, b, weight=w)
    groups = nx.community.louvain_communities(
        graph, weight="weight", resolution=resolution, seed=seed
    )
    ordered = sorted((sorted(g) for g in groups), key=lambda g: g[0])
    return {actor: index for index, group in enumerate(ordered) for actor in group}


def compute_metrics(network: Network, params: NetworkParams) -> dict[str, Any]:
    nodes = sorted(network.nodes)
    digraph: nx.DiGraph[int] = nx.DiGraph()
    digraph.add_nodes_from(nodes)
    for e in network.edges:
        existing = digraph.get_edge_data(e.from_actor, e.to_actor, {"weight": 0})["weight"]
        digraph.add_edge(e.from_actor, e.to_actor, weight=existing + e.weight)
    per_node: dict[int, dict[str, Any]] = {
        n: {
            "in_degree": digraph.in_degree(n),
            "out_degree": digraph.out_degree(n),
            "in_strength": digraph.in_degree(n, weight="weight"),
            "out_strength": digraph.out_degree(n, weight="weight"),
        }
        for n in nodes
    }
    weights = network.undirected_weights()
    metrics: dict[str, Any] = {
        "note": STRUCTURE_NOTE,
        "algorithm": {
            "networkx": nx.__version__,
            "community": "louvain",
            "resolution": params.resolution,
            "seed": params.seed,
            "betweenness": "networkx.betweenness_centrality (tak berbobot, berarah)",
        },
        "nodes": len(nodes),
        "edges": len(network.edges),
        "distinct_connected_pairs": len(weights),
        "weakly_connected_components": nx.number_weakly_connected_components(digraph)
        if nodes
        else 0,
        "density": round(nx.density(digraph), 6) if len(nodes) > 1 else None,
    }
    if len(nodes) > params.metrics_max_nodes:
        metrics["community_detection"] = {
            "status": "SKIPPED_TOO_LARGE",
            "node_limit": params.metrics_max_nodes,
        }
        metrics["betweenness"] = {
            "status": "SKIPPED_TOO_LARGE",
            "node_limit": params.metrics_max_nodes,
        }
    else:
        partition = _partition(nodes, weights, params.resolution, params.seed)
        for n in nodes:
            per_node[n]["community"] = partition[n]
        graph: nx.Graph[int] = nx.Graph()
        graph.add_nodes_from(nodes)
        for (a, b), w in weights.items():
            graph.add_edge(a, b, weight=w)
        groups = [{n for n in nodes if partition[n] == c} for c in sorted(set(partition.values()))]
        modularity = (
            nx.community.modularity(graph, groups, weight="weight", resolution=params.resolution)
            if weights
            else None
        )
        detection: dict[str, Any] = {
            "status": "OK",
            "communities": len(groups),
            "sizes": sorted((len(g) for g in groups), reverse=True),
            "modularity": None if modularity is None else round(modularity, 6),
        }
        if params.stability_seeds:
            from .stability import community_stability

            detection["stability"] = community_stability(
                network,
                params.resolution,
                [params.seed + i for i in range(params.stability_seeds)],
            )
        metrics["community_detection"] = detection
        if params.compute_betweenness:
            between = nx.betweenness_centrality(digraph)
            for n in nodes:
                per_node[n]["betweenness"] = round(between[n], 6)
            metrics["betweenness"] = {"status": "OK"}
        else:
            metrics["betweenness"] = {"status": "NOT_REQUESTED"}
    metrics["per_node"] = per_node
    return metrics
