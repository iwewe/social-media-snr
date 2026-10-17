"""A2: diagnosis rencana query trigger penjaga setelah VACUUM (bukan tes). Dijalankan oleh perf_diag.sh."""

import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collection import services  # noqa: E402
from collection.contracts import Capability  # noqa: E402
from collection.ingestion import ingest_result  # noqa: E402
from collection.models import Post  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from investigations import services as inv_services  # noqa: E402
from investigations.enums import Platform, TargetType  # noqa: E402
from perf_matrix import TABLES, build  # noqa: E402

N = int(os.environ.get("PERF_N", "5000"))
VACUUM_FIRST = os.environ.get("PERF_VACUUM", "1") == "1"


class Rollback(Exception):
    pass


def q(sql: str, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


def run_sql(sql: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql)


def stats(label: str) -> None:
    rows = q("SELECT relname, relpages, reltuples, (SELECT count(*) FROM pg_class) FROM pg_class "
             "WHERE relname = ANY(%s)", [TABLES + ["investigations_collectiontarget"]])
    print(json.dumps({"fase": label, "pg_class": {r[0]: [r[1], r[2]] for r in rows}}), flush=True)


def explain(label: str, sql: str, params=None) -> None:
    plan = [r[0] for r in q("EXPLAIN (ANALYZE, BUFFERS, COSTS) " + sql, params)]
    print(f"--- {label}\n" + "\n".join(plan[:14]), flush=True)


def main() -> None:
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"ALTER TABLE {table} SET (autovacuum_enabled = false)")
    user = User.objects.create_user("perf", password="x")
    inv = inv_services.create_investigation(user=user, name="x")

    def attempt(label: str, probe: bool) -> None:
        try:
            with transaction.atomic():
                target = inv_services.register_target(
                    investigation=inv, user=user, platform=Platform.X, target_type=TargetType.POST,
                    url=f"https://x.com/perf/status/{label}")
                run = services.create_inspection_run(target=target, user=user, requested=[Capability.INSPECT_REPLIES])
                assert ingest_result(run, build(run, N)).ok
                if probe:
                    post_id = Post.objects.filter(first_seen_run=run).values_list("id", flat=True).first()
                    explain("pencarian post (seperti trigger)", "SELECT platform FROM collection_post WHERE id = %s", [post_id])
                    explain("snr_run_platform(run)", "SELECT snr_run_platform(%s)", [run.pk])
                    stats(f"{label}: di dalam transaksi setelah ingest")
                    # Satu INSERT relasi dengan auto_explain ambang 0: rencana query di DALAM trigger.
                    from collection.models import PostRelation

                    posts = list(Post.objects.filter(first_seen_run=run).order_by("id")[:2])
                    run_sql("SET LOCAL auto_explain.log_min_duration = 0")
                    run_sql("SET LOCAL auto_explain.log_nested_statements = on")
                    PostRelation.objects.create(run=run, from_post=posts[1], relation_type="reply_to", to_post=posts[0])
                    run_sql("SET LOCAL auto_explain.log_min_duration = -1")
                raise Rollback
        except Rollback:
            pass

    attempt("a", probe=False)  # mengisi lalu rollback (membuat baris mati)
    stats("setelah rollback")
    if VACUUM_FIRST:
        with connection.cursor() as cursor:  # mode autocommit Django: VACUUM tidak boleh dalam transaksi
            for table in TABLES:
                cursor.execute(f"VACUUM (ANALYZE) {table}")
        stats("setelah VACUUM (ANALYZE)")
    attempt("b", probe=True)


if __name__ == "__main__":
    main()
