from dataclasses import dataclass

from investigations.enums import Platform, TargetType

from .errors import ContractViolation


@dataclass(frozen=True)
class TargetUrlInfo:
    """Hasil validasi URL target oleh adapter (struktur URL spesifik platform)."""

    platform: Platform
    target_type: TargetType
    normalized_url: str
    # ID stabil bila dapat diturunkan dari URL; None untuk tautan pendek/URL tanpa ID. Tidak
    # boleh diisi dengan tebakan: None berarti identitas perlu diverifikasi (PRD bagian 5).
    external_id: str | None = None

    def __post_init__(self) -> None:
        if not self.normalized_url.startswith("https://"):
            raise ContractViolation("normalized_url harus berskema https.")
        if self.external_id is not None and (
            not self.external_id.strip() or self.external_id != self.external_id.strip()
        ):
            raise ContractViolation("external_id harus string tidak kosong atau None.")
