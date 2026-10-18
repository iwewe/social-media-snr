"""Layanan analisis I2 (WP-2.1): membekukan dataset, membuat dan menjalankan AnalysisRun.

Tidak mengambil data dari platform (FR-041); hanya membaca observasi yang sudah tersimpan.
"""

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from collection.models import InspectionRun, PostObservation
from investigations.models import (
    CollectionTarget,
    Investigation,
    Issue,
    IssueContextVersion,
    TargetContextVersion,
)

from .digest import digest_ids, digest_json
from .errors import InvalidSelection, NothingNew
from .methods import Frozen, get_method
from .models import (
    AnalysisRun,
    AnalysisRunTargetContext,
    AnalysisStatus,
    DatasetVersion,
    DatasetVersionObservation,
)

_INGESTED = ("FINISHED", "FINISHED_WITH_PROBLEMS")
_BATCH = 1000


def _ingested(run: InspectionRun) -> bool:
    return isinstance(run.ingestion, dict) and run.ingestion.get("state") in _INGESTED


def create_dataset_version(
    *,
    investigation: Investigation,
    runs: Iterable[InspectionRun],
    by: User,
    note: str = "",
) -> DatasetVersion:
    """Bekukan semua observasi dari `runs` (satu platform, satu investigasi, ingestion selesai)."""
    run_list = list(runs)
    if not run_list:
        raise InvalidSelection("pilih minimal satu run")
    if len({r.pk for r in run_list}) != len(run_list):
        raise InvalidSelection("run ganda dalam pilihan")
    targets = {r.target_id: r.target for r in run_list}
    if any(t.investigation_id != investigation.pk for t in targets.values()):
        raise InvalidSelection("run harus milik target pada investigasi yang sama")
    platforms = {t.platform for t in targets.values()}
    if len(platforms) != 1:
        raise InvalidSelection("satu dataset hanya boleh berisi satu platform")
    if not all(_ingested(r) for r in run_list):
        raise InvalidSelection("semua run harus sudah selesai di-ingest")
    ids = list(
        PostObservation.objects.filter(run__in=run_list).order_by("id").values_list("id", flat=True)
    )
    if not ids:
        raise InvalidSelection("run terpilih tidak memiliki observasi")
    with transaction.atomic():
        Investigation.objects.select_for_update().get(pk=investigation.pk)
        number = (
            DatasetVersion.objects.filter(investigation=investigation).aggregate(m=Max("number"))[
                "m"
            ]
            or 0
        ) + 1
        dataset = DatasetVersion.objects.create(
            investigation=investigation,
            platform=platforms.pop(),
            number=number,
            observation_count=len(ids),
            observation_digest=digest_ids(ids),
            selection={
                "runs": sorted(str(r.public_id) for r in run_list),
                "targets": sorted(targets),
            },
            note=note,
            created_by=by,
        )
        DatasetVersionObservation.objects.bulk_create(
            (DatasetVersionObservation(dataset_version=dataset, observation_id=i) for i in ids),
            batch_size=_BATCH,
        )
        DatasetVersion.objects.filter(pk=dataset.pk, sealed_at__isnull=True).update(
            sealed_at=timezone.now()
        )
    dataset.refresh_from_db()
    return dataset


def latest_issue_context(issue: Issue | None) -> IssueContextVersion | None:
    return None if issue is None else issue.context_versions.order_by("-version").first()


def latest_target_contexts(dataset: DatasetVersion) -> dict[int, TargetContextVersion | None]:
    result: dict[int, TargetContextVersion | None] = {}
    for target in CollectionTarget.objects.filter(pk__in=dataset.selection["targets"]):
        result[target.pk] = target.context_versions.order_by("-version").first()
    return result


