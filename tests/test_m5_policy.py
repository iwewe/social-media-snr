"""WP-2.6: kebijakan confidence, saran bukti, larangan vonis, tingkat hasil (FR-077..FR-080). Murni."""

import ast
import inspect
import pathlib

import pytest
from intelligence import m5
from intelligence.m5 import (
    AXES,
    GENERAL_ALTERNATIVES,
    MODEL_TIERS,
    AlternativeOutcome,
    Confidence,
    QualityLevel,
    ResultTier,
    VerdictLanguage,
    alternatives_complete,
    check_no_verdict,
    confidence_allowed,
    confidence_ceiling,
    suggest_completeness,
    suggest_integrity,
    suggest_provenance,
    tier_of,
    validate_axes,
)

GOOD = {a: QualityLevel.GOOD for a in AXES}


def alts(outcome="RULED_OUT", **over):
    base = {k: {"outcome": outcome, "reasoning": f"alasan {k}"} for k in GENERAL_ALTERNATIVES}
    base.update(over)
    return base


# --- FR-079: larangan vonis --------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Ini jelas akun buzzer",
        "operasi berbayar",
        "Akun   bayaran",
        "dikendalikan satu pihak",
        "AKTOR PENGENDALI",
        "pasukan siber",
        "ada troll",
        "jaringan botnet",
        "mereka dibayar",
        "pengendali jaringan",
    ],
)
def test_verdict_vocabulary_is_rejected(text) -> None:
    with pytest.raises(VerdictLanguage, match="FR-079"):
        check_no_verdict("statement", text)


@pytest.mark.parametrize(
    "text",
    [
        "Dua akun menulis teks yang hampir sama dalam dua menit pada tiga target.",
        "",
        "robot vacuum",
        "botol air",
        "pengendalian mutu data",
        "merek Xbuzzer",
        "buzzerX produk",
        "kontrol kualitas data",
        "pembayaran tidak dibahas",
    ],
)
def test_neutral_descriptions_pass_and_words_match_whole_only(text) -> None:
    check_no_verdict("statement", text)


# --- hipotesis alternatif ---------------------------------------------------------------------


def test_all_four_general_alternatives_are_required_with_outcome_and_reasoning() -> None:
    assert len(GENERAL_ALTERNATIVES) == 4
    assert alternatives_complete(alts()) == []
    assert alternatives_complete({}) == list(GENERAL_ALTERNATIVES)
    partial = alts()
    del partial["external_event"]
    partial["sampling_bias"] = {"outcome": "RULED_OUT", "reasoning": "  "}
    partial["organic_mobilization"] = {"outcome": "MAYBE", "reasoning": "x"}
    assert alternatives_complete(partial) == [
        "organic_mobilization",
        "external_event",
        "sampling_bias",
    ]


# --- plafon confidence ---------------------------------------------------------------------------


def test_high_needs_good_evidence_all_alternatives_ruled_out_and_two_independent_groups() -> None:
    ceiling, reasons = confidence_ceiling(GOOD, alts(), 2)
    assert ceiling is Confidence.HIGH and reasons == []


@pytest.mark.parametrize("level", [QualityLevel.POOR, QualityLevel.NOT_ASSESSABLE])
@pytest.mark.parametrize("axis", AXES)
def test_a_poor_or_unassessable_evidence_axis_caps_confidence_at_low(axis, level) -> None:
    ceiling, reasons = confidence_ceiling({**GOOD, axis: level}, alts(), 3)
    assert ceiling is Confidence.LOW and any(axis in r for r in reasons)


def test_synthetic_data_caps_confidence_at_low_whatever_the_reviewer_rated() -> None:
    ceiling, reasons = confidence_ceiling(GOOD, alts(), 3, synthetic=True)
    assert ceiling is Confidence.LOW and any("sintetis" in r for r in reasons)
    assert confidence_allowed(Confidence.MODERATE, GOOD, alts(), 3, synthetic=True)[0] is False
    assert confidence_allowed(Confidence.LOW, GOOD, alts(), 3, synthetic=True)[0] is True
    assert confidence_allowed(Confidence.NOT_ASSESSABLE, GOOD, alts(), 3, synthetic=True)[0] is True


def test_acceptable_evidence_does_not_cap() -> None:
    assert (
        confidence_ceiling({a: QualityLevel.ACCEPTABLE for a in AXES}, alts(), 2)[0]
        is Confidence.HIGH
    )


