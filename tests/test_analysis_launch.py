"""WP-2.9: analisis dapat dimulai dari API/antarmuka, dijalankan worker, dengan parameter eksplisit."""

from datetime import timedelta

import pytest
from audit.models import AuditAction, AuditEvent
from collection.models import InspectionRun
from collection.contracts import SourceObjectType
from collection_helpers import OBSERVED, ingest, new_run, obs, register
from intelligence import launch as launch_module
from intelligence import services, tasks
from intelligence.errors import InvalidParameters
from intelligence.examples import CO_EXAMPLE, M3_EXAMPLE, M4_EXAMPLE
from intelligence.models import AnalysisRun, DatasetVersion
from investigations import services as inv_services
from investigations.enums import Platform
from test_api_analysis import CUES, get_json, post, world  # noqa: F401

pytestmark = pytest.mark.django_db
START = (OBSERVED - timedelta(days=10)).isoformat()
END = (OBSERVED + timedelta(days=1)).isoformat()


@pytest.fixture
def queued(monkeypatch):
    """Tangkap pengiriman ke antrean (tanpa broker): daftar (args, queue)."""
    sent: list[tuple] = []
    monkeypatch.setattr(
        tasks.execute_analysis,
        "apply_async",
        lambda args=None, queue=None, **kw: sent.append((args, queue)),
    )
    return sent


def runs_url(w):
    return f"/api/investigations/{w.inv.pk}/analysis-runs/"


def m2_body(w, **over):
    body = {
        "method": "m2-rules",
        "dataset_id": w.dataset.pk,
        "proposition_id": w.prop.pk,
        "parameters": {"pro_cues": CUES[0], "contra_cues": CUES[1]},
    }
    body.update(over)
    return body


def launch(w, body, who="member", capture=None):
    if capture is None:
        return post(w.clients[who], runs_url(w), body)
    with capture(execute=True):
        return post(w.clients[who], runs_url(w), body)


# --- bahan formulir -------------------------------------------------------------------------


def test_setup_lists_datasets_runs_propositions_examples_and_the_context_note(world) -> None:  # noqa: F811
    data = get_json(world, f"/api/investigations/{world.inv.pk}/analysis-setup/")
    assert world.dataset.pk in [d["id"] for d in data["datasets"]]
    assert world.run.pk in [r["id"] for r in data["inspection_runs"]]
    assert [p["id"] for p in data["propositions"]] == [world.prop.pk]
    assert data["propositions"][0]["label"] == "P1"
    assert world.m2.pk in [r["id"] for r in data["m2_runs"]]
    assert data["examples"]["co"] == CO_EXAMPLE and data["examples"]["m3"] == M3_EXAMPLE
    assert data["examples"]["m4"] == M4_EXAMPLE
    assert "CONTOH" in data["notes"]["exploratory"]
    assert "TEKSNYA belum dibaca" in data["notes"]["context"]


# --- dataset --------------------------------------------------------------------------------


def test_member_freezes_a_new_dataset_from_chosen_inspections(world) -> None:  # noqa: F811
    before = DatasetVersion.objects.filter(investigation=world.inv).count()
    res = post(
        world.clients["member"],
        f"/api/investigations/{world.inv.pk}/datasets/",
        {"inspection_run_ids": [world.run.pk], "note": "uji"},
    )
    assert res.status_code == 201, res.content[:200]
    body = res.json()
    assert body["number"] == world.dataset.number + 1 and body["platform"] == "x"
    assert body["observation_count"] == world.dataset.observation_count and body["note"] == "uji"
    assert DatasetVersion.objects.filter(investigation=world.inv).count() == before + 1


@pytest.mark.parametrize(
    "body",
    [
        {"inspection_run_ids": []},
        {"inspection_run_ids": [999999]},
        {"inspection_run_ids": ["a"]},
        {},
    ],
)
def test_dataset_creation_rejects_bad_selections(world, body) -> None:  # noqa: F811
    res = post(world.clients["member"], f"/api/investigations/{world.inv.pk}/datasets/", body)
    assert res.status_code == 400, res.content[:200]


# --- memulai analisis -----------------------------------------------------------------------


