"""Evaluasi baseline aturan M2 atas dataset sintetis + kunci jawaban (WP-2.0/2.2e).

Cue contoh ditulis dengan melihat templat sintetis, jadi angka yang keluar adalah UJI KEWARASAN
alur dan harness, bukan kualitas pada data nyata (lihat `example_rules`).
"""

from typing import Any

from intelligence.evaluation import Labels, Report, evaluate
from intelligence.synthetic import DEFAULT_SEED, generate

from .example_rules import SYNTHETIC_PROPOSITION_CUES, example_parameters
from .rules import RulesClassifier
from .taxonomy import IssueStance
from .types import ClassifierInput, ParentTurn, PropositionRef


def _depth(observations: dict[str, Any], cache: dict[str, int], oid: str) -> int:
    if oid not in cache:
        parent = observations[oid]["parent"]
        cache[oid] = 0 if parent is None else 1 + _depth(observations, cache, parent)
    return cache[oid]


def _texts(bundle: Any, target: int) -> dict[str, str | None]:
    latest: dict[str, str | None] = {}
    dataset = bundle.datasets[f"x-target-{target}.json"]
    for snapshot in dataset["snapshots"]:  # putaran terakhir yang memuat objek itu
        for o in snapshot["observations"]:
            latest[o["id"]] = o["text"]
    return latest


def predictions_and_gold(
    seed: int | None = None,
) -> tuple[dict[str, Labels], dict[str, Labels], dict[str, list[str]]]:
    bundle = generate(DEFAULT_SEED if seed is None else seed)
    params = example_parameters(SYNTHETIC_PROPOSITION_CUES)
    classifier = RulesClassifier(params)
    gold: dict[str, Labels] = {}
    predicted: dict[str, Labels] = {}
    tags: dict[str, list[str]] = {}
    for key, target in bundle.ground_truth["targets"].items():
        n = int(key)
        observations = target["observations"]
        texts = _texts(bundle, n)
        proposition = PropositionRef(f"P{n}", f"proposisi sintetis {n}", n)
        seed_stance = IssueStance(target["seed_stance"])
        depths: dict[str, int] = {}

        computed: dict[str, IssueStance] = {}
        responses = [o for o, v in observations.items() if v["kind"] == "reply"]
        for oid in sorted(responses, key=lambda o: (_depth(observations, depths, o), o)):
            chain, cursor = [], observations[oid]["parent"]
            while cursor is not None:
                stance = computed.get(cursor)
                if stance is None and observations[cursor]["kind"] == "post":
                    stance = seed_stance
                chain.append(ParentTurn(texts.get(cursor), stance))
                cursor = observations[cursor]["parent"]
            result = classifier.classify(ClassifierInput(texts.get(oid), tuple(chain), proposition))
            computed[oid] = result.issue_stance
            truth = observations[oid]
            label_id = f"{n}:{oid}"
            gold[label_id] = Labels(
                truth["issue_stance"],
                truth["target_alignment"],
                tuple(sorted(truth["response_character"])),
            )
            predicted[label_id] = Labels(
                result.issue_stance.value,
                result.target_alignment.value,
                tuple(sorted(c.value for c in result.response_character)),
            )
            item_tags = [truth["group"]]
            if truth["sarcastic"]:
                item_tags.append("sarcasm")
            if truth["media_dependent"]:
                item_tags.append("media_dependent")
            parent = observations[oid]["parent"]
            if parent is not None and observations[parent]["kind"] == "reply":
                item_tags.append("nested_parent")
            if truth["case"]:
                item_tags.append("case:" + str(truth["case"]))
            tags[label_id] = item_tags
    return gold, predicted, tags


def evaluate_synthetic(seed: int | None = None) -> Report:
    gold, predicted, tags = predictions_and_gold(seed)
    return evaluate(gold, predicted, tags)
