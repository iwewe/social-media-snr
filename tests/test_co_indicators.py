"""WP-2.5: indikator koordinasi CO-01..CO-06, baseline, korelasi (FR-072/075/076; AT-11, AT-12). Murni."""

import ast
import dataclasses
import inspect
import pathlib
import random
from datetime import UTC, datetime, timedelta

import pytest
from intelligence.m4 import baseline as baseline_mod
from intelligence.m4 import coordination as co
from intelligence.m4.baseline import exceedance, nearest_rank
from intelligence.m4.coordination import (
    CoordParams,
    Response,
    TooLarge,
    build_events,
    evidence_overlaps,
    extract_urls,
    independent_groups,
    indicator_values,
    normalize_url,
)
from intelligence.m4.indicators import ALTERNATIVE_HYPOTHESES, NOTICE, run_indicators

T0 = datetime(2026, 10, 1, tzinfo=UTC)


def P(**over):
    base = dict(
        sync_window_seconds=60,
        sync_min_events=1,
        co_response_min_shared=1,
        similarity_ngram=3,
        similarity_threshold=0.7,
        similarity_min_chars=5,
        similarity_min_pairs=1,
        similarity_max_responses=500,
        amplification_window_seconds=60,
        amplification_min_events=1,
        url_min_shared=1,
        phrase_words=4,
        phrase_min_shared=1,
        repeated_min_shared_targets=2,
        permutations=0,
        baseline_seed=5,
        evidence_limit=50,
        max_pair_events=100_000,
    )
    base.update(over)
    return CoordParams(**base)


class World:
    """Pembangun respons berindeks berurutan."""

    def __init__(self):
        self.items: list[Response] = []

    def add(
        self, actor, *, kind="reply", parent=100, target=1, t=0.0, text="halo dunia semua", amp=None
    ):
        i = len(self.items)
        time = None if t is None else T0 + timedelta(seconds=t)
        self.items.append(
            Response(
                i,
                1000 + i,
                5000 + i,
                actor,
                target,
                kind,
                parent if kind in ("reply", "comment") else None,
                amp,
                time,
                text,
            )
        )
        return self

    def values(self, params=None, labels=None, **kw):
        params = params or P()
        events = build_events(self.items, params)
        labels = labels or [r.actor_id for r in self.items]
        return indicator_values(
            self.items,
            labels,
            events,
            params,
            with_evidence=True,
            apply_min=kw.get("apply_min", True),
        )


# --- CO-01 -----------------------------------------------------------------------------------


def test_co01_jaccard_over_the_sets_of_parents_each_account_replied_to() -> None:
    w = World()
    for parent in (1, 2, 3):
        w.add(10, parent=parent).add(20, parent=parent)
    w.add(10, parent=4).add(20, parent=5)
    v = w.values()[("CO-01", "")][(10, 20)]
    assert v.support == 3 and v.value == pytest.approx(3 / 5)  # 3 / (4 + 4 - 3)
    assert v.detail["shared_parent_posts"] == [1, 2, 3] and len(v.observation_ids) == 6


def test_co01_ignores_same_account_disjoint_parents_and_respects_the_minimum() -> None:
    w = World().add(10, parent=1).add(10, parent=1).add(20, parent=2)
    assert w.values()[("CO-01", "")] == {}
    w2 = World().add(10, parent=1).add(20, parent=1)
    assert (10, 20) in w2.values(P(co_response_min_shared=1))[("CO-01", "")]
    assert w2.values(P(co_response_min_shared=2))[("CO-01", "")] == {}
    assert (10, 20) in w2.values(P(co_response_min_shared=2), apply_min=False)[("CO-01", "")]


# --- CO-02 -----------------------------------------------------------------------------------


def test_co02_counts_parents_where_two_accounts_replied_within_the_window() -> None:
    w = World().add(10, parent=1, t=0).add(20, parent=1, t=60)  # tepat pada batas: ikut
    w.add(10, parent=2, t=0).add(20, parent=2, t=61)  # di luar jendela
    w.add(10, parent=3, t=0).add(20, parent=3, t=10).add(
        20, parent=3, t=20
    )  # satu induk dihitung sekali
    v = w.values()[("CO-02", "")][(10, 20)]
    assert v.support == 2 and v.detail["synchronized_parent_posts"] == [1, 3]


