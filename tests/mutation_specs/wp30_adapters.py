"""Mutasi adapter platform yang dinonaktifkan (WP-3.0 s.d. 3.5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/docs:/docs:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_platform_adapters.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 600
P = 'backend/collection/adapters/pending.py'
I = 'backend/collection/adapters/__init__.py'
X = 'backend/collection/adapters/x/__init__.py'
T = 'backend/collection/adapters/tiktok/__init__.py'
F = 'backend/collection/adapters/facebook/__init__.py'
G = 'backend/collection/adapters/instagram/__init__.py'
H = 'backend/collection/adapters/threads/__init__.py'

MUTATIONS = [
    Mutation('status kemampuan SUPPORTED', P, 'CapabilityDeclaration(CapabilityStatus.UNTESTED, reason)', 'CapabilityDeclaration(CapabilityStatus.SUPPORTED, reason)'),
    Mutation('status kemampuan LIMITED', P, 'CapabilityDeclaration(CapabilityStatus.UNTESTED, reason)', 'CapabilityDeclaration(CapabilityStatus.LIMITED, reason)'),
    Mutation('alasan tanpa dokumen', P, 'f"organisasi dan akses yang sah ({cls.feasibility_doc})"', '"organisasi dan akses yang sah"'),
    Mutation('collect berjalan', P, '        raise ContractViolation(\n            f"adapter {self.platform.value} dinonaktifkan; "', '        return None  # type: ignore[return-value]\n        raise ContractViolation(\n            f"adapter {self.platform.value} dinonaktifkan; "'),
    Mutation('URL tak dinormalisasi', P, '        normalized = normalize_target_url(self.platform, url)  # raise InvalidTargetURL', '        normalized = url.strip()'),
    Mutation('akun cadangan tak diperiksa', P, '            if pattern.target_type is TargetType.ACCOUNT and (', '            if False and ('),
    Mutation('host pendek tak dibatasi', P, '            if host in self.short_hosts:\n                if pattern.hosts is None or host not in pattern.hosts:\n                    continue', '            if host in self.short_hosts:\n                pass'),
    Mutation('pola pendek berlaku di host utama', P, '            elif pattern.hosts is not None:\n                continue', '            elif False:\n                continue'),
    Mutation('ID stabil selalu diambil', P, 'external_id = match.groupdict().get("id") if pattern.stable_id else None', 'external_id = match.groupdict().get("id")', equivalent='setara pada pola saat ini: hanya pola dengan stable_id=True yang punya grup `id`; penjaga cadangan bila pola baru ditambah'),
    Mutation('query diabaikan', P, '        subject = parts.path + (f"?{parts.query}" if parts.query else "")', '        subject = parts.path'),
    Mutation('pencocokan sebagian', P, 'match = pattern.regex.fullmatch(subject)', 'match = pattern.regex.match(subject)'),
    Mutation('platform tak didaftarkan', I, '        if adapter.platform.value not in registry.platforms():\n            registry.register(adapter.platform, adapter)\n            added.append(adapter.platform.value)', '        pass'),
    Mutation('adapter menimpa yang ada', I, '        if adapter.platform.value not in registry.platforms():', '        if True:'),
    Mutation('X: panjang handle tak dibatasi', X, '(?P<name>[A-Za-z0-9_]{1,15})', '(?P<name>[A-Za-z0-9_]{1,150})'),
    Mutation('X: ID posting bukan angka', X, '/status/(?P<id>\\d{1,25})', '/status/(?P<id>[A-Za-z0-9]{1,25})'),
    Mutation('X: ID tak dijadikan stabil', X, 'stable_id=True,\n        ),\n        # Handle', 'stable_id=False,\n        ),\n        # Handle'),
    Mutation('X: home dicadangkan hilang', X, '            "home",\n', ''),
    Mutation('TikTok: ID video tak stabil', T, 'stable_id=True,', 'stable_id=False,'),
    Mutation('TikTok: host pendek vt hilang', T, 'short_hosts = frozenset({"vm.tiktok.com", "vt.tiktok.com"})', 'short_hosts = frozenset({"vm.tiktok.com"})'),
    Mutation('Instagram: reserved explore hilang', G, '            "explore",\n', ''),
    Mutation('Instagram: kode terlalu pendek diterima', G, '(?P<code>[A-Za-z0-9_-]{5,20})', '(?P<code>[A-Za-z0-9_-]{1,20})'),
    Mutation('Threads: akun tanpa @ diterima', H, 'r"/@(?P<name>[A-Za-z0-9._]{1,30})"', 'r"/@?(?P<name>[A-Za-z0-9._]{1,30})"'),
    Mutation('Facebook: fb.watch tak dibatasi host', F, ', hosts=("fb.watch",)', ''),
    Mutation('Facebook: login bukan akun', F, '            "login",\n', ''),
    Mutation('Facebook: permalink tanpa id halaman', F, 'r"/permalink\\.php\\?id=\\d{1,25}&story_fbid=', 'r"/permalink\\.php\\?(?:id=\\d{1,25}&)?story_fbid='),
    Mutation('Facebook: tonton tanpa ID', F, 'r"/watch\\?v=\\d{5,25}"', 'r"/watch(?:\\?v=\\d{5,25})?"'),
]
