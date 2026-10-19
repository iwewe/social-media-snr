"""Mutasi pemilihan versi konteks yang dibekukan (A2)."""

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
A = 'backend/api/analysis.py'
V = 'backend/api/analysis_views.py'
S = 'backend/api/serializers.py'

MUTATIONS = [
    Mutation('versi isu eksplisit diabaikan', L, '        issue_ctx = IssueContextVersion.objects.filter(\n            issue=proposition.issue, version=issue_version\n        ).first()', '        issue_ctx = services.latest_issue_context(proposition.issue)'),
    Mutation('versi isu tak ada diterima', L, '        if issue_ctx is None:\n            raise InvalidParameters(f"konteks isu versi {issue_version} tidak ada")', '        if False:\n            raise InvalidParameters(f"konteks isu versi {issue_version} tidak ada")'),
    Mutation('versi isu untuk metode tanpa isu diterima', L, '        if proposition is None:\n            raise InvalidParameters(\n                "metode ini tidak memakai konteks isu; versi konteks isu tidak berlaku"\n            )', '        if False:\n            raise InvalidParameters("x")'),
    Mutation('target di luar dataset diterima', L, '        if target_id not in targets:\n            raise InvalidParameters(f"target {target_id} tidak ada pada dataset ini")', '        if False:\n            raise InvalidParameters(f"target {target_id} tidak ada pada dataset ini")'),
    Mutation('tanpa konteks target diabaikan', L, '        if version is None:\n            targets[target_id] = None\n            continue', '        if version is None:\n            continue'),
    Mutation('versi target tak ada diterima', L, '        if ctx is None:\n            raise InvalidParameters(f"konteks target {target_id} versi {version} tidak ada")', '        if False:\n            raise InvalidParameters(f"konteks target {target_id} versi {version} tidak ada")'),
    Mutation('versi target eksplisit diabaikan', L, '        targets[target_id] = ctx\n    return issue_ctx, targets', '        pass\n    return issue_ctx, targets'),
    Mutation('target tak disebut tidak memakai terbaru', L, '    targets = dict(services.latest_target_contexts(dataset))', '    targets = {t: None for t in services.latest_target_contexts(dataset)}'),
    Mutation('default isu bukan terbaru', L, '        issue_ctx = services.latest_issue_context(proposition.issue if proposition else None)', '        issue_ctx = None'),
    Mutation('versi isu tak masuk audit', L, '        "issue_context_version": run.issue_context_version.version\n        if run.issue_context_version\n        else None,', '        "issue_context_version": None,'),
    Mutation('versi target tak masuk audit', L, '            str(c.target_id): (c.context_version.version if c.context_version else None)\n            for c in run.target_contexts.select_related("context_version")', '            str(c.target_id): None\n            for c in run.target_contexts.select_related("context_version")'),
    Mutation('pilihan tak diteruskan dari API (isu)', V, '            issue_context_version=data.get("issue_context_version"),', '            issue_context_version=None,'),
    Mutation('pilihan tak diteruskan dari API (target)', V, '            target_context_versions=data.get("target_context_versions") or None,', '            target_context_versions=None,'),
    Mutation('kunci target bukan angka diterima', S, '            return {int(k): v for k, v in value.items()}\n        except ValueError:\n            raise serializers.ValidationError("kunci harus id target (angka)") from None', '            return {}\n        except ValueError:\n            raise serializers.ValidationError("kunci harus id target (angka)") from None'),
    Mutation('versi nol diterima (isu)', S, '    issue_context_version = serializers.IntegerField(\n        min_value=1, required=False, allow_null=True, default=None\n    )', '    issue_context_version = serializers.IntegerField(\n        min_value=0, required=False, allow_null=True, default=None\n    )', equivalent='setara pada hasil akhir: versi 0 tidak pernah ada sehingga resolve_contexts menolaknya (400); min_value hanya pagar ganda dengan pesan berbeda'),
    Mutation('versi target nol diterima', S, 'child=serializers.IntegerField(min_value=1, allow_null=True), required=False, default=dict', 'child=serializers.IntegerField(min_value=0, allow_null=True), required=False, default=dict', equivalent='setara pada hasil akhir: versi target 0 tidak pernah ada sehingga resolve_contexts menolaknya (400)'),
    Mutation('versi isu tak tampil di bahan formulir', A, '                    for v in i.context_versions.order_by("-version")', '                    for v in i.context_versions.order_by("version")'),
    Mutation('target dataset tak tampil', A, '        "target_ids": d.selection.get("targets", []),', '        "target_ids": [],'),
]
