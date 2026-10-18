"""Adapter X (WP-3.1): DINONAKTIFKAN; lihat docs/adapters/x-feasibility.md dan pending.py."""

from typing import ClassVar

from collection.adapters.pending import PendingPermissionAdapter, TargetPattern
from collection.contracts import CollectorInfo
from investigations.enums import Platform, TargetType


class XAdapter(PendingPermissionAdapter):
    platform: ClassVar[Platform] = Platform.X
    collector: ClassVar[CollectorInfo] = CollectorInfo("snr-x-disabled", "0.1")
    feasibility_doc: ClassVar[str] = "docs/adapters/x-feasibility.md"
    reserved_accounts = frozenset(
        {
            "home",
            "explore",
            "notifications",
            "messages",
            "search",
            "settings",
            "i",
            "compose",
            "login",
            "signup",
            "tos",
            "privacy",
            "hashtag",
            "intent",
            "share",
        }
    )
    patterns = (
        # ID posting pada URL adalah ID yang sama dengan ID platform (stabil).
        TargetPattern(
            TargetType.POST,
            r"/(?P<user>[A-Za-z0-9_]{1,15})/status/(?P<id>\d{1,25})",
            stable_id=True,
        ),
        # Handle dapat berganti: bukan ID stabil.
        TargetPattern(TargetType.ACCOUNT, r"/(?P<name>[A-Za-z0-9_]{1,15})"),
    )
