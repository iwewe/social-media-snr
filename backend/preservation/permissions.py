"""Pemeriksaan izin berkas data lokal (WP-3.6b; PRD bagian 13).

Kebijakan (sejalan dengan `storage.py`): bukti read-only dan tertutup bagi "other"
(direktori tanpa bit other; berkas tanpa bit tulis maupun other); sesi browser (kredensial)
hanya untuk pemilik (tanpa bit grup/other); backup tanpa bit grup/other. Symlink tidak
diperbolehkan di dalam akar data. Pemeriksaan hanya MELAPORKAN, tidak mengubah izin.
"""

import os
import stat
from pathlib import Path

OTHER = stat.S_IRWXO
GROUP_OTHER = stat.S_IRWXG | stat.S_IRWXO
WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def _walk(root: Path) -> list[tuple[Path, bool]]:
    entries: list[tuple[Path, bool]] = []
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            entries.append((Path(base, name), True))
        for name in files:
            entries.append((Path(base, name), False))
    return entries


def check_evidence(root: Path) -> list[str]:
    if not root.exists():
        return []
    problems: list[str] = []
    if _mode(root) & OTHER:
        problems.append(f"akar evidence dapat diakses 'other' (mode {_mode(root):o})")
    for path, is_dir in _walk(root):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            problems.append(f"evidence/{rel}: symlink tidak diperbolehkan")
            continue
        mode = _mode(path)
        if is_dir:
            if mode & OTHER:
                problems.append(f"evidence/{rel}/: direktori dapat diakses 'other' ({mode:o})")
        else:
            if mode & WRITE:
                problems.append(f"evidence/{rel}: berkas bukti dapat ditulis ({mode:o})")
            if mode & OTHER:
                problems.append(f"evidence/{rel}: berkas bukti dapat diakses 'other' ({mode:o})")
    return problems


def check_private_tree(root: Path, label: str) -> list[str]:
    """Pohon yang hanya boleh diakses pemilik (sesi browser, backup)."""
    if not root.exists():
        return []
    problems: list[str] = []
    if _mode(root) & GROUP_OTHER:
        problems.append(f"{label}: akar dapat diakses grup/other (mode {_mode(root):o})")
    for path, _is_dir in _walk(root):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            problems.append(f"{label}/{rel}: symlink tidak diperbolehkan")
        elif _mode(path) & GROUP_OTHER:
            problems.append(f"{label}/{rel}: dapat diakses grup/other ({_mode(path):o})")
    return problems


def check_all(evidence: Path, profiles: Path, backup: Path | None = None) -> list[str]:
    problems = check_evidence(evidence)
    problems += check_private_tree(profiles, "browser-profiles")
    if backup is not None:
        problems += check_private_tree(backup, "backup")
    return problems
