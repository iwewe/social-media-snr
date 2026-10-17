"""Adapter browser untuk SIMULASI platform (WP-1.8). Bukan adapter platform nyata.

Satu kelas per platform (isolasi platform). URL target tetap URL platform (mis. x.com/...);
adapter memetakannya ke simulasi: `<base_url><path URL target>`. Adapter nyata (I3) akan memakai
`BrowserSession` yang sama tetapi menavigasi situs sebenarnya setelah studi izin (WP-3.0).

Prinsip yang dijaga:
- Tidak ada upaya melewati CAPTCHA, tantangan, atau tembok login: halaman seperti itu menjadi
  ACCESS_RESTRICTED (atau PARTIAL + AUTH_REQUIRED bila sebagian sudah terbaca) dan berhenti.
- Permintaan ke origin selain origin target diblokir (pelacak/pihak ketiga tidak dikunjungi);
  jumlahnya dicatat di catatan cakupan tanpa memuat URL lengkap.
- Kegagalan tidak pernah tampak sebagai "nol balasan": akses ditolak, struktur berubah, timeout,
  dan pagination terputus masing-masing berstatus sendiri dengan keterbatasan terstruktur.
- Galat infrastruktur (browser gagal diluncurkan) tidak ditelan: merambat ke orchestrator.
"""

