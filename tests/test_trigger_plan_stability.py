"""A2: rencana query trigger penjaga tidak boleh membeku jadi seq scan (anomali performa WP-1.4).

Akar masalah dan perbaikan (ADR 0020): fungsi PL/pgSQL men-cache rencana query; fungsi penjaga hanya
mencari lewat primary key sehingga `enable_seqscan = off` pada fungsi menjamin rencana berindeks. Setelah VACUUM pada tabel kosong
statistik berkata relpages=0/reltuples=0; saat tabel `collection_post` baru 500 baris (batch pertama)
perencana memilih Seq Scan untuk `WHERE id = ...`, rencana itu di-cache sesi, dan tetap dipakai ketika
tabel membesar: tiap baris memindai tabel (kuadratik; 20 detik per 10.000 objek, normalnya 6).
Seq scan berhenti pada baris pertama yang cocok, jadi biayanya bergantung pada POSISI baris di heap:
data yang merujuk post baru (induk beragam) memperlihatkannya; rujukan ke baris pertama tidak."""

import json
from datetime import UTC, datetime, timedelta

import pytest
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
from collection.models import Post
from collection_helpers import register
from django.contrib.auth.models import User
from django.db import connection, transaction
from investigations import services as inv_services
from investigations.enums import Platform

GUARDS = [
    "snr_run_platform",
    "snr_identity_platform_guard",
    "snr_observation_platform_guard",
    "snr_relation_platform_guard",
    "snr_reconciliation_guard",
    "snr_artifact_platform_guard",
]
TABLES = ["collection_post", "collection_actoraccount", "collection_postobservation",
          "collection_postrelation", "collection_inspectionrun", "collection_observationreconciliation"]
OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
POSTS = 6000


@pytest.mark.django_db
def test_every_guard_function_disables_seq_scans() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(%s)", [GUARDS])
        found = {name: config or [] for name, config in cursor.fetchall()}
    assert set(found) == set(GUARDS), "fungsi penjaga hilang atau berganti nama"
    for name, config in found.items():
        assert "enable_seqscan=off" in config, f"{name}: {config}"


def _result(run, count):
    """Induk beragam: tiap post ketiga membalas post sebelumnya (data nyata merujuk post baru)."""
    obs = tuple(
        Observation(
            platform=Platform.X, source_object_type=SourceObjectType.REPLY,
            inspection_run_id=run.run_id, observed_at=OBSERVED,
            collection_status=CollectionStatus.COMPLETED, source_method=SourceMethod.SYNTHETIC_FIXTURE,
            external_post_id=f"b{i}", external_actor_id=f"actor-{i % 200}",
            parent_post_id="root" if i % 3 else (f"b{i - 1}" if i else "root"),
            published_at=OBSERVED - timedelta(minutes=1 + i % 500), text=f"balasan {i}",
        )
        for i in range(count)
    )
    return InspectionResult(
        platform=Platform.X, inspection_run_id=run.run_id, outcome=InspectionOutcome.COMPLETED,
        collector=CollectorInfo("uji", "0"), coverage=Coverage((Capability.INSPECT_REPLIES,), True, count),
        observations=obs,
    )


def _insert_cost_in_buffers(run, from_ids: list[int], to_ids: list[int]) -> int:
    """Buffer yang dibaca satu INSERT 500 relasi (termasuk pekerjaan trigger di dalamnya)."""
    sql = (
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "INSERT INTO collection_postrelation (run_id, from_post_id, relation_type, to_post_id, "
        "to_actor_id, recorded_at) SELECT %s, f, 'quote_of', t, NULL, now() "
        "FROM unnest(%s::bigint[], %s::bigint[]) AS u(f, t)"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [run.pk, from_ids, to_ids])
        plan = cursor.fetchone()[0]
    plan = json.loads(plan) if isinstance(plan, str) else plan
    return plan[0]["Plan"]["Shared Hit Blocks"] + plan[0]["Plan"].get("Shared Read Blocks", 0)


class _Rollback(Exception):
    pass


@pytest.mark.django_db(transaction=True)  # VACUUM tidak boleh berjalan di dalam transaksi
def test_guard_lookups_stay_index_based_after_vacuum_on_empty_tables() -> None:
    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="Plan")
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"VACUUM (ANALYZE) {table}")
        cursor.execute("SELECT reltuples FROM pg_class WHERE relname = 'collection_post'")
        assert cursor.fetchone()[0] == 0, "prasyarat: statistik tabel post menyatakan kosong"
    try:
        with transaction.atomic():
            target = register(inv, user, Platform.X, "https://x.com/u/status/1")
            run = services.create_inspection_run(
                target=target, user=user, requested=[Capability.INSPECT_REPLIES]
            )
            assert ingest_result(run, _result(run, POSTS)).ok  # rencana trigger di-cache di sini
            ids = list(Post.objects.filter(first_seen_run=run).order_by("id").values_list("id", flat=True))
            late = ids[-501:]  # post terakhir dimasukkan: seq scan harus melewati hampir seluruh tabel
            buffers = _insert_cost_in_buffers(run, late[1:], late[:-1])
            raise _Rollback
    except _Rollback:
        pass
    print("BUFFERS", buffers)
    # Index scan: ~30 buffer per baris (~15.000 untuk 500 baris). Seq scan atas 6.000 post: puluhan
    # ribu lebih banyak. Batas 30.000 memisahkan keduanya.
    assert buffers < 30_000, f"INSERT 500 relasi membaca {buffers} buffer: pencarian trigger memindai tabel"


@pytest.mark.django_db
def test_migration_sql_is_reversible_and_reapplies() -> None:
    """DDL PostgreSQL transaksional: balik lalu terapkan ulang di dalam transaksi tes."""
    from importlib import import_module

    m = import_module("collection.migrations.0010_trigger_plan_stability")

    def config(name: str) -> list[str]:
        with connection.cursor() as cursor:
            cursor.execute("SELECT proconfig FROM pg_proc WHERE proname = %s", [name])
            return cursor.fetchone()[0] or []

    assert config("snr_observation_platform_guard") == ["enable_seqscan=off"]
    with connection.cursor() as cursor:
        cursor.execute(m.REVERSE)
    assert config("snr_observation_platform_guard") == []
    assert config("snr_run_platform") == []
    with connection.cursor() as cursor:
        cursor.execute(m.FORWARD)
    assert config("snr_observation_platform_guard") == ["enable_seqscan=off"]
    assert config("snr_reconciliation_guard") == ["enable_seqscan=off"]
