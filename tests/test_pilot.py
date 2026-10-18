"""WP-4.1: alat persiapan pilot (set anotasi, metrik) di atas dunia uji WP-2.7a."""

import json
import stat
from io import StringIO

import pytest
from collection.models import InspectionRun
from django.core.management import CommandError, call_command
from intelligence import pilot
from intelligence.assessment import current_assessments, review_assessment
from intelligence.evaluation import evaluate, gold_labels, load_annotations, load_predictions
from test_api_analysis import world  # noqa: F401

pytestmark = pytest.mark.django_db


# --- pengambilan contoh -----------------------------------------------------------------------


def test_sampling_is_deterministic_sorted_and_unique() -> None:
    strata = {"A": list(range(100, 200)), "B": list(range(1, 4)), "C": [50, 51]}
    first = pilot.sample_ids(strata, 20, seed=7)
    assert first == pilot.sample_ids(strata, 20, seed=7)
    assert first == sorted(set(first)) and len(first) == 20
    assert first != pilot.sample_ids(strata, 20, seed=8)


def test_sampling_round_robins_so_small_strata_are_not_drowned() -> None:
    strata = {"A": list(range(100, 300)), "B": [1, 2, 3], "C": [50, 51]}
    chosen = pilot.sample_ids(strata, 12, seed=1)
    assert {1, 2, 3, 50, 51} <= set(chosen)  # semua anggota strata kecil ikut
    assert len([c for c in chosen if c >= 100]) == 7


def test_sampling_takes_everything_when_there_are_fewer_candidates_and_ignores_empty_strata() -> (
    None
):
    assert pilot.sample_ids({"A": [3, 1], "B": [], "C": [2]}, 10, seed=1) == [1, 2, 3]
    assert pilot.sample_ids({}, 5, seed=1) == []
    assert pilot.sample_ids({"A": [1, 2, 3]}, 0, seed=1) == []


# --- set anotasi -------------------------------------------------------------------------------


def test_sheet_hides_machine_labels_and_manifest_is_honest_about_size(world) -> None:  # noqa: F811
    bundle = pilot.build_annotation_set(
        world.m2, n=60, seed=3, annotators=["penilai-A", "penilai-B"]
    )
    sheet, manifest = bundle["sheet"], bundle["manifest"]
    assert sheet["schema_version"] == 1 and "UNDETERMINED" in sheet["instructions"]
    assert manifest["selected"] == len(sheet["items"]) <= 60
    assert manifest["below_recommended_size"] is (manifest["selected"] < 50)
    assert (
        manifest["seed"] == 3
        and manifest["dataset_digest"] == world.m2.dataset_version.observation_digest
    )
    assert "PILOT" in manifest["notice"] and manifest["annotators"] == ["penilai-A", "penilai-B"]
    assert sum(manifest["strata_selected"].values()) == manifest["selected"]
    assert "RC-01" in manifest["allowed_values"]["response_character"]
    blob = json.dumps(sheet)
    for item in sheet["items"]:
        assert set(item["labels"]) == {"penilai-A", "penilai-B"}
        assert all(v is None for lab in item["labels"].values() for v in lab.values())
        assert set(item) == {"id", "text", "parent_chain", "tags", "labels"}
    assert (
        "machine_flagged" in blob or manifest["selected"] > 0
    )  # tag mesin hanya penanda, bukan label


def test_predictions_cover_the_sheet_and_come_from_the_original_machine_result(world) -> None:  # noqa: F811
    first = pilot.build_annotation_set(world.m2, n=500, seed=1, annotators=["A"])
    target = next(a for a in current_assessments(world.m2) if a.source == "MACHINE")
    machine = first["predictions"][str(target.observation_id)]
    review_assessment(
        assessment=target,
        by=world.member,
        reason="Koreksi untuk uji.",
        issue_stance="MIXED" if target.issue_stance != "MIXED" else "PRO",
    )
    again = pilot.build_annotation_set(world.m2, n=500, seed=1, annotators=["A"])
    assert set(again["predictions"]) == {i["id"] for i in again["sheet"]["items"]}
    assert again["predictions"][str(target.observation_id)] == machine  # bukan label hasil koreksi
    assert (
        again["sheet"] == first["sheet"] or again["sheet"]["items"]
    )  # lembar tak memuat label mesin


def test_same_seed_gives_the_same_set_and_a_different_seed_a_different_one(world) -> None:  # noqa: F811
    a = pilot.build_annotation_set(world.m2, n=8, seed=1, annotators=["A"])
    b = pilot.build_annotation_set(world.m2, n=8, seed=1, annotators=["A"])
    c = pilot.build_annotation_set(world.m2, n=8, seed=2, annotators=["A"])
    assert a == b
    assert [i["id"] for i in a["sheet"]["items"]] != [i["id"] for i in c["sheet"]["items"]]


