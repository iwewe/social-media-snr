"""Mutasi trigger ActorIssueProfile (WP-2.3). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m3_run.py --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0006_profile_triggers.py'

MUTATIONS = [
    Mutation('bukan run M3 diterima', T, "IF r_method NOT LIKE 'm3-%' OR r_status <> 'RUNNING' THEN", "IF r_status <> 'RUNNING' THEN"),
    Mutation('run tidak RUNNING diterima', T, "IF r_method NOT LIKE 'm3-%' OR r_status <> 'RUNNING' THEN", "IF r_method NOT LIKE 'm3-%' THEN"),
    Mutation('akun platform lain lolos', T, 'IF a_platform IS DISTINCT FROM d_platform THEN', 'IF false THEN'),
    Mutation('sumber bukan M2 lolos', T, "IF s_method NOT LIKE 'm2-%' OR s_status <> 'COMPLETED'", "IF s_status <> 'COMPLETED'"),
    Mutation('sumber belum selesai lolos', T, "IF s_method NOT LIKE 'm2-%' OR s_status <> 'COMPLETED'", "IF s_method NOT LIKE 'm2-%'"),
    Mutation('sumber di dataset lain lolos', T, '       OR s_dataset IS DISTINCT FROM r_dataset THEN', '       OR false THEN'),
    Mutation('proposition investigasi lain lolos', T, 'IF p_inv IS DISTINCT FROM r_inv THEN', 'IF false THEN'),
    Mutation('cakupan bukan objek lolos', T, "IF jsonb_typeof(NEW.coverage) IS DISTINCT FROM 'object'\n       OR", 'IF false\n       OR', equivalent="bukan objek -> ->'targets_covered' NULL -> ditolak oleh syarat kedua"),
    Mutation('targets_covered tidak wajib', T, "OR jsonb_typeof(NEW.coverage->'targets_covered') IS DISTINCT FROM 'array'", 'OR false'),
    Mutation('pernyataan cakupan boleh kosong', T, "OR COALESCE(length(NEW.coverage->>'statement'), 0) = 0 THEN", 'OR false THEN'),
    Mutation('dimensions bukan objek lolos', T, "IF jsonb_typeof(NEW.dimensions) IS DISTINCT FROM 'object' THEN", 'IF false THEN'),
    Mutation('profil dapat diubah', T, 'CREATE TRIGGER profile_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER profile_append_only\n    BEFORE DELETE'),
    Mutation('profil dapat dihapus', T, 'CREATE TRIGGER profile_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER profile_append_only\n    BEFORE UPDATE'),
    Mutation('rencana seqscan tidak dimatikan', T, 'RETURNS trigger\n    SET enable_seqscan = off AS $$', 'RETURNS trigger\n    AS $$'),
]