from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Route
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from collection.contracts import (
    Adapter,
    ArtifactCapture,
    ArtifactKind,
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
from collection.datasets.adapter import classify_url
from investigations.enums import Platform
from investigations.target_urls import normalize_target_url

from .runtime import DEFAULT_TIMEOUT_MS, BrowserSession, prepare_profile_dir

COLLECTOR_NAME = "browser-sim"
COLLECTOR_REVISION = "1"
# Pengaman teknis terhadap pagination tak berujung (bukan angka riset): setelah sejumlah klik
# "muat lebih banyak" run dihentikan sebagai PARTIAL.
DEFAULT_MAX_PAGES = 1000

_EXTRACT_REPLIES = """els => els.map(e => ({
  id: e.dataset.replyId || null,
  author: e.dataset.authorId || null,
  handle: e.dataset.handle || null,
  parent: e.dataset.parentId || null,
  published: e.querySelector('time') ? e.querySelector('time').getAttribute('datetime') : null,
  text: e.querySelector('.text') ? e.querySelector('.text').innerText : null,
}))"""
_AFTER_CLICK = """n => document.querySelectorAll('#replies > li.reply').length > n
  || document.getElementById('load-error')?.hidden === false
  || document.getElementById('login-wall')?.hidden === false
  || document.getElementById('load-more')?.hidden === true"""


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class SimulatedBrowserAdapter(Adapter):
    collector = CollectorInfo(COLLECTOR_NAME, COLLECTOR_REVISION)
    execution_queue = "browser"

    def __init__(
        self,
        base_url: str,
        *,
        profile_name: str | None = None,
        disable: Collection[Capability] = (),
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_pages: int = DEFAULT_MAX_PAGES,
        no_sandbox: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.profile_name = profile_name
        self.disable = frozenset(disable)
        self.timeout_ms = timeout_ms
        self.max_pages = max_pages
        self.no_sandbox = no_sandbox

    # --- kontrak ---------------------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        sup = CapabilityDeclaration(CapabilityStatus.SUPPORTED)
        declarations = {
            Capability.INSPECT_POST: sup,
            Capability.INSPECT_REPLIES: sup,
            Capability.PRESERVE_SCREENSHOT: sup,
            Capability.PRESERVE_DOM: sup,
            Capability.INSPECT_ACCOUNT: CapabilityDeclaration(
                CapabilityStatus.UNSUPPORTED, "halaman akun belum disimulasikan"
            ),
            Capability.PRESERVE_MEDIA: CapabilityDeclaration(
                CapabilityStatus.UNSUPPORTED, "media belum disimulasikan"
            ),
        }
        for cap in self.disable:
            declarations[cap] = CapabilityDeclaration(CapabilityStatus.UNTESTED, "dinonaktifkan")
        return Capabilities(self.platform, declarations)

    def validate_target_url(self, url: str) -> TargetUrlInfo:
        normalized = normalize_target_url(self.platform.value, url)  # raise InvalidTargetURL
        target_type, external_id = classify_url(self.platform, normalized)
        return TargetUrlInfo(self.platform, target_type, normalized, external_id)

    # --- pengambilan -----------------------------------------------------------------------

    def collect(self, request: InspectionRequest) -> InspectionResult:
        parts = urlsplit(request.target_url)
        url = f"{self.base_url}{parts.path}" + (f"?{parts.query}" if parts.query else "")
        origin = urlsplit(url)
        blocked: list[str] = []

        # Profil disiapkan saat collect (di worker-browser), bukan saat adapter dibuat: proses
        # web membuat instans hanya untuk membaca antrean dan tidak memasang browser-profiles.
        profile_dir = prepare_profile_dir(self.profile_name) if self.profile_name else None
        with BrowserSession(
            profile_dir=profile_dir,
            no_sandbox=self.no_sandbox,
            timeout_ms=self.timeout_ms,
        ) as session:
            collector = CollectorInfo(
                COLLECTOR_NAME, f"{COLLECTOR_REVISION} ({session.versions.label()})"
            )

            def guard(route: Route) -> None:
                target = urlsplit(route.request.url)
                same = (target.scheme, target.netloc) == (origin.scheme, origin.netloc)
                if same or target.scheme in ("data", "blob", "about"):
                    route.continue_()
                else:
                    blocked.append(target.hostname or "?")
                    route.abort()

            session.context.route("**/*", guard)
            page = session.new_page()
            return self._inspect(request, page, url, collector, blocked)

    def _inspect(
        self,
        request: InspectionRequest,
        page: Page,
        url: str,
        collector: CollectorInfo,
        blocked: list[str],
    ) -> InspectionResult:
        def result(
            outcome,
            limitations=(),
            observations=(),
            artifacts=(),
            complete=None,
            displayed=None,
            notes=(),
        ):  # noqa: ANN001, ANN202
            all_notes = list(notes)
            if blocked:
                all_notes.append(f"{len(blocked)} permintaan ke origin lain diblokir")
            return InspectionResult(
                platform=self.platform,
                inspection_run_id=request.inspection_run_id,
                outcome=outcome,
                collector=collector,
                coverage=Coverage(request.requested, complete, displayed, tuple(all_notes)),
                observations=tuple(observations),
                limitations=tuple(limitations),
                artifacts=tuple(artifacts),
            )

        def fail(outcome, code, message, artifacts=()):  # noqa: ANN001, ANN202
            return result(outcome, [Limitation(code, message)], artifacts=artifacts)

        try:
            response = page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeout:
            return fail(
                InspectionOutcome.FAILED,
                LimitationCode.TIMEOUT,
                "halaman tidak termuat dalam batas waktu",
            )
        except PlaywrightError:
            return fail(
                InspectionOutcome.FAILED,
                LimitationCode.NETWORK_ERROR,
                "halaman tidak dapat dijangkau",
            )

        status = response.status if response is not None else 0
        evidence = self._capture(page, request, container=False)
        if status in (401, 403):
            return fail(
                InspectionOutcome.ACCESS_RESTRICTED,
                LimitationCode.ACCESS_RESTRICTED,
                f"platform menolak akses (HTTP {status}); tidak dilewati",
                evidence,
            )
        if status == 404:
            return fail(
                InspectionOutcome.FAILED,
                LimitationCode.TARGET_UNAVAILABLE,
                "target tidak ditemukan (HTTP 404)",
                evidence,
            )
        if status >= 400 or status == 0:
            return fail(
                InspectionOutcome.FAILED,
                LimitationCode.NETWORK_ERROR,
                f"platform mengembalikan galat (HTTP {status})",
                evidence,
            )
        if page.locator("[data-snr-challenge]").count():
            return fail(
                InspectionOutcome.ACCESS_RESTRICTED,
                LimitationCode.ACCESS_RESTRICTED,
                "platform menampilkan tantangan verifikasi; tidak dilewati",
                evidence,
            )
        if page.locator("#focal").count() == 0:
            return fail(
                InspectionOutcome.FAILED,
                LimitationCode.PARSE_FAILED,
                "struktur halaman tidak dikenali (elemen utama tidak ditemukan)",
                evidence,
            )

        want_replies = Capability.INSPECT_REPLIES in request.requested
        limitations: list[Limitation] = []
        complete = True
        if want_replies:
            complete = self._paginate(page, request, limitations)
        displayed = self._displayed_count(page) if want_replies else None
        raw_replies = (
            page.eval_on_selector_all("#replies > li.reply", _EXTRACT_REPLIES)
            if want_replies
            else []
        )
        if request.max_items is not None:
            raw_replies = raw_replies[: request.max_items]

        done = complete and not limitations
        outcome = InspectionOutcome.COMPLETED if done else InspectionOutcome.PARTIAL
        observations, duplicates = self._observations(request, page, raw_replies, outcome)
        notes = [f"{duplicates} objek duplikat disatukan"] if duplicates else []
        artifacts = self._capture(page, request, container=True)
        return result(
            outcome,
            limitations,
            observations,
            artifacts,
            complete=complete and not limitations,
            displayed=displayed,
            notes=notes,
        )

    def _paginate(
        self, page: Page, request: InspectionRequest, limitations: list[Limitation]
    ) -> bool:
        """Klik "muat lebih banyak" sampai habis. True bila paginasi tuntas tanpa hambatan."""
        count = lambda: page.locator("#replies > li.reply").count()  # noqa: E731
        clicks = 0
        while True:
            if page.locator("#login-wall:not([hidden])").count():
                limitations.append(
                    Limitation(
                        LimitationCode.AUTH_REQUIRED,
                        "balasan lain memerlukan login; tidak dilewati",
                    )
                )
                return False
            button = page.locator("#load-more")
            if button.count() == 0 or not button.is_visible():
                return True
            if request.max_items is not None and count() >= request.max_items:
                limitations.append(
                    Limitation(
                        LimitationCode.MAX_ITEMS_REACHED, f"dibatasi {request.max_items} objek"
                    )
                )
                return False
            if clicks >= self.max_pages:
                limitations.append(
                    Limitation(
                        LimitationCode.MAX_ITEMS_REACHED, "batas pengaman jumlah halaman tercapai"
                    )
                )
                return False
            before = count()
            clicks += 1
            try:
                button.click()
                page.wait_for_function(_AFTER_CLICK, arg=before)
            except (PlaywrightTimeout, PlaywrightError):
                limitations.append(
                    Limitation(
                        LimitationCode.PAGINATION_INCOMPLETE, "halaman berikutnya tidak termuat"
                    )
                )
                return False
            if page.locator("#load-error:not([hidden])").count():
                limitations.append(
                    Limitation(
                        LimitationCode.PAGINATION_INCOMPLETE,
                        "platform gagal memuat halaman berikutnya",
                    )
                )
                return False

    @staticmethod
    def _displayed_count(page: Page) -> int | None:
        raw = page.locator("#conversation").first.get_attribute("data-displayed-count")
        return int(raw) if raw is not None and raw.isdigit() else None

    def _observations(
        self,
        request: InspectionRequest,
        page: Page,
        replies: list[dict],
        outcome: InspectionOutcome,
    ) -> tuple[list[Observation], int]:
        status = (
            CollectionStatus.COMPLETED
            if outcome is InspectionOutcome.COMPLETED
            else CollectionStatus.PARTIAL
        )
        now = datetime.now(UTC)
        focal = page.locator("#focal").first
        post_id = focal.get_attribute("data-post-id")
        common: dict[str, Any] = dict(
            platform=self.platform,
            inspection_run_id=request.inspection_run_id,
            observed_at=now,
            collection_status=status,
            # Data simulasi sintetis; adapter nyata memakai authorized_observation.
            source_method=SourceMethod.SYNTHETIC_FIXTURE,
        )
        out: list[Observation] = [
            Observation(
                source_object_type=SourceObjectType.POST,
                external_post_id=post_id,
                external_actor_id=focal.get_attribute("data-author-id") or None,
                actor_handle=focal.get_attribute("data-handle"),
                published_at=_parse_time(focal.locator("time").first.get_attribute("datetime")),
                text=focal.locator(".text").first.inner_text(),
                **common,
            )
        ]
        seen = {post_id}
        duplicates = 0
        for r in replies:
            if r["id"] in seen:
                duplicates += 1
                continue
            seen.add(r["id"])
            author = r["author"]
            out.append(
                Observation(
                    source_object_type=SourceObjectType.REPLY,
                    external_post_id=r["id"],
                    external_actor_id=author,
                    identity_needs_verification=author is None,
                    parent_post_id=r["parent"],
                    parent_unknown=r["parent"] is None,
                    actor_handle=r["handle"],
                    published_at=_parse_time(r["published"]),
                    text=r["text"],
                    **common,
                )
            )
        return out, duplicates

    def _capture(
        self, page: Page, request: InspectionRequest, *, container: bool
    ) -> list[ArtifactCapture]:
        artifacts: list[ArtifactCapture] = []
        try:
            if Capability.PRESERVE_SCREENSHOT in request.requested:
                artifacts.append(
                    ArtifactCapture(
                        ArtifactKind.SCREENSHOT,
                        "screenshot.png",
                        page.screenshot(full_page=True),
                        "image/png",
                    )
                )
            if Capability.PRESERVE_DOM in request.requested:
                html = None
                if container and page.locator("#conversation").count():
                    html = page.locator("#conversation").first.evaluate("e => e.outerHTML")
                if html is None:
                    html = page.content()
                artifacts.append(
                    ArtifactCapture(
                        ArtifactKind.DOM_SNAPSHOT,
                        "dom.html",
                        cast(str, html).encode("utf-8"),
                        "text/html; charset=utf-8",
                    )
                )
        except PlaywrightError:
            return []
        return artifacts


def simulated_adapter_class(platform: Platform) -> type[SimulatedBrowserAdapter]:
    name = f"Simulated{platform.name.title()}BrowserAdapter"
    cls = type(name, (SimulatedBrowserAdapter,), {"platform": platform})
    return cast(type[SimulatedBrowserAdapter], cls)


def register_simulated_adapter(registry, base_url: str, platform: Platform | str) -> None:
    """Daftarkan adapter simulasi untuk SATU platform; profil browser bernama sesuai platform."""
    platform = Platform(platform)
    cls = simulated_adapter_class(platform)
    registry.register(platform, lambda: cls(base_url, profile_name=platform.value))
