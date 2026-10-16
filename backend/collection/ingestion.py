"""Ingestion idempoten hasil inspeksi (WP-1.3; FR-032, NFR-03, NFR-04, NFR-05; AT-02, AT-03).

`ingest_result` memasukkan `InspectionResult` (kontrak WP-1.1) ke model WP-1.2.

Jaminan:
- Idempoten: meng-ingest hasil yang sama ke run yang sama dua kali tidak menambah baris apa pun.
  Identitas dipakai ulang lewat kunci unik `(platform, ID sumber)`; pemeriksaan ulang (run baru)
  menambah observasi tanpa menggandakan Post/ActorAccount.
- Aman terhadap kegagalan sebagian (NFR-04): observasi ditulis per batch dalam transaksi
  tersendiri. Batch yang gagal dibatalkan utuh dan DITANDAI di laporan (bukan dibuang diam-diam);
  batch lain dan data run sebelumnya tidak terpengaruh. Menjalankan ulang ingestion yang sama
  menyelesaikan batch yang tertinggal.
- Aman terhadap balapan: identitas dibuat dengan INSERT ... ON CONFLICT DO NOTHING lalu dibaca
  ulang; baris run dikunci per batch agar ingestion run yang sama tidak saling menimpa.
- Tidak pernah menimpa: observasi yang sudah ada dengan isi berbeda pada run yang sama dilaporkan
  sebagai konflik dan dibiarkan apa adanya.
- Dua angka dipisahkan (PRD bagian 9.3): jumlah yang DITAMPILKAN platform dan jumlah unik
  TERAMATI disimpan terpisah pada `InspectionRun.coverage`.
- Objek tanpa ID stabil menjadi kandidat `NEEDS_VERIFICATION`, tidak pernah digabung otomatis.

Ingestion tidak mengubah status run; itu tanggung jawab orchestrator (WP-1.6).
"""

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from .contracts import InspectionResult, Observation
from .models import (
    ActorAccount,
    IdentityStatus,
    InspectionRun,
    Post,
    PostObservation,
    PostRelation,
    RelationType,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500
MAX_FAILED_BATCHES = 3


class IngestionRejected(Exception):
    """Hasil ditolak SEBELUM menulis apa pun (platform/run tidak cocok, parameter salah)."""


@dataclass(frozen=True)
class BatchFailure:
    batch_index: int
    first_observation: int
    last_observation: int
    error: str


@dataclass(frozen=True)
class Problem:
    code: str
    detail: str


@dataclass
class IngestionReport:
    run_id: int
    observations_received: int = 0
    observations_created: int = 0
    observations_duplicate: int = 0
    posts_created: int = 0
    actors_created: int = 0
    candidates_created: int = 0
    relations_created: int = 0
    batches: int = 0
    # Dua angka berbeda (PRD bagian 9.3).
    platform_displayed_count: int | None = None
    observed_reply_count: int = 0
    failed_batches: list[BatchFailure] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True bila semua observasi tercatat tanpa batch gagal maupun konflik."""
        return not self.failed_batches and not self.problems

    def problem_codes(self) -> set[str]:
        return {p.code for p in self.problems}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


# --- pembantu ---------------------------------------------------------------------------------


def _chunks[T](items: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _same_content(existing: PostObservation, new: Observation) -> bool:
    return (
        existing.source_object_type == new.source_object_type.value
        and existing.collection_status == new.collection_status.value
        and existing.text == new.text
        and existing.published_at == new.published_at
        and existing.observed_at == new.observed_at
        and existing.captured_at == new.captured_at
        and existing.actor_handle == new.actor_handle
        and existing.actor_display_name == new.actor_display_name
        and existing.parent_unknown == new.parent_unknown
        and existing.identity_needs_verification == new.identity_needs_verification
        and (existing.author.external_actor_id if existing.author else None)
        == new.external_actor_id
    )


def _candidate_fingerprint(o: Observation | PostObservation) -> tuple[Any, ...]:
    """Pencocok dalam SATU run untuk objek tanpa ID (hanya untuk idempotensi re-ingest)."""
    kind = o.source_object_type if isinstance(o, PostObservation) else o.source_object_type.value
    return (kind, o.text, o.published_at, o.actor_handle, o.actor_display_name)


def _ensure_identities(
    model: Any,
    id_field: str,
    platform: str,
    wanted: dict[str, str],
    run: InspectionRun,
) -> tuple[dict[str, Any], int]:
    """Pastikan baris identitas ada untuk setiap ID.

    Mengembalikan (peta ID -> baris, jumlah dibuat).

    `wanted` memetakan ID -> status identitas awal bila baris perlu dibuat. Baris yang sudah ada
    tidak diubah (tidak ada kenaikan/penurunan status otomatis)."""
    if not wanted:
        return {}, 0
    lookup = {f"{id_field}__in": list(wanted)}
    found = {getattr(x, id_field): x for x in model.objects.filter(platform=platform, **lookup)}
    missing = [i for i in wanted if i not in found]
    created = 0
    if missing:
        model.objects.bulk_create(
            [
                model(
                    platform=platform,
                    first_seen_run=run,
                    identity_status=wanted[i],
                    **{id_field: i},
                )
                for i in missing
            ],
            ignore_conflicts=True,  # ON CONFLICT DO NOTHING: aman bila ingestion lain menyela
        )
        refetched = {
            getattr(x, id_field): x
            for x in model.objects.filter(platform=platform, **{f"{id_field}__in": missing})
        }
        created = sum(1 for x in refetched.values() if x.first_seen_run_id == run.pk)
        found.update(refetched)
    return found, created


def _status(flagged: bool) -> str:
    return IdentityStatus.NEEDS_VERIFICATION if flagged else IdentityStatus.VERIFIED


# --- satu batch -------------------------------------------------------------------------------


def _ingest_batch(
    run: InspectionRun, platform: str, batch: Sequence[Observation], report: IngestionReport
) -> None:
    # Serialisasi ingestion pada run yang sama; run berbeda tetap paralel.
    InspectionRun.objects.select_for_update().get(pk=run.pk)

    post_ids: dict[str, str] = {}
    actor_ids: dict[str, str] = {}
    for o in batch:
        if o.external_post_id:
            flagged = o.identity_needs_verification
            if flagged or post_ids.get(o.external_post_id) != IdentityStatus.NEEDS_VERIFICATION:
                post_ids[o.external_post_id] = _status(flagged)
        if o.external_actor_id:
            if o.identity_needs_verification or o.external_actor_id not in actor_ids:
                actor_ids[o.external_actor_id] = _status(o.identity_needs_verification)
        for ref in (o.parent_post_id, o.quoted_post_id, o.reposted_post_id):
            if ref:  # objek yang hanya dirujuk: ID berasal dari sumber, jadi terverifikasi
                post_ids.setdefault(ref, IdentityStatus.VERIFIED)
        for mentioned in o.mentioned_actor_ids:
            actor_ids.setdefault(mentioned, IdentityStatus.VERIFIED)

    posts, posts_created = _ensure_identities(Post, "external_post_id", platform, post_ids, run)
    actors, actors_created = _ensure_identities(
        ActorAccount, "external_actor_id", platform, actor_ids, run
    )
    report.posts_created += posts_created
    report.actors_created += actors_created

    # Kandidat tanpa ID: cocokkan multiset terhadap yang sudah ada pada run INI saja.
    existing_candidates: Counter[tuple[Any, ...]] = Counter(
        _candidate_fingerprint(o)
        for o in PostObservation.objects.filter(run=run, post__external_post_id__isnull=True)
    )

    existing_by_post = {
        o.post_id: o
        for o in PostObservation.objects.select_related("author").filter(
            run=run, post_id__in=[p.pk for p in posts.values()]
        )
    }

    new_rows: list[PostObservation] = []
    relation_inputs: list[tuple[Post, Observation]] = []
    candidate_posts: list[tuple[Observation, Post]] = []

    for o in batch:
        if o.external_post_id is None:
            fingerprint = _candidate_fingerprint(o)
            if existing_candidates[fingerprint] > 0:
                existing_candidates[fingerprint] -= 1
                report.observations_duplicate += 1
                continue
            candidate = Post(
                platform=platform,
                external_post_id=None,
                identity_status=IdentityStatus.NEEDS_VERIFICATION,
                first_seen_run=run,
            )
            candidate_posts.append((o, candidate))
            continue

        post = posts[o.external_post_id]
        existing = existing_by_post.get(post.pk)
        if existing is not None:
            if _same_content(existing, o):
                report.observations_duplicate += 1
                relation_inputs.append((post, o))  # relasi yang tertinggal tetap dilengkapi
            else:
                report.problems.append(
                    Problem(
                        "OBSERVATION_CONFLICT",
                        f"Run {run.pk} sudah punya observasi berbeda untuk {o.external_post_id}; "
                        "tidak ditimpa.",
                    )
                )
            continue
        new_rows.append(_to_row(run, post, actors, o))
        relation_inputs.append((post, o))

    if candidate_posts:
        Post.objects.bulk_create([c for _, c in candidate_posts])
        report.candidates_created += len(candidate_posts)
        for o, candidate in candidate_posts:
            new_rows.append(_to_row(run, candidate, actors, o))
            relation_inputs.append((candidate, o))

    if new_rows:
        PostObservation.objects.bulk_create(new_rows)
        report.observations_created += len(new_rows)

    _write_relations(run, relation_inputs, posts, actors, report)


def _to_row(
    run: InspectionRun, post: Post, actors: dict[str, ActorAccount], o: Observation
) -> PostObservation:
    author = actors.get(o.external_actor_id) if o.external_actor_id else None
    return PostObservation(
        post=post,
        run=run,
        author=author,
        source_object_type=o.source_object_type.value,
        collection_status=o.collection_status.value,
        text=o.text,
        published_at=o.published_at,
        observed_at=o.observed_at,
        captured_at=o.captured_at,
        actor_handle=o.actor_handle,
        actor_display_name=o.actor_display_name,
        parent_unknown=o.parent_unknown,
        identity_needs_verification=o.identity_needs_verification,
    )


def _write_relations(
    run: InspectionRun,
    inputs: Sequence[tuple[Post, Observation]],
    posts: dict[str, Post],
    actors: dict[str, ActorAccount],
    report: IngestionReport,
) -> None:
    wanted: list[PostRelation] = []
    for source_post, o in inputs:
        if o.parent_post_id:
            wanted.append(
                _relation(run, source_post, RelationType.REPLY_TO, posts[o.parent_post_id])
            )
        if o.quoted_post_id:
            wanted.append(
                _relation(run, source_post, RelationType.QUOTE_OF, posts[o.quoted_post_id])
            )
        if o.reposted_post_id:
            wanted.append(
                _relation(run, source_post, RelationType.REPOST_OF, posts[o.reposted_post_id])
            )
        for mentioned in dict.fromkeys(o.mentioned_actor_ids):
            wanted.append(
                PostRelation(
                    run=run,
                    from_post=source_post,
                    relation_type=RelationType.MENTIONS,
                    to_actor=actors[mentioned],
                )
            )
    if not wanted:
        return

    existing = {
        (r.from_post_id, r.relation_type, r.to_post_id, r.to_actor_id)
        for r in PostRelation.objects.filter(
            run=run, from_post_id__in={r.from_post.pk for r in wanted}
        )
    }
    existing_parent = {
        r.from_post_id: r.to_post_id
        for r in PostRelation.objects.filter(
            run=run,
            relation_type=RelationType.REPLY_TO,
            from_post_id__in={r.from_post.pk for r in wanted},
        )
    }
    fresh: list[PostRelation] = []
    seen = set(existing)
    for rel in wanted:
        key = (rel.from_post.pk, rel.relation_type, rel.to_post_id, rel.to_actor_id)
        if key in seen:
            continue
        if rel.relation_type == RelationType.REPLY_TO and rel.from_post.pk in existing_parent:
            report.problems.append(
                Problem(
                    "RELATION_CONFLICT",
                    f"Run {run.pk} sudah mencatat induk berbeda untuk post {rel.from_post.pk}.",
                )
            )
            continue
        seen.add(key)
        fresh.append(rel)
    if fresh:
        PostRelation.objects.bulk_create(fresh)
        report.relations_created += len(fresh)


def _relation(run: InspectionRun, source: Post, kind: str, target: Post) -> PostRelation:
    return PostRelation(run=run, from_post=source, relation_type=kind, to_post=target)


# --- metadata run -----------------------------------------------------------------------------


def _store_run_metadata(
    run: InspectionRun, result: InspectionResult, report: IngestionReport
) -> None:
    coverage = {
        "scope": [c.value for c in result.coverage.scope],
        "pagination_complete": result.coverage.pagination_complete,
        # Dua angka berbeda: yang DITAMPILKAN platform vs yang unik TERAMATI (PRD bagian 9.3).
        "platform_displayed_count": result.coverage.platform_displayed_count,
        "observed_reply_count": result.observed_reply_count,
        "observed_object_count": len(result.observations),
        "notes": list(result.coverage.notes),
        "outcome": result.outcome.value,
    }
    limitations = [
        {
            "code": lim.code.value,
            "message": lim.message,
            "capability": lim.capability.value if lim.capability else None,
        }
        for lim in result.limitations
    ]
    methods = {o.source_method.value for o in result.observations}
    if len(methods) > 1:
        report.problems.append(
            Problem(
                "MIXED_SOURCE_METHODS",
                f"Satu hasil memuat beberapa source_method: {sorted(methods)}",
            )
        )
    source_method = next(iter(methods)) if len(methods) == 1 else ""

    with transaction.atomic():
        locked = InspectionRun.objects.select_for_update().get(pk=run.pk)
        already = locked.coverage is not None
        if already and (locked.coverage != coverage or locked.limitations != limitations):
            report.problems.append(
                Problem(
                    "METADATA_CONFLICT",
                    "Run sudah memiliki metadata cakupan/keterbatasan berbeda; tidak ditimpa.",
                )
            )
            return
        if source_method and locked.source_method and locked.source_method != source_method:
            report.problems.append(
                Problem("METADATA_CONFLICT", "source_method berbeda dari yang sudah tercatat.")
            )
            return
        locked.coverage = coverage
        locked.limitations = limitations
        locked.collector_name = result.collector.name
        locked.collector_version = result.collector.version
        if source_method:
            locked.source_method = source_method
        locked.save(
            update_fields=[
                "coverage",
                "limitations",
                "collector_name",
                "collector_version",
                "source_method",
            ]
        )


def _write_ingestion_state(run: InspectionRun, state: dict[str, Any]) -> None:
    InspectionRun.objects.filter(pk=run.pk).update(ingestion=state)


# --- pintu masuk ------------------------------------------------------------------------------


def ingest_result(
    run: InspectionRun,
    result: InspectionResult,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_failed_batches: int = MAX_FAILED_BATCHES,
) -> IngestionReport:
    """Masukkan hasil inspeksi ke database. Lihat docstring modul untuk jaminannya."""
    if batch_size <= 0 or max_failed_batches <= 0:
        raise IngestionRejected("batch_size dan max_failed_batches harus positif.")
    platform = run.target.platform
    if result.platform.value != platform:
        raise IngestionRejected(
            f"Hasil platform {result.platform.value} tidak boleh dimasukkan ke run "
            f"platform {platform}."
        )
    if result.inspection_run_id != run.run_id:
        raise IngestionRejected("inspection_run_id pada hasil tidak cocok dengan run.")

    report = IngestionReport(
        run_id=run.pk,
        observations_received=len(result.observations),
        platform_displayed_count=result.coverage.platform_displayed_count,
        observed_reply_count=result.observed_reply_count,
    )
    if result.artifacts:
        # Jangan dibuang diam-diam: penyimpanan artefak ada pada WP-1.5.
        report.problems.append(
            Problem(
                "ARTIFACTS_NOT_PERSISTED",
                f"{len(result.artifacts)} artefak belum disimpan (preservasi artefak: WP-1.5).",
            )
        )

    _store_run_metadata(run, result, report)
    # Penanda "sedang berjalan": bila proses mati sebelum selesai, nilai ini tetap tinggal dan
    # run dapat dikenali sebagai ingestion yang terputus (orchestrator menandainya, WP-1.6).
    _write_ingestion_state(run, {"state": "IN_PROGRESS", "started_at": timezone.now().isoformat()})

    observations = list(result.observations)
    for index, batch in enumerate(_chunks(observations, batch_size)):
        report.batches += 1
        # Ukuran laporan awal diambil agar batch gagal tidak menyisakan hitungan setengah jadi.
        snapshot = (
            report.observations_created,
            report.observations_duplicate,
            report.posts_created,
            report.actors_created,
            report.candidates_created,
            report.relations_created,
            len(report.problems),
        )
        try:
            with transaction.atomic():
                _ingest_batch(run, platform, batch, report)
        except Exception as exc:  # noqa: BLE001 - galat apa pun harus dilaporkan, bukan ditelan
            (
                report.observations_created,
                report.observations_duplicate,
                report.posts_created,
                report.actors_created,
                report.candidates_created,
                report.relations_created,
                problem_count,
            ) = snapshot
            del report.problems[problem_count:]
            first = index * batch_size
            failure = BatchFailure(
                index, first, first + len(batch) - 1, f"{type(exc).__name__}: {exc}"
            )
            report.failed_batches.append(failure)
            logger.exception("Batch %s gagal pada run %s", index, run.pk)
            if len(report.failed_batches) >= max_failed_batches:
                report.problems.append(
                    Problem(
                        "INGESTION_ABORTED",
                        f"Dihentikan setelah {len(report.failed_batches)} batch gagal; "
                        "sisa observasi belum diproses.",
                    )
                )
                break

    _write_ingestion_state(
        run,
        {
            "state": "FINISHED" if report.ok else "FINISHED_WITH_PROBLEMS",
            "finished_at": timezone.now().isoformat(),
            "report": report.to_dict(),
        },
    )
    return report


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "BatchFailure",
    "IngestionRejected",
    "IngestionReport",
    "Problem",
    "ingest_result",
]
