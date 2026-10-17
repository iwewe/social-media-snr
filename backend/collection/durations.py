"""Pengukuran durasi run (A1): dasar menetapkan batas waktu penyapu dan soft time limit.

Hanya run yang selesai oleh pekerja yang diukur. Run yang dihentikan penyapu tidak ikut (durasinya
adalah batas penyapu itu sendiri, bukan lama eksekusi) tetapi dihitung terpisah: angka itu justru
menunjukkan batas yang terlalu rendah atau pekerja yang sering mati.

Persentil memakai nearest-rank (tanpa interpolasi); dengan sampel kecil p95 = nilai terbesar.
Angka dari dataset sintetis atau simulasi BUKAN dasar untuk platform nyata.
"""

import math
from typing import Any

from .models import InspectionRun, RunStatus

SWEPT_MARKER = "dihentikan penyapu"
FINAL = (
    RunStatus.COMPLETED,
    RunStatus.PARTIAL,
    RunStatus.FAILED,
    RunStatus.ACCESS_RESTRICTED,
    RunStatus.UNSUPPORTED,
    RunStatus.REVIEW_REQUIRED,
)


def percentile(sorted_values: list[float], q: float) -> float:
    """Nearest-rank: nilai terkecil yang mencakup q persen sampel (q dalam (0, 100])."""
    if not sorted_values:
        raise ValueError("tidak ada sampel")
    if not 0 < q <= 100:
        raise ValueError("q harus di (0, 100]")
    rank = math.ceil(q / 100 * len(sorted_values))
    return sorted_values[rank - 1]


def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "p50": percentile(ordered, 50),
        "p95": percentile(ordered, 95),
        "max": ordered[-1],
    }


def _swept(run: InspectionRun) -> bool:
    return any(SWEPT_MARKER in str(item.get("message", "")) for item in run.limitations or [])


def duration_report() -> list[dict[str, Any]]:
    """Statistik per pengambil data: lama eksekusi, antrean, dan jumlah run yang disapu."""
    runs = InspectionRun.objects.filter(
        status__in=FINAL, started_at__isnull=False, finished_at__isnull=False
    ).exclude(collector_name="")
    groups: dict[str, dict[str, Any]] = {}
    for run in runs:
        group = groups.setdefault(
            run.collector_name, {"collector": run.collector_name, "run": [], "wait": [], "swept": 0}
        )
        if _swept(run):
            group["swept"] += 1
            continue
        assert run.started_at and run.finished_at
        group["run"].append((run.finished_at - run.started_at).total_seconds())
        group["wait"].append((run.started_at - run.created_at).total_seconds())
    report = []
    for name in sorted(groups):
        g = groups[name]
        if not g["run"]:
            report.append({"collector": name, "n": 0, "swept": g["swept"]})
            continue
        report.append(
            {
                "collector": name,
                "n": len(g["run"]),
                "swept": g["swept"],
                "execution_seconds": _stats(g["run"]),
                "queue_wait_seconds": _stats(g["wait"]),
            }
        )
    return report
