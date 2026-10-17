"""Mutasi otorisasi dan keanggotaan (A3a; ADR 0021). Menjalankan tes matriks peran dan tim."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 ../tests/test_authorization.py ../tests/test_team.py --reuse-db'
BASELINE_COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 ../tests/test_authorization.py ../tests/test_team.py --create-db'
CWD = '{origin}'
TIMEOUT = 900

MUTATIONS = [
    Mutation('non-anggota lolos', 'backend/investigations/access.py', 'raise Http404("Investigasi tidak ditemukan.")', 'role = "VIEWER"'),
    Mutation('super admin tak istimewa', 'backend/investigations/access.py', '    if user.is_superuser:\n        return ADMIN', '    if False:\n        return ADMIN'),
    Mutation('peran setara ditolak', 'backend/investigations/access.py', 'RANK[Role(role)] < RANK[minimum]', 'RANK[Role(role)] <= RANK[minimum]'),
    Mutation('peran lebih rendah lolos', 'backend/investigations/access.py', 'RANK[Role(role)] < RANK[minimum]', 'RANK[Role(role)] > RANK[minimum]'),
    Mutation('daftar tak disaring untuk non-admin', 'backend/investigations/access.py', '    return Investigation.objects.filter(\n        memberships__user=user, memberships__revoked_at__isnull=True\n    ).distinct()', '    return Investigation.objects.all()'),
    Mutation('keanggotaan dicabut masih berlaku', 'backend/investigations/access.py', 'investigation=investigation, user=user, revoked_at__isnull=True\n    ).first()', 'investigation=investigation, user=user\n    ).first()'),
    Mutation('OWNER terakhir bisa turun', 'backend/investigations/team.py', '    if current.role == Role.OWNER and _owner_count(investigation) <= 1:\n        raise LastOwner("Investigasi harus memiliki setidaknya satu OWNER.")\n    _revoke_row(current, by)\n    return', '    _revoke_row(current, by)\n    return'),
    Mutation('OWNER terakhir bisa dicabut', 'backend/investigations/team.py', 'raise NotAMember("Pengguna itu bukan anggota investigasi ini.")\n    if current.role == Role.OWNER and _owner_count(investigation) <= 1:\n        raise LastOwner("Investigasi harus memiliki setidaknya satu OWNER.")\n    _revoke_row(current, by)\n', 'raise NotAMember("Pengguna itu bukan anggota investigasi ini.")\n    _revoke_row(current, by)\n'),
    Mutation('anggota ganda diizinkan', 'backend/investigations/team.py', '    if _active(investigation, user) is not None:\n        raise AlreadyMember', '    if False:\n        raise AlreadyMember'),
    Mutation('akun nonaktif diizinkan', 'backend/investigations/team.py', '    if not user.is_active:\n        raise InactiveUser', '    if False:\n        raise InactiveUser'),
    Mutation('pencabutan tidak mencabut', 'backend/investigations/team.py', '    InvestigationMembership.objects.filter(pk=row.pk, revoked_at__isnull=True).update(\n        revoked_at=timezone.now(), revoked_by=by\n    )', '    pass'),
    Mutation('peran sama membuat baris baru', 'backend/investigations/team.py', '    if current.role == new_role:\n        return current\n', ''),
    Mutation('kunci investigasi dilepas', 'backend/investigations/team.py', '    Investigation.objects.select_for_update().get(pk=investigation.pk)', '    Investigation.objects.get(pk=investigation.pk)'),
    Mutation('issue: VIEWER cukup', 'backend/api/views.py', 'inv = investigation_for(_user(request), pk, Role.MEMBER)\n        data = _valid(IssueInput, request)', 'inv = investigation_for(_user(request), pk, Role.VIEWER)\n        data = _valid(IssueInput, request)'),
    Mutation('inspeksi: VIEWER cukup', 'backend/api/views.py', 'target = target_for(_user(request), pk, Role.MEMBER)\n        data = _valid(InspectionInput, request)', 'target = target_for(_user(request), pk, Role.VIEWER)\n        data = _valid(InspectionInput, request)'),
    Mutation('tambah anggota: MEMBER cukup', 'backend/api/views.py', 'inv = investigation_for(user, pk, Role.OWNER)\n        data = _valid(MemberInput, request)', 'inv = investigation_for(user, pk, Role.MEMBER)\n        data = _valid(MemberInput, request)'),
    Mutation('isi artefak: perlu MEMBER', 'backend/api/views.py', 'artifact = artifact_for(_user(request), pk, Role.VIEWER)\n        try:', 'artifact = artifact_for(_user(request), pk, Role.MEMBER)\n        try:'),
    Mutation('detail run: perlu OWNER', 'backend/api/views.py', 'run = run_for(_user(request), pk, Role.VIEWER, detail=True)\n        return Response(runs.run_detail(run))', 'run = run_for(_user(request), pk, Role.OWNER, detail=True)\n        return Response(runs.run_detail(run))'),
    Mutation('daftar investigasi tak disaring (API)', 'backend/api/views.py', 'investigations = access.visible_investigations(user).select_related("created_by")', 'investigations = Investigation.objects.select_related("created_by")'),
    Mutation('pemeriksaan super admin akun dibuang', 'backend/api/views.py', '    if not user.is_superuser:\n        raise SuperuserRequired', '    if False:\n        raise SuperuserRequired'),
    Mutation('nama pengguna ganda lolos', 'backend/api/views.py', '        if model.objects.filter(username__iexact=username).exists():', '        if False:'),
    Mutation('kata sandi lemah lolos', 'backend/api/views.py', '        _validated_password(data["password"], candidate)\n        account =', '        account ='),
    Mutation('nonaktifkan diri diizinkan', 'backend/api/views.py', '        if account.pk == admin.pk and not data["active"]:', '        if False:'),
    Mutation('reset sandi tanpa validasi', 'backend/api/views.py', '        _validated_password(data["password"], account)\n        account.set_password', '        account.set_password'),
    Mutation('target: otorisasi dilewati', 'backend/api/access.py', '    target = get_object_or_404(CollectionTarget.objects.select_related("investigation"), pk=pk)\n    authorize(user, target.investigation, minimum)', '    target = get_object_or_404(CollectionTarget.objects.select_related("investigation"), pk=pk)'),
    Mutation('run: otorisasi dilewati', 'backend/api/access.py', '    authorize(user, run.target.investigation, minimum)', '    pass'),
    Mutation('artefak: otorisasi dilewati', 'backend/api/access.py', '    authorize(user, artifact.run.target.investigation, minimum)', '    pass'),
    Mutation('issue: otorisasi dilewati', 'backend/api/access.py', '    authorize(user, issue.investigation, minimum)', '    pass'),
    Mutation('pembuat tidak jadi OWNER', 'backend/investigations/services.py', '    InvestigationMembership.objects.create(  # type: ignore[misc]\n        investigation=investigation, user=user, role=Role.OWNER, added_by=user\n    )', '    pass'),
    Mutation('my_role kosong', 'backend/api/presenters.py', '"my_role": access.effective_role(user, inv),', '"my_role": None,'),
    Mutation('peran kurang jadi 400', 'backend/api/errors.py', '"insufficient_role"}, status=403)', '"insufficient_role"}, status=400)'),
    Mutation('daftar anggota bocor yang dicabut', 'backend/api/views.py', 'rows = inv.memberships.filter(revoked_at__isnull=True).select_related("user", "added_by")', 'rows = inv.memberships.all().select_related("user", "added_by")'),
]
