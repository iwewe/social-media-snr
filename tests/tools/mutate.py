"""Alat mutasi sengaja (verifikasi tingkat 2; docs/verification.md).

Membuktikan bahwa tes BENAR-BENAR dapat gagal: tiap mutasi mengganti satu pola teks pada kode nyata,
menjalankan tes, lalu memulihkan berkas. Mutasi yang lolos (tes tetap hijau) adalah celah tes, kecuali
ditandai `equivalent` dengan alasan tertulis.

Pengaman yang ada karena pernah terlewat secara manual:
- BASELINE harus hijau sebelum apa pun dimutasi (jika tidak, setiap mutasi tampak "tertangkap").
- Pola harus muncul TEPAT SEKALI; selain itu mutasi berstatus ERROR (bukan SKIP diam-diam) dan
  menggagalkan eksekusi.
- Keputusan memakai KODE KELUAR perintah tes, bukan membaca teks keluaran. Kode 5 (tidak ada tes
  terkumpul) dan batas waktu dilaporkan terpisah, tidak dihitung "tertangkap".
- Berkas dipulihkan di `finally` dan hash-nya diperiksa; pemulihan gagal menghentikan semuanya.

Kecepatan dan keamanan: secara bawaan tiap SLOT bekerja pada SALINAN repo (tanpa .git, venv, node_modules,
data), dan beberapa mutasi berjalan bersamaan (`--jobs`, bawaan 3). Repo asli tidak pernah dimutasi,
jadi alat yang terhenti di tengah tidak meninggalkan kode rusak. `--in-place` memutasi repo asli
(satu slot; hanya untuk perintah yang tidak dapat memakai salinan).

Pemakaian:  python tests/tools/mutate.py tests/mutation_specs/<spec>.py [--only teks] [--json hasil.json]
                                          [--jobs N] [--in-place]
Berkas spek: COMMAND (perintah tes), BASELINE_COMMAND (opsional; mis. dengan --create-db), CWD,
TIMEOUT (detik per perintah), MUTATIONS (daftar `Mutation`). Substitusi dalam COMMAND/BASELINE_COMMAND/
CWD: {root} = akar salinan slot, {origin} = akar repo asli, {job} = nomor slot (mis. untuk nama
database uji yang berbeda per slot). CWD bawaan "{root}"; perintah docker compose memakai
CWD = "{origin}" (compose.yaml dan .env ada di sana) dan memasang {root} lewat -v.
"""

import argparse
import hashlib
import importlib.util
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

CAUGHT, SURVIVED, ERROR, TIMED_OUT, NO_TESTS, EQUIVALENT_SURVIVED, EQUIVALENT_CAUGHT = (
    "CAUGHT", "SURVIVED", "ERROR", "TIMEOUT", "NO_TESTS", "EQUIVALENT", "EQUIVALENT_NOW_CAUGHT",
)


@dataclass(frozen=True)
class Mutation:
    name: str
    path: str  # relatif terhadap akar repo
    old: str
    new: str
    # Isi alasan bila mutan ini setara secara fungsional (tidak mengubah perilaku yang teramati).
    equivalent: str | None = None


@dataclass
class Result:
    name: str
    status: str
    seconds: float = 0.0
    detail: str = ""


@dataclass
class Spec:
    command: str
    mutations: list[Mutation]
    baseline_command: str | None = None
    cwd: str = "{root}"
    timeout: int = 900
    extra: dict = field(default_factory=dict)


def load_spec(path: Path) -> Spec:
    loader = importlib.util.spec_from_file_location("mutation_spec", path)
    assert loader and loader.loader
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return Spec(
        command=module.COMMAND,
        mutations=list(module.MUTATIONS),
        baseline_command=getattr(module, "BASELINE_COMMAND", None),
        cwd=getattr(module, "CWD", "{root}"),
        timeout=getattr(module, "TIMEOUT", 900),
    )


def _run(command: str, cwd: Path, timeout: int) -> tuple[int | None, float]:
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command, shell=True, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False,
        )
        return done.returncode, time.perf_counter() - started
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - started


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BaselineFailed(RuntimeError):
    pass


class RestoreFailed(RuntimeError):
    pass


IGNORED = (".git", ".venv", "node_modules", "__pycache__", "snr-data", "e2e-shots", "dist",
           ".ruff_cache", ".mypy_cache", ".pytest_cache", "staticfiles")


def make_slot(origin: Path, dest: Path) -> None:
    """Salinan kerja ringan untuk satu slot; node_modules frontend ditautkan, bukan disalin."""
    base = shutil.ignore_patterns(*IGNORED)
    dest_abs = dest.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped = set(base(directory, names))
        # Jangan menyalin diri sendiri bila direktori tujuan berada di dalam repo asal.
        skipped.update(n for n in names if (Path(directory) / n).resolve() == dest_abs)
        skipped.update(n for n in names if dest_abs.is_relative_to((Path(directory) / n).resolve()))
        return skipped

    shutil.copytree(origin, dest, ignore=ignore)
    modules = origin / "frontend" / "node_modules"
    if modules.is_dir():
        (dest / "frontend" / "node_modules").symlink_to(modules)


class _Slot:
    def __init__(self, job: int, root: Path, origin: Path) -> None:
        self.job, self.root, self.origin = job, root, origin

    def expand(self, text: str) -> str:
        return (
            text.replace("{root}", str(self.root))
            .replace("{origin}", str(self.origin))
            .replace("{job}", str(self.job))
        )


