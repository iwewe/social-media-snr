"""Adapter Instagram (WP-3.4): DINONAKTIFKAN; lihat docs/adapters/instagram-feasibility.md."""

from typing import ClassVar

from collection.adapters.pending import PendingPermissionAdapter, TargetPattern
from collection.contracts import CollectorInfo
from investigations.enums import Platform, TargetType


class InstagramAdapter(PendingPermissionAdapter):
    platform: ClassVar[Platform] = Platform.INSTAGRAM
    collector: ClassVar[CollectorInfo] = CollectorInfo("snr-instagram-disabled", "0.1")
    feasibility_doc: ClassVar[str] = "docs/adapters/instagram-feasibility.md"
    reserved_accounts = frozenset(
        {
            "explore",
            "accounts",
            "direct",
            "reels",
            "stories",
            "p",
            "reel",
            "tv",
            "about",
            "legal",
            "developer",
            "directory",
            "web",
            "api",
        }
    )
    patterns = (
        # Shortcode pada URL BUKAN ID media yang dipakai API: tidak dijadikan ID stabil.
        TargetPattern(
            TargetType.POST,
            r"/(?:[A-Za-z0-9._]{1,30}/)?(?:p|reel|reels|tv)/(?P<code>[A-Za-z0-9_-]{5,20})",
        ),
        TargetPattern(TargetType.ACCOUNT, r"/(?P<name>[A-Za-z0-9._]{1,30})"),
    )
