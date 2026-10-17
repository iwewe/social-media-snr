"""WP-1.8: suite kontrak yang sama dijalankan terhadap adapter browser (halaman simulasi)."""

import pytest
from collection.browser import simulated_adapter_class
from contract_suite import REQUIRED_SCENARIOS, OPTIONAL_SCENARIOS, ContractHarness, check_contract
from harnesses import FOREIGN, GARBAGE, X_VALID
from investigations.enums import Platform

SCENARIO_MAP = {
    "complete": "complete",
    "partial": "partial",
    "access_restricted": "forbidden",
    "parse_failure": "parse_failure",
    "empty_post": "empty_post",
    "identity_missing": "identity_missing",
}


def test_browser_adapter_satisfies_the_contract(sim_server) -> None:
    def make(scenario, disable):
        cls = simulated_adapter_class(Platform.X)
        return cls(f"{sim_server.base_url}/s/{SCENARIO_MAP[scenario]}", disable=disable)

    harness = ContractHarness(
        name="browser-sim-x",
        make_adapter=make,
        valid_urls=X_VALID,
        foreign_urls=FOREIGN,
        garbage_urls=GARBAGE,
        scenarios=REQUIRED_SCENARIOS | OPTIONAL_SCENARIOS,
    )
    failures = check_contract(harness)
    assert not failures, "\n" + "\n".join(failures)


_ = pytest
