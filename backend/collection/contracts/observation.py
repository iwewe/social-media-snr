"""Observasi ternormalisasi (PRD bagian 7.1). Seluruh adapter menghasilkan bentuk yang sama.

Prinsip:
- Nilai "tidak diketahui" selalu `None`, tidak pernah nilai bawaan palsu.
- `published_at` TIDAK PERNAH diisi dari `observed_at`/`captured_at` (PRD bagian 9.3).
- ID sumber yang tidak tersedia ditandai `identity_needs_verification` dan tidak boleh digabung
  otomatis (PRD bagian 5).
- Observasi adalah data sumber: tidak memuat label, stance, atau kesimpulan (observe first).
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any

from investigations.enums import Platform

from .enums import CollectionStatus, SourceMethod, SourceObjectType
from .errors import ContractViolation

MAX_ID_LENGTH = 256
MAX_TEXT_LENGTH = 200_000
MAX_SHORT_TEXT = 500

_REPLY_TYPES = frozenset({SourceObjectType.REPLY, SourceObjectType.COMMENT})


def _check_id(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ContractViolation(f"{name} harus string tidak kosong tanpa spasi tepi, atau None.")
    if len(value) > MAX_ID_LENGTH:
        raise ContractViolation(f"{name} melebihi {MAX_ID_LENGTH} karakter.")


def _check_aware(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise ContractViolation(f"{name} harus datetime atau None.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(f"{name} harus memuat zona waktu (timezone-aware).")


def _enum(enum_cls: type[Enum], name: str, value: object) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        raise ContractViolation(
            f"{name} tidak valid: {value!r}; harus salah satu dari {[m.value for m in enum_cls]}."
        ) from None


@dataclass(frozen=True)
class Observation:
    platform: Platform
    source_object_type: SourceObjectType
    inspection_run_id: str
    observed_at: datetime
    collection_status: CollectionStatus
    source_method: SourceMethod

    external_post_id: str | None = None
    external_actor_id: str | None = None
    # Hubungan. parent_* hanya untuk REPLY/COMMENT; quoted_* hanya QUOTE; reposted_* hanya REPOST.
    parent_post_id: str | None = None
    parent_unknown: bool = False
    quoted_post_id: str | None = None
    reposted_post_id: str | None = None
    mentioned_actor_ids: tuple[str, ...] = ()

    published_at: datetime | None = None
    captured_at: datetime | None = None
    text: str | None = None
    # Username/nama tampilan dapat berubah: informasi, BUKAN identitas (PRD bagian 5).
    actor_handle: str | None = None
    actor_display_name: str | None = None
    identity_needs_verification: bool = False

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "platform", _enum(Platform, "platform", self.platform))
        set_(
            self,
            "source_object_type",
            _enum(SourceObjectType, "source_object_type", self.source_object_type),
        )
        set_(
            self,
            "collection_status",
            _enum(CollectionStatus, "collection_status", self.collection_status),
        )
        set_(self, "source_method", _enum(SourceMethod, "source_method", self.source_method))
        set_(self, "mentioned_actor_ids", tuple(self.mentioned_actor_ids))

        if not isinstance(self.inspection_run_id, str) or not self.inspection_run_id.strip():
            raise ContractViolation("inspection_run_id wajib diisi.")
        for name in (
            "external_post_id",
            "external_actor_id",
            "parent_post_id",
            "quoted_post_id",
            "reposted_post_id",
        ):
            _check_id(name, getattr(self, name))
        for actor_id in self.mentioned_actor_ids:
            if actor_id is None:
                raise ContractViolation("mentioned_actor_ids tidak boleh memuat None.")
            _check_id("mentioned_actor_ids[]", actor_id)

        # --- waktu ---
        if self.observed_at is None:
            raise ContractViolation("observed_at wajib diisi.")
        _check_aware("observed_at", self.observed_at)
        _check_aware("published_at", self.published_at)
        _check_aware("captured_at", self.captured_at)
        if self.published_at is not None:
            if self.published_at == self.observed_at or (
                self.captured_at is not None and self.published_at == self.captured_at
            ):
                raise ContractViolation(
                    "published_at sama persis dengan observed_at/captured_at: waktu pengambilan "
                    "tidak boleh dijadikan waktu publikasi. Isi None bila waktu publikasi tidak "
                    "diketahui (PRD bagian 9.3)."
                )
            if self.published_at > self.observed_at:
                raise ContractViolation("published_at tidak boleh lebih baru dari observed_at.")

        # --- identitas (PRD bagian 5) ---
        if (self.external_post_id is None or self.external_actor_id is None) and not (
            self.identity_needs_verification
        ):
            raise ContractViolation(
                "external_post_id/external_actor_id tidak tersedia: wajib set "
                "identity_needs_verification=True agar tidak digabung otomatis."
            )

        # --- hubungan ---
        is_reply = self.source_object_type in _REPLY_TYPES
        if is_reply:
            if self.parent_post_id is None and not self.parent_unknown:
                raise ContractViolation(
                    f"{self.source_object_type.value} wajib memuat parent_post_id, atau "
                    "parent_unknown=True bila induknya tidak dapat ditentukan."
                )
            if self.parent_post_id is not None and self.parent_unknown:
                raise ContractViolation(
                    "parent_post_id dan parent_unknown=True saling bertentangan."
                )
        elif self.parent_post_id is not None or self.parent_unknown:
            raise ContractViolation("parent_post_id/parent_unknown hanya untuk reply atau comment.")
        if self.parent_post_id is not None and self.parent_post_id == self.external_post_id:
            raise ContractViolation("Sebuah objek tidak boleh menjadi induknya sendiri.")
        if (self.source_object_type is SourceObjectType.QUOTE) != (self.quoted_post_id is not None):
            raise ContractViolation("quoted_post_id wajib dan hanya untuk jenis quote.")
        if (self.source_object_type is SourceObjectType.REPOST) != (
            self.reposted_post_id is not None
        ):
            raise ContractViolation("reposted_post_id wajib dan hanya untuk jenis repost.")

        # --- teks ---
        if self.text is not None:
            if not isinstance(self.text, str):
                raise ContractViolation("text harus string atau None.")
            if len(self.text) > MAX_TEXT_LENGTH:
                raise ContractViolation(f"text melebihi {MAX_TEXT_LENGTH} karakter.")
        for name in ("actor_handle", "actor_display_name"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) > MAX_SHORT_TEXT):
                raise ContractViolation(
                    f"{name} harus string <= {MAX_SHORT_TEXT} karakter atau None."
                )

    # --- serialisasi (impor dataset, fixture, manifest) ---------------------------------------

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, tuple):
                value = list(value)
            elif hasattr(value, "value"):
                value = value.value
            out[f.name] = value
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Observation":
        """Bangun dari dict (mis. JSON). Ketat: kunci asing ditolak, nilai divalidasi."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ContractViolation(f"Kunci tidak dikenal pada observasi: {sorted(unknown)}")
        kwargs: dict[str, Any] = dict(data)
        for name in ("observed_at", "published_at", "captured_at"):
            raw = kwargs.get(name)
            if isinstance(raw, str):
                try:
                    kwargs[name] = datetime.fromisoformat(raw)
                except ValueError:
                    raise ContractViolation(
                        f"{name} bukan waktu ISO-8601 yang valid: {raw!r}"
                    ) from None
        if "mentioned_actor_ids" in kwargs:
            kwargs["mentioned_actor_ids"] = tuple(kwargs["mentioned_actor_ids"])
        try:
            return cls(**kwargs)
        except TypeError as exc:  # argumen wajib hilang
            raise ContractViolation(str(exc)) from None
