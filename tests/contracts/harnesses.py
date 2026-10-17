"""Pendaftaran adapter yang diuji suite kontrak. Adapter baru WAJIB menambah harness di sini."""

from collection.contracts import Capability
from collection.datasets import MemorySource, fixture_adapter_class
from investigations.enums import Platform
from fake_adapters import FakeXAdapter
from investigations.enums import TargetType

from contract_suite import OPTIONAL_SCENARIOS, REQUIRED_SCENARIOS, ContractHarness

X_VALID = {
    TargetType.POST: "https://x.com/someuser/status/1234567890",
    TargetType.ACCOUNT: "https://x.com/someuser",
}
FOREIGN = [
    "https://tiktok.com/@u/video/1",
    "https://instagram.com/p/XYZ/",
    "https://facebook.com/story.php?story_fbid=1&id=2",
    "https://threads.com/@u/post/AbC",
]
GARBAGE = ["", "   ", "bukan url", "javascript:alert(1)", "ftp://x.com/u/status/1", "https://x.com/"]


def harness_for(adapter_class, name: str | None = None) -> ContractHarness:
    def make(scenario: str, disable) -> object:
        return adapter_class(scenario, disable)

    return ContractHarness(
        name=name or adapter_class.__name__,
        make_adapter=make,  # type: ignore[arg-type]
        valid_urls=X_VALID,
        foreign_urls=FOREIGN,
        garbage_urls=GARBAGE,
        scenarios=REQUIRED_SCENARIOS | OPTIONAL_SCENARIOS,
    )


def fake_x() -> ContractHarness:
    return harness_for(FakeXAdapter, "fake-x")


_OBS = [
    {"type": "post", "id": "1000", "actor": "a1", "text": "Awal", "published_at": "2026-10-15T08:00:00Z"},
    {"type": "reply", "id": "1001", "actor": "a2", "parent": "1000", "text": "Setuju",
     "published_at": "2026-10-15T08:10:00Z"},
    {"type": "reply", "id": "1002", "actor": "a3", "parent": "1001", "text": None,
     "published_at": "2026-10-15T08:20:00Z"},
]


def _snapshot(outcome, complete, shown, observations, limitations=()):
    return {"observed_at": "2026-10-16T01:00:00Z", "outcome": outcome, "pagination_complete": complete,
            "displayed_count": shown, "observations": observations, "limitations": list(limitations)}


_SCENARIOS = {
    "complete": _snapshot("COMPLETED", True, 2, _OBS),
    "partial": _snapshot("PARTIAL", False, 40, _OBS[:2], [
        {"code": "PAGINATION_INCOMPLETE", "message": "Halaman berikutnya tidak termuat."}]),
    "access_restricted": _snapshot("ACCESS_RESTRICTED", None, None, [], [
        {"code": "ACCESS_RESTRICTED", "message": "Balasan butuh login."}]),
    "parse_failure": _snapshot("FAILED", None, None, [], [
        {"code": "PARSE_FAILED", "message": "Struktur halaman tak dikenali."}]),
    "empty_post": _snapshot("COMPLETED", True, 0, _OBS[:1]),
    "identity_missing": _snapshot("COMPLETED", True, 1, [
        _OBS[0],
        {"type": "reply", "id": "1001", "actor": None, "parent": "1000", "text": "Akun tak dikenal",
         "needs_verification": True}]),
}


def fixture_x() -> ContractHarness:
    def make(scenario: str, disable):
        dataset = {"schema_version": 1, "name": f"kontrak-{scenario}", "platform": "x",
                   "target_url": X_VALID[TargetType.POST], "source_method": "synthetic_fixture",
                   "snapshots": [_SCENARIOS[scenario]]}
        return fixture_adapter_class(Platform.X)(MemorySource.from_json(dataset), disable)

    return ContractHarness(
        name="fixture-dataset-x",
        make_adapter=make,
        valid_urls=X_VALID,
        foreign_urls=FOREIGN,
        garbage_urls=GARBAGE,
        scenarios=REQUIRED_SCENARIOS | OPTIONAL_SCENARIOS,
    )


# Tambahkan harness adapter nyata di sini (dataset uji WP-1.7, browser WP-1.8, platform I3).
HARNESSES = [fake_x, fixture_x]

_ = Capability  # tersedia untuk harness yang membutuhkan
