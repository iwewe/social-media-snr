"""Mutasi alat persiapan pilot (WP-4.1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_pilot.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
P = 'backend/intelligence/pilot.py'
C = 'backend/intelligence/management/commands/pilot_annotation_set.py'

MUTATIONS = [
    Mutation('strata diambil berurutan, bukan bergilir', P, '        for name in list(pools):\n            if pools[name] and len(chosen) < n:\n                chosen.append(pools[name].pop())', '        name = next(k for k, v in pools.items() if v)\n        while pools[name] and len(chosen) < n:\n            chosen.append(pools[name].pop())'),
    Mutation('benih tak berpengaruh', P, '    for ids in pools.values():\n        rng.shuffle(ids)\n', ''),
    Mutation('hasil tak terurut', P, '    return sorted(chosen)', '    return chosen'),
    Mutation('prediksi memakai label hasil koreksi', P, '    origin = assessment_history(assessment)[0]  # hasil mesin asli, bukan koreksi manusia', '    origin = assessment'),
    Mutation('tag nested terlalu longgar', P, '    if depth >= 2:', '    if depth >= 1:'),
    Mutation('tag no_parent salah', P, '    if depth == 0 and not parent_unknown:', '    if depth == 0:'),
    Mutation('tag machine_flagged hilang', P, '    if machine_flagged:\n        tags.append("machine_flagged")', '    pass'),
    Mutation('tag teks pendek hilang', P, '    if text is None or len(text.strip()) < SHORT_TEXT_CHARS:', '    if False:'),
    Mutation('tag teks pendek tanpa pangkas', P, 'len(text.strip()) < SHORT_TEXT_CHARS', 'len(text) < SHORT_TEXT_CHARS'),
    Mutation('tag teks pendek batas salah', P, 'len(text.strip()) < SHORT_TEXT_CHARS', 'len(text.strip()) <= SHORT_TEXT_CHARS'),
    Mutation('batas ukuran pilot salah', P, '    return count < MIN_PILOT_ITEMS', '    return count <= MIN_PILOT_ITEMS'),
    Mutation('label penilai terisi dari mesin', P, '                        "issue_stance": None,', '                        "issue_stance": "UNDETERMINED",'),
    Mutation('run non-M2 diterima', P, '    if not run.method.startswith("m2-"):', '    if False:'),
    Mutation('penilai ganda diterima', P, '    if len(annotators) < 1 or len(set(annotators)) != len(annotators):', '    if len(annotators) < 1:'),
    Mutation('teks tak diekspor', P, '                "text": text,', '                "text": None,'),
    Mutation('rantai induk tak diekspor', P, '                "parent_chain": [p.text for p in chain.parents],', '                "parent_chain": [],'),
    Mutation('metrik: paginasi tak lengkap tak dihitung', P, '        if coverage.get("pagination_complete") is False:', '        if False:'),
    Mutation('metrik: gagal parser tak dihitung', P, '        if "PARSE_FAILED" in codes:', '        if False:'),
    Mutation('metrik: tak didukung tak dihitung', P, '        if "UNSUPPORTED" in codes:', '        if False:'),
    Mutation('metrik: rasio dibulatkan salah', P, 'round(p["observed"] / p["displayed"], 4)', 'round(p["displayed"] / p["observed"], 4)'),
    Mutation('metrik: rasio selalu ada', P, '            None if not p["displayed"] else round', '            0 if not p["displayed"] else round'),
    Mutation('metrik: hanya run dengan kedua hitungan', P, '        if displayed is not None and observed is not None:', '        if True:'),
    Mutation('perintah: izin berkas longgar', C, '            path.chmod(0o600)', '            pass'),
    Mutation('perintah: izin direktori longgar', C, '        out.chmod(0o700)', '        pass'),
    Mutation('perintah: run belum selesai diterima', C, '            AnalysisRun.objects.filter(pk=options["run"], status="COMPLETED")', '            AnalysisRun.objects.filter(pk=options["run"])'),
]
