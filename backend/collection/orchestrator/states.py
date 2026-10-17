"""Tabel transisi status InspectionRun (PRD bagian 9.1; FR-021).

Satu sumber kebenaran di Python. Penjaga di database (migrasi 0009) menegakkan tabel yang SAMA;
tes membandingkan keduanya untuk setiap pasangan status (8 x 8) agar tidak pernah menyimpang.

  PENDING  -> RUNNING | FAILED | UNSUPPORTED
  RUNNING  -> COMPLETED | PARTIAL | FAILED | ACCESS_RESTRICTED | UNSUPPORTED | REVIEW_REQUIRED
  hasil akhir (COMPLETED, PARTIAL, FAILED, ACCESS_RESTRICTED, UNSUPPORTED) -> REVIEW_REQUIRED
  REVIEW_REQUIRED -> salah satu hasil akhir (hanya lewat `acknowledge_review`, dan Python
                     mewajibkan hasil akhir itu sama dengan hasil yang tercatat di run)

Status akhir tidak dapat kembali ke PENDING/RUNNING: pemeriksaan ulang membuat run BARU.
"""

from .._enums import RunStatus

OUTCOME_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.PARTIAL,
        RunStatus.FAILED,
        RunStatus.ACCESS_RESTRICTED,
        RunStatus.UNSUPPORTED,
    }
)
# Status tempat data hasil run sudah final (kolom hasil tidak boleh berubah lagi).
FINAL_STATUSES = OUTCOME_STATUSES | {RunStatus.REVIEW_REQUIRED}

TRANSITIONS: dict[str, frozenset[str]] = {
    RunStatus.PENDING: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.UNSUPPORTED}),
    RunStatus.RUNNING: frozenset(OUTCOME_STATUSES | {RunStatus.REVIEW_REQUIRED}),
    **{status: frozenset({RunStatus.REVIEW_REQUIRED}) for status in OUTCOME_STATUSES},
    RunStatus.REVIEW_REQUIRED: frozenset(OUTCOME_STATUSES),
}


def can_transition(source: str, target: str) -> bool:
    """True bila perpindahan `source` -> `target` sah. Status yang sama bukan perpindahan."""
    return source == target or target in TRANSITIONS.get(source, frozenset())
