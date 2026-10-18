"""Adapter Facebook (WP-3.5): DINONAKTIFKAN; lihat docs/adapters/facebook-feasibility.md."""

from typing import ClassVar

from collection.adapters.pending import PendingPermissionAdapter, TargetPattern
from collection.contracts import CollectorInfo
from investigations.enums import Platform, TargetType


class FacebookAdapter(PendingPermissionAdapter):
    platform: ClassVar[Platform] = Platform.FACEBOOK
    collector: ClassVar[CollectorInfo] = CollectorInfo("snr-facebook-disabled", "0.1")
    feasibility_doc: ClassVar[str] = "docs/adapters/facebook-feasibility.md"
    reserved_accounts = frozenset(
        {
            "watch",
            "groups",
            "marketplace",
            "events",
            "pages",
            "login",
            "gaming",
            "reel",
            "reels",
            "stories",
            "share",
            "permalink.php",
            "photo.php",
            "story.php",
            "profile.php",
            "help",
            "policies",
        }
    )
    short_hosts = frozenset({"fb.watch"})
    # ID gabungan (halaman_posting), pfbid, dan tautan pendek tidak dijadikan ID stabil.
    patterns = (
        TargetPattern(
            TargetType.POST,
            r"/(?P<page>[A-Za-z0-9.\-]{1,80})/(?:posts|videos)/(?P<post>[A-Za-z0-9]{5,60})",
        ),
        TargetPattern(
            TargetType.POST,
            r"/groups/(?P<group>[A-Za-z0-9.\-]{1,80})/(?:posts|permalink)/(?P<post>\d{5,25})",
        ),
        TargetPattern(
            TargetType.POST, r"/permalink\.php\?id=\d{1,25}&story_fbid=[A-Za-z0-9]{5,60}"
        ),
        TargetPattern(TargetType.POST, r"/story\.php\?id=\d{1,25}&story_fbid=[A-Za-z0-9]{5,60}"),
        TargetPattern(TargetType.POST, r"/watch\?v=\d{5,25}"),
        TargetPattern(TargetType.POST, r"/share/[pvr]/[A-Za-z0-9]{5,30}"),
        TargetPattern(TargetType.POST, r"/(?P<short>[A-Za-z0-9]{5,20})", hosts=("fb.watch",)),
        TargetPattern(TargetType.ACCOUNT, r"/profile\.php\?id=\d{1,25}"),
        TargetPattern(TargetType.ACCOUNT, r"/(?P<name>[A-Za-z0-9.\-]{5,80})"),
    )
