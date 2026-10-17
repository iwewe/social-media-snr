"""Format dataset uji/impor (WP-1.7; FR-029). Skema: `docs/format-dataset-impor.md`.

Satu berkas = satu TARGET dengan urutan SNAPSHOT; snapshot ke-N diputar pada run ke-N target itu,
sehingga skenario beberapa putaran dapat diulang secara deterministik tanpa platform eksternal.

Semua validasi terjadi saat parse, termasuk uji coba membangun `InspectionResult` sungguhan dari
tiap snapshot: dataset yang melanggar kontrak adapter ditolak di sini dengan lokasi yang jelas,
bukan sebagai galat adapter pada saat run. Pesan galat hanya memuat LOKASI dan jenis masalah,
tidak pernah nilai isi dataset (dapat berupa konten sensitif).
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, NoReturn

from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    Capability,
    CollectionStatus,
    CollectorInfo,
    ContractViolation,
    Coverage,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    Limitation,
    LimitationCode,
    Observation,
    SourceMethod,
    SourceObjectType,
    UnavailableObject,
)
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL
from investigations.target_urls import normalize_target_url

SCHEMA_VERSION = 1
MAX_DATASET_BYTES = 16 * 1024 * 1024
COLLECTOR = CollectorInfo("fixture-dataset", "1")
# Dataset hanya boleh berasal dari dua sumber ini; metode lain milik adapter nyata.
DATASET_SOURCE_METHODS = (SourceMethod.SYNTHETIC_FIXTURE, SourceMethod.IMPORTED_DATASET)


class DatasetError(ValueError):
    """Dataset tidak sah. Pesan = lokasi + jenis masalah, bukan isi."""


def _fail(path: str, message: str) -> NoReturn:
    raise DatasetError(f"{path}: {message}")


def _short(items: Iterable[object]) -> str:
    return ", ".join(sorted(str(i)[:40] for i in items)[:5])


def _mapping(
    value: object, path: str, *, required: tuple[str, ...], optional: tuple[str, ...] = ()
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "harus berupa objek JSON")
    unknown = set(value) - set(required) - set(optional)
    if unknown:
        _fail(path, f"kunci tidak dikenal: {_short(unknown)}")
    missing = [k for k in required if k not in value]
    if missing:
        _fail(path, f"kunci wajib tidak ada: {_short(missing)}")
    return value


def _str(value: object, path: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        _fail(path, "harus berupa string" + (" atau null" if nullable else ""))
    return value


def _req_str(value: object, path: str) -> str:
    text = _str(value, path)
    assert text is not None
    if not text.strip():
        _fail(path, "tidak boleh kosong")
    return text


def _bool(value: object, path: str, *, nullable: bool = False) -> bool | None:
    if value is None and nullable:
        return None
    if not isinstance(value, bool):
        _fail(path, "harus true/false" + (" atau null" if nullable else ""))
    return value


def _count(value: object, path: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(path, "harus bilangan bulat >= 0 atau null")
    return value


def _time(value: object, path: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    text = _str(value, path)
    assert text is not None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        _fail(path, "bukan waktu ISO-8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(path, "waktu wajib memuat zona waktu (mis. 2026-10-16T01:32:00Z)")
    return parsed


def _enum[E: StrEnum](cls: type[E], value: object, path: str, lower: bool = False) -> E:
    text = _req_str(value, path)
    try:
        return cls(text.lower() if lower else text)
    except ValueError:
        _fail(path, f"nilai tidak dikenal; pilihan: {sorted(m.value for m in cls)}")


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "harus berupa daftar")
    return value


# --- spesifikasi (hasil parse) --------------------------------------------------------------


@dataclass(frozen=True)
class ObservationSpec:
    type: SourceObjectType
    id: str | None
    actor: str | None
    parent: str | None
    parent_unknown: bool
    quoted: str | None
    reposted: str | None
    mentions: tuple[str, ...]
    published_at: datetime | None
    captured_at: datetime | None
    text: str | None
    handle: str | None
    display_name: str | None
    needs_verification: bool

    def build(
        self,
        *,
        platform: Platform,
        run_id: str,
        observed_at: datetime,
        status: CollectionStatus,
        source_method: SourceMethod,
    ) -> Observation:
        return Observation(
            platform=platform,
            source_object_type=self.type,
            inspection_run_id=run_id,
            observed_at=observed_at,
            collection_status=status,
            source_method=source_method,
            external_post_id=self.id,
            external_actor_id=self.actor,
            parent_post_id=self.parent,
            parent_unknown=self.parent_unknown,
            quoted_post_id=self.quoted,
            reposted_post_id=self.reposted,
            mentioned_actor_ids=self.mentions,
            published_at=self.published_at,
            captured_at=self.captured_at,
            text=self.text,
            actor_handle=self.handle,
            actor_display_name=self.display_name,
            identity_needs_verification=self.needs_verification,
        )


@dataclass(frozen=True)
class ArtifactSpec:
    kind: ArtifactKind
    filename: str
    content_type: str
    text: str
    note: str | None

    def build(self) -> ArtifactCapture:
        return ArtifactCapture(
            kind=self.kind,
            filename=self.filename,
            content=self.text.encode("utf-8"),
            content_type=self.content_type,
            note=self.note,
        )


@dataclass(frozen=True)
class SnapshotSpec:
    observed_at: datetime
    outcome: InspectionOutcome
    pagination_complete: bool | None
    displayed_count: int | None
    notes: tuple[str, ...]
    limitations: tuple[Limitation, ...]
    observations: tuple[ObservationSpec, ...]
    confirmed_unavailable: tuple[UnavailableObject, ...]
    artifacts: tuple[ArtifactSpec, ...]


@dataclass(frozen=True)
class Dataset:
    name: str
    platform: Platform
    target_url: str  # sudah dinormalisasi
    source_method: SourceMethod
    snapshots: tuple[SnapshotSpec, ...]


# --- parse ----------------------------------------------------------------------------------


def _parse_observation(raw: object, path: str) -> ObservationSpec:
    keys = (
        "id actor parent parent_unknown quoted reposted mentions published_at captured_at "
        "text handle display_name needs_verification"
    ).split()
    d = _mapping(raw, path, required=("type",), optional=tuple(keys))
    raw_mentions = _list(d.get("mentions", []), f"{path}.mentions")
    mentions = tuple(_req_str(m, f"{path}.mentions[{i}]") for i, m in enumerate(raw_mentions))
    return ObservationSpec(
        type=_enum(SourceObjectType, d["type"], f"{path}.type", lower=True),
        id=_str(d.get("id"), f"{path}.id", nullable=True),
        actor=_str(d.get("actor"), f"{path}.actor", nullable=True),
        parent=_str(d.get("parent"), f"{path}.parent", nullable=True),
        parent_unknown=bool(_bool(d.get("parent_unknown", False), f"{path}.parent_unknown")),
        quoted=_str(d.get("quoted"), f"{path}.quoted", nullable=True),
        reposted=_str(d.get("reposted"), f"{path}.reposted", nullable=True),
        mentions=mentions,
        published_at=_time(d.get("published_at"), f"{path}.published_at", nullable=True),
        captured_at=_time(d.get("captured_at"), f"{path}.captured_at", nullable=True),
        text=_str(d.get("text"), f"{path}.text", nullable=True),
        handle=_str(d.get("handle"), f"{path}.handle", nullable=True),
        display_name=_str(d.get("display_name"), f"{path}.display_name", nullable=True),
        needs_verification=bool(
            _bool(d.get("needs_verification", False), f"{path}.needs_verification")
        ),
    )


def _parse_limitation(raw: object, path: str) -> Limitation:
    d = _mapping(raw, path, required=("code", "message"), optional=("capability",))
    capability = d.get("capability")
    return Limitation(
        _enum(LimitationCode, d["code"], f"{path}.code"),
        _req_str(d["message"], f"{path}.message"),
        None if capability is None else _enum(Capability, capability, f"{path}.capability"),
    )


def _parse_artifact(raw: object, path: str) -> ArtifactSpec:
    d = _mapping(
        raw, path, required=("kind", "filename", "content_type", "text"), optional=("note",)
    )
    return ArtifactSpec(
        kind=_enum(ArtifactKind, d["kind"], f"{path}.kind"),
        filename=_req_str(d["filename"], f"{path}.filename"),
        content_type=_req_str(d["content_type"], f"{path}.content_type"),
        text=_str(d["text"], f"{path}.text") or "",
        note=_str(d.get("note"), f"{path}.note", nullable=True),
    )


def _parse_snapshot(raw: object, path: str) -> SnapshotSpec:
    d = _mapping(
        raw,
        path,
        required=("observed_at", "outcome", "pagination_complete"),
        optional=tuple(
            "displayed_count notes limitations observations confirmed_unavailable artifacts".split()
        ),
    )
    confirmed = []
    raw_unavailable = _list(d.get("confirmed_unavailable", []), f"{path}.confirmed_unavailable")
    for i, item in enumerate(raw_unavailable):
        p = f"{path}.confirmed_unavailable[{i}]"
        c = _mapping(item, p, required=("id", "evidence"))
        confirmed.append(
            UnavailableObject(
                _req_str(c["id"], f"{p}.id"), _req_str(c["evidence"], f"{p}.evidence")
            )
        )
    return SnapshotSpec(
        observed_at=_time(d["observed_at"], f"{path}.observed_at"),  # type: ignore[arg-type]
        outcome=_enum(InspectionOutcome, d["outcome"], f"{path}.outcome"),
        pagination_complete=_bool(
            d["pagination_complete"], f"{path}.pagination_complete", nullable=True
        ),
        displayed_count=_count(d.get("displayed_count"), f"{path}.displayed_count"),
        notes=tuple(
            _req_str(n, f"{path}.notes[{i}]")
            for i, n in enumerate(_list(d.get("notes", []), f"{path}.notes"))
        ),
        limitations=tuple(
            _parse_limitation(x, f"{path}.limitations[{i}]")
            for i, x in enumerate(_list(d.get("limitations", []), f"{path}.limitations"))
        ),
        observations=tuple(
            _parse_observation(x, f"{path}.observations[{i}]")
            for i, x in enumerate(_list(d.get("observations", []), f"{path}.observations"))
        ),
        confirmed_unavailable=tuple(confirmed),
        artifacts=tuple(
            _parse_artifact(x, f"{path}.artifacts[{i}]")
            for i, x in enumerate(_list(d.get("artifacts", []), f"{path}.artifacts"))
        ),
    )


def parse_dataset(raw: object, *, label: str = "dataset") -> Dataset:
    """Validasi dan ubah JSON hasil `json.load` menjadi `Dataset`; raise DatasetError."""
    d = _mapping(
        raw,
        label,
        required=("schema_version", "name", "platform", "target_url", "source_method", "snapshots"),
    )
    if d["schema_version"] != SCHEMA_VERSION or isinstance(d["schema_version"], bool):
        _fail(f"{label}.schema_version", f"hanya versi {SCHEMA_VERSION} yang didukung")
    platform = _enum(Platform, d["platform"], f"{label}.platform", lower=True)
    method = _enum(SourceMethod, d["source_method"], f"{label}.source_method")
    if method not in DATASET_SOURCE_METHODS:
        _fail(
            f"{label}.source_method",
            f"dataset hanya boleh {sorted(m.value for m in DATASET_SOURCE_METHODS)}",
        )
    try:
        url = normalize_target_url(platform.value, _req_str(d["target_url"], f"{label}.target_url"))
    except InvalidTargetURL as exc:
        _fail(f"{label}.target_url", f"URL tidak sah untuk platform {platform.value}: {exc}")
    raw_snapshots = _list(d["snapshots"], f"{label}.snapshots")
    if not raw_snapshots:
        _fail(f"{label}.snapshots", "minimal satu snapshot")
    dataset = Dataset(
        name=_req_str(d["name"], f"{label}.name"),
        platform=platform,
        target_url=url,
        source_method=method,
        snapshots=tuple(
            _parse_snapshot(s, f"{label}.snapshots[{i}]") for i, s in enumerate(raw_snapshots)
        ),
    )
    _dry_run(dataset, label)
    return dataset


def _dry_run(dataset: Dataset, label: str) -> None:
    """Bangun InspectionResult sungguhan dari tiap snapshot agar pelanggaran kontrak
    (mis. COMPLETED tanpa paginasi lengkap, balasan tanpa induk) terlihat sebagai galat dataset."""
    for index in range(len(dataset.snapshots)):
        stub = InspectionRequest(
            inspection_run_id="dry-run",
            platform=dataset.platform,
            target_url=dataset.target_url,
            target_type=TargetType.POST,
            requested=(Capability.INSPECT_POST,),
        )
        try:
            build_result(dataset, index, stub)
        except ContractViolation as exc:
            _fail(f"{label}.snapshots[{index}]", f"melanggar kontrak adapter: {str(exc)[:200]}")


def load_dataset_file(path: Any) -> Dataset:
    """Baca satu berkas JSON. Ukuran dibatasi; isi tidak pernah ikut dalam pesan galat."""
    label = path.name
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DatasetError(f"{label}: berkas tidak dapat dibaca ({type(exc).__name__})") from exc
    if size > MAX_DATASET_BYTES:
        raise DatasetError(f"{label}: ukuran berkas melebihi batas {MAX_DATASET_BYTES} byte")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetError(f"{label}: bukan JSON UTF-8 yang sah ({type(exc).__name__})") from exc
    return parse_dataset(raw, label=label)


# --- membangun hasil ------------------------------------------------------------------------


def build_result(
    dataset: Dataset, index: int, request: InspectionRequest, *, max_items: int | None = None
) -> InspectionResult:
    snap = dataset.snapshots[index]
    outcome = snap.outcome
    limitations = list(snap.limitations)
    complete = snap.pagination_complete
    observations = snap.observations
    limit = request.max_items if request.max_items is not None else max_items
    if limit is not None and len(observations) > limit:
        observations = observations[:limit]
        outcome = InspectionOutcome.PARTIAL
        complete = False
        limitations.append(
            Limitation(LimitationCode.MAX_ITEMS_REACHED, f"dibatasi {limit} objek oleh permintaan")
        )
    complete_run = outcome is InspectionOutcome.COMPLETED
    status = CollectionStatus.COMPLETED if complete_run else CollectionStatus.PARTIAL
    notes = (*snap.notes, f"sumber: dataset '{dataset.name}' snapshot {index + 1}")
    return InspectionResult(
        platform=dataset.platform,
        inspection_run_id=request.inspection_run_id,
        outcome=outcome,
        collector=COLLECTOR,
        coverage=Coverage(request.requested, complete, snap.displayed_count, notes),
        observations=tuple(
            o.build(
                platform=dataset.platform,
                run_id=request.inspection_run_id,
                observed_at=snap.observed_at,
                status=status,
                source_method=dataset.source_method,
            )
            for o in observations
        ),
        limitations=tuple(limitations),
        confirmed_unavailable=snap.confirmed_unavailable,
        artifacts=tuple(a.build() for a in snap.artifacts),
    )


__all__ = [
    "COLLECTOR",
    "Dataset",
    "DatasetError",
    "MAX_DATASET_BYTES",
    "SCHEMA_VERSION",
    "build_result",
    "load_dataset_file",
    "parse_dataset",
]
_ = Mapping
