"""Bentuk JSON keluaran. Eksplisit agar tidak ada field internal yang bocor."""

from typing import Any

from investigations import access
from investigations.models import (
    CollectionTarget,
    Investigation,
    Issue,
    Proposition,
    TargetContextVersion,
)

from .messages import CONTEXT_INSUFFICIENT
from .runs import latest_inspection_summary


def user_repr(user: Any) -> dict[str, Any]:
    return {
        "username": user.get_username(),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
    }


def proposition_repr(p: Proposition) -> dict[str, Any]:
    return {
        "id": p.pk,
        "number": p.number,
        "label": p.label,
        "statement": p.statement,
        "retired": p.retired_at is not None,
    }


def issue_repr(issue: Issue) -> dict[str, Any]:
    versions = list(issue.context_versions.select_related("created_by").order_by("-version"))
    latest = versions[0] if versions else None
    return {
        "id": issue.pk,
        "title": issue.title,
        "created_at": issue.created_at.isoformat(),
        "context": None
        if latest is None
        else {"version": latest.version, "definition": latest.definition},
        "context_history": [
            {
                "version": v.version,
                "definition": v.definition,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by.get_username(),
            }
            for v in versions
        ],
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


def _target_notices(versions: list[TargetContextVersion]) -> list[dict[str, Any]]:
    """Konteks belum cukup (FR-095): catatan kosong dan tanpa posisi awal."""
    latest = versions[0] if versions else None
    if latest is None or (not latest.note.strip() and not latest.stances.exists()):
        return [CONTEXT_INSUFFICIENT.to_dict()]
    return []


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
        # null berarti "belum pernah diperiksa", bukan "kosong" (NFR-08).
        "latest_inspection": latest_inspection_summary(t),
        "notices": _target_notices(versions),
    }


def investigation_summary(inv: Investigation, user: Any) -> dict[str, Any]:
    return {
        # Peran pengguna ini: OWNER/MEMBER/VIEWER atau ADMIN (super admin).
        "my_role": access.effective_role(user, inv),
        "member_count": inv.memberships.filter(revoked_at__isnull=True).count(),
        "id": inv.pk,
        "name": inv.name,
        "description": inv.description,
        "created_at": inv.created_at.isoformat(),
        "created_by": inv.created_by.get_username(),
        "issue_count": inv.issues.count(),
        "target_count": inv.targets.count(),
    }


def investigation_detail(inv: Investigation, user: Any) -> dict[str, Any]:
    return {
        **investigation_summary(inv, user),
        "issues": [issue_repr(i) for i in inv.issues.all()],
        "targets": [target_repr(t) for t in inv.targets.all()],
    }


def member_repr(m: Any) -> dict[str, Any]:
    return {
        "user_id": m.user_id,
        "username": m.user.get_username(),
        "role": m.role,
        "since": m.created_at.isoformat(),
        "added_by": m.added_by.get_username(),
    }


def account_repr(u: Any, active_memberships: int) -> dict[str, Any]:
    """Akun untuk super admin. Tanpa hash kata sandi atau data sesi."""
    return {
        "id": u.pk,
        "username": u.get_username(),
        "is_active": u.is_active,
        "is_superuser": u.is_superuser,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "date_joined": u.date_joined.isoformat(),
        "active_memberships": active_memberships,
    }
