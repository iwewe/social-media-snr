"""Model dasar analisis I2 (WP-2.1; ADR 0025; PRD bagian 8, NFR-01, FR-014, FR-041).

DatasetVersion membekukan himpunan observasi sebagai input analisis (daftar ID tak-berubah + hash).
AnalysisRun menautkan DatasetVersion, versi konteks, parameter eksplisit, dan versi metode; setelah
dibuat, semua masukan itu tidak dapat diubah (trigger database, migrasi 0002). Revisi
konteks atau data
baru tidak mengubah run lama (AT-07); analisis ulang membuat DatasetVersion dan AnalysisRun baru.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from collection.models import AppendOnlyModel, PostObservation
from investigations.enums import Platform
from investigations.models import (
    CollectionTarget,
    Investigation,
    IssueContextVersion,
    TargetContextVersion,
)

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
