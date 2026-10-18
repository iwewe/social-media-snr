"""Trigger integritas ActorIssueProfile (WP-2.3; ADR 0027).

- Append-only; ditulis hanya saat AnalysisRun M3 RUNNING.
- Akun harus dari platform yang sama dengan dataset (isolasi, NFR-06); source_run harus run M2 SELESAI
  pada dataset yang sama; proposition dari investigasi yang sama.
- `coverage` WAJIB berupa objek dengan pernyataan cakupan tidak kosong dan daftar target (FR-063, AT-17).
- Fungsi memakai enable_seqscan = off (ADR 0020).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_profile_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    r_status text;
    r_method text;
    r_dataset bigint;
    r_inv bigint;
    d_platform text;
    a_platform text;
    s_method text;
    s_status text;
    s_dataset bigint;
    p_inv bigint;
BEGIN
    SELECT a.status, a.method, a.dataset_version_id, a.investigation_id, d.platform
        INTO r_status, r_method, r_dataset, r_inv, d_platform
        FROM intelligence_analysisrun a
        JOIN intelligence_datasetversion d ON d.id = a.dataset_version_id
        WHERE a.id = NEW.analysis_run_id;
    IF r_method NOT LIKE 'm3-%' OR r_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'profil hanya ditulis saat analysis run M3 RUNNING';
    END IF;
    SELECT platform INTO a_platform FROM collection_actoraccount WHERE id = NEW.actor_id;
    IF a_platform IS DISTINCT FROM d_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'akun platform lain tidak boleh masuk profil pada dataset ini';
    END IF;
    SELECT method, status, dataset_version_id INTO s_method, s_status, s_dataset
        FROM intelligence_analysisrun WHERE id = NEW.source_run_id;
    IF s_method NOT LIKE 'm2-%' OR s_status <> 'COMPLETED'
       OR s_dataset IS DISTINCT FROM r_dataset THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'source_run harus run M2 selesai pada dataset yang sama';
    END IF;
    SELECT i.investigation_id INTO p_inv
        FROM investigations_proposition p JOIN investigations_issue i ON i.id = p.issue_id
        WHERE p.id = NEW.proposition_id;
    IF p_inv IS DISTINCT FROM r_inv THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'proposition milik investigasi lain';
    END IF;
    IF jsonb_typeof(NEW.coverage) IS DISTINCT FROM 'object'
       OR jsonb_typeof(NEW.coverage->'targets_covered') IS DISTINCT FROM 'array'
       OR COALESCE(length(NEW.coverage->>'statement'), 0) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'profil wajib memuat pernyataan cakupan (statement) dan targets_covered';
    END IF;
    IF jsonb_typeof(NEW.dimensions) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'dimensions harus objek';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profile_guard
    BEFORE INSERT ON intelligence_actorissueprofile
    FOR EACH ROW EXECUTE FUNCTION snr_profile_guard();
CREATE TRIGGER profile_append_only
    BEFORE UPDATE OR DELETE ON intelligence_actorissueprofile
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER profile_append_only ON intelligence_actorissueprofile;
DROP TRIGGER profile_guard ON intelligence_actorissueprofile;
DROP FUNCTION snr_profile_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("intelligence", "0005_actorissueprofile")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
