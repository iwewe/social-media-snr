"""Penjaga status InspectionRun di database (WP-1.6).

Memperluas `snr_run_guard` (WP-1.2) dengan:
- tabel transisi status yang SAMA dengan `collection.orchestrator.states.TRANSITIONS` (tes
  membandingkan keduanya untuk semua 64 pasangan status);
- imutabilitas data hasil run yang sudah final: setelah COMPLETED, PARTIAL, FAILED,
  ACCESS_RESTRICTED, UNSUPPORTED, atau REVIEW_REQUIRED, kolom coverage, limitations, source_method,
  collector, started_at, dan finished_at tidak dapat diubah. Kolom ingestion, reconciliation,
  preservation, dan review tetap dapat ditulis (rekonsiliasi dan tinjauan terjadi setelah final).
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION snr_run_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'InspectionRun tidak dapat dihapus';
    END IF;
    IF NEW.public_id <> OLD.public_id OR NEW.target_id <> OLD.target_id
       OR NEW.sequence <> OLD.sequence OR NEW.requested::text <> OLD.requested::text
       OR NEW.requested_by_id <> OLD.requested_by_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'kolom identitas InspectionRun tidak dapat diubah';
    END IF;
    IF NEW.status <> OLD.status AND NOT (
        (OLD.status = 'PENDING'
            AND NEW.status IN ('RUNNING', 'FAILED', 'UNSUPPORTED'))
        OR (OLD.status = 'RUNNING'
            AND NEW.status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'ACCESS_RESTRICTED',
                               'UNSUPPORTED', 'REVIEW_REQUIRED'))
        OR (OLD.status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'ACCESS_RESTRICTED', 'UNSUPPORTED')
            AND NEW.status = 'REVIEW_REQUIRED')
        OR (OLD.status = 'REVIEW_REQUIRED'
            AND NEW.status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'ACCESS_RESTRICTED',
                               'UNSUPPORTED'))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = format('transisi status %s -> %s tidak diizinkan', OLD.status, NEW.status);
    END IF;
    IF OLD.status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'ACCESS_RESTRICTED', 'UNSUPPORTED',
                      'REVIEW_REQUIRED')
       AND (NEW.coverage IS DISTINCT FROM OLD.coverage
            OR NEW.limitations IS DISTINCT FROM OLD.limitations
            OR NEW.source_method <> OLD.source_method
            OR NEW.collector_name <> OLD.collector_name
            OR NEW.collector_version <> OLD.collector_version
            OR NEW.started_at IS DISTINCT FROM OLD.started_at
            OR NEW.finished_at IS DISTINCT FROM OLD.finished_at) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'data hasil run yang sudah final tidak dapat diubah';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

REVERSE = """
CREATE OR REPLACE FUNCTION snr_run_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'InspectionRun tidak dapat dihapus';
    END IF;
    IF NEW.public_id <> OLD.public_id OR NEW.target_id <> OLD.target_id
       OR NEW.sequence <> OLD.sequence OR NEW.requested::text <> OLD.requested::text
       OR NEW.requested_by_id <> OLD.requested_by_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'kolom identitas InspectionRun tidak dapat diubah';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [("collection", "0008_run_claim_and_review")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
