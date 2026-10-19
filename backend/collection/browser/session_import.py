"""Impor sesi operator ke profil browser (keputusan organisasi 2026-10-19; PRD bagian 13).

Cookies adalah KREDENSIAL RAHASIA: modul ini tidak pernah mencetak, melog, atau menyertakan
NILAI cookie dalam pesan galat atau ringkasan; hanya nama, jumlah, dan tanggal kedaluwarsa.
Hanya cookie milik domain platform yang dipilih yang diterima (berkas ekspor browser sering
memuat situs lain). Tujuan penulisan hanya profil di `browser-profiles/`, tidak pernah evidence
atau Git. Impor TIDAK memeriksa kebolehan memakai sesi itu.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from investigations.enums import Platform
from investigations.target_urls import PLATFORM_DOMAINS

from .runtime import BrowserSession, prepare_profile_dir

SAME_SITE = {
    "no_restriction": "None",
    "none": "None",
    "lax": "Lax",
    "strict": "Strict",
}


class SessionImportError(ValueError):
    """Galat impor; pesan TIDAK memuat nilai cookie."""


@dataclass(frozen=True)
class Summary:
    accepted: int
    rejected_foreign_domain: int
    names: tuple[str, ...]
    earliest_expiry: datetime | None  # None bila semua cookie sesi (tanpa kedaluwarsa)


def _domain_ok(domain: str, platform: str) -> bool:
    host = domain.lstrip(".").lower()
    return any(host == d or host.endswith("." + d) for d in PLATFORM_DOMAINS[platform])


def _expires(item: dict[str, Any]) -> float | None:
    for key in ("expires", "expirationDate"):
        value = item.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int | float):
            return None if value <= 0 else float(value)
    return None


def _one(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SessionImportError(f"cookie[{index}] bukan objek")
    name, value, domain = item.get("name"), item.get("value"), item.get("domain")
    if not isinstance(name, str) or not name or not isinstance(value, str) or not value:
        raise SessionImportError(f"cookie[{index}]: name dan value wajib string tidak kosong")
    if not isinstance(domain, str) or not domain:
        raise SessionImportError(f"cookie[{index}] ({name}): domain wajib")
    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": item.get("path") if isinstance(item.get("path"), str) and item["path"] else "/",
        "secure": bool(item.get("secure", False)),
        "httpOnly": bool(item.get("httpOnly", item.get("http_only", False))),
    }
    expires = _expires(item)
    if expires is not None:
        cookie["expires"] = expires
    same_site = item.get("sameSite")
    if isinstance(same_site, str) and same_site.lower() in SAME_SITE:
        cookie["sameSite"] = SAME_SITE[same_site.lower()]
    return cookie


def parse_cookies(
    raw: Any,
    platform: str,
    *,
    session_days: int | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Kembalikan (cookie platform yang diterima, jumlah cookie domain asing yang dibuang).

    Menerima `storage_state` Playwright (`{"cookies": [...]}`) atau daftar hasil ekspor
    ekstensi browser.

    Cookie SESI (tanpa kedaluwarsa) tidak disimpan Chromium saat browser ditutup. Bila
    `session_days` diisi, cookie semacam itu diberi kedaluwarsa `now + session_days` agar bertahan
    di profil; ini keputusan operator yang eksplisit (dilaporkan), bukan perpanjangan diam-diam."""
    if platform not in PLATFORM_DOMAINS:
        raise SessionImportError("platform tidak dikenal")
    items = raw.get("cookies") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        raise SessionImportError("berkas harus berisi daftar cookie tidak kosong")
    kept: list[dict[str, Any]] = []
    foreign = 0
    for index, item in enumerate(items):
        cookie = _one(item, index)
        if _domain_ok(cookie["domain"], platform):
            if session_days and "expires" not in cookie:
                cookie["expires"] = (now or datetime.now(UTC)).timestamp() + session_days * 86400
            kept.append(cookie)
        else:
            foreign += 1
    if not kept:
        raise SessionImportError(
            f"tidak ada cookie untuk domain {platform}; tidak ada yang diimpor"
        )
    return kept, foreign


def summarize(cookies: list[dict[str, Any]], foreign: int) -> Summary:
    expiries = [c["expires"] for c in cookies if "expires" in c]
    earliest = datetime.fromtimestamp(min(expiries), UTC) if expiries else None
    return Summary(len(cookies), foreign, tuple(sorted({c["name"] for c in cookies})), earliest)


def load_cookie_file(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Posisi saja; jangan menyalin potongan isi ke pesan.
        raise SessionImportError(
            f"bukan JSON yang sah (baris {exc.lineno}, kolom {exc.colno})"
        ) from None


def import_session(platform: str, cookies: list[dict[str, Any]]) -> Path:
    """Tulis cookie ke profil `<akar profil>/<platform>` (profil dibuat 0700)."""
    profile = prepare_profile_dir(Platform(platform).value)
    with BrowserSession(profile_dir=profile) as session:
        session.context.add_cookies(cookies)  # type: ignore[arg-type]
    return profile


def read_session_summary(platform: str) -> Summary:
    """Ringkasan cookie platform pada profil (nama dan kedaluwarsa saja)."""
    profile = prepare_profile_dir(Platform(platform).value)
    with BrowserSession(profile_dir=profile) as session:
        stored = [c for c in session.context.cookies() if _domain_ok(c.get("domain", ""), platform)]
    cookies = [dict(c) for c in stored]
    return summarize(cookies, 0) if cookies else Summary(0, 0, (), None)
