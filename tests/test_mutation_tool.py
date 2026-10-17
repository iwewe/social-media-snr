"""Alat mutasi (tests/tools/mutate.py) diuji dengan repo mungil dan perintah python biasa (tanpa docker)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import mutate as mt  # noqa: E402

PY = f'"{sys.executable}"'
CHECK = f"{PY} -c \"import sys; sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 1)\""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text("x = 1\n")
    return tmp_path


def spec(command=CHECK, mutations=(), **kw):
    return mt.Spec(command=command, mutations=list(mutations), timeout=kw.pop("timeout", 30), **kw)


def run(repo, mutations, **kw):
    return mt.run_spec(spec(mutations=mutations, **kw), repo, log=lambda *_: None)


def status_of(results):
    return {r.name: r.status for r in results}


def test_a_mutation_the_tests_notice_is_caught(repo) -> None:
    assert status_of(run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")])) == {"a": mt.CAUGHT}


def test_a_mutation_the_tests_miss_is_a_survivor(repo) -> None:
    ignore = f"{PY} -c \"import sys; sys.exit(0)\""
    assert status_of(run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 9")], command=ignore, baseline_command=None)) == {"a": mt.SURVIVED}


def test_the_decision_uses_the_exit_code_not_the_output_text(repo) -> None:
    says_failed_but_passes = f"{PY} -c \"print('1 failed, FAILED'); import sys; sys.exit(0)\""
    says_passed_but_fails_after = (
        f"{PY} -c \"import sys; print('10 passed'); "
        f"sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 1)\""
    )
    assert status_of(run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")], command=says_failed_but_passes)) == {"a": mt.SURVIVED}
    assert status_of(run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")], command=says_passed_but_fails_after)) == {"a": mt.CAUGHT}


def test_a_pattern_that_is_absent_is_an_error_not_a_silent_skip(repo) -> None:
    result = run(repo, [mt.Mutation("a", "m.py", "tidak ada", "y")])[0]
    assert result.status == mt.ERROR and "0x" in result.detail and "harus 1x" in result.detail


def test_a_pattern_that_occurs_twice_is_an_error_too(repo) -> None:
    result = run(repo, [mt.Mutation("a", "m.py", " ", "_")])[0]  # 'x = 1' memuat dua spasi
    assert result.status == mt.ERROR and "2x" in result.detail


def test_a_missing_file_is_an_error(repo) -> None:
    assert run(repo, [mt.Mutation("a", "tidak-ada.py", "x", "y")])[0].status == mt.ERROR


def test_a_red_baseline_aborts_before_mutating_anything(repo) -> None:
    (repo / "m.py").write_text("x = 5\n")
    with pytest.raises(mt.BaselineFailed):
        run(repo, [mt.Mutation("a", "m.py", "x = 5", "x = 6")])
    assert (repo / "m.py").read_text() == "x = 5\n"


def test_exit_code_5_no_tests_collected_is_not_a_catch(repo) -> None:
    cmd = f"{PY} -c \"import sys; sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 5)\""
    assert run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")], command=cmd)[0].status == mt.NO_TESTS


def test_a_hang_is_reported_as_a_timeout_not_a_catch(repo) -> None:
    cmd = f"{PY} -c \"import time, sys; sys.exit(0) if open('m.py').read().strip() == 'x = 1' else time.sleep(20)\""
    results = run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")], command=cmd, timeout=2)
    assert results[0].status == mt.TIMED_OUT


def test_the_file_is_restored_byte_for_byte_after_every_outcome(repo) -> None:
    original = (repo / "m.py").read_bytes()
    run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2"), mt.Mutation("b", "m.py", "nope", "x")])
    assert (repo / "m.py").read_bytes() == original


def test_restore_failure_stops_everything(repo, monkeypatch) -> None:
    monkeypatch.setattr(mt, "_sha", lambda path: "bukan-hash-asli")
    with pytest.raises(mt.RestoreFailed):
        run(repo, [mt.Mutation("a", "m.py", "x = 1", "x = 2")])


def test_equivalent_mutants_are_flagged_and_stale_flags_are_reported(repo) -> None:
    survive = f"{PY} -c \"import sys; sys.exit(0)\""
    results = run(repo, [mt.Mutation("setara", "m.py", "x = 1", "x = 9", equivalent="tidak mengubah perilaku")], command=survive)
    assert results[0].status == mt.EQUIVALENT_SURVIVED
    assert mt.summarize(results)[1] is True
    stale = run(repo, [mt.Mutation("usang", "m.py", "x = 1", "x = 9", equivalent="dulu setara")])
    assert stale[0].status == mt.EQUIVALENT_CAUGHT
    assert mt.summarize(stale)[1] is False  # tanda setara yang usang harus dibersihkan


def test_summary_is_ok_only_when_nothing_needs_attention(repo) -> None:
    ok = [mt.Result("a", mt.CAUGHT), mt.Result("b", mt.EQUIVALENT_SURVIVED)]
    assert mt.summarize(ok)[1] is True
    for bad in (mt.SURVIVED, mt.ERROR, mt.TIMED_OUT, mt.NO_TESTS, mt.EQUIVALENT_CAUGHT):
        assert mt.summarize([*ok, mt.Result("c", bad)])[1] is False, bad


def test_only_filter_selects_by_name(repo) -> None:
    ms = [mt.Mutation("alpha", "m.py", "x = 1", "x = 2"), mt.Mutation("beta", "m.py", "x = 1", "x = 3")]
    results = mt.run_spec(spec(mutations=ms), repo, only="bet", log=lambda *_: None)
    assert [r.name for r in results] == ["beta"]


def write_spec(path: Path, mutations: str, command: str = CHECK) -> Path:
    path.write_text(f"from mutate import Mutation\nCOMMAND = {command!r}\nTIMEOUT = 30\nMUTATIONS = [{mutations}]\n")
    return path


def test_spec_file_loading_and_main_exit_codes(repo, tmp_path, monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(Path(mt.__file__).parent))
    good = write_spec(tmp_path / "good.py", 'Mutation("a", "m.py", "x = 1", "x = 2")')
    assert mt.main([str(good), "--root", str(repo), "--json", str(tmp_path / "out.json")]) == 0
    assert json.loads((tmp_path / "out.json").read_text())[0]["status"] == mt.CAUGHT
    bad_pattern = write_spec(tmp_path / "bad.py", 'Mutation("a", "m.py", "nope", "x")')
    assert mt.main([str(bad_pattern), "--root", str(repo)]) == 1
    (repo / "m.py").write_text("x = 5\n")
    assert mt.main([str(good), "--root", str(repo)]) == 2  # baseline merah


# --- slot terisolasi dan paralel ------------------------------------------------------------------


def isolated(repo, mutations, jobs=3, command=CHECK, **kw):
    return mt.run_spec(
        spec(command=command, mutations=mutations, **kw), repo, jobs=jobs, in_place=False, log=lambda *_: None
    )


MUTS = [mt.Mutation(f"m{i}", "m.py", "x = 1", f"x = {i + 2}") for i in range(6)]


def test_isolated_mode_never_touches_the_origin_repo(repo, tmp_path) -> None:
    side = tmp_path / "asal-dilihat.txt"
    cmd = (
        f"{PY} -c \"import sys; open(r'{side}','a').write(open(r'{{origin}}/m.py').read().strip()+'\\n'); "
        "sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 1)\""
    )
    results = isolated(repo, MUTS, command=cmd)
    assert {r.status for r in results} == {mt.CAUGHT}  # mutasi terjadi di salinan
    assert set(side.read_text().split("\n")) - {""} == {"x = 1"}  # repo asal tidak pernah termutasi
    assert (repo / "m.py").read_text() == "x = 1\n"


def test_isolated_results_match_in_place_results(repo) -> None:
    mixed = [*MUTS[:2], mt.Mutation("hilang", "m.py", "tidak ada", "y")]
    in_place = status_of(run(repo, mixed))
    assert status_of(isolated(repo, mixed, jobs=3)) == in_place == {
        "m0": mt.CAUGHT, "m1": mt.CAUGHT, "hilang": mt.ERROR}


def test_placeholders_are_expanded_and_every_slot_is_used(repo, tmp_path) -> None:
    log = tmp_path / "slot.txt"
    cmd = (
        f"{PY} -c \"import time, sys; open(r'{log}','a').write('{{job}}|'+r'{{root}}'+'\\n'); time.sleep(0.4); "
        "sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 1)\""
    )
    isolated(repo, MUTS, jobs=3, command=cmd)
    lines = [ln for ln in log.read_text().splitlines() if ln]
    assert {ln.split("|")[0] for ln in lines} == {"0", "1", "2"}
    assert all("slot" in ln.split("|")[1] and str(repo) not in ln.split("|")[1] for ln in lines)


def test_mutations_really_run_concurrently(repo, tmp_path) -> None:
    stamps = tmp_path / "waktu.txt"
    cmd = (
        f"{PY} -c \"import time, sys; a=time.time(); time.sleep(0.6); "
        f"open(r'{stamps}','a').write(f'{{a}} {{time.time()}}\\n'); "
        "sys.exit(0 if open('m.py').read().strip() == 'x = 1' else 1)\""
    )
    isolated(repo, MUTS[:3], jobs=3, command=cmd)
    spans = sorted(tuple(map(float, ln.split())) for ln in stamps.read_text().splitlines() if ln)
    # Setelah baseline (3 baris pertama), tiga mutasi harus tumpang tindih; jumlah baris = 3 baseline + 3 mutasi.
    mutation_spans = spans[-3:] if len(spans) >= 6 else spans
    overlap = max(s[0] for s in mutation_spans) < min(s[1] for s in mutation_spans)
    assert len(spans) == 6 and overlap


def test_slot_copy_skips_heavy_directories_and_links_node_modules(tmp_path) -> None:
    origin, dest = tmp_path / "asal", tmp_path / "salinan"
    for rel in (".git/x", ".venv/y", "backend/__pycache__/z", "snr-data/d", "frontend/dist/b", "backend/app.py"):
        f = origin / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("isi")
    (origin / "frontend" / "node_modules").mkdir()
    (origin / "frontend" / "node_modules" / "paket").write_text("p")
    mt.make_slot(origin, dest)
    assert (dest / "backend" / "app.py").is_file()
    for rel in (".git", ".venv", "backend/__pycache__", "snr-data", "frontend/dist"):
        assert not (dest / rel).exists(), rel
    link = dest / "frontend" / "node_modules"
    assert link.is_symlink() and (link / "paket").read_text() == "p"


def test_a_red_baseline_on_any_slot_aborts(repo) -> None:
    cmd = f"{PY} -c \"import sys; sys.exit(0 if '{{job}}' != '1' else 1)\""
    with pytest.raises(mt.BaselineFailed, match="slot 1"):
        isolated(repo, MUTS, command=cmd)


def test_temporary_slots_are_removed_afterwards(repo, tmp_path, monkeypatch) -> None:
    import tempfile

    made = []
    real = tempfile.mkdtemp
    monkeypatch.setattr(tempfile, "mkdtemp", lambda **kw: made.append(real(dir=tmp_path, **kw)) or made[-1])
    isolated(repo, MUTS[:2], jobs=2)
    assert made and not Path(made[0]).exists()
