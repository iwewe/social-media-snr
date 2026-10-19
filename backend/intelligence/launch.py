"""Memulai analisis dari antarmuka/API (WP-2.9; ADR 0041).

Semua parameter WAJIB eksplisit dan disimpan pada AnalysisRun (ADR 0024: tanpa nilai bawaan
tersembunyi); nilai contoh hanya diisi pengguna lewat tombol "contoh eksplorasi" dan tetap
dikirim eksplisit. Run dibuat PENDING di dalam transaksi bersama catatan audit, lalu dikirim ke
antrean `analysis` setelah commit; gagal mengirim menandai run FAILED (tidak menggantung
PENDING). Eksekusi dilakukan worker (`intelligence.tasks`), bukan proses web.
"""

import logging
from datetime import datetime
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from audit import services as audit
from audit.models import AuditAction, SubjectType
from investigations.models import Investigation, Proposition

from . import coordination_runs, profiles, services
from .errors import InvalidParameters
from .examples import CO_EXAMPLE
from .m2.example_rules import example_parameters
from .models import AnalysisRun, AnalysisStatus, DatasetVersion
from .networks import network_parameters

logger = logging.getLogger(__name__)

METHODS = ("m2-rules", "m3-profile", "m4-network", "co-indicators")
MAX_CUES = 100
MAX_CUE_CHARS = 200

_M3_INTS = ("min_responses", "bucket_hours", "min_active_buckets", "narrative_min_texts")
_M4_KEYS = (
    "window_start",
    "window_end",
    "unknown_time",
    "relation_types",
    "weighting",
    "resolution",
    "seed",
    "compute_betweenness",
    "metrics_max_nodes",
    "stability_seeds",
)


def _exact(data: dict[str, Any], keys: set[str], where: str) -> None:
    if set(data) != keys:
        raise InvalidParameters(f"{where}: field wajib tepat {sorted(keys)}")


