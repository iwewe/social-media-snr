"""Pelabelan empat tingkat hasil pada model (WP-2.6; PRD 11.5). Murni; label model = string."""

from .levels import ResultTier

T = ResultTier
# Setiap model hasil harus punya tingkat; model infrastruktur ditandai eksplisit tanpa tingkat.
MODEL_TIERS: dict[str, ResultTier | None] = {
    "collection.PostObservation": T.OBSERVED_EVIDENCE,
    "preservation.EvidenceArtifact": T.OBSERVED_EVIDENCE,
    "intelligence.ResponseAssessment": T.ANALYTICAL_CLASSIFICATION,
    "intelligence.ActorIssueProfile": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.GraphProjection": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.GraphNode": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.GraphEdge": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.CoordinationNetwork": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.CoordinationEdge": T.BEHAVIORAL_NETWORK_PATTERN,
    "intelligence.Finding": T.REVIEWED_ANALYTICAL_FINDING,
    # infrastruktur analisis dan jejak tinjauan: bukan hasil analitik
    "intelligence.DatasetVersion": None,
    "intelligence.DatasetVersionObservation": None,
    "intelligence.AnalysisRun": None,
    "intelligence.AnalysisRunTargetContext": None,
    "intelligence.FindingRun": None,
    "intelligence.FindingObservation": None,
    "intelligence.FindingIndicator": None,
    "intelligence.FindingReview": None,
}


def tier_of(label: str) -> ResultTier | None:
    """`label` = `app_label.ModelName`. KeyError bila model belum diklasifikasikan."""
    return MODEL_TIERS[label]
