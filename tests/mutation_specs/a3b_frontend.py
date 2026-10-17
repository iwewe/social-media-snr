"""Mutasi UI tim, peran, dan akun (A3b; ADR 0022)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'npx vitest run'
BASELINE_COMMAND = 'npx vitest run'
CWD = '{root}/frontend'
TIMEOUT = 900

MUTATIONS = [
    Mutation('Pembaca boleh menulis', 'frontend/src/team/roles.ts', 'return role === "ADMIN" || role === "OWNER" || role === "MEMBER";', 'return role === "ADMIN" || role === "OWNER" || role === "MEMBER" || role === "VIEWER";'),
    Mutation('Super admin tak boleh menulis', 'frontend/src/team/roles.ts', 'return role === "ADMIN" || role === "OWNER" || role === "MEMBER";', 'return role === "OWNER" || role === "MEMBER";'),
    Mutation('Anggota boleh mengelola', 'frontend/src/team/roles.ts', 'return role === "ADMIN" || role === "OWNER";', 'return role === "ADMIN" || role === "OWNER" || role === "MEMBER";'),
    Mutation('Super admin tak boleh mengelola', 'frontend/src/team/roles.ts', 'return role === "ADMIN" || role === "OWNER";', 'return role === "OWNER";'),
    Mutation('tim: semua boleh mengelola', 'frontend/src/components/TeamPanel.tsx', 'const manage = canManage(role);', 'const manage = true;'),
    Mutation('tim: cabut tanpa konfirmasi', 'frontend/src/components/TeamPanel.tsx', 'onClick={() => setConfirming(m.user_id)}', 'onClick={() => revoke(m)}'),
    Mutation('tim: onLeft untuk siapa pun', 'frontend/src/components/TeamPanel.tsx', 'if (member.username === username) onLeft?.();', 'onLeft?.();'),
    Mutation('tim: nama tidak dipangkas', 'frontend/src/components/TeamPanel.tsx', 'username: newName.trim()', 'username: newName'),
    Mutation('tim: tombol tambah selalu aktif', 'frontend/src/components/TeamPanel.tsx', 'disabled={busy || !newName.trim()}', 'disabled={busy}'),
    Mutation('tim: galat disembunyikan', 'frontend/src/components/TeamPanel.tsx', '      <ErrorMessage error={error} />\n      {members === null', '      {members === null'),
    Mutation('tim: tanpa petunjuk peran', 'frontend/src/components/TeamPanel.tsx', 'Tim <ContextHelp id="teamRoles" />', 'Tim'),
    Mutation('tim: penanda Anda dihapus', 'frontend/src/components/TeamPanel.tsx', '{m.username === username && <span className="muted"> (Anda)</span>}', ''),
    Mutation('halaman: semua boleh menulis', 'frontend/src/pages/InvestigationPage.tsx', 'const writable = canWrite(role);', 'const writable = true;'),
    Mutation('halaman: tim disembunyikan', 'frontend/src/pages/InvestigationPage.tsx', '{role && user && (', '{false && ('),
    Mutation('halaman: catatan hanya-baca dibuang', 'frontend/src/pages/InvestigationPage.tsx', '{!writable && role && (', '{false && ('),
    Mutation('halaman: lencana peran dibuang', 'frontend/src/pages/InvestigationPage.tsx', '{detail.name} <RoleBadge role={role} />', '{detail.name}'),
    Mutation('halaman: readOnly tak diteruskan', 'frontend/src/pages/InvestigationPage.tsx', 'readOnly={!writable} />', 'readOnly={false} />'),
    Mutation('kartu: revisi tetap ada untuk Pembaca', 'frontend/src/components/TargetCard.tsx', '{readOnly ? null : revising ? (', '{revising ? ('),
    Mutation('panel inspeksi: tombol aktif untuk Pembaca', 'frontend/src/components/InspectionPanel.tsx', 'disabled={readOnly || runs === null || busy}', 'disabled={runs === null || busy}'),
    Mutation('tinjauan: Pembaca dapat mengakui', 'frontend/src/components/ReviewPanel.tsx', '  if (!canAcknowledge) {', '  if (false) {'),
    Mutation('run: hak akui selalu ya', 'frontend/src/pages/RunPage.tsx', 'canAcknowledge={canWrite(run.my_role)}', 'canAcknowledge={true}'),
    Mutation('akun: tanpa penjagaan super admin', 'frontend/src/pages/UsersPage.tsx', 'const allowed = user?.is_superuser === true;', 'const allowed = true;'),
    Mutation('akun: nonaktifkan diri diizinkan', 'frontend/src/pages/UsersPage.tsx', 'disabled={busy || a.username === user?.username}', 'disabled={busy}'),
    Mutation('akun: kata sandi terlihat', 'frontend/src/pages/UsersPage.tsx', 'type="password"\n            value={password}', 'type="text"\n            value={password}'),
    Mutation('akun: nama tidak dipangkas', 'frontend/src/pages/UsersPage.tsx', 'username: username.trim(), password', 'username, password'),
    Mutation('akun: isian tak dikosongkan', 'frontend/src/pages/UsersPage.tsx', '      setUsername("");\n      setPassword("");', ''),
    Mutation('bilah: Akun untuk semua', 'frontend/src/App.tsx', '{user.is_superuser && (', '{true && ('),
    Mutation('daftar: lencana peran dibuang', 'frontend/src/pages/InvestigationsPage.tsx', '<RoleBadge role={i.my_role} />', ''),
]
