"""Peluncuran browser Playwright untuk adapter (WP-1.8). Hanya worker-browser yang memakainya.

- Profil browser (sesi/cookies) disimpan di `browser-profiles/`, TERPISAH dari bukti (PRD
  bagian 10). Isi profil tidak pernah dibaca, disalin ke artefak, dilog, atau dilaporkan; hanya
  direktorinya yang disiapkan (mode 0700).
- Profil Chromium hanya dapat dipakai satu proses sekaligus; worker-browser berkonkurensi 1.
- Sandbox Chromium tetap aktif secara bawaan. `no_sandbox=True` hanya untuk lingkungan yang
  memang tidak mendukungnya dan harus dipilih secara sadar.
"""

import importlib.metadata
import os
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from preservation.storage import browser_profiles_root

DEFAULT_TIMEOUT_MS = 30_000  # bawaan Playwright, ditulis eksplisit; belum diukur pada situs nyata


@dataclass(frozen=True)
class BrowserVersions:
    playwright: str
    browser: str

    def label(self) -> str:
        return f"playwright {self.playwright}, chromium {self.browser}"


def prepare_profile_dir(name: str) -> Path:
    """Direktori profil `<akar profil>/<name>`, dibuat bertahap dengan mode 0700.

    Nama hanya boleh satu komponen sederhana; hasilnya harus tetap di dalam akar profil."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("nama profil harus satu komponen sederhana")
    root = browser_profiles_root()
    target = root / name
    for directory in (root, target):
        if directory.is_symlink():
            raise ValueError("direktori profil tidak boleh berupa symlink")
        if not directory.exists():
            os.mkdir(directory, 0o700)
            os.chmod(directory, 0o700)  # abaikan umask
    if target.resolve().parent != root.resolve():
        raise ValueError("profil berada di luar akar profil")
    return target


class BrowserSession:
    """Konteks peluncuran: `with BrowserSession(profile_dir=...) as s: page = s.new_page()`."""

    def __init__(
        self,
        *,
        profile_dir: Path | None = None,
        headless: bool = True,
        no_sandbox: bool = False,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.no_sandbox = no_sandbox
        self.timeout_ms = timeout_ms
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None
        self.versions = BrowserVersions(importlib.metadata.version("playwright"), "unknown")

    def __enter__(self) -> "BrowserSession":
        args = ["--no-sandbox"] if self.no_sandbox else []
        self._pw = sync_playwright().start()
        try:
            if self.profile_dir is not None:
                self._context = self._pw.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    headless=self.headless,
                    args=args,
                    accept_downloads=False,
                )
                browser = self._context.browser
            else:
                browser = self._pw.chromium.launch(headless=self.headless, args=args)
                self._context = browser.new_context(accept_downloads=False)
            if browser is not None:
                self.versions = BrowserVersions(self.versions.playwright, browser.version)
            self._context.set_default_timeout(self.timeout_ms)
            self._context.set_default_navigation_timeout(self.timeout_ms)
        except BaseException:
            self._shutdown()
            raise
        return self

    @property
    def context(self) -> BrowserContext:
        assert self._context is not None, "BrowserSession belum dimulai"
        return self._context

    def new_page(self) -> Page:
        return self.context.new_page()

    def _shutdown(self) -> None:
        try:
            if self._context is not None:
                browser = self._context.browser
                self._context.close()
                if self.profile_dir is None and browser is not None:
                    browser.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            self._context = None
            self._pw = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._shutdown()
