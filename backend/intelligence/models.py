"""Model dasar analisis I2 (WP-2.1; ADR 0025; PRD bagian 8, NFR-01, FR-014, FR-041).

DatasetVersion membekukan himpunan observasi sebagai input analisis (daftar ID tak-berubah + hash).
AnalysisRun menautkan DatasetVersion, versi konteks, parameter eksplisit, dan versi metode; setelah
dibuat, semua masukan itu tidak dapat diubah (trigger database, migrasi 0002). Revisi
konteks atau data
baru tidak mengubah run lama (AT-07); analisis ulang membuat DatasetVersion dan AnalysisRun baru.
"""

from enum import StrEnum

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from collection.models import ActorAccount, AppendOnlyModel, PostObservation
from investigations.enums import Platform
from investigations.models import (
    CollectionTarget,
    Investigation,
    IssueContextVersion,
    Proposition,
    TargetContextVersion,
)

from .m2.taxonomy import IssueStance, NarrativeFunction, Sentiment, TargetAlignment

_HEX64 = r"^[0-9a-f]{64}$"


class DatasetVersion(AppendOnlyModel):
    """Himpunan observasi yang dibekukan untuk SATU platform (FR-073, FR-081).

    Dibuat belum tersegel, diisi anggotanya, lalu disegel sekali (`sealed_at`); setelah itu anggota
    tidak
    dapat ditambah dan baris tidak dapat diubah. Hanya dataset tersegel yang dapat dianalisis.
    """

    investigation = models.ForeignKey(
        Investigation, on_delete=models.PROTECT, related_name="dataset_versions"
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    number = models.PositiveIntegerField(help_text="Nomor urut per investigasi.")
    observation_count = models.PositiveIntegerField()
    observation_digest = models.CharField(
        max_length=64, help_text="SHA-256 atas ID observasi terurut (bukan bukti keaslian)."
    )
    selection = models.JSONField(
        help_text="Cara memilih (run dan target); untuk jejak, bukan untuk membangun ulang."
    )
    note = models.CharField(max_length=500, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    sealed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["investigation_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["investigation", "number"], name="uniq_dataset_number"),
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="dataset_platform_valid"
            ),
            models.CheckConstraint(
                condition=Q(observation_digest__regex=_HEX64), name="dataset_digest_valid"
            ),
            models.CheckConstraint(condition=Q(observation_count__gte=1), name="dataset_not_empty"),
        ]

    def __str__(self) -> str:
        return f"Dataset {self.number} [{self.platform}] ({self.observation_count} observasi)"


class DatasetVersionObservation(AppendOnlyModel):
    dataset_version = models.ForeignKey(
        DatasetVersion, on_delete=models.PROTECT, related_name="members"
    )
    observation = models.ForeignKey(PostObservation, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset_version", "observation"], name="uniq_dataset_member"
            ),
        ]


class AnalysisStatus(models.TextChoices):
    PENDING = "PENDING", "PENDING"
    RUNNING = "RUNNING", "RUNNING"
    COMPLETED = "COMPLETED", "COMPLETED"
    FAILED = "FAILED", "FAILED"


class AnalysisRun(AppendOnlyModel):
    """Satu pelaksanaan analisis atas input yang dibekukan. Hanya status, waktu, galat, dan keluaran
    yang berubah (lewat `intelligence.services`, bukan `save()`); masukan terkunci oleh trigger."""

    public_id = models.UUIDField(unique=True, editable=False)
    investigation = models.ForeignKey(
        Investigation, on_delete=models.PROTECT, related_name="analysis_runs"
    )
    dataset_version = models.ForeignKey(
        DatasetVersion, on_delete=models.PROTECT, related_name="analysis_runs"
    )
    issue_context_version = models.ForeignKey(
        IssueContextVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="None = investigasi tidak memiliki konteks issue saat dijalankan (eksplisit).",
    )
    method = models.CharField(max_length=100)
    method_version = models.CharField(max_length=50)
    parameters = models.JSONField(
        help_text="Parameter eksplisit; tidak ada nilai bawaan tersembunyi."
    )
    parameters_digest = models.CharField(max_length=64)
    previous_run = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reanalyses"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    status = models.CharField(
        max_length=10, choices=AnalysisStatus.choices, default=AnalysisStatus.PENDING, db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    output = models.JSONField(null=True, blank=True)
    output_digest = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["investigation_id", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=AnalysisStatus.values), name="analysis_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(parameters_digest__regex=_HEX64), name="analysis_params_digest_valid"
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status=AnalysisStatus.COMPLETED)
                    & Q(output__isnull=True)
                    & Q(output_digest="")
                )
                | (
                    Q(status=AnalysisStatus.COMPLETED)
                    & Q(output__isnull=False)
                    & Q(output_digest__regex=_HEX64)
                ),
                name="analysis_output_only_when_completed",
            ),
        ]
        indexes = [models.Index(fields=["dataset_version"], name="analysis_dataset_idx")]

    def __str__(self) -> str:
        return f"Analisis {self.method} v{self.method_version} ({self.status})"


