"""Pencatatan audit; dipanggil di dalam transaksi perubahan yang sama (batal bersama)."""

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from .models import AuditAction, AuditEvent, SubjectType


def record(
    *,
    investigation_id: int,
    actor: AbstractBaseUser,
    action: AuditAction,
    subject_type: SubjectType,
    subject_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    reason: str = "",
) -> AuditEvent:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("audit.record harus dipanggil di dalam transaksi perubahan.")
    return AuditEvent.objects.create(
        investigation_id=investigation_id,
        actor=actor,  # type: ignore[misc]
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        before=before,
        after=after,
        reason=reason,
    )
