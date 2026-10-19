"""WP-2.2: klasifier aturan M2 (FR-050..FR-057; AT-08, AT-09, AT-10). Murni, tanpa basis data."""

import copy

import pytest
from intelligence.m2 import (
    Character,
    ClassifierInput,
    IssueStance,
    ParentTurn,
    PropositionRef,
    RulesClassifier,
    RulesParameterError,
    TargetAlignment,
    normalize,
    validate_parameters,
)
from intelligence.m2.example_rules import example_parameters

P1 = PropositionRef("P1", "Perusahaan perlu diaudit.", id=1)
PARAMS = example_parameters(
    {1: (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit", "diaudit"])}
)
SEED = ParentTurn("Perusahaan tidak perlu diaudit.", IssueStance.CONTRA)


def classify(text, chain=(SEED,), *, parent_unknown=False, params=PARAMS):
    return RulesClassifier(params).classify(
        ClassifierInput(text, tuple(chain), P1, parent_unknown=parent_unknown)
    )


def test_normalize_is_casefolded_flat_and_keeps_question_marks() -> None:
    assert normalize("  Apa   BUKTINYA?!  ") == "apa buktinya?"
    assert normalize("tidak_perlu, diaudit.") == "tidak perlu diaudit"


def test_appendix_a_reply1_is_pro_and_opposes_the_target() -> None:
    a = classify("Justru audit harus dilakukan.")
    assert a.issue_stance is IssueStance.PRO and a.target_alignment is TargetAlignment.OPPOSE
    assert Character.COUNTERARGUMENT in a.response_character
    assert a.basis["matched"]["pro"] == ["audit harus dilakukan"]


def test_AT08_agreement_with_a_second_level_reply_follows_that_parent_not_the_seed() -> None:
    reply1 = ParentTurn("Justru audit harus dilakukan.", IssueStance.PRO)
    a = classify("Setuju sekali!", (reply1, SEED))
    assert a.issue_stance is IssueStance.PRO and a.target_alignment is TargetAlignment.SUPPORT
    assert a.response_character == (Character.SUPPORT,)
    assert a.basis["propagated_from"] == "direct_parent"
    # tanpa pengetahuan stance induk, "setuju" TIDAK boleh menebak
    unknown = classify("Setuju sekali!", (ParentTurn("?", None), SEED))
    assert unknown.issue_stance is IssueStance.UNDETERMINED
    assert unknown.target_alignment is TargetAlignment.SUPPORT  # tetap mendukung induk langsung
    assert "agreement_without_known_parent_stance" in unknown.basis["rules"]
    flagged = classify("Setuju sekali!", (reply1, SEED), parent_unknown=True)
    assert flagged.issue_stance is IssueStance.UNDETERMINED


def test_disagreement_flips_the_parent_stance_and_beats_an_embedded_agree_cue() -> None:
    reply = ParentTurn("x", IssueStance.PRO)
    a = classify("Saya tidak sependapat, itu keliru.", (reply, SEED))
    assert a.issue_stance is IssueStance.CONTRA and a.target_alignment is TargetAlignment.OPPOSE
    assert a.basis["matched"]["agree"] == [] and a.basis["matched"]["disagree"]


def test_longest_match_wins_inside_stance_cues() -> None:
    a = classify(
        "Perusahaan itu tidak perlu diaudit."
    )  # "diaudit" kontra tertelan oleh frasa lebih panjang
    assert a.issue_stance is IssueStance.CONTRA
    assert a.basis["matched"]["pro"] == [] and a.basis["matched"]["contra"] == [
        "tidak perlu diaudit"
    ]


def test_pro_and_contra_cues_together_give_mixed() -> None:
    assert (
        classify("Harus diaudit, tapi ada yang bilang tidak perlu diaudit.").issue_stance
        is IssueStance.MIXED
    )


def test_AT10_personal_attack_has_character_but_no_stance() -> None:
    a = classify("Penulis ini bodoh.")
    assert (
        a.issue_stance is IssueStance.UNDETERMINED and a.target_alignment is TargetAlignment.UNCLEAR
    )
    assert a.response_character == (Character.PERSONAL_ATTACK,)
    c = classify("Argumen ini lemah karena tidak ada sumbernya.")
    assert c.issue_stance is IssueStance.UNDETERMINED
    assert c.response_character == (Character.SUBSTANTIVE_CRITICISM,)
    assert (
        c.target_alignment is TargetAlignment.OPPOSE
    )  # mengkritik argumen induk, bukan stance isu


def test_information_request_and_emotion_do_not_decide_stance() -> None:
    q = classify("Apa buktinya keterlibatannya?")
    assert q.issue_stance is IssueStance.UNDETERMINED and q.response_character == (
        Character.INFORMATION_REQUEST,
    )
    e = classify("Saya marah melihat kebakaran ini.")
    assert e.issue_stance is IssueStance.UNDETERMINED
    assert e.expression_sentiment is not None and e.expression_sentiment.value == "NEGATIVE"
    assert e.response_character == (Character.OTHER,)


def test_AT09_media_dependent_comment_is_undetermined_not_guessed() -> None:
    a = classify("Lihat videonya, jelas banget itu.")
    assert a.issue_stance is IssueStance.UNDETERMINED and a.response_character == (Character.OTHER,)
    assert a.basis["rules"] == ["stance:no_decisive_cue"]


def test_diversion_and_promotion_are_not_relevant() -> None:
    assert (
        classify("Ada yang tahu resep nasi goreng enak?").issue_stance is IssueStance.NOT_RELEVANT
    )
    spam = classify("Jual follower murah, cek bio ya.")
    assert spam.issue_stance is IssueStance.NOT_RELEVANT and spam.response_character == (
        Character.PROMOTIONAL,
    )


def test_intimidation_always_requires_human_review() -> None:
    a = classify("Awas ya, urusannya bisa panjang kalau kamu terus begini.")
    assert Character.INTIMIDATION in a.response_character and a.needs_human_review is True
    assert classify("Penulis ini bodoh.").needs_human_review is False


def test_unavailable_text_is_undetermined_and_says_so() -> None:
    for text in (None, "   !!! "):
        a = classify(text)
        assert a.issue_stance is IssueStance.UNDETERMINED and a.basis["rules"] == [
            "text_unavailable"
        ]


def test_no_claim_about_truth_of_the_claim_or_buzzer_exists_in_output() -> None:
    a = classify("Justru audit harus dilakukan.")
    blob = repr(a).lower()
    assert "buzzer" not in blob and "score" not in blob and "skor" not in blob


def test_classification_is_deterministic() -> None:
    assert classify("Justru audit harus dilakukan.") == classify("Justru audit harus dilakukan.")


def test_unknown_proposition_is_an_error_not_a_silent_default() -> None:
    clf = RulesClassifier(PARAMS)
    with pytest.raises(RulesParameterError, match="proposition 9"):
        clf.classify(ClassifierInput("x", (), PropositionRef("P9", "x", id=9)))
    with pytest.raises(RulesParameterError):
        clf.classify(ClassifierInput("x", (), PropositionRef("P?", "x", id=None)))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("min_matches"),
        lambda p: p.update(extra=1),
        lambda p: p.update(min_matches=0),
        lambda p: p.update(min_matches=True),
        lambda p: p.update(propositions={}),
        lambda p: p["propositions"].update({"x": {"pro_cues": [], "contra_cues": []}}),
        lambda p: p["propositions"]["1"].pop("contra_cues"),
        lambda p: p.update(agree_cues="setuju"),
        lambda p: p.update(agree_cues=[""]),
        lambda p: p.update(agree_cues=["!!!"]),
        lambda p: p["character_cues"].pop("RC-05"),
        lambda p: p["character_cues"].update({"RC-01": []}),
        lambda p: p["sentiment_cues"].pop("NEGATIVE"),
    ],
)
def test_parameters_are_complete_and_strict(mutate) -> None:
    params = copy.deepcopy(PARAMS)
    mutate(params)
    with pytest.raises(RulesParameterError):
        validate_parameters(params)


