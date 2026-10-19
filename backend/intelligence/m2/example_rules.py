"""Contoh parameter aturan M2 untuk bahasa Indonesia informal (eksplorasi, dataset sintetis).

PERINGATAN: cue di sini ditulis dengan melihat templat dataset sintetis
(docs/synthetic-dataset-i2.md), sehingga hasil evaluasi atasnya adalah uji kewarasan alur dan
harness, BUKAN bukti kualitas pada data nyata. Tetap harus disalin secara eksplisit ke parameter
AnalysisRun; tidak ada nilai bawaan yang berlaku diam-diam.
"""

from collections.abc import Mapping
from typing import Any


def example_parameters(
    propositions: Mapping[int, tuple[list[str], list[str]]], *, min_matches: int = 1
) -> dict[str, Any]:
    """`propositions`: id proposition -> (cue pro, cue kontra)."""
    return {
        "propositions": {
            str(pid): {"pro_cues": list(pro), "contra_cues": list(contra)}
            for pid, (pro, contra) in propositions.items()
        },
        "agree_cues": ["setuju sekali", "sependapat", "mikir begitu"],
        "disagree_cues": ["tidak sependapat", "nggak sependapat", "kurang setuju", "keliru"],
        "character_cues": {
            "RC-02": ["lemah karena", "belum disertai rujukan"],
            "RC-04": [
                "apa bukti",
                "apa buktinya",
                "sumbernya dari mana",
                "datanya dari mana",
                "dokumen resminya",
            ],
            "RC-05": [
                "bodoh",
                "tidak mengerti apa apa",
                "nggak ngerti apa apa",
                "nggak mengerti apa apa",
                "isinya sampah",
                "pantas diabaikan",
            ],
            "RC-06": ["wah hebat sekali", "oh tentu", "jenius banget"],
            "RC-07": ["awas ya", "urusannya bisa panjang"],
            "RC-08": [
                "resep nasi goreng",
                "hujan deras",
            ],
            "RC-09": ["jual follower", "promo diskon"],
        },
        "sentiment_cues": {"POSITIVE": [], "NEGATIVE": ["marah", "sedih", "capek"]},
        # Negasi: hanya untuk menandai "perlu tinjauan manusia"; mesin tidak memahami negasi.
        "negation_cues": ["tidak", "bukan", "nggak", "gak", "ga", "tak", "belum", "jangan"],
        "negation_window": 5,
        "min_matches": min_matches,
    }


SYNTHETIC_PROPOSITION_CUES: dict[int, tuple[list[str], list[str]]] = {
    1: (
        ["harus diaudit", "audit harus dilakukan", "audit harus"],
        ["tidak perlu diaudit", "nggak perlu diaudit"],
    ),
    2: (["harus dibuka ke publik"], ["tidak perlu dipublikasikan", "nggak perlu dipublikasikan"]),
    3: (["harus dicabut"], ["sudah wajar", "udah wajar"]),
}
