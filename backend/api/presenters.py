"""Bentuk JSON keluaran. Eksplisit agar tidak ada field internal yang bocor."""

from typing import Any

from investigations.models import (
    CollectionTarget,
    Investigation,
    Issue,
    Proposition,
    TargetContextVersion,
)


def user_repr(user: Any) -> dict[str, Any]:
    return {"username": user.get_username(), "is_staff": bool(user.is_staff)}


def proposition_repr(p: Proposition) -> dict[str, Any]:
    return {
        "id": p.pk,
        "number": p.number,
        "label": p.label,
        "statement": p.statement,
        "retired": p.retired_at is not None,
    }


def issue_repr(issue: Issue) -> dict[str, Any]:
    latest = issue.context_versions.order_by("-version").first()
    return {
        "id": issue.pk,
        "title": issue.title,
        "created_at": issue.created_at.isoformat(),
        "context": None
        if latest is None
        else {"version": latest.version, "definition": latest.definition},
        "propositions": [proposition_repr(p) for p in issue.propositions.all()],
    }


def context_version_repr(v: TargetContextVersion) -> dict[str, Any]:
    return {
        "version": v.version,
        "note": v.note,
        "created_at": v.created_at.isoformat(),
        "created_by": v.created_by.get_username(),
        "stances": [
            {
                "proposition_id": s.proposition_id,
                "label": s.proposition.label,
                "statement": s.proposition.statement,
                "stance": s.stance,
            }
            for s in v.stances.select_related("proposition").order_by("proposition__number")
        ],
    }


def target_repr(t: CollectionTarget) -> dict[str, Any]:
    versions = list(t.context_versions.select_related("created_by").order_by("-version"))
    return {
        "id": t.pk,
        "platform": t.platform,
        "target_type": t.target_type,
        "url": t.url,
        "normalized_url": t.normalized_url,
        "created_at": t.created_at.isoformat(),
        "context": context_version_repr(versions[0]) if versions else None,
        "context_history": [context_version_repr(v) for v in versions],
        # InspectionRun belum ada (WP-1.2). null berarti "belum pernah diperiksa", bukan "kosong".
        "latest_inspection": None,
    }


def investigation_summary(inv: Investigation) -> dict[str, Any]:
    return {
        "id": inv.pk,
        "name": inv.name,
        "description": inv.description,
        "created_at": inv.created_at.isoformat(),
        "created_by": inv.created_by.get_username(),
        "issue_count": inv.issues.count(),
        "target_count": inv.targets.count(),
    }


def investigation_detail(inv: Investigation) -> dict[str, Any]:
    return {
        **investigation_summary(inv),
        "issues": [issue_repr(i) for i in inv.issues.all()],
        "targets": [target_repr(t) for t in inv.targets.all()],
    }
