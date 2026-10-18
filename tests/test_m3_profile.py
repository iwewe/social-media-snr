"""WP-2.3: dimensi profil aktor M3 dan perbandingan (FR-060..FR-065; PRD 11.3). Murni, tanpa basis data."""

import copy
import inspect
import json
from datetime import UTC, datetime, timedelta

import pytest
from intelligence import m3
from intelligence.m3 import (
    DIMENSIONS,
    INSUFFICIENT,
    OK,
    PlatformMismatch,
    ProfileParams,
    ResponseRecord,
    build_dimensions,
    compare_profiles,
)

START = datetime(2026, 10, 1, tzinfo=UTC)
PARAMS = ProfileParams(
    period_start=START,
    period_end=START + timedelta(days=10),
    min_responses=3,
    bucket_hours=24,
    min_active_buckets=2,
    narrative_min_texts=2,
)


def rec(n, *, target=1, parent=100, day=1.0, text="isi", stance="PRO", chars=("RC-01",), actor=7):
    published = None if day is None else START + timedelta(days=day)
    return ResponseRecord(n, actor, target, parent, published, text, stance, tuple(chars))


def dims(records, params=PARAMS, targets=2):
    return build_dimensions(records, params, targets_in_dataset=targets)


def test_all_seven_dimensions_are_always_present() -> None:
    assert tuple(dims([rec(1)])) == DIMENSIONS and len(DIMENSIONS) == 7


# --- participation -------------------------------------------------------------------------------


def test_participation_counts_unique_facts_and_unknown_times() -> None:
    d = dims([rec(1, parent=1), rec(2, parent=1), rec(3, parent=2, target=2, day=None)])
    p = d["participation"]
    assert p["status"] == OK and p["responses"] == 3 and p["distinct_parent_posts"] == 2
    assert p["distinct_targets"] == 2 and p["responses_without_known_time"] == 1
    assert (
        p["first_published_at"] == p["last_published_at"] == (START + timedelta(days=1)).isoformat()
    )


# --- data tidak cukup bukan nol -----------------------------------------------------------------


@pytest.mark.parametrize(
    "dimension",
    [
        "stance_distribution",
        "response_character",
        "temporal_activity",
        "narrative_consistency",
        "activity_evolution",
    ],
)
def test_insufficient_data_is_stated_never_reported_as_zero(dimension) -> None:
    d = dims([rec(1)])[dimension]
    assert d["status"] == INSUFFICIENT and d["reason"] and d["required_minimum"] >= 1
    assert d["observed"] < d["required_minimum"]
    assert not {"counts", "shares", "buckets", "per_target", "distinct_texts"} & set(d)


def test_stance_distribution_counts_all_classes_with_shares() -> None:
    d = dims([rec(1), rec(2), rec(3, stance="UNDETERMINED"), rec(4, stance="CONTRA")])[
        "stance_distribution"
    ]
    assert d["status"] == OK and d["responses"] == 4
    assert d["counts"] == {
        "PRO": 2,
        "CONTRA": 1,
        "MIXED": 0,
        "NEUTRAL": 0,
        "UNDETERMINED": 1,
        "NOT_RELEVANT": 0,
    }
    assert d["shares"]["PRO"] == 0.5 and d["shares"]["CONTRA"] == 0.25
    assert sum(d["shares"].values()) == pytest.approx(1.0)


def test_response_character_is_multi_label() -> None:
    d = dims([rec(1, chars=("RC-01", "RC-04")), rec(2, chars=("RC-01",)), rec(3, chars=("RC-10",))])
    c = d["response_character"]
    assert c["counts"]["RC-01"] == 2 and c["counts"]["RC-04"] == 1 and c["counts"]["RC-10"] == 1
    assert sum(c["counts"].values()) > c["responses"]  # satu respons dapat dihitung ganda
    assert "multi-label" in c["note"]


# --- temporal dan evolusi ----------------------------------------------------------------------


