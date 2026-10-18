"""`restore_check snapshot --out F` (sumber), `restore_check verify --expect F` (restore)."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from preservation import restore_check


class Command(BaseCommand):
    help = "Rekam snapshot sistem atau verifikasi hasil restore terhadap snapshot sumber (NFR-10)."

    def add_arguments(self, parser: Any) -> None:
        sub = parser.add_subparsers(dest="action", required=True)
        snap = sub.add_parser("snapshot")
        snap.add_argument("--out", type=Path, required=True)
        ver = sub.add_parser("verify")
        ver.add_argument("--expect", type=Path, required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        if options["action"] == "snapshot":
            data = restore_check.snapshot()
            options["out"].write_text(json.dumps(data, indent=2, sort_keys=True))
            self.stdout.write(
                f"snapshot: {sum(data['counts'].values())} baris, "
                f"{data['artifacts']['count']} artefak"
            )
            return
        expected = json.loads(options["expect"].read_text())
        result = restore_check.verify(expected)
        for warning in result["warnings"]:
            self.stdout.write(f"PERINGATAN: {warning}")
        if not result["ok"]:
            for problem in result["problems"]:
                self.stderr.write(f"MASALAH: {problem}")
            raise CommandError(f"restore tidak lolos: {len(result['problems'])} masalah")
        self.stdout.write(
            f"restore lolos: {result['artifacts_checked']} artefak cocok, jumlah baris sama"
        )
