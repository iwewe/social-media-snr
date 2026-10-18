"""Profil aktor M3 Level A sebagai metode AnalysisRun (WP-2.3; ADR 0027).

Dibangun dari penilaian M2 yang BERLAKU pada satu run M2 yang sudah selesai (hasil tinjauan manusia
menggantikan hasil mesin). Agar run M3 dapat diulang persis (NFR-01), parameter memuat hash himpunan
penilaian yang dipakai; bila himpunan itu berubah (mis. ada tinjauan baru), run gagal dengan pesan
jelas dan harus dibuat ulang. Level B (inspeksi tambahan) belum ada: butuh pengumpulan baru dan
WP-3.0.
"""

import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from collection.models import ActorAccount, InspectionRun
from investigations.models import CollectionTarget, Proposition

from .assessment import current_assessments
from .conversation import ConversationIndex
from .digest import digest_ids, digest_json
from .errors import InvalidParameters
from .m3 import DIMENSIONS, ProfileParams, ResponseRecord, build_dimensions
from .models import ActorIssueProfile, AnalysisRun, AnalysisStatus

_KEYS = {
    "source_run",
    "assessments_digest",
    "proposition_id",
    "period_start",
    "period_end",
    "min_responses",
    "bucket_hours",
    "min_active_buckets",
    "narrative_min_texts",
}
_BATCH = 500


def current_assessment_ids(source_run: AnalysisRun, proposition_id: int) -> list[int]:
    return sorted(
        current_assessments(source_run)
        .filter(proposition_id=proposition_id)
        .values_list("id", flat=True)
    )


def m3_parameters(
    *,
    source_run: AnalysisRun,
    proposition: Proposition,
    period_start: datetime,
    period_end: datetime,
    min_responses: int,
    bucket_hours: int,
    min_active_buckets: int,
    narrative_min_texts: int,
) -> dict[str, Any]:
    """Susun parameter run M3, termasuk hash penilaian M2 yang berlaku saat ini."""
    return {
        "source_run": source_run.pk,
        "assessments_digest": digest_ids(current_assessment_ids(source_run, proposition.pk)),
        "proposition_id": proposition.pk,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "min_responses": min_responses,
        "bucket_hours": bucket_hours,
        "min_active_buckets": min_active_buckets,
        "narrative_min_texts": narrative_min_texts,
    }


