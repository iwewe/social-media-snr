"""WP-2.2e: harness evaluasi M2 (PRD 16.3). Murni, tanpa basis data."""

import json

import pytest
from intelligence import evaluation as ev
from intelligence.evaluation import AnnotationError, Labels
from intelligence.m2 import (
    ClassifierInput,
    IssueStance,
    ParentTurn,
    PropositionRef,
    RulesClassifier,
)
from intelligence.m2.example_rules import example_parameters
from intelligence.m2.synthetic_eval import evaluate_synthetic, predictions_and_gold


def L(stance="PRO", alignment="SUPPORT", chars=("RC-01",)):
    return Labels(stance, alignment, tuple(sorted(chars)))


def raw(stance="PRO", alignment="SUPPORT", chars=("RC-01",)):
    return {
        "issue_stance": stance,
        "target_alignment": alignment,
        "response_character": list(chars),
    }


# --- kappa dan kesepakatan --------------------------------------------------------------------


def test_cohen_kappa_known_values() -> None:
    assert ev.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert ev.cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)
    assert ev.cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == pytest.approx(-1.0)
    assert (
        ev.cohen_kappa(["a"] * 4, ["a"] * 4) is None
    )  # kesepakatan kebetulan = 1: tak terdefinisi
    assert ev.cohen_kappa([], []) is None
    with pytest.raises(ValueError):
        ev.cohen_kappa([1], [1, 2])


def _two_annotator_items():
    entries = []
    pairs = [
        (raw("PRO"), raw("PRO")),
        (raw("PRO"), raw("CONTRA")),
        (raw("CONTRA"), raw("CONTRA")),
        (
            raw("UNDETERMINED", "UNCLEAR", ("RC-05",)),
            raw("UNDETERMINED", "UNCLEAR", ("RC-05", "RC-06")),
        ),
    ]
    for n, (a, b) in enumerate(pairs):
        entries.append({"id": f"i{n}", "tags": ["x"], "labels": {"A": a, "B": b}})
    return ev.load_annotations({"schema_version": 1, "items": entries})


def test_inter_annotator_agreement_reports_each_dimension_and_code() -> None:
    items = _two_annotator_items()
    out = ev.inter_annotator_agreement(items, "A", "B")
    assert out["items"] == 4
    assert out["issue_stance"]["observed_agreement"] == pytest.approx(0.75)
    assert out["issue_stance"]["kappa"] is not None
    assert out["response_character"]["exact_set_agreement"] == pytest.approx(0.75)
    assert "RC-06" in out["response_character"]["per_code"]


# --- evaluasi --------------------------------------------------------------------------------


def test_precision_recall_f1_and_confusion_are_computed_per_class() -> None:
    gold = {"1": L("PRO"), "2": L("PRO"), "3": L("CONTRA"), "4": L("CONTRA")}
    pred = {"1": L("PRO"), "2": L("CONTRA"), "3": L("CONTRA"), "4": L("CONTRA")}
    r = ev.evaluate(gold, pred).dimensions["issue_stance"]
    assert r["accuracy"] == pytest.approx(0.75)
    pro, contra = r["per_class"]["PRO"], r["per_class"]["CONTRA"]
    assert (pro["precision"], pro["recall"], pro["support"]) == (1.0, 0.5, 2)
    assert contra["precision"] == pytest.approx(2 / 3) and contra["recall"] == 1.0
    assert pro["f1"] == pytest.approx(2 / 3) and contra["f1"] == pytest.approx(0.8)
    assert r["macro_f1"] == pytest.approx((2 / 3 + 0.8) / 2)
    assert r["confusion"] == {"CONTRA": {"CONTRA": 2}, "PRO": {"CONTRA": 1, "PRO": 1}}


def test_character_is_scored_per_code_with_micro_and_exact_match() -> None:
    gold = {"1": L(chars=("RC-01", "RC-03")), "2": L(chars=("RC-05",))}
    pred = {"1": L(chars=("RC-01",)), "2": L(chars=("RC-05", "RC-06"))}
    c = ev.evaluate(gold, pred).response_character
    assert c["exact_set_match"] == 0.0
    assert c["per_code"]["RC-03"]["recall"] == 0.0 and c["per_code"]["RC-06"]["precision"] == 0.0
    assert c["micro"]["support"] == 3 and c["micro"]["predicted"] == 3
    assert c["micro"]["precision"] == pytest.approx(2 / 3) and c["micro"][
        "recall"
    ] == pytest.approx(2 / 3)


def test_missing_predictions_are_reported_not_counted_as_correct() -> None:
    gold = {"1": L(), "2": L()}
    report = ev.evaluate(gold, {"1": L()})
    assert report.missing_predictions == ["2"] and report.items == 1


def test_error_analysis_by_tag_and_error_list() -> None:
    gold = {"1": L("PRO"), "2": L("PRO"), "3": L("CONTRA")}
    pred = {"1": L("PRO"), "2": L("UNDETERMINED"), "3": L("CONTRA")}
    report = ev.evaluate(
        gold, pred, {"1": ["nested"], "2": ["sarcasm"], "3": ["sarcasm", "nested"]}
    )
    assert report.by_tag["sarcasm"]["issue_stance_accuracy"] == pytest.approx(0.5)
    assert report.by_tag["nested"]["issue_stance_accuracy"] == 1.0
    stance_errors = [e for e in report.errors if e["dimension"] == "issue_stance"]
    assert stance_errors == [
        {
            "id": "2",
            "dimension": "issue_stance",
            "gold": "PRO",
            "predicted": "UNDETERMINED",
            "tags": ["sarcasm"],
        }
    ]


