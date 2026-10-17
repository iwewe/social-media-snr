"""WP-1.6: orchestrator run dengan adapter terskrip (tanpa jaringan)."""

import threading
from datetime import timedelta

import pytest
from collection import tasks
from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    Capability,
    ContractViolation,
    LimitationCode,
)
from collection.models import InspectionRun, PostObservation, RunStatus
from collection.orchestrator import (
    OrchestrationError,
    acknowledge_review,
    registry,
    request_inspection,
    run_inspection,
    sweep_stale_runs,
)
from collection.orchestrator import service as svc
from collection_fakes import (
    BrowserScriptedAdapter,
    ScriptedAdapter,
    build_result,
    parse_failed,
    restricted,
)
from django.contrib.auth.models import User
from django.db import connection
from django.utils import timezone
from investigations import services as inv_services
from investigations.enums import Platform
from celery.exceptions import SoftTimeLimitExceeded
from collection_helpers import register

pytestmark = pytest.mark.django_db
S = RunStatus
URL = "https://x.com/u/status/1"


@pytest.fixture(autouse=True)
def clean_registry():
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def target(user):
    return register(inv_services.create_investigation(user=user, name="A"), user, Platform.X, URL)


def use(behavior, cls=ScriptedAdapter, **kw):
    adapter = cls(behavior, **kw)
    registry.register(Platform.X, lambda: adapter)
    return adapter


def pending(target, user) -> InspectionRun:
    return request_inspection(target=target, user=user, enqueue=False)


def go(target, user):
    run = pending(target, user)
    res = run_inspection(run.pk)
    run.refresh_from_db()
    return run, res


def snapshot(run):
    return (run.status, run.coverage, run.limitations, run.review)


# --- jalur utama ------------------------------------------------------------------------------


def test_happy_path_completes_ingests_and_reconciles(target, user) -> None:
    use(lambda r: build_result(r, ["r1", "r2", "r3"]))
    run, res = go(target, user)
    assert res.handled and res.status == S.COMPLETED
    assert run.status == S.COMPLETED and run.review is None
    assert PostObservation.objects.filter(run=run).count() == 3
    assert run.ingestion["state"] == "FINISHED"
    assert run.reconciliation["state"] == "DONE"
    assert run.started_at and run.finished_at and run.claimed_by == ""


def test_partial_outcome_stays_partial_and_is_reconciled(target, user) -> None:
    use(lambda r: build_result(r, ["r1"], outcome=svc.InspectionOutcome.PARTIAL, complete=False,
                               limitations=[_lim(LimitationCode.PAGINATION_INCOMPLETE)]))
    run, res = go(target, user)
    assert res.status == S.PARTIAL and run.reconciliation["state"] == "DONE"


def _lim(code):
    from collection.contracts import Limitation

    return Limitation(code, "uji")


def test_access_restricted_is_never_completed_and_has_no_observations(target, user) -> None:  # AT-14
    use(restricted)
    run, res = go(target, user)
    assert res.status == S.ACCESS_RESTRICTED and run.status == S.ACCESS_RESTRICTED
    assert not PostObservation.objects.filter(run=run).exists()
    assert run.reconciliation is None  # tidak direkonsiliasi: bukan "semua hilang"
    assert run.limitations[0]["code"] == "ACCESS_RESTRICTED"


def test_adapter_failure_is_failed_not_zero_replies(target, user) -> None:  # AT-14
    use(parse_failed)
    run, res = go(target, user)
    assert res.status == S.FAILED and run.reconciliation is None
    assert not PostObservation.objects.filter(run=run).exists()


def test_adapter_exception_becomes_failed_with_generic_message(target, user) -> None:
    def boom(request):
        raise RuntimeError("rahasia: token=abc123")

    use(boom)
    run, res = go(target, user)
    assert res.status == S.FAILED
    lim = run.limitations[0]
    assert lim["code"] == "ADAPTER_ERROR" and "RuntimeError" in lim["message"]
    assert "abc123" not in str(run.limitations) + str(run.ingestion)


def test_contract_violation_becomes_failed_adapter_error(target, user) -> None:
    def bad(request):
        raise ContractViolation("hasil tidak sah")

    use(bad)
    run, res = go(target, user)
    assert res.status == S.FAILED and run.limitations[0]["code"] == "ADAPTER_ERROR"


def test_soft_time_limit_in_adapter_is_failed_timeout(target, user) -> None:
    def slow(request):
        raise SoftTimeLimitExceeded

    use(slow)
    run, res = go(target, user)
    assert res.status == S.FAILED and run.limitations[0]["code"] == "TIMEOUT"


