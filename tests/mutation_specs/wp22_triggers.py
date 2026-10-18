"""Mutasi trigger ResponseAssessment (WP-2.2). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m2_assessment.py --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0004_assessment_triggers.py'

MUTATIONS = [
    Mutation('metode non-M2 diterima', T, "IF r_method NOT LIKE 'm2-%' THEN", 'IF false THEN'),
    Mutation('mesin menulis saat tidak RUNNING', T, "IF NEW.source = 'MACHINE' AND r_status <> 'RUNNING' THEN", 'IF false THEN'),
    Mutation('manusia menulis saat run belum selesai', T, "IF r_status <> 'COMPLETED' THEN", 'IF false THEN'),
    Mutation('penggantian lintas run', T, 'IF s_run IS DISTINCT FROM NEW.analysis_run_id\n           OR s_obs', 'IF false\n           OR s_obs'),
    Mutation('penggantian lintas observasi', T, 'OR s_obs IS DISTINCT FROM NEW.observation_id\n           OR s_prop', 'OR s_prop'),
    Mutation('penggantian lintas proposition', T, 'OR s_prop IS DISTINCT FROM NEW.proposition_id THEN', 'THEN'),
    Mutation('observasi di luar dataset', T, '    IF NOT FOUND THEN', '    IF false THEN'),
    Mutation('proposition investigasi lain', T, 'IF p_inv IS DISTINCT FROM r_inv THEN', 'IF false THEN'),
    Mutation('penilaian dapat diubah', T, 'CREATE TRIGGER assessment_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER assessment_append_only\n    BEFORE DELETE'),
    Mutation('penilaian dapat dihapus', T, 'CREATE TRIGGER assessment_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER assessment_append_only\n    BEFORE UPDATE'),
    Mutation('rencana seqscan tidak dimatikan', T, 'RETURNS trigger\n    SET enable_seqscan = off AS $$', 'RETURNS trigger\n    AS $$'),
]
