"""WP-0.6: pemisahan evidence vs sesi browser (PRD bagian 10 dan 13)."""

from pathlib import Path

import pytest
from django.core.checks import run_checks
from preservation.checks import check_storage_roots
from preservation.exports import ensure_exportable
from preservation.storage import PathNotAllowed


@pytest.fixture
def roots(tmp_path: Path, settings) -> Path:
    evidence = tmp_path / "evidence"
    profiles = tmp_path / "browser-profiles"
    (evidence / "run-1").mkdir(parents=True)
    (profiles / "Default").mkdir(parents=True)
    settings.SNR_EVIDENCE_ROOT = evidence
    settings.SNR_BROWSER_PROFILES_ROOT = profiles
    return tmp_path


# --- ekspor / arsip -------------------------------------------------------------------------


def test_evidence_file_is_exportable(roots: Path) -> None:
    f = roots / "evidence" / "run-1" / "capture.html"
    f.write_text("x")
    assert ensure_exportable(f) == f.resolve()
    assert ensure_exportable(str(f)) == f.resolve()


def test_browser_profile_files_are_never_exportable(roots: Path) -> None:
    cookies = roots / "browser-profiles" / "Default" / "Cookies"
    cookies.write_text("rahasia")
    with pytest.raises(PathNotAllowed, match="Sesi browser"):
        ensure_exportable(cookies)
    with pytest.raises(PathNotAllowed):
        ensure_exportable(roots / "browser-profiles")


def test_traversal_from_evidence_into_profiles_is_rejected(roots: Path) -> None:
    cookies = roots / "browser-profiles" / "Default" / "Cookies"
    cookies.write_text("rahasia")
    sneaky = roots / "evidence" / "run-1" / ".." / ".." / "browser-profiles" / "Default" / "Cookies"
    with pytest.raises(PathNotAllowed):
        ensure_exportable(sneaky)


def test_symlink_in_evidence_pointing_to_profiles_is_rejected(roots: Path) -> None:
    cookies = roots / "browser-profiles" / "Default" / "Cookies"
    cookies.write_text("rahasia")
    link = roots / "evidence" / "run-1" / "tautan"
    link.symlink_to(cookies)
    with pytest.raises(PathNotAllowed):
        ensure_exportable(link)


@pytest.mark.parametrize("where", ["luar.txt", "evidence"])
def test_paths_outside_evidence_or_the_root_itself_are_rejected(roots: Path, where: str) -> None:
    target = roots / where
    target.touch() if where.endswith(".txt") else None
    with pytest.raises(PathNotAllowed):
        ensure_exportable(target)


# --- system check ---------------------------------------------------------------------------


def codes(messages) -> list[str]:
    return [m.id for m in messages]


def test_default_configuration_passes_the_check(roots: Path) -> None:
    assert check_storage_roots(None) == []


def test_check_is_registered_with_django(roots: Path, settings) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = settings.SNR_EVIDENCE_ROOT
    assert "snr.E002" in codes(run_checks())


def test_same_root_is_an_error(roots: Path, settings) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = settings.SNR_EVIDENCE_ROOT
    assert codes(check_storage_roots(None)) == ["snr.E002"]


def test_profiles_nested_inside_evidence_is_an_error(roots: Path, settings) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = settings.SNR_EVIDENCE_ROOT / "profil"
    assert codes(check_storage_roots(None)) == ["snr.E002"]


def test_evidence_nested_inside_profiles_is_an_error(roots: Path, settings) -> None:
    settings.SNR_EVIDENCE_ROOT = settings.SNR_BROWSER_PROFILES_ROOT / "bukti"
    assert codes(check_storage_roots(None)) == ["snr.E002"]


def test_nesting_via_symlink_is_detected(roots: Path, settings) -> None:
    alias = roots / "alias-evidence"
    alias.symlink_to(settings.SNR_EVIDENCE_ROOT, target_is_directory=True)
    settings.SNR_BROWSER_PROFILES_ROOT = alias / "profil"
    assert codes(check_storage_roots(None)) == ["snr.E002"]


def test_relative_roots_are_an_error(roots: Path, settings) -> None:
    settings.SNR_EVIDENCE_ROOT = Path("evidence")
    assert "snr.E001" in codes(check_storage_roots(None))
