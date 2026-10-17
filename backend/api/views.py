from typing import Any

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from collection.models import InspectionRun
from collection.orchestrator import acknowledge_review, request_inspection
from investigations import access, services, team
from investigations.access import SuperuserRequired
from investigations.enums import InitialStance, Platform, Role, TargetType
from investigations.errors import InvalidContext
from investigations.models import InvestigationMembership, Proposition
from preservation import verification
from preservation.exports import ensure_exportable
from preservation.models import VerificationResult
from preservation.storage import PathNotAllowed, resolve_inside_evidence

from . import presenters, runs
from .access import (
    artifact_for,
    investigation_for,
    issue_for,
    run_for,
    target_for,
)
from .base import ApiView
from .lockout import lockout_response
from .serializers import (
    AcknowledgeInput,
    ActivationInput,
    ContextRevisionInput,
    InspectionInput,
    InvestigationInput,
    IssueInput,
    MemberInput,
    PageInput,
    PasswordInput,
    PropositionInput,
    RoleInput,
    TargetInput,
    UserCreateInput,
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
        user = _user(request)
        investigations = access.visible_investigations(user).select_related("created_by")
        return Response([presenters.investigation_summary(i, user) for i in investigations])

    def post(self, request: Request) -> Response:
        data = _valid(InvestigationInput, request)
        user = _user(request)
        inv = services.create_investigation(
            user=user, name=data["name"], description=data["description"]
        )
        return Response(presenters.investigation_detail(inv, user), status=201)


class InvestigationDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        user = _user(request)
        inv = investigation_for(user, pk, Role.VIEWER)
        return Response(presenters.investigation_detail(inv, user))


class IssueCreateView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.MEMBER)
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
        issue = issue_for(_user(request), pk, Role.MEMBER)
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
        inv = investigation_for(_user(request), pk, Role.MEMBER)
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
        target = target_for(_user(request), pk, Role.MEMBER)
        data = _valid(ContextRevisionInput, request)
        services.revise_target_context(
            target=target, user=_user(request), note=data["note"], stances=_stances(data)
        )
        return Response(presenters.target_repr(target), status=201)


# --- Inspeksi (WP-1.9a) ---------------------------------------------------------------------


class TargetInspectionsView(ApiView):
    """GET: riwayat run (terbaru dulu). POST: "Inspect" / "Inspect Again" = run BARU pada target
    yang sama (AT-01); ditolak 409 bila masih ada run yang berjalan."""

    def get(self, request: Request, pk: int) -> Response:
        target = target_for(_user(request), pk, Role.VIEWER)
        history = (
            InspectionRun.objects.filter(target=target)
            .select_related("requested_by")
            .order_by("-sequence")
        )
        return Response([runs.run_repr(r) for r in history])

    def post(self, request: Request, pk: int) -> Response:
        target = target_for(_user(request), pk, Role.MEMBER)
        data = _valid(InspectionInput, request)
        run = request_inspection(
            target=target, user=_user(request), requested=data.get("requested"), exclusive=True
        )
        # 202: run dibuat dan dikirim ke antrean; hasilnya diketahui lewat polling.
        return Response(runs.run_repr(run), status=202)


class InspectionDetailView(ApiView):
    def get(self, request: Request, pk: int) -> Response:
        user = _user(request)
        run = run_for(user, pk, Role.VIEWER, detail=True)
        return Response(runs.run_detail(run, user))


class InspectionObservationsView(ApiView):
    """Respons mentah per run (belum ada klasifikasi). Berhalaman."""

    def get(self, request: Request, pk: int) -> Response:
        run = run_for(_user(request), pk, Role.VIEWER)
        query = PageInput(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(
            runs.observation_page(
                run, page=query.validated_data["page"], page_size=query.validated_data["page_size"]
            )
        )


class InspectionAcknowledgeView(ApiView):
    """Akui tinjauan: hasil adapter yang tercatat dipulihkan; tidak mengubah data run."""

    def post(self, request: Request, pk: int) -> Response:
        run = run_for(_user(request), pk, Role.MEMBER, detail=True)
        data = _valid(AcknowledgeInput, request)
        done = acknowledge_review(run=run, user=_user(request), note=data["note"])
        return Response(runs.run_repr(done))


# --- Bukti: verifikasi dan akses (WP-1.10; FR-040) -----------------------------------------

_INLINE_IMAGES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "text/html": ".html",
    "application/json": ".json",
    "text/plain": ".txt",
}


class ArtifactVerifyView(ApiView):
    """Hitung ulang SHA-256 dan bandingkan dengan catatan. 200 walau hasilnya MISMATCH:
    pemeriksaan berhasil menghasilkan putusan; putusannya ada di `result`."""

    def post(self, request: Request, pk: int) -> Response:
        artifact = artifact_for(_user(request), pk, Role.VIEWER)
        row = verification.verify_artifact(artifact, _user(request))
        return Response(runs.verification_repr(row))


class InspectionVerifyArtifactsView(ApiView):
    """Verifikasi semua artefak sebuah run dan konsistensi manifest-nya."""

    def post(self, request: Request, pk: int) -> Response:
        run = run_for(_user(request), pk, Role.VIEWER)
        return Response(runs.run_verification_repr(verification.verify_run(run, _user(request))))


