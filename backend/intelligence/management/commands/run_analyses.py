"""Jalankan rangkaian analisis I2 (M2, M3, M4, indikator koordinasi) untuk satu investigasi.

Alat OPERATOR untuk pengembangan, demonstrasi, dan uji (analisis belum dapat dipicu dari UI).
Setiap analisis tetap menyimpan parameternya secara eksplisit di AnalysisRun; opsi `--exploratory`
hanya mengisi nilai CONTOH (ADR 0024: tidak ada ambang baku) dan WAJIB diberikan agar tidak ada
nilai yang dianggap ambang koordinasi secara diam-diam. Cue stance proposition ditulis analis.
"""

from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from collection.models import InspectionRun, PostObservation
from intelligence import coordination_runs, profiles, services
from intelligence.errors import AnalysisError
from intelligence.examples import CO_EXAMPLE, EXPLORATORY_NOTE
from intelligence.m2.example_rules import example_parameters
from intelligence.models import AnalysisRun
from intelligence.networks import network_parameters
from investigations.models import Investigation, Proposition


class Command(BaseCommand):
    help = "Jalankan M2, M3, M4, dan indikator koordinasi (nilai contoh) untuk satu investigasi."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--investigation", type=int, required=True)
        parser.add_argument("--proposition", type=int, required=True)
        parser.add_argument("--user", required=True, help="username pembuat run")
        parser.add_argument("--platform", default="x")
        parser.add_argument(
            "--pro-cue", action="append", default=[], help="frasa pro (ulangi opsi)"
        )
        parser.add_argument(
            "--contra-cue", action="append", default=[], help="frasa kontra (ulangi opsi)"
        )
        parser.add_argument(
            "--exploratory", action="store_true", help="akui bahwa nilai contoh dipakai"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["exploratory"]:
            raise CommandError(
                "Tambahkan --exploratory untuk mengakui bahwa nilai parameter lain adalah CONTOH. "
                + EXPLORATORY_NOTE
            )
        if not options["pro_cue"] and not options["contra_cue"]:
            raise CommandError(
                "Isi minimal satu --pro-cue atau --contra-cue (ditulis analis, tanpa bawaan)."
            )
        investigation = Investigation.objects.filter(pk=options["investigation"]).first()
        proposition = (
            Proposition.objects.filter(
                pk=options["proposition"], issue__investigation_id=options["investigation"]
            )
            .select_related("issue")
            .first()
        )
        user = get_user_model().objects.filter(username=options["user"], is_active=True).first()
        if investigation is None or proposition is None or user is None:
            raise CommandError(
                "Investigasi, proposition (pada investigasi itu), atau pengguna tidak ditemukan."
            )
        runs = [
            r
            for r in InspectionRun.objects.filter(
                target__investigation=investigation, target__platform=options["platform"]
            ).order_by("target_id", "sequence")
            if isinstance(r.ingestion, dict)
            and r.ingestion.get("state") in ("FINISHED", "FINISHED_WITH_PROBLEMS")
        ]
        runs = [r for r in runs if PostObservation.objects.filter(run=r).exists()]
        if not runs:
            raise CommandError(
                "Tidak ada pemeriksaan ter-ingest dengan observasi untuk platform itu."
            )
        self.stdout.write(EXPLORATORY_NOTE)
        try:
            dataset = services.create_dataset_version(
                investigation=investigation, runs=runs, by=user, note="run_analyses"
            )
            times: list[datetime] = [
                t
                for t in PostObservation.objects.filter(run__in=runs).values_list(
                    "published_at", flat=True
                )
                if t is not None
            ]
            if times:
                start, end = min(times) - timedelta(days=1), max(times) + timedelta(days=1)
            else:
                anchor = runs[-1].created_at
                start, end = anchor - timedelta(days=1), anchor + timedelta(days=1)
            issue = proposition.issue

            def run(method: str, parameters: dict[str, Any]) -> AnalysisRun:
                created = services.create_analysis_run(
                    dataset=dataset,
                    method=method,
                    parameters=parameters,
                    by=user,
                    issue_context_version=services.latest_issue_context(issue),
                    target_context_versions=services.latest_target_contexts(dataset),
                )
                done = services.execute_run(created)
                self.stdout.write(
                    f"{method}: run {done.pk} {done.status}"
                    + (f" ({done.error})" if done.error else "")
                )
                return done

            m2 = run(
                "m2-rules",
                example_parameters({proposition.pk: (options["pro_cue"], options["contra_cue"])}),
            )
            if m2.status == "COMPLETED":
                run(
                    "m3-profile",
                    profiles.m3_parameters(
                        source_run=m2,
                        proposition=proposition,
                        period_start=start,
                        period_end=end,
                        min_responses=2,
                        bucket_hours=24,
                        min_active_buckets=2,
                        narrative_min_texts=2,
                    ),
                )
                run(
                    "m4-network",
                    network_parameters(
                        window_start=start,
                        window_end=end,
                        unknown_time="include",
                        relation_types=["reply_to", "quote_of", "repost_of", "mentions"],
                        weighting="count",
                        resolution=1.0,
                        seed=1,
                        compute_betweenness=True,
                        metrics_max_nodes=1000,
                        stability_seeds=10,
                        source_run=m2,
                        proposition=proposition,
                    ),
                )
            run(
                "co-indicators",
                coordination_runs.coordination_parameters(
                    window_start=start, window_end=end, **CO_EXAMPLE
                ),
            )
        except AnalysisError as exc:
            raise CommandError(str(exc)) from exc