def test_no_adapter_registered_is_unsupported(target, user) -> None:
    run, res = go(target, user)
    assert res.status == S.UNSUPPORTED and run.limitations[0]["code"] == "UNSUPPORTED"
    assert run.ingestion["state"] == "FINISHED"


def test_unrecognised_url_is_unsupported_and_adapter_not_called(user) -> None:
    inv = inv_services.create_investigation(user=user, name="B")
    tgt = register(inv, user, Platform.X, "https://x.com/u")  # profil, bukan postingan
    adapter = use(lambda r: build_result(r, ["r1"]))
    run, res = go(tgt, user)
    assert res.status == S.UNSUPPORTED and adapter.calls == []


def test_disabled_capability_is_unsupported_without_collecting(target, user) -> None:
    adapter = use(lambda r: build_result(r, ["r1"]), disable={Capability.INSPECT_REPLIES})
    run, res = go(target, user)
    assert res.status == S.UNSUPPORTED and adapter.calls == []
    assert not PostObservation.objects.filter(run=run).exists()


# --- tinjauan ---------------------------------------------------------------------------------


def test_ingestion_problem_marks_review_required_with_reasons(target, user, monkeypatch) -> None:
    from collection.ingestion import BatchFailure

    use(lambda r: build_result(r, ["r1"]))
    real = svc.ingest_result

    def failing(run, result, **kw):
        report = real(run, result, **kw)
        report.failed_batches.append(BatchFailure(0, 0, 0, "X"))
        return report

    monkeypatch.setattr(svc, "ingest_result", failing)
    run, res = go(target, user)
    assert res.status == S.REVIEW_REQUIRED and "ingestion_failed_batches" in res.reasons
    assert run.review["outcome"] == "COMPLETED" and run.review["acknowledged"] is None
    assert run.reconciliation is None


def test_ingestion_exception_goes_to_review_and_leaves_in_progress_marker(
    target, user, monkeypatch
) -> None:
    use(lambda r: build_result(r, ["r1"]))

    def explode(run, result, **kw):
        InspectionRun.objects.filter(pk=run.pk).update(ingestion={"state": "IN_PROGRESS"})
        raise RuntimeError("db putus")

    monkeypatch.setattr(svc, "ingest_result", explode)
    run, res = go(target, user)
    assert res.status == S.REVIEW_REQUIRED and res.reasons == ["ingestion_exception"]
    assert run.ingestion["state"] == "IN_PROGRESS"


def _snapshot(name, body):
    return ArtifactCapture(kind=ArtifactKind.DOM_SNAPSHOT, filename=name, content=body,
                           content_type="text/html")


def test_secret_in_artifact_is_rejected_but_run_still_completes(target, user) -> None:
    clean = _snapshot("ok.html", b"<p>halaman biasa</p>")
    dirty = _snapshot("bad.html", b"<p>Authorization: Bearer abcdefghijklmnop1234567890</p>")
    use(lambda r: build_result(r, ["r1"], artifacts=[clean, dirty]))
    run, res = go(target, user)
    assert res.status == S.COMPLETED
    from preservation.models import EvidenceArtifact

    stored = EvidenceArtifact.objects.filter(run=run, kind=ArtifactKind.DOM_SNAPSHOT.value)
    assert stored.count() == 1  # kontrol positif: yang bersih tersimpan, yang berisi rahasia tidak
    rejected = run.ingestion["report"]["artifacts"]["rejected"]
    assert [r["filename"] for r in rejected] == ["bad.html"]
    assert "abcdefghijklmnop" not in str(run.ingestion)  # isi rahasia tak bocor ke catatan run


def test_acknowledge_review_restores_recorded_outcome_without_touching_data(
    target, user, monkeypatch
) -> None:
    use(lambda r: build_result(r, ["r1"]))
    monkeypatch.setattr(svc, "_review_reasons", lambda report: ["mixed_source_methods"])
    run, _ = go(target, user)
    before = snapshot(run)[1:3]
    reviewer = User.objects.create_user("peninjau", password="x")
    done = acknowledge_review(run=run, user=reviewer, note="sudah dicek")
    assert done.status == S.COMPLETED
    assert (done.coverage, done.limitations) == before
    assert done.review["acknowledged"]["by"] == "peninjau"
    with pytest.raises(OrchestrationError):
        acknowledge_review(run=done, user=reviewer)


def test_acknowledge_rejects_a_run_not_awaiting_review(target, user) -> None:
    use(lambda r: build_result(r, ["r1"]))
    run, _ = go(target, user)
    with pytest.raises(OrchestrationError):
        acknowledge_review(run=run, user=user)