def test_min_matches_raises_the_bar_for_stance() -> None:
    strict = copy.deepcopy(PARAMS)
    strict["min_matches"] = 2
    assert (
        classify("Justru audit harus dilakukan.", params=strict).issue_stance
        is IssueStance.UNDETERMINED
    )
    twice = classify("Audit harus dilakukan, ya harus diaudit.", params=strict)
    assert twice.issue_stance is IssueStance.PRO


# --- kasus tepi yang diburu mutasi ------------------------------------------------------------


def test_agree_and_disagree_together_never_propagate_a_stance() -> None:
    parent = ParentTurn("x", IssueStance.PRO)
    a = classify("Setuju sekali, tapi itu keliru.", (parent, SEED))
    assert a.issue_stance is IssueStance.UNDETERMINED and "propagated_from" not in a.basis


@pytest.mark.parametrize("stance", [None, IssueStance.MIXED, IssueStance.UNDETERMINED])
def test_only_a_decided_parent_stance_propagates(stance) -> None:
    parent = ParentTurn("x", stance)
    for text in ("Setuju sekali!", "Saya tidak sependapat."):
        assert classify(text, (parent, SEED)).issue_stance is IssueStance.UNDETERMINED


def test_identical_spans_from_both_sides_both_survive_pruning() -> None:
    params = example_parameters({1: (["sama persis"], ["sama persis"])})
    assert classify("Ini sama persis.", params=params).issue_stance is IssueStance.MIXED


def test_symbol_cue_matches_anywhere_but_word_cues_need_whole_words() -> None:
    params = copy.deepcopy(PARAMS)
    params["character_cues"]["RC-04"] = ["?"]
    assert classify("Benarkah begitu?", params=params).response_character == (
        Character.INFORMATION_REQUEST,
    )
    params["character_cues"]["RC-04"] = ["bukti"]
    assert classify("Mana bukti", params=params).response_character == (
        Character.INFORMATION_REQUEST,
    )
    assert classify("Apa buktinya", params=params).response_character == (Character.OTHER,)


