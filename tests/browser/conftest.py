"""Tes browser (WP-1.8): butuh Chromium Playwright, jadi dijalankan di image `worker-browser`/CI.

Tanpa Chromium tes dilewati, KECUALI `SNR_REQUIRE_BROWSER=1` (CI dan `make test`): lalu kegagalan
menyediakan browser menggagalkan tes, bukan diam-diam menghijaukannya.
"""

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
for extra in (TESTS, TESTS / "contracts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _chromium_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).exists()
    except Exception:  # noqa: BLE001 - tidak tersedia
        return False


@pytest.fixture(scope="session")
def browser_ready() -> None:
    if _chromium_ready():
        return
    if os.environ.get("SNR_REQUIRE_BROWSER") == "1":
        pytest.fail("SNR_REQUIRE_BROWSER=1 tetapi Chromium Playwright tidak tersedia")
    pytest.skip("Chromium Playwright tidak tersedia")


@pytest.fixture(scope="session")
def sim_server():
    from collection.simulation import SimulationServer

    with SimulationServer() as server:
        yield server


@pytest.fixture(autouse=True)
def _fresh_simulation(sim_server, browser_ready):
    sim_server.reset()
    yield