# --- idempotensi ------------------------------------------------------------------------------


def test_second_call_does_not_rerun_adapter(target, user) -> None:
    adapter = use(lambda r: build_result(r, ["r1"]))
    run = pending(target, user)
    first = run_inspection(run.pk)
    second = run_inspection(run.pk)
    assert first.handled and not second.handled and second.status == S.COMPLETED
    assert len(adapter.calls) == 1
    assert PostObservation.objects.filter(run=run).count() == 1


def test_redelivery_while_running_does_not_run_adapter_again(target, user) -> None:
    adapter = use(lambda r: build_result(r, ["r1"]))
    run = pending(target, user)
    InspectionRun.objects.filter(pk=run.pk).update(status=S.RUNNING)
    res = run_inspection(run.pk)
    assert not res.handled and res.status == S.RUNNING and adapter.calls == []


def test_missing_run_is_reported_not_raised() -> None:
    res = run_inspection(987654)
    assert not res.handled and res.status == "MISSING"


@pytest.mark.django_db(transaction=True)
def test_concurrent_claims_run_the_adapter_exactly_once(target, user) -> None:
    gate = threading.Barrier(2)
    adapter = use(lambda r: build_result(r, ["r1"]))
    run = pending(target, user)
    results = []

    def worker(name):
        try:
            gate.wait(5)
            results.append(run_inspection(run.pk, claimed_by=name))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(2)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    assert sorted(r.handled for r in results) == [False, True]
    assert len(adapter.calls) == 1
    run.refresh_from_db()
    assert run.status == S.COMPLETED and run.claimed_by in {"w0", "w1"}


# --- request_inspection & antrean -------------------------------------------------------------


def test_inspect_again_creates_a_new_run_on_the_same_target(target, user) -> None:
    a = pending(target, user)
    b = pending(target, user)
    assert a.pk != b.pk and a.target_id == b.target_id and b.sequence == a.sequence + 1


def test_default_scope_for_post_target(target, user) -> None:
    run = pending(target, user)
    assert run.requested == [Capability.INSPECT_POST.value, Capability.INSPECT_REPLIES.value]


@pytest.mark.parametrize(("cls", "queue"), [(ScriptedAdapter, "analysis"), (BrowserScriptedAdapter, "browser")])
def test_enqueue_after_commit_routes_to_the_adapter_queue(
    cls, queue, target, user, monkeypatch, django_capture_on_commit_callbacks
) -> None:
    use(lambda r: build_result(r), cls=cls)
    sent = []
    monkeypatch.setattr(tasks.execute_inspection, "apply_async",
                        lambda args, queue: sent.append((args, queue)))
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        run = request_inspection(target=target, user=user)
    assert sent == []  # belum commit: pekerja tak boleh melihat run
    for cb in callbacks:
        cb()
    assert sent == [([run.pk], queue)]


def test_no_adapter_routes_to_default_queue(target, user, monkeypatch, django_capture_on_commit_callbacks) -> None:
    sent = []
    monkeypatch.setattr(tasks.execute_inspection, "apply_async", lambda args, queue: sent.append(queue))
    with django_capture_on_commit_callbacks(execute=True):
        request_inspection(target=target, user=user)
    assert sent == ["analysis"]


def test_broker_failure_fails_the_run_instead_of_hanging(
    target, user, monkeypatch, django_capture_on_commit_callbacks
) -> None:
    def down(args, queue):
        raise ConnectionError("broker mati")

    monkeypatch.setattr(tasks.execute_inspection, "apply_async", down)
    with django_capture_on_commit_callbacks(execute=True):
        run = request_inspection(target=target, user=user)
    run.refresh_from_db()
    assert run.status == S.FAILED and run.limitations[0]["code"] == "NETWORK_ERROR"


def test_celery_task_runs_the_run_eagerly(target, user) -> None:
    use(lambda r: build_result(r, ["r1", "r2"]))
    run = pending(target, user)
    out = tasks.execute_inspection.apply(args=[run.pk]).get()
    assert out["status"] == "COMPLETED" and out["handled"] is True
    assert tasks.execute_inspection.name == "snr.execute_inspection"


# --- penyapu ----------------------------------------------------------------------------------


