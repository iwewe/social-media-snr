"""Mutasi trigger temuan (WP-2.6). Memakai --create-db karena migrasi yang dimutasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -v {root}/datasets:/datasets:ro -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_findings.py --create-db'
CWD = '{origin}'
TIMEOUT = 900
T = 'backend/intelligence/migrations/0012_finding_triggers.py'

MUTATIONS = [
    Mutation('temuan dibuat tersegel', T, '        IF NEW.sealed_at IS NOT NULL THEN\n            RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n                MESSAGE = \'temuan harus dibuat belum tersegel\';', '        IF false THEN\n            RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n                MESSAGE = \'temuan harus dibuat belum tersegel\';'),
    Mutation('penerus: predesesor belum tersegel', T, 'IF p_sealed IS NULL OR p_inv IS DISTINCT FROM NEW.investigation_id', 'IF p_inv IS DISTINCT FROM NEW.investigation_id'),
    Mutation('penerus: lintas investigasi', T, 'IF p_sealed IS NULL OR p_inv IS DISTINCT FROM NEW.investigation_id\n               OR p_platform', 'IF p_sealed IS NULL\n               OR p_platform'),
    Mutation('penerus: lintas platform', T, '               OR p_platform IS DISTINCT FROM NEW.platform THEN', '               OR false THEN'),
    Mutation('temuan tersegel dapat diubah', T, '    IF OLD.sealed_at IS NOT NULL THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'temuan tersegel tidak dapat diubah\';', '    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'temuan tersegel tidak dapat diubah\';'),
    Mutation('penyegelan menyelundupkan judul', T, '(NEW.id, NEW.investigation_id, NEW.platform, NEW.title,', '(NEW.id, NEW.investigation_id, NEW.platform, OLD.title,'),
    Mutation('penyegelan tanpa tautan', T, '    IF n_runs < 1 OR n_obs < 1 THEN', '    IF false THEN'),
    Mutation('penyegelan tanpa empat sumbu bukti', T, "OR NOT (NEW.evidence_quality ?& ARRAY['integrity', 'provenance', 'completeness', 'relevance'])", 'OR false'),
    Mutation('tautan run: temuan tersegel', T, "    IF f_sealed IS NOT NULL THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'tautan tidak dapat ditambah pada temuan yang sudah tersegel';\n    END IF;\n    SELECT a.status", "    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'tautan tidak dapat ditambah pada temuan yang sudah tersegel';\n    END IF;\n    SELECT a.status"),
    Mutation('tautan run: run belum selesai', T, "IF r_status IS DISTINCT FROM 'COMPLETED' OR r_inv IS DISTINCT FROM f_inv", "IF r_inv IS DISTINCT FROM f_inv"),
    Mutation('tautan run: lintas investigasi', T, "IF r_status IS DISTINCT FROM 'COMPLETED' OR r_inv IS DISTINCT FROM f_inv\n       OR d_platform", "IF r_status IS DISTINCT FROM 'COMPLETED'\n       OR d_platform"),
    Mutation('tautan run: lintas platform', T, '       OR d_platform IS DISTINCT FROM f_platform THEN', '       OR false THEN'),
    Mutation('tautan observasi: bukan anggota dataset', T, '    IF NOT FOUND THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'observasi bukan anggota', '    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'observasi bukan anggota'),
    Mutation('tautan indikator: run tak tertaut', T, '    IF NOT FOUND THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'indikator harus', '    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'indikator harus'),
    Mutation('tinjauan pada temuan belum tersegel', T, '    IF f_sealed IS NULL THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'hanya temuan tersegel', '    IF false THEN\n        RAISE EXCEPTION USING ERRCODE = \'restrict_violation\',\n            MESSAGE = \'hanya temuan tersegel'),
    Mutation('pengesahan setelah penarikan', T, "                   WHERE finding_id = NEW.finding_id AND action = 'WITHDRAW') THEN", "                   WHERE finding_id = NEW.finding_id AND action = 'NONE') THEN"),
    Mutation('pengesahan setelah penerus disahkan', T, "                   WHERE s.supersedes_id = NEW.finding_id) THEN", "                   WHERE s.supersedes_id = -1) THEN"),
    Mutation('pengesahan: pemeriksaan kunci ? dibuang', T, "            IF NOT (f_alts ? k)", "            IF false AND NOT (f_alts ? k)", equivalent="redundan: kunci hilang juga tertangkap oleh pemeriksaan outcome IS NULL"),
    Mutation('pengesahan: hasil alternatif tak sah', T, "               OR (f_alts -> k ->> 'outcome') NOT IN ('RULED_OUT', 'NOT_RULED_OUT', 'CANNOT_ASSESS')\n", "               OR false\n"),
    Mutation('pengesahan: alasan alternatif kosong', T, "               OR length(btrim(COALESCE(f_alts -> k ->> 'reasoning', ''))) = 0 THEN", "               OR false THEN"),
    Mutation('temuan dapat dihapus', T, 'CREATE TRIGGER finding_no_delete BEFORE DELETE', 'CREATE TRIGGER finding_no_delete AFTER DELETE', equivalent="AFTER DELETE yang melempar galat membatalkan pernyataan sama seperti BEFORE"),
    Mutation('tinjauan dapat diubah', T, 'CREATE TRIGGER finding_review_append_only BEFORE UPDATE OR DELETE', 'CREATE TRIGGER finding_review_append_only BEFORE DELETE'),
    Mutation('tautan observasi dapat dihapus', T, 'CREATE TRIGGER finding_observation_append_only BEFORE UPDATE OR DELETE', 'CREATE TRIGGER finding_observation_append_only BEFORE UPDATE'),
    Mutation('rencana seqscan tidak dimatikan', T, 'CREATE FUNCTION snr_finding_review_guard() RETURNS trigger\n    SET enable_seqscan = off AS $$', 'CREATE FUNCTION snr_finding_review_guard() RETURNS trigger\n    AS $$'),
]
