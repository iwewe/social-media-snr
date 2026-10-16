"""Pemetaan galat domain ke respons JSON. Dimuat lazy oleh DRF lewat settings."""

from typing import Any

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from investigations.errors import DomainError, DuplicateTarget


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DuplicateTarget):
        return Response(
            {"detail": str(exc), "code": "duplicate_target", "existing_id": exc.existing_id},
            status=409,
        )
    if isinstance(exc, Http404):
        # Pesan bawaan Django berbahasa Inggris dan menyebut nama model; jangan diteruskan ke UI.
        return Response({"detail": "Data tidak ditemukan.", "code": "not_found"}, status=404)
    if isinstance(exc, DomainError):
        return Response({"detail": str(exc), "code": type(exc).__name__}, status=400)
    return drf_exception_handler(exc, context)