class AnalysisRunTargetContext(AppendOnlyModel):
    """Versi konteks target yang dibekukan pada satu AnalysisRun."""

    run = models.ForeignKey(AnalysisRun, on_delete=models.PROTECT, related_name="target_contexts")
    target = models.ForeignKey(CollectionTarget, on_delete=models.PROTECT, related_name="+")
    context_version = models.ForeignKey(
        TargetContextVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "target"], name="uniq_run_target_context"),
        ]


class AssessmentSource(models.TextChoices):
    MACHINE = "MACHINE", "MACHINE"
    HUMAN = "HUMAN", "HUMAN"


def _values(enum: type[StrEnum]) -> list[str]:
    return [m.value for m in enum]


class ResponseAssessment(AppendOnlyModel):
    """Penilaian M2 atas satu respons terhadap satu proposition (FR-050..FR-057; PRD 8, 11.2).

    Append-only. Hasil mesin ditulis saat AnalysisRun RUNNING; koreksi manusia adalah baris BARU
    yang menggantikan (`supersedes`) baris sebelumnya dengan pelaku dan alasan; hasil mesin tidak
    pernah ditimpa (FR-055, AT-16). `basis` memuat dasar yang dapat diperiksa (cue cocok, rujukan
    observasi, rantai induk).
    """

    analysis_run = models.ForeignKey(
        AnalysisRun, on_delete=models.PROTECT, related_name="assessments"
    )
    observation = models.ForeignKey(PostObservation, on_delete=models.PROTECT, related_name="+")
    proposition = models.ForeignKey(Proposition, on_delete=models.PROTECT, related_name="+")
    issue_stance = models.CharField(max_length=12)
    target_alignment = models.CharField(max_length=8)
    expression_sentiment = models.CharField(max_length=10, null=True, blank=True)  # noqa: DJ001 - NULL = tidak dinilai
    response_character = models.JSONField(help_text="Daftar kode RC-xx (multi-label).")
    narrative_function = models.CharField(max_length=30, null=True, blank=True)  # noqa: DJ001 - NULL = tidak dinilai
    needs_human_review = models.BooleanField(default=False)
    basis = models.JSONField(help_text="Dasar/alasan yang dapat diperiksa dan rujukan observasi.")
    source = models.CharField(max_length=7, choices=AssessmentSource.choices)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="superseded_by"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    review_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["analysis_run_id", "observation_id", "proposition_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis_run", "observation", "proposition"],
                condition=Q(source="MACHINE"),
                name="uniq_machine_assessment",
            ),
            models.CheckConstraint(
                condition=Q(issue_stance__in=_values(IssueStance)), name="assessment_stance_valid"
            ),
            models.CheckConstraint(
                condition=Q(target_alignment__in=_values(TargetAlignment)),
                name="assessment_alignment_valid",
            ),
            models.CheckConstraint(
                condition=Q(expression_sentiment__isnull=True)
                | Q(expression_sentiment__in=_values(Sentiment)),
                name="assessment_sentiment_valid",
            ),
            models.CheckConstraint(
                condition=Q(narrative_function__isnull=True)
                | Q(narrative_function__in=_values(NarrativeFunction)),
                name="assessment_narrative_valid",
            ),
            models.CheckConstraint(
                condition=Q(source__in=_values(AssessmentSource)), name="assessment_source_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(source="MACHINE")
                    & Q(supersedes__isnull=True)
                    & Q(reviewed_by__isnull=True)
                    & Q(review_reason="")
                )
                | (
                    Q(source="HUMAN")
                    & Q(supersedes__isnull=False)
                    & Q(reviewed_by__isnull=False)
                    & ~Q(review_reason="")
                ),
                name="assessment_source_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["analysis_run", "observation"], name="assessment_run_obs_idx")
        ]

    def __str__(self) -> str:
        return (
            f"{self.source} {self.issue_stance}/{self.target_alignment} obs {self.observation_id}"
        )


