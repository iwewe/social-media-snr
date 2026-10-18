"""Perakitan hasil indikator koordinasi: tepi per (pasangan, indikator), baseline, korelasi.

Hasil adalah INDIKATOR, bukan Finding dan bukan skor: tiap tepi membawa nilai, dukungan, bukti (ID
observasi), penjelasan, perbandingan baseline, indikator lain yang berbagi bukti, dan hipotesis
alternatif yang wajib dipertimbangkan (PRD 11.5). Peninjauan manusia diperlukan sebelum
menjadi Finding.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .baseline import exceedance, permutation_maxima, summarize
from .coordination import (
    CoordParams,
    Events,
    Pair,
    Response,
    build_events,
    evidence_overlaps,
    independent_groups,
    indicator_values,
    statistic,
)

ALTERNATIVE_HYPOTHESES = (
    "mobilisasi organik: banyak akun tidak terkait menanggapi isu yang sama pada waktu yang mirip",
    "efek berita atau peristiwa eksternal yang mendorong reaksi serentak",
    "penyalinan konten publik (tautan, kutipan, templat) tanpa pengaturan bersama",
    "bias sampling atau cakupan pengamatan (hanya sebagian objek/akun teramati)",
)
SPECIFIC_ALTERNATIVES = {
    "CO-01": "topik atau posting yang viral menarik banyak penjawab secara wajar",
    "CO-02": "reaksi serentak terhadap peristiwa luar; ketelitian waktu antar-platform berbeda",
    "CO-03": "balasan pendek atau generik (mis. persetujuan) memang mirip secara wajar",
    "CO-04": "daftar repost/kutipan platform dapat tidak lengkap; pasangan terlihat lebih jarang",
    "CO-05:url": "tautan populer dibagikan banyak orang; lihat jumlah akun yang membagikannya",
    "CO-05:phrase": "frasa umum atau templat percakapan muncul pada banyak akun",
    "CO-06": "komunitas dengan minat sama selalu muncul bersama pada banyak target",
}
NOTICE = (
    "Indikator, bukan temuan: tidak membuktikan koordinasi, pengendali, atau niat; wajib "
    "ditinjau manusia dan dibandingkan dengan hipotesis alternatif sebelum menjadi Finding."
)


@dataclass
class IndicatorEdge:
    actor_a: int
    actor_b: int
    indicator: str
    variant: str
    value: float
    support: int
    observation_ids: list[int]
    truncated: bool
    detail: dict[str, Any]
    explanation: str
    baseline: dict[str, Any]
    overlaps_with: list[str]
    alternative_hypotheses: list[str]

    @property
    def label(self) -> str:
        return self.indicator if not self.variant else f"{self.indicator}:{self.variant}"


@dataclass
class CoordinationResult:
    edges: list[IndicatorEdge]
    exclusions: dict[str, int]
    baseline: dict[str, Any]
    pair_summary: dict[str, Any]
    events: int
    notice: str = NOTICE
    extra: dict[str, Any] = field(default_factory=dict)


def _explain(label: str, pair: Pair, value: float, support: int, detail: dict[str, Any]) -> str:
    who = f"akun {pair[0]} dan akun {pair[1]}"
    return {
        "CO-01": f"{who} membalas {support} posting induk yang sama (Jaccard {value:.2f})",
        "CO-02": f"{who} membalas {support} posting induk yang sama dalam jendela sempit",
        "CO-03": f"{who} menulis {support} pasangan respons mirip (tertinggi {value:.2f})",
        "CO-04": f"{who} me-repost/mengutip {support} objek yang sama dalam jendela waktu sempit",
        "CO-05:url": f"{who} berbagi tautan (domain+path) sama pada {support} pasangan respons",
        "CO-05:phrase": f"{who} berbagi frasa kata sama pada {support} pasangan respons",
        "CO-06": f"{who} sama-sama merespons pada {support} target berbeda dalam platform ini",
    }[label]


def run_indicators(responses: list[Response], params: CoordParams) -> CoordinationResult:
    events: Events = build_events(responses, params)
    labels = [r.actor_id for r in responses]
    observed = indicator_values(
        responses, labels, events, params, with_evidence=True, apply_min=True
    )
    maxima = permutation_maxima(responses, labels, events, params) if params.permutations else {}
    raw = indicator_values(responses, labels, events, params, with_evidence=False, apply_min=False)
    observed_max = {k: max((statistic(k, pv) for pv in raw[k].values()), default=0.0) for k in raw}
    summary: dict[str, Any] = (
        summarize(maxima, observed_max, params.permutations)
        if params.permutations
        else {"status": "NOT_COMPUTED", "note": "permutations = 0"}
    )

    per_pair: dict[Pair, dict[tuple[str, str], set[int]]] = defaultdict(dict)
    for key, pairs in observed.items():
        for pair, pv in pairs.items():
            per_pair[pair][key] = pv.observation_ids
    edges: list[IndicatorEdge] = []
    pair_summary: dict[str, Any] = {}
    for pair in sorted(per_pair):
        overlaps = evidence_overlaps(per_pair[pair])
        pair_summary[f"{pair[0]}-{pair[1]}"] = {
            "indicators": sorted(f"{k[0]}:{k[1]}" if k[1] else k[0] for k in per_pair[pair]),
            "independent_evidence_groups": independent_groups(per_pair[pair]),
        }
        for key in sorted(per_pair[pair]):
            pv = observed[key][pair]
            label = key[0] if not key[1] else f"{key[0]}:{key[1]}"
            ids = sorted(pv.observation_ids)
            stat = statistic(key, pv)
            if params.permutations:
                p95 = summary[label]["p95_of_max"]
                baseline = {
                    "permutations": params.permutations,
                    "statistic": "support",
                    "p_max_ge": exceedance(stat, maxima[key]),
                    "baseline_p95_of_max": p95,
                    "exceeds_baseline_p95": stat > p95,
                }
            else:
                baseline = {"status": "NOT_COMPUTED"}
            edges.append(
                IndicatorEdge(
                    actor_a=pair[0],
                    actor_b=pair[1],
                    indicator=key[0],
                    variant=key[1],
                    value=pv.value,
                    support=pv.support,
                    observation_ids=ids[: params.evidence_limit],
                    truncated=len(ids) > params.evidence_limit,
                    detail=pv.detail,
                    explanation=_explain(label, pair, pv.value, pv.support, pv.detail),
                    baseline=baseline,
                    overlaps_with=overlaps[key],
                    alternative_hypotheses=[*ALTERNATIVE_HYPOTHESES, SPECIFIC_ALTERNATIVES[label]],
                )
            )
    return CoordinationResult(
        edges=edges,
        exclusions=dict(sorted(events.exclusions.items())),
        baseline=summary,
        pair_summary=pair_summary,
        events=events.size(),
    )
