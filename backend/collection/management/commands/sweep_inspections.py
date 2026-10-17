from typing import Any

from django.core.management.base import BaseCommand

from collection.orchestrator import sweep_stale_runs


class Command(BaseCommand):
    help = (
        "Tandai run RUNNING yang melewati batas waktu (pekerja mati/macet). Batas WAJIB diberikan."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--older-than", type=int, required=True, help="batas waktu dalam detik")

    def handle(self, *args: Any, **options: Any) -> None:
        swept = sweep_stale_runs(older_than_seconds=options["older_than"])
        self.stdout.write(f"{len(swept)} run ditandai: {swept}")