def test_launch_creates_a_pending_run_audits_it_and_sends_it_to_the_analysis_queue(
    world, queued, django_capture_on_commit_callbacks
) -> None:  # noqa: F811
    res = launch(world, m2_body(world), capture=django_capture_on_commit_callbacks)
    assert res.status_code == 202, res.content[:300]
    run = res.json()
    assert (
        run["status"] == "PENDING"
        and run["method"] == "m2-rules"
        and run["created_by"] == "anggota"
    )
    assert run["parameters"]["propositions"][str(world.prop.pk)]["pro_cues"] == CUES[0]
    assert queued == [((run["id"],), "analysis")]
    event = AuditEvent.objects.filter(action=AuditAction.ANALYSIS_RUN, subject_id=run["id"]).get()
    assert event.actor == world.member and event.before is None
    assert (
        event.after["method"] == "m2-rules"
        and event.after["dataset_number"] == world.dataset.number
    )
    assert (
        event.after["parameters_digest"] == AnalysisRun.objects.get(pk=run["id"]).parameters_digest
    )


def test_the_worker_task_executes_the_run_and_a_second_delivery_is_harmless(world, queued) -> None:  # noqa: F811
    run = launch(world, m2_body(world)).json()
    first = tasks.execute_analysis(run["id"])
    assert first == {"run": run["id"], "handled": True, "status": "COMPLETED"}
    again = tasks.execute_analysis(run["id"])
    assert again == {"run": run["id"], "handled": False, "status": "COMPLETED"}
    assert tasks.execute_analysis(999999) == {"run": 999999, "handled": False, "status": "MISSING"}
    listed = get_json(world, runs_url(world))["results"]
    assert next(r for r in listed if r["id"] == run["id"])["status"] == "COMPLETED"


def test_every_method_can_be_launched_with_explicit_parameters(world, queued) -> None:  # noqa: F811
    m2 = launch(world, m2_body(world)).json()
    tasks.execute_analysis(m2["id"])
    m3 = launch(
        world,
        {
            "method": "m3-profile",
            "dataset_id": world.dataset.pk,
            "proposition_id": world.prop.pk,
            "source_run_id": m2["id"],
            "parameters": {"period_start": START, "period_end": END, **M3_EXAMPLE},
        },
    )
    m4_plain = launch(
        world,
        {
            "method": "m4-network",
            "dataset_id": world.dataset.pk,
            "parameters": {"window_start": START, "window_end": END, **M4_EXAMPLE},
        },
    )
    m4_stance = launch(
        world,
        {
            "method": "m4-network",
            "dataset_id": world.dataset.pk,
            "proposition_id": world.prop.pk,
            "source_run_id": m2["id"],
            "parameters": {"window_start": START, "window_end": END, **M4_EXAMPLE},
        },
    )
    co = launch(
        world,
        {
            "method": "co-indicators",
            "dataset_id": world.dataset.pk,
            "parameters": {"window_start": START, "window_end": END, **CO_EXAMPLE},
        },
    )
    for res in (m3, m4_plain, m4_stance, co):
        assert res.status_code == 202, res.content[:300]
        assert tasks.execute_analysis(res.json()["id"])["status"] == "COMPLETED"
    assert m3.json()["parameters"]["source_run"] == m2["id"]
    assert m4_plain.json()["parameters"]["source_run"] is None
    assert m4_stance.json()["parameters"]["proposition_id"] == world.prop.pk


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["parameters"].pop("pro_cues"),
        lambda b: b["parameters"].update(extra=1),
        lambda b: b["parameters"].update(pro_cues=[], contra_cues=["  "]),
        lambda b: b["parameters"].update(pro_cues="harus diaudit"),
        lambda b: b["parameters"].update(pro_cues=["x" * 201]),
        lambda b: b.update(proposition_id=None),
        lambda b: b.update(proposition_id=999999),
        lambda b: b.update(dataset_id=999999),
        lambda b: b.update(method="buzzer-score"),
        lambda b: b.pop("parameters"),
    ],
)
def test_m2_launch_rejects_incomplete_or_invalid_input_without_creating_a_run(
    world, queued, mutate
) -> None:  # noqa: F811
    body = m2_body(world)
    mutate(body)
    before = AnalysisRun.objects.count()
    res = launch(world, body)
    assert res.status_code == 400, res.content[:300]
    assert AnalysisRun.objects.count() == before and queued == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("min_responses"),
        lambda p: p.update(period_start="2026-10-01T00:00:00"),  # tanpa zona waktu
        lambda p: p.update(period_start="bukan waktu"),
        lambda p: p.update(period_end=START, period_start=END),
        lambda p: p.update(bucket_hours=0),
        lambda p: p.update(bucket_hours="24"),
    ],
)
def test_m3_launch_validates_every_parameter_and_has_no_defaults(world, queued, mutate) -> None:  # noqa: F811
    m2 = launch(world, m2_body(world)).json()
    tasks.execute_analysis(m2["id"])
    params = {"period_start": START, "period_end": END, **M3_EXAMPLE}
    mutate(params)
    res = launch(
        world,
        {
            "method": "m3-profile",
            "dataset_id": world.dataset.pk,
            "proposition_id": world.prop.pk,
            "source_run_id": m2["id"],
            "parameters": params,
        },
    )
    assert res.status_code == 400, res.content[:300]


