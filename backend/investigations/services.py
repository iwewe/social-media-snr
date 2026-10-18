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

from audit import services as audit
from audit.models import AuditAction, SubjectType

from .enums import InitialStance, Role, TargetType
from .errors import DuplicateTarget, InvalidContext
from .models import (
    CollectionTarget,
    Investigation,
    InvestigationMembership,
    Issue,
    IssueContextVersion,
    Proposition,
    TargetContextVersion,
    TargetPropositionStance,
)

User = AbstractBaseUser


@transaction.atomic
def create_investigation(*, user: User, name: str, description: str = "") -> Investigation:
    name = name.strip()
    if not name:
        raise InvalidContext("Nama investigasi wajib diisi.")
    investigation = Investigation.objects.create(  # type: ignore[misc]
        name=name, description=description, created_by=user
    )
    InvestigationMembership.objects.create(  # type: ignore[misc]
        investigation=investigation, user=user, role=Role.OWNER, added_by=user
    )
    return investigation


def _audit_issue_context(
    issue: Issue, user: User, *, before: IssueContextVersion | None, version: IssueContextVersion
) -> None:
    audit.record(
        investigation_id=issue.investigation_id,
        actor=user,
        action=AuditAction.ISSUE_CONTEXT,
        subject_type=SubjectType.ISSUE,
        subject_id=issue.pk,
        before=None
        if before is None
        else {"version": before.version, "definition": before.definition},
        after={"version": version.version, "definition": version.definition},
    )


@transaction.atomic
def create_issue(
    *, investigation: Investigation, user: User, title: str, definition: str = ""
) -> Issue:
    title = title.strip()
    if not title:
        raise InvalidContext("Judul issue wajib diisi.")
    issue = Issue.objects.create(investigation=investigation, title=title, created_by=user)  # type: ignore[misc]
    version = IssueContextVersion.objects.create(
        issue=issue,
        version=1,
        definition=definition,
        created_by=user,  # type: ignore[misc]
    )
    _audit_issue_context(issue, user, before=None, version=version)
    return issue


@transaction.atomic
def revise_issue_context(*, issue: Issue, user: User, definition: str) -> IssueContextVersion:
    Issue.objects.select_for_update().get(pk=issue.pk)
    previous = issue.context_versions.order_by("-version").first()
    version = IssueContextVersion.objects.create(
        issue=issue,
        version=(previous.version if previous else 0) + 1,
        definition=definition,
        created_by=user,  # type: ignore[misc]
    )
    _audit_issue_context(issue, user, before=previous, version=version)
    return version


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
    previous = target.context_versions.order_by("-version").first()
    version = TargetContextVersion.objects.create(
        target=target,
        version=(previous.version if previous else 0) + 1,
        note=note,
        created_by=user,  # type: ignore[misc]
    )
    TargetPropositionStance.objects.bulk_create(
        TargetPropositionStance(context_version=version, proposition=p, stance=s)
        for p, s in stances
    )
    audit.record(
        investigation_id=target.investigation_id,
        actor=user,
        action=AuditAction.TARGET_CONTEXT,
        subject_type=SubjectType.TARGET,
        subject_id=target.pk,
        before=None if previous is None else _target_context_state(previous),
        after=_target_context_state(version),
    )
    return version


def _target_context_state(version: TargetContextVersion) -> dict[str, object]:
    return {
        "version": version.version,
        "note": version.note,
        "stances": {
            s.proposition.label: s.stance for s in version.stances.select_related("proposition")
        },
    }


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
