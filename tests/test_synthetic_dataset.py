"""Dataset sintetis I2 (WP-2.0; PRD 16.1, Lampiran A; AT-08..AT-13, AT-17)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from collection.datasets import load_dataset_file
from intelligence.synthetic import DEFAULT_SEED, generate, write

COORDINATED = {f"s{i:02d}" for i in range(37, 47)}


@pytest.fixture(scope="module")
def bundle():
    return generate()


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _x_files(bundle) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in bundle.datasets.items() if v["platform"] == "x"}


def _final(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    return dataset["snapshots"][-1]["observations"]


def test_generation_is_deterministic_and_every_file_depends_on_the_seed() -> None:
    first, again, other = (
        generate(s).datasets for s in (DEFAULT_SEED, DEFAULT_SEED, DEFAULT_SEED + 1)
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first.keys() == other.keys()
    for (
        name
    ) in first:  # tiap komponen: isi percakapan, bukan hanya pemilihan perubahan antar putaran
        a, b = (
            first[name]["snapshots"][0]["observations"],
            other[name]["snapshots"][0]["observations"],
        )
        assert [(o["actor"], o["text"]) for o in a] != [(o["actor"], o["text"]) for o in b], name


def test_size_matches_prd_target(bundle) -> None:
    x = _x_files(bundle)
    assert len(x) == 3
    assert all(len(d["snapshots"]) == 4 for d in x.values())
    replies = [o for d in x.values() for o in _final(d) if o["type"] == "reply"]
    assert 280 <= len(replies) <= 310
    actors = {o["actor"] for d in x.values() for o in _final(d)}
    assert len(actors) == 50


def test_every_file_passes_the_real_loader_and_adapter_contract(tmp_path: Path) -> None:
    write(tmp_path)
    files = sorted((tmp_path / "datasets").glob("*.json"))
    assert len(files) == 4
    for f in files:
        dataset = load_dataset_file(f)  # termasuk dry-run kontrak adapter tiap snapshot
        assert dataset.source_method.value == "synthetic_fixture"
        assert dataset.name.startswith("SINTETIS-I2-")


def test_ground_truth_is_kept_outside_the_dataset_directory(tmp_path: Path) -> None:
    write(tmp_path)
    assert (tmp_path / "ground-truth.json").is_file()
    assert not list((tmp_path / "datasets").glob("ground*"))
    truth = json.loads((tmp_path / "ground-truth.json").read_text())
    assert truth["synthetic"] is True


def test_ground_truth_covers_every_observation(bundle) -> None:
    for n, dataset in enumerate(_x_files(bundle).values(), start=1):
        keyed = bundle.ground_truth["targets"][str(n)]["observations"]
        ids = {o["id"] for s in dataset["snapshots"] for o in s["observations"]}
        assert ids == set(keyed)


def _truth_by_case(bundle, case: str) -> dict[str, Any]:
    found = [
        v
        for t in bundle.ground_truth["targets"].values()
        for v in t["observations"].values()
        if v["case"] == case
    ]
    assert len(found) == 1, case
    return found[0]


def test_appendix_a_cases_are_present_with_expected_labels(bundle) -> None:
    r1 = _truth_by_case(bundle, "A-R1")
    r2 = _truth_by_case(bundle, "A-R2-setuju-pada-reply-tingkat-2")
    assert (r1["issue_stance"], r1["target_alignment"]) == ("PRO", "OPPOSE")
    # "Setuju" membalas reply (bukan seed): mendukung P1 dan SUPPORT terhadap induk langsungnya
    assert (r2["issue_stance"], r2["target_alignment"]) == ("PRO", "SUPPORT")
    assert r2["parent"] == next(
        k
        for k, v in bundle.ground_truth["targets"]["1"]["observations"].items()
        if v["case"] == "A-R1"
    )
    assert _truth_by_case(bundle, "A-R3")["response_character"] == ["RC-05"]
    assert _truth_by_case(bundle, "A-R3")["issue_stance"] == "UNDETERMINED"
    assert _truth_by_case(bundle, "A-R4")["response_character"] == ["RC-04"]
    r5 = _truth_by_case(bundle, "A-R5")
    assert (r5["issue_stance"], r5["expression_sentiment"]) == ("UNDETERMINED", "NEGATIVE")
    assert _truth_by_case(bundle, "AT-09-acuan-video")["media_dependent"] is True
    legit = _truth_by_case(bundle, "AT-10-kritik-sah")
    attack = _truth_by_case(bundle, "AT-10-serangan-pribadi")
    assert legit["response_character"] == ["RC-02"] and attack["response_character"] == ["RC-05"]
    assert legit["issue_stance"] == attack["issue_stance"] == "UNDETERMINED"


def test_threats_always_require_human_review(bundle) -> None:
    labelled = [
        v
        for t in bundle.ground_truth["targets"].values()
        for v in t["observations"].values()
        if "RC-07" in v["response_character"]
    ]
    assert labelled and all(v["needs_human_review"] for v in labelled)


def test_nested_agreement_follows_the_real_parent(bundle) -> None:
    """Label "setuju" mengikuti stance induk langsung, bukan seed (AT-08)."""
    checked = opposed = 0
    for t in bundle.ground_truth["targets"].values():
        obs = t["observations"]
        for v in obs.values():
            if v["kind"] == "reply" and v["response_character"] == ["RC-01"] and v["parent"]:
                parent = obs[v["parent"]]
                if parent["kind"] == "reply" and v["target_alignment"] == "SUPPORT":
                    assert v["issue_stance"] == parent["issue_stance"]
                    checked += 1
            if v["kind"] == "reply" and v["response_character"] == ["RC-03"] and v["parent"]:
                parent = obs[v["parent"]]
                if parent["kind"] == "reply" and v["target_alignment"] == "OPPOSE":
                    assert {v["issue_stance"], parent["issue_stance"]} == {"PRO", "CONTRA"}
                    opposed += 1
    assert checked >= 5 and opposed >= 1


def test_planted_group_is_really_synchronous_in_the_data(bundle) -> None:
    """Dibuktikan dari dataset (bukan dari kunci): K membalas induk yang sama dalam <= 90 dtk."""
    for dataset in _x_files(bundle).values():
        obs = _final(dataset)
        by_actor_reply = {
            o["actor"]: _t(o["published_at"])
            for o in obs
            if o["type"] == "reply" and o["actor"] in COORDINATED
        }
        assert len(by_actor_reply) == 8
        times = sorted(by_actor_reply.values())
        assert (times[-1] - times[0]).total_seconds() <= 90
        reposters = {o["actor"] for o in obs if o["type"] == "repost"}
        assert reposters == set(by_actor_reply)
        assert len({o["reposted"] for o in obs if o["type"] == "repost"}) == 1
    # kelompok yang sama muncul pada ketiga target (CO-06)
    per_target = [
        {o["actor"] for o in _final(d) if o["actor"] in COORDINATED}
        for d in _x_files(bundle).values()
    ]
    assert len(set.intersection(*per_target)) >= 4


def test_organic_burst_is_fast_but_not_a_planted_pattern(bundle) -> None:
    """Hard negative: banyak akun membalas cepat tetapi teksnya berbeda dan tanpa tautan bersama."""
    for n, dataset in enumerate(_x_files(bundle).values(), start=1):
        keyed = bundle.ground_truth["targets"][str(n)]["observations"]
        burst = [o for o in _final(dataset) if keyed[o["id"]]["group"] == "organic-burst"]
        assert len(burst) == 8
        assert max(_t(o["published_at"]) for o in burst) < min(
            _t(o["published_at"])
            for o in _final(dataset)
            if o["type"] == "reply" and o["actor"] in COORDINATED
        )
        assert len({o["text"] for o in burst}) >= 6
        assert not any(COORDINATED & {o["actor"]} for o in burst)


def test_many_accounts_same_stance_without_coordination(bundle) -> None:
    organic = [
        v
        for t in bundle.ground_truth["targets"].values()
        for v in t["observations"].values()
        if v["group"] == "organic" and v["issue_stance"] == "PRO" and v["kind"] == "reply"
    ]
    assert len({v["actor"] for v in organic}) >= 10
    assert not any(v["actor"] in COORDINATED for v in organic)


def test_changes_across_rounds_are_visible_in_the_data(bundle) -> None:
    x = _x_files(bundle)
    t1, t2 = (x["x-target-1.json"], x["x-target-2.json"])

    def by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {o["id"]: o for o in snapshot["observations"]}

    # perubahan teks pada ID yang sama (AT-05) dan objek baru tiap putaran (AT-03)
    edits = bundle.ground_truth["targets"]["1"]["changes"]["edited"]
    assert edits
    s2, s3 = by_id(t1["snapshots"][1]), by_id(t1["snapshots"][2])
    for e in edits:
        assert s3[e["id"]]["text"] == s2[e["id"]]["text"] + e["appended_text"]
    assert len(by_id(t1["snapshots"][3])) > len(by_id(t1["snapshots"][0]))
    # inspeksi parsial: objek hilang tanpa pernyataan sumber (AT-04) -> kembali pada putaran 4
    s3_t2 = t2["snapshots"][2]
    assert s3_t2["outcome"] == "PARTIAL" and s3_t2["pagination_complete"] is False
    missing = bundle.ground_truth["targets"]["2"]["changes"]["missing_partial_snapshot_3"]
    assert len(missing) == 4
    assert not set(missing) & set(by_id(s3_t2))
    assert set(missing) <= set(by_id(t2["snapshots"][1]))
    assert set(missing) <= set(by_id(t2["snapshots"][3]))
    # dinyatakan tidak tersedia oleh sumber hanya pada putaran 4, dengan bukti
    gone = bundle.ground_truth["targets"]["1"]["changes"]["confirmed_unavailable"]
    assert len(gone) == 2
    s4 = t1["snapshots"][3]
    assert {c["id"] for c in s4["confirmed_unavailable"]} == {g["id"] for g in gone}
    assert all(c["evidence"] for c in s4["confirmed_unavailable"])
    assert not {g["id"] for g in gone} & set(by_id(s4))
    assert not t1["snapshots"][2].get("confirmed_unavailable")


def test_removed_objects_are_never_parents_of_visible_replies(bundle) -> None:
    for dataset in _x_files(bundle).values():
        for snap in dataset["snapshots"]:
            ids = {o["id"] for o in snap["observations"]}
            for o in snap["observations"]:
                if o["type"] == "reply":
                    assert o["parent"] in ids


def test_same_handle_on_two_platforms_stays_separate(bundle) -> None:
    tiktok = bundle.datasets["tiktok-handle-sama.json"]
    assert tiktok["platform"] == "tiktok"
    shared = bundle.ground_truth["cross_platform"]["shared_handle"]
    tiktok_handles = {o["handle"]: o["actor"] for o in tiktok["snapshots"][0]["observations"]}
    x_handles = {o["handle"]: o["actor"] for d in _x_files(bundle).values() for o in _final(d)}
    assert shared in tiktok_handles and shared in x_handles
    assert tiktok_handles[shared] != x_handles[shared]
    # target TikTok tidak memuat objek X dan sebaliknya
    assert not {o["id"] for o in tiktok["snapshots"][0]["observations"]} & {
        o["id"] for d in _x_files(bundle).values() for o in _final(d)
    }


def test_partial_coverage_account_appears_in_only_one_target(bundle) -> None:
    account = bundle.ground_truth["profile_coverage"]["account"]
    seen = [
        n
        for n, d in enumerate(_x_files(bundle).values(), start=1)
        if any(o["actor"] == account for o in _final(d))
    ]
    assert seen == [1]


def test_nothing_resembles_a_verdict_or_real_identity(bundle) -> None:
    blob = json.dumps([bundle.ground_truth, bundle.datasets], ensure_ascii=False).lower()
    assert "buzzer" not in blob
    assert all(d["name"].startswith("SINTETIS-I2-") for d in bundle.datasets.values())
    assert all(d["source_method"] == "synthetic_fixture" for d in bundle.datasets.values())
