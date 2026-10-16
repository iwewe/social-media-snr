"""Normalisasi URL target (FR-011, AT-01).

Normalisasi ini generik dan hanya untuk mencegah target ganda akibat penulisan URL berbeda.
Ini BUKAN identitas objek: identitas Post/ActorAccount ditentukan ID stabil dari sumber
(PRD bagian 5). Aturan khusus per platform menjadi tanggung jawab adapter (I3).
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .enums import Platform
from .errors import InvalidTargetURL

MAX_URL_LENGTH = 2000

# Domain yang sah per platform (cocok persis atau sebagai subdomain).
PLATFORM_DOMAINS: dict[str, tuple[str, ...]] = {
    Platform.X: ("x.com", "twitter.com"),
    Platform.THREADS: ("threads.com", "threads.net"),
    Platform.TIKTOK: ("tiktok.com",),
    Platform.INSTAGRAM: ("instagram.com", "instagr.am"),
    Platform.FACEBOOK: ("facebook.com", "fb.com", "fb.watch"),
}

# Alias host yang merujuk layanan yang sama.
HOST_ALIASES = (("twitter.com", "x.com"), ("threads.net", "threads.com"))
STRIPPED_HOST_PREFIXES = ("www.", "m.", "mobile.")
TRACKING_PARAMS = frozenset(
    {"fbclid", "gclid", "igshid", "igsh", "si", "s", "t", "ref", "ref_src", "ref_url", "mibextid"}
)


def _in_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def normalize_target_url(platform: str, url: str) -> str:
    """Kembalikan bentuk kanonik URL, atau raise InvalidTargetURL."""
    url = (url or "").strip()
    if not url:
        raise InvalidTargetURL("URL target wajib diisi.")
    if len(url) > MAX_URL_LENGTH:
        raise InvalidTargetURL("URL target terlalu panjang.")
    if platform not in PLATFORM_DOMAINS:
        raise InvalidTargetURL("Platform tidak dikenal.")

    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidTargetURL("URL harus diawali http:// atau https://.")
    if parts.username is not None or parts.password is not None:
        raise InvalidTargetURL("URL tidak boleh memuat kredensial.")
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidTargetURL("Port pada URL tidak valid.") from exc
    if port not in (None, 80, 443):
        raise InvalidTargetURL("Port non-standar tidak diizinkan.")

    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise InvalidTargetURL("URL tidak memuat nama host.")
    if not any(_in_domain(host, d) for d in PLATFORM_DOMAINS[platform]):
        raise InvalidTargetURL("Domain URL tidak sesuai dengan platform yang dipilih.")

    for prefix in STRIPPED_HOST_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix) :]
    for old, new in HOST_ALIASES:
        if host == old:
            host = new
        elif host.endswith("." + old):
            host = host[: -len(old)] + new

    path = parts.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))