class ActorIssueProfile(AppendOnlyModel):
    """Profil aktivitas SATU akun pada satu platform, terikat issue/proposition, periode, dan
    AnalysisRun (WP-2.3; FR-060..FR-065). Level A saja: dibangun dari respons teramati pada target
    investigasi.

    Bukan label kepribadian, identitas orang, atau klasifikasi permanen. `coverage` WAJIB (tidak
    boleh kosong): menyatakan target, periode, pemeriksaan, dan keterbatasan sehingga profil tidak
    terbaca
    sebagai seluruh riwayat akun (FR-063, AT-17). Dimensi yang datanya kurang bernilai
    INSUFFICIENT_DATA.
    """

    analysis_run = models.ForeignKey(AnalysisRun, on_delete=models.PROTECT, related_name="profiles")
    source_run = models.ForeignKey(AnalysisRun, on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(ActorAccount, on_delete=models.PROTECT, related_name="+")
    proposition = models.ForeignKey(Proposition, on_delete=models.PROTECT, related_name="+")
    level = models.CharField(max_length=1, default="A")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    dimensions = models.JSONField()
    coverage = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["analysis_run_id", "actor_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis_run", "actor"], name="uniq_profile_per_actor"
            ),
            models.CheckConstraint(condition=Q(level="A"), name="profile_level_a_only"),
            models.CheckConstraint(
                condition=Q(period_end__gt=models.F("period_start")), name="profile_period_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"Profil Level {self.level} akun {self.actor_id} ({self.analysis_run_id})"


class GraphProjection(AppendOnlyModel):
    """Satu graf interaksi + tampilan stance untuk SATU platform pada satu AnalysisRun (WP-2.4).

    Menyimpan definisi node/edge, aturan bobot, jendela waktu, parameter, dan metrik struktur
    beserta seed dan versi pustaka (FR-074). Stance adalah atribut node/edge; stance sama tidak
    membuat edge.
    """

    analysis_run = models.OneToOneField(AnalysisRun, on_delete=models.PROTECT, related_name="graph")
    platform = models.CharField(max_length=20)
    definition = models.JSONField(help_text="Definisi node/edge, bobot, jendela, parameter.")
    metrics = models.JSONField(
        help_text="Metrik struktur + seed + versi; bukan penentu pengendali."
    )
    exclusions = models.JSONField(help_text="Relasi yang tidak masuk graf, per alasan.")
    node_count = models.PositiveIntegerField()
    edge_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="graph_platform_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"Graf [{self.platform}] {self.node_count} node, {self.edge_count} edge"


class GraphNode(AppendOnlyModel):
    projection = models.ForeignKey(GraphProjection, on_delete=models.PROTECT, related_name="nodes")
    actor = models.ForeignKey(ActorAccount, on_delete=models.PROTECT, related_name="+")
    attributes = models.JSONField(help_text="Atribut node, termasuk stance_counts (M2) bila ada.")
    metrics = models.JSONField(help_text="Derajat, betweenness, komunitas (struktur saja).")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["projection", "actor"], name="uniq_graph_node"),
        ]


