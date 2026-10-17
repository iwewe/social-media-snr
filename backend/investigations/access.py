"""Otorisasi per investigasi (A3; ADR 0021).

Peran:
- Super admin: `user.is_superuser` (bukan anggota; melihat dan mengelola SEMUA investigasi).
- OWNER: kelola anggota + semua hak MEMBER. Pembuat investigasi otomatis OWNER.
- MEMBER: baca, tulis (issue, proposition, target, konteks), jalankan inspeksi, akui tinjauan.
- VIEWER: baca saja (termasuk bukti dan verifikasi hash).

Aturan inti:
- Bukan anggota = investigasi TIDAK ADA bagi pengguna itu (404 yang sama dengan id yang tidak ada):
  keberadaan investigasi tidak bocor.
- Anggota dengan peran kurang = 403 (`insufficient_role`).
- Keanggotaan tidak pernah dihapus: dicabut (`revoked_at`), agar riwayat siapa pernah punya
  akses tetap ada.
"""

from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.http import Http404

from .enums import Role
from .errors import DomainError
from .models import Investigation, InvestigationMembership

RANK = {Role.VIEWER: 1, Role.MEMBER: 2, Role.OWNER: 3}
ADMIN = "ADMIN"  # peran efektif super admin (bukan nilai Role)


class SuperuserRequired(DomainError):
    """Tindakan khusus super admin (pengelolaan akun pengguna)."""


class InsufficientRole(DomainError):
    """Anggota investigasi tetapi perannya tidak cukup untuk tindakan ini."""


def active_membership(user: User, investigation: Investigation) -> InvestigationMembership | None:
    return InvestigationMembership.objects.filter(
        investigation=investigation, user=user, revoked_at__isnull=True
    ).first()


def effective_role(user: User, investigation: Investigation) -> str | None:
    """`ADMIN` untuk super admin, peran anggota aktif, atau None bila tidak punya akses."""
    if user.is_superuser:
        return ADMIN
    membership = active_membership(user, investigation)
    return membership.role if membership else None


def authorize(user: User, investigation: Investigation, minimum: Role) -> str:
    """Peran efektif bila cukup. Raise Http404 (tanpa akses) atau InsufficientRole (kurang)."""
    role = effective_role(user, investigation)
    if role is None:
        raise Http404("Investigasi tidak ditemukan.")
    if role != ADMIN and RANK[Role(role)] < RANK[minimum]:
        raise InsufficientRole("Peran Anda pada investigasi ini tidak mengizinkan tindakan itu.")
    return role


def visible_investigations(user: User) -> QuerySet[Investigation]:
    if user.is_superuser:
        return Investigation.objects.all()
    return Investigation.objects.filter(
        memberships__user=user, memberships__revoked_at__isnull=True
    ).distinct()