def test_co02_excludes_unknown_times_and_never_pairs_an_account_with_itself() -> None:
    w = World().add(10, parent=1, t=0).add(20, parent=1, t=None).add(10, parent=1, t=5)
    events = build_events(w.items, P())
    assert events.exclusions["sync_unknown_time"] == 1
    assert w.values()[("CO-02", "")] == {}


def test_co02_window_and_minimum_are_parameters() -> None:
    w = World().add(10, parent=1, t=0).add(20, parent=1, t=300)
    assert w.values(P(sync_window_seconds=60))[("CO-02", "")] == {}
    assert w.values(P(sync_window_seconds=300))[("CO-02", "")][(10, 20)].support == 1
    assert w.values(P(sync_window_seconds=300, sync_min_events=2))[("CO-02", "")] == {}


# --- CO-03 -----------------------------------------------------------------------------------


def test_co03_similarity_is_on_normalized_text_with_a_threshold_and_min_length() -> None:
    w = World().add(10, text="Baca klarifikasi resminya dulu sebelum berkomentar!")
    w.add(20, text="baca  KLARIFIKASI resminya dulu, sebelum berkomentar")
    w.add(30, text="Resep nasi goreng enak sekali")
    w.add(40, text="ok")  # terlalu pendek
    w.add(50, text="ok")
    v = w.values()[("CO-03", "")]
    assert set(v) == {(10, 20)} and v[(10, 20)].value == 1.0 and v[(10, 20)].support == 1
    assert w.values(P(similarity_threshold=1.01))[("CO-03", "")] == {}
    assert (40, 50) in w.values(P(similarity_min_chars=2))[("CO-03", "")]


def test_co03_threshold_is_inclusive_so_identical_texts_pass_a_threshold_of_one() -> None:
    w = (
        World()
        .add(10, text="teks yang sama persis dan cukup panjang")
        .add(20, text="teks yang sama persis dan cukup panjang")
    )
    assert (10, 20) in w.values(P(similarity_threshold=1.0))[("CO-03", "")]
    w2 = (
        World()
        .add(10, text="teks yang hampir sama persis dan cukup panjang")
        .add(20, text="teks yang hampir sama persis dan cukup panjang sekali")
    )
    assert w2.values(P(similarity_threshold=1.0))[("CO-03", "")] == {}


def test_co03_counts_pairs_and_reports_the_highest_similarity() -> None:
    w = World()
    for actor in (10, 20):
        w.add(actor, text="Sudah dijelaskan lengkap di sini, silakan baca dulu")
        w.add(actor, text="Sudah dijelaskan lengkap di sini silakan dibaca dulu")
    v = w.values()[("CO-03", "")][(10, 20)]
    assert v.support >= 2 and 0.7 <= v.value <= 1.0


def test_co03_is_skipped_visibly_when_there_are_too_many_responses() -> None:
    w = World()
    for n in range(6):
        w.add(10 + n, text=f"teks yang cukup panjang nomor {n}")
    events = build_events(w.items, P(similarity_max_responses=5))
    assert events.similar == [] and events.exclusions["similarity_skipped_too_large"] == 6


# --- CO-04 -----------------------------------------------------------------------------------


def test_co04_counts_originals_amplified_by_both_accounts_within_the_window() -> None:
    w = World().add(10, kind="repost", amp=7, t=0).add(20, kind="quote", amp=7, t=30)
    w.add(10, kind="repost", amp=8, t=0).add(20, kind="repost", amp=9, t=0)  # objek berbeda
    w.add(10, kind="repost", amp=11, t=0).add(20, kind="repost", amp=11, t=500)  # di luar jendela
    v = w.values()[("CO-04", "")][(10, 20)]
    assert v.support == 1 and v.detail["co_amplified_posts"] == [7]


