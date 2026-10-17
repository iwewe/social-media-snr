"""Pengambilan objek dengan otorisasi untuk view API (A3; ADR 0021).

Setiap objek diselesaikan ke investigasinya lalu diotorisasi dengan peran minimum. Tanpa akses =
404 (sama dengan id yang tidak ada); peran kurang = 403. View TIDAK boleh mengambil objek lewat
`get_object_or_404` langsung; arsitektur memeriksanya (tests/architecture)."""

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from collection.models import InspectionRun
from investigations.access import authorize
from investigations.enums import Role
from investigations.models import CollectionTarget, Investigation, Issue
from preservation.models import EvidenceArtifact


def investigation_for(user: User, pk: int, minimum: Role) -> Investigation:
    investigation = get_object_or_404(Investigation, pk=pk)
    authorize(user, investigation, minimum)
    return investigation


def issue_for(user: User, pk: int, minimum: Role) -> Issue:
    issue = get_object_or_404(Issue.objects.select_related("investigation"), pk=pk)
    authorize(user, issue.investigation, minimum)
    return issue


def target_for(user: User, pk: int, minimum: Role) -> CollectionTarget:
    target = get_object_or_404(CollectionTarget.objects.select_related("investigation"), pk=pk)
    authorize(user, target.investigation, minimum)
    return target


def run_for(user: User, pk: int, minimum: Role, *, detail: bool = False) -> InspectionRun:
    related = ["target__investigation", "requested_by"] if detail else ["target__investigation"]
    run = get_object_or_404(InspectionRun.objects.select_related(*related), pk=pk)
    authorize(user, run.target.investigation, minimum)
    return run


def artifact_for(user: User, pk: int, minimum: Role) -> EvidenceArtifact:
    artifact = get_object_or_404(
        EvidenceArtifact.objects.select_related("run__target__investigation"), pk=pk
    )
    authorize(user, artifact.run.target.investigation, minimum)
    return artifact
