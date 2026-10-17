"""WP-1.8: pengambilan browser lewat orchestrator sungguhan sampai bukti terverifikasi (AT-06, AT-14)."""

import pytest
from collection.browser import register_simulated_adapter
from collection.contracts import Capability
from collection.models import InspectionRun, ObservationReconciliation, PostObservation, RunStatus
from collection.orchestrator import registry, request_inspection, run_inspection
from collection_helpers import register
from django.contrib.auth.models import User
from investigations import services as inv_services
from investigations.enums import Platform
from preservation.models import EvidenceArtifact
from preservation.storage import verify_stored

pytestmark = pytest.mark.django_db
S = RunStatus
EVIDENCE = [Capability.INSPECT_POST, Capability.INSPECT_REPLIES,
            Capability.PRESERVE_SCREENSHOT, Capability.PRESERVE_DOM]


@pytest.fixture(autouse=True)
def wired(settings, tmp_path, sim_server):
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    registry.clear()
    register_simulated_adapter(registry, sim_server.base_url, Platform.X)
    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Browser")


def target_for(inv, user, post_id):
    return register(inv, user, Platform.X, f"https://x.com/contoh_redaksi/status/{post_id}")


def inspect(target, user, times=1, caps=None):
    out = []
    for _ in range(times):
        run = request_inspection(target=target, user=user, requested=caps, enqueue=False)
        res = run_inspection(run.pk)
        run.refresh_from_db()
        out.append((run, res))
    return out


def test_complete_run_has_observations_screenshot_dom_manifest_and_valid_hashes(inv, user) -> None:
    ((run, res),) = inspect(target_for(inv, user, "1001"), user, caps=EVIDENCE)
    assert res.status == S.COMPLETED and run.review is None
    assert PostObservation.objects.filter(run=run).count() == 8
    arts = {a.kind: a for a in EvidenceArtifact.objects.filter(run=run)}
    assert {"screenshot", "dom_snapshot", "manifest"} <= set(arts)
    for art in arts.values():
        assert verify_stored(art.relative_path, art.sha256), art.kind  # AT-06
    assert run.reconciliation["state"] == "DONE"


def test_collector_version_is_recorded_on_the_run(inv, user) -> None:
    ((run, _),) = inspect(target_for(inv, user, "1001"), user)
    assert run.collector_name == "browser-sim"
    assert "playwright" in run.collector_version and "chromium" in run.collector_version
    assert run.source_method == "synthetic_fixture"


@pytest.mark.parametrize(
    ("post_id", "status"),
    [("1003", S.ACCESS_RESTRICTED), ("1004", S.ACCESS_RESTRICTED), ("1005", S.FAILED),
     ("1008", S.FAILED)],
)
def test_access_loss_and_parser_failure_are_not_zero_replies(inv, user, post_id, status) -> None:  # AT-14
    ((run, res),) = inspect(target_for(inv, user, post_id), user, caps=EVIDENCE)
    assert res.status == status and run.status == status
    assert not PostObservation.objects.filter(run=run).exists()
    assert run.reconciliation is None
    assert run.limitations  # alasan terstruktur tercatat
    assert EvidenceArtifact.objects.filter(run=run, kind="screenshot").exists()  # bukti halaman gagal


def test_broken_pagination_is_partial_and_missing_objects_are_not_deleted(inv, user) -> None:  # AT-04
    target = target_for(inv, user, "1002")
    ((run, res),) = inspect(target, user)
    assert res.status == S.PARTIAL and run.coverage["pagination_complete"] is False
    assert PostObservation.objects.filter(run=run).count() == 4  # pos + 3 balasan
    assert run.reconciliation["state"] == "DONE"


def test_login_wall_run_is_partial(inv, user) -> None:
    ((run, res),) = inspect(target_for(inv, user, "1007"), user)
    assert res.status == S.PARTIAL and run.limitations[0]["code"] == "AUTH_REQUIRED"


def test_changing_content_across_three_visits_is_reconciled(inv, user) -> None:  # AT-03/04/05
    target = target_for(inv, user, "1006")
    (r1, _), (r2, _), (r3, _) = inspect(target, user, times=3)

    def state(run, reply):
        return ObservationReconciliation.objects.get(
            run=run, post__external_post_id=f"1006{reply:03d}").status

    assert state(r2, 4) == "NEW" and state(r2, 1) == "MODIFIED" and state(r2, 2) == "UNCHANGED"
    assert state(r3, 2) == "NOT_OBSERVED"  # tidak tampil di kunjungan 3: bukan DELETED
    texts = list(PostObservation.objects.filter(post__external_post_id="1006001")
                 .order_by("run__sequence").values_list("text", flat=True))
    assert len(texts) == 3 and "diedit" in texts[1]  # sejarah tetap tersedia


def test_session_cookie_never_enters_evidence_or_run_records(inv, user, settings) -> None:
    from collection.simulation.server import SESSION_COOKIE_VALUE

    ((run, _),) = inspect(target_for(inv, user, "1001"), user, caps=EVIDENCE)
    blob = str(run.ingestion) + str(run.limitations) + str(run.coverage)
    for art in EvidenceArtifact.objects.filter(run=run):
        blob += (settings.SNR_EVIDENCE_ROOT / art.relative_path).read_bytes().decode("latin-1")
    assert SESSION_COOKIE_VALUE not in blob


def test_browser_state_stays_out_of_the_evidence_tree(inv, user, settings) -> None:
    inspect(target_for(inv, user, "1001"), user)
    assert (settings.SNR_BROWSER_PROFILES_ROOT / "x").is_dir()
    evidence_files = [p for p in settings.SNR_EVIDENCE_ROOT.rglob("*") if p.is_file()]
    assert all("profiles" not in str(p) for p in evidence_files)


def test_enqueue_routes_browser_runs_to_the_browser_queue(
    inv, user, monkeypatch, django_capture_on_commit_callbacks
) -> None:
    from collection import tasks

    sent = []
    monkeypatch.setattr(tasks.execute_inspection, "apply_async", lambda args, queue: sent.append(queue))
    with django_capture_on_commit_callbacks(execute=True):
        request_inspection(target=target_for(inv, user, "1001"), user=user)
    assert sent == ["browser"]


def test_celery_task_runs_a_browser_run_eagerly(inv, user) -> None:
    from collection import tasks

    run = request_inspection(target=target_for(inv, user, "1001"), user=user, enqueue=False)
    out = tasks.execute_inspection.apply(args=[run.pk]).get()
    assert out["status"] == "COMPLETED"


def test_app_ready_registers_the_simulation_adapter_only_when_configured(settings, sim_server) -> None:
    from django.apps import apps

    registry.clear()
    settings.SNR_SIMULATION_BASE_URL = None
    apps.get_app_config("collection").ready()
    assert registry.platforms() == []
    settings.SNR_SIMULATION_BASE_URL = sim_server.base_url
    settings.SNR_SIMULATION_PLATFORM = "tiktok"
    apps.get_app_config("collection").ready()
    assert registry.platforms() == ["tiktok"]


_ = InspectionRun
