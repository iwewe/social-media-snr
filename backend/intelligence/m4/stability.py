"""Stabilitas deteksi komunitas terhadap seed (PRD bagian 18 menyebutnya belum diketahui).

Mengukur seberapa konsisten partisi Louvain antar-seed pada graf yang sama dengan indeks Rand
(pasangan node yang sama-komunitas/beda-komunitas pada kedua partisi). 1.0 = identik.
"""

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

from .network import _partition
from .types import Network


def rand_index(a: Mapping[int, int], b: Mapping[int, int]) -> float:
    nodes = sorted(a)
    if set(a) != set(b):
        raise ValueError("partisi harus memuat node yang sama")
    pairs = list(combinations(nodes, 2))
    if not pairs:
        return 1.0
    agree = sum((a[x] == a[y]) == (b[x] == b[y]) for x, y in pairs)
    return agree / len(pairs)


def community_stability(
    network: Network, resolution: float, seeds: Sequence[int]
) -> dict[str, Any]:
    if len(seeds) < 2:
        raise ValueError("minimal dua seed")
    weights = network.undirected_weights()
    partitions = [_partition(network.nodes, weights, resolution, s) for s in seeds]
    rands = [rand_index(partitions[0], p) for p in partitions[1:]]
    distinct = {tuple(sorted(p.items())) for p in partitions}
    return {
        "seeds": len(seeds),
        "distinct_partitions": len(distinct),
        "mean_rand_index_vs_first": round(sum(rands) / len(rands), 6),
        "min_rand_index_vs_first": round(min(rands), 6),
        "note": "ukuran kestabilan algoritma pada graf ini; bukan ukuran kebenaran struktur",
    }
