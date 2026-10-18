"""WP-1.7: adapter dataset, termasuk skenario 4 putaran lewat orchestrator sungguhan (AT-18)."""

import copy
import json
from pathlib import Path

import pytest
from collection.contracts import (
    Capability,
    InspectionOutcome,
    InspectionRequest,
    LimitationCode,
)
from collection.datasets import (
    DirectorySource,
    MemorySource,
    fixture_adapter_class,
    register_fixture_adapters,
)
from collection.models import InspectionRun, ObservationReconciliation, Post, PostObservation, RunStatus
from collection.orchestrator import registry, request_inspection, run_inspection
from collection_helpers import register
from django.contrib.auth.models import User
from investigations import services as inv_services
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL

pytestmark = pytest.mark.django_db
SAMPLES = Path(__file__).resolve().parents[1] / "datasets" / "sample"
S = RunStatus
X_POST = "https://x.com/contoh_redaksi/status/9000000001"
X_FAIL = "https://x.com/contoh_redaksi/status/9000000002"
TT_VIDEO = "https://www.tiktok.com/@contoh_redaksi/video/7000000000001"


@pytest.fixture(autouse=True)
def isolated(settings, tmp_path):
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    registry.clear()
    register_fixture_adapters(registry, SAMPLES)
    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Dataset")


def inspect_n(target, user, times=1):
    runs = []
    for _ in range(times):
        run = request_inspection(target=target, user=user, enqueue=False)
        res = run_inspection(run.pk)
        run.refresh_from_db()
        runs.append((run, res))
    return runs


def ids(run):
    return set(PostObservation.objects.filter(run=run).values_list("post__external_post_id", flat=True))


# --- adapter murni ----------------------------------------------------------------------------


@pytest.mark.parametrize("platform", list(Platform))
def test_each_platform_gets_its_own_adapter_class(platform) -> None:
    cls = fixture_adapter_class(platform)
    assert cls.platform == platform
    assert cls(MemorySource([])).capabilities().platform == platform


def test_adapter_classes_do_not_share_platform() -> None:
    assert fixture_adapter_class(Platform.X).platform != fixture_adapter_class(Platform.TIKTOK).platform


@pytest.mark.parametrize(
    ("platform", "url", "kind"),
    [
        (Platform.X, "https://x.com/u/status/12", TargetType.POST),
        (Platform.X, "https://twitter.com/u", TargetType.ACCOUNT),
        (Platform.THREADS, "https://threads.com/@u/post/AbC", TargetType.POST),
        (Platform.THREADS, "https://threads.com/@u", TargetType.ACCOUNT),
        (Platform.TIKTOK, "https://tiktok.com/@u/video/123", TargetType.POST),
        (Platform.TIKTOK, "https://tiktok.com/@u", TargetType.ACCOUNT),
        (Platform.INSTAGRAM, "https://instagram.com/p/XYZ/", TargetType.POST),
        (Platform.INSTAGRAM, "https://instagram.com/reel/XYZ/", TargetType.POST),
        (Platform.INSTAGRAM, "https://instagram.com/someone", TargetType.ACCOUNT),
        (Platform.FACEBOOK, "https://facebook.com/story.php?story_fbid=1&id=2", TargetType.POST),
        (Platform.FACEBOOK, "https://facebook.com/halaman/posts/55", TargetType.POST),
        (Platform.FACEBOOK, "https://facebook.com/halaman", TargetType.ACCOUNT),
    ],
)
def test_url_classification_per_platform(platform, url, kind) -> None:
    info = fixture_adapter_class(platform)(MemorySource([])).validate_target_url(url)
    assert info.target_type is kind and info.platform == platform


@pytest.mark.parametrize(
    ("platform", "url"),
    [
        (Platform.X, "https://x.com/"),
        (Platform.X, "https://tiktok.com/@u/video/1"),
        (Platform.X, "https://x.com/u/status/abc"),
        (Platform.TIKTOK, "https://tiktok.com/@u/photo/1"),
        (Platform.INSTAGRAM, "https://instagram.com/"),
        (Platform.FACEBOOK, "https://facebook.com/"),
        (Platform.THREADS, "https://threads.com/u"),
    ],
)
def test_unrecognised_urls_are_rejected(platform, url) -> None:
    with pytest.raises(InvalidTargetURL):
        fixture_adapter_class(platform)(MemorySource([])).validate_target_url(url)


def test_inspect_gates_disabled_capabilities_without_collecting() -> None:
    adapter = fixture_adapter_class(Platform.X)(DirectorySource(SAMPLES), disable={Capability.INSPECT_REPLIES})
    req = InspectionRequest("r1", Platform.X, X_POST, TargetType.POST,
                            (Capability.INSPECT_POST, Capability.INSPECT_REPLIES), run_sequence=1)
    res = adapter.inspect(req)
    assert res.outcome is InspectionOutcome.UNSUPPORTED and not res.observations


