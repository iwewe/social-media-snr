"""Mutasi inti indikator koordinasi (WP-2.5). Murni, tanpa basis data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_co_indicators.py'
CWD = '{origin}'
TIMEOUT = 300
C = 'backend/intelligence/m4/coordination.py'
B = 'backend/intelligence/m4/baseline.py'
I = 'backend/intelligence/m4/indicators.py'

MUTATIONS = [
    Mutation('jendela waktu eksklusif di batas', C, '.total_seconds() > seconds:', '.total_seconds() >= seconds:'),
    Mutation('jendela waktu terlalu longgar', C, '.total_seconds() > seconds:', '.total_seconds() > seconds * 10:'),
    Mutation('balasan tanpa waktu ikut sinkron', C, '            if r.published_at is None:\n                events.exclusions["sync_unknown_time"] += 1\n            else:\n                by_parent[r.parent_post_id].append(r)', '            by_parent[r.parent_post_id].append(r)'),
    Mutation('amplifikasi tanpa waktu ikut', C, '            if r.published_at is None:\n                events.exclusions["amplification_unknown_time"] += 1\n            else:\n                by_original[r.amplified_post_id].append(r)', '            by_original[r.amplified_post_id].append(r)'),
    Mutation('panjang minimum teks diabaikan', C, 'if len(t) >= params.similarity_min_chars]', 'if True]'),
    Mutation('batas kemiripan eksklusif', C, 'if similarity >= params.similarity_threshold:', 'if similarity > params.similarity_threshold:'),
    Mutation('batas jumlah respons kemiripan diabaikan', C, 'if len(texts) > params.similarity_max_responses:', 'if False:'),
    Mutation('penjaga ukuran peristiwa dibuang', C, '    if count > params.max_pair_events:', '    if False:'),
    Mutation('jaccard salah', C, 'union = len(parents_by_actor[a]) + len(parents_by_actor[b]) - support', 'union = len(parents_by_actor[a]) + len(parents_by_actor[b])'),
    Mutation('minimum co-response diabaikan', C, 'if keep(support, params.co_response_min_shared):', 'if True:'),
    Mutation('minimum target berulang diabaikan', C, 'if keep(len(targets), params.repeated_min_shared_targets):', 'if True:'),
    Mutation('akun sama berpasangan dengan dirinya', C, '            if a != b:\n                per_pair[_pair(a, b)][token].update((i, j))', '            if True:\n                per_pair[_pair(a, b)][token].update((i, j))'),
    Mutation('tautan: query tidak dibuang', C, 'cleaned = re.split(r"[?#]", cleaned, maxsplit=1)[0].rstrip("/").lower()', 'cleaned = cleaned.rstrip("/").lower()'),
    Mutation('tautan: www tidak dibuang', C, 'return re.sub(r"^www\\.", "", cleaned)', 'return cleaned'),
    Mutation('frasa: tautan ikut jadi frasa', C, 'tokens = normalize(_URL.sub(" ", r.text)).split()', 'tokens = normalize(r.text).split()'),
    Mutation('frasa 0 tetap dihitung', C, '        if params.phrase_words:\n            tokens', '        if True:\n            tokens'),
    Mutation('dukungan CO-05 bukan pasangan respons', C, 'support = len(pairs_seen[pair]) if by_response_pairs else len(tokens)', 'support = len(tokens)'),
    Mutation('stance dipakai pembanding (statistik salah)', C, '    return float(pv.support)', '    return pv.value'),
    Mutation('korelasi bukti: tak pernah dependen', C, '        if per_indicator[a] & per_indicator[b]:\n            out[a].append(_label(b))', '        if False:\n            out[a].append(_label(b))'),
    Mutation('kelompok independen: tak pernah digabung', C, '        if per_indicator[a] & per_indicator[b]:\n            parent[find(a)] = find(b)', '        if False:\n            parent[find(a)] = find(b)'),
    Mutation('baseline: seed diabaikan', B, 'rng = random.Random(params.baseline_seed)', 'rng = random.Random(0)'),
    Mutation('baseline: label tidak diacak', B, '        rng.shuffle(shuffled)\n', ''),
    Mutation('baseline: persentil salah', B, 'rank = max(1, math.ceil(q * len(sorted_values)))', 'rank = max(1, math.floor(q * len(sorted_values)))'),
    Mutation('baseline: eksedansi tanpa +1', B, 'return round((1 + sum(1 for m in maxima if m >= value)) / (1 + len(maxima)), 6)', 'return round(sum(1 for m in maxima if m >= value) / len(maxima), 6)'),
    Mutation('baseline: melampaui bila >=', I, '"exceeds_baseline_p95": stat > p95,', '"exceeds_baseline_p95": stat >= p95,'),
    Mutation('baseline: statistik bukan dukungan', I, '"statistic": "support",', '"statistic": "value",'),
    Mutation('bukti tidak dipotong', I, 'observation_ids=ids[: params.evidence_limit],', 'observation_ids=ids,'),
    Mutation('tanda pemotongan salah', I, 'truncated=len(ids) > params.evidence_limit,', 'truncated=False,'),
    Mutation('hipotesis alternatif spesifik hilang', I, '[*ALTERNATIVE_HYPOTHESES, SPECIFIC_ALTERNATIVES[label]]', 'list(ALTERNATIVE_HYPOTHESES)'),
]
