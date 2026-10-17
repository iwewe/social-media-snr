"""WP-1.9a: API run inspeksi, respons per run, dan tinjauan (FR-090, FR-095, NFR-08, AT-01)."""

import json
from pathlib import Path

import pytest
from collection import tasks
from collection.datasets import register_fixture_adapters
from collection.models import InspectionRun, RunStatus
from collection.orchestrator import registry, run_inspection
from collection.orchestrator import service as svc
from django.contrib.auth.models import User
from django.test import Client
from investigations.models import CollectionTarget

pytestmark = pytest.mark.django_db
S = RunStatus
SAMPLES = Path(__file__).resolve().parents[1] / "datasets" / "sample"
POST_URL = "https://x.com/contoh_redaksi/status/9000000001"  # 4 putaran
FAIL_URL = "https://x.com/contoh_redaksi/status/9000000002"  # gangguan akses
FORBIDDEN_KEYS = ("claimed_by", "relative_path", "manifest_path", "public_id")


@pytest.fixture(autouse=True)
def wired(settings, tmp_path, monkeypatch):
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()
    registry.clear()
    register_fixture_adapters(registry, SAMPLES)
    sent: list[tuple] = []
    monkeypatch.setattr(tasks.execute_inspection, "apply_async",
                        lambda args, queue: sent.append((args, queue)))
    wired.sent = sent  # type: ignore[attr-defined]
    yield
    registry.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def api(user) -> Client:
    c = Client()
    c.force_login(user)
    return c


def post(client, path, data=None):
    return client.post(path, data or {}, content_type="application/json")


def make_target(api, url=POST_URL, note="Konteks awal") -> int:
    inv = post(api, "/api/investigations/", {"name": "Uji"}).json()
    res = post(api, f"/api/investigations/{inv['id']}/targets/",
               {"platform": "x", "target_type": "post", "url": url, "note": note})
    assert res.status_code == 201, res.content
    return res.json()["id"]


def inspect(api, target_id, capture, **body):
    """POST inspeksi lalu eksekusi run seperti pekerja (broker dimatikan)."""
    with capture(execute=True):
        res = post(api, f"/api/targets/{target_id}/inspections/", body)
    assert res.status_code == 202, res.content
    run_id = res.json()["id"]
    run_inspection(run_id)
    return run_id


def detail(api, run_id):
    res = api.get(f"/api/inspections/{run_id}/")
    assert res.status_code == 200
    return res.json()


def rows(api, run_id, **q):
    res = api.get(f"/api/inspections/{run_id}/observations/", q)
    assert res.status_code == 200, res.content
    return res.json()


# --- akses ------------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("path", ["/api/targets/1/inspections/", "/api/inspections/1/",
                                  "/api/inspections/1/observations/",
                                  "/api/inspections/1/acknowledge-review/"])
def test_anonymous_gets_401(method, path) -> None:
    res = getattr(Client(), method)(path)
    assert res.status_code in (401, 403) and res.json()["detail"]


def test_unknown_ids_are_404_with_a_generic_message(api) -> None:
    for path in ("/api/inspections/999/", "/api/inspections/999/observations/"):
        res = api.get(path)
        assert res.status_code == 404 and res.json()["code"] == "not_found"
    assert api.get("/api/targets/999/inspections/").status_code == 404
    assert post(api, "/api/targets/999/inspections/").status_code == 404


# --- Inspect / Inspect Again ------------------------------------------------------------------


