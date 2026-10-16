"""Pengaman ekspor/arsip bukti (PRD bagian 10 dan 13).

Sesi browser (cookies, profil) adalah kredensial rahasia dan TIDAK PERNAH menjadi artefak
investigasi. Kode apa pun yang membentuk ekspor atau arsip dari berkas lokal wajib memanggil
`ensure_exportable` untuk setiap berkas sumber.
"""

from pathlib import Path

from .secret_filter import filename_finding
from .storage import PathNotAllowed, _is_within, browser_profiles_root, evidence_root


def ensure_exportable(path: str | Path) -> Path:
    """Jalur terselesaikan bila di dalam akar evidence; selain itu raise PathNotAllowed."""
    resolved = Path(path).resolve()
    if _is_within(resolved, browser_profiles_root().resolve()):
        raise PathNotAllowed("Sesi browser tidak boleh diekspor atau diarsipkan.")
    if not _is_within(resolved, evidence_root().resolve()) or resolved == evidence_root().resolve():
        raise PathNotAllowed("Hanya berkas di dalam akar evidence yang dapat diekspor.")
    finding = filename_finding(resolved.name)
    if finding is not None:
        raise PathNotAllowed(f"Berkas menyerupai rahasia tidak boleh diekspor ({finding.rule}).")
    return resolved
