"""Indikator koordinasi CO-01..CO-06 (WP-2.5; ADR 0024, 0029; FR-072, FR-075, FR-076). Murni.

Unit: pasangan akun pada SATU platform. Setiap indikator menghasilkan nilai terhitung beserta
bukti (ID observasi), BUKAN skor akun dan BUKAN temuan. Stance tidak dipakai sama sekali
(FR-075). Seluruh ambang adalah parameter eksplisit; tidak ada nilai bawaan yang dianggap
"ambang koordinasi".

Respons = satu Post (diwakili observasi terbarunya pada dataset), agar pemeriksaan berulang atas
objek yang sama tidak menggandakan hitungan.

Peristiwa (pasangan respons yang memenuhi kriteria) bersifat bebas-label-akun, dihitung sekali;
nilai per pasangan akun dihitung dari peristiwa itu menurut label akun. Itu memungkinkan
baseline permutasi label akun (ADR 0029) memakai peristiwa yang sama.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from typing import Any

from intelligence.m2.rules import normalize

CODES = ("CO-01", "CO-02", "CO-03", "CO-04", "CO-05", "CO-06")
KEYS = (
    ("CO-01", ""),
    ("CO-02", ""),
    ("CO-03", ""),
    ("CO-04", ""),
    ("CO-05", "url"),
    ("CO-05", "phrase"),
    ("CO-06", ""),
)
REPLY_KINDS = ("reply", "comment")
AMPLIFY_KINDS = ("repost", "quote")
TEXT_KINDS = ("reply", "comment", "quote")
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

Pair = tuple[int, int]


class TooLarge(ValueError):
    """Jumlah peristiwa pasangan melebihi batas eksplisit; hasil tidak dihitung diam-diam."""


@dataclass(frozen=True)
class Response:
    index: int
    observation_id: int
    post_id: int
    actor_id: int
    target_id: int
    kind: str
    parent_post_id: int | None
    amplified_post_id: int | None
    published_at: datetime | None
    text: str | None


@dataclass(frozen=True)
class CoordParams:
    sync_window_seconds: int
    sync_min_events: int
    co_response_min_shared: int
    similarity_ngram: int
    similarity_threshold: float
    similarity_min_chars: int
    similarity_min_pairs: int
    similarity_max_responses: int
    amplification_window_seconds: int
    amplification_min_events: int
    url_min_shared: int
    phrase_words: int  # 0 = tidak dipakai
    phrase_min_shared: int
    repeated_min_shared_targets: int
    permutations: int  # 0 = baseline tidak dihitung
    baseline_seed: int
    evidence_limit: int
    max_pair_events: int


@dataclass
class Events:
    sync: list[tuple[int, int, int]] = field(default_factory=list)  # (i, j, induk)
    similar: list[tuple[int, int, float]] = field(default_factory=list)
    co_amp: list[tuple[int, int, int]] = field(default_factory=list)  # (i, j, objek asli)
    urls: list[tuple[int, int, str]] = field(default_factory=list)
    phrases: list[tuple[int, int, str]] = field(default_factory=list)
    exclusions: Counter = field(default_factory=Counter)

    def size(self) -> int:
        return (
            len(self.sync)
            + len(self.similar)
            + len(self.co_amp)
            + len(self.urls)
            + len(self.phrases)
        )


@dataclass
class PairValue:
    value: float
    support: int
    observation_ids: set[int] = field(default_factory=set)
    detail: dict[str, Any] = field(default_factory=dict)


def normalize_url(raw: str) -> str:
    """domain + path (tanpa skema, www, query, fragmen, garis miring akhir), huruf kecil."""
    cleaned = raw.rstrip(".,;:!?")
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.split(r"[?#]", cleaned, maxsplit=1)[0].rstrip("/").lower()
    return re.sub(r"^www\.", "", cleaned)


def extract_urls(text: str | None) -> set[str]:
    return {u for u in (normalize_url(m) for m in _URL.findall(text or "")) if u}


def _guard(count: int, params: CoordParams) -> None:
    if count > params.max_pair_events:
        raise TooLarge(
            f"jumlah peristiwa pasangan ({count}) melebihi max_pair_events={params.max_pair_events}"
        )


def _windowed_pairs(members: list[Response], seconds: int) -> list[tuple[int, int]]:
    """Pasangan respons dengan selisih waktu <= seconds (dua penunjuk pada urutan waktu)."""
    timed = sorted(
        (r for r in members if r.published_at is not None), key=lambda r: (r.published_at, r.index)
    )
    out = []
    for a, first in enumerate(timed):
        for second in timed[a + 1 :]:
            if (second.published_at - first.published_at).total_seconds() > seconds:  # type: ignore[operator]
                break
            out.append((first.index, second.index))
    return out


def _shingles(text: str, n: int) -> set[str]:
    return {text[i : i + n] for i in range(max(len(text) - n + 1, 1))}


def build_events(responses: Sequence[Response], params: CoordParams) -> Events:
    events = Events()
    # CO-02: balasan pada induk yang sama dalam jendela waktu
    by_parent: dict[int, list[Response]] = defaultdict(list)
    for r in responses:
        if r.kind in REPLY_KINDS and r.parent_post_id is not None:
            if r.published_at is None:
                events.exclusions["sync_unknown_time"] += 1
            else:
                by_parent[r.parent_post_id].append(r)
    for parent, members in sorted(by_parent.items()):
        for i, j in _windowed_pairs(members, params.sync_window_seconds):
            events.sync.append((i, j, parent))
        _guard(events.size(), params)
    # CO-04: amplifikasi objek yang sama dalam jendela waktu
    by_original: dict[int, list[Response]] = defaultdict(list)
    for r in responses:
        if r.kind in AMPLIFY_KINDS and r.amplified_post_id is not None:
            if r.published_at is None:
                events.exclusions["amplification_unknown_time"] += 1
            else:
                by_original[r.amplified_post_id].append(r)
    for original, members in sorted(by_original.items()):
        for i, j in _windowed_pairs(members, params.amplification_window_seconds):
            events.co_amp.append((i, j, original))
        _guard(events.size(), params)
    # CO-03: kemiripan teks (n-gram karakter, Jaccard)
    texts = [
        (r.index, normalize(r.text))
        for r in responses
        if r.kind in TEXT_KINDS and r.text is not None
    ]
    texts = [(i, t) for i, t in texts if len(t) >= params.similarity_min_chars]
    if len(texts) > params.similarity_max_responses:
        events.exclusions["similarity_skipped_too_large"] = len(texts)
    else:
        sets = {i: _shingles(t, params.similarity_ngram) for i, t in texts}
        _guard(events.size() + len(texts) * (len(texts) - 1) // 2, params)
        for (i, _), (j, _) in combinations(texts, 2):
            union = len(sets[i] | sets[j])
            similarity = len(sets[i] & sets[j]) / union if union else 0.0
            if similarity >= params.similarity_threshold:
                events.similar.append((i, j, round(similarity, 6)))
    # CO-05: tautan yang sama (domain+path) dan frasa kata yang sama
    by_url: dict[str, list[int]] = defaultdict(list)
    by_phrase: dict[str, list[int]] = defaultdict(list)
    for r in responses:
        if r.kind not in TEXT_KINDS or r.text is None:
            continue
        for url in sorted(extract_urls(r.text)):
            by_url[url].append(r.index)
        if params.phrase_words:
            tokens = normalize(_URL.sub(" ", r.text)).split()
            for start in range(len(tokens) - params.phrase_words + 1):
                phrase = " ".join(tokens[start : start + params.phrase_words])
                if r.index not in by_phrase[phrase]:
                    by_phrase[phrase].append(r.index)
    for url, holders in sorted(by_url.items()):
        _guard(events.size() + len(holders) * (len(holders) - 1) // 2, params)
        events.urls.extend((i, j, url) for i, j in combinations(sorted(holders), 2))
    for phrase, holders in sorted(by_phrase.items()):
        if len(holders) > 1:
            _guard(events.size() + len(holders) * (len(holders) - 1) // 2, params)
            events.phrases.extend((i, j, phrase) for i, j in combinations(sorted(holders), 2))
    return events


def statistic(key: tuple[str, str], pv: PairValue) -> float:
    """Besaran yang dibandingkan dengan baseline: DUKUNGAN (jumlah kejadian) untuk semua indikator.

    Nilai deskriptif tidak dipakai karena jenuh: Jaccard CO-01 bernilai 1,0 untuk setiap dua akun
    yang masing-masing hanya membalas satu posting yang sama, dan kemiripan tertinggi CO-03 jenuh
    di 1,0.
    """
    return float(pv.support)


def _pair(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


def indicator_values(
    responses: Sequence[Response],
    labels: Sequence[int],
    events: Events,
    params: CoordParams,
    *,
    with_evidence: bool,
    apply_min: bool,
) -> dict[tuple[str, str], dict[Pair, PairValue]]:
    """Nilai per pasangan akun tiap indikator, menurut `labels` (akun pengganti tiap respons)."""
    result: dict[tuple[str, str], dict[Pair, PairValue]] = {k: {} for k in KEYS}
    obs = [r.observation_id for r in responses]

    def keep(support: int, minimum: int) -> bool:
        return support >= minimum or not apply_min

    def add_obs(pv: PairValue, *indices: int) -> None:
        if with_evidence:
            pv.observation_ids.update(obs[i] for i in indices)

    # CO-01 Co-Response: Jaccard atas himpunan induk yang dibalas
    parents_by_actor: dict[int, set[int]] = defaultdict(set)
    actors_by_parent: dict[int, set[int]] = defaultdict(set)
    replies: dict[tuple[int, int], list[int]] = defaultdict(list)
    for r in responses:
        if r.kind in REPLY_KINDS and r.parent_post_id is not None:
            actor = labels[r.index]
            parents_by_actor[actor].add(r.parent_post_id)
            actors_by_parent[r.parent_post_id].add(actor)
            replies[(actor, r.parent_post_id)].append(r.index)
    shared: dict[Pair, set[int]] = defaultdict(set)
    for parent, actors in actors_by_parent.items():
        for a, b in combinations(sorted(actors), 2):
            shared[(a, b)].add(parent)
    for (a, b), parents in shared.items():
        support = len(parents)
        if keep(support, params.co_response_min_shared):
            union = len(parents_by_actor[a]) + len(parents_by_actor[b]) - support
            pv = PairValue(
                round(support / union, 6), support, detail={"shared_parent_posts": sorted(parents)}
            )
            for parent in parents:
                add_obs(pv, *replies[(a, parent)], *replies[(b, parent)])
            result[("CO-01", "")][(a, b)] = pv

    def collect(
        events_list: list[tuple[int, int, Any]],
        key: tuple[str, str],
        minimum: int,
        label: str,
        *,
        by_response_pairs: bool = False,
    ) -> None:
        """Dukungan = token berbeda (mis. induk), atau jumlah pasangan respons bila diminta."""
        per_pair: dict[Pair, dict[Any, set[int]]] = defaultdict(lambda: defaultdict(set))
        pairs_seen: dict[Pair, set[tuple[int, int]]] = defaultdict(set)
        for i, j, token in events_list:
            a, b = labels[i], labels[j]
            if a != b:
                per_pair[_pair(a, b)][token].update((i, j))
                pairs_seen[_pair(a, b)].add((i, j))
        for pair, tokens in per_pair.items():
            support = len(pairs_seen[pair]) if by_response_pairs else len(tokens)
            if keep(support, minimum):
                detail: dict[str, Any] = {label: sorted(tokens, key=str)}
                if by_response_pairs:
                    detail["distinct_tokens"] = len(tokens)
                    detail["response_pairs"] = support
                pv = PairValue(float(support), support, detail=detail)
                for indices in tokens.values():
                    add_obs(pv, *indices)
                result[key][pair] = pv

    collect(events.sync, ("CO-02", ""), params.sync_min_events, "synchronized_parent_posts")
    collect(events.co_amp, ("CO-04", ""), params.amplification_min_events, "co_amplified_posts")
    collect(
        events.urls, ("CO-05", "url"), params.url_min_shared, "shared_urls", by_response_pairs=True
    )
    collect(
        events.phrases,
        ("CO-05", "phrase"),
        params.phrase_min_shared,
        "shared_phrases",
        by_response_pairs=True,
    )

    # CO-03 Content Similarity: nilai = kemiripan tertinggi; dukungan = jumlah pasangan mirip
    similar: dict[Pair, list[tuple[int, int, float]]] = defaultdict(list)
    for i, j, sim in events.similar:
        a, b = labels[i], labels[j]
        if a != b:
            similar[_pair(a, b)].append((i, j, sim))
    for pair, items in similar.items():
        if keep(len(items), params.similarity_min_pairs):
            pv = PairValue(
                max(s for _, _, s in items),
                len(items),
                detail={"similar_response_pairs": len(items)},
            )
            for i, j, _ in items:
                add_obs(pv, i, j)
            result[("CO-03", "")][pair] = pv

    # CO-06 Repeated Participation: target berbeda tempat kedua akun sama-sama merespons
    targets_by_actor: dict[int, set[int]] = defaultdict(set)
    responses_by: dict[tuple[int, int], list[int]] = defaultdict(list)
    for r in responses:
        actor = labels[r.index]
        targets_by_actor[actor].add(r.target_id)
        responses_by[(actor, r.target_id)].append(r.index)
    actors_by_target: dict[int, set[int]] = defaultdict(set)
    for actor, targets in targets_by_actor.items():
        for target in targets:
            actors_by_target[target].add(actor)
    common: dict[Pair, set[int]] = defaultdict(set)
    for target, actors in actors_by_target.items():
        for a, b in combinations(sorted(actors), 2):
            common[(a, b)].add(target)
    for (a, b), targets in common.items():
        if keep(len(targets), params.repeated_min_shared_targets):
            pv = PairValue(
                float(len(targets)), len(targets), detail={"shared_targets": sorted(targets)}
            )
            for target in targets:
                add_obs(pv, *responses_by[(a, target)][:1], *responses_by[(b, target)][:1])
            result[("CO-06", "")][(a, b)] = pv
    return result


def evidence_overlaps(
    per_indicator: Mapping[tuple[str, str], set[int]],
) -> dict[tuple[str, str], list[str]]:
    """Satu pasangan akun: indikator yang bukti (ID observasi)-nya bersinggungan -> dependen."""
    keys = sorted(per_indicator)
    out: dict[tuple[str, str], list[str]] = {k: [] for k in keys}
    for a, b in combinations(keys, 2):
        if per_indicator[a] & per_indicator[b]:
            out[a].append(_label(b))
            out[b].append(_label(a))
    return out


def independent_groups(per_indicator: Mapping[tuple[str, str], set[int]]) -> list[list[str]]:
    """Kelompok indikator yang buktinya bersinggungan (satu kelompok = satu bukti, bukan banyak)."""
    keys = sorted(per_indicator)
    parent = {k: k for k in keys}

    def find(k: tuple[str, str]) -> tuple[str, str]:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a, b in combinations(keys, 2):
        if per_indicator[a] & per_indicator[b]:
            parent[find(a)] = find(b)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for k in keys:
        groups[find(k)].append(_label(k))
    return sorted(sorted(g) for g in groups.values())


def _label(key: tuple[str, str]) -> str:
    return key[0] if not key[1] else f"{key[0]}:{key[1]}"
