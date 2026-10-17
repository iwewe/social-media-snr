"""A1: laporan durasi run (dasar menetapkan batas penyapu dan soft time limit)."""

import json
from datetime import timedelta
from io import StringIO

import pytest
from collection.durations import SWEPT_MARKER, duration_report, percentile
from collection.models import InspectionRun, RunStatus
from collection_helpers import new_run, register
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from django.utils import timezone
from investigations import services as inv_services
from investigations.enums import Platform

pytestmark = pytest.mark.django_db
S = RunStatus


# --- persentil --------------------------------------------------------------------------------


@pytest.mark.parametrize(("q", "expected"), [(10, 1), (50, 5), (90, 9), (95, 10), (100, 10)])
def test_nearest_rank_percentiles(q, expected) -> None:
    assert percentile(list(range(1, 11)), q) == expected


def test_percentile_of_one_sample_is_that_sample() -> None:
    assert percentile([7.5], 50) == percentile([7.5], 95) == 7.5


@pytest.mark.parametrize("q", [0, -1, 100.5])
def test_percentile_rejects_bad_q(q) -> None:
    with pytest.raises(ValueError):
        percentile([1.0], q)


def test_percentile_rejects_empty() -> None:
    with pytest.raises(ValueError):
        percentile([], 50)


# --- laporan ----------------------------------------------------------------------------------


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def make(user):
    inv = inv_services.create_investigation(user=user, name="Durasi")
    counter = iter(range(1, 1000))

    def _make(collector="adapter-a", status=S.COMPLETED, run_s=2.0, wait_s=1.0, limitations=()):
        target = register(inv, user, Platform.X, f"https://x.com/u/status/{next(counter)}")
        run = new_run(target, user)
        start = run.created_at + timedelta(seconds=wait_s)  # created_at tidak dapat diubah
        InspectionRun.objects.filter(pk=run.pk).update(
            started_at=start, status=S.RUNNING, collector_name=collector,
        )
        if status != S.RUNNING:
            InspectionRun.objects.filter(pk=run.pk).update(
                status=status, finished_at=start + timedelta(seconds=run_s),
                limitations=list(limitations),
            )
        return run

    return _make


def test_no_runs_gives_an_empty_report() -> None:
    assert duration_report() == []


def test_statistics_per_collector(make) -> None:
    for seconds in (1, 2, 3, 4, 10):
        make("adapter-a", run_s=seconds, wait_s=seconds / 2)
    make("adapter-b", run_s=7)
    rows = {r["collector"]: r for r in duration_report()}
    a = rows["adapter-a"]
    assert a["n"] == 5 and a["swept"] == 0
    assert a["execution_seconds"] == {"min": 1.0, "p50": 3.0, "p95": 10.0, "max": 10.0}
    assert a["queue_wait_seconds"]["max"] == 5.0
    assert rows["adapter-b"]["execution_seconds"]["p50"] == 7.0 and rows["adapter-b"]["n"] == 1


def test_every_final_status_counts_but_running_and_pending_do_not(make, user) -> None:
    for status in (S.COMPLETED, S.PARTIAL, S.FAILED, S.ACCESS_RESTRICTED, S.UNSUPPORTED, S.REVIEW_REQUIRED):
        make("a", status=status)
    make("a", status=S.RUNNING)  # belum selesai
    inv = inv_services.create_investigation(user=user, name="x")
    new_run(register(inv, user, Platform.X, "https://x.com/u/status/777"), user)  # PENDING
    assert duration_report()[0]["n"] == 6


def test_swept_runs_are_counted_separately_and_excluded_from_timings(make) -> None:
    make("a", run_s=2)
    swept = [{"code": "TIMEOUT", "capability": None, "message": f"pekerja berhenti ({SWEPT_MARKER})"}]
    make("a", status=S.FAILED, run_s=900, limitations=swept)
    row = duration_report()[0]
    assert row["n"] == 1 and row["swept"] == 1
    assert row["execution_seconds"]["max"] == 2.0  # 900 detik adalah batas penyapu, bukan eksekusi


def test_collector_with_only_swept_runs_reports_zero_samples(make) -> None:
    swept = [{"code": "TIMEOUT", "capability": None, "message": SWEPT_MARKER}]
    make("a", status=S.FAILED, run_s=900, limitations=swept)
    assert duration_report() == [{"collector": "a", "n": 0, "swept": 1}]


def test_runs_without_a_collector_are_not_attributed_to_an_empty_name(make) -> None:
    make("")
    assert duration_report() == []


def test_command_prints_a_readable_summary(make) -> None:
    for seconds in (1, 2, 3):
        make("adapter-a", run_s=seconds)
    out = StringIO()
    call_command("inspection_durations", stdout=out)
    text = out.getvalue()
    assert "adapter-a: n=3 disapu=0" in text and "p95=3.00" in text and "max=3.00" in text
    assert "\\n" not in text  # bukan teks "\n" mentah


def test_command_json_output_is_machine_readable(make) -> None:
    make("adapter-a", run_s=4)
    out = StringIO()
    call_command("inspection_durations", "--json", stdout=out)
    data = json.loads(out.getvalue())
    assert data[0]["collector"] == "adapter-a" and data[0]["execution_seconds"]["p50"] == 4.0


def test_command_says_so_when_there_is_nothing_to_measure() -> None:
    out = StringIO()
    call_command("inspection_durations", stdout=out)
    assert "Belum ada run selesai" in out.getvalue()


def test_the_marker_matches_what_the_real_sweeper_writes(make) -> None:
    """Pengikat: bila pesan penyapu berubah, laporan tidak boleh diam-diam mengukur run yang disapu."""
    from collection.orchestrator import sweep_stale_runs

    run = make("adapter-a", status=S.RUNNING)
    InspectionRun.objects.filter(pk=run.pk).update(started_at=timezone.now() - timedelta(hours=2))
    assert sweep_stale_runs(older_than_seconds=60) == [run.pk]
    row = duration_report()[0]
    assert row["swept"] == 1 and row["n"] == 0
