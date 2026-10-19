"""Tugas Celery analisis I2 (WP-2.9): mengeksekusi AnalysisRun PENDING di worker, bukan proses web.

`execute_run` hanya mengeksekusi run PENDING (klaim atomik); pengiriman ulang atau tugas ganda
aman: yang kedua melaporkan "sudah dijalankan" tanpa mengubah apa pun. Kegagalan metode dicatat
pada run (FAILED + pesan), bukan disembunyikan atau dilempar ulang.
"""

from typing import Any

from celery import shared_task

from . import services
from .errors import AnalysisError
from .models import AnalysisRun


@shared_task(name="snr.execute_analysis")
def execute_analysis(run_pk: int) -> dict[str, Any]:
    run = AnalysisRun.objects.filter(pk=run_pk).first()
    if run is None:
        return {"run": run_pk, "handled": False, "status": "MISSING"}
    try:
        done = services.execute_run(run)
    except AnalysisError:  # sudah dijalankan oleh pekerja lain
        current = AnalysisRun.objects.get(pk=run_pk)
        return {"run": run_pk, "handled": False, "status": current.status}
    return {"run": run_pk, "handled": True, "status": done.status}
