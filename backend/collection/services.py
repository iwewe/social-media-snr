"""Layanan penulisan pengumpulan data. Pembuatan run lewat sini agar nomor urut tidak balapan."""

from collections.abc import Iterable

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import Max

from collection.contracts.enums import Capability
from collection.contracts.errors import ContractViolation
from investigations.models import CollectionTarget

from .models import InspectionRun


@transaction.atomic
def create_inspection_run(
    *,
    target: CollectionTarget,
    user: AbstractBaseUser,
    requested: Iterable[Capability | str],
) -> InspectionRun:
    """Buat run baru untuk target yang sama (reinspection tidak membuat target baru, AT-01)."""
    try:
        caps = [Capability(c).value for c in requested]
    except ValueError as exc:
        raise ContractViolation(f"Kemampuan tidak dikenal: {exc}") from None
    if not caps:
        raise ContractViolation("Run harus meminta setidaknya satu kemampuan.")
    if len(set(caps)) != len(caps):
        raise ContractViolation("Kemampuan yang diminta tidak boleh ganda.")

    CollectionTarget.objects.select_for_update().get(pk=target.pk)
    latest = InspectionRun.objects.filter(target=target).aggregate(m=Max("sequence"))["m"] or 0
    return InspectionRun.objects.create(
        target=target,
        sequence=latest + 1,
        requested=caps,
        requested_by=user,  # type: ignore[misc]
    )