def test_m3_and_m4_require_a_completed_m2_run_on_the_same_dataset(world, queued) -> None:  # noqa: F811
    pending = launch(world, m2_body(world)).json()  # belum dieksekusi: PENDING
    other = post(
        world.clients["member"],
        f"/api/investigations/{world.inv.pk}/datasets/",
        {"inspection_run_ids": [world.run.pk]},
    ).json()
    base = {
        "method": "m3-profile",
        "proposition_id": world.prop.pk,
        "parameters": {"period_start": START, "period_end": END, **M3_EXAMPLE},
    }
    for dataset_id, source in ((world.dataset.pk, pending["id"]), (other["id"], world.m2.pk)):
        res = launch(world, {**base, "dataset_id": dataset_id, "source_run_id": source})
        assert res.status_code == 400 and "M2 sumber" in res.json()["detail"], res.content[:200]
    no_source = launch(world, {**base, "dataset_id": world.dataset.pk})
    assert no_source.status_code == 400
    half = launch(
        world,
        {
            "method": "m4-network",
            "dataset_id": world.dataset.pk,
            "proposition_id": world.prop.pk,  # stance view butuh proposition DAN run M2
            "parameters": {"window_start": START, "window_end": END, **M4_EXAMPLE},
        },
    )
    assert half.status_code == 400 and "keduanya" in half.json()["detail"]


def test_co_launch_requires_every_coordination_parameter(world, queued) -> None:  # noqa: F811
    params = {"window_start": START, "window_end": END, **CO_EXAMPLE}
    del params["permutations"]
    res = launch(
        world, {"method": "co-indicators", "dataset_id": world.dataset.pk, "parameters": params}
    )
    assert res.status_code == 400 and "tepat" in res.json()["detail"]


def test_a_broker_outage_marks_the_run_failed_instead_of_leaving_it_pending(
    world, monkeypatch, django_capture_on_commit_callbacks
) -> None:  # noqa: F811
    def boom(*args, **kwargs):
        raise ConnectionError("broker mati")

    monkeypatch.setattr(tasks.execute_analysis, "apply_async", boom)
    res = launch(world, m2_body(world), capture=django_capture_on_commit_callbacks)
    assert res.status_code == 202
    run = AnalysisRun.objects.get(pk=res.json()["id"])
    assert run.status == "FAILED" and "AntreanTidakTersedia" in run.error
    assert get_json(world, runs_url(world))["results"][0]["error"] == run.error


def test_only_members_may_launch_and_outsiders_cannot_tell_the_investigation_exists(
    world, queued
) -> None:  # noqa: F811
    assert launch(world, m2_body(world), who="viewer").status_code == 403
    assert launch(world, m2_body(world), who="outsider").status_code == 404
    assert launch(world, m2_body(world), who="owner").status_code == 202
    assert launch(world, m2_body(world), who="admin").status_code == 202
    assert (
        post(
            world.clients["viewer"], f"/api/investigations/{world.inv.pk}/datasets/", {}
        ).status_code
        == 403
    )


# --- analisis ulang -------------------------------------------------------------------------


