"""Baseline permutasi untuk indikator koordinasi (WP-2.5; ADR 0029). Murni.

Label akun diacak antar respons (jumlah respons tiap akun tetap), `permutations` kali dengan seed
tetap; peristiwa pasangan-respons (waktu, teks, tautan, induk) TIDAK berubah. Statistik pembanding
= nilai MAKSIMUM antar-pasangan per indikator, agar perbandingan memperhitungkan banyaknya
pasangan yang diuji. Ini pembanding "seberapa besar nilai terbesar yang muncul tanpa struktur
akun", BUKAN uji signifikansi dan BUKAN bukti koordinasi.
"""

import math
import random
from collections.abc import Sequence
from typing import Any

from .coordination import KEYS, CoordParams, Events, Response, indicator_values, statistic


def nearest_rank(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(q * len(sorted_values)))
    return sorted_values[rank - 1]


def permutation_maxima(
    responses: Sequence[Response], labels: Sequence[int], events: Events, params: CoordParams
) -> dict[tuple[str, str], list[float]]:
    rng = random.Random(params.baseline_seed)
    maxima: dict[tuple[str, str], list[float]] = {k: [] for k in KEYS}
    for _ in range(params.permutations):
        shuffled = list(labels)
        rng.shuffle(shuffled)
        values = indicator_values(
            responses, shuffled, events, params, with_evidence=False, apply_min=False
        )
        for key in KEYS:
            maxima[key].append(
                max((statistic(key, pv) for pv in values[key].values()), default=0.0)
            )
    return maxima


def summarize(
    maxima: dict[tuple[str, str], list[float]],
    observed_max: dict[tuple[str, str], float],
    permutations: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in KEYS:
        values = sorted(maxima[key])
        label = key[0] if not key[1] else f"{key[0]}:{key[1]}"
        out[label] = {
            "permutations": permutations,
            "mean_of_max": round(sum(values) / len(values), 6) if values else None,
            "p95_of_max": nearest_rank(values, 0.95) if values else None,
            "max_of_max": values[-1] if values else None,
            "observed_max": observed_max.get(key, 0.0),
        }
    return out


def exceedance(value: float, maxima: Sequence[float]) -> float | None:
    """(1 + banyak permutasi dengan maksimum >= nilai) / (1 + banyak permutasi)."""
    if not maxima:
        return None
    return round((1 + sum(1 for m in maxima if m >= value)) / (1 + len(maxima)), 6)
