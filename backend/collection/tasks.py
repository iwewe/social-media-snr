"""Tugas Celery untuk orkestrasi inspeksi (WP-1.6).

`acks_late` dan `reject_on_worker_lost` global (settings): pesan baru dikonfirmasi setelah tugas
selesai dan dikirim ulang bila pekerja mati. Pengiriman ulang aman karena `run_inspection` hanya
mengeksekusi run PENDING (at-most-once); run yang ditinggal mati pekerja ditandai oleh penyapu.
"""

import os
import socket
from typing import Any

from celery import shared_task
from django.conf import settings

from collection.orchestrator.service import run_inspection, sweep_stale_runs

_LIMIT = getattr(settings, "SNR_INSPECTION_SOFT_TIME_LIMIT", None)
# Tanpa angka bawaan: batas waktu hanya dipasang bila ditetapkan eksplisit (harus diukur).
_OPTIONS: dict[str, Any] = {"soft_time_limit": _LIMIT} if _LIMIT else {}


@shared_task(bind=True, name="snr.execute_inspection", **_OPTIONS)
def execute_inspection(self: Any, run_pk: int) -> dict[str, Any]:
    claimed_by = f"{socket.gethostname()}:{os.getpid()}:{self.request.id or 'lokal'}"
    return run_inspection(run_pk, claimed_by=claimed_by).to_dict()


@shared_task(name="snr.sweep_stale_inspections")
def sweep_stale_inspections(older_than_seconds: int) -> list[int]:
    return sweep_stale_runs(older_than_seconds=older_than_seconds)
