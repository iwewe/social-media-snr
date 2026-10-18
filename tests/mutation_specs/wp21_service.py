"""Mutasi layanan dan metode analisis I2 (WP-2.1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_analysis_runs.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
S = 'backend/intelligence/services.py'
M = 'backend/intelligence/methods.py'

MUTATIONS = [
    Mutation('run ganda lolos', S, 'if len({r.pk for r in run_list}) != len(run_list):', 'if False:'),
    Mutation('platform campur lolos', S, 'if len(platforms) != 1:', 'if False:'),
    Mutation('run belum di-ingest lolos', S, 'if not all(_ingested(r) for r in run_list):', 'if False:'),
    Mutation('investigasi lain lolos', S, 'if any(t.investigation_id != investigation.pk for t in targets.values()):', 'if False:'),
    Mutation('digest dataset salah', S, 'observation_digest=digest_ids(ids),', 'observation_digest=digest_ids(ids[:-1]),'),
    Mutation('dataset tidak disegel', S, 'sealed_at=timezone.now()\n        )\n    dataset.refresh_from_db()', 'sealed_at=None\n        )\n    dataset.refresh_from_db()'),
    Mutation('target dataset tidak tercatat', S, '"targets": sorted(targets),', '"targets": [],'),
    Mutation('parameter tidak divalidasi', S, '    spec.validate(parameters)\n', '    pass\n'),
    Mutation('peta konteks tak lengkap lolos', S, 'if set(target_context_versions) != set(dataset.selection["targets"]):', 'if False:'),
    Mutation('digest parameter salah', S, 'parameters_digest=digest_json(parameters),', 'parameters_digest=digest_json({}),'),
    Mutation('run dapat dijalankan dua kali', S, 'if not claimed:', 'if False:'),
    Mutation('digest keluaran salah', S, '"output_digest": digest_json(output),', '"output_digest": digest_json(run.parameters),'),
    Mutation('versi konteks issue tidak dibekukan', S, 'issue_version = run.issue_context_version.version if run.issue_context_version else None', 'issue_version = None'),
    Mutation('konteks issue terbaru salah ambil', S, 'return None if issue is None else issue.context_versions.order_by("-version").first()', 'return None if issue is None else issue.context_versions.order_by("version").first()'),
    Mutation('konteks target terbaru salah ambil', S, 'result[target.pk] = target.context_versions.order_by("-version").first()', 'result[target.pk] = target.context_versions.order_by("version").first()'),
    Mutation('analisis ulang tanpa data baru lolos', S, 'if digest_ids(current) == old.observation_digest:', 'if False:'),
    Mutation('analisis ulang kehilangan run sebelumnya', S, '        previous_run=previous,\n', '        previous_run=None,\n'),
    Mutation('analisis ulang memakai konteks terbaru diam-diam', S, '        issue_ctx = previous.issue_context_version\n', '        issue_ctx = latest_issue_context(previous.issue_context_version.issue if previous.issue_context_version else None)\n'),
    Mutation('seri penulis tidak deterministik', M, 'key=lambda kv: (-kv[1], kv[0])', 'key=lambda kv: (-kv[1], -kv[0])'),
    Mutation('penulis tak dikenal tidak dihitung', M, '"observations_without_author": sum(1 for _, a, _, _ in rows if a is None),', '"observations_without_author": 0,'),
    Mutation('jumlah post = jumlah observasi', M, '"posts": len({p for p, _, _, _ in rows}),', '"posts": len(rows),'),
    Mutation('jumlah run salah', M, '"runs": len({r for _, _, _, r in rows}),', '"runs": 1,'),
]
