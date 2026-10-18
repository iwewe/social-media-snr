"""WP-3.6b: pemeriksaan izin berkas data lokal."""

import os
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from preservation import permissions as perm
from preservation.storage import write_new


@pytest.fixture
def roots(tmp_path, settings):
    evidence = tmp_path / "evidence"
    profiles = tmp_path / "profiles"
    evidence.mkdir(mode=0o750)
    profiles.mkdir(mode=0o700)
    evidence.chmod(0o750)
    profiles.chmod(0o700)
    settings.SNR_EVIDENCE_ROOT = evidence
    settings.SNR_BROWSER_PROFILES_ROOT = profiles
    return evidence, profiles


def test_files_written_by_the_application_satisfy_the_policy(roots) -> None:
    evidence, profiles = roots
    write_new("run1/layar.png", b"data")
    assert perm.check_all(evidence, profiles) == []


def test_missing_roots_are_not_a_problem(tmp_path) -> None:
    assert perm.check_all(tmp_path / "x", tmp_path / "y", tmp_path / "z") == []


def test_world_accessible_evidence_root_and_directories_are_reported(roots) -> None:
    evidence, profiles = roots
    write_new("run1/layar.png", b"data")
    evidence.chmod(0o755)
    (evidence / "run1").chmod(0o751)
    problems = perm.check_all(evidence, profiles)
    assert any("akar evidence dapat diakses 'other'" in p for p in problems)
    assert any("evidence/run1/: direktori dapat diakses 'other'" in p for p in problems)


def test_writable_or_world_readable_evidence_files_are_reported(roots) -> None:
    evidence, profiles = roots
    write_new("run1/a.bin", b"a")
    write_new("run1/b.bin", b"b")
    (evidence / "run1" / "a.bin").chmod(0o640)
    (evidence / "run1" / "b.bin").chmod(0o444)
    problems = perm.check_all(evidence, profiles)
    assert any("a.bin: berkas bukti dapat ditulis" in p for p in problems)
    assert any("b.bin: berkas bukti dapat diakses 'other'" in p for p in problems)
    assert not any("b.bin: berkas bukti dapat ditulis" in p for p in problems)


def test_symlinks_inside_the_evidence_root_are_reported(roots, tmp_path) -> None:
    evidence, profiles = roots
    outside = tmp_path / "luar.txt"
    outside.write_text("x")
    os.symlink(outside, evidence / "tautan")
    problems = perm.check_all(evidence, profiles)
    assert any("evidence/tautan: symlink tidak diperbolehkan" in p for p in problems)


def test_browser_profiles_must_be_owner_only(roots) -> None:
    evidence, profiles = roots
    (profiles / "x").mkdir(mode=0o700)
    cookie = profiles / "x" / "Cookies"
    cookie.write_text("rahasia")
    cookie.chmod(0o640)
    problems = perm.check_all(evidence, profiles)
    assert any("browser-profiles/x/Cookies: dapat diakses grup/other" in p for p in problems)
    profiles.chmod(0o750)
    assert any(
        "browser-profiles: akar dapat diakses grup/other" in p
        for p in perm.check_all(evidence, profiles)
    )


def test_backup_directory_must_be_owner_only(roots, tmp_path) -> None:
    evidence, profiles = roots
    backup = tmp_path / "backup"
    backup.mkdir(mode=0o700)
    (backup / "db.dump").write_text("x")
    (backup / "db.dump").chmod(0o600)
    assert perm.check_all(evidence, profiles, backup) == []
    (backup / "db.dump").chmod(0o644)
    assert any("backup/db.dump" in p for p in perm.check_all(evidence, profiles, backup))
    assert perm.check_all(evidence, profiles) == []  # tanpa --backup-dir tidak diperiksa


def test_command_reports_and_fails_on_problems_and_passes_when_clean(roots, tmp_path) -> None:
    evidence, _ = roots
    write_new("run1/a.bin", b"a")
    out = StringIO()
    call_command("check_data_permissions", stdout=out)
    assert "sesuai kebijakan" in out.getvalue()
    (evidence / "run1" / "a.bin").chmod(0o660)
    err = StringIO()
    with pytest.raises(CommandError, match="1 masalah"):
        call_command("check_data_permissions", stdout=StringIO(), stderr=err)
    assert "MASALAH:" in err.getvalue() and "a.bin" in err.getvalue()
    backup = tmp_path / "b"
    backup.mkdir(mode=0o755)
    backup.chmod(0o755)
    (evidence / "run1" / "a.bin").chmod(0o440)
    with pytest.raises(CommandError):
        call_command(
            "check_data_permissions",
            "--backup-dir",
            str(backup),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_each_write_bit_and_each_non_owner_bit_is_detected_individually(roots) -> None:
    evidence, profiles = roots
    for name in ("g.bin", "o.bin", "ok.bin", "ro.bin"):
        write_new(f"run1/{name}", b"x")
    (evidence / "run1" / "g.bin").chmod(0o420)  # hanya tulis grup
    (evidence / "run1" / "o.bin").chmod(0o402)  # hanya tulis other
    (evidence / "run1" / "ro.bin").chmod(0o400)  # hanya pemilik baca: sah
    problems = perm.check_all(evidence, profiles)
    assert any("g.bin: berkas bukti dapat ditulis" in p for p in problems)
    assert any("o.bin: berkas bukti dapat ditulis" in p for p in problems)
    assert not any("ok.bin" in p or "ro.bin" in p for p in problems)


def test_private_trees_flag_group_only_and_other_only_access_and_symlinks(roots, tmp_path) -> None:
    evidence, profiles = roots
    (profiles / "grup").write_text("x")
    (profiles / "grup").chmod(0o640)  # hanya grup
    (profiles / "lain").write_text("x")
    (profiles / "lain").chmod(0o604)  # hanya other
    os.symlink(tmp_path, profiles / "tautan")
    problems = perm.check_all(evidence, profiles)
    assert any("browser-profiles/grup: dapat diakses grup/other" in p for p in problems)
    assert any("browser-profiles/lain: dapat diakses grup/other" in p for p in problems)
    assert any("browser-profiles/tautan: symlink tidak diperbolehkan" in p for p in problems)
