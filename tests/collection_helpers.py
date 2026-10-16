"""Pembantu bersama untuk tes pengumpulan data (bukan tes)."""

from datetime import UTC, datetime, timedelta

from collection import services
from collection.contracts import (
    Capability,
    CollectionStatus,
    CollectorInfo,
    Coverage,
    InspectionOutcome,
    InspectionResult,
    Limitation,
    LimitationCode,
    Observation,
    SourceMethod,
    SourceObjectType,
    UnavailableObject,
)
from collection.ingestion import ingest_result
from collection.models import InspectionRun, ObservationReconciliation
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
O = InspectionOutcome  # noqa: E741
CAPS = [Capability.INSPECT_POST, Capability.INSPECT_REPLIES]


def register(inv, user, platform, url):
    return inv_services.register_target(
        investigation=inv, user=user, platform=platform, target_type=TargetType.POST, url=url
    )


def new_run(target, user) -> InspectionRun:
    return services.create_inspection_run(target=target, user=user, requested=CAPS)


def obs(run, post_id="r1", *, kind=SourceObjectType.REPLY, actor="a1", parent="root",
        text="isi", ago=10, observed_at=None, status=CollectionStatus.COMPLETED, **kw) -> Observation:
    if kind is SourceObjectType.POST:
        parent = None
    fields = dict(
        platform=Platform(run.target.platform),
        source_object_type=kind,
        inspection_run_id=run.run_id,
        observed_at=observed_at or OBSERVED + timedelta(minutes=run.sequence),
        collection_status=status,
        source_method=SourceMethod.SYNTHETIC_FIXTURE,
        external_post_id=post_id,
        external_actor_id=actor,
        parent_post_id=parent,
        published_at=OBSERVED - timedelta(days=1, minutes=ago),
        text=text,
    )
    fields.update(kw)
    return Observation(**fields)


def make_result(run, observations=(), outcome=O.COMPLETED, displayed=None, limitations=(),
                complete=True, confirmed=(), artifacts=()) -> InspectionResult:
    return InspectionResult(
        platform=Platform(run.target.platform),
        inspection_run_id=run.run_id,
        outcome=outcome,
        collector=CollectorInfo("uji", "0.1"),
        coverage=Coverage((Capability.INSPECT_REPLIES,), complete, displayed),
        observations=tuple(observations),
        limitations=tuple(limitations),
        confirmed_unavailable=tuple(UnavailableObject(i, e) for i, e in confirmed),
        artifacts=tuple(artifacts),
    )


def replies(run, ids, **kw) -> list[Observation]:
    return [obs(run, i, actor=f"actor-{n % 5}", text=f"balasan {i}", **kw) for n, i in enumerate(ids)]


def ingest(run, observations, *, partial=False, confirmed=(), outcome=None, displayed=None,
           batch_size=500):
    """Ingest hasil sintetis dan pastikan ingestion bersih."""
    if partial:
        observations = [
            Observation(**{**o.__dict__, "collection_status": CollectionStatus.PARTIAL})
            for o in observations
        ]
        result = make_result(
            run, observations, O.PARTIAL, displayed, complete=False,
            limitations=[Limitation(LimitationCode.PAGINATION_INCOMPLETE, "halaman terputus")],
        )
    else:
        result = make_result(run, observations, outcome or O.COMPLETED, displayed, confirmed=confirmed)
    report = ingest_result(run, result, batch_size=batch_size)
    assert report.ok, report
    run.refresh_from_db()
    return report


def recon_rows(run) -> dict[str, ObservationReconciliation]:
    return {
        r.post.external_post_id: r
        for r in ObservationReconciliation.objects.filter(run=run).select_related("post")
    }


def statuses(run) -> dict[str, str]:
    return {k: v.status for k, v in recon_rows(run).items()}
