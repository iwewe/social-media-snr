"""Mutasi lapisan basis data profil M3 (WP-2.3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m3_run.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
F = 'backend/intelligence/profiles.py'

MUTATIONS = [
    Mutation('hash penilaian tidak diperiksa', F, 'if digest_ids(a.pk for a in assessments) != expected_digest:', 'if False:'),
    Mutation('run sumber bukan M2 lolos', F, '        or not source.method.startswith("m2-")\n', ''),
    Mutation('run sumber belum selesai lolos', F, '        or source.status != AnalysisStatus.COMPLETED\n', ''),
    Mutation('run sumber di dataset lain lolos', F, '        or source.dataset_version_id != run.dataset_version_id\n', ''),
    Mutation('respons tanpa akun diprofilkan', F, '        if o.author_id is None:', '        if False:'),
    Mutation('periode tidak disaring', F, '        if o.published_at is not None and not (', '        if False and o.published_at is not None and not ('),
    Mutation('cakupan sebagian selalu salah', F, '"partial_coverage": sorted(target_ids) != all_targets,', '"partial_coverage": False,'),
    Mutation('target investigasi tidak dihitung', F, 'investigation_id=run.investigation_id, platform=dataset.platform', 'investigation_id=run.investigation_id, platform=dataset.platform, pk__in=target_ids'),
    Mutation('pemeriksaan tak lengkap tak dicatat', F, 'incomplete = sorted((r.pk, r.status) for r in runs if r.status != "COMPLETED")', 'incomplete = []'),
    Mutation('induk tidak dilacak', F, 'parent_post_id=index.parent_post_id(o.pk),', 'parent_post_id=None,'),
    Mutation('pernyataan cakupan dibuang', F, '        coverage["statement"] = _statement(coverage)\n', '        coverage["statement"] = "x"\n'),
    Mutation('batas bucket tidak divalidasi', F, 'bucket_hours=_int(parameters, "bucket_hours", 1, 720),', 'bucket_hours=_int(parameters, "bucket_hours", 0, 720),'),
    Mutation('min_responses minimal 1 dilonggarkan', F, 'min_responses=_int(parameters, "min_responses", 1, 10_000),', 'min_responses=_int(parameters, "min_responses", 0, 10_000),'),
    Mutation('akhir periode tidak setelah awal', F, '    if params.period_end <= params.period_start:', '    if False:'),
    Mutation('zona waktu tidak wajib', F, '    if value.tzinfo is None:', '    if False:'),
]
