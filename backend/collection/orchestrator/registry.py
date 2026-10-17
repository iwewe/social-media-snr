"""Registri adapter per platform (FR-024).

Satu adapter per platform. Adapter nyata mendaftar sendiri (dataset uji WP-1.7, browser WP-1.8,
platform I3) atau lewat pengaturan `SNR_ADAPTERS` (daftar jalur titik ke kelas tanpa argumen).
Registri menyimpan PABRIK (callable) sehingga tiap eksekusi mendapat instans segar.
"""

from collections.abc import Callable
from importlib import import_module

from django.conf import settings

from collection.contracts import Adapter
from investigations.enums import Platform

AdapterFactory = Callable[[], Adapter]


class AdapterRegistryError(Exception):
    pass


class AdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, platform: Platform | str, factory: AdapterFactory) -> None:
        key = Platform(platform).value
        if key in self._factories:
            raise AdapterRegistryError(f"Sudah ada adapter terdaftar untuk platform {key}.")
        self._factories[key] = factory

    def unregister(self, platform: Platform | str) -> None:
        self._factories.pop(Platform(platform).value, None)

    def clear(self) -> None:
        self._factories.clear()

    def platforms(self) -> list[str]:
        return sorted(self._factories)

    def get(self, platform: Platform | str) -> Adapter | None:
        """Adapter baru untuk `platform`, atau None bila belum terdaftar."""
        key = Platform(platform).value
        factory = self._factories.get(key)
        if factory is None:
            return None
        adapter = factory()
        if adapter.platform.value != key:
            raise AdapterRegistryError(
                f"Adapter terdaftar untuk {key} ternyata menangani {adapter.platform.value}."
            )
        return adapter

    def load_from_settings(self) -> None:
        """Daftarkan kelas dari `settings.SNR_ADAPTERS` (jalur titik, tanpa argumen konstruktor)."""
        for dotted in getattr(settings, "SNR_ADAPTERS", []):
            module_path, _, class_name = dotted.rpartition(".")
            try:
                cls = getattr(import_module(module_path), class_name)
            except (ImportError, AttributeError, ValueError) as exc:
                raise AdapterRegistryError(f"Adapter tidak dapat dimuat: {dotted}") from exc
            self.register(cls.platform, cls)


registry = AdapterRegistry()