def stale(target, user, *, seconds=7200, observations=False):
    run = pending(target, user)
    InspectionRun.objects.filter(pk=run.pk).update(
        status=S.RUNNING, started_at=timezone.now() - timedelta(seconds=seconds)
    )
    if observations:
        use(lambda r: build_result(r, ["r1"]))
        from collection.contracts import InspectionRequest  # noqa: F401
        run.refresh_from_db()
        from collection.ingestion import ingest_result

        ingest_result(run, build_result(_req(run), ["r1"]))
    return run


def _req(run):
    class R:  # InspectionRequest minimal untuk helper
        platform = Platform(run.target.platform)
        inspection_run_id = run.run_id
        requested = tuple(Capability(c) for c in run.requested)

    return R


def test_sweeper_fails_stale_running_run_without_data(target, user) -> None:
    run = stale(target, user)
    assert sweep_stale_runs(older_than_seconds=3600) == [run.pk]
    run.refresh_from_db()
    assert run.status == S.FAILED and run.limitations[-1]["code"] == "TIMEOUT"
    assert run.coverage["outcome"] == "FAILED" and run.ingestion is not None


def test_sweeper_marks_run_with_observations_partial(target, user) -> None:
    run = stale(target, user, observations=True)
    InspectionRun.objects.filter(pk=run.pk).update(ingestion={"state": "IN_PROGRESS"})
    assert sweep_stale_runs(older_than_seconds=3600) == [run.pk]
    run.refresh_from_db()
    assert run.status == S.PARTIAL and run.ingestion["state"] == "IN_PROGRESS"


def test_sweeper_leaves_fresh_pending_and_final_runs(target, user) -> None:
    fresh = stale(target, user, seconds=10)
    pend = pending(target, user)
    done = stale(target, user)
    InspectionRun.objects.filter(pk=done.pk).update(status=S.COMPLETED)
    assert sweep_stale_runs(older_than_seconds=3600) == []
    assert {InspectionRun.objects.get(pk=r.pk).status for r in (fresh, pend, done)} == {
        S.RUNNING, S.PENDING, S.COMPLETED}


@pytest.mark.parametrize("bad", [None, 0, -5])
def test_sweeper_requires_an_explicit_positive_timeout(bad) -> None:
    with pytest.raises(ValueError):
        sweep_stale_runs(older_than_seconds=bad)


def test_sweeper_is_idempotent(target, user) -> None:
    stale(target, user)
    assert len(sweep_stale_runs(older_than_seconds=3600)) == 1
    assert sweep_stale_runs(older_than_seconds=3600) == []


def test_sweep_command_requires_older_than(target, user) -> None:
    from django.core.management import CommandError, call_command

    with pytest.raises(CommandError):
        call_command("sweep_inspections")
    stale(target, user)
    call_command("sweep_inspections", "--older-than", "3600")
    assert InspectionRun.objects.filter(status=S.FAILED).count() == 1


# --- registry ---------------------------------------------------------------------------------


def test_registry_get_unregister_and_platforms() -> None:
    assert registry.get(Platform.X) is None
    registry.register(Platform.X, lambda: ScriptedAdapter(lambda r: build_result(r)))
    assert registry.platforms() == [Platform.X] and registry.get(Platform.X) is not None
    registry.unregister(Platform.X)
    assert registry.get(Platform.X) is None


def test_registry_rejects_duplicate_and_wrong_platform() -> None:
    from collection.orchestrator import AdapterRegistryError

    registry.register(Platform.X, lambda: ScriptedAdapter(lambda r: build_result(r)))
    with pytest.raises(AdapterRegistryError):
        registry.register(Platform.X, lambda: ScriptedAdapter(lambda r: build_result(r)))
    registry.register(Platform.TIKTOK, lambda: ScriptedAdapter(lambda r: build_result(r)))
    with pytest.raises(AdapterRegistryError):
        registry.get(Platform.TIKTOK)  # adapter mengaku platform X


def test_sweeper_does_not_overwrite_a_run_that_finishes_during_the_sweep(
    target, user, monkeypatch
) -> None:
    run = stale(target, user)

    class _Racy:
        class objects:  # noqa: N801 - menyamar sebagai manager
            @staticmethod
            def filter(**kw):
                class _Q:
                    @staticmethod
                    def exists():
                        # Pekerja menyelesaikan run tepat setelah penyapu membacanya.
                        InspectionRun.objects.filter(pk=run.pk).update(status=S.COMPLETED)
                        return False

                return _Q

    monkeypatch.setattr(svc, "PostObservation", _Racy)
    assert sweep_stale_runs(older_than_seconds=3600) == []
    run.refresh_from_db()
    assert run.status == S.COMPLETED and not any(
        lim["code"] == "TIMEOUT" for lim in (run.limitations or [])
    )