def test_reanalysis_without_new_observations_is_a_clear_conflict(world, queued) -> None:  # noqa: F811
    res = post(world.clients["member"], f"/api/analysis-runs/{world.m2.pk}/reanalyze/", {})
    assert res.status_code == 409 and res.json()["code"] == "nothing_new"


def test_reanalysis_after_a_new_inspection_makes_a_new_dataset_and_run_and_keeps_the_old(
    world, queued
) -> None:  # noqa: F811
    run = new_run(world.target, world.owner)
    ingest(
        run,
        [obs(run, "r-baru", actor="u9", parent="seed", text="Komentar baru.", published_at=None)],
    )
    InspectionRun.objects.filter(pk=run.pk).update(status="RUNNING")
    InspectionRun.objects.filter(pk=run.pk).update(status="COMPLETED")
    old_status = AnalysisRun.objects.get(pk=world.m2.pk).status
    res = post(
        world.clients["member"],
        f"/api/analysis-runs/{world.m2.pk}/reanalyze/",
        {"use_latest_context": True},
    )
    assert res.status_code == 202, res.content[:300]
    new = res.json()
    assert new["previous_run"] == world.m2.pk and new["status"] == "PENDING"
    assert new["dataset"]["number"] > world.m2.dataset_version.number
    assert new["parameters"] == world.m2.parameters
    assert AnalysisRun.objects.get(pk=world.m2.pk).status == old_status  # run lama utuh
    event = AuditEvent.objects.filter(action=AuditAction.ANALYSIS_RUN, subject_id=new["id"]).get()
    assert event.before["analysis_run_id"] == world.m2.pk
    assert (
        post(
            world.clients["viewer"], f"/api/analysis-runs/{world.m2.pk}/reanalyze/", {}
        ).status_code
        == 403
    )


# --- pagar berlapis yang diuji satu per satu --------------------------------------------------


@pytest.fixture
def other(world):  # noqa: F811
    """Investigasi lain (milik orang yang sama) dengan proposition, pemeriksaan, dan dataset sendiri."""
    inv = inv_services.create_investigation(user=world.owner, name="Investigasi lain")
    issue = inv_services.create_issue(investigation=inv, user=world.owner, title="Isu lain")
    prop = inv_services.add_proposition(issue=issue, user=world.owner, statement="Klaim lain.")
    target = register(inv, world.owner, Platform.X, "https://x.com/lain/status/77")
    run = new_run(target, world.owner)
    ingest(
        run,
        [
            obs(run, "s", kind=SourceObjectType.POST, actor="z0", text="Posting lain."),
            obs(run, "r", actor="z1", parent="s", text="Balasan lain.", published_at=None),
        ],
    )
    dataset = services.create_dataset_version(investigation=inv, runs=[run], by=world.owner)
    return type("Other", (), {"inv": inv, "prop": prop, "run": run, "dataset": dataset})


def test_cues_are_trimmed_and_deduplicated_before_being_stored(world, queued) -> None:  # noqa: F811
    res = launch(
        world,
        m2_body(
            world,
            parameters={
                "pro_cues": ["  harus diaudit  ", "harus diaudit", "", "audit harus dilakukan"],
                "contra_cues": ["tidak perlu diaudit"],
            },
        ),
    )
    stored = res.json()["parameters"]["propositions"][str(world.prop.pk)]
    assert stored["pro_cues"] == ["harus diaudit", "audit harus dilakukan"]


def test_the_issue_context_is_frozen_into_the_run(world, queued) -> None:  # noqa: F811
    assert launch(world, m2_body(world)).json()["issue_context_version"] == 1
    inv_services.revise_issue_context(issue=world.issue, user=world.owner, definition="Revisi.")
    assert launch(world, m2_body(world)).json()["issue_context_version"] == 2


def test_a_proposition_from_another_investigation_is_rejected(world, other, queued) -> None:  # noqa: F811
    res = launch(world, m2_body(world, proposition_id=other.prop.pk))
    assert res.status_code == 400 and "tidak ditemukan pada investigasi ini" in res.json()["detail"]


