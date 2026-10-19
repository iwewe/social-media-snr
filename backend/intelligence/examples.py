"""Nilai CONTOH parameter analisis untuk eksplorasi (ADR 0024: tidak ada ambang baku).

Dipakai bersama oleh perintah operator `run_analyses` dan antarmuka (tombol "isi contoh
eksplorasi"). Nilai ini BUKAN ambang koordinasi atau konfigurasi yang telah dievaluasi; setiap
run menyimpan parameternya secara eksplisit dan hasilnya adalah indikator, bukan temuan.
"""

from typing import Any

EXPLORATORY_NOTE = (
    "Nilai parameter adalah CONTOH untuk eksplorasi (bukan ambang koordinasi); tiap run menyimpan "
    "parameternya dan hasilnya adalah indikator, bukan temuan."
)
CO_EXAMPLE: dict[str, Any] = dict(
    sync_window_seconds=120,
    sync_min_events=1,
    co_response_min_shared=1,
    similarity_ngram=3,
    similarity_threshold=0.8,
    similarity_min_chars=20,
    similarity_min_pairs=1,
    similarity_max_responses=1000,
    amplification_window_seconds=300,
    amplification_min_events=1,
    url_min_shared=1,
    phrase_words=5,
    phrase_min_shared=1,
    repeated_min_shared_targets=2,
    permutations=100,
    baseline_seed=1,
    evidence_limit=50,
    max_pair_events=5_000_000,
)
M3_EXAMPLE: dict[str, Any] = dict(
    min_responses=2, bucket_hours=24, min_active_buckets=2, narrative_min_texts=2
)
M4_EXAMPLE: dict[str, Any] = dict(
    unknown_time="include",
    relation_types=["reply_to", "quote_of", "repost_of", "mentions"],
    weighting="count",
    resolution=1.0,
    seed=1,
    compute_betweenness=True,
    metrics_max_nodes=1000,
    stability_seeds=10,
)
