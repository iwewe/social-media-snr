"""WP-0.3: autentikasi (FR-001, FR-006). Tes ini memakai PostgreSQL (lihat compose.yaml / CI)."""

import re
import uuid
from collections.abc import Iterator

import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

LOGIN_URL = "/accounts/login/"
ADMIN_LOGIN_URL = "/admin/login/"

# Path halaman yang boleh diakses anonim. Menambah entri di sini harus disengaja.
PUBLIC_PATHS = {LOGIN_URL, ADMIN_LOGIN_URL}
# Endpoint API publik (tidak mengembalikan data): cookie CSRF dan login.
PUBLIC_API_PATHS = {"/api/auth/csrf/", "/api/auth/login/"}

_CONVERTER_SAMPLES = {"int": "1", "str": "x", "slug": "x", "path": "x", "uuid": str(uuid.UUID(int=0))}
_ROUTE_PARAM = re.compile(r"<(?:(?P<conv>\w+):)?\w+>")
_REGEX_GROUP = re.compile(r"\(\?P<\w+>[^)]*\)")


def _route_to_sample(route: str) -> str | None:
    """Ubah pola route/regex menjadi path contoh; None jika tidak bisa dibentuk dengan aman."""
    sample = _ROUTE_PARAM.sub(lambda m: _CONVERTER_SAMPLES.get(m.group("conv") or "str", "x"), route)
    sample = _REGEX_GROUP.sub("1", sample).lstrip("^").removesuffix("$")
    if re.search(r"[\[\](){}|*+?\\]", sample):
        return None
    return sample


def _iter_paths(patterns: list, prefix: str = "") -> Iterator[str | None]:
    for pattern in patterns:
        route = _route_to_sample(str(pattern.pattern))
        if isinstance(pattern, URLResolver):
            if route is None:
                yield None
                continue
            yield from _iter_paths(pattern.url_patterns, prefix + route)
        elif isinstance(pattern, URLPattern):
            yield None if route is None else prefix + route


def _all_paths() -> tuple[list[str], int]:
    paths: list[str] = []
    skipped = 0
    for path in _iter_paths(get_resolver().url_patterns):
        if path is None:
            skipped += 1
        else:
            paths.append("/" + path.lstrip("/"))
    return sorted(set(paths)), skipped


def test_every_url_requires_login_except_whitelist(client: Client) -> None:
    paths, _skipped = _all_paths()
    # Pengaman: enumerasi tidak boleh diam-diam kosong.
    assert len(paths) >= 10, f"terlalu sedikit URL terenumerasi: {paths}"
    assert LOGIN_URL in paths
    # Pengaman: enumerasi harus benar-benar mencakup endpoint API.
    assert sum(p.startswith("/api/") for p in paths) >= 8, paths

    offenders = []
    for path in paths:
        if path in PUBLIC_PATHS or path in PUBLIC_API_PATHS:
            continue
        response = client.get(path)
        if path.startswith("/api/"):
            # API menolak anonim dengan 401 JSON, bukan redirect HTML.
            if response.status_code != 401 or "json" not in response.headers.get("Content-Type", ""):
                offenders.append((path, response.status_code, response.headers.get("Content-Type")))
            continue
        location = response.headers.get("Location", "")
        redirected_to_login = response.status_code == 302 and (
            location.startswith(LOGIN_URL) or location.startswith(ADMIN_LOGIN_URL)
        )
        if not redirected_to_login:
            offenders.append((path, response.status_code, location))
    assert not offenders, f"URL dapat diakses tanpa login: {offenders}"


def test_public_paths_are_reachable_anonymously(client: Client) -> None:
    for path in PUBLIC_PATHS:
        assert client.get(path).status_code == 200


def test_unknown_url_is_404_and_reveals_nothing(client: Client) -> None:
    # LoginRequiredMiddleware hanya berjalan untuk URL yang terpetakan, jadi URL tak dikenal
    # tetap 404. Ini tidak membocorkan halaman nyata: semua halaman nyata dialihkan ke login.
    response = client.get("/tidak/ada/")
    assert response.status_code == 404
    assert "analis" not in response.content.decode()


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("analis1", password="kata-sandi-uji-123")


def test_login_logout_flow(client: Client, user: User) -> None:
    response = client.post(LOGIN_URL, {"username": "analis1", "password": "kata-sandi-uji-123"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    home = client.get("/")
    assert home.status_code == 200
    assert "analis1" in home.content.decode()

    assert client.post("/accounts/logout/").status_code == 302
    after = client.get("/")
    assert after.status_code == 302
    assert after.headers["Location"].startswith(LOGIN_URL)


def test_logout_requires_post(client: Client, user: User) -> None:
    client.force_login(user)
    assert client.get("/accounts/logout/").status_code == 405
    # Sesi tetap aktif setelah GET yang ditolak.
    assert client.get("/").status_code == 200


def test_wrong_password_is_rejected(client: Client, user: User) -> None:
    response = client.post(LOGIN_URL, {"username": "analis1", "password": "salah"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_is_locked_after_too_many_failures(client: Client, user: User) -> None:
    for _ in range(settings.AXES_FAILURE_LIMIT):
        client.post(LOGIN_URL, {"username": "analis1", "password": "salah"})

    # Setelah batas terlampaui, bahkan kata sandi yang benar ditolak.
    locked = client.post(LOGIN_URL, {"username": "analis1", "password": "kata-sandi-uji-123"})
    assert locked.status_code in (403, 429)
    assert "_auth_user_id" not in client.session


def test_analyst_group_exists(db: None) -> None:
    assert Group.objects.filter(name="analyst").exists()
