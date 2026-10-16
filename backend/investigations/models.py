"""Model domain WP-0.4 (PRD bagian 8).

Aturan yang dijaga:
- Semua FK memakai PROTECT: riwayat tidak terhapus beruntun. Tidak ada jalur penghapusan di UI.
- Tabel versi (konteks issue, konteks target, stance target) append-only; dijaga trigger DB
  (migrasi 0002), bukan hanya kode aplikasi.
- Isi Proposition tidak dapat diubah. Koreksi = proposition baru, yang lama di-retire.
- Issue tidak memiliki stance: pro/kontra hanya dinilai terhadap Proposition (M1).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .enums import InitialStance, Platform, TargetType
from .errors import DomainError
from .target_urls import normalize_target_url


class _Authored(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True


class Investigation(_Authored):
    """Wadah aktivitas pemeriksaan dan analisis atas satu ruang masalah (FR-002, FR-003)."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Issue(_Authored):
    """Topik yang diteliti. Tidak diberi label pro/kontra; itu hanya untuk Proposition."""

    investigation = models.ForeignKey(
        Investigation, on_delete=models.PROTECT, related_name="issues"
    )
    title = models.CharField(max_length=200)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["investigation", "title"], name="uniq_issue_title"),
        ]

    def __str__(self) -> str:
        return self.title


class IssueContextVersion(_Authored):
    """Definisi/arahan konteks issue, berversi (FR-014). Append-only."""

    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="context_versions")
    version = models.PositiveIntegerField()
    definition = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["issue", "version"], name="uniq_issue_context_version"),
        ]

    def __str__(self) -> str:
        return f"{self.issue} v{self.version}"


class Proposition(_Authored):
    """Klaim spesifik yang menjadi acuan pro/kontra (M1). Isi tidak dapat diubah."""

    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="propositions")
    number = models.PositiveIntegerField(
        help_text="Nomor urut per issue, ditampilkan sebagai P1, P2."
    )
    statement = models.TextField()
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["issue_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["issue", "number"], name="uniq_proposition_number"),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.statement[:60]}"

    @property
    def label(self) -> str:
        return f"P{self.number}"


class CollectionTarget(_Authored):
    """URL posting atau akun yang sengaja dipilih untuk diperiksa (FR-011).

    Satu target dapat memiliki banyak InspectionRun (WP-1.2); pemeriksaan ulang tidak membuat
    target baru (AT-01).
    """

    investigation = models.ForeignKey(
        Investigation, on_delete=models.PROTECT, related_name="targets"
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    url = models.CharField(max_length=2000, help_text="URL sebagaimana dimasukkan pengguna.")
    normalized_url = models.CharField(max_length=2000, editable=False)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["investigation", "platform", "normalized_url"], name="uniq_target_url"
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.platform}] {self.normalized_url}"

    def save(self, *args: object, **kwargs: object) -> None:
        self.url = self.url.strip()
        self.normalized_url = normalize_target_url(self.platform, self.url)
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class TargetContextVersion(_Authored):
    """Catatan interpretasi target, berversi (FR-012, FR-014, FR-016). Append-only.

    `note` adalah panduan interpretasi analis, bukan instruksi agar mesin memaksakan label.
    """

    target = models.ForeignKey(
        CollectionTarget, on_delete=models.PROTECT, related_name="context_versions"
    )
    version = models.PositiveIntegerField()
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "version"], name="uniq_target_context_version"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target} v{self.version}"


class TargetPropositionStance(models.Model):
    """Posisi awal target terhadap satu proposition pada satu versi konteks (FR-013, FR-015)."""

    context_version = models.ForeignKey(
        TargetContextVersion, on_delete=models.PROTECT, related_name="stances"
    )
    proposition = models.ForeignKey(Proposition, on_delete=models.PROTECT, related_name="+")
    stance = models.CharField(max_length=12, choices=InitialStance.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["context_version", "proposition"], name="uniq_target_stance"
            ),
            models.CheckConstraint(
                condition=models.Q(stance__in=InitialStance.values), name="target_stance_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.proposition.label}: {self.stance}"

    def clean(self) -> None:
        target_investigation = self.context_version.target.investigation_id
        if self.proposition.issue.investigation_id != target_investigation:
            raise DomainError("Proposition harus berasal dari investigasi yang sama dengan target.")
