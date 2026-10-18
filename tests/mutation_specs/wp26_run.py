"""Mutasi lapisan basis data temuan (WP-2.6)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_findings.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
F = 'backend/intelligence/findings.py'

MUTATIONS = [
    Mutation('vonis tidak diperiksa', F, '            check_no_verdict(field, text)', '            pass'),
    Mutation('tanpa AnalysisRun diterima', F, '    if not runs:', '    if False:'),
    Mutation('run belum selesai/lain investigasi diterima', F, '        if run.investigation_id != investigation.pk or run.status != AnalysisStatus.COMPLETED:', '        if False:'),
    Mutation('platform campur diterima', F, '    if len(platforms) != 1:', '    if False:'),
    Mutation('indikator dari run lain diterima', F, '        if edge.network.analysis_run_id not in run_ids:', '        if False:'),
    Mutation('tanpa observasi diterima', F, '    if not obs_ids:', '    if False:'),
    Mutation('observasi di luar dataset diterima', F, '    if not obs_ids <= members:', '    if False:'),
    Mutation('kunci alternatif asing diterima', F, '    unknown = set(alternatives) - set(GENERAL_ALTERNATIVES)\n    if unknown:', '    unknown = set()\n    if unknown:'),
    Mutation('plafon confidence tidak ditegakkan', F, '    if not allowed:', '    if False:'),
    Mutation('data sintetis tidak dibatasi', F, 'synthetic=bool(evaluation["facts"]["synthetic"]),', 'synthetic=False,'),
    Mutation('kelompok bukti: yang terbesar dipakai', F, '    return min(counts)', '    return max(counts)'),
    Mutation('kelompok bukti: tanpa indikator dianggap cukup', F, '    if not edges:\n        return None', '    if not edges:\n        return 99'),
    Mutation('flag sintetis tidak disimpan', F, 'synthetic_data=evaluation["facts"]["synthetic"],', 'synthetic_data=False,'),
    Mutation('catatan bukan-vonis tidak disimpan', F, '                notice=NOTICE,', '                notice="-",'),
    Mutation('override_reason tidak disimpan', F, '"override_reason": str(evidence_ratings[axis].get("override_reason", "")).strip(),', '"override_reason": "",'),
    Mutation('saran sistem tidak disimpan', F, '            "system_suggestion": evaluation["suggestions"][axis],', '            "system_suggestion": {},'),
    Mutation('verifikasi hash pertama menang', F, '        latest[artifact_id] = result  # yang terakhir menang', '        latest.setdefault(artifact_id, result)'),
    Mutation('penerus lintas investigasi diterima (layanan)', F, '            supersedes.investigation_id != investigation.pk\n', '            False\n', equivalent='pelindung berlapis: revise_finding selalu memakai investigasi yang sama dan trigger DB menolak lintas investigasi (diuji)'),
    Mutation('penerus kedua diterima', F, '        if hasattr(supersedes, "superseded_by"):', '        if False:', equivalent='batasan unik supersedes di database menghasilkan InvalidFinding dengan pesan yang sama'),
    Mutation('temuan ditarik dapat digantikan', F, '        if supersedes.reviews.filter(action=ReviewAction.WITHDRAW).exists():', '        if False:'),
    Mutation('penarikan tak terdeteksi pada status', F, '    if ReviewAction.WITHDRAW in actions:', '    if False:'),
    Mutation('penerus draft menandai SUPERSEDED', F, '    if successor is not None and successor.reviews.filter(action=ReviewAction.ENDORSE).exists():', '    if successor is not None:'),
    Mutation('pengesahan tak terdeteksi pada status', F, '    if ReviewAction.ENDORSE in actions:', '    if True:'),
    Mutation('pengesahan non-DRAFT diterima', F, '    if finding_status(finding) != FindingState.DRAFT:', '    if False:'),
    Mutation('alternatif tak lengkap boleh disahkan (layanan)', F, '    if missing:\n        raise InvalidFinding(', '    if False:\n        raise InvalidFinding('),
    Mutation('penarikan ganda diterima', F, '    if finding_status(finding) == FindingState.WITHDRAWN:', '    if False:', equivalent='batasan unik (temuan, aksi) di database menghasilkan InvalidFinding dengan pesan yang sama'),
    Mutation('temuan berlaku salah saring', F, '        if finding_status(f) == FindingState.ENDORSED', '        if finding_status(f) != FindingState.WITHDRAWN'),
]
