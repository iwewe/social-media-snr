"""Trigger integritas graf M4 (WP-2.4; ADR 0028).

- Append-only pada GraphProjection, GraphNode, GraphEdge.
- Ditulis hanya saat AnalysisRun bermetode M4 RUNNING; platform proyeksi = platform dataset.
- Tepat SATU platform per graf (AT-13, NFR-06): akun node harus berplatform sama dengan proyeksi.
- Ujung edge harus node pada proyeksi yang sama.
- Fungsi memakai enable_seqscan = off (ADR 0020).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_graph_projection_guard() RETURNS trigger
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
    IF r_method NOT LIKE 'm4-%' OR r_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'graf hanya ditulis saat analysis run M4 RUNNING';
    END IF;
    IF NEW.platform IS DISTINCT FROM d_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'platform graf harus sama dengan platform dataset';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_graph_node_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    g_platform text;
    g_status text;
    a_platform text;
BEGIN
    SELECT g.platform, a.status INTO g_platform, g_status
        FROM intelligence_graphprojection g
        JOIN intelligence_analysisrun a ON a.id = g.analysis_run_id
        WHERE g.id = NEW.projection_id;
    IF g_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'node hanya ditambah saat analysis run RUNNING';
    END IF;
    SELECT platform INTO a_platform FROM collection_actoraccount WHERE id = NEW.actor_id;
    IF a_platform IS DISTINCT FROM g_platform THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'akun platform lain tidak boleh menjadi node pada graf ini';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION snr_graph_edge_guard() RETURNS trigger
    SET enable_seqscan = off AS $$
DECLARE
    g_status text;
    f_proj bigint;
    t_proj bigint;
BEGIN
    SELECT a.status INTO g_status
        FROM intelligence_graphprojection g
        JOIN intelligence_analysisrun a ON a.id = g.analysis_run_id
        WHERE g.id = NEW.projection_id;
    IF g_status <> 'RUNNING' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'edge hanya ditambah saat analysis run RUNNING';
    END IF;
    SELECT projection_id INTO f_proj FROM intelligence_graphnode WHERE id = NEW.from_node_id;
    SELECT projection_id INTO t_proj FROM intelligence_graphnode WHERE id = NEW.to_node_id;
    IF f_proj IS DISTINCT FROM NEW.projection_id OR t_proj IS DISTINCT FROM NEW.projection_id THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'ujung edge harus node pada graf yang sama';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER graph_projection_guard BEFORE INSERT ON intelligence_graphprojection
    FOR EACH ROW EXECUTE FUNCTION snr_graph_projection_guard();
CREATE TRIGGER graph_node_guard BEFORE INSERT ON intelligence_graphnode
    FOR EACH ROW EXECUTE FUNCTION snr_graph_node_guard();
CREATE TRIGGER graph_edge_guard BEFORE INSERT ON intelligence_graphedge
    FOR EACH ROW EXECUTE FUNCTION snr_graph_edge_guard();
CREATE TRIGGER graph_projection_append_only BEFORE UPDATE OR DELETE ON intelligence_graphprojection
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER graph_node_append_only BEFORE UPDATE OR DELETE ON intelligence_graphnode
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER graph_edge_append_only BEFORE UPDATE OR DELETE ON intelligence_graphedge
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
"""

REVERSE = """
DROP TRIGGER graph_edge_append_only ON intelligence_graphedge;
DROP TRIGGER graph_node_append_only ON intelligence_graphnode;
DROP TRIGGER graph_projection_append_only ON intelligence_graphprojection;
DROP TRIGGER graph_edge_guard ON intelligence_graphedge;
DROP TRIGGER graph_node_guard ON intelligence_graphnode;
DROP TRIGGER graph_projection_guard ON intelligence_graphprojection;
DROP FUNCTION snr_graph_edge_guard();
DROP FUNCTION snr_graph_node_guard();
DROP FUNCTION snr_graph_projection_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("intelligence", "0007_graph")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
