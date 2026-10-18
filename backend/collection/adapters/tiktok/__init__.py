"""Adapter TikTok (WP-3.3): DINONAKTIFKAN; lihat docs/adapters/tiktok-feasibility.md."""

from typing import ClassVar

from collection.adapters.pending import PendingPermissionAdapter, TargetPattern
from collection.contracts import CollectorInfo
from investigations.enums import Platform, TargetType


class TikTokAdapter(PendingPermissionAdapter):
    platform: ClassVar[Platform] = Platform.TIKTOK
    collector: ClassVar[CollectorInfo] = CollectorInfo("snr-tiktok-disabled", "0.1")
    feasibility_doc: ClassVar[str] = "docs/adapters/tiktok-feasibility.md"
    short_hosts = frozenset({"vm.tiktok.com", "vt.tiktok.com"})
    patterns = (
        # ID video numerik pada URL adalah ID platform (stabil).
        TargetPattern(
            TargetType.POST,
            r"/@(?P<user>[A-Za-z0-9._]{1,40})/video/(?P<id>\d{1,25})",
            stable_id=True,
        ),
        # Tautan pendek (vm./vt.tiktok.com): jenis dan ID tidak dapat diturunkan tanpa jaringan.
        TargetPattern(
            TargetType.POST,
            r"/(?P<short>[A-Za-z0-9]{6,20})",
            hosts=("vm.tiktok.com", "vt.tiktok.com"),
        ),
        TargetPattern(TargetType.ACCOUNT, r"/@(?P<name>[A-Za-z0-9._]{1,40})"),
    )
