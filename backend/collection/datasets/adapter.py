"""Adapter dataset uji/impor (WP-1.7; FR-029, AT-18). Tidak memakai jaringan.

Satu kelas adapter per platform (isolasi platform tetap berlaku: instans mengaku satu platform).
Sumber dataset berupa direktori berkas JSON. Run ke-N pada sebuah target memutar snapshot ke-N
dataset target itu; target tanpa dataset atau run melebihi jumlah snapshot menghasilkan
UNSUPPORTED dengan alasan yang jelas (bukan hasil kosong yang tampak sukses).

Dataset TIDAK didaftarkan secara bawaan: tanpa `SNR_FIXTURE_DATASETS_DIR` adapter ini tidak ada,
sehingga data uji tidak dapat menyamar sebagai pengamatan platform (observasi selalu bertanda
`synthetic_fixture` atau `imported_dataset`).
"""

import re
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import parse_qs, urlsplit

from collection.contracts import (
    Adapter,
    Capabilities,
    Capability,
    CapabilityDeclaration,
    CapabilityStatus,
    ContractViolation,
    Coverage,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    Limitation,
    LimitationCode,
    TargetUrlInfo,
)
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL
from investigations.target_urls import normalize_target_url

from .dataset import (
    COLLECTOR,
    Dataset,
    DatasetError,
    build_result,
    load_dataset_file,
    parse_dataset,
)

_USER = r"[\w.]{1,30}"


def classify_url(platform: Platform, normalized: str) -> tuple[TargetType, str | None]:
    """Penyederhanaan untuk dataset uji: jenis target dari bentuk URL. Aturan ini TIDAK
    menggantikan adapter nyata (I3), yang mempelajari struktur URL platform masing-masing."""
    parts = urlsplit(normalized)
    segs = [s for s in parts.path.split("/") if s]
    query = parse_qs(parts.query)
    match platform:
        case Platform.X:
            if len(segs) == 3 and segs[1] == "status" and segs[2].isdigit():
                return TargetType.POST, segs[2]
            if len(segs) == 1 and re.fullmatch(r"\w{1,15}", segs[0]):
                return TargetType.ACCOUNT, None
        case Platform.THREADS:
            if len(segs) == 3 and segs[0].startswith("@") and segs[1] == "post":
                return TargetType.POST, segs[2]
            if len(segs) == 1 and re.fullmatch(rf"@{_USER}", segs[0]):
                return TargetType.ACCOUNT, None
        case Platform.TIKTOK:
            is_video = len(segs) == 3 and segs[1] == "video" and segs[2].isdigit()
            if is_video and segs[0].startswith("@"):
                return TargetType.POST, segs[2]
            if len(segs) == 1 and re.fullmatch(rf"@{_USER}", segs[0]):
                return TargetType.ACCOUNT, None
        case Platform.INSTAGRAM:
            if len(segs) == 2 and segs[0] in ("p", "reel", "tv"):
                return TargetType.POST, segs[1]
            if len(segs) == 1 and re.fullmatch(_USER, segs[0]):
                return TargetType.ACCOUNT, None
        case Platform.FACEBOOK:
            if "story_fbid" in query:
                return TargetType.POST, query["story_fbid"][0]
            if len(segs) == 3 and segs[1] == "posts":
                return TargetType.POST, segs[2]
            if len(segs) == 1 and re.fullmatch(_USER, segs[0]):
                return TargetType.ACCOUNT, None
    raise InvalidTargetURL("Struktur URL tidak dikenali oleh adapter dataset.")


class Lookup:
    def __init__(self, datasets: list[Dataset], problems: list[str]) -> None:
        self.datasets = datasets
        self.problems = problems


class DatasetSource(Protocol):
    def find(self, platform: Platform, normalized_url: str) -> Lookup: ...


class MemorySource:
    """Sumber dataset di memori (uji dan harness kontrak)."""

    def __init__(self, datasets: Iterable[Dataset]) -> None:
        self._datasets = list(datasets)

    def find(self, platform: Platform, normalized_url: str) -> Lookup:
        found = [
            d for d in self._datasets if d.platform == platform and d.target_url == normalized_url
        ]
        return Lookup(found, [])

    @classmethod
    def from_json(cls, *raw: object) -> "MemorySource":
        return cls(parse_dataset(r) for r in raw)