class GraphEdge(AppendOnlyModel):
    projection = models.ForeignKey(GraphProjection, on_delete=models.PROTECT, related_name="edges")
    from_node = models.ForeignKey(GraphNode, on_delete=models.PROTECT, related_name="edges_out")
    to_node = models.ForeignKey(GraphNode, on_delete=models.PROTECT, related_name="edges_in")
    relation_type = models.CharField(max_length=12)
    weight = models.PositiveIntegerField()
    observation_ids = models.JSONField(
        help_text="Asal edge: ID observasi respons yang membentuknya."
    )
    stance_counts = models.JSONField(help_text="Stance respons pembentuk edge (atribut).")
    first_published_at = models.DateTimeField(null=True, blank=True)
    last_published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["projection", "from_node", "to_node", "relation_type"],
                name="uniq_graph_edge",
            ),
            models.CheckConstraint(
                condition=Q(relation_type__in=["reply_to", "quote_of", "repost_of", "mentions"]),
                name="graph_edge_type_valid",
            ),
            models.CheckConstraint(
                condition=~Q(from_node=models.F("to_node")), name="graph_edge_no_self"
            ),
            models.CheckConstraint(condition=Q(weight__gte=1), name="graph_edge_weight_positive"),
        ]
        indexes = [models.Index(fields=["projection", "relation_type"], name="graph_edge_type_idx")]


class CoordinationNetwork(AppendOnlyModel):
    """Behavioral Coordination Network untuk SATU platform pada satu AnalysisRun (WP-2.5; FR-072).

    Tabel dan tampilan terpisah dari Interaction Network: tepi di sini adalah INDIKATOR terhitung,
    bukan interaksi. Bukan Finding (FR-077): wajib ditinjau manusia dan dibandingkan dengan
    hipotesis alternatif. Menyimpan parameter eksplisit, baseline, dan pengecualian.
    """

    analysis_run = models.OneToOneField(
        AnalysisRun, on_delete=models.PROTECT, related_name="coordination"
    )
    platform = models.CharField(max_length=20)
    definition = models.JSONField(help_text="Parameter eksplisit, aturan indikator, dan catatan.")
    baseline = models.JSONField(help_text="Ringkasan baseline permutasi, atau NOT_COMPUTED.")
    exclusions = models.JSONField(help_text="Respons/peristiwa yang tidak dihitung, per alasan.")
    pair_summary = models.JSONField(
        help_text="Per pasangan: indikator dan kelompok bukti independen."
    )
    responses_considered = models.PositiveIntegerField()
    events = models.PositiveIntegerField()
    edge_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="coordination_platform_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"Koordinasi [{self.platform}] {self.edge_count} indikator"


class CoordinationEdge(AppendOnlyModel):
    """Satu indikator untuk satu pasangan akun (a < b): nilai, dukungan, bukti, baseline."""

    network = models.ForeignKey(CoordinationNetwork, on_delete=models.PROTECT, related_name="edges")
    actor_a = models.ForeignKey(ActorAccount, on_delete=models.PROTECT, related_name="+")
    actor_b = models.ForeignKey(ActorAccount, on_delete=models.PROTECT, related_name="+")
    indicator = models.CharField(max_length=5)
    variant = models.CharField(max_length=10, blank=True, default="")
    value = models.FloatField()
    support = models.PositiveIntegerField()
    observation_ids = models.JSONField(help_text="Bukti: ID observasi (dibatasi evidence_limit).")
    evidence_truncated = models.BooleanField(default=False)
    detail = models.JSONField()
    explanation = models.TextField()
    baseline = models.JSONField()
    overlaps_with = models.JSONField(help_text="Indikator lain yang berbagi bukti (dependen).")
    alternative_hypotheses = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["network", "actor_a", "actor_b", "indicator", "variant"],
                name="uniq_coordination_edge",
            ),
            models.CheckConstraint(
                condition=Q(indicator__in=["CO-01", "CO-02", "CO-03", "CO-04", "CO-05", "CO-06"]),
                name="coordination_indicator_valid",
            ),
            models.CheckConstraint(
                condition=(Q(indicator="CO-05") & Q(variant__in=["url", "phrase"]))
                | (~Q(indicator="CO-05") & Q(variant="")),
                name="coordination_variant_valid",
            ),
            models.CheckConstraint(
                condition=Q(actor_a__lt=models.F("actor_b")), name="coordination_pair_ordered"
            ),
            models.CheckConstraint(
                condition=Q(support__gte=1), name="coordination_support_positive"
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0), name="coordination_value_nonnegative"
            ),
        ]
        indexes = [models.Index(fields=["network", "indicator"], name="coordination_indicator_idx")]