def test_screenshot_and_media_are_declared_unsupported_with_reasons() -> None:
    caps = fixture_adapter_class(Platform.X)(MemorySource([])).capabilities()
    for cap in (Capability.PRESERVE_SCREENSHOT, Capability.PRESERVE_MEDIA):
        assert not caps.runnable(cap) and caps.declarations[cap].reason


def request(platform, url, seq, **kw):
    return InspectionRequest("r1", platform, url, TargetType.POST, (Capability.INSPECT_REPLIES,),
                             run_sequence=seq, **kw)


def adapter_x():
    return fixture_adapter_class(Platform.X)(DirectorySource(SAMPLES))


def test_missing_sequence_defaults_to_the_first_snapshot() -> None:
    res = adapter_x().inspect(request(Platform.X, X_POST, None))
    assert res.outcome is InspectionOutcome.COMPLETED and len(res.observations) == 5


def test_sequence_beyond_the_snapshots_is_unsupported_with_an_explicit_reason() -> None:
    res = adapter_x().inspect(request(Platform.X, X_POST, 5))
    assert res.outcome is InspectionOutcome.UNSUPPORTED and not res.observations
    assert "4 snapshot" in res.limitations[0].message and "ke-5" in res.limitations[0].message


def test_unknown_target_is_unsupported_not_an_empty_success() -> None:
    res = adapter_x().inspect(request(Platform.X, "https://x.com/lain/status/1", 1))
    assert res.outcome is InspectionOutcome.UNSUPPORTED
    assert res.limitations[0].code is LimitationCode.UNSUPPORTED


def test_dataset_for_another_platform_is_not_served() -> None:
    adapter = fixture_adapter_class(Platform.THREADS)(DirectorySource(SAMPLES))
    res = adapter.inspect(InspectionRequest("r1", Platform.THREADS, "https://threads.com/@contoh_redaksi/post/AbC",
                                            TargetType.POST, (Capability.INSPECT_REPLIES,), run_sequence=1))
    assert res.outcome is InspectionOutcome.UNSUPPORTED


def test_same_input_gives_identical_observation_identities() -> None:
    a = adapter_x().inspect(request(Platform.X, X_POST, 2))
    b = adapter_x().inspect(request(Platform.X, X_POST, 2))
    key = lambda r: [(o.source_object_type, o.external_post_id, o.text) for o in r.observations]  # noqa: E731
    assert key(a) == key(b) and len(key(a)) == 7


def test_max_items_truncates_and_reports_partial_with_a_limitation() -> None:
    res = adapter_x().inspect(request(Platform.X, X_POST, 2, max_items=3))
    assert res.outcome is InspectionOutcome.PARTIAL and len(res.observations) == 3
    assert res.coverage.pagination_complete is False
    assert any(lim.code is LimitationCode.MAX_ITEMS_REACHED for lim in res.limitations)


def test_source_method_comes_from_the_dataset() -> None:
    synthetic = adapter_x().inspect(request(Platform.X, X_POST, 1))
    imported = fixture_adapter_class(Platform.TIKTOK)(DirectorySource(SAMPLES)).inspect(
        request(Platform.TIKTOK, TT_VIDEO, 1))
    assert {o.source_method.value for o in synthetic.observations} == {"synthetic_fixture"}
    assert {o.source_method.value for o in imported.observations} == {"imported_dataset"}


# --- sumber direktori -------------------------------------------------------------------------


def dataset_json(url="https://x.com/u/status/1", **over):
    d = {"schema_version": 1, "name": "uji", "platform": "x", "target_url": url,
         "source_method": "synthetic_fixture",
         "snapshots": [{"observed_at": "2026-10-16T01:00:00Z", "outcome": "COMPLETED",
                        "pagination_complete": True, "displayed_count": 0,
                        "observations": [{"type": "post", "id": "1", "actor": "a", "text": "t"}]}]}
    d.update(over)
    return d


def collect_from(tmp_path, url="https://x.com/u/status/1"):
    return fixture_adapter_class(Platform.X)(DirectorySource(tmp_path)).inspect(request(Platform.X, url, 1))


def test_invalid_file_makes_unmatched_targets_failed_not_silently_unsupported(tmp_path) -> None:
    (tmp_path / "rusak.json").write_text("{")
    res = collect_from(tmp_path)
    assert res.outcome is InspectionOutcome.FAILED
    assert res.limitations[0].code is LimitationCode.PARSE_FAILED and "rusak.json" in res.limitations[0].message


