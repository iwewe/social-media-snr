"""Registri metode analisis. Metode murni dan deterministik atas masukan yang dibekukan.

`dataset-summary` v1 adalah metode pertama: ringkasan hitungan dataset. Ia ada agar rantai
DatasetVersion -> AnalysisRun -> keluaran dapat diuji ujung ke ujung (reproduksibilitas,
NFR-01) sebelum
metode M2/M3/M4 ditambahkan; ia bukan analisis perilaku dan tidak menyimpulkan apa pun tentang akun.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from collection.models import PostObservation

from .errors import InvalidParameters, UnknownMethod


@dataclass(frozen=True)
class Frozen:
    """Masukan beku yang diberikan kepada metode."""

    platform: str
    observation_ids: tuple[int, ...]
    issue_context_version: int | None
    target_context_versions: dict[int, int | None]
    run_id: int


@dataclass(frozen=True)
class Method:
    name: str
    version: str
    validate: Callable[[dict[str, Any]], None]
    run: Callable[[Frozen, dict[str, Any]], dict[str, Any]]


def _validate_summary(parameters: dict[str, Any]) -> None:
    if set(parameters) != {"top_authors"}:
        raise InvalidParameters("parameter wajib: top_authors (tanpa parameter lain)")
    value = parameters["top_authors"]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1000:
        raise InvalidParameters("top_authors harus bilangan bulat 0..1000")


def _run_summary(frozen: Frozen, parameters: dict[str, Any]) -> dict[str, Any]:
    rows = list(
        PostObservation.objects.filter(id__in=frozen.observation_ids)
        .order_by("id")
        .values_list("post_id", "author_id", "source_object_type", "run_id")
    )
    authors = Counter(a for _, a, _, _ in rows if a is not None)
    top = sorted(authors.items(), key=lambda kv: (-kv[1], kv[0]))[: parameters["top_authors"]]
    return {
        "platform": frozen.platform,
        "observations": len(rows),
        "posts": len({p for p, _, _, _ in rows}),
        "runs": len({r for _, _, _, r in rows}),
        "by_type": dict(sorted(Counter(t for _, _, t, _ in rows).items())),
        "observations_without_author": sum(1 for _, a, _, _ in rows if a is None),
        "top_authors": [{"actor_id": a, "observations": n} for a, n in top],
        "issue_context_version": frozen.issue_context_version,
        "target_context_versions": {
            str(k): v for k, v in sorted(frozen.target_context_versions.items())
        },
    }


REGISTRY: dict[str, Method] = {
    "dataset-summary": Method("dataset-summary", "1", _validate_summary, _run_summary),
}


def get_method(name: str) -> Method:
    try:
        return REGISTRY[name]
    except KeyError:
        raise UnknownMethod(f"metode analisis tidak dikenal: {name}") from None


from . import assessment as _assessment  # noqa: E402 - mendaftarkan m2-rules

_assessment.register()
