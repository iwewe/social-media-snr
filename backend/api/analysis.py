"""Penyaji data analisis I2 untuk API (WP-2.7): respons M2, graf M4, indikator, profil M3, temuan.

Setiap payload membawa `tier` (empat tingkat hasil) dan kategori tampilan (FR-094: fakta observasi,
hasil mesin, dikoreksi manusia, temuan yang telah ditinjau). Tidak ada skor atau peringkat "paling
mencurigakan": graf dan profil hanya memuat atribut dan metrik struktur apa adanya.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any

from django.db.models import Q, QuerySet

from audit.models import AuditAction, AuditEvent, SubjectType
from collection.models import InspectionRun, PostObservation
from intelligence import findings as fs
from intelligence.assessment import assessment_history, current_assessments
from intelligence.conversation import ConversationIndex
from intelligence.m2.taxonomy import CHARACTER_NAMES, Character
from intelligence.m5 import ALTERNATIVE_TITLES, ResultTier
from intelligence.models import (
    ActorIssueProfile,
    AnalysisRun,
    DatasetVersion,
    DatasetVersionObservation,
    Finding,
    GraphEdge,
    GraphNode,
    ResponseAssessment,
)
from investigations.models import Investigation
from preservation.models import ArtifactVerification, EvidenceArtifact

MAX_PAGE_SIZE = 200
OBSERVED, MACHINE, HUMAN, FINDING = (
    "observed_fact",
    "machine_result",
    "human_reviewed",
    "reviewed_finding",
)
CATEGORY_LABELS = {
    OBSERVED: "Fakta observasi",
    MACHINE: "Hasil mesin",
    HUMAN: "Dikoreksi manusia",
    FINDING: "Temuan yang telah ditinjau",
}
TIER_LABELS = {
    ResultTier.OBSERVED_EVIDENCE: "Bukti teramati",
    ResultTier.ANALYTICAL_CLASSIFICATION: "Klasifikasi analitik",
    ResultTier.BEHAVIORAL_NETWORK_PATTERN: "Pola perilaku dan jaringan",
    ResultTier.REVIEWED_ANALYTICAL_FINDING: "Temuan analitik yang ditinjau",
}
METHOD_TIERS = {
    "m2-rules": ResultTier.ANALYTICAL_CLASSIFICATION,
    "m3-profile": ResultTier.BEHAVIORAL_NETWORK_PATTERN,
    "m4-network": ResultTier.BEHAVIORAL_NETWORK_PATTERN,
    "co-indicators": ResultTier.BEHAVIORAL_NETWORK_PATTERN,
}


class WrongMethod(Exception):
    """Endpoint untuk jenis analisis lain."""


def tier_repr(tier: ResultTier, category: str) -> dict[str, Any]:
    return {
        "tier": int(tier),
        "tier_name": tier.name,
        "tier_label": TIER_LABELS[tier],
        "category": category,
        "category_label": CATEGORY_LABELS[category],
    }


def require_method(run: AnalysisRun, prefix: str) -> None:
    if not run.method.startswith(prefix):
        raise WrongMethod(f"Endpoint ini untuk analisis {prefix}*, bukan {run.method}.")


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


# --- run ----------------------------------------------------------------------------------------


def run_repr(run: AnalysisRun, *, full: bool = False) -> dict[str, Any]:
    tier = METHOD_TIERS.get(run.method)
    out: dict[str, Any] = {
        "id": run.pk,
        "method": run.method,
        "method_version": run.method_version,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "created_by": run.created_by.get_username(),
        "dataset": {
            "id": run.dataset_version_id,
            "number": run.dataset_version.number,
            "platform": run.dataset_version.platform,
            "observation_count": run.dataset_version.observation_count,
            "digest": run.dataset_version.observation_digest,
        },
        "error": run.error,
        "previous_run": run.previous_run_id,
        "tier": None if tier is None else tier_repr(tier, MACHINE),
    }
    if full:
        out.update(
            parameters=run.parameters,
            output=run.output,
            error=run.error,
            started_at=_iso(run.started_at),
            finished_at=_iso(run.finished_at),
            issue_context_version=(
                None if run.issue_context_version is None else run.issue_context_version.version
            ),
            target_contexts=[
                {
                    "target_id": c.target_id,
                    "version": None if c.context_version is None else c.context_version.version,
                }
                for c in run.target_contexts.select_related("context_version")
            ],
        )
    return out


# --- aktor dan observasi ------------------------------------------------------------------------


def actor_labels(actor_ids: set[int]) -> dict[int, dict[str, Any]]:
    """Identitas tampilan terakhir per akun. Username hanya informasi; identitas = ID sumber."""
    out: dict[int, dict[str, Any]] = {}
    rows = (
        PostObservation.objects.filter(author_id__in=actor_ids)
        .select_related("author")
        .order_by("author_id", "-id")
        .distinct("author_id")
    )
    for o in rows:
        out[o.author_id] = {  # type: ignore[index]
            "id": o.author_id,
            "handle": o.actor_handle,
            "display_name": o.actor_display_name,
            "external_actor_id": o.author.external_actor_id if o.author else None,
        }
    for actor_id in actor_ids - set(out):
        out[actor_id] = {
            "id": actor_id,
            "handle": None,
            "display_name": None,
            "external_actor_id": None,
        }
    return out


def observation_ref(
    o: PostObservation, labels: dict[int, dict[str, Any]] | None = None
) -> dict[str, Any]:
    author = None
    if o.author_id is not None:
        author = (labels or {}).get(o.author_id) or {
            "id": o.author_id,
            "handle": o.actor_handle,
            "display_name": o.actor_display_name,
            "external_actor_id": o.author.external_actor_id if o.author else None,
        }
    return {
        "id": o.pk,
        "external_post_id": o.post.external_post_id,
        "type": o.source_object_type,
        "text": o.text,
        "published_at": _iso(o.published_at),
        "observed_at": o.observed_at.isoformat(),
        "run_id": o.run_id,
        "author": author,
    }


def artifacts_for(pairs: set[tuple[int, int]]) -> dict[tuple[int, int], list[int]]:
    """(run_id, post_id) -> id artefak."""
    out: dict[tuple[int, int], list[int]] = defaultdict(list)
    if not pairs:
        return out
    runs = {r for r, _ in pairs}
    posts = {p for _, p in pairs}
    for art_id, run_id, post_id in EvidenceArtifact.objects.filter(
        run_id__in=runs, post_id__in=posts
    ).values_list("id", "run_id", "post_id"):
        if (run_id, post_id) in pairs:
            out[(run_id, post_id)].append(art_id)
    return out


# --- respons M2 ---------------------------------------------------------------------------------


def _labels_repr(a: ResponseAssessment) -> dict[str, Any]:
    return {
        "issue_stance": a.issue_stance,
        "target_alignment": a.target_alignment,
        "expression_sentiment": a.expression_sentiment,
        "response_character": [
            {"code": c, "name": CHARACTER_NAMES[Character(c)]} for c in a.response_character
        ],
        "narrative_function": a.narrative_function,
    }


def _basis_repr(a: ResponseAssessment) -> dict[str, Any]:
    basis = a.basis or {}
    return {
        "method": basis.get("method"),
        "rules": basis.get("rules", []),
        "matched": basis.get("matched"),
        "changed": basis.get("changed"),
        "evidence": basis.get("evidence"),
    }


def _parent_author(
    parent_obs: dict[int, PostObservation], labels: dict[int, dict[str, Any]], observation_id: int
) -> dict[str, Any] | None:
    parent = parent_obs.get(observation_id)
    if parent is None or parent.author_id is None:
        return None
    return labels.get(parent.author_id)


def default_proposition(run: AnalysisRun) -> int:
    return min(int(k) for k in run.parameters["propositions"])


def responses_page(
    run: AnalysisRun, *, filters: dict[str, Any], page: int, page_size: int
) -> dict[str, Any]:
    require_method(run, "m2-")
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    proposition_id = filters.get("proposition") or default_proposition(run)
    qs: QuerySet[ResponseAssessment] = (
        current_assessments(run)
        .filter(proposition_id=proposition_id)
        .select_related("observation__post", "observation__author", "proposition", "reviewed_by")
        .order_by("observation_id")
    )
    if filters.get("stance"):
        qs = qs.filter(issue_stance=filters["stance"])
    if filters.get("alignment"):
        qs = qs.filter(target_alignment=filters["alignment"])
    if filters.get("character"):
        qs = qs.filter(response_character__contains=[filters["character"]])
    if filters.get("origin"):
        qs = qs.filter(source=filters["origin"].upper())
    if filters.get("needs_review") is not None:
        qs = qs.filter(needs_human_review=filters["needs_review"])
    if filters.get("actor"):
        qs = qs.filter(observation__author_id=filters["actor"])
    total = qs.count()
    chunk = list(qs[(page - 1) * page_size : page * page_size])

    index = ConversationIndex(
        DatasetVersionObservation.objects.filter(
            dataset_version_id=run.dataset_version_id
        ).values_list("observation_id", flat=True)
    )
    chains = {a.observation_id: index.chain(a.observation_id) for a in chunk}
    parent_ids = {n.observation_id for c in chains.values() for n in c.parents}
    parent_stance = dict(
        current_assessments(run)
        .filter(proposition_id=proposition_id, observation_id__in=parent_ids)
        .values_list("observation_id", "issue_stance")
    )
    parent_obs = {
        o.pk: o
        for o in PostObservation.objects.filter(pk__in=parent_ids).select_related("author", "post")
    }
    actor_ids = {a.observation.author_id for a in chunk if a.observation.author_id} | {
        o.author_id for o in parent_obs.values() if o.author_id
    }
    labels = actor_labels(actor_ids)
    arts = artifacts_for({(a.observation.run_id, a.observation.post_id) for a in chunk})
    results = []
    for a in chunk:
        o = a.observation
        chain = chains[a.observation_id]
        human = a.source == "HUMAN"
        results.append(
            {
                "assessment_id": a.pk,
                "proposition": {"id": a.proposition_id, "label": a.proposition.label},
                "observation": observation_ref(o, labels),
                "parent_chain": [
                    {
                        "observation_id": n.observation_id,
                        "text": n.text,
                        "stance": parent_stance.get(n.observation_id),
                        "author": _parent_author(parent_obs, labels, n.observation_id),
                    }
                    for n in chain.parents
                ],
                "parent_unknown": chain.parent_unknown,
                "labels": _labels_repr(a),
                "source": a.source,
                "needs_human_review": a.needs_human_review,
                "basis": _basis_repr(a),
                "review": (
                    {
                        "by": a.reviewed_by.get_username(),
                        "reason": a.review_reason,
                        "at": a.created_at.isoformat(),
                    }
                    if human and a.reviewed_by
                    else None
                ),
                "versions": len(assessment_history(a)) if human else 1,
                "artifact_ids": arts.get((o.run_id, o.post_id), []),
                **tier_repr(ResultTier.ANALYTICAL_CLASSIFICATION, HUMAN if human else MACHINE),
            }
        )
    return {
        "run": run_repr(run),
        "proposition": {"id": proposition_id},
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "notice": (
            "Hasil mesin berbasis aturan (baseline); stance isu dan keselarasan dengan posting "
            "yang dibalas adalah dimensi berbeda."
        ),
    }


def assessment_repr(a: ResponseAssessment) -> dict[str, Any]:
    human = a.source == "HUMAN"
    return {
        "assessment_id": a.pk,
        "observation_id": a.observation_id,
        "analysis_run_id": a.analysis_run_id,
        "proposition_id": a.proposition_id,
        "labels": _labels_repr(a),
        "source": a.source,
        "needs_human_review": a.needs_human_review,
        "basis": _basis_repr(a),
        "review": (
            {
                "by": a.reviewed_by.get_username(),
                "reason": a.review_reason,
                "at": a.created_at.isoformat(),
            }
            if human and a.reviewed_by
            else None
        ),
        "supersedes": a.supersedes_id,
        **tier_repr(ResultTier.ANALYTICAL_CLASSIFICATION, HUMAN if human else MACHINE),
    }


# --- graf M4 ------------------------------------------------------------------------------------


def graph_payload(run: AnalysisRun, *, params: dict[str, Any]) -> dict[str, Any]:
    require_method(run, "m4-")
    projection = run.graph
    wanted_types = (
        {t for t in params["relation_types"].split(",") if t}
        if params.get("relation_types")
        else None
    )
    nodes = {
        n.actor_id: n
        for n in GraphNode.objects.filter(projection=projection).select_related("actor")
    }
    edges = list(
        GraphEdge.objects.filter(projection=projection).select_related("from_node", "to_node")
    )
    kept_edges = []
    for e in edges:
        if wanted_types is not None and e.relation_type not in wanted_types:
            continue
        since, until = params.get("since"), params.get("until")
        if e.first_published_at is None and e.last_published_at is None:
            if params.get("include_unknown_time") is False:
                continue
        else:
            if since and e.last_published_at and e.last_published_at < since:
                continue
            if until and e.first_published_at and e.first_published_at >= until:
                continue
        kept_edges.append(e)
    stance = params.get("stance")
    if stance:
        allowed = {a for a, n in nodes.items() if n.attributes.get("stance_summary") == stance}
        kept_edges = [
            e
            for e in kept_edges
            if e.from_node.actor_id in allowed and e.to_node.actor_id in allowed
        ]
        keep_nodes = allowed
    else:
        keep_nodes = set(nodes)
    strength: dict[int, int] = defaultdict(int)
    for e in kept_edges:
        strength[e.from_node.actor_id] += e.weight
        strength[e.to_node.actor_id] += e.weight
    total_nodes = len(keep_nodes)
    max_nodes = params.get("max_nodes", 300)
    truncated = total_nodes > max_nodes
    if truncated:
        ranked = sorted(keep_nodes, key=lambda a: (-strength.get(a, 0), a))[:max_nodes]
        keep_nodes = set(ranked)
        kept_edges = [
            e
            for e in kept_edges
            if e.from_node.actor_id in keep_nodes and e.to_node.actor_id in keep_nodes
        ]
    labels = actor_labels(keep_nodes)
    return {
        "run": run_repr(run),
        "platform": projection.platform,
        "definition": projection.definition,
        "metrics": projection.metrics,
        "exclusions": projection.exclusions,
        "filters": {
            "relation_types": sorted(wanted_types) if wanted_types is not None else None,
            "since": _iso(params.get("since")),
            "until": _iso(params.get("until")),
            "stance": stance,
            "max_nodes": max_nodes,
            "include_unknown_time": params.get("include_unknown_time") is not False,
        },
        "nodes": [
            {
                "id": a,
                "label": labels[a]["handle"] or labels[a]["external_actor_id"] or f"akun {a}",
                "actor": labels[a],
                "attributes": nodes[a].attributes,
                "metrics": nodes[a].metrics,
            }
            for a in sorted(keep_nodes)
        ],
        "edges": [
            {
                "id": e.pk,
                "kind": "interaction",
                "source": e.from_node.actor_id,
                "target": e.to_node.actor_id,
                "type": e.relation_type,
                "weight": e.weight,
                "observation_ids": e.observation_ids,
                "stance_counts": e.stance_counts,
                "first_published_at": _iso(e.first_published_at),
                "last_published_at": _iso(e.last_published_at),
            }
            for e in sorted(kept_edges, key=lambda e: e.pk)
        ],
        "total_nodes": total_nodes,
        "truncated": truncated,
        "notice": projection.metrics.get("note"),
        **tier_repr(ResultTier.BEHAVIORAL_NETWORK_PATTERN, MACHINE),
    }


# --- indikator koordinasi -----------------------------------------------------------------------


def coordination_page(
    run: AnalysisRun, *, filters: dict[str, Any], page: int, page_size: int
) -> dict[str, Any]:
    require_method(run, "co-")
    network = run.coordination
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    qs = network.edges.select_related("actor_a", "actor_b").order_by(
        "actor_a_id", "actor_b_id", "indicator", "variant"
    )
    if filters.get("indicator"):
        qs = qs.filter(indicator=filters["indicator"])
    if filters.get("min_support"):
        qs = qs.filter(support__gte=filters["min_support"])
    if filters.get("actor"):
        qs = qs.filter(Q(actor_a_id=filters["actor"]) | Q(actor_b_id=filters["actor"]))
    rows = list(qs)
    if filters.get("beyond_baseline") is not None:
        rows = [
            r
            for r in rows
            if bool(r.baseline.get("exceeds_baseline_p95")) == filters["beyond_baseline"]
        ]
    total = len(rows)
    chunk = rows[(page - 1) * page_size : page * page_size]
    labels = actor_labels({r.actor_a_id for r in chunk} | {r.actor_b_id for r in chunk})
    pairs = {f"{r.actor_a_id}-{r.actor_b_id}" for r in chunk}
    return {
        "run": run_repr(run),
        "platform": network.platform,
        "notice": network.definition.get("notice"),
        "alternative_hypotheses": network.definition.get("alternative_hypotheses"),
        "definition": network.definition,
        "baseline": network.baseline,
        "exclusions": network.exclusions,
        "pair_summary": {k: v for k, v in network.pair_summary.items() if k in pairs},
        "results": [
            {
                "id": r.pk,
                "kind": "behavioral_similarity",
                "indicator": r.indicator,
                "variant": r.variant,
                "actor_a": labels[r.actor_a_id],
                "actor_b": labels[r.actor_b_id],
                "value": r.value,
                "support": r.support,
                "explanation": r.explanation,
                "detail": r.detail,
                "baseline": r.baseline,
                "overlaps_with": r.overlaps_with,
                "observation_ids": r.observation_ids,
                "evidence_truncated": r.evidence_truncated,
                "alternative_hypotheses": r.alternative_hypotheses,
            }
            for r in chunk
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        **tier_repr(ResultTier.BEHAVIORAL_NETWORK_PATTERN, MACHINE),
    }


# --- profil aktor M3 ----------------------------------------------------------------------------


def profile_summary(p: ActorIssueProfile, labels: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": p.pk,
        "actor": labels[p.actor_id],
        "level": p.level,
        "participation": p.dimensions["participation"],
        "coverage_statement": p.coverage["statement"],
        "partial_coverage": p.coverage["partial_coverage"],
    }


def profiles_page(run: AnalysisRun, *, page: int, page_size: int) -> dict[str, Any]:
    require_method(run, "m3-")
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    qs = run.profiles.select_related("actor").order_by("actor_id")
    total = qs.count()
    chunk = list(qs[(page - 1) * page_size : page * page_size])
    labels = actor_labels({p.actor_id for p in chunk})
    return {
        "run": run_repr(run),
        "results": [profile_summary(p, labels) for p in chunk],
        "total": total,
        "page": page,
        "page_size": page_size,
        "notice": (
            "Profil hanya berlaku bagi sampel, platform, isu, dan periode yang diperiksa; bukan "
            "seluruh aktivitas akun dan bukan penilaian terhadap orangnya."
        ),
        **tier_repr(ResultTier.BEHAVIORAL_NETWORK_PATTERN, MACHINE),
    }


def profile_detail(p: ActorIssueProfile) -> dict[str, Any]:
    labels = actor_labels({p.actor_id})
    return {
        "id": p.pk,
        "run": run_repr(p.analysis_run),
        "actor": labels[p.actor_id],
        "platform": p.coverage["platform"],
        "proposition_id": p.proposition_id,
        "level": p.level,
        "period": {"start": p.period_start.isoformat(), "end": p.period_end.isoformat()},
        "coverage": p.coverage,
        "dimensions": p.dimensions,
        **tier_repr(ResultTier.BEHAVIORAL_NETWORK_PATTERN, MACHINE),
    }


# --- temuan M5 ----------------------------------------------------------------------------------


def finding_summary(f: Finding) -> dict[str, Any]:
    successor = getattr(f, "superseded_by", None)
    return {
        "id": f.pk,
        "title": f.title,
        "status": fs.finding_status(f),
        "confidence": f.confidence,
        "synthetic_data": f.synthetic_data,
        "platform": f.platform,
        "created_by": f.created_by.get_username(),
        "created_at": f.created_at.isoformat(),
        "supersedes": f.supersedes_id,
        "superseded_by": None if successor is None else successor.pk,
        **tier_repr(ResultTier.REVIEWED_ANALYTICAL_FINDING, FINDING),
    }


def finding_detail(f: Finding) -> dict[str, Any]:
    obs_links = list(f.observations.select_related("observation__post", "observation__author")[:50])
    labels = actor_labels({o.observation.author_id for o in obs_links if o.observation.author_id})
    return {
        **finding_summary(f),
        "statement": f.statement,
        "interpretation": f.interpretation,
        "confidence_reason": f.confidence_reason,
        "evidence_quality": f.evidence_quality,
        "alternatives": f.alternatives,
        "alternative_titles": ALTERNATIVE_TITLES,
        "independent_evidence_groups": f.independent_evidence_groups,
        "notice": f.notice,
        "history": [
            {"id": x.pk, "status": fs.finding_status(x), "created_at": x.created_at.isoformat()}
            for x in fs.finding_history(f)
        ],
        "reviews": [
            {
                "action": r.action,
                "reviewer": r.reviewer.get_username(),
                "note": r.note,
                "at": r.created_at.isoformat(),
            }
            for r in f.reviews.select_related("reviewer").order_by("id")
        ],
        "runs": [
            run_repr(r.analysis_run)
            for r in f.runs.select_related(
                "analysis_run__dataset_version", "analysis_run__created_by"
            )
        ],
        "observation_count": f.observations.count(),
        "observations": [observation_ref(o.observation, labels) for o in obs_links],
        "indicator_ids": list(f.indicators.values_list("edge_id", flat=True)),
    }


def finding_history_ids(f: Finding) -> list[int]:
    return [x.pk for x in fs.finding_history(f)]


# --- jejak bukti: satu observasi ----------------------------------------------------------------


def observation_detail(o: PostObservation) -> dict[str, Any]:
    from collection.models import PostRelation, RelationType

    run: InspectionRun = o.run
    chain = []
    seen = {o.post_id}
    current = o
    for _ in range(50):
        link = PostRelation.objects.filter(
            run=current.run, from_post_id=current.post_id, relation_type=RelationType.REPLY_TO
        ).first()
        if link is None or link.to_post_id is None or link.to_post_id in seen:
            break
        parent = (
            PostObservation.objects.filter(post_id=link.to_post_id, run=current.run)
            .select_related("post", "author")
            .first()
        )
        if parent is None:
            break
        seen.add(parent.post_id)
        chain.append(parent)
        current = parent
    labels = actor_labels({x.author_id for x in [o, *chain] if x.author_id})
    artifacts = []
    scope = Q(run=run) & (
        Q(post_id__in=[o.post_id, *[p.post_id for p in chain]]) | Q(post__isnull=True)
    )
    for art in EvidenceArtifact.objects.filter(scope).order_by("id"):
        last = ArtifactVerification.objects.filter(artifact=art).order_by("-id").first()
        artifacts.append(
            {
                "id": art.pk,
                "kind": art.kind,
                "content_type": art.content_type,
                "size_bytes": art.size_bytes,
                "sha256": art.sha256,
                "post_specific": art.post_id is not None,
                "last_verification": None
                if last is None
                else {"result": last.result, "at": last.verified_at.isoformat()},
            }
        )
    assessments = [
        assessment_repr(a)
        for a in ResponseAssessment.objects.filter(observation=o, superseded_by__isnull=True)
        .select_related("reviewed_by")
        .order_by("analysis_run_id", "proposition_id")
    ]
    finding_ids = list(
        Finding.objects.filter(observations__observation=o).values_list("pk", flat=True).distinct()
    )
    classification_trail = [
        audit_event_repr(e)
        for e in AuditEvent.objects.filter(
            investigation_id=run.target.investigation_id,
            subject_type=SubjectType.RESPONSE_ASSESSMENT,
            after__observation_id=o.pk,
        )
        .select_related("actor")
        .order_by("-id")[:50]
    ]
    return {
        "observation": observation_ref(o, labels),
        "parent_chain": [observation_ref(p, labels) for p in chain],
        "run": {
            "id": run.pk,
            "sequence": run.sequence,
            "status": run.status,
            "target_id": run.target_id,
            "source_method": run.source_method,
        },
        "artifacts": artifacts,
        "assessments": assessments,
        "finding_ids": finding_ids,
        "classification_trail": classification_trail,
        **tier_repr(ResultTier.OBSERVED_EVIDENCE, OBSERVED),
    }


# --- jejak audit (WP-2.8) ---------------------------------------------------------------------


def audit_event_repr(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.pk,
        "at": e.occurred_at.isoformat(),
        "actor": e.actor.get_username(),
        "action": e.action,
        "action_label": AuditAction(e.action).label,
        "subject_type": e.subject_type,
        "subject_type_label": SubjectType(e.subject_type).label,
        "subject_id": e.subject_id,
        "before": e.before,
        "after": e.after,
        "reason": e.reason,
    }


def audit_page(
    investigation: Investigation, *, filters: dict[str, Any], page: int, page_size: int
) -> dict[str, Any]:
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    qs = AuditEvent.objects.filter(investigation=investigation).select_related("actor")
    for key in ("action", "subject_type", "subject_id"):
        if filters.get(key) is not None:
            qs = qs.filter(**{key: filters[key]})
    if filters.get("actor"):
        qs = qs.filter(actor__username=filters["actor"])
    if filters.get("observation") is not None:
        qs = qs.filter(
            subject_type=SubjectType.RESPONSE_ASSESSMENT,
            after__observation_id=filters["observation"],
        )
    total = qs.count()
    chunk = list(qs.order_by("-id")[(page - 1) * page_size : page * page_size])
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": [audit_event_repr(e) for e in chunk],
        "notice": (
            "Jejak ini hanya dapat bertambah: setiap perubahan konteks, tinjauan klasifikasi, "
            "dan siklus temuan tercatat beserta pelaku, waktu, nilai sebelum/sesudah, alasan."
        ),
    }


# --- akses bukti (WP-3.6b) ---------------------------------------------------------------------

PURPOSE_LABELS = {
    "verify": "Verifikasi hash satu artefak",
    "verify_run": "Verifikasi seluruh artefak satu pemeriksaan",
    "download": "Unduh isi artefak",
}


def evidence_access_page(
    investigation: Investigation, *, filters: dict[str, Any], page: int, page_size: int
) -> dict[str, Any]:
    """Siapa membuka/memverifikasi bukti, kapan, untuk apa, dan hasilnya (NFR-02, PRD bagian 13).

    Sumbernya riwayat verifikasi yang sudah append-only; jalur berkas tidak ditampilkan."""
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    qs = ArtifactVerification.objects.filter(
        artifact__run__target__investigation=investigation
    ).select_related("verified_by", "artifact", "artifact__run")
    if filters.get("purpose"):
        qs = qs.filter(purpose=filters["purpose"])
    if filters.get("result"):
        qs = qs.filter(result=filters["result"])
    if filters.get("user"):
        qs = qs.filter(verified_by__username=filters["user"])
    if filters.get("artifact") is not None:
        qs = qs.filter(artifact_id=filters["artifact"])
    total = qs.count()
    chunk = list(qs.order_by("-id")[(page - 1) * page_size : page * page_size])
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": [
            {
                "id": v.pk,
                "at": v.verified_at.isoformat(),
                "user": v.verified_by.get_username(),
                "purpose": v.purpose,
                "purpose_label": PURPOSE_LABELS.get(v.purpose, v.purpose),
                "result": v.result,
                "artifact": {
                    "id": v.artifact_id,
                    "kind": v.artifact.kind,
                    "run_id": v.artifact.run_id,
                    "run_sequence": v.artifact.run.sequence,
                },
            }
            for v in chunk
        ],
        "notice": (
            "Riwayat ini hanya dapat bertambah. Hash membuktikan berkas sama dengan saat disimpan, "
            "bukan keaslian konten platform."
        ),
    }


# --- memulai analisis (WP-2.9) ----------------------------------------------------------------

CONTEXT_NOTE = (
    "Catatan konteks target tersimpan dan berversi, tetapi TEKSNYA belum dibaca klasifier mesin. "
    "Yang dipakai: stance awal target, cue yang Anda tulis, dan rantai balasan. Mengubah "
    "penjelasan konteks saja tidak mengubah klasifikasi; baseline juga belum memahami negasi "
    "secara umum, dan narrative function tidak diisi mesin."
)


def dataset_repr(d: DatasetVersion) -> dict[str, Any]:
    return {
        "id": d.pk,
        "number": d.number,
        "platform": d.platform,
        "observation_count": d.observation_count,
        "inspection_runs": len(d.selection.get("runs", [])),
        "note": d.note,
        "created_at": d.created_at.isoformat(),
    }


def setup_payload(investigation: Investigation) -> dict[str, Any]:
    """Bahan formulir 'Jalankan analisis': dataset, pemeriksaan, proposition, run M2, contoh."""
    from intelligence.examples import CO_EXAMPLE, EXPLORATORY_NOTE, M3_EXAMPLE, M4_EXAMPLE
    from intelligence.services import INGESTED_STATES
    from investigations.models import Proposition

    datasets = DatasetVersion.objects.filter(investigation=investigation).order_by("-number")
    runs = (
        InspectionRun.objects.filter(
            target__investigation=investigation, ingestion__state__in=INGESTED_STATES
        )
        .select_related("target")
        .order_by("target_id", "sequence")
    )
    propositions = (
        Proposition.objects.filter(issue__investigation=investigation, retired_at__isnull=True)
        .select_related("issue")
        .order_by("issue_id", "number")
    )
    m2_runs = AnalysisRun.objects.filter(
        investigation=investigation, method__startswith="m2-", status="COMPLETED"
    ).order_by("-id")
    return {
        "datasets": [dataset_repr(d) for d in datasets],
        "inspection_runs": [
            {
                "id": r.pk,
                "target_id": r.target_id,
                "target_url": r.target.normalized_url,
                "platform": r.target.platform,
                "sequence": r.sequence,
                "status": r.status,
                "finished_at": _iso(r.finished_at),
            }
            for r in runs
        ],
        "propositions": [
            {
                "id": p.pk,
                "label": p.label,
                "statement": p.statement,
                "issue": {"id": p.issue_id, "title": p.issue.title},
            }
            for p in propositions
        ],
        "m2_runs": [
            {"id": r.pk, "dataset_id": r.dataset_version_id, "created_at": r.created_at.isoformat()}
            for r in m2_runs
        ],
        "examples": {"m3": M3_EXAMPLE, "m4": M4_EXAMPLE, "co": CO_EXAMPLE},
        "notes": {"exploratory": EXPLORATORY_NOTE, "context": CONTEXT_NOTE},
    }