def test_co04_unknown_time_is_excluded_and_counted() -> None:
    w = World().add(10, kind="repost", amp=7, t=None).add(20, kind="repost", amp=7, t=0)
    assert build_events(w.items, P()).exclusions["amplification_unknown_time"] == 1


# --- CO-05 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.Contoh.example/Berita/1?utm=x#bagian", "contoh.example/berita/1"),
        ("http://contoh.example/berita/1/", "contoh.example/berita/1"),
        ("https://contoh.example/a.", "contoh.example/a"),
    ],
)
def test_url_normalization_is_domain_plus_path(raw, expected) -> None:
    assert normalize_url(raw) == expected


def test_extract_urls_finds_all_and_ignores_text_without_links() -> None:
    assert extract_urls("lihat https://a.example/x dan http://b.example/y?z=1, ok") == {
        "a.example/x",
        "b.example/y",
    }
    assert extract_urls(None) == set() and extract_urls("tanpa tautan") == set()


def test_co05_shared_urls_across_accounts_and_distinct_count() -> None:
    w = World().add(10, text="baca https://www.contoh.example/laporan?x=1 sekarang")
    w.add(20, text="Ini dia HTTPS://contoh.example/laporan/ lengkap")
    w.add(10, text="juga https://contoh.example/lain").add(
        20, text="dan https://contoh.example/lain!"
    )
    v = w.values(P(phrase_words=0))[("CO-05", "url")][(10, 20)]
    assert v.support == 2 and v.detail["shared_urls"] == [
        "contoh.example/lain",
        "contoh.example/laporan",
    ]
    assert v.detail["distinct_tokens"] == 2 and v.detail["response_pairs"] == 2
    assert ("CO-05", "phrase") not in {k for k, p in w.values(P(phrase_words=0)).items() if p}


def test_co05_counts_repeated_sharing_of_the_same_link_not_just_distinct_links() -> None:
    w = World()
    for n in range(3):
        w.add(10, parent=n, text="baca https://contoh.example/sama dulu")
        w.add(20, parent=n, text="lihat https://contoh.example/sama ya")
    v = w.values(P(phrase_words=0))[("CO-05", "url")][(10, 20)]
    assert v.detail["distinct_tokens"] == 1 and v.support == 9 and v.detail["response_pairs"] == 9


def test_co05_phrases_are_word_shingles_and_exclude_urls() -> None:
    w = World().add(10, text="menurut saya sebaiknya baca klarifikasi resminya https://c.example/a")
    w.add(20, text="Sebaiknya BACA klarifikasi resminya dulu https://c.example/b")
    v = w.values(P(phrase_words=3))[("CO-05", "phrase")][(10, 20)]
    assert "sebaiknya baca klarifikasi" in v.detail["shared_phrases"]
    assert not any("example" in p or "https" in p for p in v.detail["shared_phrases"])
    assert w.values(P(phrase_words=0))[("CO-05", "phrase")] == {}


# --- CO-06 -----------------------------------------------------------------------------------


def test_co06_counts_distinct_targets_both_accounts_took_part_in() -> None:
    w = World()
    for target in (1, 2, 3):
        w.add(10, target=target, parent=target).add(20, target=target, kind="repost", amp=target)
    w.add(10, target=4, parent=4)
    v = w.values()[("CO-06", "")][(10, 20)]
    assert v.support == 3 and v.detail["shared_targets"] == [1, 2, 3]
    one = World().add(10, target=1).add(20, target=1)
    assert one.values()[("CO-06", "")] == {}  # minimum 2 target


# --- FR-075 / AT-11: stance dan intensitas tidak membentuk indikator -------------------------------


def test_AT11_nothing_in_the_model_uses_stance_and_many_independent_accounts_form_no_edges() -> (
    None
):
    assert not any("stance" in f.name for f in dataclasses.fields(Response))
    w = World()
    words = [
        "audit",
        "perusahaan",
        "kebakaran",
        "hutan",
        "data",
        "sumber",
        "publik",
        "kajian",
        "izin",
        "lahan",
        "warga",
        "kebijakan",
        "laporan",
        "bukti",
        "dana",
        "desa",
    ]
    for n in range(12):  # pandangan sama, tetapi induk, waktu, dan teks berbeda
        text = " ".join(random.Random(n).sample(words, 7))
        w.add(100 + n, parent=n, target=1, t=n * 4000, text=text)
    result = run_indicators(w.items, P())
    assert result.edges == []


