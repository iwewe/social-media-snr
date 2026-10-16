"""EvidenceArtifact (kerangka WP-1.2; manifest, provenance lengkap, dan penyaringan rahasia
ada pada WP-1.5). Basis data menyimpan indeks dan penunjuk berkas; berkas ada di filesystem lokal
lewat preservation.storage (PRD bagian 10, FR-038)."""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from collection.contracts.enums import ArtifactKind
from collection.models import AppendOnlyModel, InspectionRun, Post

from .storage import StoredFile, validate_relative_path


class EvidenceArtifact(AppendOnlyModel):
    """Artefak preservasi yang benar-benar tersimpan. Append-only: pemeriksaan baru menambah
    artefak, tidak mengganti yang lama (FR-039)."""

    run = models.ForeignKey(InspectionRun, on_delete=models.PROTECT, related_name="artifacts")
    post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="artifacts",
        help_text="Post yang menjadi sasaran artefak (mis. screenshot), bila ada.",
    )
    kind = models.CharField(max_length=20, choices=[(m.value, m.value) for m in ArtifactKind])
    relative_path = models.CharField(
        max_length=1024, unique=True, help_text="Relatif terhadap akar evidence."
    )
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=100)
    note = models.TextField(blank=True, default="")
    stored_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["run_id", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(sha256__regex=r"^[0-9a-f]{64}$"), name="artifact_sha256_format"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=[m.value for m in ArtifactKind]), name="artifact_kind_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["run", "kind"], name="artifact_run_kind_idx"),
            models.Index(fields=["post"], name="artifact_post_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.relative_path}"

    def save(self, *args: object, **kwargs: object) -> None:
        validate_relative_path(self.relative_path)  # tidak ada penunjuk keluar akar evidence
        self.sha256 = self.sha256.lower()
        super().save(*args, **kwargs)

    @classmethod
    def record(
        cls,
        *,
        run: InspectionRun,
        kind: ArtifactKind | str,
        stored: StoredFile,
        content_type: str,
        post: Post | None = None,
        note: str = "",
    ) -> "EvidenceArtifact":
        """Catat artefak yang sudah ditulis `preservation.storage.write_new`."""
        return cls.objects.create(
            run=run,
            post=post,
            kind=ArtifactKind(kind).value,
            relative_path=stored.relative_path,
            sha256=stored.sha256,
            size_bytes=stored.size,
            content_type=content_type,
            note=note,
        )