def _time(data: dict[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(data[key]))
    except ValueError:
        raise InvalidParameters(f"{key} bukan waktu ISO-8601") from None
    if value.tzinfo is None:
        raise InvalidParameters(f"{key} wajib memuat zona waktu")
    return value


def _cues(data: dict[str, Any], key: str) -> list[str]:
    raw = data[key]
    if not isinstance(raw, list) or not all(isinstance(c, str) for c in raw):
        raise InvalidParameters(f"{key} harus daftar teks")
    cues = list(dict.fromkeys(c.strip() for c in raw if c.strip()))
    if len(cues) > MAX_CUES or any(len(c) > MAX_CUE_CHARS for c in cues):
        raise InvalidParameters(
            f"{key}: maksimum {MAX_CUES} cue, masing-masing {MAX_CUE_CHARS} karakter"
        )
    return cues


def _proposition(investigation: Investigation, proposition_id: int | None) -> Proposition:
    if proposition_id is None:
        raise InvalidParameters("proposition wajib untuk metode ini")
    proposition = (
        Proposition.objects.filter(pk=proposition_id, issue__investigation=investigation)
        .select_related("issue")
        .first()
    )
    if proposition is None:
        raise InvalidParameters("proposition tidak ditemukan pada investigasi ini")
    return proposition


def _source_run(
    investigation: Investigation, dataset: DatasetVersion, source_run_id: int | None
) -> AnalysisRun:
    source = (
        AnalysisRun.objects.filter(pk=source_run_id, investigation=investigation).first()
        if source_run_id is not None
        else None
    )
    if (
        source is None
        or not source.method.startswith("m2-")
        or source.status != AnalysisStatus.COMPLETED
        or source.dataset_version_id != dataset.pk
    ):
        raise InvalidParameters("run M2 sumber harus selesai dan memakai dataset yang sama")
    return source


def build_parameters(
    *,
    investigation: Investigation,
    dataset: DatasetVersion,
    method: str,
    data: dict[str, Any],
    proposition_id: int | None,
    source_run_id: int | None,
) -> tuple[dict[str, Any], Proposition | None]:
    """Susun parameter run dari masukan eksplisit; kembalikan (parameter, proposition atau None)."""
    if method not in METHODS:
        raise InvalidParameters(f"metode harus salah satu dari {list(METHODS)}")
    if dataset.investigation_id != investigation.pk:
        raise InvalidParameters("dataset bukan milik investigasi ini")
    if method == "m2-rules":
        _exact(data, {"pro_cues", "contra_cues"}, "parameters")
        proposition = _proposition(investigation, proposition_id)
        pro, contra = _cues(data, "pro_cues"), _cues(data, "contra_cues")
        if not pro and not contra:
            raise InvalidParameters(
                "isi minimal satu cue pro atau kontra (ditulis analis, tanpa bawaan)"
            )
        return example_parameters({proposition.pk: (pro, contra)}), proposition
    if method == "m3-profile":
        _exact(data, {"period_start", "period_end", *_M3_INTS}, "parameters")
        proposition = _proposition(investigation, proposition_id)
        source = _source_run(investigation, dataset, source_run_id)
        return (
            profiles.m3_parameters(
                source_run=source,
                proposition=proposition,
                period_start=_time(data, "period_start"),
                period_end=_time(data, "period_end"),
                **{k: data[k] for k in _M3_INTS},
            ),
            proposition,
        )
    if method == "m4-network":
        _exact(data, set(_M4_KEYS), "parameters")
        m4_proposition: Proposition | None = None
        m4_source: AnalysisRun | None = None
        if (proposition_id is None) != (source_run_id is None):
            raise InvalidParameters(
                "proposition dan run M2 sumber harus diisi keduanya atau tidak sama sekali"
            )
        if proposition_id is not None:
            m4_proposition = _proposition(investigation, proposition_id)
            m4_source = _source_run(investigation, dataset, source_run_id)
        return (
            network_parameters(
                window_start=_time(data, "window_start"),
                window_end=_time(data, "window_end"),
                source_run=m4_source,
                proposition=m4_proposition,
                **{k: data[k] for k in _M4_KEYS if k not in ("window_start", "window_end")},
            ),
            m4_proposition,
        )
    _exact(data, {"window_start", "window_end", *CO_EXAMPLE}, "parameters")
    return (
        coordination_runs.coordination_parameters(
            window_start=_time(data, "window_start"),
            window_end=_time(data, "window_end"),
            **{k: data[k] for k in CO_EXAMPLE},
        ),
        None,
    )


def enqueue(run_pk: int) -> None:
    """Kirim ke antrean `analysis`; bila tak tersedia, run ditandai FAILED (tidak menggantung)."""
    from .tasks import execute_analysis

    try:
        execute_analysis.apply_async(args=(run_pk,), queue="analysis")
    except Exception:  # noqa: BLE001 - antrean tak tersedia: jangan biarkan run menggantung PENDING
        logger.exception("Gagal mengirim analisis %s ke antrean", run_pk)
        AnalysisRun.objects.filter(pk=run_pk, status=AnalysisStatus.PENDING).update(
            status=AnalysisStatus.FAILED,
            finished_at=timezone.now(),
            error="AntreanTidakTersedia: analisis tidak dikirim ke worker",
        )


def _audit_creation(
    run: AnalysisRun, by: User, *, reanalysis_of: AnalysisRun | None = None
) -> None:
    audit.record(
        investigation_id=run.investigation_id,
        actor=by,
        action=AuditAction.ANALYSIS_RUN,
        subject_type=SubjectType.ANALYSIS_RUN,
        subject_id=run.pk,
        before=None
        if reanalysis_of is None
        else {
            "analysis_run_id": reanalysis_of.pk,
            "dataset_number": reanalysis_of.dataset_version.number,
        },
        after={
            "analysis_run_id": run.pk,
            "method": run.method,
            "method_version": run.method_version,
            "dataset_number": run.dataset_version.number,
            "parameters_digest": run.parameters_digest,
        },
    )


def launch(
    *,
    investigation: Investigation,
    by: User,
    dataset: DatasetVersion,
    method: str,
    data: dict[str, Any],
    proposition_id: int | None = None,
    source_run_id: int | None = None,
) -> AnalysisRun:
    parameters, proposition = build_parameters(
        investigation=investigation,
        dataset=dataset,
        method=method,
        data=data,
        proposition_id=proposition_id,
        source_run_id=source_run_id,
    )
    with transaction.atomic():
        run = services.create_analysis_run(
            dataset=dataset,
            method=method,
            parameters=parameters,
            by=by,
            issue_context_version=services.latest_issue_context(
                proposition.issue if proposition else None
            ),
            target_context_versions=services.latest_target_contexts(dataset),
        )
        _audit_creation(run, by)
        transaction.on_commit(lambda: enqueue(run.pk))
    return run


def launch_reanalysis(*, previous: AnalysisRun, by: User, use_latest_context: bool) -> AnalysisRun:
    """Analisis ulang pada data terbaru (FR-041): dataset dan run baru, yang lama utuh."""
    with transaction.atomic():
        run = services.reanalyze(previous, by=by, use_latest_context=use_latest_context)
        _audit_creation(run, by, reanalysis_of=previous)
        transaction.on_commit(lambda: enqueue(run.pk))
    return run
