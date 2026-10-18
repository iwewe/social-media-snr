"""Mutasi jejak audit (WP-2.8)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_audit.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
S = 'backend/investigations/services.py'
AS = 'backend/intelligence/assessment.py'
F = 'backend/intelligence/findings.py'
A = 'backend/api/analysis.py'

MUTATIONS = [
    Mutation('issue baru tidak diaudit', S, '    _audit_issue_context(issue, user, before=None, version=version)', '    pass'),
    Mutation('revisi issue tanpa nilai sebelum', S, '    _audit_issue_context(issue, user, before=previous, version=version)', '    _audit_issue_context(issue, user, before=None, version=version)'),
    Mutation('aksi audit issue salah', S, 'action=AuditAction.ISSUE_CONTEXT,', 'action=AuditAction.TARGET_CONTEXT,'),
    Mutation('pelaku audit issue salah', S, '        investigation_id=issue.investigation_id,\n        actor=user,', '        investigation_id=issue.investigation_id,\n        actor=issue.created_by,'),
    Mutation('definisi sesudah tak dicatat', S, 'after={"version": version.version, "definition": version.definition},', 'after={"version": version.version, "definition": ""},'),
    Mutation('target tanpa nilai sebelum', S, 'before=None if previous is None else _target_context_state(previous),', 'before=None,'),
    Mutation('target tidak diaudit', S, '    audit.record(\n        investigation_id=target.investigation_id,', '    (lambda **_: None)(\n        investigation_id=target.investigation_id,'),
    Mutation('stance target tak dicatat', S, '        "stances": {\n            s.proposition.label: s.stance for s in version.stances.select_related("proposition")\n        },', '        "stances": {},'),
    Mutation('catatan target tak dicatat', S, '        "note": version.note,\n        "stances"', '        "note": "",\n        "stances"'),
    Mutation('tinjauan klasifikasi tanpa alasan', AS, '                reason=reason,\n            )\n            return reviewed', '                reason="",\n            )\n            return reviewed'),
    Mutation('tinjauan klasifikasi: pelaku salah', AS, '                investigation_id=assessment.analysis_run.investigation_id,\n                actor=by,', '                investigation_id=assessment.analysis_run.investigation_id,\n                actor=assessment.analysis_run.created_by,'),
    Mutation('tinjauan klasifikasi: subjek = yang lama', AS, '                subject_id=reviewed.pk,', '                subject_id=assessment.pk,'),
    Mutation('tinjauan klasifikasi: nilai lama tak dicatat', AS, '                    **{k: v[0] for k, v in changed.items()},', '                    **{},'),
    Mutation('tinjauan klasifikasi: nilai baru tak dicatat', AS, '                    **{k: v[1] for k, v in changed.items()},', '                    **{},'),
    Mutation('tinjauan klasifikasi: rujukan observasi hilang', AS, '                    "observation_id": assessment.observation_id,\n', ''),
    Mutation('tinjauan klasifikasi: rujukan run hilang', AS, '                    "analysis_run_id": assessment.analysis_run_id,\n', ''),
    Mutation('temuan: aksi draf/revisi tertukar', F, 'action=AuditAction.FINDING_DRAFT if supersedes is None else AuditAction.FINDING_REVISE,', 'action=AuditAction.FINDING_REVISE if supersedes is None else AuditAction.FINDING_DRAFT,'),
    Mutation('temuan: revisi tanpa rujukan pendahulu', F, '            before=None\n            if supersedes is None\n            else {\n                "finding_id": supersedes.pk,', '            before=None\n            if True\n            else {\n                "finding_id": supersedes.pk,'),
    Mutation('temuan: status pendahulu tak dicatat', F, '                "status": finding_status(supersedes),', '                "status": "",'),
    Mutation('temuan: run tak dicatat', F, '"analysis_run_ids": sorted(r.pk for r in runs),', '"analysis_run_ids": [],'),
    Mutation('temuan: jumlah observasi tak dicatat', F, '"observation_count": len(obs_ids),', '"observation_count": 0,'),
    Mutation('temuan: alasan confidence tak dicatat', F, '            reason=reason,\n        )\n    finding.refresh_from_db()', '            reason="",\n        )\n    finding.refresh_from_db()'),
    Mutation('pengesahan: status lama salah', F, '                FindingState.DRAFT,\n                FindingState.ENDORSED,', '                FindingState.ENDORSED,\n                FindingState.ENDORSED,'),
    Mutation('pengesahan: catatan tak dicatat', F, '        after={"finding_id": finding.pk, "status": new_status},\n        reason=note,', '        after={"finding_id": finding.pk, "status": new_status},\n        reason="",'),
    Mutation('pengesahan tidak diaudit', F, '            _audit_review(\n                finding,\n                by,\n                AuditAction.FINDING_ENDORSE,', '            (lambda *_: None)(\n                finding,\n                by,\n                AuditAction.FINDING_ENDORSE,'),
    Mutation('penarikan memakai status sesudah', F, 'finding, by, AuditAction.FINDING_WITHDRAW, old_status, FindingState.WITHDRAWN, note', 'finding, by, AuditAction.FINDING_WITHDRAW, FindingState.WITHDRAWN, FindingState.WITHDRAWN, note'),
    Mutation('penarikan tidak diaudit', F, '            _audit_review(\n                finding, by, AuditAction.FINDING_WITHDRAW', '            (lambda *_: None)(\n                finding, by, AuditAction.FINDING_WITHDRAW'),
    Mutation('API audit: filter aksi diabaikan', A, '    for key in ("action", "subject_type", "subject_id"):', '    for key in ("subject_type", "subject_id"):'),
    Mutation('API audit: filter subject_type diabaikan', A, '    for key in ("action", "subject_type", "subject_id"):', '    for key in ("action", "subject_id"):'),
    Mutation('API audit: filter subject_id diabaikan', A, '    for key in ("action", "subject_type", "subject_id"):', '    for key in ("action", "subject_type"):'),
    Mutation('API audit: filter pelaku diabaikan', A, '        qs = qs.filter(actor__username=filters["actor"])', '        pass'),
    Mutation('API audit: urutan terbalik', A, 'qs.order_by("-id")[(page - 1)', 'qs.order_by("id")[(page - 1)'),
    Mutation('API audit: halaman tak bergeser', A, '[(page - 1) * page_size : page * page_size])\n    return {\n        "count": total,', '[0 : page * page_size])\n    return {\n        "count": total,'),
    Mutation('API audit: tak dibatasi investigasi', A, '    qs = AuditEvent.objects.filter(investigation=investigation).select_related("actor")', '    qs = AuditEvent.objects.all().select_related("actor")'),
    Mutation('API audit: filter observasi diabaikan', A, '    if filters.get("observation") is not None:', '    if False:'),
    Mutation('API audit: filter observasi tak menyaring nilai', A, '            after__observation_id=filters["observation"],', '            after__observation_id__isnull=False,'),
    Mutation('jejak observasi: bukan observasi ini', A, '            after__observation_id=o.pk,', '            after__observation_id__isnull=False,'),
    Mutation('jejak observasi: urutan terbalik', A, '        .order_by("-id")[:50]', '        .order_by("id")[:50]'),
    Mutation('jejak observasi: tak dibatasi investigasi', A, '            investigation_id=run.target.investigation_id,\n', '', equivalent='tak terjangkau: id observasi unik di seluruh sistem dan otorisasi sudah memeriksa investigasinya; pelindung berlapis'),
]
