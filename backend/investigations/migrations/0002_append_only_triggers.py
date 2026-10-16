"""Trigger PostgreSQL: tabel versi append-only dan proposition tak dapat diubah isinya.

Penjagaan di DB (bukan hanya kode aplikasi) agar queryset.update()/delete() dan akses SQL
langsung pun ditolak. Catatan: TRUNCATE tidak diblokir (akan merusak flush pada test).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION snr_forbid_modification() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION USING
        ERRCODE = 'restrict_violation',
        MESSAGE = format('tabel %s bersifat append-only: %s ditolak', TG_TABLE_NAME, TG_OP);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER issue_context_version_append_only
    BEFORE UPDATE OR DELETE ON investigations_issuecontextversion
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER target_context_version_append_only
    BEFORE UPDATE OR DELETE ON investigations_targetcontextversion
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();
CREATE TRIGGER target_proposition_stance_append_only
    BEFORE UPDATE OR DELETE ON investigations_targetpropositionstance
    FOR EACH ROW EXECUTE FUNCTION snr_forbid_modification();

CREATE FUNCTION snr_proposition_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'proposition tidak dapat dihapus';
    END IF;
    IF NEW.issue_id <> OLD.issue_id OR NEW.number <> OLD.number
       OR NEW.statement <> OLD.statement OR NEW.created_by_id <> OLD.created_by_id
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'isi proposition tidak dapat diubah; buat proposition baru';
    END IF;
    IF OLD.retired_at IS NOT NULL AND NEW.retired_at IS DISTINCT FROM OLD.retired_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'proposition yang sudah dinonaktifkan tidak dapat diubah';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER proposition_guard
    BEFORE UPDATE OR DELETE ON investigations_proposition
    FOR EACH ROW EXECUTE FUNCTION snr_proposition_guard();
"""

REVERSE = """
DROP TRIGGER proposition_guard ON investigations_proposition;
DROP FUNCTION snr_proposition_guard();
DROP TRIGGER target_proposition_stance_append_only ON investigations_targetpropositionstance;
DROP TRIGGER target_context_version_append_only ON investigations_targetcontextversion;
DROP TRIGGER issue_context_version_append_only ON investigations_issuecontextversion;
DROP FUNCTION snr_forbid_modification();
"""


class Migration(migrations.Migration):
    dependencies = [("investigations", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
