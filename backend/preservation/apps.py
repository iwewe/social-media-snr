from django.apps import AppConfig


class PreservationConfig(AppConfig):
    name = "preservation"

    def ready(self) -> None:
        from . import checks  # noqa: F401  (mendaftarkan system check)
