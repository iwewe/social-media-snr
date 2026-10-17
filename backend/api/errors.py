"""Pemetaan galat domain ke respons JSON. Dimuat lazy oleh DRF lewat settings."""

from typing import Any

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from collection.orchestrator import InspectionInProgress, NotAwaitingReview, OrchestrationError
from investigations.access import InsufficientRole, SuperuserRequired
from investigations.errors import DomainError, DuplicateTarget
from investigations.team import AlreadyMember, InactiveUser, LastOwner, NotAMember, UnknownUser


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DuplicateTarget):
        return Response(
            {"detail": str(exc), "code": "duplicate_target", "existing_id": exc.existing_id},
            status=409,
        )
    if isinstance(exc, InspectionInProgress):
        return Response({"detail": str(exc), "code": "inspection_in_progress"}, status=409)
    if isinstance(exc, NotAwaitingReview):
        return Response({"detail": str(exc), "code": "not_awaiting_review"}, status=409)
    if isinstance(exc, OrchestrationError):
        return Response({"detail": str(exc), "code": "orchestration_error"}, status=409)
    if isinstance(exc, InsufficientRole):
        return Response({"detail": str(exc), "code": "insufficient_role"}, status=403)
    if isinstance(exc, SuperuserRequired):
        return Response({"detail": str(exc), "code": "superuser_required"}, status=403)
    for kind, code, status in (
        (AlreadyMember, "already_member", 409),
        (LastOwner, "last_owner", 409),
        (NotAMember, "not_a_member", 404),
        (UnknownUser, "user_not_found", 404),
        (InactiveUser, "inactive_user", 400),
    ):
        if isinstance(exc, kind):
            return Response({"detail": str(exc), "code": code}, status=status)
    if isinstance(exc, Http404):
        # Pesan bawaan Django berbahasa Inggris dan menyebut nama model; jangan diteruskan ke UI.
        return Response({"detail": "Data tidak ditemukan.", "code": "not_found"}, status=404)
    if isinstance(exc, DomainError):
        return Response({"detail": str(exc), "code": type(exc).__name__}, status=400)
    return drf_exception_handler(exc, context)
