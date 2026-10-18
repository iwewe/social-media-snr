"""`pilot_metrics [--json]`: metrik pilot (kelengkapan, kegagalan parser, durasi, penyimpanan)."""

import json
from typing import Any

from django.core.management.base import BaseCommand

from intelligence.pilot import pilot_metrics


class Command(BaseCommand):
    help = "Cetak metrik pilot (WP-4.1). Tanpa target lulus: hanya angka dan sumbernya."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--json", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        report = pilot_metrics()
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))
            return
        self.stdout.write(report["notice"])
        for name, p in report["platforms"].items():
            ratio = p["observed_vs_displayed"]
            self.stdout.write(
                f"{name}: {p['runs']} run {p['outcomes']}; teramati/ditampilkan "
                f"{p['observed']}/{p['displayed']}"
                + ("" if ratio is None else f" ({ratio:.0%})")
                + f"; paginasi tak lengkap {p['pagination_incomplete']}; gagal parser "
                f"{p['parse_failures']}; tidak didukung {p['unsupported']}"
            )
        s = report["storage"]
        self.stdout.write(
            f"penyimpanan: evidence {s['evidence_bytes']} bita ({s['artifact_rows']} artefak); "
            f"database {s['database_bytes']} bita"
        )
        self.stdout.write(f"uji restore: {report['restore_test']}")
