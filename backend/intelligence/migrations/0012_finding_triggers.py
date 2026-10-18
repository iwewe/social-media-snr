"""Trigger integritas temuan (WP-2.6; ADR 0030).

- Finding: dibuat belum tersegel; satu-satunya perubahan adalah penyegelan (butuh >= 1 AnalysisRun dan
  >= 1 observasi, empat sumbu bukti, objek hipotesis alternatif); tersegel = tidak dapat diubah/dihapus.
- Tautan (run, observasi, indikator) hanya sebelum disegel: run harus SELESAI pada investigasi dan platform
  yang sama; observasi harus anggota dataset salah satu run tertaut; indikator harus dari run tertaut.
- FindingReview: hanya pada temuan tersegel; ENDORSE wajib hanya bila SELURUH empat hipotesis alternatif
  sudah dinilai (outcome sah + alasan) dan temuan belum ditarik atau digantikan oleh penerus yang disahkan.
- Semua append-only. Fungsi memakai enable_seqscan = off (ADR 0020).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_finding_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    n_runs bigint;
    n_obs bigint;
    p_inv bigint;
    p_platform text;
    p_sealed timestamptz;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.sealed_at IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'temuan harus dibuat belum tersegel';
        END IF;
        IF NEW.supersedes_id IS NOT NULL THEN
            SELECT investigation_id, platform, sealed_at INTO p_inv, p_platform, p_sealed
                FROM intelligence_finding WHERE id = NEW.supersedes_id;
            IF p_sealed IS NULL OR p_inv IS DISTINCT FROM NEW.investigation_id
               OR p_platform IS DISTINCT FROM NEW.platform THEN
                RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                    MESSAGE = 'temuan yang digantikan harus tersegel, satu investigasi, satu platform';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.sealed_at IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'temuan tersegel tidak dapat diubah';
    END IF;
    IF NEW.sealed_at IS NULL OR
       (NEW.id, NEW.investigation_id, NEW.platform, NEW.title, NEW.statement, NEW.interpretation,
        NEW.confidence, NEW.confidence_reason, NEW.evidence_quality, NEW.alternatives,
        NEW.independent_evidence_groups, NEW.synthetic_data, NEW.notice, NEW.supersedes_id,
        NEW.created_by_id, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.investigation_id, OLD.platform, OLD.title, OLD.statement, OLD.interpretation,
        OLD.confidence, OLD.confidence_reason, OLD.evidence_quality, OLD.alternatives,
        OLD.independent_evidence_groups, OLD.synthetic_data, OLD.notice, OLD.supersedes_id,
        OLD.created_by_id, OLD.created_at) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'temuan hanya boleh disegel; kolom lain tidak boleh berubah';
    END IF;
    SELECT count(*) INTO n_runs FROM intelligence_findingrun WHERE finding_id = NEW.id;
    SELECT count(*) INTO n_obs FROM intelligence_findingobservation WHERE finding_id = NEW.id;
    IF n_runs < 1 OR n_obs < 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'temuan wajib tertaut ke minimal satu AnalysisRun dan satu observasi';
    END IF;
    IF jsonb_typeof(NEW.evidence_quality) IS DISTINCT FROM 'object'
       OR NOT (NEW.evidence_quality ?& ARRAY['integrity', 'provenance', 'completeness', 'relevance'])
       OR jsonb_typeof(NEW.alternatives) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'temuan wajib memuat empat sumbu bukti dan objek hipotesis alternatif';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_finding_run_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    f_sealed timestamptz;
    f_inv bigint;
    f_platform text;
    r_status text;
    r_inv bigint;
    d_platform text;
BEGIN
    SELECT sealed_at, investigation_id, platform INTO f_sealed, f_inv, f_platform
        FROM intelligence_finding WHERE id = NEW.finding_id;
    IF f_sealed IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'tautan tidak dapat ditambah pada temuan yang sudah tersegel';
    END IF;
    SELECT a.status, a.investigation_id, d.platform INTO r_status, r_inv, d_platform
        FROM intelligence_analysisrun a
        JOIN intelligence_datasetversion d ON d.id = a.dataset_version_id
        WHERE a.id = NEW.analysis_run_id;
    IF r_status IS DISTINCT FROM 'COMPLETED' OR r_inv IS DISTINCT FROM f_inv
       OR d_platform IS DISTINCT FROM f_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'AnalysisRun harus selesai, satu investigasi, dan satu platform dengan temuan';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_finding_observation_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    f_sealed timestamptz;
BEGIN
    SELECT sealed_at INTO f_sealed FROM intelligence_finding WHERE id = NEW.finding_id;
    IF f_sealed IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'tautan tidak dapat ditambah pada temuan yang sudah tersegel';
    END IF;
    PERFORM 1
        FROM intelligence_findingrun fr
        JOIN intelligence_analysisrun a ON a.id = fr.analysis_run_id
        JOIN intelligence_datasetversionobservation m ON m.dataset_version_id = a.dataset_version_id
        WHERE fr.finding_id = NEW.finding_id AND m.observation_id = NEW.observation_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'observasi bukan anggota dataset dari AnalysisRun yang ditautkan';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_finding_indicator_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    f_sealed timestamptz;
BEGIN
    SELECT sealed_at INTO f_sealed FROM intelligence_finding WHERE id = NEW.finding_id;
    IF f_sealed IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'tautan tidak dapat ditambah pada temuan yang sudah tersegel';
    END IF;
    PERFORM 1
        FROM intelligence_findingrun fr
        JOIN intelligence_coordinationnetwork c ON c.analysis_run_id = fr.analysis_run_id
        JOIN intelligence_coordinationedge e ON e.network_id = c.id
        WHERE fr.finding_id = NEW.finding_id AND e.id = NEW.edge_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'indikator harus berasal dari AnalysisRun yang ditautkan ke temuan';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_finding_review_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    f_sealed timestamptz;
    f_alts jsonb;
    k text;
BEGIN
    SELECT sealed_at, alternatives INTO f_sealed, f_alts
        FROM intelligence_finding WHERE id = NEW.finding_id;
    IF f_sealed IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'hanya temuan tersegel yang dapat ditinjau';
    END IF;
    IF NEW.action = 'ENDORSE' THEN
        IF EXISTS (SELECT 1 FROM intelligence_findingreview
                   WHERE finding_id = NEW.finding_id AND action = 'WITHDRAW') THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'temuan yang sudah ditarik tidak dapat disahkan';
        END IF;
        IF EXISTS (SELECT 1 FROM intelligence_finding s
                   JOIN intelligence_findingreview r ON r.finding_id = s.id AND r.action = 'ENDORSE'
                   WHERE s.supersedes_id = NEW.finding_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'temuan yang sudah digantikan penerus yang disahkan tidak dapat disahkan';
        END IF;
        FOREACH k IN ARRAY ARRAY['organic_mobilization', 'external_event',
                                 'public_content_copying', 'sampling_bias'] LOOP
            IF NOT (f_alts ? k)
               OR (f_alts -> k ->> 'outcome') IS NULL
               OR (f_alts -> k ->> 'outcome') NOT IN ('RULED_OUT', 'NOT_RULED_OUT', 'CANNOT_ASSESS')
               OR length(btrim(COALESCE(f_alts -> k ->> 'reasoning', ''))) = 0 THEN
                RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                    MESSAGE = 'seluruh hipotesis alternatif wajib sudah dipertimbangkan sebelum pengesahan';
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER finding_guard BEFORE INSERT OR UPDATE ON intelligence_finding
    FOR EACH ROW EXECUTE FUNCTION snr_finding_guard();
CREATE TRIGGER finding_no_delete BEFORE DELETE ON intelligence_finding
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER finding_run_guard BEFORE INSERT ON intelligence_findingrun
    FOR EACH ROW EXECUTE FUNCTION snr_finding_run_guard();
CREATE TRIGGER finding_run_append_only BEFORE UPDATE OR DELETE ON intelligence_findingrun
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER finding_observation_guard BEFORE INSERT ON intelligence_findingobservation
    FOR EACH ROW EXECUTE FUNCTION snr_finding_observation_guard();
CREATE TRIGGER finding_observation_append_only BEFORE UPDATE OR DELETE ON intelligence_findingobservation
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER finding_indicator_guard BEFORE INSERT ON intelligence_findingindicator
    FOR EACH ROW EXECUTE FUNCTION snr_finding_indicator_guard();
CREATE TRIGGER finding_indicator_append_only BEFORE UPDATE OR DELETE ON intelligence_findingindicator
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER finding_review_guard BEFORE INSERT ON intelligence_findingreview
    FOR EACH ROW EXECUTE FUNCTION snr_finding_review_guard();
CREATE TRIGGER finding_review_append_only BEFORE UPDATE OR DELETE ON intelligence_findingreview
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER finding_review_append_only ON intelligence_findingreview;
DROP TRIGGER finding_review_guard ON intelligence_findingreview;
DROP TRIGGER finding_indicator_append_only ON intelligence_findingindicator;
DROP TRIGGER finding_indicator_guard ON intelligence_findingindicator;
DROP TRIGGER finding_observation_append_only ON intelligence_findingobservation;
DROP TRIGGER finding_observation_guard ON intelligence_findingobservation;
DROP TRIGGER finding_run_append_only ON intelligence_findingrun;
DROP TRIGGER finding_run_guard ON intelligence_findingrun;
DROP TRIGGER finding_no_delete ON intelligence_finding;
DROP TRIGGER finding_guard ON intelligence_finding;
DROP FUNCTION snr_finding_review_guard();
DROP FUNCTION snr_finding_indicator_guard();
DROP FUNCTION snr_finding_observation_guard();
DROP FUNCTION snr_finding_run_guard();
DROP FUNCTION snr_finding_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("intelligence", "0011_finding")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
