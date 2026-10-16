"""Respons lockout django-axes: JSON untuk /api/, teks Indonesia untuk halaman biasa."""

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

LOCKED_DETAIL = "Terlalu banyak percobaan gagal. Coba lagi beberapa saat lagi."


def lockout_response(
    request: HttpRequest, credentials: dict[str, Any] | None = None
) -> HttpResponse:
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": LOCKED_DETAIL, "code": "locked_out"}, status=429)
    return HttpResponse(LOCKED_DETAIL, status=429, content_type="text/plain; charset=utf-8")
