from django.apps import AppConfig


class CollectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "collection"

    def ready(self) -> None:
        from .orchestrator import registry

        registry.load_from_settings()
