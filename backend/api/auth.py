"""Kelas autentikasi API. Modul terpisah dari base.py untuk menghindari import melingkar:
DRF memuat kelas autentikasi bawaan dari settings saat APIView didefinisikan."""

from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class SessionAuth401(SessionAuthentication):
    """SessionAuthentication yang membalas 401 (bukan 403) untuk pengguna anonim."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"
