"""Indikator koordinasi sebagai metode AnalysisRun `co-indicators` (WP-2.5; ADR 0029).

Membaca observasi dan relasi yang SUDAH tersimpan pada dataset beku satu platform (tanpa mengambil
data). Tidak memakai M2 sama sekali: stance dan intensitas tidak membentuk indikator (FR-075).
Semua ambang adalah parameter eksplisit di AnalysisRun; tidak ada nilai bawaan.
Hasil berupa INDIKATOR, bukan Finding; peninjauan manusia diperlukan (FR-077).
"""

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from collection.models import ActorAccount, PostObservation, PostRelation, RelationType

from .digest import digest_json
from .errors import InvalidParameters
from .m4.coordination import CoordParams, Response
from .m4.indicators import ALTERNATIVE_HYPOTHESES, NOTICE, run_indicators
from .models import AnalysisRun, CoordinationEdge, CoordinationNetwork

KINDS = ("reply", "comment", "quote", "repost")
_BATCH = 1000
_INT_RANGES: dict[str, tuple[int, int]] = {
    "sync_window_seconds": (1, 86_400),
    "sync_min_events": (1, 1000),
    "co_response_min_shared": (1, 1000),
    "similarity_ngram": (2, 10),
    "similarity_min_chars": (1, 1000),
    "similarity_min_pairs": (1, 10_000),
    "similarity_max_responses": (2, 5000),
    "amplification_window_seconds": (1, 86_400),
    "amplification_min_events": (1, 1000),
    "url_min_shared": (1, 10_000),
    "phrase_min_shared": (1, 10_000),
    "repeated_min_shared_targets": (2, 1000),
    "baseline_seed": (0, 2**31 - 1),
    "evidence_limit": (1, 500),
    "max_pair_events": (1000, 10_000_000),
}
_KEYS = {
    "window_start",
    "window_end",
    "similarity_threshold",
    "phrase_words",
    "permutations",
    *_INT_RANGES,
}


def coordination_parameters(
    *, window_start: datetime, window_end: datetime, **values: Any
) -> dict[str, Any]:
    """Susun parameter run; seluruh nilai wajib eksplisit (tanpa bawaan)."""
    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        **values,
    }


def _int(parameters: Mapping[str, Any], key: str, low: int, high: int) -> int:
    value = parameters[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidParameters(f"{key} harus bilangan bulat {low}..{high}")
    return value


def _time(parameters: Mapping[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(parameters[key]))
    except ValueError:
        raise InvalidParameters(f"{key} bukan waktu ISO-8601") from None
    if value.tzinfo is None:
        raise InvalidParameters(f"{key} wajib memuat zona waktu")
    return value


def _parse(parameters: Mapping[str, Any]) -> tuple[CoordParams, datetime, datetime]:
    if set(parameters) != _KEYS:
        raise InvalidParameters(f"parameter wajib tepat: {sorted(_KEYS)}")
    start, end = _time(parameters, "window_start"), _time(parameters, "window_end")
    if end <= start:
        raise InvalidParameters("window_end harus setelah window_start")
    threshold = parameters["similarity_threshold"]
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, int | float)
        or not 0 < threshold <= 1
    ):
        raise InvalidParameters("similarity_threshold harus angka (0, 1]")
    phrase = parameters["phrase_words"]
    if (
        isinstance(phrase, bool)
        or not isinstance(phrase, int)
        or not (phrase == 0 or 3 <= phrase <= 12)
    ):
        raise InvalidParameters("phrase_words harus 0 (tidak dipakai) atau 3..12")
    permutations = parameters["permutations"]
    if (
        isinstance(permutations, bool)
        or not isinstance(permutations, int)
        or not (permutations == 0 or 10 <= permutations <= 1000)
    ):
        raise InvalidParameters("permutations harus 0 (tanpa baseline) atau 10..1000")
    ints = {key: _int(parameters, key, *bounds) for key, bounds in _INT_RANGES.items()}
    return (
        CoordParams(
            similarity_threshold=float(threshold),
            phrase_words=phrase,
            permutations=permutations,
            **ints,
        ),
        start,
        end,
    )


def validate_coordination_parameters(parameters: Mapping[str, Any]) -> None:
    _parse(parameters)