class DirectorySource:
    """Semua `*.json` pada satu direktori (tidak rekursif). Berkas yang tidak sah dilaporkan,
    bukan diabaikan diam-diam, karena berkas itu mungkin dataset target yang diminta."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def find(self, platform: Platform, normalized_url: str) -> Lookup:
        datasets: list[Dataset] = []
        problems: list[str] = []
        if not self.directory.is_dir():
            return Lookup([], [f"direktori dataset tidak ditemukan: {self.directory.name}"])
        for path in sorted(self.directory.glob("*.json")):
            try:
                dataset = load_dataset_file(path)
            except DatasetError as exc:
                problems.append(str(exc))
                continue
            if dataset.platform == platform and dataset.target_url == normalized_url:
                datasets.append(dataset)
        return Lookup(datasets, problems)


class FixtureAdapter(Adapter):
    collector = COLLECTOR
    execution_queue = "analysis"

    def __init__(self, source: DatasetSource, disable: Collection[Capability] = ()) -> None:
        self.source = source
        self.disable = frozenset(disable)

    def capabilities(self) -> Capabilities:
        sup = CapabilityDeclaration(CapabilityStatus.SUPPORTED)
        declarations = {
            Capability.INSPECT_POST: sup,
            Capability.INSPECT_REPLIES: sup,
            Capability.INSPECT_ACCOUNT: sup,
            Capability.PRESERVE_DOM: sup,
            Capability.PRESERVE_SCREENSHOT: CapabilityDeclaration(
                CapabilityStatus.UNSUPPORTED, "dataset tidak memuat tangkapan layar"
            ),
            Capability.PRESERVE_MEDIA: CapabilityDeclaration(
                CapabilityStatus.UNSUPPORTED, "dataset tidak memuat media"
            ),
        }
        for cap in self.disable:
            declarations[cap] = CapabilityDeclaration(CapabilityStatus.UNTESTED, "dinonaktifkan")
        return Capabilities(self.platform, declarations)

    def validate_target_url(self, url: str) -> TargetUrlInfo:
        normalized = normalize_target_url(self.platform.value, url)  # raise InvalidTargetURL
        target_type, external_id = classify_url(self.platform, normalized)
        return TargetUrlInfo(self.platform, target_type, normalized, external_id)

    def collect(self, request: InspectionRequest) -> InspectionResult:
        normalized = normalize_target_url(self.platform.value, request.target_url)
        lookup = self.source.find(self.platform, normalized)
        if len(lookup.datasets) > 1:
            return self._failed(request, "lebih dari satu dataset untuk target ini; hasil ambigu")
        if not lookup.datasets:
            if lookup.problems:
                return self._failed(
                    request,
                    "ada berkas dataset tidak sah sehingga target tidak dapat dipastikan: "
                    + "; ".join(lookup.problems)[:500],
                )
            return self._no_data(request, "tidak ada dataset untuk target ini")
        dataset = lookup.datasets[0]
        sequence = request.run_sequence or 1
        if sequence > len(dataset.snapshots):
            return self._no_data(
                request,
                f"dataset '{dataset.name}' hanya memiliki {len(dataset.snapshots)} snapshot; "
                f"run ke-{sequence} tidak punya data",
            )
        return build_result(dataset, sequence - 1, request)

    def _no_data(self, request: InspectionRequest, message: str) -> InspectionResult:
        outcome, code = InspectionOutcome.UNSUPPORTED, LimitationCode.UNSUPPORTED
        return self._empty(request, outcome, code, message)

    def _failed(self, request: InspectionRequest, message: str) -> InspectionResult:
        return self._empty(request, InspectionOutcome.FAILED, LimitationCode.PARSE_FAILED, message)

    def _empty(
        self,
        request: InspectionRequest,
        outcome: InspectionOutcome,
        code: LimitationCode,
        message: str,
    ) -> InspectionResult:
        return InspectionResult(
            platform=self.platform,
            inspection_run_id=request.inspection_run_id,
            outcome=outcome,
            collector=self.collector,
            coverage=Coverage(request.requested, None),
            limitations=(Limitation(code, message),),
        )


def fixture_adapter_class(platform: Platform) -> type[FixtureAdapter]:
    """Kelas adapter untuk SATU platform (registry mensyaratkan `platform` pada kelas)."""
    name = f"Fixture{platform.name.title()}Adapter"
    return cast(type[FixtureAdapter], type(name, (FixtureAdapter,), {"platform": platform}))


def register_fixture_adapters(
    registry, directory: Path, platforms: Iterable[Platform] | None = None
) -> None:
    source = DirectorySource(directory)
    for platform in platforms or Platform:
        cls = fixture_adapter_class(platform)
        registry.register(platform, lambda cls=cls: cls(source))


_ = ContractViolation
