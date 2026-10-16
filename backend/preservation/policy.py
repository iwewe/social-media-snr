"""Kebijakan artefak: menentukan apakah sebuah artefak boleh disimpan sebagai bukti (WP-1.5).

Penyimpanan artefak (`preservation.service.persist_run_artifacts`) MEWAJIBKAN kebijakan sebagai
parameter tanpa nilai bawaan, agar tidak ada jalur yang menyimpan artefak tanpa pemeriksaan.
Kebijakan produksi (penyaring cookies/token) ada di `preservation.secrets` (WP-1.5b).
"""

from dataclasses import dataclass
from typing import Protocol

from collection.contracts import ArtifactCapture


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    # Identitas aturan yang menolak (stabil, untuk log/manifest).
    # JANGAN pernah memuat nilai rahasia.
    rule: str = ""
    reason: str = ""


class ArtifactPolicy(Protocol):
    def check(self, capture: ArtifactCapture) -> PolicyDecision: ...


class UncheckedPolicy:
    """TIDAK AMAN: menerima semua artefak. Hanya untuk tes dan alat internal; jangan dipakai pada
    data nyata. Penyaring produksi: `preservation.secrets.SecretFilterPolicy`."""

    def check(self, capture: ArtifactCapture) -> PolicyDecision:
        return PolicyDecision(True)
