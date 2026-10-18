"""Trigger integritas ResponseAssessment (WP-2.2; ADR 0026).

- Append-only: tidak ada UPDATE/DELETE (koreksi manusia = baris baru yang menggantikan).
- Penilaian mesin hanya ditulis saat AnalysisRun RUNNING; tinjauan manusia hanya saat run COMPLETED.
- Hanya untuk run bermetode M2; observasi harus anggota dataset beku run itu; proposition harus dari
  investigasi yang sama dengan run.
- Tinjauan manusia harus menggantikan baris untuk (run, observasi, proposition) yang sama.
- Fungsi memakai enable_seqscan = off (ADR 0020).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_assessment_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    r_status text;
    r_method text;
    r_dataset bigint;
    r_inv bigint;
    p_inv bigint;
    s_run bigint;
    s_obs bigint;
    s_prop bigint;
BEGIN
    SELECT status, method, dataset_version_id, investigation_id
        INTO r_status, r_method, r_dataset, r_inv
        FROM intelligence_analysisrun WHERE id = NEW.analysis_run_id;
    IF r_method NOT LIKE 'm2-%' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'penilaian respons hanya untuk analysis run bermetode M2';
    END IF;
    IF NEW.source = 'MACHINE' AND r_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'penilaian mesin hanya ditulis saat analysis run RUNNING';
    END IF;
    IF NEW.source = 'HUMAN' THEN
        IF r_status <> 'COMPLETED' THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'tinjauan manusia hanya pada analysis run yang selesai';
        END IF;
        SELECT analysis_run_id, observation_id, proposition_id INTO s_run, s_obs, s_prop
            FROM intelligence_responseassessment WHERE id = NEW.supersedes_id;
        IF s_run IS DISTINCT FROM NEW.analysis_run_id
           OR s_obs IS DISTINCT FROM NEW.observation_id
           OR s_prop IS DISTINCT FROM NEW.proposition_id THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'tinjauan harus menggantikan penilaian untuk respons dan proposition yang sama';
        END IF;
    END IF;
    PERFORM 1 FROM intelligence_datasetversionobservation
        WHERE dataset_version_id = r_dataset AND observation_id = NEW.observation_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'observasi bukan anggota dataset beku analysis run ini';
    END IF;
    SELECT i.investigation_id INTO p_inv
        FROM investigations_proposition p JOIN investigations_issue i ON i.id = p.issue_id
        WHERE p.id = NEW.proposition_id;
    IF p_inv IS DISTINCT FROM r_inv THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'proposition milik investigasi lain';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER assessment_guard
    BEFORE INSERT ON intelligence_responseassessment
    FOR EACH ROW EXECUTE FUNCTION snr_assessment_guard();
CREATE TRIGGER assessment_append_only
    BEFORE UPDATE OR DELETE ON intelligence_responseassessment
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER assessment_append_only ON intelligence_responseassessment;
DROP TRIGGER assessment_guard ON intelligence_responseassessment;
DROP FUNCTION snr_assessment_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("intelligence", "0003_responseassessment")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
