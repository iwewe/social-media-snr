"""Enum model pengumpulan data yang dipakai lintas modul (tanpa impor model)."""

from django.db import models


class RunStatus(models.TextChoices):
    """Status InspectionRun (PRD bagian 9.1). Tabel transisi diuji pada WP-1.6."""

    PENDING = "PENDING", "PENDING"
    RUNNING = "RUNNING", "RUNNING"
    COMPLETED = "COMPLETED", "COMPLETED"
    PARTIAL = "PARTIAL", "PARTIAL"
    FAILED = "FAILED", "FAILED"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED", "ACCESS_RESTRICTED"
    UNSUPPORTED = "UNSUPPORTED", "UNSUPPORTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED", "REVIEW_REQUIRED"
