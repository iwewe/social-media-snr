from django.contrib import admin

from . import models


class ReadOnlyAdmin(admin.ModelAdmin):
    """Data pengumpulan bersifat provenance: hanya lihat; dibuat lewat layanan/orchestrator."""

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False


@admin.register(models.InspectionRun)
class InspectionRunAdmin(ReadOnlyAdmin):
    list_display = ("target", "sequence", "status", "created_at", "finished_at")
    list_filter = ("status",)


@admin.register(models.Post, models.ActorAccount)
class IdentityAdmin(ReadOnlyAdmin):
    list_display = ("__str__", "platform", "identity_status", "created_at")
    list_filter = ("platform", "identity_status")


@admin.register(models.PostObservation, models.PostRelation, models.ObservationReconciliation)
class ObservationAdmin(ReadOnlyAdmin):
    list_display = ("__str__", "run")