def test_inspect_creates_a_pending_run_and_enqueues_after_commit(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        res = post(api, f"/api/targets/{tid}/inspections/")
    body = res.json()
    assert res.status_code == 202 and body["status"] == "PENDING" and body["sequence"] == 1
    assert body["data_state"] == "in_progress" and body["requested"] == ["inspect_post", "inspect_replies"]
    assert wired.sent == []  # type: ignore[attr-defined]
    for cb in callbacks:
        cb()
    assert wired.sent == [([body["id"]], "analysis")]  # type: ignore[attr-defined]


def test_inspect_again_adds_a_run_to_the_same_target_not_a_new_target(api, django_capture_on_commit_callbacks) -> None:  # AT-01
    tid = make_target(api)
    first = inspect(api, tid, django_capture_on_commit_callbacks)
    second = inspect(api, tid, django_capture_on_commit_callbacks)
    assert first != second and CollectionTarget.objects.count() == 1
    assert [r["sequence"] for r in api.get(f"/api/targets/{tid}/inspections/").json()] == [2, 1]


def test_a_running_target_rejects_another_inspection_with_409(api) -> None:
    tid = make_target(api)
    assert post(api, f"/api/targets/{tid}/inspections/").status_code == 202
    res = post(api, f"/api/targets/{tid}/inspections/")
    assert res.status_code == 409 and res.json()["code"] == "inspection_in_progress"
    assert InspectionRun.objects.filter(target_id=tid).count() == 1


def test_a_running_state_also_blocks_and_final_state_unblocks(api) -> None:
    tid = make_target(api)
    run_id = post(api, f"/api/targets/{tid}/inspections/").json()["id"]
    InspectionRun.objects.filter(pk=run_id).update(status=S.RUNNING)
    assert post(api, f"/api/targets/{tid}/inspections/").status_code == 409
    InspectionRun.objects.filter(pk=run_id).update(status=S.FAILED)
    assert post(api, f"/api/targets/{tid}/inspections/").status_code == 202


def test_other_targets_are_not_blocked(api) -> None:
    a, b = make_target(api), make_target(api, FAIL_URL)
    assert post(api, f"/api/targets/{a}/inspections/").status_code == 202
    assert post(api, f"/api/targets/{b}/inspections/").status_code == 202


@pytest.mark.parametrize("body", [{"requested": []}, {"requested": ["bukan_kemampuan"]},
                                  {"requested": ["inspect_post", "inspect_post"]},
                                  {"requested": "inspect_post"}])
def test_invalid_scope_is_a_400_and_creates_no_run(api, body) -> None:
    tid = make_target(api)
    assert post(api, f"/api/targets/{tid}/inspections/", body).status_code == 400
    assert not InspectionRun.objects.exists()


def test_explicit_scope_is_honoured(api) -> None:
    tid = make_target(api)
    body = post(api, f"/api/targets/{tid}/inspections/", {"requested": ["inspect_post"]}).json()
    assert body["requested"] == ["inspect_post"]


# --- detail run -------------------------------------------------------------------------------


def test_completed_run_detail_exposes_both_counts_and_no_internal_fields(api, django_capture_on_commit_callbacks) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    d = detail(api, run_id)
    assert d["status"] == "COMPLETED" and d["data_state"] == "has_data"
    cov = d["coverage"]
    assert cov["platform_displayed_count"] == 4 and cov["observed_reply_count"] == 4
    assert cov["observed_object_count"] == 5 and cov["pagination_complete"] is True
    assert d["collector"] == {"name": "fixture-dataset", "version": "1"}
    assert d["source_method"] == "synthetic_fixture"
    assert d["ingestion"]["state"] == "FINISHED" and d["ingestion"]["failed_batches"] == 0
    assert d["reconciliation"]["state"] == "DONE" and d["reconciliation"]["counts"]["NEW"] == 5
    assert [x["code"] for x in d["messages"]] == ["run_completed"]
    blob = json.dumps(d)
    for key in FORBIDDEN_KEYS:
        assert key not in blob, key


def test_run_detail_does_not_contain_response_text(api, django_capture_on_commit_callbacks) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    assert "Setuju, kajian publik" not in json.dumps(detail(api, run_id))


def test_failure_runs_have_the_access_failed_state_and_a_friendly_headline(api, django_capture_on_commit_callbacks) -> None:  # AT-14
    tid = make_target(api, FAIL_URL)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(3)]
    ok, restricted, failed = (detail(api, i) for i in ids)
    assert ok["data_state"] == "has_data"
    assert restricted["status"] == "ACCESS_RESTRICTED" and restricted["data_state"] == "access_failed"
    assert restricted["messages"][0]["code"] == "access_restricted"
    assert failed["status"] == "FAILED" and failed["messages"][0]["code"] == "parse_failed"
    assert restricted["coverage"]["observed_reply_count"] in (0, None)
    assert rows(api, ids[1])["count"] == 0  # tanpa baris: bukan "nol balasan" yang sukses


def test_partial_run_detail(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(3)]
    d = detail(api, ids[2])
    assert d["status"] == "PARTIAL" and d["data_state"] == "partial"
    assert d["coverage"]["pagination_complete"] is False
    assert [x["code"] for x in d["messages"]][:2] == ["run_partial", "pagination_incomplete"]


def test_artifacts_are_listed_with_hashes_but_without_paths(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(4)]
    arts = detail(api, ids[3])["artifacts"]
    assert {a["kind"] for a in arts} == {"dom_snapshot", "manifest"}
    for a in arts:
        assert len(a["sha256"]) == 64 and a["size_bytes"] > 0
        assert set(a) == {"id", "kind", "sha256", "size_bytes", "content_type", "stored_at", "post_id"}
    assert detail(api, ids[0])["artifacts"] != arts


