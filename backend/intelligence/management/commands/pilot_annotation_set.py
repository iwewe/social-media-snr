"""`pilot_annotation_set --run ID --out DIR --annotators A B [--n 60 --seed 1]` (WP-4.1)."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from intelligence import pilot
from intelligence.models import AnalysisRun


class Command(BaseCommand):
    help = (
        "Buat set anotasi pilot dari satu run M2: lembar anotator (tanpa label mesin), prediksi "
        "mesin asli, dan manifest. Berisi teks nyata: simpan di luar Git dan batasi aksesnya."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--run", type=int, required=True, help="id AnalysisRun M2 selesai")
        parser.add_argument("--out", type=Path, required=True)
        parser.add_argument("--annotators", nargs="+", required=True)
        parser.add_argument("--n", type=int, default=60)
        parser.add_argument(
            "--seed", type=int, required=True, help="wajib: pengambilan contoh dapat diulang"
        )
        parser.add_argument("--proposition", type=int, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        run = (
            AnalysisRun.objects.filter(pk=options["run"], status="COMPLETED")
            .select_related("dataset_version")
            .first()
        )
        if run is None:
            raise CommandError("AnalysisRun tidak ditemukan atau belum selesai.")
        try:
            bundle = pilot.build_annotation_set(
                run,
                n=options["n"],
                seed=options["seed"],
                annotators=options["annotators"],
                proposition_id=options["proposition"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        out: Path = options["out"]
        out.mkdir(parents=True, exist_ok=True, mode=0o700)
        out.chmod(0o700)
        for name, key in (
            ("sheet.json", "sheet"),
            ("predictions.json", "predictions"),
            ("manifest.json", "manifest"),
        ):
            path = out / name
            path.write_text(json.dumps(bundle[key], indent=2, ensure_ascii=False), encoding="utf-8")
            path.chmod(0o600)
        manifest = bundle["manifest"]
        self.stdout.write(
            f"{manifest['selected']} item ditulis ke {out}"
            + (
                " (di bawah ukuran pilot yang disarankan)"
                if manifest["below_recommended_size"]
                else ""
            )
        )
