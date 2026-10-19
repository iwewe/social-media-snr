"""Tujuh dimensi profil aktivitas akun (WP-2.3; FR-060..FR-065; PRD 11.3). Murni dan deterministik.

Unit = akun pada SATU platform; profil menggambarkan respons yang teramati pada target investigasi,
bukan seluruh riwayat akun dan bukan sifat orang. Setiap dimensi dihitung hanya bila datanya cukup;
bila tidak, nilainya `INSUFFICIENT_DATA` dengan alasan dan jumlah teramati, TIDAK PERNAH nol.
Tidak ada skor gabungan, peringkat, atau label.
"""

from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from intelligence.m2.rules import normalize
from intelligence.m2.taxonomy import Character, IssueStance

from .types import INSUFFICIENT, OK, ProfileParams, ResponseRecord


def _insufficient(reason: str, observed: int, minimum: int) -> dict[str, Any]:
    return {
        "status": INSUFFICIENT,
        "reason": reason,
        "observed": observed,
        "required_minimum": minimum,
    }


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def _share(count: int, total: int) -> float:
    return round(count / total, 4)


def _bucket_index(record: ResponseRecord, params: ProfileParams) -> int | None:
    if record.published_at is None:
        return None
    if not params.period_start <= record.published_at < params.period_end:
        return None
    return (record.published_at - params.period_start) // timedelta(hours=params.bucket_hours)


def _bucket_start(index: int, params: ProfileParams) -> str:
    return (params.period_start + timedelta(hours=params.bucket_hours * index)).isoformat()


def participation(records: Sequence[ResponseRecord]) -> dict[str, Any]:
    known = [r.published_at for r in records if r.published_at is not None]
    return {
        "status": OK,
        "unit": "satu Post = satu respons (observasi terbarunya dalam dataset)",
        "responses": len(records),
        "observations": sum(r.observation_count for r in records),
        "responses_with_changed_text": sum(1 for r in records if r.text_variants > 1),
        "distinct_parent_posts": len({r.parent_post_id for r in records if r.parent_post_id}),
        "distinct_targets": len({r.target_id for r in records}),
        "responses_without_known_time": len(records) - len(known),
        "first_published_at": _iso(min(known)) if known else None,
        "last_published_at": _iso(max(known)) if known else None,
    }


def stance_distribution(records: Sequence[ResponseRecord], params: ProfileParams) -> dict[str, Any]:
    n = len(records)
    if n < params.min_responses:
        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)
    counts = Counter(r.stance for r in records)
    return {
        "status": OK,
        "responses": n,
        "counts": {s.value: counts.get(s.value, 0) for s in IssueStance},
        "shares": {s.value: _share(counts.get(s.value, 0), n) for s in IssueStance},
    }


def response_character(records: Sequence[ResponseRecord], params: ProfileParams) -> dict[str, Any]:
    n = len(records)
    if n < params.min_responses:
        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)
    counts = Counter(c for r in records for c in r.characters)
    return {
        "status": OK,
        "responses": n,
        "counts": {c.value: counts.get(c.value, 0) for c in Character},
        "note": "multi-label: satu respons dapat dihitung pada lebih dari satu karakter",
    }


def temporal_activity(records: Sequence[ResponseRecord], params: ProfileParams) -> dict[str, Any]:
    placed = [(r, _bucket_index(r, params)) for r in records]
    indexed = [i for _, i in placed if i is not None]
    if len(indexed) < params.min_responses:
        return _insufficient(
            "respons dengan waktu publikasi dalam periode terlalu sedikit",
            len(indexed),
            params.min_responses,
        )
    counts = Counter(indexed)
    return {
        "status": OK,
        "responses_placed": len(indexed),
        "outside_period_or_unknown_time": len(records) - len(indexed),
        "bucket_hours": params.bucket_hours,
        "buckets": [
            {"start": _bucket_start(i, params), "responses": counts[i]} for i in sorted(counts)
        ],
    }


def target_concentration(
    records: Sequence[ResponseRecord], params: ProfileParams, *, targets_in_dataset: int
) -> dict[str, Any]:
    n = len(records)
    if targets_in_dataset < 2:
        return _insufficient("dataset hanya memuat satu target", targets_in_dataset, 2)
    if n < params.min_responses:
        return _insufficient("respons terlalu sedikit", n, params.min_responses)
    counts = Counter(r.target_id for r in records)
    top_target, top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {
        "status": OK,
        "responses": n,
        "targets_in_dataset": targets_in_dataset,
        "per_target": {str(t): c for t, c in sorted(counts.items())},
        "top_target": top_target,
        "top_target_share": _share(top, n),
    }


def narrative_consistency(
    records: Sequence[ResponseRecord], params: ProfileParams
) -> dict[str, Any]:
    """Repetisi teks yang TERSEDIA (setelah normalisasi). Bukan konsistensi pandangan atau niat."""
    texts = [normalize(r.text) for r in records if r.text is not None and normalize(r.text)]
    if len(texts) < params.narrative_min_texts:
        return _insufficient(
            "teks tersedia terlalu sedikit", len(texts), params.narrative_min_texts
        )
    counts = Counter(texts)
    repeated = sum(c for c in counts.values() if c > 1)
    return {
        "status": OK,
        "texts_considered": len(texts),
        "responses_without_text": len(records) - len(texts),
        "distinct_texts": len(counts),
        "texts_in_repeated_groups": repeated,
        "largest_repeated_group": max(counts.values()),
        "note": "hanya kesamaan teks tersedia; tidak menyimpulkan tujuan atau koordinasi",
    }


def activity_evolution(records: Sequence[ResponseRecord], params: ProfileParams) -> dict[str, Any]:
    per_bucket: dict[int, Counter] = {}
    for r in records:
        index = _bucket_index(r, params)
        if index is not None:
            per_bucket.setdefault(index, Counter())[r.stance] += 1
    if len(per_bucket) < params.min_active_buckets:
        return _insufficient(
            "periode aktif terlalu sedikit untuk melihat perubahan",
            len(per_bucket),
            params.min_active_buckets,
        )
    return {
        "status": OK,
        "bucket_hours": params.bucket_hours,
        "active_buckets": len(per_bucket),
        "buckets": [
            {
                "start": _bucket_start(i, params),
                "responses": sum(c.values()),
                "stance_counts": dict(sorted(c.items())),
            }
            for i, c in sorted(per_bucket.items())
        ],
        "note": "deskriptif per periode; bukan klaim tren atau perubahan sikap",
    }


def build_dimensions(
    records: Sequence[ResponseRecord], params: ProfileParams, *, targets_in_dataset: int
) -> dict[str, dict[str, Any]]:
    return {
        "participation": participation(records),
        "stance_distribution": stance_distribution(records, params),
        "response_character": response_character(records, params),
        "temporal_activity": temporal_activity(records, params),
        "target_concentration": target_concentration(
            records, params, targets_in_dataset=targets_in_dataset
        ),
        "narrative_consistency": narrative_consistency(records, params),
        "activity_evolution": activity_evolution(records, params),
    }
