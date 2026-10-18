"""Trigger integritas jaringan koordinasi (WP-2.5; ADR 0029).

- Append-only pada CoordinationNetwork dan CoordinationEdge.
- Ditulis hanya saat AnalysisRun bermetode `co-` RUNNING; platform jaringan = platform dataset.
- Tepat SATU platform (AT-13, NFR-06): kedua akun pada tepi harus berplatform sama dengan jaringan.
- Fungsi memakai enable_seqscan = off (ADR 0020).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_coordination_network_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    r_status text;
    r_method text;
    d_platform text;
BEGIN
    SELECT a.status, a.method, d.platform INTO r_status, r_method, d_platform
        FROM intelligence_analysisrun a
        JOIN intelligence_datasetversion d ON d.id = a.dataset_version_id
        WHERE a.id = NEW.analysis_run_id;
    IF r_method NOT LIKE 'co-%' OR r_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'jaringan koordinasi hanya ditulis saat analysis run indikator RUNNING';
    END IF;
    IF NEW.platform IS DISTINCT FROM d_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'platform jaringan koordinasi harus sama dengan platform dataset';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_coordination_edge_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    n_platform text;
    n_status text;
    a_platform text;
    b_platform text;
BEGIN
    SELECT c.platform, a.status INTO n_platform, n_status
        FROM intelligence_coordinationnetwork c
        JOIN intelligence_analysisrun a ON a.id = c.analysis_run_id
        WHERE c.id = NEW.network_id;
    IF n_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'indikator hanya ditambah saat analysis run RUNNING';
    END IF;
    SELECT platform INTO a_platform FROM collection_actoraccount WHERE id = NEW.actor_a_id;
    SELECT platform INTO b_platform FROM collection_actoraccount WHERE id = NEW.actor_b_id;
    IF a_platform IS DISTINCT FROM n_platform OR b_platform IS DISTINCT FROM n_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'akun platform lain tidak boleh menjadi pasangan pada jaringan ini';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER coordination_network_guard BEFORE INSERT ON intelligence_coordinationnetwork
    FOR EACH ROW EXECUTE FUNCTION snr_coordination_network_guard();
CREATE TRIGGER coordination_edge_guard BEFORE INSERT ON intelligence_coordinationedge
    FOR EACH ROW EXECUTE FUNCTION snr_coordination_edge_guard();
CREATE TRIGGER coordination_network_append_only
    BEFORE UPDATE OR DELETE ON intelligence_coordinationnetwork
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER coordination_edge_append_only
    BEFORE UPDATE OR DELETE ON intelligence_coordinationedge
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER coordination_edge_append_only ON intelligence_coordinationedge;
DROP TRIGGER coordination_network_append_only ON intelligence_coordinationnetwork;
DROP TRIGGER coordination_edge_guard ON intelligence_coordinationedge;
DROP TRIGGER coordination_network_guard ON intelligence_coordinationnetwork;
DROP FUNCTION snr_coordination_edge_guard();
DROP FUNCTION snr_coordination_network_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("intelligence", "0009_coordination")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
