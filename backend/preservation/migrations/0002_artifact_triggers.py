"""Trigger PostgreSQL untuk EvidenceArtifact (WP-1.2): append-only dan isolasi platform."""

from django.db import migrations

FORWARD = """
CREATE TRIGGER evidence_artifact_append_only
    BEFORE UPDATE OR DELETE ON preservation_evidenceartifact
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_artifact_platform_guard() RETURNS trigger AS $$
DECLARE
    post_platform text;
BEGIN
    IF NEW.post_id IS NOT NULL THEN
        SELECT platform INTO post_platform FROM collection_post WHERE id = NEW.post_id;
        IF post_platform IS DISTINCT FROM snr_run_platform(NEW.run_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'artefak untuk post platform lain pada run ini ditolak';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER evidence_artifact_platform_guard
    BEFORE INSERT ON preservation_evidenceartifact
    FOR EACH ROW EXECUTE FUNCTION snr_artifact_platform_guard();
"""

REVERSE = """
DROP TRIGGER evidence_artifact_platform_guard ON preservation_evidenceartifact;
DROP FUNCTION snr_artifact_platform_guard();
DROP TRIGGER evidence_artifact_append_only ON preservation_evidenceartifact;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("preservation", "0001_initial"),
        ("collection", "0002_isolation_and_append_only_triggers"),
        ("investigations", "0002_append_only_triggers"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
