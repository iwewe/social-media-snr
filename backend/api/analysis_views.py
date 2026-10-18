"""View API analisis I2 (WP-2.7): respons M2, graf M4, indikator, profil M3, temuan M5, jejak bukti.

Semua objek diambil lewat `api.access` (404 untuk non-anggota, 403 untuk peran kurang).
Baca = VIEWER;
menulis (tinjauan klasifikasi, pembuatan/pengesahan/penarikan temuan) = MEMBER.
"""

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response

from intelligence import findings as fs
from intelligence.assessment import assessment_history, review_assessment
from intelligence.m5 import AXES
from intelligence.models import AnalysisRun, CoordinationEdge, Finding
from investigations.enums import Role
from investigations.models import Investigation

from . import analysis
from .access import (
    analysis_run_for,
    assessment_for,
    finding_for,
    investigation_for,
    observation_for,
    profile_for,
)
from .base import ApiView
from .serializers import (
    AssessmentReviewInput,
    AuditListInput,
    CoordinationInput,
    FindingInput,
    FindingNoteInput,
    GraphInput,
    PageInput,
    ResponseListInput,
)


def _user(request: Request) -> Any:
    return request.user


def _valid(serializer: Any, request: Request) -> dict[str, Any]:
    s = serializer(data=request.data)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _query(serializer: Any, request: Request) -> dict[str, Any]:
    s = serializer(data=request.query_params)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


# --- run analisis -------------------------------------------------------------------------------


class AnalysisRunListView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.VIEWER)
        runs = AnalysisRun.objects.filter(investigation=inv).select_related(
            "dataset_version", "created_by"
        )
        method = request.query_params.get("method")
        if method:
            runs = runs.filter(method=method)
        return Response({"results": [analysis.run_repr(r) for r in runs.order_by("-id")]})


class AnalysisRunDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        run = analysis_run_for(_user(request), pk, Role.VIEWER)
        return Response(analysis.run_repr(run, full=True))


# --- respons M2 ---------------------------------------------------------------------------------


class AnalysisResponsesView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        run = analysis_run_for(_user(request), pk, Role.VIEWER)
        query = _query(ResponseListInput, request)
        page, size = query.pop("page"), query.pop("page_size")
        return Response(analysis.responses_page(run, filters=query, page=page, page_size=size))


class AssessmentReviewView(ApiView):
    """Koreksi manusia: baris baru yang menggantikan; hasil mesin tidak ditimpa (FR-055, AT-16)."""

    def post(self, request: Request, pk: int) -> Response:
        current = assessment_for(_user(request), pk, Role.MEMBER)
        data = _valid(AssessmentReviewInput, request)
        reason = data.pop("reason")
        kwargs: dict[str, Any] = {k: v for k, v in data.items()}
        new = review_assessment(assessment=current, by=_user(request), reason=reason, **kwargs)
        return Response(analysis.assessment_repr(new), status=201)


class AssessmentHistoryView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        current = assessment_for(_user(request), pk, Role.VIEWER)
        return Response(
            {"results": [analysis.assessment_repr(a) for a in assessment_history(current)]}
        )


# --- graf, indikator, profil --------------------------------------------------------------------


class AnalysisGraphView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        run = analysis_run_for(_user(request), pk, Role.VIEWER)
        return Response(analysis.graph_payload(run, params=_query(GraphInput, request)))


class AnalysisCoordinationView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        run = analysis_run_for(_user(request), pk, Role.VIEWER)
        query = _query(CoordinationInput, request)
        page, size = query.pop("page"), query.pop("page_size")
        return Response(analysis.coordination_page(run, filters=query, page=page, page_size=size))


class AnalysisProfilesView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        run = analysis_run_for(_user(request), pk, Role.VIEWER)
        query = _query(PageInput, request)
        return Response(
            analysis.profiles_page(run, page=query["page"], page_size=query["page_size"])
        )


class ProfileDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        return Response(analysis.profile_detail(profile_for(_user(request), pk, Role.VIEWER)))


