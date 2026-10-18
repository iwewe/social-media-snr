"""WP-3.6b: pengaturan HTTPS aktif hanya dengan SNR_HTTPS=1 dan salah konfigurasi ditolak saat startup.

Settings dibaca saat impor, jadi setiap kasus dijalankan di subproses dengan environment sendiri."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_BACKEND = Path(__file__).resolve().parents[1] / "backend"
# Di kontainer tes dipasang di /tests dan kode di /app (direktori kerja pytest); di CI/host: repo/backend.
BACKEND = _REPO_BACKEND if (_REPO_BACKEND / "manage.py").exists() else Path.cwd()
KEY = "uji-kunci-rahasia-acak-" + "q7Zx2LmP9wRt4VbN8sKd3FgH6jYc1AeU5oIn0XyW"  # secret-scan: allow
BASE_ENV = {"DJANGO_SECRET_KEY": KEY, "DJANGO_ALLOWED_HOSTS": "snr.contoh.test"}
PROBE = (
    "import json, django.conf as c; s = c.settings;"
    "print(json.dumps({k: getattr(s, k, None) for k in ("
    "'SESSION_COOKIE_SECURE','CSRF_COOKIE_SECURE','SECURE_HSTS_SECONDS',"
    "'SECURE_PROXY_SSL_HEADER','SECURE_SSL_REDIRECT','SECURE_CONTENT_TYPE_NOSNIFF')}))"
)


def run(extra: dict[str, str], code: str = PROBE) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "SNR_"))}
    env.update(BASE_ENV)
    env.update(extra)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    return subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True
    )


def probe(extra: dict[str, str]) -> dict:
    res = run(extra)
    assert res.returncode == 0, res.stderr[-400:]
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_https_mode_secures_cookies_trusts_the_proxy_header_and_sets_hsts() -> None:
    s = probe({"SNR_HTTPS": "1"})
    assert s["SESSION_COOKIE_SECURE"] is True and s["CSRF_COOKIE_SECURE"] is True
    assert s["SECURE_HSTS_SECONDS"] == 3600
    assert s["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert s["SECURE_SSL_REDIRECT"] is False and s["SECURE_CONTENT_TYPE_NOSNIFF"] is True


def test_hsts_duration_is_configurable() -> None:
    assert probe({"SNR_HTTPS": "1", "SNR_HSTS_SECONDS": "86400"})["SECURE_HSTS_SECONDS"] == 86400


def test_default_mode_leaves_development_settings_alone() -> None:
    s = probe({"DJANGO_DEBUG": "1"})
    assert not s["SESSION_COOKIE_SECURE"] and not s["CSRF_COOKIE_SECURE"]
    assert not s["SECURE_HSTS_SECONDS"] and s["SECURE_PROXY_SSL_HEADER"] is None


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"SNR_HTTPS": "1", "DJANGO_DEBUG": "1"}, "DJANGO_DEBUG"),
        ({"SNR_HTTPS": "1", "DJANGO_ALLOWED_HOSTS": "*"}, "tanpa '*'"),
        ({"SNR_HTTPS": "1", "DJANGO_ALLOWED_HOSTS": "a.test,*"}, "tanpa '*'"),
        ({"SNR_HTTPS": "1", "DJANGO_ALLOWED_HOSTS": ""}, "ALLOWED_HOSTS eksplisit"),
    ],
)
def test_misconfigured_https_mode_refuses_to_start(extra: dict[str, str], message: str) -> None:
    res = run(extra)
    assert res.returncode != 0 and message in res.stderr


def test_deploy_check_has_no_warnings_in_https_mode() -> None:
    code = (
        "import django; django.setup();"
        "from django.core.management import call_command;"
        "call_command('check', '--deploy', '--fail-level', 'WARNING')"
    )
    res = run({"SNR_HTTPS": "1", "SNR_HSTS_SECONDS": "3600"}, code)
    assert res.returncode == 0, res.stderr[-600:] + res.stdout[-300:]


def test_only_the_three_documented_deploy_checks_are_silenced() -> None:
    res = run(
        {"SNR_HTTPS": "1"},
        "import django.conf as c; print(sorted(c.settings.SILENCED_SYSTEM_CHECKS))",
    )
    assert res.returncode == 0, res.stderr[-300:]
    assert res.stdout.strip() == "['security.W005', 'security.W008', 'security.W021']"
    plain = run(
        {"DJANGO_DEBUG": "1"}, "import django.conf as c; print(c.settings.SILENCED_SYSTEM_CHECKS)"
    )
    assert plain.stdout.strip() == "[]"
