from django.contrib import admin

from .models import EvidenceArtifact


@admin.register(EvidenceArtifact)
class EvidenceArtifactAdmin(admin.ModelAdmin):
    """Hanya lihat. Hash dan jalur adalah catatan provenance."""

    list_display = ("kind", "relative_path", "sha256", "run", "stored_at")
    list_filter = ("kind",)

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False
