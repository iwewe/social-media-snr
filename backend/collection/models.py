"""Model inti pengumpulan data WP-1.2 (PRD bagian 8; FR-030, FR-031, FR-033, NFR-03, NFR-05).

Prinsip yang dijaga di tingkat DATABASE (trigger pada migrasi 0002), bukan hanya kode:
- Identitas unik per platform: Post (platform, external_post_id), ActorAccount (platform,
  external_actor_id). ID yang sama di platform lain adalah objek lain (AT-13).
- Observasi dan relasi append-only: pemeriksaan ulang menambah baris, tidak menimpa.
- Isolasi platform: observasi, relasi, dan identitas tidak boleh melintasi platform target run.
- Objek tanpa ID stabil dibuat sebagai kandidat `NEEDS_VERIFICATION`, tidak pernah digabung
  otomatis dan tidak ikut analisis sampai diverifikasi.
- InspectionRun adalah rujukan provenance: kolom identitasnya tidak dapat diubah dan run tidak
  dapat dihapus.

Satu Post dapat muncul di beberapa Investigation lewat run -> target -> investigation (PRD bagian
8, relasi 3), tanpa tabel penghubung dan tanpa menduplikasi identitas.
"""

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from collection.contracts.enums import CollectionStatus, SourceMethod, SourceObjectType
from investigations.enums import Platform
from investigations.models import CollectionTarget, Investigation

from .errors import AppendOnlyViolation


def _choices(enum_cls: Any) -> list[tuple[str, str]]:
    return [(m.value, m.value) for m in enum_cls]


class IdentityStatus(models.TextChoices):
    VERIFIED = "VERIFIED", "Terverifikasi"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION", "Perlu verifikasi identitas"


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


class RelationType(models.TextChoices):
    REPLY_TO = "reply_to", "Reply/comment ke"
    QUOTE_OF = "quote_of", "Kutipan dari"
    REPOST_OF = "repost_of", "Repost dari"
    MENTIONS = "mentions", "Menyebut akun"


