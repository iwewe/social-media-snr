"""WP-0.6: jalur tulis bukti (FR-037, FR-038, FR-039; NFR-02, NFR-07)."""

import hashlib
import os
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from preservation import storage
from preservation.storage import OverwriteRefused, PathNotAllowed


@pytest.fixture
def roots(tmp_path: Path, settings) -> Path:
    evidence = tmp_path / "data" / "evidence"
    profiles = tmp_path / "data" / "browser-profiles"
    evidence.mkdir(parents=True)
    profiles.mkdir(parents=True)
    settings.SNR_EVIDENCE_ROOT = evidence
    settings.SNR_BROWSER_PROFILES_ROOT = profiles
    return tmp_path / "data"


def listing(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


# --- penulisan dasar, hash, dan hak akses ---------------------------------------------------


def test_write_new_stores_content_and_returns_matching_sha256(roots: Path) -> None:
    data = b"isi bukti uji"
    stored = storage.write_new("run-1/capture.html", data)
    assert stored.relative_path == "run-1/capture.html"
    assert stored.size == len(data)
    assert stored.sha256 == hashlib.sha256(data).hexdigest()
    assert (roots / "evidence" / "run-1" / "capture.html").read_bytes() == data
    assert storage.verify_stored("run-1/capture.html", stored.sha256)  # AT-06


def test_streaming_hash_of_large_payload(roots: Path) -> None:
    chunk = os.urandom(1024 * 1024)
    chunks = [chunk, chunk, b"akhir"]
    stored = storage.write_new("besar.bin", iter(chunks))
    expected = hashlib.sha256(b"".join(chunks)).hexdigest()
    assert stored.sha256 == expected
    assert stored.size == 2 * 1024 * 1024 + 5
    assert storage.sha256_of("besar.bin") == expected


def test_empty_file_is_allowed_and_hashed(roots: Path) -> None:
    stored = storage.write_new("kosong.txt", b"")
    assert stored.size == 0
    assert stored.sha256 == hashlib.sha256(b"").hexdigest()


def test_stored_file_is_read_only_and_directories_are_not_world_accessible(roots: Path) -> None:
    storage.write_new("a/b/c.txt", b"x")
    assert storage.is_read_only("a/b/c.txt")
    for d in ("a", "a/b"):
        mode = (roots / "evidence" / d).stat().st_mode & 0o777
        assert mode & 0o007 == 0, oct(mode)


def test_tampering_is_detected_by_verify(roots: Path) -> None:
    stored = storage.write_new("bukti.txt", b"asli")
    path = roots / "evidence" / "bukti.txt"
    path.chmod(0o640)
    path.write_bytes(b"diubah")
    assert storage.verify_stored("bukti.txt", stored.sha256) is False


def test_verify_missing_file_raises_instead_of_returning_false(roots: Path) -> None:
    with pytest.raises(FileNotFoundError):
        storage.verify_stored("tidak-ada.txt", "0" * 64)


# --- tidak pernah menimpa (FR-039) ----------------------------------------------------------


def test_second_write_to_same_path_is_refused_and_original_is_untouched(roots: Path) -> None:
    first = storage.write_new("run-1/shot.png", b"pertama")
    with pytest.raises(OverwriteRefused):
        storage.write_new("run-1/shot.png", b"kedua-menimpa")
    assert (roots / "evidence" / "run-1" / "shot.png").read_bytes() == b"pertama"
    assert storage.verify_stored("run-1/shot.png", first.sha256)


def test_refused_overwrite_leaves_no_temp_files(roots: Path) -> None:
    storage.write_new("x.txt", b"1")
    with pytest.raises(OverwriteRefused):
        storage.write_new("x.txt", b"2")
    assert listing(roots / "evidence") == ["x.txt"]


def test_new_inspection_run_uses_a_new_path_and_keeps_the_old_file(roots: Path) -> None:
    storage.write_new("run-1/page.html", b"v1")
    storage.write_new("run-2/page.html", b"v2")
    assert listing(roots / "evidence") == ["run-1/page.html", "run-2/page.html"]


def test_concurrent_writers_exactly_one_wins(roots: Path) -> None:
    n = 8
    barrier = threading.Barrier(n)
    results: list[str] = []
    lock = threading.Lock()

    def writer(i: int) -> None:
        barrier.wait()
        try:
            storage.write_new("balapan.txt", f"penulis-{i}".encode())
            outcome = f"menang-{i}"
        except OverwriteRefused:
            outcome = "ditolak"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    winners = [r for r in results if r.startswith("menang")]
    assert len(winners) == 1, results
    assert results.count("ditolak") == n - 1
    content = (roots / "evidence" / "balapan.txt").read_bytes()
    assert content == f"penulis-{winners[0].split('-')[1]}".encode()  # utuh, tidak campur
    assert listing(roots / "evidence") == ["balapan.txt"]


def test_failure_midway_leaves_no_partial_file_or_temp(roots: Path) -> None:
    def broken() -> Iterator[bytes]:
        yield b"separuh"
        raise RuntimeError("koneksi putus")

    with pytest.raises(RuntimeError):
        storage.write_new("run-1/rusak.bin", broken())
    assert listing(roots / "evidence") == []
    # Nama itu tetap bebas dipakai setelah kegagalan.
    assert storage.write_new("run-1/rusak.bin", b"ulang").size == 5


def test_existing_directory_at_target_is_not_replaced(roots: Path) -> None:
    storage.write_new("dir/isi.txt", b"x")
    with pytest.raises(OverwriteRefused):
        storage.write_new("dir", b"y")


def test_file_in_the_way_of_a_parent_directory_is_not_clobbered(roots: Path) -> None:
    storage.write_new("run-1", b"saya-berkas")
    with pytest.raises((FileExistsError, NotADirectoryError, OverwriteRefused)):
        storage.write_new("run-1/anak.txt", b"y")
    assert (roots / "evidence" / "run-1").read_bytes() == b"saya-berkas"


# --- jalur tidak sah ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "",
        ".",
        "..",
        "../luar.txt",
        "a/../../luar.txt",
        "a/./b.txt",
        "a//b.txt",
        "/etc/passwd",
        "a/b/",
        "a\\b.txt",
        "a\x00b.txt",
        "x" * 300,
        "a/" + "y" * 300 + ".txt",
        "p/" * 600 + "f",
    ],
)
def test_malformed_or_escaping_paths_are_rejected(roots: Path, bad: str) -> None:
    with pytest.raises(PathNotAllowed):
        storage.write_new(bad, b"x")
    assert listing(roots) == []