# --- respons mentah per run -------------------------------------------------------------------


def test_first_run_rows_are_all_new_with_parent_and_author_information(api, django_capture_on_commit_callbacks) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    page = rows(api, run_id)
    assert page["count"] == 5 and page["reconciled"] is True
    assert {r["reconciliation"] for r in page["results"]} == {"NEW"}
    by_id = {r["external_post_id"]: r for r in page["results"]}
    assert by_id["9000000013"]["parent_external_post_id"] == "9000000011"
    assert by_id["9000000001"]["parent_external_post_id"] is None
    reply = by_id["9000000011"]
    assert reply["author"]["external_actor_id"] == "a02" and reply["author"]["handle"] == "akun_a02"
    assert reply["published_at"] and reply["observed_in_this_run"] is True


def test_modified_and_not_observed_rows_across_runs(api, django_capture_on_commit_callbacks) -> None:  # AT-04/05
    tid = make_target(api)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(3)]
    second = {r["external_post_id"]: r for r in rows(api, ids[1])["results"]}
    assert second["9000000012"]["reconciliation"] == "MODIFIED"
    assert "text" in second["9000000012"]["changed_fields"]
    assert second["9000000015"]["reconciliation"] == "NEW"
    third = rows(api, ids[2])
    missing = [r for r in third["results"] if r["reconciliation"] == "NOT_OBSERVED"]
    assert [r["external_post_id"] for r in missing] == ["9000000014"]
    row = missing[0]
    assert row["observed_in_this_run"] is False and row["observed_at"] is None
    assert row["last_seen_run_sequence"] == 2 and row["text"]  # data terakhir terlihat
    assert third["results"][-1]["reconciliation"] == "NOT_OBSERVED"  # diurutkan paling akhir


def test_confirmed_unavailable_carries_the_adapter_evidence(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(4)]
    row = next(r for r in rows(api, ids[3])["results"] if r["external_post_id"] == "9000000014")
    assert row["reconciliation"] == "CONFIRMED_UNAVAILABLE" and "dihapus" in row["evidence"]