def test_a_dataset_from_another_investigation_is_rejected_at_both_layers(
    world, other, queued
) -> None:  # noqa: F811
    res = launch(world, m2_body(world, dataset_id=other.dataset.pk))
    assert res.status_code == 400 and "dataset tidak ditemukan" in res.json()["detail"]
    with pytest.raises(InvalidParameters, match="bukan milik investigasi ini"):
        launch_module.build_parameters(
            investigation=world.inv,
            dataset=other.dataset,
            method="m2-rules",
            data={"pro_cues": ["a"], "contra_cues": []},
            proposition_id=world.prop.pk,
            source_run_id=None,
        )


def test_the_method_is_checked_by_the_builder_not_only_by_the_serializer(world) -> None:  # noqa: F811
    with pytest.raises(InvalidParameters, match="metode harus salah satu"):
        launch_module.build_parameters(
            investigation=world.inv,
            dataset=world.dataset,
            method="buzzer-score",
            data={},
            proposition_id=None,
            source_run_id=None,
        )


def test_proposition_is_required_and_the_message_says_so(world, queued) -> None:  # noqa: F811
    res = launch(world, m2_body(world, proposition_id=None))
    assert res.status_code == 400 and "proposition wajib" in res.json()["detail"]


def test_the_source_run_must_be_an_m2_run_even_when_it_is_complete_on_the_same_dataset(
    world, queued
) -> None:  # noqa: F811
    res = launch(
        world,
        {
            "method": "m3-profile",
            "dataset_id": world.dataset.pk,
            "proposition_id": world.prop.pk,
            "source_run_id": world.co.pk,  # selesai, dataset sama, tetapi bukan M2
            "parameters": {"period_start": START, "period_end": END, **M3_EXAMPLE},
        },
    )
    assert res.status_code == 400 and "M2 sumber" in res.json()["detail"]


def test_dataset_creation_reports_unknown_and_foreign_inspections_clearly(world, other) -> None:  # noqa: F811
    url = f"/api/investigations/{world.inv.pk}/datasets/"
    for ids in ([999999], [other.run.pk], [world.run.pk, 999999]):
        res = post(world.clients["member"], url, {"inspection_run_ids": ids})
        assert (
            res.status_code == 400
            and "tidak ditemukan pada investigasi ini" in res.json()["detail"]
        )


def add_inspection(world, external_id):  # noqa: F811
    run = new_run(world.target, world.owner)
    ingest(
        run,
        [
            obs(
                run,
                external_id,
                actor="u9",
                parent="seed",
                text="Komentar baru.",
                published_at=None,
            )
        ],
    )
    InspectionRun.objects.filter(pk=run.pk).update(status="RUNNING")
    InspectionRun.objects.filter(pk=run.pk).update(status="COMPLETED")


def test_reanalysis_is_sent_to_the_queue_after_commit(
    world, queued, django_capture_on_commit_callbacks
) -> None:  # noqa: F811
    add_inspection(world, "r-ulang")
    with django_capture_on_commit_callbacks(execute=True):
        res = post(world.clients["member"], f"/api/analysis-runs/{world.m2.pk}/reanalyze/", {})
    assert res.status_code == 202 and queued == [((res.json()["id"],), "analysis")]


@pytest.mark.parametrize(("latest", "expected"), [(True, 2), (False, 1)])
def test_reanalysis_uses_the_latest_issue_context_only_when_asked(
    world, queued, latest, expected
) -> None:  # noqa: F811
    add_inspection(world, f"r-konteks-{expected}")
    inv_services.revise_issue_context(issue=world.issue, user=world.owner, definition="Revisi.")
    res = post(
        world.clients["member"],
        f"/api/analysis-runs/{world.m2.pk}/reanalyze/",
        {"use_latest_context": latest},
    )
    assert res.status_code == 202 and res.json()["issue_context_version"] == expected


# --- versi konteks yang dibekukan (A2) ---------------------------------------------------------


def ctx_of(run_json):
    return run_json["issue_context_version"], {
        c["target_id"]: c["version"] for c in run_json["target_contexts"]
    }


def revise_both(world):  # noqa: F811
    inv_services.revise_issue_context(issue=world.issue, user=world.owner, definition="Isu v2.")
    inv_services.revise_target_context(target=world.target, user=world.owner, note="Target v2.")


