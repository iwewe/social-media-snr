"""Toolkit browser (Playwright) dan adapter simulasi (WP-1.8). Hanya worker-browser."""

from .runtime import BrowserSession, BrowserVersions, prepare_profile_dir
from .simulated import (
    SimulatedBrowserAdapter,
    register_simulated_adapter,
    simulated_adapter_class,
)

__all__ = [
    "BrowserSession",
    "BrowserVersions",
    "SimulatedBrowserAdapter",
    "prepare_profile_dir",
    "register_simulated_adapter",
    "simulated_adapter_class",
]
