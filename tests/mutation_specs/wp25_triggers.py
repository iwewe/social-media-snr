"""Mutasi trigger jaringan koordinasi (WP-2.5). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_co_run.py -k "not synthetic" --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0010_coordination_triggers.py'

MUTATIONS = [
    Mutation('jaringan: bukan run indikator diterima', T, "IF r_method NOT LIKE 'co-%' OR r_status <> 'RUNNING' THEN", "IF r_status <> 'RUNNING' THEN"),
    Mutation('jaringan: run tidak RUNNING diterima', T, "IF r_method NOT LIKE 'co-%' OR r_status <> 'RUNNING' THEN", "IF r_method NOT LIKE 'co-%' THEN"),
    Mutation('jaringan: platform berbeda dari dataset', T, 'IF NEW.platform IS DISTINCT FROM d_platform THEN', 'IF false THEN'),
    Mutation('tepi: run tidak RUNNING diterima', T, "    IF n_status <> 'RUNNING' THEN", '    IF false THEN'),
    Mutation('tepi: akun A platform lain', T, 'IF a_platform IS DISTINCT FROM n_platform OR b_platform IS DISTINCT FROM n_platform THEN', 'IF b_platform IS DISTINCT FROM n_platform THEN'),
    Mutation('tepi: akun B platform lain', T, 'IF a_platform IS DISTINCT FROM n_platform OR b_platform IS DISTINCT FROM n_platform THEN', 'IF a_platform IS DISTINCT FROM n_platform THEN'),
    Mutation('jaringan dapat diubah', T, 'CREATE TRIGGER coordination_network_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER coordination_network_append_only\n    BEFORE DELETE'),
    Mutation('tepi dapat dihapus', T, 'CREATE TRIGGER coordination_edge_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER coordination_edge_append_only\n    BEFORE UPDATE'),
    Mutation('rencana seqscan tidak dimatikan', T, 'CREATE FUNCTION snr_coordination_edge_guard() RETURNS trigger\n    SET enable_seqscan = off AS $$', 'CREATE FUNCTION snr_coordination_edge_guard() RETURNS trigger\n    AS $$'),
]