def test_temporal_activity_buckets_only_known_times_inside_the_period() -> None:
    records = [rec(1, day=0.5), rec(2, day=0.9), rec(3, day=2.5), rec(4, day=None), rec(5, day=30)]
    t = dims(records)["temporal_activity"]
    assert (
        t["status"] == OK
        and t["responses_placed"] == 3
        and t["outside_period_or_unknown_time"] == 2
    )
    assert [b["responses"] for b in t["buckets"]] == [2, 1]
    assert t["buckets"][0]["start"] == START.isoformat()
    assert t["buckets"][1]["start"] == (START + timedelta(days=2)).isoformat()


def test_period_end_is_exclusive_and_start_inclusive() -> None:
    edge = [rec(1, day=0), rec(2, day=0.1), rec(3, day=10)]  # hari ke-10 = period_end -> di luar
    assert (
        dims(edge, ProfileParams(START, START + timedelta(days=10), 2, 24, 2, 2))[
            "temporal_activity"
        ]["responses_placed"]
        == 2
    )


def test_activity_evolution_needs_enough_active_buckets_and_makes_no_trend_claim() -> None:
    one_bucket = dims([rec(1, day=0.1), rec(2, day=0.2), rec(3, day=0.3)])["activity_evolution"]
    assert one_bucket["status"] == INSUFFICIENT and one_bucket["observed"] == 1
    d = dims([rec(1, day=0.1), rec(2, day=1.2, stance="CONTRA"), rec(3, day=1.4, stance="CONTRA")])
    e = d["activity_evolution"]
    assert e["status"] == OK and e["active_buckets"] == 2
    assert e["buckets"][1]["stance_counts"] == {"CONTRA": 2} and e["buckets"][0]["responses"] == 1
    assert "bukan klaim tren" in e["note"]
    assert not {"trend", "slope", "change", "shift"} & set(e)


# --- konsentrasi target dan narasi -------------------------------------------------------------


def test_target_concentration_needs_more_than_one_target_in_the_dataset() -> None:
    d = dims([rec(1), rec(2), rec(3)], targets=1)["target_concentration"]
    assert d["status"] == INSUFFICIENT and "satu target" in d["reason"]


def test_target_concentration_also_needs_enough_responses() -> None:
    d = dims([rec(1, target=1), rec(2, target=2)], targets=2)["target_concentration"]
    assert d["status"] == INSUFFICIENT and d["observed"] == 2 and d["required_minimum"] == 3
    assert "per_target" not in d


def test_target_concentration_reports_distribution_and_breaks_ties_by_id() -> None:
    records = [rec(1, target=5), rec(2, target=5), rec(3, target=3), rec(4, target=3)]
    d = dims(records)["target_concentration"]
    assert d["status"] == OK and d["per_target"] == {"3": 2, "5": 2}
    assert d["top_target"] == 3 and d["top_target_share"] == 0.5


def test_narrative_consistency_counts_repeated_available_texts_only() -> None:
    records = [
        rec(1, text="Baca Klarifikasinya!"),
        rec(2, text="baca klarifikasinya"),
        rec(3, text="Berbeda sama sekali"),
        rec(4, text=None),
        rec(5, text="  !!! "),
    ]
    n = dims(records)["narrative_consistency"]
    assert n["status"] == OK and n["texts_considered"] == 3 and n["responses_without_text"] == 2
    assert n["distinct_texts"] == 2 and n["texts_in_repeated_groups"] == 2
    assert n["largest_repeated_group"] == 2
    assert "tidak menyimpulkan" in n["note"]
    assert not any(
        "baca klarifikasinya" in json.dumps(v).lower() for v in n.values()
    )  # isi tidak disalin


def test_profile_is_deterministic_and_independent_of_record_order() -> None:
    records = [rec(i, day=i % 5, stance="PRO" if i % 2 else "CONTRA") for i in range(1, 12)]
    assert dims(records) == dims(list(reversed(records)))


# --- FR-065: tidak ada vonis, skor, atau label kepribadian --------------------------------------

FORBIDDEN = (
    "buzzer",
    "score",
    "skor",
    "rating",
    "rank",
    "peringkat",
    "personality",
    "kepribadian",
    "verdict",
    "vonis",
    "bot",
    "troll",
    "paid",
)


