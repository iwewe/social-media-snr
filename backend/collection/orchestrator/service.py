"""Orchestrator inspeksi (WP-1.6; FR-020, FR-021, FR-025, FR-026; PRD bagian 9.1).

Alur satu run: klaim (PENDING -> RUNNING) -> adapter -> ingestion (+ artefak lewat penyaring
rahasia) -> status akhir -> rekonsiliasi. Prinsip yang dijaga:

- AT-MOST-ONCE: klaim adalah satu UPDATE bersyarat (`WHERE status = 'PENDING'`). Pengiriman ganda
  atau percobaan ulang Celery menemukan run bukan PENDING dan tidak menjalankan adapter lagi.
  Run yang ditinggal mati pekerja berstatus RUNNING sampai penyapu menandainya; pemeriksaan
  ulang dilakukan lewat run BARU (alur B), bukan dengan menghidupkan run lama.
- TIDAK ADA SUKSES PALSU: COMPLETED hanya bila adapter menyatakan COMPLETED DAN ingestion serta
  penyimpanan artefak bersih. Masalah yang belum ditangani menghasilkan REVIEW_REQUIRED beserta
  alasannya (FR-026, AT-14); kegagalan adapter tidak pernah tampak sebagai "nol respons".
- Kegagalan buatan orchestrator (tidak ada adapter, galat adapter, URL tidak dikenal) dikonversi
  menjadi InspectionResult gagal dan melewati jalur ingestion yang sama, sehingga keterbatasan dan
  status ingestion tercatat seragam.
- Galat tak terduga tidak ditelan: dilog di sisi server; ke run hanya jenis galat dan keterangan
  generik (pesan galat dapat memuat isi).
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from collection import services
from collection.contracts import (
    Capability,
    CollectorInfo,
    ContractViolation,
    Coverage,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    Limitation,
    LimitationCode,
)
from collection.ingestion import IngestionReport, ingest_result
from collection.models import InspectionRun, PostObservation, RunStatus
from collection.reconciliation import reconcile_run
from collection.reconciliation.service import BLOCKING_PROBLEM_CODES
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL
from investigations.models import CollectionTarget

from .registry import registry
from .states import OUTCOME_STATUSES, can_transition

logger = logging.getLogger(__name__)

ORCHESTRATOR = CollectorInfo("snr-orchestrator", "1")
DEFAULT_QUEUE = "analysis"
_ARTIFACT_PROBLEM_CODES = {"ARTIFACT_PERSISTENCE_FAILED", "ARTIFACT_PERSISTENCE_PROBLEMS"}
_DEFAULT_SCOPE = {
    TargetType.POST: [Capability.INSPECT_POST, Capability.INSPECT_REPLIES],
    TargetType.ACCOUNT: [Capability.INSPECT_ACCOUNT],
}


class OrchestrationError(Exception):
    """Pelanggaran aturan orkestrasi (mis. meninjau run yang tidak memerlukan tinjauan)."""


@dataclass(frozen=True)
class ExecutionResult:
    run_id: int
    handled: bool  # False = run sudah diklaim/selesai (tidak dijalankan lagi)
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "handled": self.handled,
            "status": self.status,
            "reasons": self.reasons,
        }


# --- permintaan inspeksi ("Inspect" / "Inspect Again") -------------------------------------------


def request_inspection(
    *,
    target: CollectionTarget,
    user: AbstractBaseUser,
    requested: list[Capability | str] | None = None,
    enqueue: bool = True,
) -> InspectionRun:
    """Buat run baru untuk TARGET yang sama dan kirim ke antrean adapternya.

    Pemeriksaan ulang menambah run, bukan target baru (alur B, AT-01). Pengiriman memakai
    `transaction.on_commit` agar pekerja tidak melihat run sebelum tersimpan."""
    scope = requested or _DEFAULT_SCOPE[TargetType(target.target_type)]
    run = services.create_inspection_run(target=target, user=user, requested=scope)
    if enqueue:
        queue = _queue_for(target.platform)
        transaction.on_commit(lambda: _enqueue_or_fail(run.pk, queue))
    return run


def _queue_for(platform: str) -> str:
    adapter = registry.get(Platform(platform))
    return adapter.execution_queue if adapter is not None else DEFAULT_QUEUE


def _enqueue_or_fail(run_pk: int, queue: str) -> None:
    from collection.tasks import execute_inspection

    try:
        execute_inspection.apply_async(args=[run_pk], queue=queue)
    except Exception:  # noqa: BLE001 - antrean tak tersedia: jangan biarkan run menggantung PENDING
        logger.exception("Gagal mengirim run %s ke antrean %s", run_pk, queue)
        _fail_pending(
            run_pk, LimitationCode.NETWORK_ERROR, "antrean tidak tersedia; run tidak dikirim"
        )


def _fail_pending(run_pk: int, code: LimitationCode, message: str) -> None:
    now = timezone.now()
    InspectionRun.objects.filter(pk=run_pk, status=RunStatus.PENDING).update(
        status=RunStatus.FAILED,
        finished_at=now,
        limitations=[{"code": code.value, "message": message, "capability": None}],
        coverage=_minimal_coverage(None, RunStatus.FAILED),
        ingestion=_empty_ingestion("tidak pernah dijalankan"),
    )


# --- eksekusi ----------------------------------------------------------------------------------


def _claim(run_pk: int, claimed_by: str) -> bool:
    updated = InspectionRun.objects.filter(pk=run_pk, status=RunStatus.PENDING).update(
        status=RunStatus.RUNNING, started_at=timezone.now(), claimed_by=claimed_by[:200]
    )
    return updated == 1


def _finalize(run_pk: int, status: str, **fields: Any) -> bool:
    """Pindahkan RUNNING -> `status` secara atomik (UPDATE bersyarat); False bila run berubah."""
    assert can_transition(RunStatus.RUNNING, status), (RunStatus.RUNNING, status)
    updated = InspectionRun.objects.filter(pk=run_pk, status=RunStatus.RUNNING).update(
        status=status, finished_at=timezone.now(), **fields
    )
    if updated != 1:
        logger.warning("Run %s tidak lagi RUNNING saat difinalkan menjadi %s", run_pk, status)
    return updated == 1


def _minimal_coverage(run: InspectionRun | None, status: str) -> dict[str, Any]:
    return {
        "scope": list(run.requested) if run else [],
        "pagination_complete": None,
        "platform_displayed_count": None,
        "observed_reply_count": 0,
        "observed_object_count": 0,
        "notes": [],
        "outcome": status,
        "confirmed_unavailable": [],
    }


def _empty_ingestion(note: str) -> dict[str, Any]:
    return {
        "state": "FINISHED",
        "finished_at": timezone.now().isoformat(),
        "note": note,
        "report": {
            "observations_received": 0,
            "observations_created": 0,
            "ok": True,
            "failed_batches": [],
            "problems": [],
        },
    }


def _failure_result(
    run: InspectionRun,
    outcome: InspectionOutcome,
    code: LimitationCode,
    message: str,
    collector: CollectorInfo = ORCHESTRATOR,
) -> InspectionResult:
    """Hasil gagal buatan orchestrator, agar melewati jalur ingestion yang sama (FR-026)."""
    return InspectionResult(
        platform=Platform(run.target.platform),
        inspection_run_id=run.run_id,
        outcome=outcome,
        collector=collector,
        coverage=Coverage(
            scope=tuple(Capability(c) for c in run.requested), pagination_complete=None
        ),
        limitations=(Limitation(code, message),),
    )


def _call_adapter(run: InspectionRun) -> InspectionResult:
    adapter = registry.get(Platform(run.target.platform))
    if adapter is None:
        return _failure_result(
            run,
            InspectionOutcome.UNSUPPORTED,
            LimitationCode.UNSUPPORTED,
            f"tidak ada adapter terdaftar untuk platform {run.target.platform}",
        )
    collector = adapter.collector
    try:
        info = adapter.validate_target_url(run.target.normalized_url)
    except InvalidTargetURL:
        return _failure_result(
            run,
            InspectionOutcome.UNSUPPORTED,
            LimitationCode.UNSUPPORTED,
            "URL target tidak dikenali oleh adapter platform ini",
            collector,
        )
    request = InspectionRequest(
        inspection_run_id=run.run_id,
        platform=Platform(run.target.platform),
        target_url=info.normalized_url,
        target_type=info.target_type,
        requested=tuple(Capability(c) for c in run.requested),
        target_external_id=info.external_id,
    )
    try:
        return adapter.inspect(request)
    except SoftTimeLimitExceeded:
        return _failure_result(
            run,
            InspectionOutcome.FAILED,
            LimitationCode.TIMEOUT,
            "melampaui batas waktu eksekusi",
            collector,
        )
    except ContractViolation as exc:
        logger.exception("Adapter %s melanggar kontrak pada run %s", type(adapter).__name__, run.pk)
        return _failure_result(
            run,
            InspectionOutcome.FAILED,
            LimitationCode.ADAPTER_ERROR,
            f"adapter melanggar kontrak: {str(exc)[:200]}",
            collector,
        )
    except Exception as exc:  # noqa: BLE001 - bug adapter: dilog; ke run hanya jenis galat
        logger.exception("Adapter %s gagal pada run %s", type(adapter).__name__, run.pk)
        return _failure_result(
            run,
            InspectionOutcome.FAILED,
            LimitationCode.ADAPTER_ERROR,
            f"galat tak terduga pada adapter ({type(exc).__name__})",
            collector,
        )


def _review_reasons(report: IngestionReport) -> list[str]:
    reasons: list[str] = []
    if report.failed_batches:
        reasons.append("ingestion_failed_batches")
    for code in sorted(report.problem_codes() & BLOCKING_PROBLEM_CODES):
        reasons.append(f"ingestion_{code.lower()}")
    if report.problem_codes() & _ARTIFACT_PROBLEM_CODES:
        reasons.append("artifact_persistence_problems")
    if "ARTIFACTS_NOT_PERSISTED" in report.problem_codes():
        reasons.append("artifacts_not_persisted")
    if "MIXED_SOURCE_METHODS" in report.problem_codes():
        reasons.append("mixed_source_methods")
    return reasons


def run_inspection(run_pk: int, *, claimed_by: str = "") -> ExecutionResult:
    """Jalankan satu run. Aman dipanggil berulang: hanya pemanggil pertama yang mengeksekusi."""
    if not _claim(run_pk, claimed_by):
        current = InspectionRun.objects.filter(pk=run_pk).values_list("status", flat=True).first()
        logger.info("Run %s dilewati: status %s", run_pk, current)
        return ExecutionResult(run_pk, handled=False, status=current or "MISSING")

    from preservation.service import make_artifact_sink

    run = InspectionRun.objects.select_related("target").get(pk=run_pk)
    result = _call_adapter(run)
    try:
        report = ingest_result(run, result, artifact_sink=make_artifact_sink())
    except SoftTimeLimitExceeded:
        return _finalize_review(run, result, ["ingestion_timeout"])
    except Exception:  # noqa: BLE001 - ingestion gagal total: tinjau, jangan klaim sukses
        logger.exception("Ingestion gagal pada run %s", run_pk)
        return _finalize_review(run, result, ["ingestion_exception"])

    reasons = _review_reasons(report)
    if reasons:
        return _finalize_review(run, result, reasons)

    status = RunStatus(result.outcome.value)
    _finalize(run_pk, status)
    if status in (RunStatus.COMPLETED, RunStatus.PARTIAL):
        _reconcile_safely(run)
    return ExecutionResult(run_pk, handled=True, status=status.value)


def _finalize_review(
    run: InspectionRun, result: InspectionResult, reasons: list[str]
) -> ExecutionResult:
    review = {"reasons": reasons, "outcome": result.outcome.value, "acknowledged": None}
    _finalize(run.pk, RunStatus.REVIEW_REQUIRED, review=review)
    return ExecutionResult(
        run.pk, handled=True, status=RunStatus.REVIEW_REQUIRED.value, reasons=reasons
    )


def _reconcile_safely(run: InspectionRun) -> None:
    try:
        fresh = InspectionRun.objects.get(pk=run.pk)
        reconcile_run(fresh)
    except Exception as exc:  # noqa: BLE001 - rekonsiliasi dapat diulang; jangan jatuhkan run
        logger.exception("Rekonsiliasi gagal pada run %s", run.pk)
        InspectionRun.objects.filter(pk=run.pk).update(
            reconciliation={
                "state": "ERROR",
                "reason": type(exc).__name__,
                "reconciled_at": timezone.now().isoformat(),
            }
        )


# --- penyapu run yang menggantung --------------------------------------------------------------


def sweep_stale_runs(*, older_than_seconds: int | None, now: Any = None) -> list[int]:
    """Tandai run RUNNING yang melewati batas waktu (pekerja mati/macet) agar tidak menggantung.

    Batas waktu WAJIB ditetapkan eksplisit (PRD tidak menetapkan angka; harus diukur). Run dengan
    observasi menjadi PARTIAL, tanpa observasi menjadi FAILED; keduanya dengan keterbatasan TIMEOUT.
    Penanda ingestion IN_PROGRESS yang tertinggal tidak dihapus, sehingga rekonsiliasi tetap
    menolak run itu. Memakai UPDATE bersyarat: run yang selesai bersamaan tidak ditimpa."""
    if older_than_seconds is None or older_than_seconds <= 0:
        raise ValueError("older_than_seconds wajib berupa angka positif yang ditetapkan eksplisit")
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=older_than_seconds)
    swept: list[int] = []
    for run in InspectionRun.objects.filter(status=RunStatus.RUNNING, started_at__lt=cutoff):
        has_data = PostObservation.objects.filter(run=run).exists()
        status = RunStatus.PARTIAL if has_data else RunStatus.FAILED
        limitations = list(run.limitations or []) + [
            {
                "code": LimitationCode.TIMEOUT.value,
                "capability": None,
                "message": "pekerja berhenti sebelum run selesai (dihentikan penyapu)",
            }
        ]
        fields: dict[str, Any] = {"limitations": limitations}
        if run.coverage is None:
            fields["coverage"] = _minimal_coverage(run, status)
        if run.ingestion is None:
            fields["ingestion"] = _empty_ingestion("run dihentikan penyapu sebelum ingestion")
        updated = InspectionRun.objects.filter(pk=run.pk, status=RunStatus.RUNNING).update(
            status=status, finished_at=now, **fields
        )
        if updated:
            swept.append(run.pk)
    return swept


# --- tinjauan manusia --------------------------------------------------------------------------


def acknowledge_review(
    *, run: InspectionRun, user: AbstractBaseUser, note: str = ""
) -> InspectionRun:
    """Akui tinjauan: REVIEW_REQUIRED kembali ke hasil adapter yang tercatat di run.

    Tidak mengubah data run; hanya mencatat siapa, kapan, dan catatan peninjau."""
    run.refresh_from_db()
    if run.status != RunStatus.REVIEW_REQUIRED or not run.review:
        raise OrchestrationError("Run ini tidak sedang menunggu tinjauan.")
    outcome = RunStatus(run.review["outcome"])
    if outcome not in OUTCOME_STATUSES or not can_transition(RunStatus.REVIEW_REQUIRED, outcome):
        raise OrchestrationError("Hasil tercatat tidak sah untuk diakui.")
    review = dict(run.review)
    review["acknowledged"] = {
        "by": user.get_username(),
        "at": timezone.now().isoformat(),
        "note": note,
    }
    updated = InspectionRun.objects.filter(pk=run.pk, status=RunStatus.REVIEW_REQUIRED).update(
        status=outcome, review=review
    )
    if updated != 1:
        raise OrchestrationError("Status run berubah saat diakui.")
    run.refresh_from_db()
    return run
