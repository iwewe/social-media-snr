"""Suite kontrak adapter yang dapat dipakai ulang (WP-1.1).

Setiap adapter (tiruan, dataset uji, browser, per platform) mendaftarkan sebuah `ContractHarness`
di `harnesses.py`; suite yang SAMA dijalankan terhadap semuanya. Harness menyediakan cara membuat
adapter yang disimulasikan pada skenario tertentu memakai fixture (tanpa jaringan).

`check_contract` mengembalikan daftar pelanggaran bertanda aturan (C01...). Daftar kosong = patuh.

Aturan:
 C00 harness lengkap (skenario wajib tersedia)
 C01 capabilities(): semua kemampuan dinyatakan, platform sesuai
 C02 validate_target_url menerima URL valid dengan platform/jenis yang benar
 C03 validate_target_url menolak URL platform lain
 C04 validate_target_url menolak URL sampah
 C05 metode murni tidak memakai jaringan
 C06 inspect() tidak ditimpa (gerbang kemampuan tidak dapat dilewati)
 C07 kemampuan yang tidak runnable menghasilkan UNSUPPORTED tanpa observasi
 C08 permintaan platform lain ditolak
 C09 skenario complete -> COMPLETED dengan data
 C10 skenario partial -> PARTIAL dengan keterbatasan yang menghalangi
 C11 skenario access_restricted -> ACCESS_RESTRICTED (bukan hasil kosong yang sukses)
 C12 skenario parse_failure -> bukan COMPLETED, dengan PARSE_FAILED
 C13 identitas objek deterministik antarpemanggilan (dasar tanpa duplikasi, NFR-03)
 C14 adapter tidak melanggar invarian hasil (galat kontrak = pelanggaran)
 C15 skenario opsional (empty_post, identity_missing) berperilaku benar bila tersedia
"""

import socket
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from unittest import mock

from collection.contracts import (
    Adapter,
    Capability,
    ContractViolation,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    LimitationCode,
)
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL

REQUIRED_SCENARIOS = frozenset({"complete", "partial", "access_restricted", "parse_failure"})
OPTIONAL_SCENARIOS = frozenset({"empty_post", "identity_missing"})
RUN_ID = "run-contract-1"


@dataclass
class ContractHarness:
    name: str
    # (skenario, kemampuan yang dinonaktifkan) -> adapter yang disimulasikan
    make_adapter: Callable[[str, Collection[Capability]], Adapter]
    valid_urls: Mapping[TargetType, str]
    foreign_urls: Sequence[str]
    garbage_urls: Sequence[str]
    scenarios: frozenset[str]


class NetworkUsed(AssertionError):
    """Adapter mencoba memakai jaringan saat diuji."""


@contextmanager
def forbid_network() -> Iterator[None]:
    def blocked(*args, **kwargs):
        raise NetworkUsed("akses jaringan terdeteksi")

    with (
        mock.patch.object(socket.socket, "connect", blocked),
        mock.patch.object(socket, "getaddrinfo", blocked),
    ):
        yield


class _Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, rule: str, message: str) -> None:
        self.failures.append(f"{rule}: {message}")

    def attempt(self, rule: str, fn: Callable[[], object]) -> object | None:
        try:
            with forbid_network():
                return fn()
        except NetworkUsed:
            self.fail("C05", f"memakai jaringan saat menjalankan {rule}")
        except ContractViolation as exc:
            self.fail("C14" if rule not in ("C01",) else "C01", f"{rule}: adapter melanggar kontrak: {exc}")
        except AssertionError as exc:
            self.fail(rule, str(exc) or "asersi gagal")
        except Exception as exc:  # noqa: BLE001 - galat apa pun dari adapter adalah temuan
            self.fail(rule, f"galat tak terduga {type(exc).__name__}: {exc}")
        return None


def _request(adapter: Adapter, harness: ContractHarness, caps=None) -> InspectionRequest:
    info = adapter.validate_target_url(harness.valid_urls[TargetType.POST])
    return InspectionRequest(
        inspection_run_id=RUN_ID,
        platform=adapter.platform,
        target_url=info.normalized_url,
        target_type=info.target_type,
        requested=tuple(caps or (Capability.INSPECT_POST, Capability.INSPECT_REPLIES)),
        target_external_id=info.external_id,
    )


def _run(harness: ContractHarness, scenario: str) -> InspectionResult:
    adapter = harness.make_adapter(scenario, ())
    return adapter.inspect(_request(adapter, harness))


def _identities(result: InspectionResult) -> set[tuple]:
    return {(o.source_object_type, o.external_post_id, o.text) for o in result.observations}


