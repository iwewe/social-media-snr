"""AuditEvent hanya dapat ditambahkan (WP-2.8): UPDATE dan DELETE ditolak trigger, termasuk SQL langsung."""

from django.db import migrations

FORWARD = """
CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit_auditevent
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""
REVERSE = "DROP TRIGGER IF EXISTS audit_event_append_only ON audit_auditevent;"


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("collection", "0002_isolation_and_append_only_triggers"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