def _responses(
    observation_ids: tuple[int, ...], start: datetime, end: datetime
) -> tuple[list[Response], Counter]:
    exclusions: Counter = Counter()
    rows: list[dict[str, Any]] = [
        dict(r)
        for r in PostObservation.objects.filter(
            id__in=observation_ids, source_object_type__in=KINDS
        ).values(
            "id",
            "post_id",
            "run_id",
            "run__sequence",
            "run__target_id",
            "author_id",
            "source_object_type",
            "published_at",
            "text",
        )
    ]
    latest: dict[int, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: (r["run__sequence"], r["id"])):
        latest[row["post_id"]] = row  # satu Post = satu respons: observasi terbarunya
    relations: dict[tuple[int, int], dict[str, int | None]] = {}
    for rel in PostRelation.objects.filter(
        run_id__in={r["run_id"] for r in latest.values()},
        relation_type__in=[RelationType.REPLY_TO, RelationType.REPOST_OF, RelationType.QUOTE_OF],
    ).values("run_id", "from_post_id", "relation_type", "to_post_id"):
        slot = relations.setdefault((rel["run_id"], rel["from_post_id"]), {})
        slot["parent" if rel["relation_type"] == RelationType.REPLY_TO else "amplified"] = rel[
            "to_post_id"
        ]
    responses: list[Response] = []
    for post_id in sorted(latest):
        row = latest[post_id]
        if row["author_id"] is None:
            exclusions["responses_without_author"] += 1
            continue
        when = row["published_at"]
        if when is not None and not start <= when < end:
            exclusions["responses_outside_window"] += 1
            continue
        link = relations.get((row["run_id"], post_id), {})
        responses.append(
            Response(
                index=len(responses),
                observation_id=row["id"],
                post_id=post_id,
                actor_id=row["author_id"],
                target_id=row["run__target_id"],
                kind=row["source_object_type"],
                parent_post_id=link.get("parent"),
                amplified_post_id=link.get("amplified"),
                published_at=when,
                text=row["text"],
            )
        )
    return responses, exclusions


def run_co_indicators(frozen: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    params, start, end = _parse(parameters)
    run = AnalysisRun.objects.select_related("dataset_version").get(pk=frozen.run_id)
    dataset = run.dataset_version
    responses, exclusions = _responses(frozen.observation_ids, start, end)
    actors = {r.actor_id for r in responses}
    if ActorAccount.objects.filter(pk__in=actors).exclude(platform=dataset.platform).exists():
        raise InvalidParameters("akun dari platform lain tidak boleh masuk analisis ini")
    result = run_indicators(responses, params)
    all_exclusions = dict(sorted({**exclusions, **result.exclusions}.items()))
    network = CoordinationNetwork.objects.create(
        analysis_run=run,
        platform=dataset.platform,
        definition={
            "notice": NOTICE,
            "alternative_hypotheses": list(ALTERNATIVE_HYPOTHESES),
            "unit": "pasangan akun pada satu platform",
            "response_rule": "satu Post = satu respons (observasi terbarunya dalam dataset)",
            "stance_used": False,
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "dataset_version": dataset.number,
            "parameters": parameters,
            "baseline_rule": (
                "label akun diacak antar respons (jumlah respons per akun tetap), seed tetap; "
                "pembanding = nilai maksimum antar-pasangan per indikator"
            ),
            "comparison_statistic": "dukungan (jumlah kejadian) untuk semua indikator",
        },
        baseline=result.baseline,
        exclusions=all_exclusions,
        pair_summary=result.pair_summary,
        responses_considered=len(responses),
        events=result.events,
        edge_count=len(result.edges),
    )
    CoordinationEdge.objects.bulk_create(
        (
            CoordinationEdge(
                network=network,
                actor_a_id=e.actor_a,
                actor_b_id=e.actor_b,
                indicator=e.indicator,
                variant=e.variant,
                value=e.value,
                support=e.support,
                observation_ids=e.observation_ids,
                evidence_truncated=e.truncated,
                detail=e.detail,
                explanation=e.explanation,
                baseline=e.baseline,
                overlaps_with=e.overlaps_with,
                alternative_hypotheses=e.alternative_hypotheses,
            )
            for e in result.edges
        ),
        batch_size=_BATCH,
    )
    by_indicator = Counter(e.label for e in result.edges)
    signature = [
        (e.actor_a, e.actor_b, e.label, e.value, e.support, e.observation_ids, e.baseline)
        for e in result.edges
    ]
    return {
        "edges": len(result.edges),
        "pairs": len(result.pair_summary),
        "responses_considered": len(responses),
        "by_indicator": dict(sorted(by_indicator.items())),
        "beyond_baseline_edges": sum(
            1 for e in result.edges if e.baseline.get("exceeds_baseline_p95") is True
        ),
        "baseline": result.baseline,
        "exclusions": all_exclusions,
        "notice": NOTICE,
        "result_digest": digest_json(signature),
    }


def register() -> None:
    from .methods import REGISTRY, Method

    REGISTRY["co-indicators"] = Method(
        "co-indicators", "1", validate_coordination_parameters, run_co_indicators
    )