def test_setup_lists_every_context_version_newest_first_and_dataset_targets(world) -> None:  # noqa: F811
    revise_both(world)
    data = get_json(world, f"/api/investigations/{world.inv.pk}/analysis-setup/")
    issue = next(i for i in data["issues"] if i["id"] == world.issue.pk)
    assert [v["version"] for v in issue["versions"]] == [2, 1]
    assert issue["versions"][0]["text"] == "Isu v2."
    target = next(t for t in data["targets"] if t["id"] == world.target.pk)
    assert [v["version"] for v in target["versions"]] == [2, 1]
    assert target["versions"][0]["text"] == "Target v2."
    dataset = next(d for d in data["datasets"] if d["id"] == world.dataset.pk)
    assert world.target.pk in dataset["target_ids"]


def test_without_an_explicit_choice_the_latest_contexts_are_frozen(world, queued) -> None:  # noqa: F811
    revise_both(world)
    issue_v, targets = ctx_of(launch(world, m2_body(world)).json())
    assert issue_v == 2 and targets[world.target.pk] == 2


def test_an_explicit_older_version_is_what_gets_frozen_and_audited(world, queued) -> None:  # noqa: F811
    revise_both(world)
    body = m2_body(
        world,
        issue_context_version=1,
        target_context_versions={str(world.target.pk): 1},
    )
    res = launch(world, body)
    assert res.status_code == 202, res.content[:300]
    issue_v, targets = ctx_of(res.json())
    assert issue_v == 1 and targets[world.target.pk] == 1
    event = AuditEvent.objects.filter(
        action=AuditAction.ANALYSIS_RUN, subject_id=res.json()["id"]
    ).get()
    assert event.after["issue_context_version"] == 1
    assert event.after["target_context_versions"] == {str(world.target.pk): 1}


def test_a_target_can_be_frozen_without_context_and_unlisted_targets_use_the_latest(
    world, queued
) -> None:  # noqa: F811
    revise_both(world)
    res = launch(world, m2_body(world, target_context_versions={str(world.target.pk): None}))
    issue_v, targets = ctx_of(res.json())
    assert targets[world.target.pk] is None and issue_v == 2
    only_issue = launch(world, m2_body(world, issue_context_version=1))
    issue_v, targets = ctx_of(only_issue.json())
    assert issue_v == 1 and targets[world.target.pk] == 2


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"issue_context_version": 99}, "konteks isu versi 99 tidak ada"),
        ({"target_context_versions": {"999999": 1}}, "tidak ada pada dataset ini"),
        ({"target_context_versions": {"TARGET": 99}}, "versi 99 tidak ada"),
    ],
)
def test_unknown_versions_and_foreign_targets_are_rejected_clearly(
    world, queued, extra, message
) -> None:  # noqa: F811
    if "TARGET" in extra.get("target_context_versions", {}):
        extra = {"target_context_versions": {str(world.target.pk): 99}}
    before = AnalysisRun.objects.count()
    res = launch(world, m2_body(world, **extra))
    assert res.status_code == 400 and message in res.json()["detail"], res.content[:300]
    assert AnalysisRun.objects.count() == before


def test_target_outside_the_dataset_is_rejected_even_if_it_exists(world, other, queued) -> None:  # noqa: F811
    foreign = other.run.target_id
    res = launch(world, m2_body(world, target_context_versions={str(foreign): 1}))
    assert res.status_code == 400 and "tidak ada pada dataset ini" in res.json()["detail"]


def test_an_issue_version_is_rejected_for_methods_without_an_issue(world, queued) -> None:  # noqa: F811
    res = launch(
        world,
        {
            "method": "co-indicators",
            "dataset_id": world.dataset.pk,
            "issue_context_version": 1,
            "parameters": {"window_start": START, "window_end": END, **CO_EXAMPLE},
        },
    )
    assert res.status_code == 400 and "tidak memakai konteks isu" in res.json()["detail"]


@pytest.mark.parametrize("bad", [{"abc": 1}, {"1": "x"}, {"1": 0}])
def test_malformed_target_version_maps_are_rejected(world, queued, bad) -> None:  # noqa: F811
    assert launch(world, m2_body(world, target_context_versions=bad)).status_code == 400