def _int(parameters: Mapping[str, Any], key: str, low: int, high: int) -> int:
    value = parameters[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidParameters(f"{key} harus bilangan bulat {low}..{high}")
    return value


def _time(parameters: Mapping[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(parameters[key]))
    except ValueError:
        raise InvalidParameters(f"{key} bukan waktu ISO-8601") from None
    if value.tzinfo is None:
        raise InvalidParameters(f"{key} wajib memuat zona waktu")
    return value


def _parse(parameters: Mapping[str, Any]) -> tuple[ProfileParams, int, int, str]:
    if set(parameters) != _KEYS:
        raise InvalidParameters(f"parameter wajib tepat: {sorted(_KEYS)}")
    digest = parameters["assessments_digest"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise InvalidParameters("assessments_digest harus SHA-256 heksadesimal")
    params = ProfileParams(
        period_start=_time(parameters, "period_start"),
        period_end=_time(parameters, "period_end"),
        min_responses=_int(parameters, "min_responses", 1, 10_000),
        bucket_hours=_int(parameters, "bucket_hours", 1, 720),
        min_active_buckets=_int(parameters, "min_active_buckets", 2, 1000),
        narrative_min_texts=_int(parameters, "narrative_min_texts", 2, 10_000),
    )
    if params.period_end <= params.period_start:
        raise InvalidParameters("period_end harus setelah period_start")
    return (
        params,
        _int(parameters, "source_run", 1, 2**62),
        _int(parameters, "proposition_id", 1, 2**62),
        digest,
    )


def validate_m3_parameters(parameters: Mapping[str, Any]) -> None:
    _parse(parameters)


def _statement(coverage: Mapping[str, Any]) -> str:
    return (
        f"Profil Level A: hanya respons akun ini yang teramati pada "
        f"{len(coverage['targets_covered'])} dari {len(coverage['targets_in_investigation'])} "
        f"target {coverage['platform']} dalam investigasi, periode {coverage['period']['start']} "
        f"sampai {coverage['period']['end']}, dari {len(coverage['runs_covered'])} pemeriksaan"
        f"{' (ada yang tidak lengkap)' if coverage['incomplete_runs'] else ''}. Ini bukan seluruh "
        "aktivitas akun, bukan identitas orang, dan bukan klasifikasi permanen."
    )


def run_m3_profile(frozen: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    params, source_id, proposition_id, expected_digest = _parse(parameters)
    run = AnalysisRun.objects.select_related("dataset_version").get(pk=frozen.run_id)
    source = AnalysisRun.objects.filter(pk=source_id).first()
    if (
        source is None
        or not source.method.startswith("m2-")
        or source.status != AnalysisStatus.COMPLETED
        or source.dataset_version_id != run.dataset_version_id
    ):
        raise InvalidParameters("source_run harus run M2 selesai pada dataset yang sama")
    proposition = Proposition.objects.filter(pk=proposition_id).first()
    if proposition is None:
        raise InvalidParameters(f"proposition tidak ditemukan: {proposition_id}")
    assessments = list(
        current_assessments(source)
        .filter(proposition_id=proposition_id)
        .select_related("observation__run", "observation__author")
    )
    if digest_ids(a.pk for a in assessments) != expected_digest:
        raise InvalidParameters(
            "penilaian M2 berubah sejak run dibuat (mis. ada tinjauan baru); buat run baru"
        )

    index = ConversationIndex(frozen.observation_ids)
    records: dict[int, list[ResponseRecord]] = defaultdict(list)
    without_author = outside_period = 0
    target_ids: set[int] = set()
    run_ids: set[int] = set()
    for a in assessments:
        o = a.observation
        target_ids.add(o.run.target_id)
        run_ids.add(o.run_id)
        if o.author_id is None:
            without_author += 1
            continue
        if o.published_at is not None and not (
            params.period_start <= o.published_at < params.period_end
        ):
            outside_period += 1
            continue
        records[o.author_id].append(
            ResponseRecord(
                observation_id=o.pk,
                actor_id=o.author_id,
                target_id=o.run.target_id,
                parent_post_id=index.parent_post_id(o.pk),
                published_at=o.published_at,
                text=o.text,
                stance=a.issue_stance,
                characters=tuple(a.response_character),
            )
        )
    dataset = run.dataset_version
    all_targets = sorted(
        CollectionTarget.objects.filter(
            investigation_id=run.investigation_id, platform=dataset.platform
        ).values_list("pk", flat=True)
    )
    runs = InspectionRun.objects.filter(pk__in=run_ids)
    incomplete = sorted((r.pk, r.status) for r in runs if r.status != "COMPLETED")
    actors = {
        a.pk: a for a in ActorAccount.objects.filter(pk__in=records, platform=dataset.platform)
    }
    rows = []
    signature = []
    for actor_id in sorted(records):
        if actor_id not in actors:
            raise InvalidParameters("akun dari platform lain tidak boleh dimasukkan ke profil")
        mine = sorted(records[actor_id], key=lambda r: r.observation_id)
        dimensions = build_dimensions(mine, params, targets_in_dataset=len(target_ids))
        coverage: dict[str, Any] = {
            "level": "A",
            "platform": dataset.platform,
            "source": "respons teramati pada target investigasi (penilaian M2 yang berlaku)",
            "dataset_version": dataset.number,
            "source_analysis_run": source.pk,
            "proposition_id": proposition_id,
            "period": {
                "start": params.period_start.isoformat(),
                "end": params.period_end.isoformat(),
            },
            "targets_covered": sorted(target_ids),
            "targets_in_investigation": all_targets,
            "partial_coverage": sorted(target_ids) != all_targets,
            "runs_covered": sorted(run_ids),
            "incomplete_runs": [{"run": r, "status": s} for r, s in incomplete],
            "responses_without_known_time": dimensions["participation"][
                "responses_without_known_time"
            ],
            "responses_excluded_outside_period": outside_period,
            "responses_without_author": without_author,
        }
        coverage["statement"] = _statement(coverage)
        rows.append(
            ActorIssueProfile(
                analysis_run=run,
                source_run=source,
                actor=actors[actor_id],
                proposition=proposition,
                level="A",
                period_start=params.period_start,
                period_end=params.period_end,
                dimensions=dimensions,
                coverage=coverage,
            )
        )
        signature.append((actor_id, dimensions))
    ActorIssueProfile.objects.bulk_create(rows, batch_size=_BATCH)
    return {
        "profiles": len(rows),
        "responses_profiled": sum(len(v) for v in records.values()),
        "responses_without_author": without_author,
        "responses_excluded_outside_period": outside_period,
        "dimensions": list(DIMENSIONS),
        "profiles_digest": digest_json(signature),
    }


def register() -> None:
    from .methods import REGISTRY, Method

    REGISTRY["m3-profile"] = Method("m3-profile", "1", validate_m3_parameters, run_m3_profile)
