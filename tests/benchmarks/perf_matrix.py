"""Percobaan terkontrol anomali performa ingestion/rekonsiliasi (A2). Bukan tes.

Berbeda dari ingestion_bench.py: transaksi SUNGGUHAN (di-commit seperti produksi), bukan rollback,
dan tiap skenario memakai database baru. Dijalankan oleh deployment/perf.sh dengan variabel:
  PERF_N (objek per run), PERF_REPS (jumlah target berurutan: data bertumbuh seperti produksi),
  PERF_ANALYZE (never | after_ingest), PERF_AUTOVACUUM (on | off), PERF_JIT (on | off),
  PERF_SPLIT (0/1: sebagian objek tanpa ID agar jalur kandidat ikut dipakai).
Keluaran: satu baris JSON per target.
"""

import json
import os
import time
from datetime import UTC, datetime, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collection import services  # noqa: E402
from collection.contracts import (  # noqa: E402
    Capability, CollectionStatus, CollectorInfo, Coverage, InspectionOutcome, InspectionResult,
    Observation, SourceMethod, SourceObjectType,
)
from collection.ingestion import ingest_result  # noqa: E402
from collection.reconciliation import reconcile_run  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connection  # noqa: E402
from investigations import services as inv_services  # noqa: E402
from investigations.enums import Platform, TargetType  # noqa: E402

N = int(os.environ.get("PERF_N", "10000"))
REPS = int(os.environ.get("PERF_REPS", "3"))
ANALYZE = os.environ.get("PERF_ANALYZE", "never")
AUTOVAC = os.environ.get("PERF_AUTOVACUUM", "on")
JIT = os.environ.get("PERF_JIT", "on")
SPLIT = os.environ.get("PERF_SPLIT", "1") == "1"
OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
TABLES = ["collection_post", "collection_actoraccount", "collection_postobservation",
          "collection_postrelation", "collection_inspectionrun",
          "collection_observationreconciliation"]


def build(run, count, prefix="b", edit_every=0, no_id_every=0):
    obs = []
    for i in range(count):
        text = f"balasan sintetis nomor {i}" + (" (diedit)" if edit_every and i % edit_every == 0 else "")
        missing_id = bool(no_id_every) and i % no_id_every == 0
        obs.append(Observation(
            platform=Platform.X, source_object_type=SourceObjectType.REPLY,
            inspection_run_id=run.run_id, observed_at=OBSERVED,
            collection_status=CollectionStatus.COMPLETED, source_method=SourceMethod.SYNTHETIC_FIXTURE,
            external_post_id=None if missing_id else f"{prefix}{i}",
            external_actor_id=f"actor-{i % 200}",
            identity_needs_verification=missing_id,
            parent_post_id="root" if i % 3 else (f"{prefix}{max(i - 1, 0)}" if i else "root"),
            published_at=OBSERVED - timedelta(minutes=1 + i % 500), text=text,
        ))
    return InspectionResult(
        platform=Platform.X, inspection_run_id=run.run_id, outcome=InspectionOutcome.COMPLETED,
        collector=CollectorInfo("perf", "0"),
        coverage=Coverage((Capability.INSPECT_REPLIES,), True, count), observations=tuple(obs))


FIX_FUNCTIONS = [
    "snr_run_platform(bigint)", "snr_identity_platform_guard()", "snr_observation_platform_guard()",
    "snr_relation_platform_guard()", "snr_reconciliation_guard()", "snr_artifact_platform_guard()",
]


def apply_variant(cursor, variant: str) -> None:
    """Varian perbaikan untuk perbandingan: none (tanpa), custom (force_custom_plan),
    seqscan (enable_seqscan=off), keep (biarkan hasil migrasi)."""
    if variant == "keep":
        return
    for function in FIX_FUNCTIONS:
        cursor.execute(f"ALTER FUNCTION {function} RESET plan_cache_mode")
        cursor.execute(f"ALTER FUNCTION {function} RESET enable_seqscan")
        if variant == "custom":
            cursor.execute(f"ALTER FUNCTION {function} SET plan_cache_mode = force_custom_plan")
        elif variant == "seqscan":
            cursor.execute(f"ALTER FUNCTION {function} SET enable_seqscan = off")


def analyze() -> float:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"ANALYZE {table}")
    return time.perf_counter() - started


def main() -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"SET jit = {JIT}")
        apply_variant(cursor, os.environ.get("PERF_FIX", "keep"))
        for table in TABLES:
            cursor.execute(f"ALTER TABLE {table} SET (autovacuum_enabled = {'true' if AUTOVAC == 'on' else 'false'})")
    user = User.objects.create_user("perf", password="x")
    inv = inv_services.create_investigation(user=user, name="perf")
    no_id = 20 if SPLIT else 0
    for rep in range(REPS):
        target = inv_services.register_target(
            investigation=inv, user=user, platform=Platform.X, target_type=TargetType.POST,
            url=f"https://x.com/perf/status/{rep + 1}")
        row = {"rep": rep, "n": N, "analyze": ANALYZE, "autovacuum": AUTOVAC, "jit": JIT}
        run1 = services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_REPLIES])
        t = time.perf_counter()
        assert ingest_result(run1, build(run1, N, no_id_every=no_id)).ok
        row["ingest1_s"] = round(time.perf_counter() - t, 2)
        if ANALYZE == "after_ingest":
            row["analyze1_s"] = round(analyze(), 2)
        reconcile_run(run1)
        run2 = services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_REPLIES])
        t = time.perf_counter()
        assert ingest_result(run2, build(run2, N, edit_every=100, no_id_every=no_id)).ok
        row["ingest2_s"] = round(time.perf_counter() - t, 2)
        if ANALYZE == "after_ingest":
            row["analyze2_s"] = round(analyze(), 2)
        t = time.perf_counter()
        reconcile_run(run2)
        row["reconcile_s"] = round(time.perf_counter() - t, 2)
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
