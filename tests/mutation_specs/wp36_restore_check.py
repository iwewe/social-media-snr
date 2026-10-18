"""Mutasi pemeriksaan restore (WP-3.6)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_restore_check.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 600
R = 'backend/preservation/restore_check.py'
C = 'backend/preservation/management/commands/restore_check.py'

MUTATIONS = [
    Mutation('app audit tak dihitung', R, 'DOMAIN_APPS = frozenset({"investigations", "collection", "preservation", "intelligence", "audit"})', 'DOMAIN_APPS = frozenset({"investigations", "collection", "preservation", "intelligence"})'),
    Mutation('app preservation tak dihitung', R, 'DOMAIN_APPS = frozenset({"investigations", "collection", "preservation", "intelligence", "audit"})', 'DOMAIN_APPS = frozenset({"investigations", "collection", "intelligence", "audit"})'),
    Mutation('pengguna tak dihitung', R, 'EXTRA_MODELS = frozenset({"auth.User", "auth.Group"})', 'EXTRA_MODELS = frozenset({"auth.Group"})'),
    Mutation('ukuran tak masuk katalog', R, 'digest.update(f"{path}\\0{sha}\\0{size}\\n".encode())', 'digest.update(f"{path}\\0{sha}\\n".encode())'),
    Mutation('hash tak masuk katalog', R, 'digest.update(f"{path}\\0{sha}\\0{size}\\n".encode())', 'digest.update(f"{path}\\0{size}\\n".encode())'),
    Mutation('jalur tak masuk katalog', R, 'digest.update(f"{path}\\0{sha}\\0{size}\\n".encode())', 'digest.update(f"{sha}\\0{size}\\n".encode())'),
    Mutation('katalog tergantung urutan', R, '    for path, sha, size in sorted(rows):', '    for path, sha, size in rows:'),
    Mutation('jumlah baris tak dibandingkan', R, '        if want != have:\n            problems.append(f"jumlah baris', '        if False:\n            problems.append(f"jumlah baris'),
    Mutation('label hanya di sumber diabaikan', R, 'for label in sorted(set(expected["counts"]) | set(now["counts"])):', 'for label in sorted(set(expected["counts"]) & set(now["counts"])):'),
    Mutation('label hanya di hasil diabaikan', R, 'for label in sorted(set(expected["counts"]) | set(now["counts"])):', 'for label in sorted(set(expected["counts"])):'),
    Mutation('katalog tak dibandingkan', R, '    if expected["artifacts"]["catalog_sha256"] != now["artifacts"]["catalog_sha256"]:', '    if False:'),
    Mutation('berkas tak diperiksa ulang', R, '        if inspection.result != VerificationResult.MATCH:\n            problems.append(f"artefak', '        if False:\n            problems.append(f"artefak'),
    Mutation('berkas tak dihitung', R, '        checked += 1\n', ''),
    Mutation('format tak dikenal diterima', R, '    if expected.get("format") != FORMAT:', '    if False:'),
    Mutation('berkas tak tercatat jadi kegagalan', R, '        warnings.append(\n            f"{len(orphans)} berkas', '        problems.append(\n            f"{len(orphans)} berkas'),
    Mutation('berkas tak tercatat diabaikan', R, '    if orphans:\n', '    if False:\n'),
    Mutation('hasil selalu ok', R, '        "ok": not problems,', '        "ok": True,'),
    Mutation('perintah tak gagal saat masalah', C, '            raise CommandError(f"restore tidak lolos: {len(result[\'problems\'])} masalah")', '            return'),
    Mutation('peringatan tak dicetak', C, '            self.stdout.write(f"PERINGATAN: {warning}")', '            pass'),
]
