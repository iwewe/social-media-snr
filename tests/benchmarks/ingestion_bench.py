"""Pengukuran biaya ingestion (WP-1.3). Bukan tes: tidak dikoleksi pytest.

Dijalankan DI DALAM transaksi yang selalu di-ROLLBACK, jadi database dev tidak berubah:

    docker compose run --rm -T web python manage.py shell -c \
        "exec(open('/tests/benchmarks/ingestion_bench.py').read())"

Membandingkan ingestion dengan trigger penjaga aktif (kondisi nyata) dan dengan trigger pengguna
dinonaktifkan sementara (hanya untuk mengukur biayanya; tidak pernah dilakukan di data nyata).
Hasil pada mesin dev hanyalah gambaran relatif, bukan target performa produksi.
"""

import time
import uuid
from datetime import UTC, datetime, timedelta

from collection import services
from collection.contracts import (
    Capability,
    CollectionStatus,
    CollectorInfo,
    Coverage,
    InspectionOutcome,
    InspectionResult,
    Observation,
    SourceMethod,
    SourceObjectType,
)
from collection.ingestion import ingest_result
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

TABLES = [
    "collection_post",
    "collection_actoraccount",
    "collection_postobservation",
    "collection_postrelation",
    "collection_inspectionrun",
]
OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)


class _Rollback(Exception):
    pass


def _build(run, n):
    return InspectionResult(
        platform=Platform.X,
        inspection_run_id=run.run_id,
        outcome=InspectionOutcome.COMPLETED,
        collector=CollectorInfo("bench", "0"),
        coverage=Coverage((Capability.INSPECT_REPLIES,), True, n),
        observations=tuple(
            Observation(
                platform=Platform.X,
                source_object_type=SourceObjectType.REPLY,
                inspection_run_id=run.run_id,
                observed_at=OBSERVED,
                collection_status=CollectionStatus.COMPLETED,
                source_method=SourceMethod.SYNTHETIC_FIXTURE,
                external_post_id=f"b{i}",
                external_actor_id=f"actor-{i % 200}",
                parent_post_id="root" if i % 3 else f"b{max(i - 1, 0)}" if i else "root",
                published_at=OBSERVED - timedelta(minutes=1 + i % 500),
                text=f"balasan sintetis nomor {i}",
            )
            for i in range(n)
        ),
    )


def measure(n, batch, triggers_enabled):
    try:
        with transaction.atomic():
            user = User.objects.create_user(f"bench-{uuid.uuid4().hex[:8]}", password="x")
            inv = inv_services.create_investigation(user=user, name="bench")
            target = inv_services.register_target(
                investigation=inv, user=user, platform=Platform.X,
                target_type=TargetType.POST, url="https://x.com/bench/status/1",
            )
            run = services.create_inspection_run(
                target=target, user=user, requested=[Capability.INSPECT_REPLIES]
            )
            result = _build(run, n)
            if not triggers_enabled:
                with connection.cursor() as cursor:
                    # Selesaikan dulu pengecekan FK yang tertunda; kalau tidak, PostgreSQL menolak ALTER.
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    for table in TABLES:
                        cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
            with CaptureQueriesContext(connection) as ctx:
                started = time.perf_counter()
                report = ingest_result(run, result, batch_size=batch)
                elapsed = time.perf_counter() - started
            assert report.ok and report.observations_created == n, report
            raise _Rollback((elapsed, len(ctx)))
    except _Rollback as done:
        return done.args[0]


print(f"{'N':>6} {'batch':>6} {'trigger':>8} {'detik':>8} {'ms/obs':>8} {'query':>7}")
for n, batch in [(1000, 500), (5000, 500), (5000, 1000), (10000, 1000)]:
    for enabled in (True, False):
        seconds, queries = measure(n, batch, enabled)
        label = "aktif" if enabled else "mati"
        print(f"{n:>6} {batch:>6} {label:>8} {seconds:>8.2f} {seconds / n * 1000:>8.2f} {queries:>7}", flush=True)


# --- rekonsiliasi (WP-1.4) ---------------------------------------------------------------------
from collection.reconciliation import reconcile_run  # noqa: E402


def measure_reconcile(n):
    """Run 2 memuat semua objek run 1 (1% diedit) ditambah 10% objek baru; 5% objek run 1 hilang."""
    try:
        with transaction.atomic():
            user = User.objects.create_user(f"bench-{uuid.uuid4().hex[:8]}", password="x")
            inv = inv_services.create_investigation(user=user, name="bench-recon")
            target = inv_services.register_target(
                investigation=inv, user=user, platform=Platform.X,
                target_type=TargetType.POST, url="https://x.com/bench/status/2",
            )
            run1 = services.create_inspection_run(
                target=target, user=user, requested=[Capability.INSPECT_REPLIES]
            )
            assert ingest_result(run1, _build(run1, n), batch_size=1000).ok
            run2 = services.create_inspection_run(
                target=target, user=user, requested=[Capability.INSPECT_REPLIES]
            )
            second = _build(run2, n)
            keep = n - n // 20  # 5% hilang
            edited = set(range(0, n, 100))  # 1% diedit
            observations = [
                Observation(**{**o.__dict__, "text": o.text + " (diedit)"})
                if i in edited else o
                for i, o in enumerate(second.observations[:keep])
            ]
            observations += list(_build(run2, n // 10).observations)  # id bentrok -> ganti nama
            observations = [
                Observation(**{**o.__dict__, "external_post_id": f"baru-{i}"})
                if i >= keep else o
                for i, o in enumerate(observations)
            ]
            result = InspectionResult(
                platform=Platform.X, inspection_run_id=run2.run_id,
                outcome=InspectionOutcome.COMPLETED, collector=CollectorInfo("bench", "0"),
                coverage=Coverage((Capability.INSPECT_REPLIES,), True, len(observations)),
                observations=tuple(observations),
            )
            assert ingest_result(run2, result, batch_size=1000).ok
            with CaptureQueriesContext(connection) as ctx:
                started = time.perf_counter()
                outcome = reconcile_run(run2)
                elapsed = time.perf_counter() - started
            raise _Rollback((elapsed, len(ctx), outcome.counts))
    except _Rollback as done:
        return done.args[0]


print(f"\n{'N':>6} {'detik':>8} {'ms/objek':>9} {'query':>7}  hasil")
for n in (1000, 5000, 10000):
    seconds, queries, counts = measure_reconcile(n)
    shown = {k: v for k, v in counts.items() if v}
    print(f"{n:>6} {seconds:>8.2f} {seconds / n * 1000:>9.2f} {queries:>7}  {shown}", flush=True)
