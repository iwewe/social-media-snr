"""Mutasi riwayat akses bukti (WP-3.6b)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_evidence_access.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
A = 'backend/api/analysis.py'
V = 'backend/api/analysis_views.py'

MUTATIONS = [
    Mutation('akses bukti: filter keperluan diabaikan', A, '    if filters.get("purpose"):\n        qs = qs.filter(purpose=filters["purpose"])', '    if False:\n        qs = qs.filter(purpose=filters["purpose"])'),
    Mutation('akses bukti: filter hasil diabaikan', A, '    if filters.get("result"):\n        qs = qs.filter(result=filters["result"])', '    if False:\n        qs = qs.filter(result=filters["result"])'),
    Mutation('akses bukti: filter pengguna diabaikan', A, '        qs = qs.filter(verified_by__username=filters["user"])', '        pass'),
    Mutation('akses bukti: filter artefak diabaikan', A, '        qs = qs.filter(artifact_id=filters["artifact"])', '        pass'),
    Mutation('akses bukti: tak dibatasi investigasi', A, '        artifact__run__target__investigation=investigation\n', '        artifact__run__target__isnull=False\n'),
    Mutation('akses bukti: urutan terbalik', A, '    chunk = list(qs.order_by("-id")[(page - 1) * page_size : page * page_size])\n    return {\n        "count": total,\n        "page": page,\n        "page_size": page_size,\n        "results": [\n            {\n                "id": v.pk,', '    chunk = list(qs.order_by("id")[(page - 1) * page_size : page * page_size])\n    return {\n        "count": total,\n        "page": page,\n        "page_size": page_size,\n        "results": [\n            {\n                "id": v.pk,'),
    Mutation('akses bukti: halaman tak bergeser', A, '    chunk = list(qs.order_by("-id")[(page - 1) * page_size : page * page_size])\n    return {\n        "count": total,\n        "page": page,\n        "page_size": page_size,\n        "results": [\n            {\n                "id": v.pk,', '    chunk = list(qs.order_by("-id")[0 : page * page_size])\n    return {\n        "count": total,\n        "page": page,\n        "page_size": page_size,\n        "results": [\n            {\n                "id": v.pk,'),
    Mutation('akses bukti: pengguna salah', A, '"user": v.verified_by.get_username(),', '"user": v.artifact.run.requested_by.get_username(),'),
    Mutation('akses bukti: hasil salah', A, '"result": v.result,\n                "artifact"', '"result": "MATCH",\n                "artifact"'),
    Mutation('akses bukti: jalur berkas bocor', A, '"kind": v.artifact.kind,', '"kind": v.artifact.kind,\n                    "relative_path": v.artifact.relative_path,'),
    Mutation('akses bukti: peran turun ke non-anggota', V, '        inv = investigation_for(_user(request), pk, Role.VIEWER)\n        query = _query(EvidenceAccessInput, request)', '        inv = Investigation.objects.get(pk=pk)\n        query = _query(EvidenceAccessInput, request)'),
]
