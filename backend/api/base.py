"""Fondasi API JSON untuk frontend React (WP-0.5).

Pola keamanan:
- Semua view API dikecualikan dari LoginRequiredMiddleware (yang mengalihkan ke halaman login HTML)
  dan menegakkan autentikasi sendiri lewat DRF: anonim mendapat 401 JSON, bukan redirect.
- Izin bawaan IsAuthenticated; endpoint publik harus menyatakan AllowAny secara eksplisit.
- Sesi Django + CSRF (header X-CSRFToken). Tidak ada token/JWT.
"""

from typing import Any

from django.contrib.auth.decorators import login_not_required
from rest_framework.views import APIView


class ApiView(APIView):
    """Basis semua view API: dikecualikan dari middleware login-redirect, dilindungi DRF."""

    @classmethod
    def as_view(cls, **initkwargs: Any) -> Any:
        return login_not_required(super().as_view(**initkwargs))
