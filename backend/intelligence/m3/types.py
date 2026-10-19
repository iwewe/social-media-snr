"""Tipe murni profil aktor M3 (WP-2.3; PRD 11.3). Tanpa Django: dapat diuji tanpa basis data."""

from dataclasses import dataclass
from datetime import datetime

INSUFFICIENT = "INSUFFICIENT_DATA"
OK = "OK"
DIMENSIONS = (
    "participation",
    "stance_distribution",
    "response_character",
    "temporal_activity",
    "target_concentration",
    "narrative_consistency",
    "activity_evolution",
)


@dataclass(frozen=True)
class ResponseRecord:
    """Satu respons teramati milik satu akun beserta penilaian M2 yang berlaku."""

    observation_id: int
    actor_id: int
    target_id: int
    parent_post_id: int | None
    published_at: datetime | None
    text: str | None
    stance: str
    characters: tuple[str, ...]
    # Satu Post = satu respons (observasi terbarunya). Dua angka di bawah melaporkan RIWAYAT-nya
    # menjadikannya aktivitas tambahan: berapa kali Post itu teramati, dan berapa teks berbeda.
    observation_count: int = 1
    text_variants: int = 1


@dataclass(frozen=True)
class ProfileParams:
    """Seluruh ambang eksplisit (ADR 0024: tanpa nilai bawaan tersembunyi)."""

    period_start: datetime
    period_end: datetime
    min_responses: int
    bucket_hours: int
    min_active_buckets: int
    narrative_min_texts: int
