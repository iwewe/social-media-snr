"""Trigger PostgreSQL untuk model inti pengumpulan data (WP-1.2).

- Observasi dan relasi append-only (memakai snr_forbid_modification dari investigations 0002).
- InspectionRun: kolom identitas tidak dapat diubah, run tidak dapat dihapus.
- Post/ActorAccount: platform, ID sumber (setelah terisi), provenance, dan status terverifikasi
  tidak dapat diubah; hanya ID NULL -> terisi dan NEEDS_VERIFICATION -> VERIFIED yang diizinkan.
- ISOLASI PLATFORM di DB: identitas, observasi, dan relasi harus memiliki platform yang sama dengan
  target run-nya (AT-13, NFR-06, FR-024).

Catatan: TRUNCATE tidak diblokir; pemilik DB/superuser masih dapat menghapus trigger.
"""

from django.db import migrations

FORWARD = """
CREATE TRIGGER post_observation_append_only
    BEFORE UPDATE OR DELETE ON collection_postobservation
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER post_relation_append_only
    BEFORE UPDATE OR DELETE ON collection_postrelation
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_run_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'InspectionRun tidak dapat dihapus';
    END IF;
    IF NEW.public_id <> OLD.public_id OR NEW.target_id <> OLD.target_id
       OR NEW.sequence <> OLD.sequence OR NEW.requested::text <> OLD.requested::text
       OR NEW.requested_by_id <> OLD.requested_by_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'kolom identitas InspectionRun tidak dapat diubah';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER inspection_run_guard
    BEFORE UPDATE OR DELETE ON collection_inspectionrun
    FOR EACH ROW EXECUTE FUNCTION snr_run_guard();

CREATE FUNCTION snr_identity_guard() RETURNS trigger AS $$
DECLARE
    col text := TG_ARGV[0];
    old_id text;
    new_id text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'identitas tidak dapat dihapus';
    END IF;
    old_id := to_jsonb(OLD) ->> col;
    new_id := to_jsonb(NEW) ->> col;
    IF NEW.platform <> OLD.platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'platform identitas tidak dapat diubah';
    END IF;
    IF old_id IS NOT NULL AND new_id IS DISTINCT FROM old_id THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'ID sumber tidak dapat diubah setelah terisi';
    END IF;
    IF NEW.first_seen_run_id <> OLD.first_seen_run_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'provenance identitas tidak dapat diubah';
    END IF;
    IF OLD.identity_status = 'VERIFIED' AND NEW.identity_status <> 'VERIFIED' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'status verifikasi identitas tidak dapat dicabut';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER post_identity_guard
    BEFORE UPDATE OR DELETE ON collection_post
    FOR EACH ROW EXECUTE FUNCTION snr_identity_guard('external_post_id');
CREATE TRIGGER actor_identity_guard
    BEFORE UPDATE OR DELETE ON collection_actoraccount
    FOR EACH ROW EXECUTE FUNCTION snr_identity_guard('external_actor_id');

CREATE FUNCTION snr_run_platform(run_pk bigint) RETURNS text AS $$
    SELECT t.platform
    FROM collection_inspectionrun r
    JOIN investigations_collectiontarget t ON t.id = r.target_id
    WHERE r.id = run_pk
$$ LANGUAGE sql STABLE;

CREATE FUNCTION snr_identity_platform_guard() RETURNS trigger AS $$
BEGIN
    IF snr_run_platform(NEW.first_seen_run_id) IS DISTINCT FROM NEW.platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = format('identitas platform %s tidak boleh dibuat pada run platform %s',
                             NEW.platform, snr_run_platform(NEW.first_seen_run_id));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER post_platform_guard
    BEFORE INSERT ON collection_post
    FOR EACH ROW EXECUTE FUNCTION snr_identity_platform_guard();
CREATE TRIGGER actor_platform_guard
    BEFORE INSERT ON collection_actoraccount
    FOR EACH ROW EXECUTE FUNCTION snr_identity_platform_guard();

CREATE FUNCTION snr_observation_platform_guard() RETURNS trigger AS $$
DECLARE
    run_platform text := snr_run_platform(NEW.run_id);
    post_platform text;
    author_platform text;
BEGIN
    SELECT platform INTO post_platform FROM collection_post WHERE id = NEW.post_id;
    IF post_platform IS DISTINCT FROM run_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = format('observasi post platform %s pada run platform %s ditolak',
                             post_platform, run_platform);
    END IF;
    IF NEW.author_id IS NOT NULL THEN
        SELECT platform INTO author_platform FROM collection_actoraccount WHERE id = NEW.author_id;
        IF author_platform IS DISTINCT FROM run_platform THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = format('penulis platform %s pada run platform %s ditolak',
                                 author_platform, run_platform);
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER post_observation_platform_guard
    BEFORE INSERT ON collection_postobservation
    FOR EACH ROW EXECUTE FUNCTION snr_observation_platform_guard();

CREATE FUNCTION snr_relation_platform_guard() RETURNS trigger AS $$
DECLARE
    run_platform text := snr_run_platform(NEW.run_id);
    other_platform text;
BEGIN
    SELECT platform INTO other_platform FROM collection_post WHERE id = NEW.from_post_id;
    IF other_platform IS DISTINCT FROM run_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'relasi dari post platform lain ditolak';
    END IF;
    IF NEW.to_post_id IS NOT NULL THEN
        SELECT platform INTO other_platform FROM collection_post WHERE id = NEW.to_post_id;
        IF other_platform IS DISTINCT FROM run_platform THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'relasi ke post platform lain ditolak';
        END IF;
    END IF;
    IF NEW.to_actor_id IS NOT NULL THEN
        SELECT platform INTO other_platform FROM collection_actoraccount WHERE id = NEW.to_actor_id;
        IF other_platform IS DISTINCT FROM run_platform THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'relasi ke akun platform lain ditolak';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER post_relation_platform_guard
    BEFORE INSERT ON collection_postrelation
    FOR EACH ROW EXECUTE FUNCTION snr_relation_platform_guard();
"""

REVERSE = """
DROP TRIGGER post_relation_platform_guard ON collection_postrelation;
DROP FUNCTION snr_relation_platform_guard();
DROP TRIGGER post_observation_platform_guard ON collection_postobservation;
DROP FUNCTION snr_observation_platform_guard();
DROP TRIGGER actor_platform_guard ON collection_actoraccount;
DROP TRIGGER post_platform_guard ON collection_post;
DROP FUNCTION snr_identity_platform_guard();
DROP FUNCTION snr_run_platform(bigint);
DROP TRIGGER actor_identity_guard ON collection_actoraccount;
DROP TRIGGER post_identity_guard ON collection_post;
DROP FUNCTION snr_identity_guard();
DROP TRIGGER inspection_run_guard ON collection_inspectionrun;
DROP FUNCTION snr_run_guard();
DROP TRIGGER post_relation_append_only ON collection_postrelation;
DROP TRIGGER post_observation_append_only ON collection_postobservation;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("collection", "0001_initial"),
        ("investigations", "0002_append_only_triggers"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