# --- baseline --------------------------------------------------------------------------------------


def test_nearest_rank_and_exceedance_are_computed_as_documented() -> None:
    assert nearest_rank([1, 2, 3, 4], 0.95) == 4 and nearest_rank([1, 2, 3, 4], 0.5) == 2
    assert nearest_rank([], 0.95) == 0.0
    assert exceedance(3, [1, 2, 3, 4]) == pytest.approx((1 + 2) / 5)
    assert exceedance(5, [1, 2, 3, 4]) == pytest.approx(1 / 5)
    assert exceedance(1, []) is None


def planted_world(seed=3):
    """20 akun: A dan B bertindak bersama (induk sama, waktu sama, teks dan tautan sama); sisanya acak."""
    rng = random.Random(seed)
    w = World()
    for parent in range(1, 5):
        base_t = parent * 10_000
        for actor in (1, 2):
            w.add(
                actor,
                parent=parent,
                target=parent % 2 + 1,
                t=base_t + rng.randint(0, 20),
                text="Baca klarifikasi resminya dulu di https://c.example/klarifikasi sebelum menghakimi",
            )
    for actor in range(3, 21):
        for _ in range(4):
            parent = rng.randint(1, 30)
            w.add(
                actor,
                parent=parent,
                target=rng.randint(1, 2),
                t=rng.randint(0, 400_000),
                text=f"komentar acak {rng.random():.6f} dari akun {actor} tentang isu {rng.randint(0, 999)}",
            )
    return w


def test_a_planted_pair_exceeds_the_baseline_while_random_pairs_do_not() -> None:
    w = planted_world()
    result = run_indicators(w.items, P(permutations=200))
    flagged = {(e.actor_a, e.actor_b) for e in result.edges if e.baseline["exceeds_baseline_p95"]}
    assert (1, 2) in flagged
    assert flagged == {(1, 2)}  # tidak ada pasangan acak yang melampaui baseline
    labels = {
        e.label
        for e in result.edges
        if (e.actor_a, e.actor_b) == (1, 2) and e.baseline["exceeds_baseline_p95"]
    }
    assert {"CO-01", "CO-02", "CO-03", "CO-05:url"} <= labels


def test_baseline_is_reproducible_and_seed_dependent() -> None:
    w = planted_world()
    a = run_indicators(w.items, P(permutations=50, baseline_seed=1))
    b = run_indicators(w.items, P(permutations=50, baseline_seed=1))
    c = run_indicators(w.items, P(permutations=50, baseline_seed=2))
    assert a.baseline == b.baseline
    assert [e.baseline for e in a.edges] == [e.baseline for e in b.edges]
    assert a.baseline != c.baseline


def test_edges_declare_that_the_baseline_compares_support_counts() -> None:
    result = run_indicators(planted_world().items, P(permutations=20))
    assert result.edges and all(e.baseline["statistic"] == "support" for e in result.edges)


def test_baseline_summary_records_permutations_and_observed_maxima() -> None:
    result = run_indicators(planted_world().items, P(permutations=40))
    summary = result.baseline["CO-01"]
    assert summary["permutations"] == 40 and summary["observed_max"] >= summary["p95_of_max"]
    assert summary["mean_of_max"] <= summary["p95_of_max"] <= summary["max_of_max"]
    assert set(result.baseline) == {
        "CO-01",
        "CO-02",
        "CO-03",
        "CO-04",
        "CO-05:url",
        "CO-05:phrase",
        "CO-06",
    }


def test_without_permutations_the_baseline_is_explicitly_not_computed() -> None:
    result = run_indicators(planted_world().items, P(permutations=0))
    assert result.baseline["status"] == "NOT_COMPUTED"
    assert all(e.baseline == {"status": "NOT_COMPUTED"} for e in result.edges)