def _words(obj, found=None):
    found = found if found is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k).lower())
            _words(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _words(v, found)
    return found


def test_FR065_no_key_in_a_profile_names_a_verdict_score_or_personality() -> None:
    d = dims([rec(i, day=i * 0.7) for i in range(1, 9)])
    keys = _words(d)
    for word in FORBIDDEN:
        assert not any(word in k for k in keys), (word, sorted(keys))


def _names_in(path) -> set[str]:
    """Identifier dan kunci kamus dari AST; docstring/komentar sengaja tidak ikut (boleh menolak istilah)."""
    import ast

    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Dict):
            names.update(
                k.value
                for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
    return {n.lower() for n in names}


def test_FR065_package_source_never_uses_verdict_vocabulary_as_names() -> None:
    import pathlib

    root = pathlib.Path(inspect.getsourcefile(m3)).parent
    files = list(root.glob("*.py"))
    assert len(files) >= 4
    for path in files:
        names = _names_in(path)
        for word in ("buzzer", "score", "skor", "personality", "kepribadian", "verdict", "vonis"):
            assert not any(word in name for name in names), (path.name, word)


# --- perbandingan (FR-064) ---------------------------------------------------------------------


def _profile(
    records,
    *,
    targets=(1, 2),
    all_targets=(1, 2),
    platform="x",
    period=("a", "b"),
    dataset=1,
    proposition=1,
    incomplete=(),
    unknown_time=0,
):
    return {
        "coverage": {
            "platform": platform,
            "targets_covered": list(targets),
            "targets_in_investigation": list(all_targets),
            "period": {"start": period[0], "end": period[1]},
            "dataset_version": dataset,
            "proposition_id": proposition,
            "partial_coverage": sorted(targets) != sorted(all_targets),
            "incomplete_runs": list(incomplete),
            "responses_without_known_time": unknown_time,
        },
        "dimensions": dims(records),
    }


ENOUGH = [rec(i, day=i * 0.6, target=1 + i % 2) for i in range(1, 9)]


def test_comparable_profiles_have_no_warnings_and_no_score() -> None:
    out = compare_profiles(_profile(ENOUGH), _profile(ENOUGH))
    assert out["comparable"] is True and out["warnings"] == []
    assert set(out) == {"comparable", "warnings", "dimensions"}
    assert all(set(v) == {"a", "b", "comparable"} for v in out["dimensions"].values())


def test_unequal_coverage_produces_warnings() -> None:
    a = _profile(ENOUGH, targets=(1,), all_targets=(1, 2))
    b = _profile(ENOUGH)
    out = compare_profiles(a, b)
    assert out["comparable"] is False
    text = " | ".join(out["warnings"])
    assert "A: hanya 1 dari 2 target" in text and "cakupan target berbeda" in text


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"period": ("a", "c")}, "periode berbeda"),
        ({"dataset": 2}, "versi dataset berbeda"),
        ({"proposition": 2}, "proposition berbeda"),
        ({"incomplete": [{"run": 1, "status": "PARTIAL"}]}, "tidak lengkap"),
        ({"unknown_time": 2}, "tanpa waktu publikasi"),
    ],
)
def test_each_coverage_difference_is_called_out(override, fragment) -> None:
    out = compare_profiles(_profile(ENOUGH), _profile(ENOUGH, **override))
    assert out["comparable"] is False and any(fragment in w for w in out["warnings"])


def test_dimensions_with_insufficient_data_are_not_compared() -> None:
    out = compare_profiles(_profile(ENOUGH), _profile([rec(1)]))
    assert out["dimensions"]["participation"]["comparable"] is True
    assert out["dimensions"]["stance_distribution"]["comparable"] is False
    assert any("stance_distribution: data tidak cukup" in w for w in out["warnings"])


def test_profiles_from_different_platforms_are_never_compared() -> None:
    with pytest.raises(PlatformMismatch):
        compare_profiles(_profile(ENOUGH), _profile(ENOUGH, platform="tiktok"))


def test_comparison_does_not_mutate_its_inputs() -> None:
    a, b = _profile(ENOUGH), _profile(ENOUGH)
    snapshot = copy.deepcopy((a, b))
    compare_profiles(a, b)
    assert (a, b) == snapshot
