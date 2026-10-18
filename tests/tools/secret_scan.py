"""Pemindai kebocoran rahasia (WP-3.6; PRD bagian 13): cookie, token, kunci privat pada repo atau log.

Pemakaian:
  python tests/tools/secret_scan.py                  # semua berkas yang dilacak git
  python tests/tools/secret_scan.py PATH [PATH...]   # berkas/direktori tertentu (mis. log)
  docker compose logs --no-color | python tests/tools/secret_scan.py --stdin
Kode keluar 1 bila ada temuan. Temuan dicetak TANPA nilai rahasia (hanya jalur, baris, jenis).
Baris yang sengaja berisi nilai contoh dapat ditandai `secret-scan: allow`. Nilai penampung
(`ci-only-not-a-secret`, `uji`, `xxx`, `<...>`) diabaikan.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOW_MARK = "secret-scan: allow"
MAX_BYTES = 2_000_000
SKIP_NAMES = {"package-lock.json", "uv.lock"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pdf", ".svg"}
FORBIDDEN_NAMES = (
    re.compile(r"(^|/)cookies[^/]*\.(txt|json)$", re.I),
    re.compile(r"(^|/)storage_state[^/]*\.json$", re.I),
    re.compile(r"\.(har|pem|key|p12)$", re.I),
    re.compile(r"(^|/)\.env($|\.(?!example$))", re.I),
)
PLACEHOLDER = re.compile(
    r"(ci-only|not-a-secret|placeholder|example|contoh|dummy|fake|palsu|x{4,}|\*{3,}|<[^>]+>|\.\.\.)",
    re.I,
)
VALUE = r"[A-Za-z0-9._~+/=%-]{16,}"
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("kunci privat", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("cookie sesi", re.compile(rf"\b(sessionid|csrftoken|auth_token|ct0|sid)\s*[=:]\s*['\"]?({VALUE})", re.I)),
    ("header Set-Cookie/Cookie", re.compile(rf"\b(set-cookie|cookie)\s*:\s*[A-Za-z_.-]+=({VALUE})", re.I)),
    ("bearer token", re.compile(rf"\bbearer\s+({VALUE})", re.I)),
    ("token akses", re.compile(rf"\b(access_token|refresh_token|oauth_token|api[_-]?key|secret[_-]?key)\b\s*[=:]\s*['\"]?({VALUE})", re.I)),
    ("kunci cloud", re.compile(r"\b(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|xox[baprs]-[A-Za-z0-9-]{10,})\b")),
    ("dump cookie JSON", re.compile(r"\"cookies\"\s*:\s*\[\s*\{")),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind} (nilai disembunyikan)"


def scan_text(path: str, text: str) -> list[Finding]:
    found: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARK in line:
            continue
        for kind, rule in RULES:
            match = rule.search(line)
            if match is None:
                continue
            secret = match.group(match.lastindex) if match.lastindex else match.group(0)
            if kind not in ("kunci privat", "dump cookie JSON", "kunci cloud") and PLACEHOLDER.search(secret):
                continue
            found.append(Finding(path, number, kind))
            break
    return found


def scan_name(path: str) -> list[Finding]:
    return [Finding(path, 0, "nama berkas terlarang (rahasia/kredensial tidak boleh dilacak)")
            for rule in FORBIDDEN_NAMES if rule.search(path)][:1]


def scan_file(path: Path, display: str) -> list[Finding]:
    if path.name in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
        return []
    if path.stat().st_size > MAX_BYTES:
        return []
    data = path.read_bytes()
    if b"\0" in data[:4096]:
        return []
    return scan_text(display, data.decode("utf-8", errors="replace"))


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode()
    return [root / name for name in out.split("\0") if name]


def expand(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        files.extend(sorted(q for q in p.rglob("*") if q.is_file()) if p.is_dir() else [p])
    return files


def main(argv: list[str]) -> int:
    findings: list[Finding] = []
    if argv == ["--stdin"]:
        findings = scan_text("<stdin>", sys.stdin.read())
    else:
        root = Path.cwd()
        files = expand(argv) if argv else tracked_files(root)
        for f in files:
            display = str(f.relative_to(root)) if f.is_absolute() and root in f.parents else str(f)
            if not argv:
                findings += scan_name(display)
            findings += scan_file(f, display)
    for finding in findings:
        print(finding)
    print(f"{len(findings)} temuan")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