def test_an_alternative_not_ruled_out_caps_at_moderate_and_unassessed_at_low() -> None:
    not_ruled = alts(
        external_event={"outcome": "NOT_RULED_OUT", "reasoning": "peristiwa besar hari itu"}
    )
    ceiling, reasons = confidence_ceiling(GOOD, not_ruled, 3)
    assert ceiling is Confidence.MODERATE and any("external_event" in r for r in reasons)
    cannot = alts(sampling_bias={"outcome": "CANNOT_ASSESS", "reasoning": "tidak ada data"})
    assert confidence_ceiling(GOOD, cannot, 3)[0] is Confidence.LOW
    assert (
        confidence_ceiling(GOOD, {}, 3)[0] is Confidence.LOW
    )  # belum ada pertimbangan sama sekali


@pytest.mark.parametrize("groups", [None, 0, 1])
def test_fewer_than_two_independent_evidence_groups_caps_at_moderate(groups) -> None:
    ceiling, reasons = confidence_ceiling(GOOD, alts(), groups)
    assert ceiling is Confidence.MODERATE and any("independen" in r for r in reasons)


def test_the_lowest_applicable_cap_wins() -> None:
    ceiling, _ = confidence_ceiling({**GOOD, "integrity": QualityLevel.POOR}, alts(), 1)
    assert ceiling is Confidence.LOW


def test_chosen_confidence_must_not_exceed_the_ceiling_but_unassessable_is_always_allowed() -> None:
    capped = {**GOOD, "completeness": QualityLevel.POOR}
    assert confidence_allowed(Confidence.LOW, capped, alts(), 3)[0] is True
    ok, ceiling, reasons = confidence_allowed(Confidence.MODERATE, capped, alts(), 3)
    assert ok is False and ceiling is Confidence.LOW and reasons
    assert confidence_allowed(Confidence.HIGH, GOOD, alts(), 1)[0] is False
    assert confidence_allowed(Confidence.HIGH, GOOD, alts(), 2)[0] is True
    assert confidence_allowed(Confidence.NOT_ASSESSABLE, capped, {}, None)[0] is True


# --- saran dari fakta sistem ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("facts", "level"),
    [
        (
            {"artifacts": 0, "verified_match": 0, "mismatch": 0, "missing": 0, "unreadable": 0},
            "NOT_ASSESSABLE",
        ),
        (
            {"artifacts": 4, "verified_match": 4, "mismatch": 0, "missing": 0, "unreadable": 0},
            "GOOD",
        ),
        (
            {"artifacts": 4, "verified_match": 2, "mismatch": 0, "missing": 0, "unreadable": 0},
            "ACCEPTABLE",
        ),
        (
            {"artifacts": 4, "verified_match": 0, "mismatch": 0, "missing": 0, "unreadable": 0},
            "NOT_ASSESSABLE",
        ),
        (
            {"artifacts": 4, "verified_match": 3, "mismatch": 1, "missing": 0, "unreadable": 0},
            "POOR",
        ),
        (
            {"artifacts": 4, "verified_match": 3, "mismatch": 0, "missing": 1, "unreadable": 0},
            "POOR",
        ),
        (
            {"artifacts": 4, "verified_match": 3, "mismatch": 0, "missing": 0, "unreadable": 1},
            "POOR",
        ),
    ],
)
def test_integrity_suggestion_follows_hash_verification_results(facts, level) -> None:
    got, reason = suggest_integrity(facts)
    assert got.value == level and reason
    if level == "GOOD":
        assert "bukan bukti keaslian" in reason


def run(outcome="COMPLETED", pagination=True, limitations=()):
    return {"outcome": outcome, "pagination_complete": pagination, "limitations": list(limitations)}


@pytest.mark.parametrize(
    ("runs", "level"),
    [
        ([], "NOT_ASSESSABLE"),
        ([run(), run()], "GOOD"),
        ([run(), run(limitations=[{"code": "X"}])], "ACCEPTABLE"),
        ([run(pagination=None)], "NOT_ASSESSABLE"),
        ([run(pagination=False)], "POOR"),
        ([run(), run(outcome="PARTIAL")], "POOR"),
        ([run(outcome="FAILED")], "POOR"),
        ([run(outcome="ACCESS_RESTRICTED")], "POOR"),
        ([run(outcome="UNSUPPORTED")], "POOR"),
    ],
)
def test_completeness_suggestion_follows_run_coverage_metadata(runs, level) -> None:
    assert suggest_completeness(runs)[0].value == level