def check_contract(harness: ContractHarness) -> list[str]:  # noqa: C901 - daftar periksa linear
    c = _Checker()

    missing = REQUIRED_SCENARIOS - harness.scenarios
    if missing:
        c.fail("C00", f"harness tidak menyediakan skenario wajib: {sorted(missing)}")
    if TargetType.POST not in harness.valid_urls:
        c.fail("C00", "harness wajib menyediakan valid_urls[POST]")
        return c.failures

    probe = harness.make_adapter("complete", ())

    # C01 capabilities
    def check_capabilities() -> None:
        caps = probe.capabilities()
        assert caps.platform == probe.platform, (
            f"capabilities().platform={caps.platform.value} != adapter {probe.platform.value}"
        )
        assert set(caps.declarations) == set(Capability), "ada kemampuan yang tidak dinyatakan"

    c.attempt("C01", check_capabilities)

    # C06 inspect tidak ditimpa
    if type(probe).inspect is not Adapter.inspect:
        c.fail("C06", "inspect() ditimpa; gunakan collect() agar gerbang kemampuan tetap berlaku")

    # C02-C04 validasi URL
    for kind, url in harness.valid_urls.items():
        def check_valid(kind=kind, url=url) -> None:
            info = probe.validate_target_url(url)
            assert info.platform == probe.platform, f"platform URL {info.platform.value}"
            assert info.target_type == kind, f"jenis {info.target_type.value}, diharapkan {kind.value}"
            assert info.normalized_url.startswith("https://"), "normalized_url bukan https"

        c.attempt("C02", check_valid)

    for url in harness.foreign_urls:
        def check_foreign(url=url) -> None:
            try:
                info = probe.validate_target_url(url)
            except InvalidTargetURL:
                return
            raise AssertionError(f"menerima URL platform lain: {url} -> {info.normalized_url}")

        c.attempt("C03", check_foreign)

    for url in harness.garbage_urls:
        def check_garbage(url=url) -> None:
            try:
                probe.validate_target_url(url)
            except InvalidTargetURL:
                return
            raise AssertionError(f"menerima URL sampah: {url!r}")

        c.attempt("C04", check_garbage)

    # C07 gerbang kemampuan
    for cap in (Capability.INSPECT_REPLIES, Capability.INSPECT_POST):
        def check_gate(cap=cap) -> None:
            adapter = harness.make_adapter("complete", [cap])
            result = adapter.inspect(_request(adapter, harness))
            assert result.outcome is InspectionOutcome.UNSUPPORTED, (
                f"kemampuan {cap.value} tidak runnable tetapi hasilnya {result.outcome.value}"
            )
            assert not result.observations, "UNSUPPORTED membawa observasi"
            assert any(
                lim.code is LimitationCode.UNSUPPORTED and lim.capability == cap
                for lim in result.limitations
            ), "tidak ada limitation UNSUPPORTED untuk kemampuan itu"

        c.attempt("C07", check_gate)

    # C08 platform lain
    def check_platform_mismatch() -> None:
        other = Platform.THREADS if probe.platform != Platform.THREADS else Platform.X
        request = InspectionRequest(
            RUN_ID, other, "https://example.com/x", TargetType.POST, (Capability.INSPECT_POST,)
        )
        try:
            harness.make_adapter("complete", ()).inspect(request)
        except ContractViolation:
            return
        raise AssertionError("permintaan untuk platform lain diterima")

    c.attempt("C08", check_platform_mismatch)

    # C09-C12 skenario wajib
    def scenario_checks() -> None:
        pass

    if "complete" in harness.scenarios:
        def check_complete() -> None:
            r = _run(harness, "complete")
            assert r.outcome is InspectionOutcome.COMPLETED, f"outcome {r.outcome.value}"
            assert r.observations, "tanpa observasi"
            assert all(o.platform == probe.platform for o in r.observations), "platform campur"
            assert r.coverage.pagination_complete is True

        c.attempt("C09", check_complete)

        def check_deterministic() -> None:
            first, second = _run(harness, "complete"), _run(harness, "complete")
            assert _identities(first) == _identities(second), (
                "identitas objek berbeda antarpemanggilan (reinspection akan menggandakan objek)"
            )

        c.attempt("C13", check_deterministic)

    if "partial" in harness.scenarios:
        def check_partial() -> None:
            r = _run(harness, "partial")
            assert r.outcome is InspectionOutcome.PARTIAL, f"outcome {r.outcome.value}"
            assert any(lim.code.blocking for lim in r.limitations), "tanpa keterbatasan"

        c.attempt("C10", check_partial)

    if "access_restricted" in harness.scenarios:
        def check_restricted() -> None:
            r = _run(harness, "access_restricted")
            assert r.outcome is InspectionOutcome.ACCESS_RESTRICTED, (
                f"akses ditolak dilaporkan sebagai {r.outcome.value}"
            )
            assert not r.observations

        c.attempt("C11", check_restricted)

    if "parse_failure" in harness.scenarios:
        def check_parse_failure() -> None:
            r = _run(harness, "parse_failure")
            assert r.outcome is not InspectionOutcome.COMPLETED, (
                "kegagalan parser dilaporkan COMPLETED (tampak seperti 'tidak ada komentar')"
            )
            assert any(lim.code is LimitationCode.PARSE_FAILED for lim in r.limitations), (
                "tanpa limitation PARSE_FAILED"
            )

        c.attempt("C12", check_parse_failure)

    # C15 skenario opsional
    if "empty_post" in harness.scenarios:
        def check_empty() -> None:
            r = _run(harness, "empty_post")
            assert r.outcome is InspectionOutcome.COMPLETED
            assert r.coverage.platform_displayed_count == 0
            assert r.observed_reply_count == 0

        c.attempt("C15", check_empty)

    if "identity_missing" in harness.scenarios:
        def check_identity() -> None:
            r = _run(harness, "identity_missing")
            missing_ids = [
                o for o in r.observations if o.external_post_id is None or o.external_actor_id is None
            ]
            assert missing_ids, "skenario tidak menghasilkan objek tanpa ID"
            assert all(o.identity_needs_verification for o in missing_ids)

        c.attempt("C15", check_identity)

    return c.failures
