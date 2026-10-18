"""Mutasi pemindai rahasia (WP-3.6)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

# Dijalankan di host (butuh git untuk tes mode git), memakai venv repo asli; salinan slot tak punya .venv.
COMMAND = 'DJANGO_SECRET_KEY=x {origin}/backend/.venv/bin/python -m pytest -c pyproject.toml -q -x -p no:cacheprovider ../tests/test_secret_scan.py'
BASELINE_COMMAND = COMMAND
CWD = '{root}/backend'
TIMEOUT = 300
T = 600
T = 'tests/tools/secret_scan.py'

MUTATIONS = [
    Mutation('batas panjang nilai terlalu besar', T, 'VALUE = r"[A-Za-z0-9._~+/=%-]{16,}"', 'VALUE = r"[A-Za-z0-9._~+/=%-]{40,}"'),
    Mutation('batas panjang nilai terlalu kecil', T, 'VALUE = r"[A-Za-z0-9._~+/=%-]{16,}"', 'VALUE = r"[A-Za-z0-9._~+/=%-]{4,}"'),
    Mutation('nama sid tak dikenali', T, '(sessionid|csrftoken|auth_token|ct0|sid)', '(sessionid|csrftoken|auth_token|ct0)'),
    Mutation('nama ct0 tak dikenali', T, '(sessionid|csrftoken|auth_token|ct0|sid)', '(sessionid|csrftoken|auth_token|sid)'),
    Mutation('refresh_token tak dikenali', T, '(access_token|refresh_token|oauth_token|api[_-]?key|secret[_-]?key)', '(access_token|oauth_token|api[_-]?key|secret[_-]?key)'),
    Mutation('oauth_token tak dikenali', T, '(access_token|refresh_token|oauth_token|api[_-]?key|secret[_-]?key)', '(access_token|refresh_token|api[_-]?key|secret[_-]?key)'),
    Mutation('secret_key tak dikenali', T, '(access_token|refresh_token|oauth_token|api[_-]?key|secret[_-]?key)', '(access_token|refresh_token|oauth_token|api[_-]?key)'),
    Mutation('api_key tak dikenali', T, '(access_token|refresh_token|oauth_token|api[_-]?key|secret[_-]?key)', '(access_token|refresh_token|oauth_token|secret[_-]?key)'),
    Mutation('aturan kunci privat dihapus', T, '    ("kunci privat", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),\n', ''),
    Mutation('aturan kunci cloud dihapus', T, '    ("kunci cloud", re.compile(r"\\b(AKIA', '    ("kunci cloud", re.compile(r"\\b(NEVERAKIA'),
    Mutation('aturan bearer dihapus', T, '    ("bearer token", re.compile(rf"\\bbearer\\s+({VALUE})", re.I)),\n', ''),
    Mutation('aturan header cookie dihapus', T, '    ("header Set-Cookie/Cookie", ', '    ("header Set-Cookie/Cookie", re.compile(r"NEVERMATCH_ZZZ")),\n    ("header cookie lama", '),
    Mutation('dump cookie tak dideteksi', T, '    ("dump cookie JSON", re.compile(r"\\"cookies\\"\\s*:\\s*\\[\\s*\\{")),\n', ''),
    Mutation('penampung tak pernah diabaikan', T, '            if kind not in ("kunci privat", "dump cookie JSON", "kunci cloud") and PLACEHOLDER.search(secret):', '            if False:'),
    Mutation('penampung berlaku juga untuk kunci privat', T, '            if kind not in ("kunci privat", "dump cookie JSON", "kunci cloud") and PLACEHOLDER.search(secret):', '            if PLACEHOLDER.search(secret):'),
    Mutation('penampung berlaku untuk kunci cloud', T, '("kunci privat", "dump cookie JSON", "kunci cloud")', '("kunci privat", "dump cookie JSON")'),
    Mutation('tanda allow diabaikan', T, '        if ALLOW_MARK in line:\n            continue\n', ''),
    Mutation('tanda allow membungkam semua baris', T, '        if ALLOW_MARK in line:\n            continue\n', '        if ALLOW_MARK in text:\n            continue\n'),
    Mutation('berkas biner dipindai', T, '    if b"\\0" in data[:4096]:\n        return []\n', ''),
    Mutation('berkas besar dipindai', T, '    if path.stat().st_size > MAX_BYTES:\n        return []\n', ''),
    Mutation('lockfile dipindai', T, 'SKIP_NAMES = {"package-lock.json", "uv.lock"}', 'SKIP_NAMES = set()'),
    Mutation('batas ukuran salah arah', T, 'if path.stat().st_size > MAX_BYTES:', 'if path.stat().st_size >= 0:'),
    Mutation('nama cookies tak dilarang', T, '    re.compile(r"(^|/)cookies[^/]*\\.(txt|json)$", re.I),\n', ''),
    Mutation('nama storage_state tak dilarang', T, '    re.compile(r"(^|/)storage_state[^/]*\\.json$", re.I),\n', ''),
    Mutation('ekstensi har/pem tak dilarang', T, '    re.compile(r"\\.(har|pem|key|p12)$", re.I),\n', ''),
    Mutation('.env tak dilarang', T, '    re.compile(r"(^|/)\\.env($|\\.(?!example$))", re.I),\n', ''),
    Mutation('.env.example ikut dilarang', T, '(^|/)\\.env($|\\.(?!example$))', '(^|/)\\.env($|\\.)'),
    Mutation('nama berkas tak diperiksa pada mode git', T, '            if not argv:\n                findings += scan_name(display)\n', ''),
    Mutation('nama berkas diperiksa pada mode jalur', T, '            if not argv:\n                findings += scan_name(display)\n', '            findings += scan_name(display)\n'),
    Mutation('kode keluar tak mencerminkan temuan', T, '    return 1 if findings else 0', '    return 0'),
    Mutation('mode stdin tak memindai', T, '        findings = scan_text("<stdin>", sys.stdin.read())', '        findings = []'),
    Mutation('direktori tak dipindai rekursif', T, 'sorted(q for q in p.rglob("*") if q.is_file())', 'sorted(q for q in p.glob("*") if q.is_file())'),
]
