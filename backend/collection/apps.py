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
        if settings.SNR_SIMULATION_BASE_URL is not None:
            from .browser import register_simulated_adapter

            register_simulated_adapter(
                registry, settings.SNR_SIMULATION_BASE_URL, settings.SNR_SIMULATION_PLATFORM
            )
