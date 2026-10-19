"""Mutasi impor sesi operator (WP-3.1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_session_import.py'
COMMAND = _BASE
BASELINE_COMMAND = _BASE
CWD = '{origin}'
TIMEOUT = 600
S = 'backend/collection/browser/session_import.py'

MUTATIONS = [
    Mutation('domain tanpa titik pemisah', S, 'host.endswith("." + d)', 'host.endswith(d)'),
    Mutation('titik awal domain tak dipangkas', S, 'host = domain.lstrip(".").lower()', 'host = domain.lower()', equivalent='setara: ".x.com".endswith(".x.com") sudah benar; lstrip hanya merapikan'),
    Mutation('domain peka huruf besar', S, 'host = domain.lstrip(".").lower()', 'host = domain.lstrip(".")'),
    Mutation('cookie asing ikut diterima', S, '        if _domain_ok(cookie["domain"], platform):', '        if True:'),
    Mutation('tanpa cookie platform tetap diterima', S, '    if not kept:\n        raise SessionImportError', '    if False:\n        raise SessionImportError'),
    Mutation('jumlah asing tak dihitung', S, '        else:\n            foreign += 1', '        else:\n            pass'),
    Mutation('nama kosong diterima', S, 'if not isinstance(name, str) or not name or not isinstance(value, str) or not value:', 'if not isinstance(name, str) or not isinstance(value, str):'),
    Mutation('nilai kosong diterima', S, 'or not isinstance(value, str) or not value:', 'or not isinstance(value, str):'),
    Mutation('domain kosong diterima', S, 'if not isinstance(domain, str) or not domain:', 'if not isinstance(domain, str):'),
    Mutation('jalur bawaan salah', S, 'else "/",', 'else "",'),
    Mutation('secure selalu benar', S, '"secure": bool(item.get("secure", False)),', '"secure": True,'),
    Mutation('httpOnly diabaikan', S, '"httpOnly": bool(item.get("httpOnly", item.get("http_only", False))),', '"httpOnly": False,'),
    Mutation('http_only tak dikenal', S, 'item.get("httpOnly", item.get("http_only", False))', 'item.get("httpOnly", False)'),
    Mutation('expirationDate tak dikenal', S, 'for key in ("expires", "expirationDate"):', 'for key in ("expires",):'),
    Mutation('expires nol dianggap berlaku', S, 'return None if value <= 0 else float(value)', 'return None if value < 0 else float(value)'),
    Mutation('expires boolean diterima', S, 'if isinstance(value, bool) or value is None:', 'if value is None:'),
    Mutation('sameSite tak dipetakan', S, '        cookie["sameSite"] = SAME_SITE[same_site.lower()]', '        pass'),
    Mutation('no_restriction salah peta', S, '"no_restriction": "None",', '"no_restriction": "Lax",'),
    Mutation('umur sesi tak diterapkan', S, '            if session_days and "expires" not in cookie:', '            if False:'),
    Mutation('umur menimpa kedaluwarsa asli', S, '            if session_days and "expires" not in cookie:', '            if session_days:'),
    Mutation('umur dalam jam bukan hari', S, 'session_days * 86400', 'session_days * 3600'),
    Mutation('umur sesi nol tetap diterapkan', S, 'if session_days and "expires"', 'if session_days is not None and "expires"'),
    Mutation('kedaluwarsa paling awal jadi paling akhir', S, 'datetime.fromtimestamp(min(expiries), UTC)', 'datetime.fromtimestamp(max(expiries), UTC)'),
    Mutation('nama tak unik/terurut', S, 'tuple(sorted({c["name"] for c in cookies}))', 'tuple(c["name"] for c in cookies)'),
    Mutation('storage_state tak dikenal', S, 'items = raw.get("cookies") if isinstance(raw, dict) else raw', 'items = raw if isinstance(raw, list) else None'),
    Mutation('platform tak dikenal diterima', S, '    if platform not in PLATFORM_DOMAINS:\n        raise SessionImportError("platform tidak dikenal")\n', ''),
    Mutation('galat JSON memuat isi', S, 'bukan JSON yang sah (baris {exc.lineno}, kolom {exc.colno})', 'bukan JSON yang sah: {exc.doc[:40]}'),
]
