"""Impor/periksa/hapus sesi operator pada profil browser nyata (Chromium). Nilai cookie tidak bocor."""

import io
import json
import stat
import sys

import pytest
from collection.browser.session_import import import_session, parse_cookies, read_session_summary
from django.core.management import CommandError, call_command

SECRET = "nilai-rahasia-cookie-1234567890"
COOKIES = [
    {
        "name": "auth_token",
        "value": SECRET,
        "domain": ".x.com",
        "path": "/",
        "secure": True,
        "httpOnly": True,
        "expires": 1_900_000_000,
    },
    {"name": "ct0", "value": SECRET + "-2", "domain": ".x.com", "path": "/", "secure": True},
    {"name": "lain", "value": "v", "domain": ".facebook.com", "path": "/"},
]


@pytest.fixture(autouse=True)
def _roots(settings, tmp_path, browser_ready):
    settings.SNR_EVIDENCE_ROOT = tmp_path / "evidence"
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "evidence").mkdir()


def test_import_writes_only_platform_cookies_into_a_private_profile(tmp_path) -> None:
    kept, foreign = parse_cookies(COOKIES, "x", session_days=7)
    assert foreign == 1
    profile = import_session("x", kept)
    assert profile == tmp_path / "profiles" / "x"
    assert stat.S_IMODE(profile.stat().st_mode) == 0o700
    summary = read_session_summary("x")
    assert summary.accepted == 2 and summary.names == ("auth_token", "ct0")
    assert SECRET not in repr(summary)


def test_status_before_import_reports_no_session() -> None:
    out = io.StringIO()
    call_command("browser_session", "status", "--platform", "x", stdout=out)
    assert "belum ada sesi" in out.getvalue()


def test_command_imports_from_a_file_prints_no_values_and_can_delete_the_source(tmp_path) -> None:
    source = tmp_path / "cookies.json"
    source.write_text(json.dumps(COOKIES))
    out = io.StringIO()
    call_command(
        "browser_session",
        "import",
        "--platform",
        "x",
        "--file",
        str(source),
        "--delete-source",
        stdout=out,
    )
    text = out.getvalue()
    assert "2 cookie" in text and "1 cookie domain lain dibuang" in text and "auth_token" in text
    assert SECRET not in text
    assert not source.exists()
    status = io.StringIO()
    call_command("browser_session", "status", "--platform", "x", stdout=status)
    assert "2 cookie" in status.getvalue() and SECRET not in status.getvalue()


def test_command_imports_from_stdin_and_keeps_a_file_source_by_default(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"cookies": COOKIES})))
    call_command(
        "browser_session", "import", "--platform", "x", "--file", "-", stdout=io.StringIO()
    )
    assert read_session_summary("x").accepted == 2
    source = tmp_path / "keep.json"
    source.write_text(json.dumps(COOKIES))
    call_command(
        "browser_session", "import", "--platform", "x", "--file", str(source), stdout=io.StringIO()
    )
    assert source.exists()


@pytest.mark.parametrize(
    "content", ["{rusak", "[]", '[{"name":"a","value":"b","domain":".facebook.com"}]']
)
def test_command_rejects_bad_files_without_echoing_content(tmp_path, content) -> None:
    source = tmp_path / "bad.json"
    source.write_text(content)
    with pytest.raises(CommandError) as info:
        call_command(
            "browser_session",
            "import",
            "--platform",
            "x",
            "--file",
            str(source),
            stdout=io.StringIO(),
        )
    assert "facebook" not in str(info.value).replace("domain x", "") or "tidak ada cookie" in str(
        info.value
    )
    assert read_session_summary("x").accepted == 0


def test_missing_file_is_a_command_error(tmp_path) -> None:
    with pytest.raises(CommandError):
        call_command(
            "browser_session",
            "import",
            "--platform",
            "x",
            "--file",
            str(tmp_path / "tidak-ada.json"),
        )


def test_clear_empties_the_profile_and_status_confirms(tmp_path) -> None:
    import_session("x", parse_cookies(COOKIES, "x", session_days=7)[0])
    out = io.StringIO()
    call_command("browser_session", "clear", "--platform", "x", stdout=out)
    assert "dihapus" in out.getvalue()
    assert list((tmp_path / "profiles" / "x").iterdir()) == []
    assert read_session_summary("x").accepted == 0


def test_session_cookies_without_days_are_not_persisted_by_chromium(tmp_path) -> None:
    """Dasar keputusan --session-days: cookie sesi hilang saat browser ditutup bila tak diberi umur."""
    import_session("x", parse_cookies(COOKIES, "x", session_days=0)[0])
    assert read_session_summary("x").names == ("auth_token",)
