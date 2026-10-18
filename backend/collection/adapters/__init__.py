"""Adapter per platform (I3); semuanya DINONAKTIFKAN (lihat pending.py, docs/adapters/)."""

from collection.orchestrator.registry import AdapterRegistry

from .facebook import FacebookAdapter
from .instagram import InstagramAdapter
from .pending import PendingPermissionAdapter
from .threads import ThreadsAdapter
from .tiktok import TikTokAdapter
from .x import XAdapter

DISABLED_ADAPTERS: tuple[type[PendingPermissionAdapter], ...] = (
    XAdapter,
    ThreadsAdapter,
    TikTokAdapter,
    InstagramAdapter,
    FacebookAdapter,
)


def register_disabled_adapters(registry: AdapterRegistry) -> list[str]:
    """Daftarkan adapter nonaktif HANYA untuk platform yang belum punya adapter (dataset,
    simulasi, atau SNR_ADAPTERS tetap menang), agar UI menampilkan alasan keterbatasan."""
    added: list[str] = []
    for adapter in DISABLED_ADAPTERS:
        if adapter.platform.value not in registry.platforms():
            registry.register(adapter.platform, adapter)
            added.append(adapter.platform.value)
    return added
