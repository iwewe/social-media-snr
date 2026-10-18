"""Alat persiapan pilot (WP-4.1; PRD 16.3): set anotasi dan metrik pilot.

TIDAK menetapkan "target lulus" apa pun (PRD tidak menetapkannya): modul ini hanya menyiapkan
bahan ukur. Set anotasi memuat teks nyata pihak ketiga: perlakukan setara bukti (jangan di Git,
batasi akses; lihat docs/pilot/protokol-pilot.md). Lembar anotator TIDAK memuat label mesin agar
penilaian tidak bias; label mesin (yang asli, bukan hasil koreksi manusia) diekspor terpisah
untuk dievaluasi terhadap putusan akhir.
"""

import os
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import connection

from collection.durations import duration_report
from collection.models import InspectionRun
from preservation.models import EvidenceArtifact
from preservation.storage import evidence_root

from .assessment import assessment_history, current_assessments
from .conversation import ConversationIndex
from .evaluation import CHARACTER_CODES, MIN_PILOT_ITEMS, PILOT_NOTICE, SINGLE_DIMENSIONS
from .models import AnalysisRun, DatasetVersionObservation

SHORT_TEXT_CHARS = 20
INSTRUCTIONS = (
    "Nilai SETIAP respons terhadap proposition yang tertulis. issue_stance dinilai terhadap "
    "proposition; target_alignment menilai kesepakatan terhadap posting yang dibalas; keduanya "
    "dimensi berbeda. Pilih UNDETERMINED bila ragu atau bila bergantung pada gambar/video yang "
    "tidak tersedia. response_character: satu atau lebih kode RC-xx. Jangan melihat label mesin "
    "sebelum selesai. Tambahkan tag (mis. sarcasm, informal, nested) pada kolom tags bila relevan."
)


def sample_ids(strata: Mapping[str, Sequence[int]], n: int, seed: int) -> list[int]:
    """Ambil sampai `n` id bergilir antar strata (acak berbenih dalam strata) agar kategori beragam.

    Deterministik untuk (strata, n, seed). Bila total kandidat < n, semuanya diambil."""
    rng = random.Random(seed)  # noqa: S311 - pengambilan contoh berbenih, bukan kriptografi
    pools = {name: sorted(ids) for name, ids in sorted(strata.items()) if ids}
    for ids in pools.values():
        rng.shuffle(ids)
    chosen: list[int] = []
    while len(chosen) < n and any(pools.values()):
        for name in list(pools):
            if pools[name] and len(chosen) < n:
                chosen.append(pools[name].pop())
    return sorted(chosen)


def context_tags(
    *, depth: int, parent_unknown: bool, machine_flagged: bool, text: str | None
) -> list[str]:
    """Tag konteks otomatis (bukan penilaian): bahan analisis galat; tag kualitatif oleh penilai."""
    tags = []
    if depth >= 2:
        tags.append("nested")
    if parent_unknown:
        tags.append("parent_unknown")
    if depth == 0 and not parent_unknown:
        tags.append("no_parent")
    if machine_flagged:
        tags.append("machine_flagged")
    if text is None or len(text.strip()) < SHORT_TEXT_CHARS:
        tags.append("short_or_missing_text")
    return tags


def below_recommended_size(count: int) -> bool:
    return count < MIN_PILOT_ITEMS


def _machine_labels(assessment: Any) -> dict[str, Any]:
    origin = assessment_history(assessment)[0]  # hasil mesin asli, bukan koreksi manusia
    return {
        "issue_stance": origin.issue_stance,
        "target_alignment": origin.target_alignment,
        "response_character": sorted(origin.response_character),
    }