class ArtifactContentView(ApiView):
    """Isi artefak, hanya untuk pengguna terautentikasi dan HANYA bila hash cocok.

    Berkas yang tidak lolos verifikasi tidak disajikan (409): menyajikan bukti yang berubah tanpa
    peringatan lebih berbahaya daripada menolaknya; rinciannya ada di endpoint verifikasi. Berkas
    dibuka sekali: hash dan aliran memakai deskriptor yang sama. Isi berasal dari platform dan
    TIDAK DIPERCAYA: selalu diunduh sebagai lampiran kecuali gambar berjenis aman, dengan nosniff
    dan CSP sandbox, agar tidak pernah dieksekusi pada origin aplikasi."""

    def get(self, request: Request, pk: int) -> Any:
        artifact = artifact_for(_user(request), pk, Role.VIEWER)
        try:
            ensure_exportable(resolve_inside_evidence(artifact.relative_path))
        except (PathNotAllowed, FileNotFoundError, OSError):
            inspection = verification.Inspection(VerificationResult.UNREADABLE)
        else:
            inspection = verification.inspect_artifact(artifact)
        row = verification.record(artifact, _user(request), inspection, "download")
        if inspection.handle is None:
            return Response(
                {
                    "detail": "Berkas tidak lolos verifikasi hash dan tidak disajikan.",
                    "code": "artifact_integrity_failed",
                    "verification": runs.verification_repr(row),
                },
                status=409,
            )
        content_type = artifact.content_type.split(";")[0].strip().lower()
        inline = artifact.kind == "screenshot" and content_type in _INLINE_IMAGES
        extension = _EXTENSIONS.get(content_type, ".bin")
        response = FileResponse(
            inspection.handle,
            as_attachment=not inline,
            filename=f"snr-{artifact.kind}-{artifact.pk}{extension}",
            content_type=content_type if inline else "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox; frame-ancestors 'none'"
        response["Cache-Control"] = "private, no-store"
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        return response


# --- Tim: anggota investigasi (A3; ADR 0021) ----------------------------------------------


class InvestigationMembersView(ApiView):
    """GET: daftar anggota aktif (semua peran dapat melihat siapa timnya). POST: tambah (OWNER)."""

    def get(self, request: Request, pk: int) -> Response:
        inv = investigation_for(_user(request), pk, Role.VIEWER)
        rows = inv.memberships.filter(revoked_at__isnull=True).select_related("user", "added_by")
        return Response([presenters.member_repr(m) for m in rows.order_by("created_at", "id")])

    def post(self, request: Request, pk: int) -> Response:
        user = _user(request)
        inv = investigation_for(user, pk, Role.OWNER)
        data = _valid(MemberInput, request)
        member = team.grant(
            investigation=inv,
            user=team.user_by_username(data["username"]),
            role=data["role"],
            added_by=user,
        )
        return Response(presenters.member_repr(member), status=201)


class InvestigationMemberRoleView(ApiView):
    def post(self, request: Request, pk: int, user_id: int) -> Response:
        user = _user(request)
        inv = investigation_for(user, pk, Role.OWNER)
        data = _valid(RoleInput, request)
        member = team.change_role(
            investigation=inv, user=_account(user_id), role=data["role"], by=user
        )
        return Response(presenters.member_repr(member))


class InvestigationMemberRevokeView(ApiView):
    def post(self, request: Request, pk: int, user_id: int) -> Response:
        user = _user(request)
        inv = investigation_for(user, pk, Role.OWNER)
        team.revoke(investigation=inv, user=_account(user_id), by=user)
        return Response(status=204)


def _account(user_id: int) -> Any:
    return get_object_or_404(get_user_model(), pk=user_id)


# --- Akun pengguna: hanya super admin (A3) -------------------------------------------------


def _superuser(request: Request) -> Any:
    user = _user(request)
    if not user.is_superuser:
        raise SuperuserRequired("Hanya super admin yang dapat mengelola akun pengguna.")
    return user


def _validated_password(password: str, user: Any) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from None


class UserListCreateView(ApiView):
    def get(self, request: Request) -> Response:
        _superuser(request)
        counts = dict(
            InvestigationMembership.objects.filter(revoked_at__isnull=True)
            .values_list("user_id")
            .annotate(n=Count("id"))
        )
        users = get_user_model().objects.order_by("username")
        return Response([presenters.account_repr(u, counts.get(u.pk, 0)) for u in users])

    def post(self, request: Request) -> Response:
        _superuser(request)
        data = _valid(UserCreateInput, request)
        model = get_user_model()
        username = data["username"].strip()
        try:
            model._meta.get_field("username").run_validators(username)
        except DjangoValidationError as exc:
            raise ValidationError({"username": list(exc.messages)}) from None
        if model.objects.filter(username__iexact=username).exists():
            raise ValidationError({"username": ["Nama pengguna itu sudah dipakai."]})
        candidate = model(username=username)
        _validated_password(data["password"], candidate)
        account = model.objects.create_user(username=username, password=data["password"])
        return Response(presenters.account_repr(account, 0), status=201)


class UserActivationView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        admin = _superuser(request)
        data = _valid(ActivationInput, request)
        account = _account(pk)
        if account.pk == admin.pk and not data["active"]:
            raise ValidationError({"active": ["Anda tidak dapat menonaktifkan akun Anda sendiri."]})
        account.is_active = data["active"]
        account.save(update_fields=["is_active"])
        active = InvestigationMembership.objects.filter(user=account, revoked_at__isnull=True)
        count = active.count()
        return Response(presenters.account_repr(account, count))


class UserPasswordView(ApiView):
    def post(self, request: Request, pk: int) -> Response:
        _superuser(request)
        data = _valid(PasswordInput, request)
        account = _account(pk)
        _validated_password(data["password"], account)
        account.set_password(data["password"])
        account.save(update_fields=["password"])
        return Response(status=204)


def _user(request: Request) -> User:
    """Pengguna terautentikasi; lapis kedua di samping IsAuthenticated."""
    user = request.user
    if not user.is_authenticated:
        raise NotAuthenticated()
    assert isinstance(user, User)
    return user


def _valid(serializer_class: Any, request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
