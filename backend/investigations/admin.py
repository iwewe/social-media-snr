from django.contrib import admin

from . import models


class ReadOnlyAdmin(admin.ModelAdmin):
    """Untuk tabel append-only: hanya lihat. Pembuatan lewat services (jalur terversi)."""

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False


@admin.register(models.Investigation)
class InvestigationAdmin(ReadOnlyAdmin):
    list_display = ("name", "created_by", "created_at")


@admin.register(models.Issue)
class IssueAdmin(ReadOnlyAdmin):
    list_display = ("title", "investigation", "created_at")


@admin.register(models.Proposition)
class PropositionAdmin(ReadOnlyAdmin):
    list_display = ("label", "statement", "issue", "retired_at")


@admin.register(models.CollectionTarget)
class CollectionTargetAdmin(ReadOnlyAdmin):
    list_display = ("platform", "target_type", "normalized_url", "investigation")
    list_filter = ("platform", "target_type")


@admin.register(models.IssueContextVersion, models.TargetContextVersion)
class ContextVersionAdmin(ReadOnlyAdmin):
    list_display = ("__str__", "version", "created_by", "created_at")
