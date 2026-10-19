"""Mutasi revisi konteks isu (FR-014)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_issue_context_api.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
V = 'backend/api/views.py'
P = 'backend/api/presenters.py'
S = 'backend/api/serializers.py'

MUTATIONS = [
    Mutation('peran revisi turun ke pembaca', V, 'issue = issue_for(_user(request), pk, Role.MEMBER)\n        data = _valid(IssueContextInput, request)', 'issue = issue_for(_user(request), pk, Role.VIEWER)\n        data = _valid(IssueContextInput, request)'),
    Mutation('definisi sama diterima', V, '        if latest is not None and latest.definition == data["definition"]:', '        if False:'),
    Mutation('definisi dipangkas saat dibandingkan', V, 'latest.definition == data["definition"]', 'latest.definition.strip() == data["definition"].strip()'),
    Mutation('revisi tidak disimpan', V, '        services.revise_issue_context(\n            issue=issue, user=_user(request), definition=data["definition"]\n        )\n', ''),
    Mutation('pelaku revisi salah', V, 'issue=issue, user=_user(request), definition=data["definition"]', 'issue=issue, user=issue.created_by, definition=data["definition"]'),
    Mutation('status respons bukan 201', V, '        return Response(presenters.issue_repr(issue), status=201)\n\n\nclass PropositionCreateView', '        return Response(presenters.issue_repr(issue), status=200)\n\n\nclass PropositionCreateView'),
    Mutation('riwayat terlama dulu', P, 'issue.context_versions.select_related("created_by").order_by("-version")', 'issue.context_versions.select_related("created_by").order_by("version")'),
    Mutation('pembuat versi tak dicatat', P, '"created_by": v.created_by.get_username(),\n            }\n            for v in versions', '"created_by": "",\n            }\n            for v in versions'),
    Mutation('definisi riwayat kosong', P, '                "definition": v.definition,\n                "created_at"', '                "definition": "",\n                "created_at"'),
    Mutation('definisi kosong ditolak', S, '    definition = serializers.CharField(allow_blank=True, trim_whitespace=False)\n\n\nclass PropositionInput', '    definition = serializers.CharField(allow_blank=False, trim_whitespace=False)\n\n\nclass PropositionInput'),
    Mutation('spasi dipangkas serializer', S, '    definition = serializers.CharField(allow_blank=True, trim_whitespace=False)\n\n\nclass PropositionInput', '    definition = serializers.CharField(allow_blank=True, trim_whitespace=True)\n\n\nclass PropositionInput'),
]
