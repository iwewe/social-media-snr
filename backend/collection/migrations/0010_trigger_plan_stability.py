"""Stabilitas rencana query pada trigger penjaga (A2; ADR 0020).

Fungsi PL/pgSQL men-cache rencana query per sesi. Setelah VACUUM pada tabel kosong (statistik 0/0),
pencarian `WHERE id = ...` pada batch pertama (tabel baru 500 baris) direncanakan sebagai Seq Scan,
rencana itu tetap dipakai ketika tabel membesar, dan tiap baris memindai tabel: kuadratik (20 detik per
10.000 objek, normalnya 6). Fungsi-fungsi ini HANYA mencari baris lewat primary key, jadi
`enable_seqscan = off` pada fungsi (bukan global) membuat rencana yang di-cache pasti memakai indeks,
tanpa biaya perencanaan ulang per panggilan (alternatif `plan_cache_mode = force_custom_plan` stabil
tetapi menambah 40-60% waktu pada beban normal; ADR 0020).
"""

from django.db import migrations

FUNCTIONS = [
    "snr_run_platform(bigint)",
    "snr_identity_platform_guard()",
    "snr_observation_platform_guard()",
    "snr_relation_platform_guard()",
    "snr_reconciliation_guard()",
]
FORWARD = "\n".join(f"ALTER FUNCTION {f} SET enable_seqscan = off;" for f in FUNCTIONS)
REVERSE = "\n".join(f"ALTER FUNCTION {f} RESET enable_seqscan;" for f in FUNCTIONS)


class Migration(migrations.Migration):
    dependencies = [("collection", "0009_run_status_guard")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
