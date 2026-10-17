"""Pengelolaan anggota investigasi (A3). Tindakan di sini TIDAK memeriksa hak pelaku; pemanggil
(API) wajib memastikan pelaku adalah OWNER atau super admin lewat `access.authorize`.

Riwayat: keanggotaan dicabut (revoked_at/revoked_by), tidak dihapus; mengubah peran = mencabut baris
lama dan membuat baris baru dalam satu transaksi. Investigasi tidak boleh kehilangan OWNER
terakhir."""

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .enums import Role
from .errors import DomainError
from .models import Investigation, InvestigationMembership


class AlreadyMember(DomainError):
    pass


class NotAMember(DomainError):
    pass


class LastOwner(DomainError):
    pass


class UnknownUser(DomainError):
    pass


class InactiveUser(DomainError):
    pass


def _lock(investigation: Investigation) -> None:
    """Serialkan perubahan keanggotaan per investigasi (aturan OWNER terakhir tahan balapan)."""
    Investigation.objects.select_for_update().get(pk=investigation.pk)


def _active(investigation: Investigation, user: User) -> InvestigationMembership | None:
    return InvestigationMembership.objects.filter(
        investigation=investigation, user=user, revoked_at__isnull=True
    ).first()


def _owner_count(investigation: Investigation) -> int:
    return InvestigationMembership.objects.filter(
        investigation=investigation, role=Role.OWNER, revoked_at__isnull=True
    ).count()


def user_by_username(username: str) -> User:
    user = User.objects.filter(username=username.strip()).first()
    if user is None:
        raise UnknownUser("Pengguna dengan nama itu tidak ditemukan.")
    return user


@transaction.atomic
def grant(
    *, investigation: Investigation, user: User, role: str, added_by: User
) -> InvestigationMembership:
    """Tambahkan `user` sebagai anggota. Dipakai juga untuk pembuat investigasi (OWNER)."""
    _lock(investigation)
    if not user.is_active:
        raise InactiveUser("Akun pengguna itu tidak aktif.")
    if _active(investigation, user) is not None:
        raise AlreadyMember("Pengguna itu sudah menjadi anggota investigasi ini.")
    return InvestigationMembership.objects.create(
        investigation=investigation, user=user, role=Role(role).value, added_by=added_by
    )


def _revoke_row(row: InvestigationMembership, by: User) -> None:
    InvestigationMembership.objects.filter(pk=row.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_by=by
    )


@transaction.atomic
def change_role(
    *, investigation: Investigation, user: User, role: str, by: User
) -> InvestigationMembership:
    _lock(investigation)
    current = _active(investigation, user)
    if current is None:
        raise NotAMember("Pengguna itu bukan anggota investigasi ini.")
    new_role = Role(role).value
    if current.role == new_role:
        return current
    if current.role == Role.OWNER and _owner_count(investigation) <= 1:
        raise LastOwner("Investigasi harus memiliki setidaknya satu OWNER.")
    _revoke_row(current, by)
    return InvestigationMembership.objects.create(
        investigation=investigation, user=user, role=new_role, added_by=by
    )


@transaction.atomic
def revoke(*, investigation: Investigation, user: User, by: User) -> None:
    _lock(investigation)
    current = _active(investigation, user)
    if current is None:
        raise NotAMember("Pengguna itu bukan anggota investigasi ini.")
    if current.role == Role.OWNER and _owner_count(investigation) <= 1:
        raise LastOwner("Investigasi harus memiliki setidaknya satu OWNER.")
    _revoke_row(current, by)
