"""Bentuk JSON run inspeksi, observasi per run, dan artefak (WP-1.9a; FR-090, FR-095, NFR-08).

Prinsip:
- Whitelist eksplisit: tidak ada kolom internal (identitas pekerja, jalur berkas, laporan mentah)
  yang bocor ke antarmuka.
- `None` tetap `null`: "tidak diketahui" tidak pernah menjadi string kosong atau nol.
- `data_state` dihitung SERVER-side agar UI membedakan keadaan data secara konsisten (NFR-08).
"""

from typing import Any

from django.db.models import F, QuerySet

from collection.models import (
    InspectionRun,
    ObservationReconciliation,
    PostObservation,
    PostRelation,
    RunStatus,
)
from preservation.models import ArtifactVerification, EvidenceArtifact

from .messages import (
    INTEGRITY_STATEMENT,
    MANIFEST_MESSAGES,
    VERIFICATION_MESSAGES,
    Message,
    run_messages,
)

# Keadaan data (NFR-08 + keadaan operasional):
NOT_INSPECTED = "not_inspected"  # belum pernah ada run
IN_PROGRESS = "in_progress"  # run menunggu/berjalan
HAS_DATA = "has_data"  # selesai dan ada balasan teramati
NO_DATA = "no_data"  # selesai penuh; platform dapat diakses; tidak ada balasan
PARTIAL = "partial"  # hanya sebagian terbaca (nol balasan di sini BUKAN "tidak ada data")
ACCESS_FAILED = "access_failed"  # gagal mengakses (ditolak, gagal, tidak didukung)
NEEDS_REVIEW = "needs_review"  # data ada tetapi perlu ditinjau manusia

PENDING_STATUSES = (RunStatus.PENDING, RunStatus.RUNNING)


def data_state(run: InspectionRun | None) -> str:
    if run is None:
        return NOT_INSPECTED
    status = run.status
    if status in PENDING_STATUSES:
        return IN_PROGRESS
    if status in (RunStatus.ACCESS_RESTRICTED, RunStatus.FAILED, RunStatus.UNSUPPORTED):
        return ACCESS_FAILED
    if status == RunStatus.REVIEW_REQUIRED:
        return NEEDS_REVIEW
    if status == RunStatus.PARTIAL:
        return PARTIAL
    observed = (run.coverage or {}).get("observed_reply_count")
    return NO_DATA if observed == 0 else HAS_DATA


def coverage_repr(coverage: dict[str, Any] | None) -> dict[str, Any] | None:
    if coverage is None:
        return None
    return {
        "scope": list(coverage.get("scope", [])),
        "pagination_complete": coverage.get("pagination_complete"),
        # Dua angka yang berbeda (PRD 9.3): jangan pernah digabung.
        "platform_displayed_count": coverage.get("platform_displayed_count"),
        "observed_reply_count": coverage.get("observed_reply_count"),
        "observed_object_count": coverage.get("observed_object_count"),
        "notes": list(coverage.get("notes", [])),
        "outcome": coverage.get("outcome"),
    }


def _ingestion_repr(ingestion: dict[str, Any] | None) -> dict[str, Any] | None:
    if ingestion is None:
        return None
    report = ingestion.get("report") or {}
    return {
        "state": ingestion.get("state"),
        "observations_received": report.get("observations_received"),
        "observations_created": report.get("observations_created"),
        "failed_batches": len(report.get("failed_batches", [])),
        "problem_codes": sorted({p.get("code") for p in report.get("problems", [])}),
    }


def _reconciliation_repr(rec: dict[str, Any] | None) -> dict[str, Any] | None:
    if rec is None:
        return None
    return {
        "state": rec.get("state"),
        "counts": dict(rec.get("counts", {})),
        "baseline_run_count": len(rec.get("baseline_runs", [])),
    }


def _preservation_repr(pres: dict[str, Any] | None) -> dict[str, Any] | None:
    if pres is None:
        return None
    report = pres.get("report") or {}
    return {
        "state": pres.get("state"),
        "stored": report.get("stored"),
        "rejected_count": len(report.get("rejected", [])),
        "failed_count": len(report.get("failed", [])),
    }


