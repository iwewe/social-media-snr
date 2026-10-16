"""Satu-satunya jalur menulis berkas bukti (FR-037, FR-038, FR-039; PRD bagian 10).

Aturan yang dijaga:
- Tidak pernah menimpa: berkas ditulis ke berkas sementara lalu di-`link` ke nama akhir. `link`
  gagal bila nama sudah ada dan atomik, sehingga dua penulis bersamaan tidak bisa saling menimpa
  dan pembaca tidak pernah melihat berkas setengah jadi.
- Jalur hanya relatif terhadap akar evidence; traversal (`..`), jalur absolut, symlink keluar akar,
  dan jalur di bawah akar sesi browser ditolak.
- SHA-256 dihitung selagi menulis (streaming). Hash hanya membuktikan berkas tidak berubah sejak
  di-hash; tidak membuktikan konten platform autentik (PRD bagian 10).
- Berkas dibuat baca-saja.

Detail manifest, provenance, dan penyaringan rahasia ada pada WP-1.5.
"""

import hashlib
import os
import stat
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from django.conf import settings

MAX_COMPONENT_LENGTH = 255
MAX_PATH_LENGTH = 1024
CHUNK_SIZE = 1024 * 1024
FILE_MODE = 0o440
DIR_MODE = 0o750


class EvidenceStorageError(Exception):
    """Basis galat penyimpanan bukti."""


class OverwriteRefused(EvidenceStorageError):
    """Berkas dengan nama itu sudah ada; bukti tidak boleh ditimpa (FR-039)."""


class PathNotAllowed(EvidenceStorageError):
    """Jalur tidak diizinkan (traversal, absolut, keluar akar, atau area sesi browser)."""


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    size: int
    sha256: str


def evidence_root() -> Path:
    return Path(settings.SNR_EVIDENCE_ROOT)


def browser_profiles_root() -> Path:
    return Path(settings.SNR_BROWSER_PROFILES_ROOT)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def validate_relative_path(relative_path: str) -> PurePosixPath:
    """Validasi bentuk jalur relatif; tidak menyentuh filesystem."""
    if not isinstance(relative_path, str) or not relative_path:
        raise PathNotAllowed("Jalur berkas kosong.")
    if "\x00" in relative_path or "\\" in relative_path:
        raise PathNotAllowed("Jalur berkas memuat karakter terlarang.")
    if len(relative_path) > MAX_PATH_LENGTH:
        raise PathNotAllowed("Jalur berkas terlalu panjang.")
    if relative_path.startswith("/"):
        raise PathNotAllowed("Jalur absolut tidak diizinkan.")
    parts = relative_path.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise PathNotAllowed("Jalur berkas memuat komponen terlarang ('', '.', atau '..').")
        if len(part) > MAX_COMPONENT_LENGTH:
            raise PathNotAllowed("Nama komponen jalur terlalu panjang.")
    return PurePosixPath(*parts)


def resolve_inside_evidence(relative_path: str) -> Path:
    """Jalur absolut tepercaya di dalam akar evidence, atau raise PathNotAllowed.

    Symlink pada komponen mana pun diselesaikan dulu; hasilnya harus tetap di dalam akar evidence
    dan tidak di dalam akar sesi browser.
    """
    rel = validate_relative_path(relative_path)
    root = evidence_root().resolve()
    target = (root / rel).resolve()
    if not _is_within(target, root) or target == root:
        raise PathNotAllowed("Jalur berada di luar akar evidence.")
    if _is_within(target, browser_profiles_root().resolve()):
        raise PathNotAllowed("Sesi browser tidak boleh diperlakukan sebagai bukti.")
    return target


def _as_chunks(data: bytes | Iterable[bytes]) -> Iterable[bytes]:
    if isinstance(data, bytes | bytearray | memoryview):
        raw = bytes(data)
        return [raw[i : i + CHUNK_SIZE] for i in range(0, len(raw), CHUNK_SIZE)]
    return data


def _ensure_dirs(directory: Path, root: Path) -> None:
    """Buat direktori yang belum ada di bawah `root`, masing-masing dengan mode DIR_MODE.

    Path.mkdir(parents=True, mode=...) hanya memakai `mode` untuk komponen terakhir; induknya
    mengikuti umask (mis. 0o755). Karena itu tiap komponen dibuat satu per satu.
    """
    current = root
    for part in directory.relative_to(root).parts:
        current = current / part
        try:
            os.mkdir(current, DIR_MODE)
            os.chmod(current, DIR_MODE)  # umask dapat melonggarkan atau mengetatkan mode awal
        except FileExistsError:
            if not current.is_dir():
                raise OverwriteRefused(f"Bukan direktori: {current.name}") from None


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(relative_path: str, data: bytes | Iterable[bytes]) -> StoredFile:
    """Tulis berkas bukti baru. Raise OverwriteRefused bila nama sudah ada."""
    target = resolve_inside_evidence(relative_path)
    parent = target.parent
    root = evidence_root().resolve()
    _ensure_dirs(parent, root)
    # Setelah pembuatan, pastikan parent tetap di dalam akar evidence (mis. bukan symlink keluar).
    if not _is_within(parent.resolve(), root):
        raise PathNotAllowed("Direktori tujuan berada di luar akar evidence.")
    if target.is_symlink() or (target.exists() and target.is_dir()):
        raise OverwriteRefused(f"Sudah ada entri pada {relative_path}.")

    digest = hashlib.sha256()
    size = 0
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            for chunk in _as_chunks(data):
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, FILE_MODE)
        try:
            os.link(tmp, target)  # atomik dan gagal bila target sudah ada
        except FileExistsError:
            raise OverwriteRefused(f"Berkas sudah ada: {relative_path}") from None
        _fsync_dir(parent)
    finally:
        tmp.unlink(missing_ok=True)

    return StoredFile(
        relative_path=str(validate_relative_path(relative_path)),
        size=size,
        sha256=digest.hexdigest(),
    )


def sha256_of(relative_path: str) -> str:
    """Hitung SHA-256 berkas tersimpan. Raise FileNotFoundError bila tidak ada."""
    target = resolve_inside_evidence(relative_path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_stored(relative_path: str, expected_sha256: str) -> bool:
    """True bila berkas tersimpan masih sama dengan hash yang dicatat (NFR-02)."""
    return sha256_of(relative_path) == expected_sha256.lower()


def is_read_only(relative_path: str) -> bool:
    mode = resolve_inside_evidence(relative_path).stat().st_mode
    return not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
