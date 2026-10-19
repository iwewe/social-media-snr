"""Jejak audit perubahan konteks, klasifikasi, dan temuan (WP-2.8; PRD bagian 8 `AuditEvent`).

Satu baris per perubahan: siapa, kapan, apa, nilai sebelum dan sesudah, alasan. Baris hanya dapat
ditambahkan (trigger DB, migrasi 0002). Rujukan ke objek memakai (subject_type, subject_id) tanpa FK
agar app ini tidak bergantung pada app yang dicatatnya.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from collection.models import AppendOnlyModel


class AuditAction(models.TextChoices):
    ISSUE_CONTEXT = "ISSUE_CONTEXT", "Konteks issue"
    TARGET_CONTEXT = "TARGET_CONTEXT", "Konteks target"
    CLASSIFICATION_REVIEW = "CLASSIFICATION_REVIEW", "Tinjauan klasifikasi"
    FINDING_DRAFT = "FINDING_DRAFT", "Temuan dibuat"
    FINDING_REVISE = "FINDING_REVISE", "Temuan direvisi"
    FINDING_ENDORSE = "FINDING_ENDORSE", "Temuan disahkan"
    FINDING_WITHDRAW = "FINDING_WITHDRAW", "Temuan ditarik"
    ANALYSIS_RUN = "ANALYSIS_RUN", "Analisis dijalankan"


class SubjectType(models.TextChoices):
    ISSUE = "issue", "Issue"
    TARGET = "target", "Target"
    RESPONSE_ASSESSMENT = "response_assessment", "Klasifikasi respons"
    FINDING = "finding", "Temuan"
    ANALYSIS_RUN = "analysis_run", "Analisis"


class AuditEvent(AppendOnlyModel):
    investigation = models.ForeignKey(
        "investigations.Investigation", on_delete=models.PROTECT, related_name="+"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    subject_type = models.CharField(max_length=30, choices=SubjectType.choices)
    subject_id = models.PositiveBigIntegerField()
    before = models.JSONField(
        null=True, blank=True, help_text="Keadaan sebelum; null = baru dibuat."
    )
    after = models.JSONField(help_text="Keadaan sesudah.")
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["investigation", "-id"], name="audit_inv_idx"),
            models.Index(fields=["subject_type", "subject_id"], name="audit_subject_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.subject_type}#{self.subject_id}"
