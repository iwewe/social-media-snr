"""WP-3.6: pemindai kebocoran rahasia (tests/tools/secret_scan.py) dan repo ini harus bersih."""

import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import secret_scan as ss  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LONG = "a1B2c3D4e5F6g7H8i9J0"  # 20 karakter, bukan placeholder


def kinds(text: str) -> list[str]:
    return [f.kind for f in ss.scan_text("x.txt", text)]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("-----BEGIN " + "RSA PRIVATE KEY-----", "kunci privat"),
        (f"sessionid={LONG}", "cookie sesi"),
        (f'csrftoken: "{LONG}"', "cookie sesi"),
        (f"auth_token = {LONG}", "cookie sesi"),
        (f"sid={LONG}", "cookie sesi"),
        (f"ct0: {LONG}", "cookie sesi"),
        (f"refresh_token={LONG}", "token akses"),
        (f"oauth_token={LONG}", "token akses"),
        (f"SECRET_KEY = '{LONG}'", "token akses"),
        (f"Set-Cookie: session={LONG}; Path=/", "header Set-Cookie/Cookie"),
        (f"Cookie: tracker={LONG}", "header Set-Cookie/Cookie"),
        (f"Authorization: Bearer {LONG}", "bearer token"),
        (f"access_token={LONG}", "token akses"),
        (f"API_KEY: '{LONG}'", "token akses"),
        ("key " + "AKIA" + "ABCDEFGHIJKLMNOP", "kunci cloud"),
        ("ghp_" + "A" * 36, "kunci cloud"),
        ('{"cook' + 'ies": [{"name": "a"}]}', "dump cookie JSON"),
    ],
)
def test_each_rule_detects_its_kind(text: str, kind: str) -> None:
    assert kinds(text) == [kind]


@pytest.mark.parametrize(
    "text",
    [
        "tidak ada rahasia di sini",
        "sessionid=pendek",  # terlalu pendek untuk nilai sesi
        "password_reset_token_name",
        "sessionid=ci-only-not-a-secret-ci-only",
        "Authorization: Bearer <token-anda-di-sini>",
        "access_token=xxxxxxxxxxxxxxxxxxxxxxxx",
        "api_key = contoh-contoh-contoh-contoh",
        "csrftoken: placeholder-placeholder",
        "sessionid=0123456789abcde",  # 15 karakter: di bawah batas nilai
        '{"cookies": []}',  # kosong bukan dump
    ],
)
def test_harmless_text_and_placeholders_are_ignored(text: str) -> None:
    assert kinds(text) == []


def test_private_key_and_cloud_keys_ignore_the_placeholder_filter() -> None:
    # Kunci privat dan kunci cloud tidak boleh lolos hanya karena memuat kata penampung.
    assert kinds("AKIA" + "EXAMPLEEXAMPLE12") == ["kunci cloud"]
    assert kinds("-----BEGIN " + "PRIVATE KEY----- contoh") == ["kunci privat"]


def test_the_allow_mark_silences_one_line_only() -> None:
    text = f"sessionid={LONG}  # secret-scan: allow\nsessionid={LONG}"
    found = ss.scan_text("x", text)
    assert [f.line for f in found] == [2]


def test_findings_never_contain_the_secret_value() -> None:
    finding = ss.scan_text("x.txt", f"sessionid={LONG}")[0]
    assert LONG not in str(finding) and "x.txt:1" in str(finding)


@pytest.mark.parametrize(
    "name",
    [
        "cookies.txt",
        "data/cookies-x.json",
        "storage_state.json",
        "trace.har",
        "server.pem",
        "id.key",
        ".env",
        "backend/.env.production",
    ],
)
def test_forbidden_file_names_are_flagged(name: str) -> None:
    assert ss.scan_name(name)


@pytest.mark.parametrize("name", [".env.example", "backend/settings.py", "docs/cookies-policy.md"])
def test_ordinary_file_names_are_not_flagged(name: str) -> None:
    assert ss.scan_name(name) == []


def test_scan_file_skips_binary_oversize_and_lockfiles(tmp_path) -> None:
    secret = f"sessionid={LONG}".encode()
    binary = tmp_path / "b.bin"
    binary.write_bytes(b"\0\0" + secret)
    lock = tmp_path / "package-lock.json"
    lock.write_bytes(secret)
    big = tmp_path / "big.txt"
    big.write_bytes(secret + b"\n" + b"x" * (ss.MAX_BYTES + 1))
    plain = tmp_path / "p.txt"
    plain.write_bytes(secret)
    assert ss.scan_file(binary, "b.bin") == []
    assert ss.scan_file(lock, "package-lock.json") == []
    assert ss.scan_file(big, "big.txt") == []
    assert len(ss.scan_file(plain, "p.txt")) == 1


def test_directories_are_scanned_recursively_and_exit_code_reflects_findings(tmp_path, capsys) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "log.txt").write_text(f"Authorization: Bearer {LONG}\n")
    (tmp_path / "ok.txt").write_text("aman\n")
    assert ss.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "log.txt:1: bearer token" in out and "1 temuan" in out and LONG not in out
    assert ss.main([str(tmp_path / "ok.txt")]) == 0


def test_stdin_mode_scans_logs(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"INFO login sessionid={LONG}\n"))
    assert ss.main(["--stdin"]) == 1
    assert "<stdin>:1" in capsys.readouterr().out


def test_this_repository_has_no_leaked_secrets() -> None:
    """Pengaman permanen: berkas yang dilacak git tidak boleh memuat cookie/token/kunci (PRD 13)."""
    if not (ROOT / ".git").exists():
        pytest.skip("bukan checkout git (mis. direktori tes dipasang terpisah)")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "tools" / "secret_scan.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout


def test_tracked_file_names_are_checked_in_a_git_checkout(tmp_path, monkeypatch, capsys) -> None:
    if shutil.which("git") is None:
        pytest.skip("git tidak tersedia")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "cookies.txt").write_text("kosong\n")
    (tmp_path / "ok.md").write_text("aman\n")
    subprocess.run([*git, "-C", str(tmp_path), "add", "-A"], check=True)
    monkeypatch.chdir(tmp_path)
    assert ss.main([]) == 1
    assert "cookies.txt:0: nama berkas terlarang" in capsys.readouterr().out
    # nama yang sama pada mode jalur eksplisit (mis. log) tidak diperiksa sebagai nama
    assert ss.main(["cookies.txt"]) == 0