def _review_repr(review: dict[str, Any] | None) -> dict[str, Any] | None:
    if review is None:
        return None
    return {
        "reasons": list(review.get("reasons", [])),
        "outcome": review.get("outcome"),
        "acknowledged": review.get("acknowledged"),
    }


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def run_repr(run: InspectionRun, *, messages: list[Message] | None = None) -> dict[str, Any]:
    msgs = run_messages(run) if messages is None else messages
    return {
        "id": run.pk,
        "target_id": run.target_id,
        "sequence": run.sequence,
        "status": run.status,
        "data_state": data_state(run),
        "requested": list(run.requested),
        "requested_by": run.requested_by.get_username(),
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "collector": {"name": run.collector_name, "version": run.collector_version}
        if run.collector_name
        else None,
        "source_method": run.source_method or None,
        "coverage": coverage_repr(run.coverage),
        "limitations": [
            {
                "code": item.get("code"),
                "message": item.get("message"),
                "capability": item.get("capability"),
            }
            for item in (run.limitations or [])
        ],
        "ingestion": _ingestion_repr(run.ingestion),
        "reconciliation": _reconciliation_repr(run.reconciliation),
        "preservation": _preservation_repr(run.preservation),
        "review": _review_repr(run.review),
        "messages": [m.to_dict() for m in msgs],
    }


def run_detail(run: InspectionRun) -> dict[str, Any]:
    target = run.target
    return {
        **run_repr(run),
        # Cukup untuk judul halaman dan tautan kembali; tanpa catatan konteks target.
        "target": {
            "id": target.pk,
            "platform": target.platform,
            "target_type": target.target_type,
            "normalized_url": target.normalized_url,
            "investigation_id": target.investigation_id,
        },
        "artifacts": [artifact_repr(a) for a in run.artifacts.all()],
    }


def verification_repr(v: ArtifactVerification) -> dict[str, Any]:
    """Hasil verifikasi hash. Tanpa jalur berkas; pesan dari kode hasil, bukan teks bebas."""
    return {
        "id": v.pk,
        "artifact_id": v.artifact_id,
        "result": v.result,
        "purpose": v.purpose,
        "verified_at": _iso(v.verified_at),
        "verified_by": v.verified_by.get_username(),
        "expected_sha256": v.expected_sha256,
        "actual_sha256": v.actual_sha256,
        "expected_size_bytes": v.expected_size,
        "actual_size_bytes": v.actual_size,
        "message": VERIFICATION_MESSAGES[v.result].to_dict(),
        "statement": INTEGRITY_STATEMENT,
    }


def run_verification_repr(outcome: dict[str, Any]) -> dict[str, Any]:
    manifest = outcome["manifest"]
    return {
        "all_match": outcome["all_match"],
        "summary": outcome["summary"],
        "verifications": [verification_repr(v) for v in outcome["verifications"]],
        "manifest": {
            "state": manifest["state"],
            "problems": manifest["problems"],
            "message": MANIFEST_MESSAGES[manifest["state"]].to_dict(),
        },
        "statement": INTEGRITY_STATEMENT,
    }


def artifact_repr(a: EvidenceArtifact) -> dict[str, Any]:
    # Tanpa jalur berkas (internal). Verifikasi dan unduhan lewat endpoint khusus (WP-1.10).
    last = (
        ArtifactVerification.objects.filter(artifact=a)
        .select_related("verified_by")
        .order_by("-id")
        .first()
    )
    return {
        "last_verification": None
        if last is None
        else {
            "result": last.result,
            "verified_at": _iso(last.verified_at),
            "verified_by": last.verified_by.get_username(),
            "purpose": last.purpose,
        },
        "id": a.pk,
        "kind": a.kind,
        "sha256": a.sha256,
        "size_bytes": a.size_bytes,
        "content_type": a.content_type,
        "stored_at": _iso(a.stored_at),
        "post_id": a.post_id,
    }


def latest_inspection_summary(target: Any) -> dict[str, Any] | None:
    """Ringkasan run terakhir untuk kartu target; None bila belum pernah diperiksa."""
    run = target.runs.select_related("requested_by").order_by("-sequence").first()
    if run is None:
        return None
    messages = run_messages(run)
    return {
        "id": run.pk,
        "sequence": run.sequence,
        "status": run.status,
        "data_state": data_state(run),
        "finished_at": _iso(run.finished_at),
        "created_at": _iso(run.created_at),
        "coverage": coverage_repr(run.coverage),
        "headline": messages[0].to_dict() if messages else None,
        "run_count": target.runs.count(),
    }