class AppendOnlyModel(models.Model):
    """Baris hanya dapat dibuat. save() atas baris yang sudah ada dan delete() ditolak di kode;
    queryset.update()/delete() dan SQL langsung ditolak oleh trigger database."""

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AppendOnlyViolation(f"{type(self).__name__} bersifat append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise AppendOnlyViolation(f"{type(self).__name__} tidak dapat dihapus.")


# --- InspectionRun ---------------------------------------------------------------------------


class InspectionRun(models.Model):
    """Satu pelaksanaan pemeriksaan atas satu target (FR-020, FR-021). Pemeriksaan ulang menambah
    run baru, bukan target baru (AT-01). Kolom identitas tidak dapat diubah (trigger)."""

    # Dipakai sebagai `inspection_run_id` pada kontrak observasi (str).
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    target = models.ForeignKey(CollectionTarget, on_delete=models.PROTECT, related_name="runs")
    sequence = models.PositiveIntegerField(help_text="Urutan run per target: 1, 2, 3, ...")
    status = models.CharField(
        max_length=20, choices=RunStatus.choices, default=RunStatus.PENDING, db_index=True
    )
    requested = models.JSONField(help_text="Daftar kemampuan yang diminta (nilai Capability).")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Diisi saat run berjalan/selesai.
    source_method = models.CharField(
        max_length=30, choices=_choices(SourceMethod), blank=True, default=""
    )
    collector_name = models.CharField(max_length=100, blank=True, default="")
    collector_version = models.CharField(max_length=50, blank=True, default="")
    coverage = models.JSONField(null=True, blank=True)
    limitations = models.JSONField(default=list, blank=True)
    # Status ingestion (WP-1.3): None = belum pernah di-ingest; IN_PROGRESS = proses terputus bila
    # tidak pernah selesai; FINISHED / FINISHED_WITH_PROBLEMS + ringkasan laporan.
    ingestion = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["target_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["target", "sequence"], name="uniq_run_sequence"),
            models.CheckConstraint(condition=Q(sequence__gte=1), name="run_sequence_positive"),
            models.CheckConstraint(
                condition=Q(status__in=RunStatus.values), name="run_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(started_at__isnull=True)
                | Q(finished_at__isnull=True)
                | Q(finished_at__gte=F("started_at")),
                name="run_finished_after_started",
            ),
        ]

    def __str__(self) -> str:
        return f"Run {self.sequence} - {self.target}"

    @property
    def run_id(self) -> str:
        """Nilai `inspection_run_id` untuk kontrak observasi/adapter."""
        return str(self.public_id)


# --- identitas -------------------------------------------------------------------------------


class _IdentityQuerySet(models.QuerySet):
    def verified(self) -> "_IdentityQuerySet":
        """Hanya identitas terverifikasi; dipakai analisis (kandidat tidak ikut)."""
        return self.filter(identity_status=IdentityStatus.VERIFIED)


class PostQuerySet(_IdentityQuerySet):
    def observed_in_investigation(self, investigation: Investigation) -> "PostQuerySet":
        """Post yang teramati pada run target milik investigasi ini. Satu Post dapat muncul di
        banyak investigasi tanpa diduplikasi (PRD bagian 8, relasi 3)."""
        return self.filter(observations__run__target__investigation=investigation).distinct()


class ActorAccount(models.Model):
    """Identitas satu akun PADA SATU platform. Bukan orang (PRD bagian 5). Username/nama tampilan
    bukan identitas dan dicatat per observasi."""

    platform = models.CharField(max_length=20, choices=Platform.choices)
    # None hanya untuk kandidat yang perlu verifikasi; tidak pernah ditebak.
    external_actor_id = models.CharField(max_length=256, null=True, blank=True)  # noqa: DJ001 - NULL berarti 'tidak diketahui', beda dari string kosong
    identity_status = models.CharField(
        max_length=20, choices=IdentityStatus.choices, default=IdentityStatus.VERIFIED
    )
    first_seen_run = models.ForeignKey(
        InspectionRun, on_delete=models.PROTECT, related_name="+", help_text="Provenance."
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = _IdentityQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "external_actor_id"],
                condition=Q(external_actor_id__isnull=False),
                name="uniq_actor_per_platform",
            ),
            models.CheckConstraint(
                condition=Q(external_actor_id__isnull=False)
                | Q(identity_status=IdentityStatus.NEEDS_VERIFICATION),
                name="actor_id_or_needs_verification",
            ),
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="actor_platform_valid"
            ),
            models.CheckConstraint(
                condition=Q(identity_status__in=IdentityStatus.values),
                name="actor_identity_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.platform}] {self.external_actor_id or '(tanpa ID)'}"


class Post(models.Model):
    """Identitas tetap posting/komentar/media pada satu platform (PRD bagian 8)."""

    platform = models.CharField(max_length=20, choices=Platform.choices)
    external_post_id = models.CharField(max_length=256, null=True, blank=True)  # noqa: DJ001 - NULL berarti 'tidak diketahui', beda dari string kosong
    identity_status = models.CharField(
        max_length=20, choices=IdentityStatus.choices, default=IdentityStatus.VERIFIED
    )
    first_seen_run = models.ForeignKey(
        InspectionRun, on_delete=models.PROTECT, related_name="+", help_text="Provenance."
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = PostQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "external_post_id"],
                condition=Q(external_post_id__isnull=False),
                name="uniq_post_per_platform",
            ),
            models.CheckConstraint(
                condition=Q(external_post_id__isnull=False)
                | Q(identity_status=IdentityStatus.NEEDS_VERIFICATION),
                name="post_id_or_needs_verification",
            ),
            models.CheckConstraint(
                condition=Q(platform__in=Platform.values), name="post_platform_valid"
            ),
            models.CheckConstraint(
                condition=Q(identity_status__in=IdentityStatus.values),
                name="post_identity_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.platform}] {self.external_post_id or '(tanpa ID)'}"


# --- observasi dan relasi (append-only) ------------------------------------------------------


class PostObservation(AppendOnlyModel):
    """Kondisi satu Post pada satu InspectionRun (PRD bagian 8; FR-033, NFR-05).

    Satu baris per (Post, run). Pemeriksaan ulang menambah baris pada run baru; baris lama tidak
    diubah. Waktu publikasi (`published_at`), waktu pengamatan (`observed_at`), dan waktu
    penangkapan (`captured_at`) disimpan terpisah; `None` berarti tidak diketahui (PRD bagian 9.3).
    """

    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name="observations")
    run = models.ForeignKey(InspectionRun, on_delete=models.PROTECT, related_name="observations")
    author = models.ForeignKey(
        ActorAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="observations",
        help_text="None = penulis tidak diketahui.",
    )
    source_object_type = models.CharField(max_length=10, choices=_choices(SourceObjectType))
    collection_status = models.CharField(max_length=10, choices=_choices(CollectionStatus))
    text = models.TextField(  # noqa: DJ001 - NULL = tidak tersedia, beda dari teks kosong
        null=True, blank=True, help_text="None = tidak tersedia/teramati."
    )
    published_at = models.DateTimeField(null=True, blank=True)
    observed_at = models.DateTimeField()
    captured_at = models.DateTimeField(null=True, blank=True)
    actor_handle = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001 - NULL berarti 'tidak diketahui', beda dari string kosong
    actor_display_name = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001 - NULL berarti 'tidak diketahui', beda dari string kosong
    parent_unknown = models.BooleanField(default=False)
    identity_needs_verification = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["run_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["post", "run"], name="uniq_observation_per_run"),
            models.CheckConstraint(
                condition=Q(published_at__isnull=True) | ~Q(published_at=F("observed_at")),
                name="observation_published_not_observed",
            ),
            models.CheckConstraint(
                condition=Q(published_at__isnull=True) | Q(published_at__lte=F("observed_at")),
                name="observation_published_not_future",
            ),
            models.CheckConstraint(
                condition=Q(source_object_type__in=[m.value for m in SourceObjectType]),
                name="observation_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(collection_status__in=[m.value for m in CollectionStatus]),
                name="observation_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "source_object_type"], name="obs_run_type_idx"),
            models.Index(fields=["author", "run"], name="obs_author_run_idx"),
            models.Index(fields=["post", "-observed_at"], name="obs_post_time_idx"),
        ]

    def __str__(self) -> str:
        return f"Observasi {self.post} @ run {self.run_id}"


class PostRelation(AppendOnlyModel):
    """Relasi teramati pada satu run: reply_to, quote_of, repost_of, mentions (PRD bagian 8).

    Karena terikat run, riwayat relasi (mis. perubahan induk) otomatis tercatat per pemeriksaan.
    Sumber relasi (cara perolehan) adalah `run.source_method`.
    """

    run = models.ForeignKey(InspectionRun, on_delete=models.PROTECT, related_name="relations")
    from_post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name="relations_out")
    relation_type = models.CharField(max_length=12, choices=RelationType.choices)
    to_post = models.ForeignKey(
        Post, on_delete=models.PROTECT, null=True, blank=True, related_name="relations_in"
    )
    to_actor = models.ForeignKey(
        ActorAccount, on_delete=models.PROTECT, null=True, blank=True, related_name="mentions_in"
    )
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(relation_type__in=RelationType.values), name="relation_type_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(relation_type=RelationType.MENTIONS)
                    & Q(to_actor__isnull=False)
                    & Q(to_post__isnull=True)
                )
                | (
                    ~Q(relation_type=RelationType.MENTIONS)
                    & Q(to_post__isnull=False)
                    & Q(to_actor__isnull=True)
                ),
                name="relation_target_matches_type",
            ),
            models.CheckConstraint(
                condition=Q(to_post__isnull=True) | ~Q(to_post=F("from_post")),
                name="relation_not_self",
            ),
            models.UniqueConstraint(
                fields=["run", "from_post", "relation_type", "to_post"],
                condition=Q(to_post__isnull=False),
                name="uniq_relation_post",
            ),
            models.UniqueConstraint(
                fields=["run", "from_post", "relation_type", "to_actor"],
                condition=Q(to_actor__isnull=False),
                name="uniq_relation_actor",
            ),
            # Satu reply/comment hanya punya satu induk pada satu run.
            models.UniqueConstraint(
                fields=["run", "from_post"],
                condition=Q(relation_type=RelationType.REPLY_TO),
                name="uniq_single_parent_per_run",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "relation_type"], name="rel_run_type_idx"),
            models.Index(fields=["to_post", "relation_type"], name="rel_to_post_idx"),
            models.Index(fields=["from_post", "relation_type"], name="rel_from_post_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.from_post} {self.relation_type} {self.to_post or self.to_actor}"
