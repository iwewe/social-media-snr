"""Pengukuran durasi run pada adapter yang ada (A1). Dijalankan lewat deployment/measure.sh pada
database sementara. Hasil dari simulasi/dataset sintetis BUKAN dasar untuk platform nyata; skrip ini
hanya memberi pegangan awal dan memperlihatkan cara memperoleh angka (`inspection_durations`)."""

import json
import os
import sys
import tempfile
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collection.browser import register_simulated_adapter  # noqa: E402
from collection.contracts import Capability  # noqa: E402
from collection.datasets import register_fixture_adapters  # noqa: E402
from collection.durations import duration_report  # noqa: E402
from collection.orchestrator import registry, request_inspection, run_inspection  # noqa: E402
from collection.simulation import SimulationServer  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from investigations import services as inv_services  # noqa: E402
from investigations.enums import Platform, TargetType  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
EVIDENCE = [Capability.INSPECT_POST, Capability.INSPECT_REPLIES,
            Capability.PRESERVE_SCREENSHOT, Capability.PRESERVE_DOM]


def main() -> None:
    work = Path(tempfile.mkdtemp())
    (work / "ds").mkdir()
    url_ig = "https://instagram.com/p/UjiDurasi/"
    snapshot = {"observed_at": "2026-10-16T01:00:00Z", "outcome": "COMPLETED",
                "pagination_complete": True, "displayed_count": 1,
                "observations": [{"type": "post", "id": "UjiDurasi", "actor": "a1", "text": "awal"},
                                 {"type": "comment", "id": "c1", "actor": "a2", "parent": "UjiDurasi",
                                  "text": "komentar"}]}
    (work / "ds" / "ig.json").write_text(json.dumps({
        "schema_version": 1, "name": "durasi", "platform": "instagram", "target_url": url_ig,
        "source_method": "synthetic_fixture", "snapshots": [snapshot] * N}))

    user = User.objects.create_user("pengukur", password="tidak-dipakai-" + os.urandom(4).hex())
    inv = inv_services.create_investigation(user=user, name="Pengukuran durasi")

    def target(platform, url):
        return inv_services.register_target(investigation=inv, user=user, platform=platform,
                                            target_type=TargetType.POST, url=url)

    def go(tgt, times, caps=None):
        for _ in range(times):
            run = request_inspection(target=tgt, user=user, requested=caps, enqueue=False)
            run_inspection(run.pk)

    with SimulationServer() as sim:
        registry.clear()
        register_simulated_adapter(registry, sim.base_url, Platform.X)
        register_fixture_adapters(registry, work / "ds", [Platform.INSTAGRAM])
        go(target(Platform.X, "https://x.com/u/status/1001"), N)              # lengkap
        go(target(Platform.X, "https://x.com/u/status/1004"), N // 2 + 1, EVIDENCE)  # + bukti
        go(target(Platform.X, "https://x.com/u/status/1002"), N // 2)          # pagination putus
        go(target(Platform.X, "https://x.com/u/status/1003"), N // 2)          # akses ditolak
        go(target(Platform.INSTAGRAM, url_ig), N)                              # dataset
    print(json.dumps(duration_report(), indent=2))


if __name__ == "__main__":
    main()