# --- daftar respons mentah per run ----------------------------------------------------------

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


def _row(
    obs: PostObservation,
    *,
    reconciliation: ObservationReconciliation | None,
    parents: dict[int, str | None],
    artifact_ids: dict[int, list[int]],
    observed_here: bool,
    last_seen_sequence: int | None,
) -> dict[str, Any]:
    post = obs.post
    author = obs.author
    return {
        "post_id": post.pk,
        "external_post_id": post.external_post_id,  # None = kandidat tanpa ID
        "identity_status": post.identity_status,
        "object_type": obs.source_object_type,
        "reconciliation": reconciliation.status if reconciliation else None,
        "changed_fields": list(reconciliation.changed_fields) if reconciliation else [],
        "evidence": (reconciliation.evidence or None) if reconciliation else None,
        "observed_in_this_run": observed_here,
        "last_seen_run_sequence": last_seen_sequence,
        "author": {
            "external_actor_id": author.external_actor_id if author else None,
            "handle": obs.actor_handle,  # informasi, bukan identitas
            "display_name": obs.actor_display_name,
            "needs_verification": obs.identity_needs_verification,
        },
        "text": obs.text,
        "published_at": _iso(obs.published_at),  # null = tidak diketahui
        "observed_at": _iso(obs.observed_at) if observed_here else None,
        "parent_external_post_id": parents.get(post.pk),
        "parent_unknown": obs.parent_unknown,
        "collection_status": obs.collection_status,
        "artifact_ids": artifact_ids.get(post.pk, []),
    }


def _parents(run: InspectionRun, post_ids: list[int]) -> dict[int, str | None]:
    rows = PostRelation.objects.filter(
        run=run, relation_type="reply_to", from_post_id__in=post_ids
    ).select_related("to_post")
    return {r.from_post_id: (r.to_post.external_post_id if r.to_post else None) for r in rows}


def _artifacts_by_post(run: InspectionRun, post_ids: list[int]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for art_id, post_id in EvidenceArtifact.objects.filter(
        run=run, post_id__in=post_ids
    ).values_list("id", "post_id"):
        out.setdefault(post_id, []).append(art_id)
    return out


def observation_page(run: InspectionRun, *, page: int, page_size: int) -> dict[str, Any]:
    """Satu halaman respons mentah untuk `run`. Bila rekonsiliasi selesai, baris NOT_OBSERVED
    (terlihat sebelumnya, tidak pada run ini) ikut ditampilkan dengan data terakhir terlihat."""
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    page = max(1, page)
    offset = (page - 1) * page_size
    reconciled = (run.reconciliation or {}).get("state") == "DONE"

    if reconciled:
        qs: QuerySet[ObservationReconciliation] = (
            ObservationReconciliation.objects.filter(run=run)
            .select_related(
                "post",
                "current_observation__author",
                "current_observation__post",
                "previous_observation__author",
                "previous_observation__post",
                "previous_observation__run",
            )
            .order_by(F("current_observation_id").asc(nulls_last=True), "id")
        )
        total = qs.count()
        chunk = list(qs[offset : offset + page_size])
        post_ids = [r.post_id for r in chunk]
        parents = _parents(run, post_ids)
        arts = _artifacts_by_post(run, post_ids)
        results = []
        for rec in chunk:
            seen_here = rec.current_observation is not None
            obs = rec.current_observation or rec.previous_observation
            assert obs is not None
            last_seq = None if seen_here else obs.run.sequence
            results.append(
                _row(
                    obs,
                    reconciliation=rec,
                    parents=parents,
                    artifact_ids=arts,
                    observed_here=seen_here,
                    last_seen_sequence=last_seq,
                )
            )
    else:
        oqs = (
            PostObservation.objects.filter(run=run).select_related("post", "author").order_by("id")
        )
        total = oqs.count()
        chunk_obs = list(oqs[offset : offset + page_size])
        post_ids = [o.post_id for o in chunk_obs]
        parents = _parents(run, post_ids)
        arts = _artifacts_by_post(run, post_ids)
        results = [
            _row(
                o,
                reconciliation=None,
                parents=parents,
                artifact_ids=arts,
                observed_here=True,
                last_seen_sequence=None,
            )
            for o in chunk_obs
        ]
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "reconciled": reconciled,
        "results": results,
    }
