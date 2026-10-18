"""Mutasi pengaturan HTTPS (WP-3.6b)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

# Di host (subproses butuh settings dari salinan slot, venv dari repo asli).
COMMAND = 'DJANGO_SECRET_KEY=x {origin}/backend/.venv/bin/python -m pytest -c pyproject.toml -q -x -p no:cacheprovider ../tests/test_https_settings.py'
BASELINE_COMMAND = COMMAND
CWD = '{root}/backend'
TIMEOUT = 300
S = 'backend/config/settings.py'

MUTATIONS = [
    Mutation('cookie sesi tak Secure', S, '    SESSION_COOKIE_SECURE = True\n', '    SESSION_COOKIE_SECURE = False\n'),
    Mutation('cookie CSRF tak Secure', S, '    CSRF_COOKIE_SECURE = True\n', '    CSRF_COOKIE_SECURE = False\n'),
    Mutation('header proxy tak dipercaya', S, '    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")\n', '    pass\n'),
    Mutation('header proxy salah', S, '("HTTP_X_FORWARDED_PROTO", "https")', '("HTTP_X_FORWARDED_PROTO", "http")'),
    Mutation('HSTS bawaan nol', S, 'os.environ.get("SNR_HSTS_SECONDS", "3600")', 'os.environ.get("SNR_HSTS_SECONDS", "0")'),
    Mutation('HSTS tak dapat dikonfigurasi', S, '    SECURE_HSTS_SECONDS = int(os.environ.get("SNR_HSTS_SECONDS", "3600"))', '    SECURE_HSTS_SECONDS = 3600'),
    Mutation('debug diizinkan bersama HTTPS', S, '    if DEBUG:\n        raise RuntimeError("SNR_HTTPS=1 tidak boleh', '    if False:\n        raise RuntimeError("SNR_HTTPS=1 tidak boleh'),
    Mutation('bintang pada host diizinkan', S, 'if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:', 'if not ALLOWED_HOSTS:'),
    Mutation('host kosong diizinkan', S, 'if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:', 'if "*" in ALLOWED_HOSTS:'),
    Mutation('pengalihan SSL diaktifkan di Django', S, '    SECURE_SSL_REDIRECT = False\n', '    SECURE_SSL_REDIRECT = True\n'),
    Mutation('nosniff dimatikan', S, '    SECURE_CONTENT_TYPE_NOSNIFF = True\n', '    SECURE_CONTENT_TYPE_NOSNIFF = False\n'),
    Mutation('mode HTTPS selalu aktif', S, 'SNR_HTTPS = _env_bool("SNR_HTTPS", False)', 'SNR_HTTPS = _env_bool("SNR_HTTPS", True)'),
    Mutation('peringatan deploy dibungkam berlebihan', S, 'SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]', 'SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021", "security.W012", "security.W016"]'),
]