@pytest.mark.parametrize(
    ("methods", "level"),
    [
        ([], "NOT_ASSESSABLE"),
        (["synthetic_fixture"], "NOT_ASSESSABLE"),
        (["synthetic_fixture", "imported_dataset"], "POOR"),
        (["imported_dataset"], "ACCEPTABLE"),
        (["browser_observation"], "GOOD"),
    ],
)
def test_provenance_suggestion_flags_synthetic_and_imported_sources(methods, level) -> None:
    assert suggest_provenance(methods)[0].value == level


# --- penilaian peninjau per sumbu ---------------------------------------------------------------


def ratings(level="GOOD", **over):
    base = {a: {"level": level, "reason": f"alasan {a}"} for a in AXES}
    base.update(over)
    return base


SUGGEST = {a: (QualityLevel.GOOD, "saran") for a in AXES}


def test_axis_ratings_must_cover_exactly_the_four_axes_with_reasons() -> None:
    assert validate_axes(ratings(), SUGGEST) == GOOD
    for bad in (
        {k: v for k, v in ratings().items() if k != "relevance"},
        {**ratings(), "extra": {"level": "GOOD", "reason": "x"}},
        ratings(integrity={"level": "GOOD", "reason": "  "}),
        ratings(integrity={"level": "GOOD"}),
        ratings(integrity={"level": "SUPER", "reason": "x"}),
        ratings(integrity={"reason": "x"}),
    ):
        with pytest.raises(ValueError):
            validate_axes(bad, SUGGEST)


def test_rating_better_than_the_system_suggestion_needs_an_override_reason() -> None:
    suggest = {**SUGGEST, "integrity": (QualityLevel.POOR, "hash tidak cocok")}
    with pytest.raises(ValueError, match="override_reason"):
        validate_axes(ratings(), suggest)
    ok = ratings(
        integrity={
            "level": "GOOD",
            "reason": "berkas dipulihkan",
            "override_reason": "diverifikasi manual",
        }
    )
    assert validate_axes(ok, suggest)["integrity"] is QualityLevel.GOOD
    lower = ratings(integrity={"level": "POOR", "reason": "setuju dengan sistem"})
    assert validate_axes(lower, suggest)["integrity"] is QualityLevel.POOR
    unknown = {**SUGGEST, "integrity": (QualityLevel.NOT_ASSESSABLE, "belum diverifikasi")}
    assert (
        validate_axes(ratings(), unknown)["integrity"] is QualityLevel.GOOD
    )  # saran tak pasti tidak mengikat


# --- empat tingkat hasil ------------------------------------------------------------------------------------


def test_result_tiers_are_ordered_and_only_findings_are_tier_four() -> None:
    assert [t.value for t in ResultTier] == [1, 2, 3, 4]
    assert tier_of("intelligence.Finding") is ResultTier.REVIEWED_ANALYTICAL_FINDING
    assert [m for m, t in MODEL_TIERS.items() if t is ResultTier.REVIEWED_ANALYTICAL_FINDING] == [
        "intelligence.Finding"
    ]
    assert tier_of("collection.PostObservation") is ResultTier.OBSERVED_EVIDENCE
    assert tier_of("intelligence.ResponseAssessment") is ResultTier.ANALYTICAL_CLASSIFICATION
    assert tier_of("intelligence.CoordinationEdge") is ResultTier.BEHAVIORAL_NETWORK_PATTERN
    assert tier_of("intelligence.AnalysisRun") is None
    with pytest.raises(KeyError):
        tier_of("intelligence.Unclassified")


def test_confidence_levels_are_exactly_the_four_defined_by_the_prd() -> None:
    assert {c.value for c in Confidence} == {"HIGH", "MODERATE", "LOW", "NOT_ASSESSABLE"}
    assert {o.value for o in AlternativeOutcome} == {"RULED_OUT", "NOT_RULED_OUT", "CANNOT_ASSESS"}


def test_no_verdict_or_score_vocabulary_in_names() -> None:
    root = pathlib.Path(inspect.getsourcefile(m5)).parent
    for path in root.glob("*.py"):
        if path.name == "policy.py":
            continue  # memuat daftar istilah terlarang sebagai data penjaga
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
        for word in ("buzzer", "score", "skor", "verdict", "vonis", "probability", "probabilitas"):
            assert not any(word in n.lower() for n in names), (path.name, word)