def test_invalid_file_does_not_block_a_valid_matching_dataset(tmp_path) -> None:
    (tmp_path / "rusak.json").write_text("{")
    (tmp_path / "ok.json").write_text(json.dumps(dataset_json()))
    assert collect_from(tmp_path).outcome is InspectionOutcome.COMPLETED


def test_two_datasets_for_one_target_is_ambiguous_and_fails(tmp_path) -> None:
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text(json.dumps(dataset_json()))
    res = collect_from(tmp_path)
    assert res.outcome is InspectionOutcome.FAILED and "ambigu" in res.limitations[0].message


def test_missing_directory_is_reported(tmp_path) -> None:
    res = collect_from(tmp_path / "tidak-ada")
    assert res.outcome is InspectionOutcome.FAILED


def test_non_json_files_and_subdirectories_are_ignored(tmp_path) -> None:
    (tmp_path / "catatan.txt").write_text("bukan dataset")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.json").write_text("{")
    assert collect_from(tmp_path).outcome is InspectionOutcome.UNSUPPORTED


def test_dataset_edits_are_picked_up_without_restart(tmp_path) -> None:
    f = tmp_path / "d.json"
    f.write_text(json.dumps(dataset_json()))
    assert collect_from(tmp_path).outcome is InspectionOutcome.COMPLETED
    d = dataset_json()
    d["snapshots"] = []
    f.write_text(json.dumps(d))
    assert collect_from(tmp_path).outcome is InspectionOutcome.FAILED


# --- orchestrator: 4 putaran (AT-01..05, AT-14, AT-18) -----------------------------------------


def test_four_rounds_follow_the_planned_scenario(inv, user) -> None:
    target = register(inv, user, Platform.X, X_POST)
    (r1, _), (r2, _), (r3, _), (r4, _) = inspect_n(target, user, 4)

    assert [r.status for r in (r1, r2, r3, r4)] == [S.COMPLETED, S.COMPLETED, S.PARTIAL, S.COMPLETED]
    assert r1.target_id == r4.target_id  # AT-01: satu target, run bertambah

    # AT-02/03: objek lama tidak diduplikasi; hanya ID baru menjadi Post baru.
    posts = Post.objects.filter(platform="x")
    assert posts.count() == len(set(posts.values_list("external_post_id", flat=True))) == 8  # post + r1..r7

    # AT-05: konten berubah pada ID yang sama -> observasi baru, sejarah lama tersimpan.
    texts = list(PostObservation.objects.filter(post__external_post_id="9000000012")
                 .order_by("run__sequence").values_list("text", flat=True))
    assert len(texts) == 4 and "diedit" not in texts[0] and "diedit" in texts[1]

    # AT-04: tidak tampil pada run parsial -> NOT_OBSERVED, bukan DELETED.
    def state(run, post_id):
        return ObservationReconciliation.objects.get(run=run, post__external_post_id=post_id).status

    assert state(r3, "9000000014") == "NOT_OBSERVED"
    # Run 4: dinyatakan tidak tersedia secara eksplisit oleh sumber.
    assert state(r4, "9000000014") == "CONFIRMED_UNAVAILABLE"
    assert state(r2, "9000000013") == "UNCHANGED" and state(r2, "9000000012") == "MODIFIED"
    assert state(r2, "9000000015") == "NEW"


def test_fourth_round_preserves_the_dom_artifact(inv, user) -> None:
    target = register(inv, user, Platform.X, X_POST)
    runs = inspect_n(target, user, 4)
    from preservation.models import EvidenceArtifact

    assert EvidenceArtifact.objects.filter(run=runs[3][0], kind="dom_snapshot").count() == 1
    assert not EvidenceArtifact.objects.filter(run=runs[0][0], kind="dom_snapshot").exists()


def test_access_failures_are_never_zero_replies(inv, user) -> None:  # AT-14
    target = register(inv, user, Platform.X, X_FAIL)
    (r1, _), (r2, _), (r3, _), (r4, _) = inspect_n(target, user, 4)
    assert [r.status for r in (r1, r2, r3, r4)] == [
        S.COMPLETED, S.ACCESS_RESTRICTED, S.FAILED, S.COMPLETED]
    for run in (r2, r3):
        assert not PostObservation.objects.filter(run=run).exists()
        assert run.reconciliation is None  # tidak ada "semua objek hilang"
    # Objek tidak ditandai hilang karena gangguan; run 4 melihatnya UNCHANGED.
    assert not ObservationReconciliation.objects.filter(status__in=["NOT_OBSERVED", "CONFIRMED_UNAVAILABLE"],
                                                        run__target=target).exists()


def test_run_beyond_the_dataset_is_unsupported_through_the_orchestrator(inv, user) -> None:
    target = register(inv, user, Platform.X, X_POST)
    runs = inspect_n(target, user, 5)
    assert runs[4][0].status == S.UNSUPPORTED and runs[4][0].limitations[0]["code"] == "UNSUPPORTED"


def test_imported_dataset_runs_through_the_same_path_on_another_platform(inv, user) -> None:
    target = register(inv, user, Platform.TIKTOK, TT_VIDEO)
    ((run, res),) = inspect_n(target, user)
    assert res.status == S.COMPLETED and run.source_method == "imported_dataset"
    kinds = set(PostObservation.objects.filter(run=run).values_list("source_object_type", flat=True))
    assert kinds == {"post", "comment"}


def test_same_handle_on_two_platforms_stays_separate(inv, user) -> None:  # dasar AT-13
    x = register(inv, user, Platform.X, X_POST)
    tt = register(inv, user, Platform.TIKTOK, TT_VIDEO)
    inspect_n(x, user)
    inspect_n(tt, user)
    handles = PostObservation.objects.filter(actor_handle="contoh_redaksi")
    assert set(handles.values_list("post__platform", flat=True)) == {"x", "tiktok"}
    from collection.models import ActorAccount

    actors = ActorAccount.objects.filter(external_actor_id__in=["a01", "t01"])
    assert actors.count() == 2 and {a.platform for a in actors} == {"x", "tiktok"}


def test_inspecting_a_target_with_no_dataset_is_unsupported(inv, user) -> None:
    target = register(inv, user, Platform.X, "https://x.com/lain/status/55")
    ((run, res),) = inspect_n(target, user)
    assert res.status == S.UNSUPPORTED and not PostObservation.objects.filter(run=run).exists()


def test_orchestrator_passes_the_run_sequence_to_the_adapter(inv, user) -> None:
    seen = []
    base = fixture_adapter_class(Platform.X)

    class Spy(base):  # type: ignore[valid-type, misc]
        def collect(self, request):
            seen.append(request.run_sequence)
            return super().collect(request)

    registry.unregister(Platform.X)
    registry.register(Platform.X, lambda: Spy(DirectorySource(SAMPLES)))
    inspect_n(register(inv, user, Platform.X, X_POST), user, 2)
    assert seen == [1, 2]


def test_adapter_is_absent_unless_the_datasets_directory_is_configured(inv, user) -> None:
    registry.clear()
    assert registry.get(Platform.X) is None
    target = register(inv, user, Platform.X, X_POST)
    ((run, res),) = inspect_n(target, user)
    assert res.status == S.UNSUPPORTED


def test_app_ready_registers_adapters_only_when_configured(settings) -> None:
    from django.apps import apps

    from collection.adapters.pending import PendingPermissionAdapter

    registry.clear()
    settings.SNR_FIXTURE_DATASETS_DIR = None
    apps.get_app_config("collection").ready()
    # Tanpa konfigurasi: hanya adapter platform yang DINONAKTIFKAN (WP-3.0), tidak ada adapter dataset.
    assert registry.platforms() == sorted(p.value for p in Platform)
    assert all(isinstance(registry.get(p), PendingPermissionAdapter) for p in Platform)
    registry.clear()
    settings.SNR_FIXTURE_DATASETS_DIR = SAMPLES
    apps.get_app_config("collection").ready()
    assert registry.platforms() == sorted(p.value for p in Platform)
    assert not any(isinstance(registry.get(p), PendingPermissionAdapter) for p in Platform)


_ = (copy, InspectionRun)


def test_sources_filter_by_platform_even_if_urls_were_to_collide() -> None:
    # Pertahanan berlapis: URL ternormalisasi sudah per platform, tetapi sumber tetap menyaring platform.
    import dataclasses

    from collection.datasets import parse_dataset

    ds = parse_dataset(dataset_json())
    foreign = dataclasses.replace(ds, platform=Platform.THREADS)  # tidak terjangkau lewat parse
    assert MemorySource([foreign]).find(Platform.X, ds.target_url).datasets == []
    assert MemorySource([ds]).find(Platform.X, ds.target_url).datasets == [ds]
    assert MemorySource([foreign]).find(Platform.THREADS, ds.target_url).datasets == [foreign]


def test_directory_source_filters_by_platform(tmp_path, monkeypatch) -> None:
    import dataclasses

    import collection.datasets.adapter as mod
    from collection.datasets import parse_dataset

    ds = parse_dataset(dataset_json())
    foreign = dataclasses.replace(ds, platform=Platform.THREADS)
    (tmp_path / "a.json").write_text("{}")
    monkeypatch.setattr(mod, "load_dataset_file", lambda path: foreign)
    assert DirectorySource(tmp_path).find(Platform.X, ds.target_url).datasets == []
    assert DirectorySource(tmp_path).find(Platform.THREADS, ds.target_url).datasets == [foreign]
