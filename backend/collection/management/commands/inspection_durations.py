import json
from typing import Any

from django.core.management.base import BaseCommand

from collection.durations import duration_report


class Command(BaseCommand):
    help = (
        "Ringkas durasi run per pengambil data (min/p50/p95/max) sebagai dasar menetapkan batas "
        "waktu penyapu dan soft time limit. Hasil dari dataset/simulasi bukan dasar platform nyata."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--json", action="store_true", help="keluaran JSON")

    def handle(self, *args: Any, **options: Any) -> None:
        report = duration_report()
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return
        if not report:
            self.stdout.write("Belum ada run selesai yang dapat diukur.")
            return
        for row in report:
            if row["n"] == 0:
                self.stdout.write(
                    f"{row['collector']}: belum ada run selesai (disapu: {row['swept']})"
                )
                continue
            ex, qw = row["execution_seconds"], row["queue_wait_seconds"]
            self.stdout.write(
                f"{row['collector']}: n={row['n']} disapu={row['swept']}\n"
                f"  eksekusi (detik): min={ex['min']:.2f} p50={ex['p50']:.2f} "
                f"p95={ex['p95']:.2f} max={ex['max']:.2f}\n"
                f"  tunggu antrean (detik): min={qw['min']:.2f} p50={qw['p50']:.2f} "
                f"p95={qw['p95']:.2f} max={qw['max']:.2f}"
            )
