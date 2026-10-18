"""Mutasi API analisis (WP-2.7a)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_api_analysis.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
A = 'backend/api/analysis.py'
V = 'backend/api/analysis_views.py'
X = 'backend/api/access.py'
S = 'backend/api/serializers.py'

MUTATIONS = [
    Mutation('filter stance diabaikan', A, '    if filters.get("stance"):\n        qs = qs.filter(issue_stance=filters["stance"])', '    if False:\n        qs = qs.filter(issue_stance=filters["stance"])'),
    Mutation('filter alignment diabaikan', A, '    if filters.get("alignment"):\n        qs = qs.filter(target_alignment=filters["alignment"])', '    if False:\n        qs = qs.filter(target_alignment=filters["alignment"])'),
    Mutation('filter karakter diabaikan', A, '    if filters.get("character"):\n        qs = qs.filter(response_character__contains=[filters["character"]])', '    if False:\n        qs = qs.filter(response_character__contains=[filters["character"]])'),
    Mutation('filter asal diabaikan', A, '    if filters.get("origin"):', '    if False:'),
    Mutation('needs_review hanya benar yang berlaku', A, '    if filters.get("needs_review") is not None:', '    if filters.get("needs_review"):'),
    Mutation('filter akun respons diabaikan', A, '        qs = qs.filter(observation__author_id=filters["actor"])', '        pass'),
    Mutation('metode salah diterima', A, '    if not run.method.startswith(prefix):', '    if False:'),
    Mutation('kategori koreksi manusia hilang', A, '**tier_repr(ResultTier.ANALYTICAL_CLASSIFICATION, HUMAN if human else MACHINE),\n            }', '**tier_repr(ResultTier.ANALYTICAL_CLASSIFICATION, MACHINE),\n            }'),
    Mutation('jumlah versi tidak dihitung', A, '"versions": len(assessment_history(a)) if human else 1,', '"versions": 1,'),
    Mutation('stance induk tidak dibawa', A, '"stance": parent_stance.get(n.observation_id),', '"stance": None,'),
    Mutation('filter jenis relasi graf diabaikan', A, '        if wanted_types is not None and e.relation_type not in wanted_types:', '        if False:'),
    Mutation('filter since graf diabaikan', A, '            if since and e.last_published_at and e.last_published_at < since:', '            if False:'),
    Mutation('filter until graf diabaikan', A, '            if until and e.first_published_at and e.first_published_at >= until:', '            if False:'),
    Mutation('waktu tak diketahui selalu dikecualikan', A, '            if params.get("include_unknown_time") is False:', '            if True:'),
    Mutation('waktu tak diketahui tak pernah dikecualikan', A, '            if params.get("include_unknown_time") is False:', '            if False:'),
    Mutation('filter stance graf terbalik', A, 'if n.attributes.get("stance_summary") == stance}', 'if n.attributes.get("stance_summary") != stance}'),
    Mutation('edge stance memakai ATAU', A, 'if e.from_node.actor_id in allowed and e.to_node.actor_id in allowed', 'if e.from_node.actor_id in allowed or e.to_node.actor_id in allowed'),
    Mutation('pemotongan graf salah batas', A, '    truncated = total_nodes > max_nodes', '    truncated = total_nodes >= max_nodes'),
    Mutation('pemotongan graf: yang terlemah dipertahankan', A, 'key=lambda a: (-strength.get(a, 0), a)', 'key=lambda a: (strength.get(a, 0), a)'),
    Mutation('jenis edge interaksi salah', A, '"kind": "interaction",', '"kind": "behavioral_similarity",'),
    Mutation('jenis edge kesamaan salah', A, '"kind": "behavioral_similarity",\n                "indicator": r.indicator,', '"kind": "interaction",\n                "indicator": r.indicator,'),
    Mutation('filter indikator diabaikan', A, '        qs = qs.filter(indicator=filters["indicator"])', '        pass'),
    Mutation('filter dukungan minimum diabaikan', A, '        qs = qs.filter(support__gte=filters["min_support"])', '        pass'),
    Mutation('filter akun indikator hanya A', A, 'qs = qs.filter(Q(actor_a_id=filters["actor"]) | Q(actor_b_id=filters["actor"]))', 'qs = qs.filter(Q(actor_a_id=filters["actor"]))'),
    Mutation('filter beyond_baseline terbalik', A, 'if bool(r.baseline.get("exceeds_baseline_p95")) == filters["beyond_baseline"]', 'if bool(r.baseline.get("exceeds_baseline_p95")) != filters["beyond_baseline"]'),
    Mutation('artefak tanpa post tidak ikut', A, '| Q(post__isnull=True)', '| Q(pk__in=[])'),
    Mutation('ringkasan profil kehilangan cakupan', A, '"coverage_statement": p.coverage["statement"],', '"coverage_statement": "",'),
    Mutation('temuan: sejarah tidak dimuat', A, '        "history": [', '        "history_hidden": ['),
    Mutation('run indikator tak diperiksa di temuan', V, '    if len(runs) != len(set(data["analysis_run_ids"])) or len(edges) != len(\n        set(data["indicator_edge_ids"])\n    ):', '    if False:'),
    Mutation('peran tulis temuan turun ke VIEWER', V, '        inv = investigation_for(_user(request), pk, Role.MEMBER)\n        finding = fs.draft_finding(', '        inv = investigation_for(_user(request), pk, Role.VIEWER)\n        finding = fs.draft_finding('),
    Mutation('peran tinjauan klasifikasi turun ke VIEWER', V, 'current = assessment_for(_user(request), pk, Role.MEMBER)', 'current = assessment_for(_user(request), pk, Role.VIEWER)'),
    Mutation('peran pengesahan turun ke VIEWER', V, '        finding = finding_for(_user(request), pk, Role.MEMBER)\n        data = _valid(FindingNoteInput, request)\n        fs.endorse_finding(', '        finding = finding_for(_user(request), pk, Role.VIEWER)\n        data = _valid(FindingNoteInput, request)\n        fs.endorse_finding('),
    Mutation('peran penarikan turun ke VIEWER', V, '        finding = finding_for(_user(request), pk, Role.MEMBER)\n        data = _valid(FindingNoteInput, request)\n        fs.withdraw_finding(', '        finding = finding_for(_user(request), pk, Role.VIEWER)\n        data = _valid(FindingNoteInput, request)\n        fs.withdraw_finding('),
    Mutation('peran revisi turun ke VIEWER', V, '        previous = finding_for(_user(request), pk, Role.MEMBER)', '        previous = finding_for(_user(request), pk, Role.VIEWER)'),
    Mutation('peran detail run naik ke OWNER', V, '        run = analysis_run_for(_user(request), pk, Role.VIEWER)\n        return Response(analysis.run_repr(run, full=True))', '        run = analysis_run_for(_user(request), pk, Role.OWNER)\n        return Response(analysis.run_repr(run, full=True))'),
    Mutation('otorisasi run analisis dibuang', X, '    run = get_object_or_404(\n        AnalysisRun.objects.select_related("investigation", "dataset_version", "created_by"), pk=pk\n    )\n    authorize(user, run.investigation, minimum)', '    run = get_object_or_404(\n        AnalysisRun.objects.select_related("investigation", "dataset_version", "created_by"), pk=pk\n    )'),
    Mutation('otorisasi klasifikasi dibuang', X, '    authorize(user, assessment.analysis_run.investigation, minimum)', '    pass'),
    Mutation('otorisasi profil dibuang', X, '    authorize(user, profile.analysis_run.investigation, minimum)', '    pass'),
    Mutation('otorisasi temuan dibuang', X, '    authorize(user, finding.investigation, minimum)', '    pass'),
    Mutation('otorisasi observasi dibuang', X, '    authorize(user, observation.run.target.investigation, minimum)', '    pass'),
    Mutation('boolean needs_review kembali ke bawaan DRF', S, '    needs_review = serializers.BooleanField(required=False, allow_null=True)', '    needs_review = serializers.BooleanField(required=False)'),
    Mutation('boolean include_unknown_time kembali ke bawaan DRF', S, '    include_unknown_time = serializers.BooleanField(required=False, allow_null=True)', '    include_unknown_time = serializers.BooleanField(required=False)'),
    Mutation('boolean beyond_baseline kembali ke bawaan DRF', S, '    beyond_baseline = serializers.BooleanField(required=False, allow_null=True)', '    beyond_baseline = serializers.BooleanField(required=False)'),
]
