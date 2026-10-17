"""Stabilitas rencana query pada trigger artefak (A2; ADR 0020). Lihat collection 0010."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("preservation", "0004_artifact_verification")]
    operations = [
        migrations.RunSQL(
            "ALTER FUNCTION snr_artifact_platform_guard() SET enable_seqscan = off;",
            "ALTER FUNCTION snr_artifact_platform_guard() RESET enable_seqscan;",
        )
    ]