def build_annotation_set(
    run: AnalysisRun,
    *,
    n: int,
    seed: int,
    annotators: Sequence[str],
    proposition_id: int | None = None,
) -> dict[str, Any]:
    """Bangun `sheet`, `predictions`, dan `manifest` dari satu AnalysisRun M2 yang selesai."""
    if not run.method.startswith("m2-"):
        raise ValueError("annotation set hanya dari run M2 (klasifikasi respons)")
    if len(annotators) < 1 or len(set(annotators)) != len(annotators):
        raise ValueError("annotators: minimal satu nama, tanpa duplikat")
    if proposition_id is None:
        proposition_id = min(int(k) for k in run.parameters["propositions"])
    assessments = list(
        current_assessments(run).filter(proposition_id=proposition_id).select_related("observation")
    )
    index = ConversationIndex(
        DatasetVersionObservation.objects.filter(
            dataset_version_id=run.dataset_version_id
        ).values_list("observation_id", flat=True)
    )
    by_obs = {a.observation_id: a for a in assessments}
    strata: dict[str, list[int]] = {}
    for a in assessments:
        strata.setdefault(_machine_labels(a)["issue_stance"], []).append(a.observation_id)
    chosen = sample_ids(strata, n, seed)

    items: list[dict[str, Any]] = []
    predictions: dict[str, Any] = {}
    for oid in chosen:
        a = by_obs[oid]
        chain = index.chain(oid)
        text = a.observation.text
        tags = context_tags(
            depth=chain.depth,
            parent_unknown=chain.parent_unknown,
            machine_flagged=a.needs_human_review,
            text=text,
        )
        key = str(oid)
        items.append(
            {
                "id": key,
                "text": text,
                "parent_chain": [p.text for p in chain.parents],
                "tags": tags,
                "labels": {
                    name: {
                        "issue_stance": None,
                        "target_alignment": None,
                        "response_character": None,
                    }
                    for name in annotators
                },
            }
        )
        predictions[key] = _machine_labels(a)
    manifest = {
        "notice": PILOT_NOTICE,
        "analysis_run_id": run.pk,
        "dataset_digest": run.dataset_version.observation_digest,
        "proposition_id": proposition_id,
        "seed": seed,
        "requested": n,
        "selected": len(items),
        "min_recommended": MIN_PILOT_ITEMS,
        "below_recommended_size": below_recommended_size(len(items)),
        "annotators": list(annotators),
        "strata_available": {k: len(v) for k, v in sorted(strata.items())},
        "strata_selected": dict(
            sorted(Counter(predictions[str(i)]["issue_stance"] for i in chosen).items())
        ),
        "allowed_values": {
            **SINGLE_DIMENSIONS,
            "response_character": CHARACTER_CODES,
        },
    }
    sheet = {
        "schema_version": 1,
        "instructions": INSTRUCTIONS,
        "proposition": {"id": proposition_id},
        "items": items,
    }
    return {"sheet": sheet, "predictions": predictions, "manifest": manifest}


def _tree_size(root: Any) -> int:
    total = 0
    for base, _dirs, files in os.walk(root):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                continue
    return total


def pilot_metrics() -> dict[str, Any]:
    """Metrik yang dicatat selama pilot (WP-4.1). Tanpa ambang: hanya angka dan sumbernya."""
    platforms: dict[str, dict[str, Any]] = {}
    runs = InspectionRun.objects.select_related("target").order_by("id")
    for run in runs:
        p = platforms.setdefault(
            run.target.platform,
            {
                "runs": 0,
                "outcomes": Counter(),
                "displayed": 0,
                "observed": 0,
                "runs_with_count": 0,
                "pagination_incomplete": 0,
                "parse_failures": 0,
                "unsupported": 0,
            },
        )
        p["runs"] += 1
        p["outcomes"][run.status] += 1
        coverage = run.coverage or {}
        displayed, observed = (
            coverage.get("platform_displayed_count"),
            coverage.get("observed_reply_count"),
        )
        if displayed is not None and observed is not None:
            p["displayed"] += displayed
            p["observed"] += observed
            p["runs_with_count"] += 1
        if coverage.get("pagination_complete") is False:
            p["pagination_incomplete"] += 1
        codes = {lim.get("code") for lim in run.limitations or []}
        if "PARSE_FAILED" in codes:
            p["parse_failures"] += 1
        if "UNSUPPORTED" in codes:
            p["unsupported"] += 1
    for p in platforms.values():
        p["outcomes"] = dict(sorted(p["outcomes"].items()))
        p["observed_vs_displayed"] = (
            None if not p["displayed"] else round(p["observed"] / p["displayed"], 4)
        )
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        db_bytes = cursor.fetchone()[0]
    return {
        "notice": (
            "Angka pilot, bukan target lulus. Kelengkapan = respons teramati dibanding jumlah yang "
            "ditampilkan platform, hanya untuk run yang melaporkan keduanya."
        ),
        "platforms": dict(sorted(platforms.items())),
        "durations": duration_report(),
        "storage": {
            "evidence_bytes": _tree_size(evidence_root()),
            "artifact_rows": EvidenceArtifact.objects.count(),
            "database_bytes": db_bytes,
        },
        "restore_test": "lihat docs/operations.md (catat hasil uji restore terbaru di sana)",
    }
