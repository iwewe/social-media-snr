"""Mutasi lapisan basis data indikator koordinasi (WP-2.5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_co_run.py -k "not synthetic"'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
F = 'backend/intelligence/coordination_runs.py'

MUTATIONS = [
    Mutation('satu Post bukan satu respons', F, '        latest[row["post_id"]] = row  # satu Post = satu respons: observasi terbarunya', '        latest[(row["post_id"], row["id"])] = row'),
    Mutation('observasi lama menggantikan yang baru', F, 'sorted(rows, key=lambda r: (r["run__sequence"], r["id"]))', 'sorted(rows, key=lambda r: (-r["run__sequence"], r["id"]))'),
    Mutation('respons tanpa akun ikut', F, '        if row["author_id"] is None:', '        if False:'),
    Mutation('jendela waktu tidak disaring', F, '        if when is not None and not start <= when < end:', '        if False:'),
    Mutation('jendela: batas akhir inklusif', F, 'not start <= when < end:', 'not start <= when <= end:'),
    Mutation('induk balasan tidak dibaca', F, '"parent" if rel["relation_type"] == RelationType.REPLY_TO else "amplified"', '"amplified"'),
    Mutation('amplifikasi tidak dibaca', F, '"parent" if rel["relation_type"] == RelationType.REPLY_TO else "amplified"', '"parent"'),
    Mutation('akun platform lain lolos', F, '    if ActorAccount.objects.filter(pk__in=actors).exclude(platform=dataset.platform).exists():', '    if False:', equivalent='tak terjangkau: trigger dataset menjamin satu platform; trigger tepi diuji terpisah'),
    Mutation('akhir jendela tidak setelah awal', F, '    if end <= start:', '    if False:'),
    Mutation('ambang kemiripan tak dibatasi', F, '        or not 0 < threshold <= 1\n', ''),
    Mutation('frasa 1-2 kata diterima', F, 'not (phrase == 0 or 3 <= phrase <= 12)', 'False'),
    Mutation('permutasi kecil diterima', F, 'or not (permutations == 0 or 10 <= permutations <= 1000)', 'or False'),
    Mutation('stance masuk definisi', F, '"stance_used": False,', '"stance_used": True,'),
    Mutation('bukti tidak diteruskan', F, '                observation_ids=e.observation_ids,', '                observation_ids=[],'),
    Mutation('hipotesis alternatif tidak disimpan', F, '                alternative_hypotheses=e.alternative_hypotheses,', '                alternative_hypotheses=[],'),
    Mutation('baseline tidak disimpan di tepi', F, '                baseline=e.baseline,', '                baseline={},'),
    Mutation('pernyataan bukan-temuan hilang', F, '            "notice": NOTICE,\n            "alternative_hypotheses"', '            "notice": "",\n            "alternative_hypotheses"'),
]