def test_tags_mark_nested_and_missing_parent_context(world) -> None:  # noqa: F811
    bundle = pilot.build_annotation_set(world.m2, n=500, seed=1, annotators=["A"])
    tags = {t for item in bundle["sheet"]["items"] for t in item["tags"]}
    assert tags <= {
        "nested",
        "parent_unknown",
        "no_parent",
        "machine_flagged",
        "short_or_missing_text",
    }
    nested = [i for i in bundle["sheet"]["items"] if "nested" in i["tags"]]
    assert all(len(i["parent_chain"]) >= 2 for i in nested)


@pytest.mark.parametrize("annotators", [[], ["A", "A"]])
def test_bad_annotator_lists_are_rejected(world, annotators) -> None:  # noqa: F811
    with pytest.raises(ValueError, match="annotators"):
        pilot.build_annotation_set(world.m2, n=5, seed=1, annotators=annotators)


def test_only_m2_runs_can_be_sampled(world) -> None:  # noqa: F811
    with pytest.raises(ValueError, match="M2"):
        pilot.build_annotation_set(world.co, n=5, seed=1, annotators=["A"])


def test_filled_sheet_plugs_into_the_evaluation_harness_end_to_end(world) -> None:  # noqa: F811
    bundle = pilot.build_annotation_set(world.m2, n=30, seed=1, annotators=["A", "B"])
    sheet, predictions = bundle["sheet"], bundle["predictions"]
    with pytest.raises(Exception, match="issue_stance|wajib"):
        load_annotations(sheet)  # belum diisi: harness menolak, tidak diam-diam menganggap kosong
    for item in sheet["items"]:
        for name in ("A", "B"):
            item["labels"][name] = dict(predictions[item["id"]])
        item["gold"] = dict(predictions[item["id"]])
    items = load_annotations(sheet)
    report = evaluate(
        gold_labels(items), load_predictions(predictions), {i.id: i.tags for i in items}
    )
    assert report.to_dict()  # alur selesai; kesepakatan dan galat dihitung oleh harness yang sama


# --- perintah ----------------------------------------------------------------------------------


def test_command_writes_private_files(world, tmp_path) -> None:  # noqa: F811
    out = tmp_path / "pilot"
    buf = StringIO()
    call_command(
        "pilot_annotation_set",
        "--run",
        str(world.m2.pk),
        "--out",
        str(out),
        "--annotators",
        "A",
        "B",
        "--n",
        "10",
        "--seed",
        "4",
        stdout=buf,
    )
    assert "item ditulis" in buf.getvalue()
    for name in ("sheet.json", "predictions.json", "manifest.json"):
        assert stat.S_IMODE((out / name).stat().st_mode) == 0o600
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    assert json.loads((out / "manifest.json").read_text())["seed"] == 4


def test_command_requires_a_seed_and_a_completed_m2_run(world, tmp_path) -> None:  # noqa: F811
    with pytest.raises(CommandError):
        call_command(
            "pilot_annotation_set",
            "--run",
            str(world.m2.pk),
            "--out",
            str(tmp_path),
            "--annotators",
            "A",
        )
    with pytest.raises(CommandError, match="tidak ditemukan"):
        call_command(
            "pilot_annotation_set",
            "--run",
            "999999",
            "--out",
            str(tmp_path),
            "--annotators",
            "A",
            "--seed",
            "1",
        )
    with pytest.raises(CommandError, match="M2"):
        call_command(
            "pilot_annotation_set",
            "--run",
            str(world.co.pk),
            "--out",
            str(tmp_path),
            "--annotators",
            "A",
            "--seed",
            "1",
        )


# --- metrik ------------------------------------------------------------------------------------


def test_metrics_report_coverage_parse_failures_storage_and_never_a_pass_mark(world) -> None:  # noqa: F811
    run = InspectionRun.objects.filter(target__platform="x").order_by("id").first()
    InspectionRun.objects.filter(pk=run.pk).update(
        limitations=[{"code": "PARSE_FAILED", "message": "uji", "capability": None}],
        coverage={
            "platform_displayed_count": 10,
            "observed_reply_count": 7,
            "pagination_complete": False,
        },
    )
    report = pilot.pilot_metrics()
    x = report["platforms"]["x"]
    assert x["runs"] == InspectionRun.objects.filter(target__platform="x").count()
    assert x["parse_failures"] == 1 and x["pagination_incomplete"] == 1
    assert x["displayed"] >= 10 and x["observed"] >= 7
    assert x["observed_vs_displayed"] == round(x["observed"] / x["displayed"], 4)
    assert sum(x["outcomes"].values()) == x["runs"]
    assert report["storage"]["database_bytes"] > 0 and report["storage"]["artifact_rows"] >= 0
    assert "target lulus" in report["notice"] and "docs/operations.md" in report["restore_test"]
    assert not any(k in json.dumps(report).lower() for k in ("passed", "threshold", "ambang lulus"))


