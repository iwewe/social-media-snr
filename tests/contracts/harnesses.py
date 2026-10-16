"""Pendaftaran adapter yang diuji suite kontrak. Adapter baru WAJIB menambah harness di sini."""

from collection.contracts import Capability
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


# Tambahkan harness adapter nyata di sini (dataset uji WP-1.7, browser WP-1.8, platform I3).
HARNESSES = [fake_x]

_ = Capability  # tersedia untuk harness yang membutuhkan
