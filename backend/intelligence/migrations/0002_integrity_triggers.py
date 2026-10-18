"""Trigger integritas analisis I2 (WP-2.1; ADR 0025).

- DatasetVersion: append-only; satu-satunya perubahan yang boleh adalah penyegelan (sealed_at NULL -> terisi)
  dengan jumlah anggota sama dengan observation_count. Anggota hanya dapat ditambah sebelum disegel dan harus
  dari platform dan investigasi yang sama (NFR-06, FR-073).
- AnalysisRun: hanya dapat dibuat PENDING atas dataset tersegel pada investigasi yang sama; masukan terkunci;
  transisi status satu arah; keluaran hanya saat COMPLETED. Tidak dapat dihapus.
- Fungsi memakai enable_seqscan = off (ADR 0020): hanya mencari lewat primary key/indeks.
"""

from django.db import migrations

FUNCTIONS = [
    "snr_dataset_version_guard()",
    "snr_dataset_member_guard()",
    "snr_analysis_run_guard()",
    "snr_analysis_target_context_guard()",
]

FORWARD = """
CREATE FUNCTION snr_dataset_version_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE n bigint;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.sealed_at IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'dataset version harus dibuat belum tersegel';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.sealed_at IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'dataset version tersegel tidak dapat diubah';
    END IF;
    IF NEW.sealed_at IS NULL OR
       (NEW.id, NEW.investigation_id, NEW.platform, NEW.number, NEW.observation_count,
        NEW.observation_digest, NEW.selection, NEW.note, NEW.created_by_id, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.investigation_id, OLD.platform, OLD.number, OLD.observation_count,
        OLD.observation_digest, OLD.selection, OLD.note, OLD.created_by_id, OLD.created_at) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'dataset version hanya boleh disegel; kolom lain tidak boleh berubah';
    END IF;
    SELECT count(*) INTO n FROM intelligence_datasetversionobservation
        WHERE dataset_version_id = NEW.id;
    IF n <> NEW.observation_count THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'jumlah anggota dataset tidak sama dengan observation_count';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dataset_version_guard
    BEFORE INSERT OR UPDATE ON intelligence_datasetversion
    FOR EACH ROW EXECUTE FUNCTION snr_dataset_version_guard();
CREATE TRIGGER dataset_version_no_delete
    BEFORE DELETE ON intelligence_datasetversion
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_dataset_member_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    d_sealed timestamptz;
    d_platform text;
    d_inv bigint;
    o_platform text;
    o_inv bigint;
BEGIN
    SELECT sealed_at, platform, investigation_id INTO d_sealed, d_platform, d_inv
        FROM intelligence_datasetversion WHERE id = NEW.dataset_version_id;
    IF d_sealed IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'anggota tidak dapat ditambah pada dataset yang sudah tersegel';
    END IF;
    SELECT p.platform, t.investigation_id INTO o_platform, o_inv
        FROM collection_postobservation o
        JOIN collection_post p ON p.id = o.post_id
        JOIN collection_inspectionrun r ON r.id = o.run_id
        JOIN investigations_collectiontarget t ON t.id = r.target_id
        WHERE o.id = NEW.observation_id;
    IF o_platform IS DISTINCT FROM d_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'observasi platform lain tidak boleh masuk dataset ini';
    END IF;
    IF o_inv IS DISTINCT FROM d_inv THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'observasi investigasi lain tidak boleh masuk dataset ini';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dataset_member_guard
    BEFORE INSERT ON intelligence_datasetversionobservation
    FOR EACH ROW EXECUTE FUNCTION snr_dataset_member_guard();
CREATE TRIGGER dataset_member_append_only
    BEFORE UPDATE OR DELETE ON intelligence_datasetversionobservation
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_analysis_run_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    d_sealed timestamptz;
    d_inv bigint;
    c_inv bigint;
    p_inv bigint;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PENDING' THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'analysis run harus dibuat PENDING';
        END IF;
        SELECT sealed_at, investigation_id INTO d_sealed, d_inv
            FROM intelligence_datasetversion WHERE id = NEW.dataset_version_id;
        IF d_sealed IS NULL THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'analysis run hanya untuk dataset yang sudah tersegel';
        END IF;
        IF d_inv IS DISTINCT FROM NEW.investigation_id THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'dataset milik investigasi lain';
        END IF;
        IF NEW.issue_context_version_id IS NOT NULL THEN
            SELECT i.investigation_id INTO c_inv
                FROM investigations_issuecontextversion v
                JOIN investigations_issue i ON i.id = v.issue_id
                WHERE v.id = NEW.issue_context_version_id;
            IF c_inv IS DISTINCT FROM NEW.investigation_id THEN
                RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                    MESSAGE = 'konteks issue milik investigasi lain';
            END IF;
        END IF;
        IF NEW.previous_run_id IS NOT NULL THEN
            SELECT investigation_id INTO p_inv FROM intelligence_analysisrun
                WHERE id = NEW.previous_run_id;
            IF p_inv IS DISTINCT FROM NEW.investigation_id THEN
                RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                    MESSAGE = 'run sebelumnya milik investigasi lain';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF (NEW.id, NEW.public_id, NEW.investigation_id, NEW.dataset_version_id,
        NEW.issue_context_version_id, NEW.method, NEW.method_version, NEW.parameters,
        NEW.parameters_digest, NEW.previous_run_id, NEW.created_by_id, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.public_id, OLD.investigation_id, OLD.dataset_version_id,
        OLD.issue_context_version_id, OLD.method, OLD.method_version, OLD.parameters,
        OLD.parameters_digest, OLD.previous_run_id, OLD.created_by_id, OLD.created_at) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'masukan analysis run terkunci dan tidak dapat diubah';
    END IF;
    IF NOT ((OLD.status = 'PENDING' AND NEW.status IN ('RUNNING', 'FAILED'))
         OR (OLD.status = 'RUNNING' AND NEW.status IN ('COMPLETED', 'FAILED'))) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'transisi status analysis run tidak sah';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER analysis_run_guard
    BEFORE INSERT OR UPDATE ON intelligence_analysisrun
    FOR EACH ROW EXECUTE FUNCTION snr_analysis_run_guard();
CREATE TRIGGER analysis_run_no_delete
    BEFORE DELETE ON intelligence_analysisrun
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_analysis_target_context_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    r_status text;
    r_inv bigint;
    r_platform text;
    t_inv bigint;
    t_platform text;
    c_target bigint;
BEGIN
    SELECT a.status, a.investigation_id, d.platform INTO r_status, r_inv, r_platform
        FROM intelligence_analysisrun a
        JOIN intelligence_datasetversion d ON d.id = a.dataset_version_id
        WHERE a.id = NEW.run_id;
    IF r_status <> 'PENDING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'konteks target tidak dapat ditambah setelah run dimulai';
    END IF;
    SELECT investigation_id, platform INTO t_inv, t_platform
        FROM investigations_collectiontarget WHERE id = NEW.target_id;
    IF t_inv IS DISTINCT FROM r_inv OR t_platform IS DISTINCT FROM r_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'target harus pada investigasi dan platform yang sama dengan run';
    END IF;
    IF NEW.context_version_id IS NOT NULL THEN
        SELECT target_id INTO c_target FROM investigations_targetcontextversion
            WHERE id = NEW.context_version_id;
        IF c_target IS DISTINCT FROM NEW.target_id THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'versi konteks bukan milik target ini';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER analysis_target_context_guard
    BEFORE INSERT ON intelligence_analysisruntargetcontext
    FOR EACH ROW EXECUTE FUNCTION snr_analysis_target_context_guard();
CREATE TRIGGER analysis_target_context_append_only
    BEFORE UPDATE OR DELETE ON intelligence_analysisruntargetcontext
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER analysis_target_context_append_only ON intelligence_analysisruntargetcontext;
DROP TRIGGER analysis_target_context_guard ON intelligence_analysisruntargetcontext;
DROP TRIGGER analysis_run_no_delete ON intelligence_analysisrun;
DROP TRIGGER analysis_run_guard ON intelligence_analysisrun;
DROP TRIGGER dataset_member_append_only ON intelligence_datasetversionobservation;
DROP TRIGGER dataset_member_guard ON intelligence_datasetversionobservation;
DROP TRIGGER dataset_version_no_delete ON intelligence_datasetversion;
DROP TRIGGER dataset_version_guard ON intelligence_datasetversion;
DROP FUNCTION snr_analysis_target_context_guard();
DROP FUNCTION snr_analysis_run_guard();
DROP FUNCTION snr_dataset_member_guard();
DROP FUNCTION snr_dataset_version_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("intelligence", "0001_initial"),
        ("collection", "0010_trigger_plan_stability"),
        ("investigations", "0003_investigation_membership"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
