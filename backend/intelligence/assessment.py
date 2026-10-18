"""Penilaian respons M2 sebagai metode AnalysisRun, dan tinjauan manusia (WP-2.2).

Metode `m2-rules` v1 menilai setiap respons (reply/comment/quote) pada dataset beku terhadap tiap
proposition yang disebut parameter, memakai rantai induk nyata. Baris ditulis dalam transaksi yang
sama dengan eksekusi run: bila metode gagal, tidak ada baris yang tertinggal. Tinjauan manusia
membuat baris baru yang menggantikan, tidak menimpa (FR-055, AT-16).
"""

from collections import Counter
from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from audit import services as audit
from audit.models import AuditAction, SubjectType
from investigations.models import Proposition, TargetPropositionStance

from .conversation import Chain, ConversationIndex
from .digest import digest_json
from .errors import AnalysisError, InvalidParameters
from .m2 import (
    Character,
    ClassifierInput,
    IssueStance,
    NarrativeFunction,
    ParentTurn,
    PropositionRef,
    RulesClassifier,
    RulesParameterError,
    Sentiment,
    TargetAlignment,
    validate_parameters,
)
from .models import (
    AnalysisRun,
    AnalysisStatus,
    AssessmentSource,
    ResponseAssessment,
)

RESPONSE_TYPES = ("reply", "comment", "quote")
_BATCH = 500
_UNSET: Any = object()


class AlreadyReviewed(AnalysisError):
    pass


class InvalidReview(AnalysisError):
    pass


def validate_m2_parameters(parameters: Mapping[str, Any]) -> None:
    try:
        validate_parameters(parameters)
    except RulesParameterError as exc:
        raise InvalidParameters(str(exc)) from exc


def _initial_stances(run: AnalysisRun) -> dict[tuple[int, int], IssueStance]:
    """(target_id, proposition_id) -> stance awal target pada versi konteks yang DIBEKUKAN run."""
    result: dict[tuple[int, int], IssueStance] = {}
    for link in run.target_contexts.select_related("context_version"):
        if link.context_version_id is None:
            continue
        for stance in TargetPropositionStance.objects.filter(
            context_version_id=link.context_version_id
        ):
            result[(link.target_id, stance.proposition_id)] = IssueStance(stance.stance)
    return result


def _chain_turns(
    chain: Chain,
    index: ConversationIndex,
    run_targets: Mapping[int, int],
    initial: Mapping[tuple[int, int], IssueStance],
    computed: Mapping[tuple[int, int], IssueStance],
    proposition_id: int,
) -> tuple[ParentTurn, ...]:
    turns = []
    last = len(chain.parents) - 1
    for position, parent in enumerate(chain.parents):
        stance = computed.get((proposition_id, parent.observation_id))
        if stance is None and position == last and parent.source_type == "post":
            target_id = run_targets.get(parent.run_id)
            stance = initial.get((target_id, proposition_id)) if target_id else None
        turns.append(ParentTurn(parent.text, stance, parent.observation_id))
    return tuple(turns)