def test_pagination_walks_every_row_exactly_once(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    ids = [inspect(api, tid, django_capture_on_commit_callbacks) for _ in range(3)]
    full = [r["post_id"] for r in rows(api, ids[2], page_size=200)["results"]]
    seen: list[int] = []
    page = 1
    while True:
        chunk = rows(api, ids[2], page=page, page_size=2)
        assert chunk["page_size"] == 2 and chunk["count"] == len(full)
        seen += [r["post_id"] for r in chunk["results"]]
        if page * 2 >= chunk["count"]:
            break
        page += 1
    assert seen == full and len(set(seen)) == len(seen)


@pytest.mark.parametrize("query", [{"page": 0}, {"page": "x"}, {"page_size": 0}, {"page_size": 201}])
def test_bad_pagination_parameters_are_400(api, django_capture_on_commit_callbacks, query) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    assert api.get(f"/api/inspections/{run_id}/observations/", query).status_code == 400


def test_unreconciled_run_still_lists_observations_without_status(api, django_capture_on_commit_callbacks) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    InspectionRun.objects.filter(pk=run_id).update(reconciliation=None)
    page = rows(api, run_id)
    assert page["reconciled"] is False and page["count"] == 5
    assert {r["reconciliation"] for r in page["results"]} == {None}
    assert "reconciliation_pending" in [x["code"] for x in detail(api, run_id)["messages"]]


def test_unknown_values_stay_null_not_empty(api, tmp_path, settings, django_capture_on_commit_callbacks) -> None:
    d = tmp_path / "ds"
    d.mkdir()
    (d / "x.json").write_text(json.dumps({
        "schema_version": 1, "name": "nol", "platform": "x", "target_url": "https://x.com/u/status/5",
        "source_method": "synthetic_fixture",
        "snapshots": [{"observed_at": "2026-10-16T01:00:00Z", "outcome": "COMPLETED",
                       "pagination_complete": True, "observations": [
            {"type": "post", "id": "5", "actor": "a1", "text": "awal"},
            {"type": "reply", "id": "6", "actor": None, "parent": "5", "text": None,
             "needs_verification": True}]}]}))
    registry.clear()
    register_fixture_adapters(registry, d)
    run_id = inspect(api, make_target(api, "https://x.com/u/status/5"), django_capture_on_commit_callbacks)
    reply = next(r for r in rows(api, run_id)["results"] if r["external_post_id"] == "6")
    assert reply["text"] is None and reply["published_at"] is None
    assert reply["author"]["external_actor_id"] is None and reply["author"]["needs_verification"] is True
    d_ = detail(api, run_id)
    assert d_["coverage"]["platform_displayed_count"] is None  # tidak diketahui, bukan 0


# --- tinjauan ---------------------------------------------------------------------------------


def test_review_required_run_can_be_acknowledged_once(api, monkeypatch, django_capture_on_commit_callbacks) -> None:
    monkeypatch.setattr(svc, "_review_reasons", lambda report: ["mixed_source_methods"])
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    d = detail(api, run_id)
    assert d["status"] == "REVIEW_REQUIRED" and d["data_state"] == "needs_review"
    assert "review_mixed_source_methods" in [x["code"] for x in d["messages"]]
    res = post(api, f"/api/inspections/{run_id}/acknowledge-review/", {"note": "sudah dicek"})
    assert res.status_code == 200 and res.json()["status"] == "COMPLETED"
    assert res.json()["review"]["acknowledged"]["by"] == "analis"
    again = post(api, f"/api/inspections/{run_id}/acknowledge-review/")
    assert again.status_code == 409 and again.json()["code"] == "not_awaiting_review"


def test_acknowledging_a_run_that_needs_no_review_is_409(api, django_capture_on_commit_callbacks) -> None:
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    assert post(api, f"/api/inspections/{run_id}/acknowledge-review/").status_code == 409


def test_acknowledge_note_length_is_limited(api, monkeypatch, django_capture_on_commit_callbacks) -> None:
    monkeypatch.setattr(svc, "_review_reasons", lambda report: ["mixed_source_methods"])
    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    assert post(api, f"/api/inspections/{run_id}/acknowledge-review/", {"note": "x" * 2001}).status_code == 400


# --- kartu target -----------------------------------------------------------------------------


def target_json(api, tid):
    inv = api.get("/api/investigations/").json()[0]["id"]
    return next(t for t in api.get(f"/api/investigations/{inv}/").json()["targets"] if t["id"] == tid)


def test_target_has_null_latest_inspection_until_it_is_inspected(api) -> None:
    t = target_json(api, make_target(api))
    assert t["latest_inspection"] is None  # belum diperiksa, bukan "kosong"


def test_target_latest_inspection_summary_follows_the_newest_run(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api, FAIL_URL)
    inspect(api, tid, django_capture_on_commit_callbacks)
    assert target_json(api, tid)["latest_inspection"]["data_state"] == "has_data"
    inspect(api, tid, django_capture_on_commit_callbacks)
    latest = target_json(api, tid)["latest_inspection"]
    assert latest["sequence"] == 2 and latest["status"] == "ACCESS_RESTRICTED"
    assert latest["data_state"] == "access_failed" and latest["run_count"] == 2
    assert latest["headline"]["code"] == "access_restricted"


def test_pending_run_makes_the_target_in_progress(api) -> None:
    tid = make_target(api)
    post(api, f"/api/targets/{tid}/inspections/")
    assert target_json(api, tid)["latest_inspection"]["data_state"] == "in_progress"


def test_empty_context_adds_the_insufficient_context_notice(api) -> None:
    empty = target_json(api, make_target(api, note=""))
    assert [n["code"] for n in empty["notices"]] == ["context_insufficient"]
    filled = target_json(api, make_target(api, FAIL_URL, note="Ada konteks"))
    assert filled["notices"] == []


def test_presenter_caps_page_size_independently_of_the_serializer(api, django_capture_on_commit_callbacks) -> None:
    from api.runs import MAX_PAGE_SIZE, observation_page

    run_id = inspect(api, make_target(api), django_capture_on_commit_callbacks)
    page = observation_page(InspectionRun.objects.get(pk=run_id), page=1, page_size=10**6)
    assert page["page_size"] == MAX_PAGE_SIZE == 200
    assert observation_page(InspectionRun.objects.get(pk=run_id), page=-3, page_size=0)["page"] == 1


def test_run_detail_identifies_its_target_for_navigation(api, django_capture_on_commit_callbacks) -> None:
    tid = make_target(api)
    run_id = inspect(api, tid, django_capture_on_commit_callbacks)
    target = detail(api, run_id)["target"]
    inv_id = CollectionTarget.objects.get(pk=tid).investigation_id
    assert target == {"id": tid, "platform": "x", "target_type": "post",
                      "normalized_url": POST_URL, "investigation_id": inv_id}
    assert "context" not in target and "note" not in json.dumps(target)
