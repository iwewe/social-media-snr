"""Rekonsiliasi antar-run (WP-1.4; FR-034, FR-035, FR-036; PRD bagian 9.2).

`reconcile_run(run)` membandingkan observasi run ini dengan seluruh run SEBELUMNYA pada TARGET yang
sama dan menyimpan status per objek (NEW, UNCHANGED, MODIFIED, NOT_OBSERVED,
CONFIRMED_UNAVAILABLE) sebagai data append-only. Pencocokan memakai ID stabil sumber.

Aturan:
- Pembanding setiap objek adalah observasi TERBARU dari run-run sebelumnya pada target ini.
- NOT_OBSERVED = pernah terlihat, kini tidak muncul. BUKAN bukti penghapusan (FR-036), baik pada
  run COMPLETED maupun PARTIAL.
- CONFIRMED_UNAVAILABLE hanya bila adapter menyatakannya eksplisit pada run COMPLETED
  (`coverage.confirmed_unavailable`), tidak pernah dari absennya objek pada sebuah daftar.
- Rekonsiliasi DITOLAK (state BLOCKED) bila ingestion run ini atau run pembanding belum tuntas
  (terputus, batch gagal, konflik): data yang hilang karena kegagalan ingestion tidak boleh terbaca
  sebagai 'tidak muncul'. Run yang tidak menghasilkan observasi (FAILED, ACCESS_RESTRICTED,
  UNSUPPORTED) dilewati (SKIPPED): tidak ada yang dapat dibandingkan.
- Objek tanpa ID stabil (kandidat) tidak dapat dicocokkan: tidak direkonsiliasi, hanya dihitung.
- Idempoten: run yang sudah DONE mengembalikan hasil tersimpan.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..content import CanonicalContent, canonical
from ..models import (
    InspectionRun,
    ObservationReconciliation,
    Post,
    PostObservation,
    PostRelation,
    ReconciliationStatus,
    RelationType,
    RunStatus,
)

S = ReconciliationStatus

# Masalah ingestion yang membuat data run tidak lengkap/tidak dapat dipercaya.
BLOCKING_PROBLEM_CODES = frozenset(
    {"INGESTION_ABORTED", "OBSERVATION_CONFLICT", "RELATION_CONFLICT", "METADATA_CONFLICT"}
)
NON_OBSERVING_OUTCOMES = frozenset({"FAILED", "ACCESS_RESTRICTED", "UNSUPPORTED"})
INSERT_BATCH = 1000


@dataclass(frozen=True)
class ReconciliationResult:
    state: str  # DONE | SKIPPED | BLOCKED
    reason: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    baseline_runs: list[int] = field(default_factory=list)
    unmatched_candidates_current: int = 0
    unmatched_candidates_baseline: int = 0
    unmatched_confirmed_unavailable: list[str] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.state == "DONE"


def _result_from(summary: dict[str, Any]) -> ReconciliationResult:
    return ReconciliationResult(
        state=summary["state"],
        reason=summary.get("reason"),
        counts=summary.get("counts", {}),
        baseline_runs=summary.get("baseline_runs", []),
        unmatched_candidates_current=summary.get("unmatched_candidates_current", 0),
        unmatched_candidates_baseline=summary.get("unmatched_candidates_baseline", 0),
        unmatched_confirmed_unavailable=summary.get("unmatched_confirmed_unavailable", []),
    )


def _ingestion_blocker(run: InspectionRun) -> str | None:
    """Alasan ingestion run ini tidak dapat dijadikan dasar rekonsiliasi, atau None."""
    ingestion = run.ingestion
    if ingestion is None:
        return "ingestion belum dilakukan"
    if ingestion.get("state") == "IN_PROGRESS":
        return "ingestion belum selesai (kemungkinan terputus)"
    report = ingestion.get("report") or {}
    if report.get("failed_batches"):
        return "ada batch ingestion yang gagal"
    codes = {p.get("code") for p in report.get("problems", [])} & BLOCKING_PROBLEM_CODES
    if codes:
        return f"ingestion bermasalah: {sorted(codes)}"
    return None


def _store(run: InspectionRun, state: str, **data: Any) -> ReconciliationResult:
    summary = {"state": state, "reconciled_at": timezone.now().isoformat(), **data}
    run.reconciliation = summary
    run.save(update_fields=["reconciliation"])
    return _result_from(summary)


def _canonical_from_row(obs: PostObservation, relations: list[PostRelation]) -> CanonicalContent:
    def target(kind: str) -> str | None:
        for r in relations:
            if r.relation_type == kind and r.to_post is not None:
                return r.to_post.external_post_id
        return None

    return canonical(
        object_type=obs.source_object_type,
        text=obs.text,
        author=obs.author.external_actor_id if obs.author else None,
        parent=target(RelationType.REPLY_TO),
        parent_unknown=obs.parent_unknown,
        quoted=target(RelationType.QUOTE_OF),
        reposted=target(RelationType.REPOST_OF),
        mentions=[
            r.to_actor.external_actor_id
            for r in relations
            if r.relation_type == RelationType.MENTIONS
            and r.to_actor is not None
            and r.to_actor.external_actor_id
        ],
    )


def _published_conflict(prev: PostObservation, cur: PostObservation) -> bool:
    """Waktu publikasi berbeda hanya dihitung bila KEDUANYA diketahui (None -> nilai = info)."""
    return (
        prev.published_at is not None
        and cur.published_at is not None
        and prev.published_at != cur.published_at
    )


def reconcile_run(run: InspectionRun) -> ReconciliationResult:
    """Rekonsiliasikan `run` terhadap run-run sebelumnya pada target yang sama."""
    with transaction.atomic():
        locked = InspectionRun.objects.select_for_update().get(pk=run.pk)
        if locked.reconciliation and locked.reconciliation.get("state") == "DONE":
            return _result_from(locked.reconciliation)  # idempoten

        blocker = _ingestion_blocker(locked)
        if blocker:
            return _store(locked, "BLOCKED", reason=f"run ini: {blocker}")

        outcome = (locked.coverage or {}).get("outcome")
        if outcome in NON_OBSERVING_OUTCOMES:
            return _store(locked, "SKIPPED", reason=f"run tidak menghasilkan observasi ({outcome})")

        earlier = list(
            InspectionRun.objects.filter(
                target_id=locked.target_id, sequence__lt=locked.sequence
            ).order_by("sequence")
        )
        for previous in earlier:
            if previous.ingestion is None and previous.status == RunStatus.PENDING:
                continue  # run yang belum pernah dijalankan tidak mempengaruhi pembanding
            problem = _ingestion_blocker(previous)
            if problem:
                return _store(
                    locked, "BLOCKED", reason=f"run pembanding {previous.sequence}: {problem}"
                )

        # Daftar id run diambil dulu (kecil) lalu dipakai sebagai filter IN: tidak ada JOIN ke tabel
        # run yang rencananya bergantung pada statistik tabel.
        baseline_run_ids = [r.pk for r in earlier]
        baseline = {
            o.post_id: o
            for o in (
                PostObservation.objects.filter(
                    run_id__in=baseline_run_ids, post__external_post_id__isnull=False
                )
                .order_by("post_id", "-run__sequence")
                .distinct("post_id")
                .select_related("author", "post", "run")
                if baseline_run_ids
                else []
            )
        }
        current = {
            o.post_id: o
            for o in PostObservation.objects.filter(
                run=locked, post__external_post_id__isnull=False
            ).select_related("author", "post", "run")
        }
        # Kandidat selalu dibuat bersama observasinya pada run yang pertama melihatnya; dihitung
        # lewat indeks parsial Post.first_seen_run (bukan JOIN observasi-post).
        candidates_current = Post.objects.filter(
            external_post_id__isnull=True, first_seen_run=locked
        ).count()
        candidates_baseline = (
            Post.objects.filter(
                external_post_id__isnull=True, first_seen_run_id__in=baseline_run_ids
            ).count()
            if baseline_run_ids
            else 0
        )
        confirmed = {
            c["external_post_id"]: c["evidence"]
            for c in (locked.coverage or {}).get("confirmed_unavailable", [])
        }

        # Pasangan yang hash-nya tidak dapat dibandingkan langsung dijelaskan dari data mentah.
        needs_detail: list[tuple[PostObservation, PostObservation]] = []
        decided: dict[int, tuple[ReconciliationStatus, list[str]]] = {}
        for post_id, cur in current.items():
            prev = baseline.get(post_id)
            if prev is None:
                continue
            same_version = (
                prev.content_hash_version == cur.content_hash_version
                and cur.content_hash_version != 0
            )
            if same_version and prev.content_hash == cur.content_hash:
                changed = ["published_at"] if _published_conflict(prev, cur) else []
                decided[post_id] = (S.MODIFIED if changed else S.UNCHANGED, changed)
            else:
                needs_detail.append((prev, cur))

        if needs_detail:
            run_ids = {o.run_id for pair in needs_detail for o in pair}
            post_ids = {o.post_id for pair in needs_detail for o in pair}
            by_key: dict[tuple[int, int], list[PostRelation]] = {}
            for rel in PostRelation.objects.filter(
                run_id__in=run_ids, from_post_id__in=post_ids
            ).select_related("to_post", "to_actor"):
                by_key.setdefault((rel.run_id, rel.from_post_id), []).append(rel)
            for prev, cur in needs_detail:
                before = _canonical_from_row(prev, by_key.get((prev.run_id, prev.post_id), []))
                after = _canonical_from_row(cur, by_key.get((cur.run_id, cur.post_id), []))
                changed = before.diff(after)
                if _published_conflict(prev, cur):
                    changed.append("published_at")
                decided[cur.post_id] = (S.MODIFIED if changed else S.UNCHANGED, changed)

        rows: list[ObservationReconciliation] = []
        counts: Counter[str] = Counter({status.value: 0 for status in S})
        for post_id, cur in current.items():
            prev = baseline.get(post_id)
            if prev is None:
                status, changed = S.NEW, []
            else:
                status, changed = decided[post_id]
            counts[status.value] += 1
            rows.append(
                ObservationReconciliation(
                    run=locked,
                    post=cur.post,
                    status=status,
                    previous_observation=prev,
                    current_observation=cur,
                    changed_fields=changed,
                )
            )
        seen_unavailable: set[str] = set()
        for post_id, prev in baseline.items():
            if post_id in current:
                continue
            external = prev.post.external_post_id or ""
            if external in confirmed:
                status, evidence = S.CONFIRMED_UNAVAILABLE, confirmed[external]
                seen_unavailable.add(external)
            else:
                status, evidence = S.NOT_OBSERVED, ""  # bukan bukti penghapusan (FR-036)
            counts[status.value] += 1
            rows.append(
                ObservationReconciliation(
                    run=locked,
                    post=prev.post,
                    status=status,
                    previous_observation=prev,
                    current_observation=None,
                    evidence=evidence,
                )
            )

        for start in range(0, len(rows), INSERT_BATCH):
            ObservationReconciliation.objects.bulk_create(rows[start : start + INSERT_BATCH])

        baseline_externals = {o.post.external_post_id for o in baseline.values()}
        return _store(
            locked,
            "DONE",
            reason=None,
            counts=dict(counts),
            baseline_runs=[r.sequence for r in earlier],
            unmatched_candidates_current=candidates_current,
            unmatched_candidates_baseline=candidates_baseline,
            # Pernyataan 'tidak tersedia' untuk objek yang tak pernah terlihat pada target ini.
            unmatched_confirmed_unavailable=sorted(set(confirmed) - baseline_externals),
        )
