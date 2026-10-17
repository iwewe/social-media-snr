"""Adapter tiruan untuk menguji KONTRAK (WP-1.1). Bukan adapter produksi dan tidak memakai jaringan.

`FakeXAdapter` patuh pada kontrak. Subkelas `Bad*` sengaja melanggar satu aturan agar suite kontrak
terbukti benar-benar menangkapnya.
"""

import re
import socket
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from itertools import count
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

OBSERVED_AT = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
O = InspectionOutcome  # noqa: E741
S = CollectionStatus


class FakeXAdapter(Adapter):
    platform = Platform.X
    collector = CollectorInfo("fake-x", "0.0.1")

    def __init__(self, scenario: str = "complete", disable: Collection[Capability] = ()) -> None:
        self.scenario = scenario
        self.disable = frozenset(disable)

    # --- kontrak ---------------------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        declarations = {c: CapabilityDeclaration(CapabilityStatus.SUPPORTED) for c in Capability}
        for cap in self.disable:
            declarations[cap] = CapabilityDeclaration(CapabilityStatus.UNTESTED, "dinonaktifkan uji")
        return Capabilities(self.platform, declarations)

    def validate_target_url(self, url: str) -> TargetUrlInfo:
        normalized = normalize_target_url(Platform.X, url)  # raise InvalidTargetURL
        parts = urlsplit(normalized).path.strip("/").split("/")
        if len(parts) == 3 and parts[1] == "status" and parts[2].isdigit():
            return TargetUrlInfo(Platform.X, TargetType.POST, normalized, parts[2])
        if len(parts) == 1 and re.fullmatch(r"\w{1,15}", parts[0] or ""):
            return TargetUrlInfo(Platform.X, TargetType.ACCOUNT, normalized, None)
        raise InvalidTargetURL("Struktur URL X tidak dikenali.")

    def collect(self, request: InspectionRequest) -> InspectionResult:
        build = getattr(self, f"_scenario_{self.scenario}", None)
        if build is None:
            raise ValueError(f"skenario tidak dikenal: {self.scenario}")
        return build(request)

    # --- skenario --------------------------------------------------------------------------

    def _obs(self, request, post_id, kind, actor, status, parent=None, text="", ago=10, **kw):
        return Observation(
            platform=self.platform,
            source_object_type=kind,
            inspection_run_id=request.inspection_run_id,
            observed_at=OBSERVED_AT,
            collection_status=status,
            source_method=SourceMethod.SYNTHETIC_FIXTURE,
            external_post_id=post_id,
            external_actor_id=actor,
            parent_post_id=parent,
            published_at=OBSERVED_AT - timedelta(minutes=ago),
            text=text,
            **kw,
        )

    def _threads(self, request, status):
        post, reply = SourceObjectType.POST, SourceObjectType.REPLY
        return [
            self._obs(request, "1000", post, "a1", status, text="Perusahaan tidak perlu diaudit", ago=60),
            self._obs(request, "1001", reply, "a2", status, parent="1000", text="Justru audit harus dilakukan.", ago=30),
            self._obs(request, "1002", reply, "a3", status, parent="1001", text="Setuju sekali!", ago=20),
            self._obs(request, "1003", reply, "a4", status, parent="1000", text=None, ago=10),
        ]

    def _result(self, request, outcome, observations=(), limitations=(), complete=True, shown=None):
        return InspectionResult(
            platform=self.platform,
            inspection_run_id=request.inspection_run_id,
            outcome=outcome,
            collector=self.collector,
            coverage=Coverage(request.requested, complete, shown),
            observations=tuple(observations),
            limitations=tuple(limitations),
        )

    def _scenario_complete(self, request):
        return self._result(request, O.COMPLETED, self._threads(request, S.COMPLETED), shown=3)

    def _scenario_partial(self, request):
        return self._result(
            request,
            O.PARTIAL,
            self._threads(request, S.PARTIAL)[:3],
            [Limitation(LimitationCode.PAGINATION_INCOMPLETE, "Halaman berikutnya tidak termuat.")],
            complete=False,
            shown=40,
        )

    def _scenario_access_restricted(self, request):
        return self._result(
            request,
            O.ACCESS_RESTRICTED,
            limitations=[Limitation(LimitationCode.ACCESS_RESTRICTED, "Balasan butuh login.")],
            complete=None,
        )

    def _scenario_parse_failure(self, request):
        return self._result(
            request,
            O.FAILED,
            limitations=[Limitation(LimitationCode.PARSE_FAILED, "Struktur halaman tak dikenali.")],
            complete=None,
        )

    def _scenario_empty_post(self, request):
        seed = self._obs(request, "1000", SourceObjectType.POST, "a1", S.COMPLETED, text="Sepi", ago=5)
        return self._result(request, O.COMPLETED, [seed], shown=0)

    def _scenario_identity_missing(self, request):
        reply = self._obs(
            request, "1001", SourceObjectType.REPLY, None, S.COMPLETED, parent="1000",
            text="Akun tak teridentifikasi", identity_needs_verification=True,
        )
        seed = self._obs(request, "1000", SourceObjectType.POST, "a1", S.COMPLETED, text="Awal", ago=60)
        return self._result(request, O.COMPLETED, [seed, reply], shown=1)


