"""Adapter Threads (WP-3.2): DINONAKTIFKAN; lihat docs/adapters/threads-feasibility.md."""

from typing import ClassVar

from collection.adapters.pending import PendingPermissionAdapter, TargetPattern
from collection.contracts import CollectorInfo
from investigations.enums import Platform, TargetType


class ThreadsAdapter(PendingPermissionAdapter):
    platform: ClassVar[Platform] = Platform.THREADS
    collector: ClassVar[CollectorInfo] = CollectorInfo("snr-threads-disabled", "0.1")
    feasibility_doc: ClassVar[str] = "docs/adapters/threads-feasibility.md"
    patterns = (
        # Kode pada URL BUKAN ID media yang dipakai API: tidak dijadikan ID stabil.
        TargetPattern(
            TargetType.POST, r"/@(?P<user>[A-Za-z0-9._]{1,30})/post/(?P<code>[A-Za-z0-9_-]{5,20})"
        ),
        TargetPattern(TargetType.ACCOUNT, r"/@(?P<name>[A-Za-z0-9._]{1,30})"),
    )
