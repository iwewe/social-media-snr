"""Mutasi trigger graf M4 (WP-2.4). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m4_run.py --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0008_graph_triggers.py'

MUTATIONS = [
    Mutation('proyeksi: bukan run M4 diterima', T, "IF r_method NOT LIKE 'm4-%' OR r_status <> 'RUNNING' THEN", "IF r_status <> 'RUNNING' THEN"),
    Mutation('proyeksi: run tidak RUNNING diterima', T, "IF r_method NOT LIKE 'm4-%' OR r_status <> 'RUNNING' THEN", "IF r_method NOT LIKE 'm4-%' THEN"),
    Mutation('proyeksi: platform berbeda dari dataset', T, 'IF NEW.platform IS DISTINCT FROM d_platform THEN', 'IF false THEN'),
    Mutation('node: run tidak RUNNING diterima', T, "    IF g_status <> 'RUNNING' THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'node hanya", "    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'node hanya"),
    Mutation('node: akun platform lain lolos', T, 'IF a_platform IS DISTINCT FROM g_platform THEN', 'IF false THEN'),
    Mutation('edge: run tidak RUNNING diterima', T, "    IF g_status <> 'RUNNING' THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'edge hanya", "    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'edge hanya"),
    Mutation('edge: ujung di graf lain (dari)', T, 'IF f_proj IS DISTINCT FROM NEW.projection_id OR t_proj IS DISTINCT FROM NEW.projection_id THEN', 'IF t_proj IS DISTINCT FROM NEW.projection_id THEN'),
    Mutation('edge: ujung di graf lain (ke)', T, 'IF f_proj IS DISTINCT FROM NEW.projection_id OR t_proj IS DISTINCT FROM NEW.projection_id THEN', 'IF f_proj IS DISTINCT FROM NEW.projection_id THEN'),
    Mutation('proyeksi dapat diubah', T, 'CREATE TRIGGER graph_projection_append_only BEFORE UPDATE OR DELETE', 'CREATE TRIGGER graph_projection_append_only BEFORE DELETE'),
    Mutation('node dapat dihapus', T, 'CREATE TRIGGER graph_node_append_only BEFORE UPDATE OR DELETE', 'CREATE TRIGGER graph_node_append_only BEFORE UPDATE'),
    Mutation('edge dapat diubah', T, 'CREATE TRIGGER graph_edge_append_only BEFORE UPDATE OR DELETE', 'CREATE TRIGGER graph_edge_append_only BEFORE DELETE'),
    Mutation('rencana seqscan tidak dimatikan (edge)', T, 'CREATE FUNCTION snr_graph_edge_guard() RETURNS trigger\n    SET enable_seqscan = off AS $$', 'CREATE FUNCTION snr_graph_edge_guard() RETURNS trigger\n    AS $$'),
]
