"""M3 - Actor Behavior Analysis, Level A (WP-2.3; ADR 0027)."""

from .compare import PlatformMismatch, compare_profiles
from .profile import build_dimensions
from .types import DIMENSIONS, INSUFFICIENT, OK, ProfileParams, ResponseRecord

__all__ = [
    "DIMENSIONS",
    "INSUFFICIENT",
    "OK",
    "PlatformMismatch",
    "ProfileParams",
    "ResponseRecord",
    "build_dimensions",
    "compare_profiles",
]