# =============================== adapter yang SENGAJA melanggar ===============================


class BadPublishedFromObserved(FakeXAdapter):
    """Mengisi published_at dengan waktu pengambilan (dilarang, PRD bagian 9.3)."""

    def _scenario_complete(self, request):
        lazy = self._obs(request, "1000", SourceObjectType.POST, "a1", S.COMPLETED, ago=0)
        return self._result(request, O.COMPLETED, [lazy], shown=1)


class BadSwallowsParseFailure(FakeXAdapter):
    """Kegagalan parser dilaporkan sebagai 'platform menyatakan nol komentar'."""

    def _scenario_parse_failure(self, request):
        return self._result(request, O.COMPLETED, [], shown=0)


class BadSwallowsAccessRestriction(FakeXAdapter):
    """Akses ditolak dilaporkan sebagai hasil kosong yang sukses."""

    def _scenario_access_restricted(self, request):
        return self._result(request, O.COMPLETED, [], shown=0)


class BadOverridesInspect(FakeXAdapter):
    """Menimpa inspect() sehingga gerbang kemampuan dilewati."""

    def inspect(self, request):
        return self.collect(request)


class BadForeignPlatformData(FakeXAdapter):
    """Mengembalikan observasi platform lain (melanggar isolasi platform)."""

    def _scenario_complete(self, request):
        foreign = Observation(
            platform=Platform.THREADS,
            source_object_type=SourceObjectType.POST,
            inspection_run_id=request.inspection_run_id,
            observed_at=OBSERVED_AT,
            collection_status=S.COMPLETED,
            source_method=SourceMethod.SYNTHETIC_FIXTURE,
            external_post_id="9",
            external_actor_id="z",
        )
        return self._result(request, O.COMPLETED, [foreign], shown=1)


class BadAcceptsAnyUrl(FakeXAdapter):
    """Menerima URL platform lain."""

    def validate_target_url(self, url):
        return TargetUrlInfo(Platform.X, TargetType.POST, "https://x.com/u/status/1", "1")


class BadUsesNetworkInValidation(FakeXAdapter):
    """validate_target_url melakukan akses jaringan (harus murni)."""

    def validate_target_url(self, url):
        socket.getaddrinfo("example.invalid", 80)
        return super().validate_target_url(url)


class BadNondeterministicIds(FakeXAdapter):
    """ID objek berubah-ubah antarpemanggilan; reinspection akan menggandakan objek."""

    _counter = count()

    def _scenario_complete(self, request):
        n = next(self._counter)
        seed = self._obs(request, f"90{n}", SourceObjectType.POST, "a1", S.COMPLETED, text="x")
        return self._result(request, O.COMPLETED, [seed], shown=0 + 1)


class BadWrongPlatformInCapabilities(FakeXAdapter):
    def capabilities(self):
        real = super().capabilities()
        return Capabilities(Platform.THREADS, dict(real.declarations))


class BadIncompleteCapabilities(FakeXAdapter):
    def capabilities(self):
        declarations = {c: CapabilityDeclaration(CapabilityStatus.SUPPORTED) for c in Capability}
        del declarations[Capability.PRESERVE_MEDIA]  # tidak dinyatakan
        return Capabilities(self.platform, declarations)


class BadUnknownQueue(FakeXAdapter):
    execution_queue = "gpu"  # antrean yang tidak dilayani siapa pun
