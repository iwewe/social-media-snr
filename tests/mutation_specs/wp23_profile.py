"""Mutasi dimensi dan perbandingan profil M3 (WP-2.3). Murni, tanpa basis data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m3_profile.py'
CWD = '{origin}'
TIMEOUT = 300
P = 'backend/intelligence/m3/profile.py'
C = 'backend/intelligence/m3/compare.py'

MUTATIONS = [
    Mutation('stance: ambang diabaikan', P, '    n = len(records)\n    if n < params.min_responses:\n        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)\n    counts = Counter(r.stance for r in records)', '    n = len(records)\n    if False:\n        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)\n    counts = Counter(r.stance for r in records)'),
    Mutation('karakter: ambang diabaikan', P, '    n = len(records)\n    if n < params.min_responses:\n        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)\n    counts = Counter(c for r in records for c in r.characters)', '    n = len(records)\n    if False:\n        return _insufficient("respons terlalu sedikit untuk distribusi", n, params.min_responses)\n    counts = Counter(c for r in records for c in r.characters)'),
    Mutation('temporal: ambang diabaikan', P, 'if len(indexed) < params.min_responses:', 'if False:'),
    Mutation('konsentrasi: satu target tetap dihitung', P, 'if targets_in_dataset < 2:', 'if False:'),
    Mutation('konsentrasi: ambang diabaikan', P, '    if n < params.min_responses:\n        return _insufficient("respons terlalu sedikit", n, params.min_responses)\n    counts = Counter(r.target_id for r in records)', '    if False:\n        return _insufficient("respons terlalu sedikit", n, params.min_responses)\n    counts = Counter(r.target_id for r in records)'),
    Mutation('narasi: ambang diabaikan', P, 'if len(texts) < params.narrative_min_texts:', 'if False:'),
    Mutation('evolusi: ambang diabaikan', P, 'if len(per_bucket) < params.min_active_buckets:', 'if False:'),
    Mutation('periode: batas akhir inklusif', P, 'if not params.period_start <= record.published_at < params.period_end:', 'if not params.period_start <= record.published_at <= params.period_end:'),
    Mutation('periode: batas awal eksklusif', P, 'if not params.period_start <= record.published_at < params.period_end:', 'if not params.period_start < record.published_at < params.period_end:'),
    Mutation('bucket: lebar salah', P, '// timedelta(hours=params.bucket_hours)', '// timedelta(hours=1)'),
    Mutation('porsi dibulatkan salah', P, 'return round(count / total, 4)', 'return round(count / total, 1)'),
    Mutation('seri target tidak deterministik', P, 'key=lambda kv: (-kv[1], kv[0])', 'key=lambda kv: (-kv[1], -kv[0])'),
    Mutation('kelompok berulang: hitung salah', P, 'repeated = sum(c for c in counts.values() if c > 1)', 'repeated = sum(1 for c in counts.values() if c > 1)'),
    Mutation('kelompok terbesar salah', P, '"largest_repeated_group": max(counts.values()),', '"largest_repeated_group": min(counts.values()),'),
    Mutation('perbandingan: cakupan sebagian tak diperingatkan', C, '    if cov.get("partial_coverage"):', '    if False:'),
    Mutation('perbandingan: pemeriksaan tak lengkap tak diperingatkan', C, '    if cov.get("incomplete_runs"):', '    if False:'),
    Mutation('perbandingan: waktu tak diketahui tak diperingatkan', C, '    if cov.get("responses_without_known_time"):', '    if False:'),
    Mutation('perbandingan: platform berbeda lolos', C, 'if ca["platform"] != cb["platform"]:', 'if False:'),
    Mutation('perbandingan: target berbeda tak diperingatkan', C, 'if set(ca["targets_covered"]) != set(cb["targets_covered"]):', 'if False:'),
    Mutation('perbandingan: periode berbeda tak diperingatkan', C, 'if ca["period"] != cb["period"]:', 'if False:'),
    Mutation('perbandingan: dataset berbeda tak diperingatkan', C, 'if ca["dataset_version"] != cb["dataset_version"]:', 'if False:'),
    Mutation('perbandingan: proposition berbeda tak diperingatkan', C, 'if ca["proposition_id"] != cb["proposition_id"]:', 'if False:'),
    Mutation('perbandingan: data kurang dianggap sebanding', C, 'usable = da["status"] == OK and db["status"] == OK', 'usable = True'),
]