class Finding(AppendOnlyModel):
    """Temuan analitik yang sudah ditinjau manusia (tingkat 4; PRD 11.5; FR-077..FR-080).

    Isi tidak dapat diubah setelah disegel; revisi = Finding baru yang menggantikan (`supersedes`),
    sehingga sejarah utuh. Siklus hidup (disahkan/ditarik) ada pada `FindingReview` append-only.
    Confidence BUKAN probabilitas akun adalah buzzer; teks dijaga dari vonis operasi berbayar/aktor
    pengendali. Tertaut ke observasi, AnalysisRun, dan indikator yang mendasarinya.
    """

    investigation = models.ForeignKey(
        Investigation, on_delete=models.PROTECT, related_name="findings"
    )
    platform = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    statement = models.TextField(help_text="Pola yang terobservasi, tanpa vonis.")
    interpretation = models.TextField(help_text="Interpretasi peninjau.")
    confidence = models.CharField(max_length=14)
    confidence_reason = models.TextField(help_text="Alasan confidence (wajib).")
    evidence_quality = models.JSONField(help_text="Empat sumbu bukti: level, alasan, saran sistem.")
    alternatives = models.JSONField(help_text="Pertimbangan hipotesis alternatif.")
    independent_evidence_groups = models.PositiveIntegerField(null=True, blank=True)
    synthetic_data = models.BooleanField(default=False)
    notice = models.TextField()
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="superseded_by"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    sealed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["investigation_id", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="finding_platform_valid"
            ),
            models.CheckConstraint(
                condition=Q(confidence__in=["HIGH", "MODERATE", "LOW", "NOT_ASSESSABLE"]),
                name="finding_confidence_valid",
            ),
            models.CheckConstraint(
                condition=~Q(statement="")
                & ~Q(interpretation="")
                & ~Q(confidence_reason="")
                & ~Q(title=""),
                name="finding_text_required",
            ),
            models.CheckConstraint(
                condition=Q(supersedes__isnull=True) | ~Q(supersedes=models.F("id")),
                name="finding_not_self_superseding",
            ),
        ]

    def __str__(self) -> str:
        return f"Temuan {self.pk}: {self.title}"


class FindingRun(AppendOnlyModel):
    """AnalysisRun (versi analisis) yang mendasari temuan."""

    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name="runs")
    analysis_run = models.ForeignKey(AnalysisRun, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["finding", "analysis_run"], name="uniq_finding_run"),
        ]


class FindingObservation(AppendOnlyModel):
    """Observasi (bukti tingkat 1) yang mendasari temuan; harus anggota dataset salah satu run."""

    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name="observations")
    observation = models.ForeignKey(PostObservation, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["finding", "observation"], name="uniq_finding_observation"
            ),
        ]


class FindingIndicator(AppendOnlyModel):
    """Indikator koordinasi (tingkat 3) yang ditinjau dan ditafsirkan oleh temuan."""

    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name="indicators")
    edge = models.ForeignKey(CoordinationEdge, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["finding", "edge"], name="uniq_finding_indicator"),
        ]


class ReviewAction(models.TextChoices):
    ENDORSE = "ENDORSE", "ENDORSE"
    WITHDRAW = "WITHDRAW", "WITHDRAW"


class FindingReview(AppendOnlyModel):
    """Pengesahan atau penarikan temuan oleh manusia. Append-only; satu per jenis aksi."""

    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name="reviews")
    action = models.CharField(max_length=8, choices=ReviewAction.choices)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    note = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["finding", "action"], name="uniq_finding_review_action"
            ),
            models.CheckConstraint(
                condition=Q(action__in=ReviewAction.values), name="finding_review_action_valid"
            ),
            models.CheckConstraint(condition=~Q(note=""), name="finding_review_note_required"),
        ]
