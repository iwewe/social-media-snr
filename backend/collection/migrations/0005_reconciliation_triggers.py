"""Trigger PostgreSQL untuk ObservationReconciliation (WP-1.4): append-only dan integritas rujukan.

Memastikan di tingkat database bahwa: observasi 'saat ini' memang milik post dan run yang sama;
observasi 'pembanding' milik post yang sama dan berasal dari run SEBELUMNYA pada target yang
SAMA; dan platform post sama dengan platform run (NFR-06).
"""

from django.db import migrations

FORWARD = """
CREATE TRIGGER observation_reconciliation_append_only
    BEFORE UPDATE OR DELETE ON collection_observationreconciliation
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_reconciliation_guard() RETURNS trigger AS $$
DECLARE
    run_seq integer;
    run_target bigint;
    post_platform text;
    o_post bigint;
    o_run bigint;
    p_post bigint;
    p_target bigint;
    p_seq integer;
BEGIN
    SELECT sequence, target_id INTO run_seq, run_target
        FROM collection_inspectionrun WHERE id = NEW.run_id;
    SELECT platform INTO post_platform FROM collection_post WHERE id = NEW.post_id;
    IF post_platform IS DISTINCT FROM snr_run_platform(NEW.run_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'rekonsiliasi untuk post platform lain pada run ini ditolak';
    END IF;
    IF NEW.current_observation_id IS NOT NULL THEN
        SELECT post_id, run_id INTO o_post, o_run
            FROM collection_postobservation WHERE id = NEW.current_observation_id;
        IF o_post IS DISTINCT FROM NEW.post_id OR o_run IS DISTINCT FROM NEW.run_id THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'observasi saat ini harus milik post dan run yang direkonsiliasi';
        END IF;
    END IF;
    IF NEW.previous_observation_id IS NOT NULL THEN
        SELECT o.post_id, r.target_id, r.sequence INTO p_post, p_target, p_seq
            FROM collection_postobservation o
            JOIN collection_inspectionrun r ON r.id = o.run_id
            WHERE o.id = NEW.previous_observation_id;
        IF p_post IS DISTINCT FROM NEW.post_id OR p_target IS DISTINCT FROM run_target
           OR p_seq >= run_seq THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'observasi pembanding harus dari run sebelumnya pada target yang sama';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER observation_reconciliation_guard
    BEFORE INSERT ON collection_observationreconciliation
    FOR EACH ROW EXECUTE FUNCTION snr_reconciliation_guard();
"""

REVERSE = """
DROP TRIGGER observation_reconciliation_guard ON collection_observationreconciliation;
DROP FUNCTION snr_reconciliation_guard();
DROP TRIGGER observation_reconciliation_append_only ON collection_observationreconciliation;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("collection", "0004_reconciliation"),
        ("investigations", "0002_append_only_triggers"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
