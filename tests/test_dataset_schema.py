"""WP-1.7: validasi format dataset uji/impor. Pesan galat memuat lokasi, bukan isi."""

import copy
import json
from pathlib import Path

import pytest
from collection.datasets import DatasetError, load_dataset_file, parse_dataset

SAMPLES = Path(__file__).resolve().parents[1] / "datasets" / "sample"
SECRET_TEXT = "ISI-RAHASIA-JANGAN-BOCOR"

REPLY = {"type": "reply", "id": "2", "actor": "a2", "parent": "1", "text": SECRET_TEXT,
         "published_at": "2026-10-15T08:10:00Z"}
POST = {"type": "post", "id": "1", "actor": "a1", "text": "awal", "published_at": "2026-10-15T08:00:00Z"}


def good() -> dict:
    return copy.deepcopy({
        "schema_version": 1, "name": "uji", "platform": "x",
        "target_url": "https://x.com/u/status/1", "source_method": "synthetic_fixture",
        "snapshots": [{"observed_at": "2026-10-16T01:00:00Z", "outcome": "COMPLETED",
                       "pagination_complete": True, "displayed_count": 1,
                       "observations": [POST, REPLY]}],
    })


def snap(d: dict) -> dict:
    return d["snapshots"][0]


def test_valid_dataset_parses_and_normalises_the_url() -> None:
    d = good()
    d["target_url"] = "https://twitter.com/u/status/1?s=20"
    ds = parse_dataset(d)
    assert ds.target_url == "https://x.com/u/status/1" and ds.platform.value == "x"
    assert len(ds.snapshots[0].observations) == 2


@pytest.mark.parametrize("path", sorted(SAMPLES.glob("*.json")), ids=lambda p: p.name)
def test_every_shipped_sample_dataset_is_valid(path) -> None:
    assert load_dataset_file(path).snapshots


def test_sample_directory_is_not_empty() -> None:
    assert len(list(SAMPLES.glob("*.json"))) >= 3


def mutate(fn):
    d = good()
    fn(d)
    return d


