"""Mutasi lapisan basis data jaringan M4 (WP-2.4)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m4_run.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
F = 'backend/intelligence/networks.py'

MUTATIONS = [
    Mutation('hash penilaian tidak diperiksa', F, '    if digest_ids(pk for pk, _, _ in rows) != digest:', '    if False:'),
    Mutation('sumber bukan M2 lolos', F, '        or not source.method.startswith("m2-")\n', ''),
    Mutation('sumber belum selesai lolos', F, '        or source.status != AnalysisStatus.COMPLETED\n', ''),
    Mutation('sumber di dataset lain lolos', F, '        or source.dataset_version_id != run.dataset_version_id\n', ''),
    Mutation('akun platform lain lolos (penulis)', F, '    if author_ids - platform_ok:', '    if False:', equivalent='tak terjangkau: trigger anggota dataset menjamin satu platform; pelindung berlapis, trigger node diuji terpisah'),
    Mutation('akun platform lain lolos (simpul)', F, '    if unknown_actors.exists():', '    if False:', equivalent='tak terjangkau: simpul berasal dari penulis dataset satu platform; trigger node diuji terpisah'),
    Mutation('relasi di luar dataset tak dicatat', F, '    if outside_dataset:', '    if False:', equivalent='tak terjangkau: relasi hanya dibaca dari run dataset dan selalu berasal dari post yang diobservasi'),
    Mutation('stance tidak masuk edge', F, '                stance=stance_by_obs.get(origin["id"]),', '                stance=None,'),
    Mutation('stance tidak masuk node', F, '        if stance_view:', '        if False:'),
    Mutation('stance node dihitung dari semua observasi', F, '        if o["author_id"] is not None and o["id"] in stance_by_obs:', '        if o["author_id"] is not None:'),
    Mutation('induk tak dicari lintas run', F, ' or latest_by_post.get(', ' or {}.get('),
    Mutation('mention tidak memakai akun dituju', F, '        if rel["to_actor_id"] is not None:', '        if False:'),
    Mutation('asal relasi di luar dataset diterima', F, '        if origin is None:', '        if False:', equivalent='tak terjangkau: lihat mutasi "relasi di luar dataset tak dicatat"'),
    Mutation('akhir jendela tidak setelah awal', F, '    if end <= start:', '    if False:'),
    Mutation('jenis relasi duplikat diterima', F, '        or len(set(types)) != len(types)\n', ''),
    Mutation('resolusi tak dibatasi', F, '        or not 0.1 <= resolution <= 10\n', ''),
    Mutation('seed negatif diterima', F, 'or not 0 <= seed < 2**31:', 'or False:'),
    Mutation('stabilitas 1 seed diterima', F, '        or not (stability == 0 or 2 <= stability <= 100)', '        or False'),
    Mutation('parameter stance sebagian diterima', F, '    if any(v is None for v in stance_keys) and not all(v is None for v in stance_keys):', '    if False:'),
    Mutation('stance_view selalu benar', F, '        "stance_view": stance_view,\n        "stance_rule"', '        "stance_view": True,\n        "stance_rule"'),
]