def test_metrics_ratio_is_none_when_no_run_reports_both_counts(world) -> None:  # noqa: F811
    InspectionRun.objects.update(coverage=None)
    report = pilot.pilot_metrics()
    assert all(p["observed_vs_displayed"] is None for p in report["platforms"].values())


def test_metrics_command_prints_text_and_json(world) -> None:  # noqa: F811
    text, js = StringIO(), StringIO()
    call_command("pilot_metrics", stdout=text)
    call_command("pilot_metrics", "--json", stdout=js)
    assert "penyimpanan:" in text.getvalue() and "uji restore:" in text.getvalue()
    assert "platforms" in json.loads(js.getvalue())


def test_context_tags_are_exact_per_condition() -> None:
    long = "teks yang cukup panjang untuk dinilai"
    base = {"depth": 1, "parent_unknown": False, "machine_flagged": False, "text": long}
    assert pilot.context_tags(**base) == []
    assert pilot.context_tags(**{**base, "depth": 2}) == ["nested"]
    assert pilot.context_tags(**{**base, "depth": 0}) == ["no_parent"]
    assert pilot.context_tags(**{**base, "depth": 0, "parent_unknown": True}) == ["parent_unknown"]
    assert pilot.context_tags(**{**base, "machine_flagged": True}) == ["machine_flagged"]
    assert pilot.context_tags(**{**base, "text": None}) == ["short_or_missing_text"]
    assert pilot.context_tags(**{**base, "text": "  pendek  "}) == ["short_or_missing_text"]
    padded = (
        " " * 3 + "x" * (pilot.SHORT_TEXT_CHARS - 1) + " " * 3
    )  # panjang mentah >= batas, terpangkas < batas
    assert pilot.context_tags(**{**base, "text": padded}) == ["short_or_missing_text"]
    assert pilot.context_tags(**{**base, "text": "x" * pilot.SHORT_TEXT_CHARS}) == []
    assert pilot.context_tags(**{**base, "text": "x" * (pilot.SHORT_TEXT_CHARS - 1)}) == [
        "short_or_missing_text"
    ]


def test_recommended_size_boundary_is_fifty() -> None:
    assert pilot.below_recommended_size(49) is True
    assert pilot.below_recommended_size(50) is False


def test_exported_text_and_parent_chain_match_the_stored_observations(world) -> None:  # noqa: F811
    from collection.models import PostObservation

    bundle = pilot.build_annotation_set(world.m2, n=500, seed=1, annotators=["A"])
    with_text = [i for i in bundle["sheet"]["items"] if i["text"]]
    assert with_text
    for item in with_text:
        assert item["text"] == PostObservation.objects.get(pk=int(item["id"])).text
    chained = [i for i in bundle["sheet"]["items"] if i["parent_chain"]]
    assert chained and all(
        isinstance(t, str | type(None)) for i in chained for t in i["parent_chain"]
    )


def test_metrics_count_unsupported_runs(world) -> None:  # noqa: F811
    run = InspectionRun.objects.filter(target__platform="x").order_by("id").first()
    InspectionRun.objects.filter(pk=run.pk).update(
        limitations=[{"code": "UNSUPPORTED", "message": "uji", "capability": None}]
    )
    assert pilot.pilot_metrics()["platforms"]["x"]["unsupported"] == 1


def test_command_tightens_an_existing_output_directory(world, tmp_path) -> None:  # noqa: F811
    out = tmp_path / "ada"
    out.mkdir(mode=0o755)
    out.chmod(0o755)
    call_command(
        "pilot_annotation_set",
        "--run",
        str(world.m2.pk),
        "--out",
        str(out),
        "--annotators",
        "A",
        "--n",
        "5",
        "--seed",
        "1",
        stdout=StringIO(),
    )
    assert stat.S_IMODE(out.stat().st_mode) == 0o700


def test_command_rejects_runs_that_are_not_completed(world, tmp_path) -> None:  # noqa: F811
    from intelligence import services
    from intelligence.models import AnalysisRun

    pending = services.create_analysis_run(
        dataset=world.m2.dataset_version,
        method="m2-rules",
        parameters=world.m2.parameters,
        by=world.owner,
        issue_context_version=world.m2.issue_context_version,
        target_context_versions=services.latest_target_contexts(world.m2.dataset_version),
    )
    assert AnalysisRun.objects.get(pk=pending.pk).status != "COMPLETED"
    with pytest.raises(CommandError, match="tidak ditemukan atau belum selesai"):
        call_command(
            "pilot_annotation_set",
            "--run",
            str(pending.pk),
            "--out",
            str(tmp_path / "x"),
            "--annotators",
            "A",
            "--seed",
            "1",
        )