def _mutate_in_slot(spec: Spec, slot: _Slot, mutation: Mutation) -> Result:
    path = slot.root / mutation.path
    if not path.is_file():
        return Result(mutation.name, ERROR, detail=f"berkas tidak ada: {mutation.path}")
    original = path.read_bytes()
    text = original.decode("utf-8")
    found = text.count(mutation.old)
    if found != 1:
        return Result(
            mutation.name, ERROR, detail=f"pola muncul {found}x (harus 1x) di {mutation.path}"
        )
    digest = hashlib.sha256(original).hexdigest()
    path.write_text(text.replace(mutation.old, mutation.new), encoding="utf-8")
    try:
        code, secs = _run(slot.expand(spec.command), Path(slot.expand(spec.cwd)), spec.timeout)
    finally:
        path.write_bytes(original)
        if _sha(path) != digest:
            raise RestoreFailed(f"berkas tidak pulih: {mutation.path}")
    return Result(mutation.name, _classify(code, mutation), secs, f"kode keluar {code}")


def run_spec(
    spec: Spec,
    root: Path,
    *,
    only: str | None = None,
    jobs: int = 1,
    in_place: bool = True,
    workdir: Path | None = None,
    log=print,
) -> list[Result]:
    """Jalankan semua mutasi. `in_place=True` memutasi `root` (satu slot); selain itu tiap slot
    bekerja pada salinan di `workdir` dan `jobs` mutasi berjalan bersamaan."""
    import tempfile

    jobs = 1 if in_place else max(1, jobs)
    selected = [m for m in spec.mutations if not only or only in m.name]
    cleanup: Path | None = None
    slots: list[_Slot] = []
    if in_place:
        slots.append(_Slot(0, root, root))
    else:
        base = workdir or Path(tempfile.mkdtemp(prefix="snr-mut-"))
        cleanup = None if workdir else base
        for job in range(jobs):
            dest = base / f"slot{job}"
            make_slot(root, dest)
            slots.append(_Slot(job, dest, root))
    try:
        # Baseline pada SETIAP slot (basis data uji dan salinan masing-masing harus hijau).
        def baseline(slot: _Slot) -> tuple[int | None, float]:
            return _run(
                slot.expand(spec.baseline_command or spec.command),
                Path(slot.expand(spec.cwd)),
                spec.timeout,
            )

        with ThreadPoolExecutor(max_workers=len(slots)) as pool:
            outcomes = list(pool.map(baseline, slots))
        for slot, (code, secs) in zip(slots, outcomes, strict=True):
            if code != 0:
                raise BaselineFailed(
                    f"BASELINE TIDAK HIJAU pada slot {slot.job} (kode keluar {code}); hasil mutasi tidak "
                    "berarti. Perbaiki dulu."
                )
        log(f"baseline hijau pada {len(slots)} slot ({max(o[1] for o in outcomes):.0f} detik)")

        free: queue.Queue[_Slot] = queue.Queue()
        for slot in slots:
            free.put(slot)
        lock = threading.Lock()

        def work(mutation: Mutation) -> Result:
            slot = free.get()
            try:
                result = _mutate_in_slot(spec, slot, mutation)
            finally:
                free.put(slot)
            with lock:
                log(f"{result.status:<9} {result.name} ({result.seconds:.0f} detik)  [slot {slot.job}]")
            return result

        with ThreadPoolExecutor(max_workers=len(slots)) as pool:
            return list(pool.map(work, selected))
    finally:
        if cleanup is not None:
            shutil.rmtree(cleanup, ignore_errors=True)


def _classify(code: int | None, mutation: Mutation) -> str:
    if code is None:
        return TIMED_OUT
    if code == 5:
        return NO_TESTS
    caught = code != 0
    if mutation.equivalent is not None:
        return EQUIVALENT_CAUGHT if caught else EQUIVALENT_SURVIVED
    return CAUGHT if caught else SURVIVED


def summarize(results: list[Result]) -> tuple[str, bool]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    # EQUIVALENT_NOW_CAUGHT berarti tanda 'setara' sudah usang: laporkan sebagai masalah.
    bad = sum(counts.get(s, 0) for s in (SURVIVED, ERROR, TIMED_OUT, NO_TESTS, EQUIVALENT_CAUGHT))
    line = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    return f"{len(results)} mutasi: {line}", bad == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("spec")
    parser.add_argument("--only", help="hanya mutasi yang namanya memuat teks ini")
    parser.add_argument("--json", help="tulis hasil ke berkas JSON")
    parser.add_argument("--root", help="akar repo (bawaan: dua tingkat di atas alat ini)")
    parser.add_argument("--jobs", type=int, default=3, help="mutasi bersamaan (salinan terisolasi)")
    parser.add_argument("--in-place", action="store_true", help="mutasi repo asli, satu slot")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    spec = load_spec(Path(args.spec))
    try:
        results = run_spec(
            spec, root, only=args.only, jobs=args.jobs, in_place=args.in_place
        )
    except (BaselineFailed, RestoreFailed) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    summary, ok = summarize(results)
    print(summary)
    for r in results:
        if r.status in (SURVIVED, ERROR, TIMED_OUT, NO_TESTS, EQUIVALENT_CAUGHT):
            print(f"  PERLU PERHATIAN {r.status}: {r.name} {r.detail}")
    if args.json:
        Path(args.json).write_text(json.dumps([r.__dict__ for r in results], indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