def run_m2_rules(frozen: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    from collection.models import InspectionRun

    run = AnalysisRun.objects.select_related("dataset_version").get(pk=frozen.run_id)
    classifier = RulesClassifier(parameters)
    proposition_ids = sorted(int(k) for k in parameters["propositions"])
    propositions = {p.pk: p for p in Proposition.objects.filter(pk__in=proposition_ids)}
    missing = [i for i in proposition_ids if i not in propositions]
    if missing:
        raise InvalidParameters(f"proposition tidak ditemukan: {missing}")
    index = ConversationIndex(frozen.observation_ids)
    run_targets = dict(
        InspectionRun.objects.filter(pk__in={n.run_id for n in index.nodes.values()}).values_list(
            "pk", "target_id"
        )
    )
    initial = _initial_stances(run)
    targets = [n for n in index.nodes.values() if n.source_type in RESPONSE_TYPES]
    chains = {n.observation_id: index.chain(n.observation_id) for n in targets}
    ordered = sorted(targets, key=lambda n: (chains[n.observation_id].depth, n.observation_id))

    computed: dict[tuple[int, int], IssueStance] = {}
    rows: list[ResponseAssessment] = []
    for proposition_id in proposition_ids:
        prop = propositions[proposition_id]
        ref = PropositionRef(prop.label, prop.statement, prop.pk)
        for node in ordered:
            chain = chains[node.observation_id]
            turns = _chain_turns(chain, index, run_targets, initial, computed, proposition_id)
            result = classifier.classify(
                ClassifierInput(node.text, turns, ref, parent_unknown=chain.parent_unknown)
            )
            computed[(proposition_id, node.observation_id)] = result.issue_stance
            basis = dict(result.basis)
            basis["evidence"] = {
                "observation_id": node.observation_id,
                "parent_observation_ids": [p.observation_id for p in chain.parents],
                "parent_unknown": chain.parent_unknown,
                "parent_stance_used": turns[0].stance.value if turns and turns[0].stance else None,
                "issue_context_version": frozen.issue_context_version,
            }
            rows.append(
                ResponseAssessment(
                    analysis_run=run,
                    observation_id=node.observation_id,
                    proposition=prop,
                    issue_stance=result.issue_stance.value,
                    target_alignment=result.target_alignment.value,
                    expression_sentiment=(
                        result.expression_sentiment.value if result.expression_sentiment else None
                    ),
                    response_character=[c.value for c in result.response_character],
                    narrative_function=(
                        result.narrative_function.value if result.narrative_function else None
                    ),
                    needs_human_review=result.needs_human_review,
                    basis=basis,
                    source=AssessmentSource.MACHINE,
                )
            )
    ResponseAssessment.objects.bulk_create(rows, batch_size=_BATCH)
    return _summary(rows, len(targets), proposition_ids, len(index.nodes) - len(targets))


def _summary(
    rows: list[ResponseAssessment], assessed: int, propositions: list[int], skipped: int
) -> dict[str, Any]:
    characters = Counter(c for r in rows for c in r.response_character)
    signature = sorted(
        (
            r.observation_id,
            r.proposition_id,
            r.issue_stance,
            r.target_alignment,
            tuple(r.response_character),
            r.expression_sentiment,
            r.needs_human_review,
        )
        for r in rows
    )
    return {
        "assessments": len(rows),
        "responses_assessed": assessed,
        "observations_not_responses": skipped,
        "proposition_ids": propositions,
        "by_stance": dict(sorted(Counter(r.issue_stance for r in rows).items())),
        "by_alignment": dict(sorted(Counter(r.target_alignment for r in rows).items())),
        "by_character": dict(sorted(characters.items())),
        "needs_human_review": sum(1 for r in rows if r.needs_human_review),
        "assessments_digest": digest_json(signature),
    }


# --- tinjauan manusia ---------------------------------------------------------------------------


def current_assessments(run: AnalysisRun) -> QuerySet[ResponseAssessment]:
    """Penilaian yang berlaku: yang belum digantikan."""
    return run.assessments.filter(superseded_by__isnull=True)


def assessment_history(assessment: ResponseAssessment) -> list[ResponseAssessment]:
    """Dari penilaian mesin awal sampai `assessment`, berurutan."""
    chain = [assessment]
    while chain[-1].supersedes_id is not None:
        chain.append(ResponseAssessment.objects.get(pk=chain[-1].supersedes_id))
    return list(reversed(chain))


def review_assessment(
    *,
    assessment: ResponseAssessment,
    by: User,
    reason: str,
    issue_stance: str | None = None,
    target_alignment: str | None = None,
    expression_sentiment: Any = _UNSET,
    response_character: list[str] | None = None,
    narrative_function: Any = _UNSET,
) -> ResponseAssessment:
    """Koreksi manusia: baris BARU yang menggantikan; hasil sebelumnya tidak berubah."""
    reason = reason.strip()
    if not reason:
        raise InvalidReview("Alasan tinjauan wajib diisi.")
    if assessment.analysis_run.status != AnalysisStatus.COMPLETED:
        raise InvalidReview("Hanya penilaian pada run selesai yang dapat ditinjau.")
    if hasattr(assessment, "superseded_by"):
        raise AlreadyReviewed("Penilaian ini sudah digantikan; tinjau versi terbaru.")
    new: dict[str, Any] = {}
    if issue_stance is not None:
        new["issue_stance"] = _check(IssueStance, issue_stance, "issue_stance")
    if target_alignment is not None:
        new["target_alignment"] = _check(TargetAlignment, target_alignment, "target_alignment")
    if expression_sentiment is not _UNSET:
        new["expression_sentiment"] = (
            None
            if expression_sentiment is None
            else _check(Sentiment, expression_sentiment, "expression_sentiment")
        )
    if response_character is not None:
        if not response_character:
            raise InvalidReview(
                "response_character tidak boleh kosong (pakai RC-10 bila tak jelas)."
            )
        new["response_character"] = [
            _check(Character, c, "response_character") for c in response_character
        ]
    if narrative_function is not _UNSET:
        new["narrative_function"] = (
            None
            if narrative_function is None
            else _check(NarrativeFunction, narrative_function, "narrative_function")
        )
    changed = {
        k: [getattr(assessment, k), v] for k, v in new.items() if getattr(assessment, k) != v
    }
    if not changed:
        raise InvalidReview("Tinjauan harus mengubah setidaknya satu dimensi.")
    fields = {
        "issue_stance": assessment.issue_stance,
        "target_alignment": assessment.target_alignment,
        "expression_sentiment": assessment.expression_sentiment,
        "response_character": assessment.response_character,
        "narrative_function": assessment.narrative_function,
    }
    fields.update(new)
    evidence = (assessment.basis or {}).get("evidence")
    try:
        with transaction.atomic():
            reviewed = ResponseAssessment.objects.create(
                analysis_run=assessment.analysis_run,
                observation=assessment.observation,
                proposition=assessment.proposition,
                needs_human_review=False,
                basis={
                    "reviewed": True,
                    "previous_id": assessment.pk,
                    "changed": changed,
                    "evidence": evidence,
                },
                source=AssessmentSource.HUMAN,
                supersedes=assessment,
                reviewed_by=by,
                review_reason=reason,
                **fields,
            )
            audit.record(
                investigation_id=assessment.analysis_run.investigation_id,
                actor=by,
                action=AuditAction.CLASSIFICATION_REVIEW,
                subject_type=SubjectType.RESPONSE_ASSESSMENT,
                subject_id=reviewed.pk,
                before={
                    "assessment_id": assessment.pk,
                    **{k: v[0] for k, v in changed.items()},
                },
                after={
                    "assessment_id": reviewed.pk,
                    "observation_id": assessment.observation_id,
                    "analysis_run_id": assessment.analysis_run_id,
                    "proposition_id": assessment.proposition_id,
                    **{k: v[1] for k, v in changed.items()},
                },
                reason=reason,
            )
            return reviewed
    except IntegrityError as exc:
        raise AlreadyReviewed("Penilaian ini sudah digantikan oleh tinjauan lain.") from exc


def _check(enum: type, value: str, name: str) -> str:
    try:
        return str(enum(value).value)
    except ValueError:
        raise InvalidReview(f"Nilai {name} tidak sah: {value!r}") from None


# Ditambahkan ke registri metode (methods.py) agar execute_run dapat menjalankannya.
def register() -> None:
    from .methods import REGISTRY, Method

    REGISTRY["m2-rules"] = Method("m2-rules", "1", validate_m2_parameters, run_m2_rules)
