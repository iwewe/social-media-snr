from django.apps import AppConfig
from django.conf import settings


class CollectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "collection"

    def ready(self) -> None:
        from .orchestrator import registry

        registry.load_from_settings()
        if settings.SNR_FIXTURE_DATASETS_DIR is not None:
            from .datasets import register_fixture_adapters

            register_fixture_adapters(registry, settings.SNR_FIXTURE_DATASETS_DIR)
