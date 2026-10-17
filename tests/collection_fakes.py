"""Adapter terskrip untuk menguji orchestrator (bukan adapter produksi, tanpa jaringan)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from collection.contracts import (
    Adapter,
    Capabilities,
    Capability,
    CapabilityDeclaration,
    CapabilityStatus,
    CollectionStatus,
    CollectorInfo,
    Coverage,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    Limitation,
    LimitationCode,
    Observation,
    SourceMethod,
    SourceObjectType,
    TargetUrlInfo,
)
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL
from investigations.target_urls import normalize_target_url

OBSERVED = datetime(2026, 10, 17, 1, 32, tzinfo=UTC)
O = InspectionOutcome  # noqa: E741


def build_obs(
    request: InspectionRequest,
    post_id: str,
    *,
    actor="a1",
    text=None,
    parent="root",
    kind=SourceObjectType.REPLY,
    status=CollectionStatus.COMPLETED,
    **kw,
) -> Observation:
    fields = dict(
        platform=request.platform,
        source_object_type=kind,
        inspection_run_id=request.inspection_run_id,
        observed_at=OBSERVED,
        collection_status=status,
        source_method=SourceMethod.SYNTHETIC_FIXTURE,
        external_post_id=post_id,
        external_actor_id=actor,
        parent_post_id=None if kind is SourceObjectType.POST else parent,
        published_at=OBSERVED - timedelta(hours=1),
        text=text if text is not None else f"balasan {post_id}",
    )
    fields.update(kw)
    return Observation(**fields)


def build_result(
    request: InspectionRequest,
    ids=(),
    *,
    outcome=O.COMPLETED,
    displayed=None,
    limitations=(),
    complete=True,
    artifacts=(),
    confirmed=(),
) -> InspectionResult:
    status = CollectionStatus.COMPLETED if outcome is O.COMPLETED else CollectionStatus.PARTIAL
    observations = tuple(build_obs(request, i, status=status) for i in ids)
    return InspectionResult(
        platform=request.platform,
        inspection_run_id=request.inspection_run_id,
        outcome=outcome,
        collector=ScriptedAdapter.collector,
        coverage=Coverage(
            request.requested, complete, len(ids) if displayed is None else displayed
        ),
        observations=observations,
        limitations=tuple(limitations),
        artifacts=tuple(artifacts),
        confirmed_unavailable=tuple(confirmed),
    )


def restricted(request: InspectionRequest) -> InspectionResult:
    return build_result(
        request,
        outcome=O.ACCESS_RESTRICTED,
        complete=None,
        limitations=[Limitation(LimitationCode.ACCESS_RESTRICTED, "butuh login")],
    )


def parse_failed(request: InspectionRequest) -> InspectionResult:
    return build_result(
        request,
        outcome=O.FAILED,
        complete=None,
        limitations=[Limitation(LimitationCode.PARSE_FAILED, "struktur tak dikenal")],
    )


Behavior = Callable[[InspectionRequest], InspectionResult]


class ScriptedAdapter(Adapter):
    platform = Platform.X
    collector = CollectorInfo("scripted", "0.1")
    execution_queue = "analysis"

    def __init__(self, behavior: Behavior, disable=()) -> None:
        self.behavior = behavior
        self.disable = frozenset(disable)
        self.calls: list[InspectionRequest] = []

    def capabilities(self) -> Capabilities:
        decl = {c: CapabilityDeclaration(CapabilityStatus.SUPPORTED) for c in Capability}
        for cap in self.disable:
            decl[cap] = CapabilityDeclaration(CapabilityStatus.UNTESTED, "dinonaktifkan uji")
        return Capabilities(self.platform, decl)

    def validate_target_url(self, url: str) -> TargetUrlInfo:
        normalized = normalize_target_url(Platform.X, url)  # raise InvalidTargetURL
        parts = urlsplit(normalized).path.strip("/").split("/")
        if len(parts) == 3 and parts[1] == "status" and parts[2].isdigit():
            return TargetUrlInfo(Platform.X, TargetType.POST, normalized, parts[2])
        raise InvalidTargetURL("struktur URL tidak dikenali")

    def collect(self, request: InspectionRequest) -> InspectionResult:
        self.calls.append(request)
        return self.behavior(request)


class BrowserScriptedAdapter(ScriptedAdapter):
    execution_queue = "browser"
