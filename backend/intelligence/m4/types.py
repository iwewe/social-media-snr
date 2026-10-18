"""Tipe murni jaringan M4 (WP-2.4; PRD 11.4). Tanpa Django."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

RELATION_TYPES = ("reply_to", "quote_of", "repost_of", "mentions")
UNKNOWN_TIME_POLICIES = ("include", "exclude")
WEIGHTINGS = ("count", "binary")
NOT_ASSESSED = "NOT_ASSESSED"
STRUCTURE_NOTE = (
    "Metrik ini menggambarkan STRUKTUR jaringan pada relasi yang teramati; bukan penentu "
    "pengendali, koordinasi, atau niat."
)


@dataclass(frozen=True)
class RelationRecord:
    """Satu relasi teramati: akun penulis (dari) -> akun yang dituju (ke)."""

    relation_id: int
    relation_type: str
    from_actor: int | None
    to_actor: int | None
    from_observation_id: int
    published_at: datetime | None
    stance: str | None = None  # stance respons yang membuat relasi (M2), None = tidak dinilai


@dataclass(frozen=True)
class NetworkParams:
    """Seluruh aturan eksplisit; disimpan bersama graf (FR-074)."""

    window_start: datetime
    window_end: datetime
    unknown_time: str
    relation_types: tuple[str, ...]
    weighting: str
    resolution: float
    seed: int
    compute_betweenness: bool
    metrics_max_nodes: int
    stability_seeds: (
        int  # 0 = tidak diukur; selain itu jumlah seed untuk mengukur kestabilan komunitas
    )


@dataclass
class Edge:
    from_actor: int
    to_actor: int
    relation_type: str
    weight: int
    observation_ids: tuple[int, ...]
    stance_counts: dict[str, int]
    first_published_at: datetime | None
    last_published_at: datetime | None


@dataclass
class Network:
    nodes: dict[int, dict[str, Any]]
    edges: list[Edge]
    exclusions: Counter = field(default_factory=Counter)
    metrics: dict[str, Any] = field(default_factory=dict)

    def undirected_weights(self) -> dict[tuple[int, int], int]:
        out: dict[tuple[int, int], int] = {}
        for e in self.edges:
            key = (min(e.from_actor, e.to_actor), max(e.from_actor, e.to_actor))
            out[key] = out.get(key, 0) + e.weight
        return out