def test_symlink_pointing_outside_the_root_is_rejected(roots: Path, tmp_path: Path) -> None:
    outside = tmp_path / "luar"
    outside.mkdir()
    (roots / "evidence" / "tautan").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathNotAllowed):
        storage.write_new("tautan/rahasia.txt", b"x")
    assert list(outside.iterdir()) == []


def test_symlink_into_browser_profiles_is_rejected(roots: Path) -> None:
    (roots / "evidence" / "sesi").symlink_to(roots / "browser-profiles", target_is_directory=True)
    with pytest.raises(PathNotAllowed):
        storage.write_new("sesi/cookies.txt", b"rahasia")
    assert listing(roots / "browser-profiles") == []


def test_symlink_as_final_component_is_never_followed(roots: Path, tmp_path: Path) -> None:
    victim = tmp_path / "korban.txt"
    victim.write_text("jangan ditimpa")
    (roots / "evidence" / "tautan.txt").symlink_to(victim)
    with pytest.raises((PathNotAllowed, OverwriteRefused)):
        storage.write_new("tautan.txt", b"timpa")
    assert victim.read_text() == "jangan ditimpa"


def test_profiles_nested_inside_evidence_are_still_refused_for_writes(
    roots: Path, settings
) -> None:
    # Konfigurasi salah (bersarang) ditolak oleh system check, tetapi penulisan juga tidak boleh
    # sampai masuk ke area sesi browser.
    nested = roots / "evidence" / "profil"
    nested.mkdir()
    settings.SNR_BROWSER_PROFILES_ROOT = nested
    with pytest.raises(PathNotAllowed):
        storage.write_new("profil/Default/Cookies", b"x")
    assert listing(nested) == []


def test_root_itself_cannot_be_a_write_target(roots: Path) -> None:
    with pytest.raises(PathNotAllowed):
        storage.resolve_inside_evidence("a/..")  # komponen '..' ditolak sejak validasi bentuk


def test_default_settings_use_separate_roots() -> None:
    assert storage.evidence_root() != storage.browser_profiles_root()
    assert django_settings.SNR_EVIDENCE_ROOT.name == "evidence"