def test_permutation_keeps_each_accounts_number_of_responses(monkeypatch) -> None:
    seen = []

    def spy(responses, labels, events, params, **kw):
        seen.append(sorted(labels))
        return {k: {} for k in co.KEYS}

    monkeypatch.setattr(baseline_mod, "indicator_values", spy)
    w = planted_world()
    labels = [r.actor_id for r in w.items]
    baseline_mod.permutation_maxima(w.items, labels, build_events(w.items, P()), P(permutations=5))
    assert len(seen) == 5 and all(s == sorted(labels) for s in seen)


# --- korelasi antar-indikator ----------------------------------------------------------------------


def test_indicators_sharing_evidence_are_marked_dependent_and_grouped() -> None:
    per = {
        ("CO-01", ""): {1, 2, 3},
        ("CO-02", ""): {2, 3},
        ("CO-03", ""): {9},
        ("CO-05", "url"): {9, 10},
    }
    overlaps = evidence_overlaps(per)
    assert overlaps[("CO-01", "")] == ["CO-02"] and overlaps[("CO-03", "")] == ["CO-05:url"]
    assert independent_groups(per) == [["CO-01", "CO-02"], ["CO-03", "CO-05:url"]]
    assert independent_groups({("CO-01", ""): {1}, ("CO-06", ""): {2}}) == [["CO-01"], ["CO-06"]]


def test_edges_report_overlap_and_pairs_summarize_independent_evidence_groups() -> None:
    result = run_indicators(planted_world().items, P())
    summary = result.pair_summary["1-2"]
    assert "CO-01" in summary["indicators"]
    assert any(len(group) >= 2 for group in summary["independent_evidence_groups"])
    edge = next(e for e in result.edges if (e.actor_a, e.actor_b, e.label) == (1, 2, "CO-01"))
    assert "CO-02" in edge.overlaps_with


# --- bentuk hasil ----------------------------------------------------------------------------------------


def test_every_edge_carries_evidence_explanation_and_alternative_hypotheses() -> None:
    result = run_indicators(planted_world().items, P())
    assert result.notice == NOTICE and "bukan temuan" in NOTICE.lower()
    for e in result.edges:
        assert e.observation_ids and e.explanation and e.actor_a < e.actor_b
        assert (
            list(ALTERNATIVE_HYPOTHESES) == e.alternative_hypotheses[:4]
            and len(e.alternative_hypotheses) == 5
        )


def test_evidence_is_truncated_visibly_at_the_limit() -> None:
    result = run_indicators(planted_world().items, P(evidence_limit=2))
    edge = next(e for e in result.edges if e.label == "CO-01" and (e.actor_a, e.actor_b) == (1, 2))
    assert len(edge.observation_ids) == 2 and edge.truncated is True


def test_results_are_deterministic_and_sorted() -> None:
    a = run_indicators(planted_world().items, P(permutations=20))
    b = run_indicators(planted_world().items, P(permutations=20))
    assert a.edges == b.edges
    keys = [(e.actor_a, e.actor_b, e.indicator, e.variant) for e in a.edges]
    assert keys == sorted(keys)


def test_oversized_inputs_fail_loudly_instead_of_truncating() -> None:
    w = World()
    for n in range(30):
        w.add(10 + n, parent=1, t=n)
    with pytest.raises(TooLarge):
        build_events(w.items, P(max_pair_events=10))


def test_repeated_observations_of_the_same_post_do_not_double_count() -> None:
    """Satu Post = satu respons (pemanggil menyatukan observasi); dua respons berbeda tetap dua."""
    w = World().add(10, parent=1, t=0).add(20, parent=1, t=1)
    assert w.values()[("CO-02", "")][(10, 20)].support == 1


def test_no_verdict_or_control_vocabulary_in_names() -> None:
    root = pathlib.Path(inspect.getsourcefile(co)).parent
    for name in ("coordination.py", "baseline.py", "indicators.py"):
        names = set()
        for node in ast.walk(ast.parse((root / name).read_text())):
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
            "leader",
            "verdict",
            "vonis",
            "botnet",
            "troll",
        ):
            assert not any(word in n.lower() for n in names), (name, word)