def test_sentiment_follows_the_cues_and_conflict_is_unrated() -> None:
    params = copy.deepcopy(PARAMS)
    params["sentiment_cues"] = {"POSITIVE": ["senang"], "NEGATIVE": ["marah"]}
    assert classify("Saya senang.", params=params).expression_sentiment.value == "POSITIVE"
    assert classify("Saya marah.", params=params).expression_sentiment.value == "NEGATIVE"
    assert classify("Senang tapi marah.", params=params).expression_sentiment is None
    assert classify("Biasa saja.", params=params).expression_sentiment is None


def test_min_matches_applies_to_contra_cues_too() -> None:
    strict = copy.deepcopy(PARAMS)
    strict["min_matches"] = 2
    assert classify("Perusahaan itu tidak perlu diaudit.", params=strict).issue_stance is (
        IssueStance.UNDETERMINED
    )
    twice = classify("Tidak perlu diaudit, sungguh tidak perlu diaudit.", params=strict)
    assert twice.issue_stance is IssueStance.CONTRA


def test_not_relevant_only_when_the_response_is_purely_diversion_or_promotion() -> None:
    mixed = classify("Ada yang tahu resep nasi goreng? Apa buktinya?")
    assert mixed.issue_stance is IssueStance.UNDETERMINED
    assert set(mixed.response_character) == {
        Character.TOPIC_DIVERSION,
        Character.INFORMATION_REQUEST,
    }


def _no_negation(params):
    params = copy.deepcopy(params)
    del params["negation_cues"], params["negation_window"]
    return params


def test_negation_before_a_stance_cue_flags_review_but_keeps_the_stance() -> None:
    text = "Tidak benar bahwa perusahaan harus diaudit"
    a = classify(text, ())
    assert a.issue_stance is IssueStance.PRO
    assert a.needs_human_review is True
    assert "review:negation_near_stance_cue" in a.basis["rules"]
    assert a.basis["matched"]["negation"] == [
        {"cue": "harus diaudit", "class": "pro", "negation": ["tidak"]}
    ]


def test_without_negation_parameters_behaviour_is_unchanged() -> None:
    a = classify("Tidak benar bahwa perusahaan harus diaudit", (), params=_no_negation(PARAMS))
    assert a.issue_stance is IssueStance.PRO
    assert a.needs_human_review is False
    assert "negation" not in a.basis["matched"]
    validate_parameters(_no_negation(PARAMS))


def test_negation_inside_the_cue_itself_is_not_flagged() -> None:
    a = classify("Perusahaan tidak perlu diaudit", ())
    assert a.issue_stance is IssueStance.CONTRA
    assert a.needs_human_review is False


def test_negation_window_boundary_is_exact() -> None:
    params = copy.deepcopy(PARAMS)
    params["negation_window"] = 2
    inside = classify("tidak benar harus diaudit", (), params=params)
    outside = classify("tidak sangat benar harus diaudit", (), params=params)
    assert inside.needs_human_review is True
    assert outside.needs_human_review is False


def test_negation_must_be_a_whole_word() -> None:
    assert classify("katanya ketidaktahuan harus diaudit", ()).needs_human_review is False


def test_negation_also_flags_agreement_cues() -> None:
    params = copy.deepcopy(PARAMS)
    params["agree_cues"] = ["setuju"]
    a = classify("saya tidak setuju", (SEED,), params=params)
    assert a.needs_human_review is True


def test_negation_in_a_sentence_before_still_counts_only_inside_the_window() -> None:
    a = classify("Bukan masalah. Kami semua dan banyak lainnya bilang harus diaudit", ())
    assert a.needs_human_review is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("negation_window"),
        lambda p: p.pop("negation_cues"),
        lambda p: p.update(negation_window=0),
        lambda p: p.update(negation_window=11),
        lambda p: p.update(negation_window=True),
        lambda p: p.update(negation_window="5"),
        lambda p: p.update(negation_cues="tidak"),
        lambda p: p.update(negation_cues=[""]),
    ],
)
def test_negation_parameters_are_validated(mutate) -> None:
    params = copy.deepcopy(PARAMS)
    mutate(params)
    with pytest.raises(RulesParameterError):
        validate_parameters(params)


def test_negation_window_upper_bound_is_accepted() -> None:
    params = copy.deepcopy(PARAMS)
    params["negation_window"] = 10
    validate_parameters(params)
    params["negation_window"] = 1
    validate_parameters(params)


def test_negation_flags_contra_cues() -> None:
    params = copy.deepcopy(PARAMS)
    params["negation_window"] = 10
    b = classify("jangan bilang perusahaan tidak perlu diaudit", (), params=params)
    assert b.issue_stance is IssueStance.CONTRA
    assert b.needs_human_review is True
    assert b.basis["matched"]["negation"][0]["class"] == "contra"


def test_negation_flags_disagreement_cues() -> None:
    params = copy.deepcopy(PARAMS)
    params["disagree_cues"] = ["salah besar"]
    params["agree_cues"] = ["setuju"]
    a = classify("bukan salah besar", (SEED,), params=params)
    assert a.needs_human_review is True
    assert a.basis["matched"]["negation"][0]["class"] == "disagree"
