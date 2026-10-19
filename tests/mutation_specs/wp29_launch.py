"""Mutasi memulai analisis dari API (WP-2.9)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_analysis_launch.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
L = 'backend/intelligence/launch.py'
V = 'backend/api/analysis_views.py'
T = 'backend/intelligence/tasks.py'

MUTATIONS = [
    Mutation('field tak diperiksa tepat', L, '    if set(data) != keys:', '    if False:'),
    Mutation('zona waktu tak diwajibkan', L, '    if value.tzinfo is None:\n        raise InvalidParameters(f"{key} wajib memuat zona waktu")', '    if False:\n        raise InvalidParameters(f"{key} wajib memuat zona waktu")', equivalent='setara: validator metode (profiles/networks/coordination_runs) menolak waktu tanpa zona dengan pesan identik saat run dibuat; pemeriksaan di sini hanya pagar ganda'),
    Mutation('cue kosong lolos', L, '    if not pro and not contra:', '    if False:'),
    Mutation('cue tak dipangkas', L, 'cues = list(dict.fromkeys(c.strip() for c in raw if c.strip()))', 'cues = list(dict.fromkeys(c for c in raw))'),
    Mutation('batas panjang cue hilang', L, 'any(len(c) > MAX_CUE_CHARS for c in cues)', 'False', equivalent='setara: validator M2 (example_parameters/validate_m2_parameters) menolak cue terlalu panjang; pemeriksaan di sini pagar ganda dengan pesan berbeda'),
    Mutation('proposition lintas investigasi', L, 'Proposition.objects.filter(pk=proposition_id, issue__investigation=investigation)', 'Proposition.objects.filter(pk=proposition_id)'),
    Mutation('proposition wajib dilonggarkan', L, '    if proposition_id is None:\n        raise InvalidParameters("proposition wajib untuk metode ini")', '    if False:\n        raise InvalidParameters("proposition wajib untuk metode ini")'),
    Mutation('run sumber lintas investigasi', L, 'AnalysisRun.objects.filter(pk=source_run_id, investigation=investigation).first()', 'AnalysisRun.objects.filter(pk=source_run_id).first()', equivalent='setara: pemeriksaan dataset yang sama (source.dataset_version_id == dataset.pk) sudah menjamin investigasi yang sama karena dataset milik satu investigasi'),
    Mutation('run sumber bukan M2 diterima', L, '        or not source.method.startswith("m2-")\n', ''),
    Mutation('run sumber belum selesai diterima', L, '        or source.status != AnalysisStatus.COMPLETED\n', ''),
    Mutation('run sumber dataset lain diterima', L, '        or source.dataset_version_id != dataset.pk\n', ''),
    Mutation('dataset investigasi lain diterima', L, '    if dataset.investigation_id != investigation.pk:', '    if False:'),
    Mutation('metode tak dikenal diterima', L, '    if method not in METHODS:', '    if False:'),
    Mutation('M4 setengah stance diterima', L, '        if (proposition_id is None) != (source_run_id is None):', '        if False:'),
    Mutation('antrean mati tak ditandai gagal', L, '        AnalysisRun.objects.filter(pk=run_pk, status=AnalysisStatus.PENDING).update(\n            status=AnalysisStatus.FAILED,', '        AnalysisRun.objects.filter(pk=-1, status=AnalysisStatus.PENDING).update(\n            status=AnalysisStatus.FAILED,'),
    Mutation('pesan antrean mati hilang', L, 'error="AntreanTidakTersedia: analisis tidak dikirim ke worker"', 'error=""'),
    Mutation('pengiriman ke antrean salah', L, 'queue="analysis"', 'queue="browser"'),
    Mutation('audit pembuatan hilang', L, '        _audit_creation(run, by)\n', ''),
    Mutation('audit analisis ulang tanpa asal', L, '        _audit_creation(run, by, reanalysis_of=previous)', '        _audit_creation(run, by)'),
    Mutation('tidak dikirim setelah commit (analisis baru)', L, '        _audit_creation(run, by)\n        transaction.on_commit(lambda: enqueue(run.pk))', '        _audit_creation(run, by)'),
    Mutation('tidak dikirim setelah commit (ulang)', L, '        _audit_creation(run, by, reanalysis_of=previous)\n        transaction.on_commit(lambda: enqueue(run.pk))', '        _audit_creation(run, by, reanalysis_of=previous)'),
    Mutation('konteks isu terbaru tak dibekukan', L, '            issue_context_version=services.latest_issue_context(\n                proposition.issue if proposition else None\n            ),', '            issue_context_version=None,'),
    Mutation('digest parameter tak diaudit', L, '"parameters_digest": run.parameters_digest,', '"parameters_digest": "",'),
    Mutation('tugas ganda dilaporkan ditangani', T, '        return {"run": run_pk, "handled": False, "status": current.status}', '        return {"run": run_pk, "handled": True, "status": current.status}'),
    Mutation('run hilang dianggap ditangani', T, '        return {"run": run_pk, "handled": False, "status": "MISSING"}', '        return {"run": run_pk, "handled": True, "status": "MISSING"}'),
    Mutation('peran mulai analisis turun ke pembaca', V, '        """Mulai analisis: parameter eksplisit, dijalankan worker (WP-2.9; ADR 0041)."""\n        inv = investigation_for(_user(request), pk, Role.MEMBER)', '        """Mulai analisis: parameter eksplisit, dijalankan worker (WP-2.9; ADR 0041)."""\n        inv = investigation_for(_user(request), pk, Role.VIEWER)'),
    Mutation('dataset lintas investigasi', V, 'DatasetVersion.objects.filter(pk=data["dataset_id"], investigation=inv).first()', 'DatasetVersion.objects.filter(pk=data["dataset_id"]).first()'),
    Mutation('pemeriksaan tak ditemukan hilang', V, '        if len(runs) != len(ids):', '        if False:'),
    Mutation('pemeriksaan lintas investigasi', V, 'InspectionRun.objects.filter(pk__in=ids, target__investigation=inv)', 'InspectionRun.objects.filter(pk__in=ids)'),
    Mutation('peran dataset baru turun ke pembaca', V, '        inv = investigation_for(_user(request), pk, Role.MEMBER)\n        data = _valid(DatasetCreateInput, request)', '        inv = investigation_for(_user(request), pk, Role.VIEWER)\n        data = _valid(DatasetCreateInput, request)'),
    Mutation('peran analisis ulang turun ke pembaca', V, 'previous = analysis_run_for(_user(request), pk, Role.MEMBER)', 'previous = analysis_run_for(_user(request), pk, Role.VIEWER)'),
    Mutation('analisis ulang abaikan konteks terbaru', V, 'use_latest_context=data["use_latest_context"],', 'use_latest_context=False,'),
]
