"""Mutasi izin berkas (WP-3.6b)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_data_permissions.py'
COMMAND = _BASE
BASELINE_COMMAND = _BASE
CWD = '{origin}'
TIMEOUT = 600
P = 'backend/preservation/permissions.py'
C = 'backend/preservation/management/commands/check_data_permissions.py'

MUTATIONS = [
    Mutation('bit other hanya baca', P, 'OTHER = stat.S_IRWXO', 'OTHER = stat.S_IROTH'),
    Mutation('bit grup/other hanya other', P, 'GROUP_OTHER = stat.S_IRWXG | stat.S_IRWXO', 'GROUP_OTHER = stat.S_IRWXO'),
    Mutation('bit grup/other hanya grup', P, 'GROUP_OTHER = stat.S_IRWXG | stat.S_IRWXO', 'GROUP_OTHER = stat.S_IRWXG'),
    Mutation('bit tulis pemilik diabaikan', P, 'WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH', 'WRITE = stat.S_IWGRP | stat.S_IWOTH'),
    Mutation('bit tulis grup diabaikan', P, 'WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH', 'WRITE = stat.S_IWUSR | stat.S_IWOTH'),
    Mutation('bit tulis other diabaikan', P, 'WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH', 'WRITE = stat.S_IWUSR | stat.S_IWGRP'),
    Mutation('akar evidence tak diperiksa', P, '    if _mode(root) & OTHER:\n        problems.append(f"akar evidence', '    if False:\n        problems.append(f"akar evidence'),
    Mutation('symlink evidence diizinkan', P, '        if path.is_symlink():\n            problems.append(f"evidence/{rel}: symlink', '        if False:\n            problems.append(f"evidence/{rel}: symlink'),
    Mutation('direktori evidence tak diperiksa', P, '            if mode & OTHER:\n                problems.append(f"evidence/{rel}/:', '            if False:\n                problems.append(f"evidence/{rel}/:'),
    Mutation('berkas bukti boleh ditulis', P, '            if mode & WRITE:\n', '            if False:\n'),
    Mutation('berkas bukti boleh diakses other', P, '            if mode & OTHER:\n                problems.append(f"evidence/{rel}: berkas bukti dapat diakses', '            if False:\n                problems.append(f"evidence/{rel}: berkas bukti dapat diakses'),
    Mutation('akar privat tak diperiksa', P, '    if _mode(root) & GROUP_OTHER:\n        problems.append(f"{label}: akar', '    if False:\n        problems.append(f"{label}: akar'),
    Mutation('isi privat tak diperiksa', P, '        elif _mode(path) & GROUP_OTHER:', '        elif False:'),
    Mutation('symlink privat diizinkan', P, '        if path.is_symlink():\n            problems.append(f"{label}/{rel}: symlink', '        if False:\n            problems.append(f"{label}/{rel}: symlink'),
    Mutation('akar tak ada dianggap masalah', P, '    if not root.exists():\n        return []\n    problems: list[str] = []\n    if _mode(root) & GROUP_OTHER', '    problems: list[str] = []\n    if _mode(root) & GROUP_OTHER'),
    Mutation('backup selalu diperiksa', P, '    if backup is not None:', '    if True:'),
    Mutation('backup tak pernah diperiksa', P, '    if backup is not None:', '    if False:'),
    Mutation('profil browser tak diperiksa', P, '    problems += check_private_tree(profiles, "browser-profiles")\n', ''),
    Mutation('perintah mengabaikan backup-dir', C, '            options["backup_dir"],\n', '            None,\n'),
    Mutation('perintah tidak gagal saat ada masalah', C, '            raise CommandError(f"izin berkas tidak sesuai kebijakan: {len(problems)} masalah")', '            pass'),
]
