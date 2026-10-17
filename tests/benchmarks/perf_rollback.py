"""A2: hipotesis 'rollback berulang atas kunci yang sama menumpuk entri indeks mati'. Bukan tes.

Memasukkan 10.000 objek dengan kunci yang SAMA berkali-kali di dalam transaksi yang di-rollback
(pola ingestion_bench.py lama), dengan autovacuum mati, lalu menjalankan VACUUM dan mengulang.
Keluaran: satu baris JSON per iterasi (durasi, baris mati)."""

import json
import os
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collection import services  # noqa: E402
from collection.contracts import Capability  # noqa: E402
from collection.ingestion import ingest_result  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from investigations import services as inv_services  # noqa: E402
from investigations.enums import Platform, TargetType  # noqa: E402
from perf_matrix import TABLES, apply_variant, build  # noqa: E402

N = int(os.environ.get("PERF_N", "10000"))
ROUNDS = int(os.environ.get("PERF_ROUNDS", "8"))


class Rollback(Exception):
    pass


def dead_tuples() -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, n_dead_tup FROM pg_stat_user_tables WHERE relname = ANY(%s)", [TABLES])
        return dict(cursor.fetchall())


def one_round(label: str, user) -> None:
    inv = inv_services.create_investigation(user=user, name="x")  # di luar transaksi yang di-rollback
    started = None
    try:
        with transaction.atomic():
            target = inv_services.register_target(
                investigation=inv, user=user, platform=Platform.X, target_type=TargetType.POST,
                url=f"https://x.com/perf/status/{time.time_ns()}")
            run = services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_REPLIES])
            result = build(run, N)  # kunci b0..b{N-1}: SAMA di setiap putaran
            started = time.perf_counter()
            assert ingest_result(run, result).ok
            elapsed = time.perf_counter() - started
            raise Rollback(elapsed)
    except Rollback as done:
        elapsed = done.args[0]
    dead = dead_tuples()
    print(json.dumps({"fase": label, "ingest_s": round(elapsed, 2),
                      "mati_post": dead.get("collection_post"),
                      "mati_obs": dead.get("collection_postobservation")}), flush=True)


def main() -> None:
    with connection.cursor() as cursor:
        if os.environ.get("PERF_AUTOVAC", "off") == "off":
            for table in TABLES:
                cursor.execute(f"ALTER TABLE {table} SET (autovacuum_enabled = false)")
        apply_variant(cursor, os.environ.get("PERF_FIX", "keep"))
    user = User.objects.create_user("perf", password="x")
    for i in range(ROUNDS):
        one_round(f"rollback-{i + 1}", user)
    connection.ensure_connection()
    raw = connection.connection
    raw.autocommit = True
    with raw.cursor() as cursor:
        started = time.perf_counter()
        for table in TABLES:
            cursor.execute(f"VACUUM (ANALYZE) {table}")
        print(json.dumps({"fase": "vacuum", "detik": round(time.perf_counter() - started, 2)}), flush=True)
    if os.environ.get("PERF_RECONNECT") == "1":
        connection.close()  # sesi baru: rencana PL/pgSQL yang di-cache sesi lama dibuang
        print(json.dumps({"fase": "sambung-ulang"}), flush=True)
    for i in range(2):
        one_round(f"setelah-vacuum-{i + 1}", user)


if __name__ == "__main__":
    main()
