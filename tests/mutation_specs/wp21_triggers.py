"""Mutasi trigger integritas analisis I2 (WP-2.1). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_analysis_runs.py --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0002_integrity_triggers.py'

MUTATIONS = [
    Mutation('jumlah anggota tidak diperiksa saat segel', T, 'IF n <> NEW.observation_count THEN', 'IF false THEN'),
    Mutation('dataset tersegel boleh diubah', T, 'IF OLD.sealed_at IS NOT NULL THEN', 'IF false THEN'),
    Mutation('penyegelan menyelundupkan digest', T, 'NEW.observation_digest, NEW.selection', 'OLD.observation_digest, NEW.selection'),
    Mutation('penyegelan menyelundupkan nomor', T, '(NEW.id, NEW.investigation_id, NEW.platform, NEW.number,', '(NEW.id, NEW.investigation_id, NEW.platform, OLD.number,'),
    Mutation('anggota ditambah setelah segel', T, 'IF d_sealed IS NOT NULL THEN', 'IF false THEN'),
    Mutation('anggota platform lain lolos', T, 'IF o_platform IS DISTINCT FROM d_platform THEN', 'IF false THEN'),
    Mutation('anggota investigasi lain lolos', T, 'IF o_inv IS DISTINCT FROM d_inv THEN', 'IF false THEN'),
    Mutation('anggota dapat dihapus', T, 'CREATE TRIGGER dataset_member_append_only\n    BEFORE UPDATE OR DELETE', 'CREATE TRIGGER dataset_member_append_only\n    BEFORE UPDATE'),
    Mutation('run dibuat tidak PENDING', T, "IF NEW.status <> 'PENDING' THEN", 'IF false THEN'),
    Mutation('run pada dataset belum tersegel', T, 'IF d_sealed IS NULL THEN', 'IF false THEN'),
    Mutation('run pada investigasi lain', T, 'IF d_inv IS DISTINCT FROM NEW.investigation_id THEN', 'IF false THEN'),
    Mutation('konteks issue investigasi lain', T, 'IF c_inv IS DISTINCT FROM NEW.investigation_id THEN', 'IF false THEN'),
    Mutation('run sebelumnya investigasi lain', T, 'IF p_inv IS DISTINCT FROM NEW.investigation_id THEN', 'IF false THEN'),
    Mutation('metode run dapat diubah', T, 'NEW.issue_context_version_id, NEW.method, NEW.method_version', 'NEW.issue_context_version_id, OLD.method, NEW.method_version'),
    Mutation('parameter run dapat diubah', T, 'NEW.method_version, NEW.parameters,', 'NEW.method_version, OLD.parameters,'),
    Mutation('PENDING boleh langsung COMPLETED', T, "NEW.status IN ('RUNNING', 'FAILED'))", "NEW.status IN ('RUNNING', 'FAILED', 'COMPLETED'))"),
    Mutation('status terminal boleh berubah', T, "OR (OLD.status = 'RUNNING' AND NEW.status IN ('COMPLETED', 'FAILED'))", "OR (OLD.status IN ('RUNNING', 'COMPLETED') AND NEW.status IN ('COMPLETED', 'FAILED'))"),
    Mutation('konteks target ditambah setelah mulai', T, "IF r_status <> 'PENDING' THEN", 'IF false THEN'),
    Mutation('target beda investigasi/platform lolos', T, 'IF t_inv IS DISTINCT FROM r_inv OR t_platform IS DISTINCT FROM r_platform THEN', 'IF false THEN'),
    Mutation('versi konteks milik target lain', T, 'IF c_target IS DISTINCT FROM NEW.target_id THEN', 'IF false THEN'),
    Mutation('rencana seqscan tidak dimatikan', T, 'CREATE FUNCTION snr_dataset_member_guard() RETURNS trigger\n    SET enable_seqscan = off AS $$', 'CREATE FUNCTION snr_dataset_member_guard() RETURNS trigger\n    AS $$'),
]
