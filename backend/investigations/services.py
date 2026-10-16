"""Jalur penulisan domain WP-0.4.

Semua pembuatan versi lewat modul ini: nomor versi diberikan di bawah kunci baris induk
(select_for_update) sehingga dua revisi bersamaan tidak menghasilkan versi ganda. Constraint
unik di DB menjadi pengaman terakhir.
"""

from collections.abc import Mapping

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from .enums import InitialStance, TargetType
from .errors import DuplicateTarget, InvalidContext
from .models import (
    CollectionTarget,
    Investigation,
    Issue,
    IssueContextVersion,
    Proposition,
    TargetContextVersion,
    TargetPropositionStance,
)

User = AbstractBaseUser


def create_investigation(*, user: User, name: str, description: str = "") -> Investigation:
    name = name.strip()
    if not name:
        raise InvalidContext("Nama investigasi wajib diisi.")
    return Investigation.objects.create(name=name, description=description, created_by=user)  # type: ignore[misc]


@transaction.atomic
def create_issue(
    *, investigation: Investigation, user: User, title: str, definition: str = ""
) -> Issue:
    title = title.strip()
    if not title:
        raise InvalidContext("Judul issue wajib diisi.")
    issue = Issue.objects.create(investigation=investigation, title=title, created_by=user)  # type: ignore[misc]
    IssueContextVersion.objects.create(
        issue=issue,
        version=1,
        definition=definition,
        created_by=user,  # type: ignore[misc]
    )
    return issue


@transaction.atomic
def revise_issue_context(*, issue: Issue, user: User, definition: str) -> IssueContextVersion:
    Issue.objects.select_for_update().get(pk=issue.pk)
    latest = issue.context_versions.aggregate(m=Max("version"))["m"] or 0
    return IssueContextVersion.objects.create(
        issue=issue,
        version=latest + 1,
        definition=definition,
        created_by=user,  # type: ignore[misc]
    )


@transaction.atomic
def add_proposition(*, issue: Issue, user: User, statement: str) -> Proposition:
    statement = statement.strip()
    if not statement:
        raise InvalidContext("Pernyataan proposition wajib diisi.")
    Issue.objects.select_for_update().get(pk=issue.pk)
    latest = issue.propositions.aggregate(m=Max("number"))["m"] or 0
    return Proposition.objects.create(
        issue=issue,
        number=latest + 1,
        statement=statement,
        created_by=user,  # type: ignore[misc]
    )


def retire_proposition(*, proposition: Proposition) -> Proposition:
    """Tandai proposition tidak dipakai lagi. Isinya tidak berubah; hanya dapat dilakukan sekali."""
    if proposition.retired_at is not None:
        raise InvalidContext("Proposition sudah dinonaktifkan.")
    proposition.retired_at = timezone.now()
    proposition.save(update_fields=["retired_at"])
    return proposition


def _validate_stances(
    investigation: Investigation, stances: Mapping[Proposition, str]
) -> list[tuple[Proposition, str]]:
    checked = []
    for proposition, stance in stances.items():
        if proposition.issue.investigation_id != investigation.pk:
            raise InvalidContext(
                "Proposition harus berasal dari investigasi yang sama dengan target."
            )
        if proposition.retired_at is not None:
            raise InvalidContext(f"{proposition.label} sudah dinonaktifkan.")
        if stance not in InitialStance.values:
            raise InvalidContext(
                f"Stance awal harus salah satu dari: {', '.join(InitialStance.values)}."
            )
        checked.append((proposition, stance))
    return checked


def _write_context_version(
    *,
    target: CollectionTarget,
    user: User,
    note: str,
    stances: list[tuple[Proposition, str]],
) -> TargetContextVersion:
    latest = target.context_versions.aggregate(m=Max("version"))["m"] or 0
    version = TargetContextVersion.objects.create(
        target=target,
        version=latest + 1,
        note=note,
        created_by=user,  # type: ignore[misc]
    )
    TargetPropositionStance.objects.bulk_create(
        TargetPropositionStance(context_version=version, proposition=p, stance=s)
        for p, s in stances
    )
    return version


@transaction.atomic
def register_target(
    *,
    investigation: Investigation,
    user: User,
    platform: str,
    target_type: str,
    url: str,
    note: str = "",
    stances: Mapping[Proposition, str] | None = None,
) -> CollectionTarget:
    """Daftarkan target beserta versi konteks pertama. URL ganda (setelah normalisasi) ditolak."""
    if target_type not in TargetType.values:
        raise InvalidContext("Jenis target harus posting atau akun.")
    checked = _validate_stances(investigation, stances or {})

    target = CollectionTarget(
        investigation=investigation,
        platform=platform,
        target_type=target_type,
        url=url,
        created_by=user,  # type: ignore[misc]
    )
    try:
        with transaction.atomic():
            target.save()
    except IntegrityError:
        existing = CollectionTarget.objects.get(
            investigation=investigation, platform=platform, normalized_url=target.normalized_url
        )
        raise DuplicateTarget(existing.pk) from None

    _write_context_version(target=target, user=user, note=note, stances=checked)
    return target


@transaction.atomic
def revise_target_context(
    *,
    target: CollectionTarget,
    user: User,
    note: str,
    stances: Mapping[Proposition, str] | None = None,
) -> TargetContextVersion:
    """Buat versi konteks baru. Versi lama tidak berubah (AT-07).

    stances=None berarti posisi awal versi sebelumnya dibawa ke versi baru; mapping kosong `{}`
    berarti sengaja tanpa posisi awal.
    """
    CollectionTarget.objects.select_for_update().get(pk=target.pk)
    if stances is None:
        previous = target.context_versions.order_by("-version").first()
        carried = (
            {s.proposition: s.stance for s in previous.stances.select_related("proposition")}
            if previous
            else {}
        )
        checked = _validate_stances(target.investigation, carried)
    else:
        checked = _validate_stances(target.investigation, stances)
    return _write_context_version(target=target, user=user, note=note, stances=checked)
