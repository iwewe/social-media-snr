"""Penjadwalan penyapu run basi (A1; ADR 0019). Murni dan tanpa Django, agar mudah diuji.

Penyapu menandai run RUNNING yang ditinggal mati pekerja agar target tidak terkunci selamanya
(aturan satu-run-aktif). Batas waktunya TIDAK punya angka bawaan: PRD tidak menetapkannya dan harus
diukur pada adapter nyata (`manage.py inspection_durations`). Penjadwalan hanya aktif bila operator
menetapkan DUA nilai secara eksplisit; salah satu saja, atau nilai tidak masuk akal, menghentikan
startup dengan pesan jelas (gagal keras lebih baik daripada penyapu yang diam-diam mati).
"""

import re
from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ImproperlyConfigured

OLDER_THAN_VAR = "SNR_SWEEP_OLDER_THAN_SECONDS"
INTERVAL_VAR = "SNR_SWEEP_INTERVAL_SECONDS"
TASK_NAME = "snr.sweep_stale_inspections"
ENTRY_NAME = "snr-sweep-stale-inspections"


def _positive_int(env: Mapping[str, str], name: str) -> int | None:
    raw = (env.get(name) or "").strip()
    if not raw:
        return None
    # Hanya digit ASCII: int() menerima digit Unicode lain (mis. Arab-Indik) yang pasti salah ketik.
    if not re.fullmatch(r"[0-9]+", raw):
        raise ImproperlyConfigured(
            f"{name} harus bilangan bulat positif (detik, digit 0-9), bukan {raw!r}."
        )
    value = int(raw)
    if value <= 0:
        raise ImproperlyConfigured(f"{name} harus lebih dari 0 (detik), bukan {value}.")
    return value


def sweep_settings(env: Mapping[str, str], soft_time_limit: int | None) -> tuple[int, int] | None:
    """(older_than, interval) bila penyapu dijadwalkan; None bila tidak dikonfigurasi."""
    older = _positive_int(env, OLDER_THAN_VAR)
    interval = _positive_int(env, INTERVAL_VAR)
    if older is None and interval is None:
        return None
    if older is None or interval is None:
        missing = OLDER_THAN_VAR if older is None else INTERVAL_VAR
        raise ImproperlyConfigured(
            f"Penyapu run basi butuh {OLDER_THAN_VAR} dan {INTERVAL_VAR} sekaligus; "
            f"{missing} belum diisi."
        )
    if interval > older:
        raise ImproperlyConfigured(
            f"{INTERVAL_VAR} ({interval}) tidak boleh lebih besar dari {OLDER_THAN_VAR} ({older}): "
            "run basi akan terlambat ditandai melebihi batasnya."
        )
    if soft_time_limit is not None and older <= soft_time_limit:
        raise ImproperlyConfigured(
            f"{OLDER_THAN_VAR} ({older}) harus lebih besar dari SNR_INSPECTION_SOFT_TIME_LIMIT "
            f"({soft_time_limit}); kalau tidak, penyapu menandai run yang masih sah berjalan."
        )
    return older, interval


def beat_schedule(env: Mapping[str, str], soft_time_limit: int | None) -> dict[str, Any]:
    """Isi `CELERY_BEAT_SCHEDULE`: kosong bila penyapu tidak dikonfigurasi."""
    parsed = sweep_settings(env, soft_time_limit)
    if parsed is None:
        return {}
    older, interval = parsed
    return {
        ENTRY_NAME: {
            "task": TASK_NAME,
            "schedule": float(interval),
            "args": [older],
            "options": {"queue": "analysis"},
        }
    }