# --- temuan -------------------------------------------------------------------------------------


def _draft_kwargs(inv: Investigation, request: Request) -> dict[str, Any]:
    data = _valid(FindingInput, request)
    runs = list(AnalysisRun.objects.filter(pk__in=data["analysis_run_ids"], investigation=inv))
    edges = list(
        CoordinationEdge.objects.filter(
            pk__in=data["indicator_edge_ids"], network__analysis_run__investigation=inv
        ).select_related("network")
    )
    if len(runs) != len(set(data["analysis_run_ids"])) or len(edges) != len(
        set(data["indicator_edge_ids"])
    ):
        raise fs.InvalidFinding("Run analisis atau indikator tidak ditemukan pada investigasi ini.")
    return {
        "analysis_runs": runs,
        "indicator_edges": edges,
        "observation_ids": data["observation_ids"],
        "title": data["title"],
        "statement": data["statement"],
        "interpretation": data["interpretation"],
        "evidence_ratings": data["evidence_ratings"],
        "alternatives": data["alternatives"],
        "confidence": data["confidence"],
        "confidence_reason": data["confidence_reason"],
        "by": _user(request),
    }


class FindingListCreateView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.VIEWER)
        found = (
            Finding.objects.filter(investigation=inv)
            .select_related("created_by")
            .prefetch_related("reviews")
            .order_by("-id")
        )
        return Response({"results": [analysis.finding_summary(f) for f in found]})

    def post(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.MEMBER)
        finding = fs.draft_finding(investigation=inv, **_draft_kwargs(inv, request))
        return Response(analysis.finding_detail(finding), status=201)


class FindingDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        return Response(analysis.finding_detail(finding_for(_user(request), pk, Role.VIEWER)))


class FindingEvidenceView(ApiView):
    """Saran sistem untuk empat sumbu bukti dari observasi yang dipilih (sebelum menulis temuan)."""

    def post(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.MEMBER)
        ids = request.data.get("observation_ids") if isinstance(request.data, dict) else None
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            raise fs.InvalidFinding(
                "observation_ids wajib berupa daftar bilangan bulat tidak kosong."
            )
        from collection.models import PostObservation

        valid = list(
            PostObservation.objects.filter(pk__in=ids, run__target__investigation=inv).values_list(
                "pk", flat=True
            )
        )
        if len(valid) != len(set(ids)):
            raise fs.InvalidFinding("Observasi tidak ditemukan pada investigasi ini.")
        result = fs.evaluate_evidence(valid)
        return Response(
            {"axes": list(AXES), "facts": result["facts"], "suggestions": result["suggestions"]}
        )


class FindingReviseView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        previous = finding_for(_user(request), pk, Role.MEMBER)
        kwargs = _draft_kwargs(previous.investigation, request)
        new = fs.revise_finding(previous=previous, **kwargs)
        return Response(analysis.finding_detail(new), status=201)


class FindingEndorseView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        finding = finding_for(_user(request), pk, Role.MEMBER)
        data = _valid(FindingNoteInput, request)
        fs.endorse_finding(finding=finding, by=_user(request), note=data["note"])
        return Response(analysis.finding_detail(Finding.objects.get(pk=finding.pk)))


class FindingWithdrawView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        finding = finding_for(_user(request), pk, Role.MEMBER)
        data = _valid(FindingNoteInput, request)
        fs.withdraw_finding(finding=finding, by=_user(request), note=data["note"])
        return Response(analysis.finding_detail(Finding.objects.get(pk=finding.pk)))


# --- jejak bukti --------------------------------------------------------------------------------


class ObservationDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        return Response(
            analysis.observation_detail(observation_for(_user(request), pk, Role.VIEWER))
        )


# --- jejak audit ----------------------------------------------------------------------------------


class AuditListView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.VIEWER)
        query = _query(AuditListInput, request)
        page, size = query.pop("page"), query.pop("page_size")
        return Response(analysis.audit_page(inv, filters=query, page=page, page_size=size))
