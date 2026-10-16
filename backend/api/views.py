from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AbstractBaseUser
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from investigations import services
from investigations.enums import InitialStance, Platform, TargetType
from investigations.errors import InvalidContext
from investigations.models import CollectionTarget, Investigation, Issue, Proposition

from . import presenters
from .base import ApiView
from .lockout import lockout_response
from .serializers import (
    ContextRevisionInput,
    InvestigationInput,
    IssueInput,
    PropositionInput,
    TargetInput,
)

# --- Autentikasi ---------------------------------------------------------------------------


class CsrfView(ApiView):
    """Menyetel cookie CSRF untuk SPA. Publik, tidak mengembalikan data."""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request: Request) -> Response:
        return Response({"detail": "ok"})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(ApiView):
    """Login JSON. CSRF ditegakkan walau belum login; pembatasan percobaan oleh django-axes."""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    def post(self, request: Request) -> Response:
        payload = request.data if isinstance(request.data, dict) else {}
        username = payload.get("username", "")
        password = payload.get("password", "")
        # Gunakan HttpRequest asli: django-axes menandai lockout pada objek ini, dan
        # AxesMiddleware membaca tanda itu untuk menghasilkan respons 429 (api/lockout.py).
        http_request = request._request
        user = authenticate(http_request, username=username, password=password)
        if user is None:
            if getattr(http_request, "axes_locked_out", False):
                return lockout_response(http_request)  # type: ignore[return-value]
            return Response(
                {
                    "detail": "Nama pengguna atau kata sandi tidak sesuai.",
                    "code": "invalid_credentials",
                },
                status=400,
            )
        login(http_request, user)
        return Response(presenters.user_repr(user))


class LogoutView(ApiView):
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=204)


class MeView(ApiView):
    def get(self, request: Request) -> Response:
        return Response(presenters.user_repr(request.user))


class MetaView(ApiView):
    """Pilihan enum yang sah; sumber kebenaran tetap backend."""

    def get(self, request: Request) -> Response:
        def pairs(choices: Any) -> list[dict[str, str]]:
            return [{"value": v, "label": str(label)} for v, label in choices.choices]

        return Response(
            {
                "platforms": pairs(Platform),
                "target_types": pairs(TargetType),
                "initial_stances": pairs(InitialStance),
            }
        )


# --- Investigasi ---------------------------------------------------------------------------


class InvestigationListCreateView(ApiView):
    def get(self, request: Request) -> Response:
        investigations = Investigation.objects.select_related("created_by")
        return Response([presenters.investigation_summary(i) for i in investigations])

    def post(self, request: Request) -> Response:
        data = _valid(InvestigationInput, request)
        inv = services.create_investigation(
            user=_user(request), name=data["name"], description=data["description"]
        )
        return Response(presenters.investigation_detail(inv), status=201)


class InvestigationDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        inv = get_object_or_404(Investigation, pk=pk)
        return Response(presenters.investigation_detail(inv))


class IssueCreateView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        inv = get_object_or_404(Investigation, pk=pk)
        data = _valid(IssueInput, request)
        issue = services.create_issue(
            investigation=inv,
            user=_user(request),
            title=data["title"],
            definition=data["definition"],
        )
        return Response(presenters.issue_repr(issue), status=201)


class PropositionCreateView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        issue = get_object_or_404(Issue, pk=pk)
        data = _valid(PropositionInput, request)
        prop = services.add_proposition(
            issue=issue, user=_user(request), statement=data["statement"]
        )
        return Response(presenters.proposition_repr(prop), status=201)


def _stances(data: dict[str, Any]) -> dict[Proposition, str] | None:
    """None = tidak dikirim (bawa versi sebelumnya); dict = sengaja dikirim."""
    if "stances" not in data:
        return None
    ids = [s["proposition"] for s in data["stances"]]
    found = {p.pk: p for p in Proposition.objects.select_related("issue").filter(pk__in=ids)}
    result: dict[Proposition, str] = {}
    for item in data["stances"]:
        prop = found.get(item["proposition"])
        if prop is None:
            raise InvalidContext("Proposition tidak ditemukan.")
        if prop in result:
            raise InvalidContext("Satu proposition hanya boleh memiliki satu stance awal.")
        result[prop] = item["stance"]
    return result


class TargetCreateView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        inv = get_object_or_404(Investigation, pk=pk)
        data = _valid(TargetInput, request)
        target = services.register_target(
            investigation=inv,
            user=_user(request),
            platform=data["platform"],
            target_type=data["target_type"],
            url=data["url"],
            note=data["note"],
            stances=_stances(data),
        )
        return Response(presenters.target_repr(target), status=201)


class TargetContextReviseView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        target = get_object_or_404(CollectionTarget, pk=pk)
        data = _valid(ContextRevisionInput, request)
        services.revise_target_context(
            target=target, user=_user(request), note=data["note"], stances=_stances(data)
        )
        return Response(presenters.target_repr(target), status=201)


def _user(request: Request) -> AbstractBaseUser:
    """Pengguna terautentikasi; lapis kedua di samping IsAuthenticated."""
    user = request.user
    if not user.is_authenticated:
        raise NotAuthenticated()
    return user


def _valid(serializer_class: Any, request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