def create_analysis_run(
    *,
    dataset: DatasetVersion,
    method: str,
    parameters: dict[str, Any],
    by: User,
    issue_context_version: IssueContextVersion | None,
    target_context_versions: Mapping[int, TargetContextVersion | None],
    previous_run: AnalysisRun | None = None,
) -> AnalysisRun:
    """Buat AnalysisRun PENDING dengan masukan yang dibekukan dan eksplisit (tanpa nilai bawaan)."""
    spec = get_method(method)
    spec.validate(parameters)
    if set(target_context_versions) != set(dataset.selection["targets"]):
        raise InvalidSelection("konteks harus ditentukan (boleh None) untuk setiap target dataset")
    with transaction.atomic():
        run = AnalysisRun.objects.create(
            public_id=uuid.uuid4(),
            investigation_id=dataset.investigation_id,
            dataset_version=dataset,
            issue_context_version=issue_context_version,
            method=spec.name,
            method_version=spec.version,
            parameters=parameters,
            parameters_digest=digest_json(parameters),
            previous_run=previous_run,
            created_by=by,
        )
        AnalysisRunTargetContext.objects.bulk_create(
            AnalysisRunTargetContext(run=run, target_id=target_id, context_version=version)
            for target_id, version in target_context_versions.items()
        )
    return run


def frozen_inputs(run: AnalysisRun) -> Frozen:
    ids = tuple(
        DatasetVersionObservation.objects.filter(dataset_version_id=run.dataset_version_id)
        .order_by("observation_id")
        .values_list("observation_id", flat=True)
    )
    contexts = {
        c.target_id: (c.context_version.version if c.context_version else None)
        for c in run.target_contexts.select_related("context_version")
    }
    issue_version = run.issue_context_version.version if run.issue_context_version else None
    return Frozen(run.dataset_version.platform, ids, issue_version, contexts)


def execute_run(run: AnalysisRun) -> AnalysisRun:
    """PENDING -> RUNNING -> COMPLETED/FAILED. Keluaran dan hash-nya ditulis sekali."""
    claimed = AnalysisRun.objects.filter(pk=run.pk, status=AnalysisStatus.PENDING).update(
        status=AnalysisStatus.RUNNING, started_at=timezone.now()
    )
    if not claimed:
        raise InvalidSelection("run ini sudah dijalankan")
    run.refresh_from_db()
    try:
        output = get_method(run.method).run(frozen_inputs(run), run.parameters)
        done = {
            "status": AnalysisStatus.COMPLETED,
            "output": output,
            "output_digest": digest_json(output),
        }
    except Exception as exc:  # noqa: BLE001 - kegagalan metode dicatat, bukan disembunyikan
        done = {"status": AnalysisStatus.FAILED, "error": f"{type(exc).__name__}: {exc}"[:300]}
    AnalysisRun.objects.filter(pk=run.pk, status=AnalysisStatus.RUNNING).update(
        finished_at=timezone.now(), **done
    )
    run.refresh_from_db()
    return run


def reanalyze(previous: AnalysisRun, *, by: User, use_latest_context: bool = False) -> AnalysisRun:
    """Analisis ulang pada data terbaru (FR-041, alur B): dataset dan run BARU; yang lama utuh.

    Metode dan parameter sama. Konteks sama dengan run sebelumnya kecuali `use_latest_context=True`.
    """
    old = previous.dataset_version
    runs = list(
        InspectionRun.objects.filter(
            target_id__in=old.selection["targets"], ingestion__state__in=_INGESTED
        ).order_by("target_id", "sequence")
    )
    current = PostObservation.objects.filter(run__in=runs).values_list("id", flat=True)
    if digest_ids(current) == old.observation_digest:
        raise NothingNew("tidak ada observasi baru dibanding dataset sebelumnya")
    dataset = create_dataset_version(
        investigation=previous.investigation,
        runs=runs,
        by=by,
        note=f"Analisis ulang dari dataset {old.number}",
    )
    if use_latest_context:
        issue_ctx = latest_issue_context(
            previous.issue_context_version.issue if previous.issue_context_version else None
        )
        targets = latest_target_contexts(dataset)
    else:
        issue_ctx = previous.issue_context_version
        targets = {
            c.target_id: c.context_version
            for c in previous.target_contexts.select_related("context_version")
        }
        for target_id in dataset.selection["targets"]:
            targets.setdefault(target_id, None)
    return create_analysis_run(
        dataset=dataset,
        method=previous.method,
        parameters=previous.parameters,
        by=by,
        issue_context_version=issue_ctx,
        target_context_versions=targets,
        previous_run=previous,
    )
