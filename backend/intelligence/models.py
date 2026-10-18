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