def test_every_report_says_it_is_a_pilot_and_small_samples_are_warned() -> None:
    report = ev.evaluate({"1": L()}, {"1": L()})
    assert "PILOT" in report.notice and report.pilot_size_warning
    text = ev.format_report(report)
    assert text.startswith("PILOT") and "PERINGATAN" in text
    big = {str(n): L() for n in range(ev.MIN_PILOT_ITEMS)}
    assert ev.evaluate(big, big).pilot_size_warning is None
    assert "PILOT" in json.dumps(report.to_dict(), ensure_ascii=False)


# --- format anotasi ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"schema_version": 2, "items": []},
        {"schema_version": 1},
        {"schema_version": 1, "items": [{"labels": {"A": raw()}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": raw("BUZZER")}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": raw(alignment="MAYBE")}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": raw(chars=())}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": raw(chars=("RC-99",))}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": {"issue_stance": "PRO"}}}]},
        {"schema_version": 1, "items": [{"id": "a", "labels": {"A": raw()}, "tags": "x"}]},
        {
            "schema_version": 1,
            "items": [{"id": "a", "labels": {"A": raw()}}, {"id": "a", "labels": {"A": raw()}}],
        },
    ],
)
def test_annotation_files_are_validated_strictly(document) -> None:
    with pytest.raises(AnnotationError):
        ev.load_annotations(document)


def test_two_annotators_need_an_adjudicated_gold_label() -> None:
    items = _two_annotator_items()
    with pytest.raises(AnnotationError, match="adjudikasi"):
        ev.gold_labels(items)
    adjudicated = ev.load_annotations(
        {
            "schema_version": 1,
            "items": [
                {"id": "a", "labels": {"A": raw("PRO"), "B": raw("CONTRA")}, "gold": raw("PRO")}
            ],
        }
    )
    assert ev.gold_labels(adjudicated)["a"].issue_stance == "PRO"


def test_command_line_evaluates_files(tmp_path, capsys) -> None:
    gold = {
        "schema_version": 1,
        "items": [
            {"id": "a", "tags": ["t"], "labels": {"A": raw("PRO")}},
            {"id": "b", "tags": ["t"], "labels": {"A": raw("CONTRA", "OPPOSE", ("RC-03",))}},
        ],
    }
    pred = {"a": raw("PRO"), "b": raw("PRO")}
    (tmp_path / "g.json").write_text(json.dumps(gold))
    (tmp_path / "p.json").write_text(json.dumps(pred))
    assert (
        ev.main(["--gold", str(tmp_path / "g.json"), "--pred", str(tmp_path / "p.json"), "--json"])
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["dimensions"]["issue_stance"]["accuracy"] == 0.5 and out["by_tag"]["t"]["items"] == 2
    assert ev.main(["--gold", str(tmp_path / "g.json"), "--agreement", "A", "A"]) == 0


# --- data sintetis ---------------------------------------------------------------------------


def test_synthetic_evaluation_covers_every_response_and_tags_the_hard_cases() -> None:
    gold, predicted, tags = predictions_and_gold()
    assert 280 <= len(gold) == len(predicted) <= 310
    report = evaluate_synthetic()
    assert report.missing_predictions == [] and report.items == len(gold)
    for tag in ("sarcasm", "nested_parent", "media_dependent", "attacker", "coordinated-planted"):
        assert tag in report.by_tag and report.by_tag[tag]["items"] > 0
    assert any(t.startswith("case:A-R2") for t in report.by_tag)
    assert "PILOT" in report.notice


def test_synthetic_baseline_clears_a_sanity_floor_only() -> None:
    """Lantai kewarasan alur. BUKAN klaim kualitas: cue contoh ditulis dari templat sintetis yang sama."""
    report = evaluate_synthetic()
    assert report.dimensions["issue_stance"]["accuracy"] >= 0.9
    assert report.dimensions["target_alignment"]["accuracy"] >= 0.9
    assert report.response_character["exact_set_match"] >= 0.9


def test_harness_detects_a_degraded_classifier() -> None:
    """Harness harus bisa MERAH: classifier tanpa cue stance membuat akurasi stance jatuh nyata."""
    blind = example_parameters({1: ([], []), 2: ([], []), 3: ([], [])})
    clf = RulesClassifier(blind)
    gold, _, tags = predictions_and_gold()
    blind_pred = {i: Labels("UNDETERMINED", "UNCLEAR", ("RC-10",)) for i in gold}
    report = ev.evaluate(gold, blind_pred, tags)
    assert report.dimensions["issue_stance"]["accuracy"] < 0.5
    assert clf.classify(ClassifierInput("x", (), PropositionRef("P1", "x", 1))).issue_stance is (
        IssueStance.UNDETERMINED
    )


# --- batas yang diketahui (didokumentasikan; bila berubah, tes ini memberi tahu) ------------------


PARAMS = example_parameters({1: (["harus diaudit"], ["tidak perlu diaudit"])})
SEED = ParentTurn("Perusahaan tidak perlu diaudit.", IssueStance.CONTRA)


def _classify(text):
    return RulesClassifier(PARAMS).classify(
        ClassifierInput(text, (SEED,), PropositionRef("P1", "x", 1))
    )


def test_known_limitation_negation_of_a_cue_is_not_understood() -> None:
    # "Tidak benar bahwa perusahaan harus diaudit" bermakna KONTRA, tetapi aturan hanya melihat cue.
    assert _classify("Tidak benar bahwa perusahaan harus diaudit.").issue_stance is IssueStance.PRO


def test_known_limitation_uncued_sarcasm_is_not_detected() -> None:
    a = _classify("Ya ya, auditnya pasti bersih sekali ya.")
    assert a.issue_stance is IssueStance.UNDETERMINED and a.response_character[0].value == "RC-10"