BAD = {
    "kunci tidak dikenal di akar": lambda d: d.update(extra=1),
    "kunci wajib hilang": lambda d: d.pop("name"),
    "versi skema lain": lambda d: d.update(schema_version=2),
    "versi skema bool": lambda d: d.update(schema_version=True),
    "platform tak dikenal": lambda d: d.update(platform="myspace"),
    "URL platform lain": lambda d: d.update(target_url="https://tiktok.com/@u/video/1"),
    "URL berkredensial": lambda d: d.update(target_url="https://a:b@x.com/u/status/1"),
    "source_method nyata dilarang": lambda d: d.update(source_method="official_api"),
    "source_method pengamatan dilarang": lambda d: d.update(source_method="authorized_observation"),
    "tanpa snapshot": lambda d: d.update(snapshots=[]),
    "snapshots bukan daftar": lambda d: d.update(snapshots={}),
    "waktu tanpa zona": lambda d: snap(d).update(observed_at="2026-10-16T01:00:00"),
    "waktu sampah": lambda d: snap(d).update(observed_at="kemarin"),
    "outcome tak dikenal": lambda d: snap(d).update(outcome="OK"),
    "paginasi hilang": lambda d: snap(d).pop("pagination_complete"),
    "paginasi bukan bool": lambda d: snap(d).update(pagination_complete="ya"),
    "COMPLETED tanpa paginasi lengkap": lambda d: snap(d).update(pagination_complete=None),
    "COMPLETED dengan limitation blocking": lambda d: snap(d).update(
        limitations=[{"code": "PARSE_FAILED", "message": "x"}]),
    "displayed negatif": lambda d: snap(d).update(displayed_count=-1),
    "displayed bool": lambda d: snap(d).update(displayed_count=True),
    "ACCESS_RESTRICTED membawa observasi": lambda d: snap(d).update(
        outcome="ACCESS_RESTRICTED", pagination_complete=None,
        limitations=[{"code": "ACCESS_RESTRICTED", "message": "x"}]),
    "jenis objek tak dikenal": lambda d: snap(d)["observations"][0].update(type="story"),
    "balasan tanpa induk": lambda d: snap(d)["observations"][1].update(parent=None),
    "post dengan induk": lambda d: snap(d)["observations"][0].update(parent="9"),
    "kunci observasi tak dikenal": lambda d: snap(d)["observations"][1].update(likes=3),
    "published_at tanpa zona": lambda d: snap(d)["observations"][1].update(published_at="2026-10-15T08:10:00"),
    "text bukan string": lambda d: snap(d)["observations"][1].update(text=5),
    "mentions bukan daftar": lambda d: snap(d)["observations"][1].update(mentions="a1"),
    "limitation tanpa pesan": lambda d: snap(d).update(limitations=[{"code": "TIMEOUT", "message": " "}]),
    "limitation kode tak dikenal": lambda d: snap(d).update(limitations=[{"code": "X", "message": "m"}]),
    "artefak manifest dilarang": lambda d: snap(d).update(artifacts=[
        {"kind": "manifest", "filename": "m.json", "content_type": "application/json", "text": "{}"}]),
    "artefak nama berdirektori": lambda d: snap(d).update(artifacts=[
        {"kind": "dom_snapshot", "filename": "../x.html", "content_type": "text/html", "text": "x"}]),
    "unavailable tanpa evidence": lambda d: snap(d).update(confirmed_unavailable=[{"id": "2", "evidence": ""}]),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_invalid_dataset_is_rejected_with_a_dataset_error(name) -> None:
    with pytest.raises(DatasetError):
        parse_dataset(mutate(BAD[name]))


def test_error_messages_locate_the_problem_but_never_echo_content() -> None:
    d = good()
    snap(d)["observations"][1]["parent"] = None  # balasan tanpa induk, teks memuat SECRET_TEXT
    snap(d)["observations"][1]["likes"] = SECRET_TEXT
    with pytest.raises(DatasetError) as exc:
        parse_dataset(d, label="berkas.json")
    msg = str(exc.value)
    assert "berkas.json.snapshots[0].observations[1]" in msg and SECRET_TEXT not in msg


def test_contract_violations_are_reported_with_the_snapshot_location() -> None:
    d = good()
    snap(d)["observations"][1]["parent"] = None
    with pytest.raises(DatasetError, match=r"snapshots\[0\].*melanggar kontrak"):
        parse_dataset(d)


def test_snapshot_location_identifies_the_failing_snapshot() -> None:
    d = good()
    d["snapshots"].append(copy.deepcopy(snap(d)))
    d["snapshots"][1]["outcome"] = "NOPE"
    with pytest.raises(DatasetError, match=r"snapshots\[1\]\.outcome"):
        parse_dataset(d)


def test_unknown_key_message_truncates_long_key_names() -> None:
    d = good()
    d["k" * 500] = 1
    with pytest.raises(DatasetError) as exc:
        parse_dataset(d)
    assert len(str(exc.value)) < 200


def test_null_identity_is_allowed_for_needs_verification_cases() -> None:
    d = good()
    snap(d)["observations"][1].update(actor=None, needs_verification=True)
    assert parse_dataset(d).snapshots[0].observations[1].actor is None


# --- berkas -----------------------------------------------------------------------------------


def test_load_rejects_non_json_and_does_not_echo_file_content(tmp_path) -> None:
    f = tmp_path / "rusak.json"
    f.write_text("{ " + SECRET_TEXT)
    with pytest.raises(DatasetError) as exc:
        load_dataset_file(f)
    assert "rusak.json" in str(exc.value) and SECRET_TEXT not in str(exc.value)


def test_load_rejects_invalid_utf8(tmp_path) -> None:
    f = tmp_path / "bin.json"
    f.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(DatasetError, match="bin.json"):
        load_dataset_file(f)


def test_load_rejects_oversize_files(tmp_path, monkeypatch) -> None:
    import collection.datasets.dataset as mod

    monkeypatch.setattr(mod, "MAX_DATASET_BYTES", 10)
    f = tmp_path / "besar.json"
    f.write_text(json.dumps(good()))
    with pytest.raises(DatasetError, match="melebihi batas"):
        load_dataset_file(f)


def test_load_rejects_top_level_non_object(tmp_path) -> None:
    f = tmp_path / "daftar.json"
    f.write_text("[1, 2]")
    with pytest.raises(DatasetError, match="objek JSON"):
        load_dataset_file(f)


def test_naive_timestamps_are_rejected_by_the_schema_with_a_clear_reason() -> None:
    d = good()
    snap(d)["observed_at"] = "2026-10-16T01:00:00"
    with pytest.raises(DatasetError, match=r"snapshots\[0\]\.observed_at: .*zona waktu"):
        parse_dataset(d)


def test_contract_violation_messages_do_not_echo_observation_content() -> None:
    d = good()
    snap(d)["observations"][1]["parent"] = None  # melanggar kontrak; teks memuat SECRET_TEXT
    with pytest.raises(DatasetError) as exc:
        parse_dataset(d)
    assert SECRET_TEXT not in str(exc.value) and "melanggar kontrak" in str(exc.value)
