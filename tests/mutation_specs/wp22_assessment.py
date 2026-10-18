"""Mutasi lapisan basis data M2 (WP-2.2): penilaian, rantai percakapan, tinjauan."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m2_assessment.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
A = 'backend/intelligence/assessment.py'
C = 'backend/intelligence/conversation.py'

MUTATIONS = [
    Mutation('stance awal target tidak dipakai', A, 'stance = initial.get((target_id, proposition_id)) if target_id else None', 'stance = None'),
    Mutation('stance induk tidak diteruskan', A, '            computed[(proposition_id, node.observation_id)] = result.issue_stance\n', ''),
    Mutation('anak dinilai sebelum induk', A, 'key=lambda n: (chains[n.observation_id].depth, n.observation_id)', 'key=lambda n: (-chains[n.observation_id].depth, n.observation_id)'),
    Mutation('posting target ikut dinilai', A, 'RESPONSE_TYPES = ("reply", "comment", "quote")', 'RESPONSE_TYPES = ("reply", "comment", "quote", "post")'),
    Mutation('bukti: parent_unknown hilang', A, '"parent_unknown": chain.parent_unknown,', '"parent_unknown": False,'),
    Mutation('bukti: rantai induk hilang', A, '"parent_observation_ids": [p.observation_id for p in chain.parents],', '"parent_observation_ids": [],'),
    Mutation('tinjauan tanpa alasan', A, '    if not reason:\n', '    if False:\n'),
    Mutation('tinjauan tanpa perubahan', A, '    if not changed:\n', '    if False:\n'),
    Mutation('tinjauan pada run belum selesai', A, 'if assessment.analysis_run.status != AnalysisStatus.COMPLETED:', 'if False:'),
    Mutation('tinjauan tetap menandai perlu tinjauan', A, '                needs_human_review=False,\n                basis={', '                needs_human_review=True,\n                basis={'),
    Mutation('rujukan bukti tidak terbawa', A, '"evidence": evidence,', '"evidence": None,'),
    Mutation('karakter kosong diterima', A, '        if not response_character:\n', '        if False:\n'),
    Mutation('peninjau tidak dicatat', A, 'reviewed_by=by,', 'reviewed_by=None,'),
    Mutation('induk dari run lain', C, '        same_run = [c for c in candidates if c.run_id == node.run_id]', '        same_run = []'),
    Mutation('lingkaran tidak dihentikan', C, 'if parent.post_id in seen:', 'if False:'),
    Mutation('tinjauan terlalu longgar: versi lama bisa ditinjau', A, 'if hasattr(assessment, "superseded_by"):', 'if False:', equivalent='IntegrityError dari unique supersedes menghasilkan AlreadyReviewed yang sama'),
]
