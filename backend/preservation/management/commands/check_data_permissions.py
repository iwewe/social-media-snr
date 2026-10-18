"""`check_data_permissions [--backup-dir D]`: laporkan izin berkas yang terlalu longgar (PRD 13)."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from preservation import permissions
from preservation.storage import browser_profiles_root, evidence_root


class Command(BaseCommand):
    help = (
        "Periksa izin evidence (read-only, tertutup), browser-profiles dan backup (hanya pemilik)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--backup-dir", type=Path, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        problems = permissions.check_all(
            evidence_root(),
            browser_profiles_root(),
            options["backup_dir"],
        )
        for problem in problems:
            self.stderr.write(f"MASALAH: {problem}")
        if problems:
            raise CommandError(f"izin berkas tidak sesuai kebijakan: {len(problems)} masalah")
        self.stdout.write("izin berkas sesuai kebijakan")
