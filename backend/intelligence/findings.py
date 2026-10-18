"""Temuan (Finding) dan evaluasi kualitas bukti M5 (WP-2.6; ADR 0030; FR-077..FR-080).

Alur: indikator -> peninjau menulis interpretasi, menilai empat sumbu bukti, dan menimbang SEMUA
hipotesis alternatif -> temuan disegel (DRAFT) -> disahkan. Confidence dibatasi plafon kebijakan
(`m5.policy`). Revisi/reinspection menghasilkan temuan baru yang menggantikan; yang lama tetap ada.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit import services as audit
from audit.models import AuditAction, SubjectType
from collection.models import InspectionRun, PostObservation
from investigations.models import Investigation
from preservation.models import ArtifactVerification, EvidenceArtifact, VerificationResult

from .errors import AnalysisError
from .m5 import (
    AXES,
    GENERAL_ALTERNATIVES,
    Confidence,
    QualityLevel,
    VerdictLanguage,
    alternatives_complete,
    check_no_verdict,
    confidence_allowed,
    suggest_completeness,
    suggest_integrity,
    suggest_provenance,
    validate_axes,
)
from .models import (
    AnalysisRun,
    AnalysisStatus,
    CoordinationEdge,
    DatasetVersionObservation,
    Finding,
    FindingIndicator,
    FindingObservation,
    FindingReview,
    FindingRun,
    ReviewAction,
)

NOTICE = (
    "Temuan analitik yang ditinjau manusia: menggambarkan pola terobservasi pada data terbatas. "
    "Bukan vonis tentang operasi berbayar atau aktor pengendali, dan confidence bukan probabilitas."
)


class InvalidFinding(AnalysisError):
    pass


class ConfidenceAboveCeiling(InvalidFinding):
    pass


class FindingState:
    DRAFT = "DRAFT"
    ENDORSED = "ENDORSED"
    WITHDRAWN = "WITHDRAWN"
    SUPERSEDED = "SUPERSEDED"


# --- evaluasi kualitas bukti ------------------------------------------------------------------


def evidence_facts(observation_ids: Iterable[int]) -> dict[str, Any]:
    """Fakta sistem untuk sumbu bukti: verifikasi hash, metadata cakupan, dan sumber pengumpulan."""
    ids = list(observation_ids)
    run_ids = sorted(
        set(PostObservation.objects.filter(pk__in=ids).values_list("run_id", flat=True))
    )
    runs = list(InspectionRun.objects.filter(pk__in=run_ids).order_by("pk"))
    artifacts = list(
        EvidenceArtifact.objects.filter(run_id__in=run_ids).values_list("pk", flat=True)
    )
    latest: dict[int, str] = {}
    for artifact_id, result in (
        ArtifactVerification.objects.filter(artifact_id__in=artifacts)
        .order_by("artifact_id", "id")
        .values_list("artifact_id", "result")
    ):
        latest[artifact_id] = result  # yang terakhir menang
    counts = Counter(latest.values())
    integrity = {
        "artifacts": len(artifacts),
        "verified_match": counts.get(VerificationResult.MATCH, 0),
        "mismatch": counts.get(VerificationResult.MISMATCH, 0),
        "missing": counts.get(VerificationResult.MISSING, 0),
        "unreadable": counts.get(VerificationResult.UNREADABLE, 0),
        "never_verified": len(artifacts) - len(latest),
    }
    run_facts = [
        {
            "run": r.pk,
            "status": r.status,
            "outcome": (r.coverage or {}).get("outcome", r.status),
            "pagination_complete": (r.coverage or {}).get("pagination_complete"),
            "platform_displayed_count": (r.coverage or {}).get("platform_displayed_count"),
            "observed_object_count": (r.coverage or {}).get("observed_object_count"),
            "limitations": list(r.limitations or []),
        }
        for r in runs
    ]
    methods = sorted({r.source_method for r in runs if r.source_method})
    return {
        "observations": len(ids),
        "run_ids": run_ids,
        "integrity": integrity,
        "runs": run_facts,
        "source_methods": methods,
        "synthetic": "synthetic_fixture" in methods,
    }


def evaluate_evidence(observation_ids: Iterable[int]) -> dict[str, Any]:
    """Saran sistem per sumbu (peninjau memutuskan). `relevance` hanya dapat dinilai manusia."""
    facts = evidence_facts(observation_ids)
    integrity = suggest_integrity(facts["integrity"])
    completeness = suggest_completeness(facts["runs"])
    provenance = suggest_provenance(facts["source_methods"])
    relevance = (QualityLevel.NOT_ASSESSABLE, "relevansi hanya dapat dinilai peninjau manusia")
    suggestions = {
        "integrity": integrity,
        "provenance": provenance,
        "completeness": completeness,
        "relevance": relevance,
    }
    return {
        "facts": facts,
        "suggestions": {k: {"level": v[0].value, "reason": v[1]} for k, v in suggestions.items()},
        "_raw": suggestions,
    }


# --- pembuatan temuan ---------------------------------------------------------------------------


def _require(name: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise InvalidFinding(f"{name} wajib diisi")
    return value


def _independent_groups(edges: list[CoordinationEdge]) -> int | None:
    """Jumlah kelompok bukti independen; beberapa pasangan: yang TERKECIL (konservatif)."""
    if not edges:
        return None
    counts = []
    for pair in {(e.network_id, e.actor_a_id, e.actor_b_id) for e in edges}:
        network = next(
            e.network for e in edges if (e.network_id, e.actor_a_id, e.actor_b_id) == pair
        )
        summary = network.pair_summary.get(f"{pair[1]}-{pair[2]}", {})
        counts.append(len(summary.get("independent_evidence_groups", [])))
    return min(counts)


def draft_finding(
    *,
    investigation: Investigation,
    analysis_runs: Iterable[AnalysisRun],
    indicator_edges: Iterable[CoordinationEdge],
    observation_ids: Iterable[int],
    title: str,
    statement: str,
    interpretation: str,
    evidence_ratings: Mapping[str, Mapping[str, Any]],
    alternatives: Mapping[str, Mapping[str, Any]],
    confidence: str,
    confidence_reason: str,
    by: User,
    supersedes: Finding | None = None,
) -> Finding:
    """Buat temuan DRAFT (isi tersegel). Hipotesis alternatif yang belum lengkap diperbolehkan pada
    draft (plafon confidence menjadi LOW) tetapi menghalangi pengesahan."""
    title = _require("title", title)
    statement = _require("statement", statement)
    interpretation = _require("interpretation", interpretation)
    reason = _require("confidence_reason", confidence_reason)
    try:
        for field, text in (
            ("title", title),
            ("statement", statement),
            ("interpretation", interpretation),
            ("confidence_reason", reason),
        ):
            check_no_verdict(field, text)
    except VerdictLanguage as exc:
        raise InvalidFinding(str(exc)) from exc
    try:
        chosen_confidence = Confidence(confidence)
    except ValueError:
        raise InvalidFinding(f"confidence tidak sah: {confidence!r}") from None

    runs = list(analysis_runs)
    if not runs:
        raise InvalidFinding("temuan wajib tertaut ke minimal satu AnalysisRun")
    for run in runs:
        if run.investigation_id != investigation.pk or run.status != AnalysisStatus.COMPLETED:
            raise InvalidFinding("AnalysisRun harus selesai dan milik investigasi yang sama")
    platforms = {run.dataset_version.platform for run in runs}
    if len(platforms) != 1:
        raise InvalidFinding("temuan hanya boleh mencakup satu platform")
    platform = platforms.pop()
    edges = list(indicator_edges)
    run_ids = {run.pk for run in runs}
    for edge in edges:
        if edge.network.analysis_run_id not in run_ids:
            raise InvalidFinding("run indikator belum ditautkan ke temuan")
    members = set(
        DatasetVersionObservation.objects.filter(
            dataset_version_id__in={run.dataset_version_id for run in runs}
        ).values_list("observation_id", flat=True)
    )
    obs_ids = set(observation_ids)
    for edge in edges:
        obs_ids.update(edge.observation_ids)
    if not obs_ids:
        raise InvalidFinding("temuan wajib tertaut ke minimal satu observasi")
    if not obs_ids <= members:
        raise InvalidFinding("observasi harus anggota dataset dari AnalysisRun yang ditautkan")

    unknown = set(alternatives) - set(GENERAL_ALTERNATIVES)
    if unknown:
        raise InvalidFinding(f"kunci hipotesis alternatif tidak dikenal: {sorted(unknown)}")
    evaluation = evaluate_evidence(obs_ids)
    try:
        axes = validate_axes(evidence_ratings, evaluation["_raw"])
    except ValueError as exc:
        raise InvalidFinding(str(exc)) from exc
    groups = _independent_groups(edges)
    allowed, ceiling, why = confidence_allowed(
        chosen_confidence,
        axes,
        alternatives,
        groups,
        synthetic=bool(evaluation["facts"]["synthetic"]),
    )
    if not allowed:
        raise ConfidenceAboveCeiling(
            f"confidence {chosen_confidence.value} melebihi plafon {ceiling.value}: "
            + "; ".join(why)
        )
    if supersedes is not None:
        if (
            supersedes.investigation_id != investigation.pk
            or supersedes.platform != platform
            or supersedes.sealed_at is None
        ):
            raise InvalidFinding(
                "temuan yang digantikan harus tersegel, satu investigasi, satu platform"
            )
        if hasattr(supersedes, "superseded_by"):
            raise InvalidFinding("temuan itu sudah memiliki penerus")
        if supersedes.reviews.filter(action=ReviewAction.WITHDRAW).exists():
            raise InvalidFinding("temuan yang sudah ditarik tidak dapat digantikan")

    quality = {
        axis: {
            "level": evidence_ratings[axis]["level"],
            "reason": evidence_ratings[axis]["reason"].strip(),
            "override_reason": str(evidence_ratings[axis].get("override_reason", "")).strip(),
            "system_suggestion": evaluation["suggestions"][axis],
        }
        for axis in AXES
    }
    quality["_facts"] = {
        "observations": evaluation["facts"]["observations"],
        "run_ids": evaluation["facts"]["run_ids"],
        "integrity": evaluation["facts"]["integrity"],
        "runs": evaluation["facts"]["runs"],
        "source_methods": evaluation["facts"]["source_methods"],
    }
    with transaction.atomic():
        Investigation.objects.select_for_update().get(pk=investigation.pk)
        try:
            finding = Finding.objects.create(
                investigation=investigation,
                platform=platform,
                title=title,
                statement=statement,
                interpretation=interpretation,
                confidence=chosen_confidence.value,
                confidence_reason=reason,
                evidence_quality=quality,
                alternatives={k: dict(v) for k, v in alternatives.items()},
                independent_evidence_groups=groups,
                synthetic_data=evaluation["facts"]["synthetic"],
                notice=NOTICE,
                supersedes=supersedes,
                created_by=by,
            )
        except IntegrityError as exc:
            raise InvalidFinding("temuan yang digantikan sudah memiliki penerus") from exc
        FindingRun.objects.bulk_create(FindingRun(finding=finding, analysis_run=r) for r in runs)
        FindingObservation.objects.bulk_create(
            FindingObservation(finding=finding, observation_id=o) for o in sorted(obs_ids)
        )
        FindingIndicator.objects.bulk_create(
            FindingIndicator(finding=finding, edge=e) for e in edges
        )
        Finding.objects.filter(pk=finding.pk, sealed_at__isnull=True).update(
            sealed_at=timezone.now()
        )
        audit.record(
            investigation_id=investigation.pk,
            actor=by,
            action=AuditAction.FINDING_DRAFT if supersedes is None else AuditAction.FINDING_REVISE,
            subject_type=SubjectType.FINDING,
            subject_id=finding.pk,
            before=None
            if supersedes is None
            else {
                "finding_id": supersedes.pk,
                "title": supersedes.title,
                "confidence": supersedes.confidence,
                "status": finding_status(supersedes),
            },
            after={
                "finding_id": finding.pk,
                "title": title,
                "confidence": chosen_confidence.value,
                "status": FindingState.DRAFT,
                "analysis_run_ids": sorted(r.pk for r in runs),
                "observation_count": len(obs_ids),
                "synthetic_data": evaluation["facts"]["synthetic"],
            },
            reason=reason,
        )
    finding.refresh_from_db()
    return finding


def revise_finding(*, previous: Finding, **kwargs: Any) -> Finding:
    """Temuan baru yang menggantikan `previous` (mis. setelah reinspection; AT-15)."""
    return draft_finding(supersedes=previous, investigation=previous.investigation, **kwargs)


# --- siklus hidup -----------------------------------------------------------------------------


def finding_status(finding: Finding) -> str:
    actions = {r.action for r in finding.reviews.all()}
    if ReviewAction.WITHDRAW in actions:
        return FindingState.WITHDRAWN
    successor = getattr(finding, "superseded_by", None)
    if successor is not None and successor.reviews.filter(action=ReviewAction.ENDORSE).exists():
        return FindingState.SUPERSEDED
    if ReviewAction.ENDORSE in actions:
        return FindingState.ENDORSED
    return FindingState.DRAFT


def _audit_review(
    finding: Finding, by: User, action: AuditAction, old_status: str, new_status: str, note: str
) -> None:
    audit.record(
        investigation_id=finding.investigation_id,
        actor=by,
        action=action,
        subject_type=SubjectType.FINDING,
        subject_id=finding.pk,
        before={"finding_id": finding.pk, "status": old_status},
        after={"finding_id": finding.pk, "status": new_status},
        reason=note,
    )


def endorse_finding(*, finding: Finding, by: User, note: str) -> FindingReview:
    """Sahkan temuan: wajib seluruh hipotesis alternatif sudah dipertimbangkan (FR-077)."""
    note = _require("catatan pengesahan", note)
    if finding_status(finding) != FindingState.DRAFT:
        raise InvalidFinding("hanya temuan DRAFT yang dapat disahkan")
    missing = alternatives_complete(finding.alternatives)
    if missing:
        raise InvalidFinding(
            f"hipotesis alternatif belum lengkap: {missing}; buat revisi sebelum disahkan"
        )
    try:
        with transaction.atomic():
            review = FindingReview.objects.create(
                finding=finding, action=ReviewAction.ENDORSE, reviewer=by, note=note
            )
            _audit_review(
                finding,
                by,
                AuditAction.FINDING_ENDORSE,
                FindingState.DRAFT,
                FindingState.ENDORSED,
                note,
            )
            return review
    except IntegrityError as exc:
        raise InvalidFinding("temuan ini sudah ditinjau") from exc


def withdraw_finding(*, finding: Finding, by: User, note: str) -> FindingReview:
    note = _require("alasan penarikan", note)
    old_status = finding_status(finding)
    if old_status == FindingState.WITHDRAWN:
        raise InvalidFinding("temuan sudah ditarik")
    try:
        with transaction.atomic():
            review = FindingReview.objects.create(
                finding=finding, action=ReviewAction.WITHDRAW, reviewer=by, note=note
            )
            _audit_review(
                finding, by, AuditAction.FINDING_WITHDRAW, old_status, FindingState.WITHDRAWN, note
            )
            return review
    except IntegrityError as exc:
        raise InvalidFinding("temuan sudah ditarik") from exc


def finding_history(finding: Finding) -> list[Finding]:
    """Dari versi tertua sampai `finding`."""
    chain = [finding]
    while chain[-1].supersedes_id is not None:
        chain.append(Finding.objects.get(pk=chain[-1].supersedes_id))
    return list(reversed(chain))


def current_findings(investigation: Investigation) -> list[Finding]:
    """Temuan berlaku: disahkan dan belum digantikan oleh penerus yang disahkan."""
    return [
        f
        for f in Finding.objects.filter(investigation=investigation).prefetch_related("reviews")
        if finding_status(f) == FindingState.ENDORSED
    ]
