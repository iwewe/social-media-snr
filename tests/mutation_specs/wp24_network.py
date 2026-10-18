"""Mutasi inti jaringan M4 (WP-2.4). Murni, tanpa basis data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m4_network.py'
CWD = '{origin}'
TIMEOUT = 300
N = 'backend/intelligence/m4/network.py'
S = 'backend/intelligence/m4/stability.py'

MUTATIONS = [
    Mutation('jenis relasi tak terpilih tidak dikecualikan', N, '        if record.relation_type not in params.relation_types:', '        if False:'),
    Mutation('aktor tak dikenal membentuk edge', N, '        if record.from_actor is None or record.to_actor is None:', '        if False:'),
    Mutation('interaksi diri sendiri menjadi edge', N, '        if record.from_actor == record.to_actor:', '        if False:'),
    Mutation('batas awal jendela eksklusif', N, 'if params.window_start <= record.published_at < params.window_end:', 'if params.window_start < record.published_at < params.window_end:'),
    Mutation('batas akhir jendela inklusif', N, 'if params.window_start <= record.published_at < params.window_end:', 'if params.window_start <= record.published_at <= params.window_end:'),
    Mutation('waktu tak diketahui selalu masuk', N, 'return None if params.unknown_time == "include" else "unknown_time_excluded"', 'return None'),
    Mutation('bobot hitung salah', N, 'weight=len(observation_ids) if params.weighting == "count" else 1,', 'weight=len(group) if params.weighting == "count" else 1,'),
    Mutation('bobot biner diabaikan', N, 'weight=len(observation_ids) if params.weighting == "count" else 1,', 'weight=len(observation_ids),'),
    Mutation('stance edge hilang', N, 'sorted(Counter(r.stance or NOT_ASSESSED for r in group).items())', 'sorted(Counter(NOT_ASSESSED for r in group).items())'),
    Mutation('ringkasan: MIXED hilang', N, '    if pro and contra:\n        return "MIXED"', '    if pro and contra:\n        return "PRO"'),
    Mutation('urutan label komunitas tidak deterministik', N, 'key=lambda g: g[0])', 'key=lambda g: -g[0])'),
    Mutation('graf besar tidak dilewati', N, '    if len(nodes) > params.metrics_max_nodes:', '    if False:'),
    Mutation('betweenness selalu dihitung', N, '        if params.compute_betweenness:', '        if True:'),
    Mutation('stabilitas selalu dihitung', N, '        if params.stability_seeds:', '        if True:'),
    Mutation('seed stabilitas sama', N, '[params.seed + i for i in range(params.stability_seeds)]', '[params.seed for i in range(params.stability_seeds)]'),
    Mutation('modularitas tanpa edge dihitung', N, '            if weights\n', '            if True\n'),
    Mutation('partisi berbeda dianggap sama', S, '    agree = sum((a[x] == a[y]) == (b[x] == b[y]) for x, y in pairs)', '    agree = len(pairs)'),
    Mutation('pasangan kosong bukan 1.0', S, '    if not pairs:\n        return 1.0', '    if not pairs:\n        return 0.0'),
    Mutation('node berbeda diterima', S, '    if set(a) != set(b):', '    if False:'),
    Mutation('satu seed diterima', S, '    if len(seeds) < 2:', '    if False:'),
    Mutation('rand minimum salah', S, '"min_rand_index_vs_first": round(min(rands), 6),', '"min_rand_index_vs_first": round(max(rands), 6),'),
    Mutation('partisi berbeda dihitung satu', S, '"distinct_partitions": len(distinct),', '"distinct_partitions": 1,'),
]
