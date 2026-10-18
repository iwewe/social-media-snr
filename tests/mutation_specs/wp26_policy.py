"""Mutasi kebijakan M5 murni (WP-2.6)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m5_policy.py'
CWD = '{origin}'
TIMEOUT = 300
P = 'backend/intelligence/m5/policy.py'
V = 'backend/intelligence/m5/verdict_terms.txt'

MUTATIONS = [
    Mutation('data sintetis tidak membatasi', P, '    if synthetic:', '    if False:'),
    Mutation('sumbu buruk hanya membatasi ke MODERATE', P, 'cap(Confidence.LOW, f"sumbu bukti \'{axis}\' bernilai {level.value}")', 'cap(Confidence.MODERATE, f"sumbu bukti \'{axis}\' bernilai {level.value}")'),
    Mutation('sumbu NOT_ASSESSABLE tak membatasi', P, '        if level in (QualityLevel.POOR, QualityLevel.NOT_ASSESSABLE):', '        if level in (QualityLevel.POOR,):'),
    Mutation('sumbu POOR tak membatasi', P, '        if level in (QualityLevel.POOR, QualityLevel.NOT_ASSESSABLE):', '        if level in (QualityLevel.NOT_ASSESSABLE,):'),
    Mutation('alternatif belum disingkirkan membatasi ke LOW', P, 'cap(Confidence.MODERATE, f"hipotesis alternatif \'{key}\' belum dapat disingkirkan")', 'cap(Confidence.LOW, f"hipotesis alternatif \'{key}\' belum dapat disingkirkan")'),
    Mutation('alternatif belum dinilai tak membatasi', P, '        elif outcome != AlternativeOutcome.RULED_OUT:', '        elif False:'),
    Mutation('satu kelompok bukti dianggap cukup', P, 'if independent_groups is None or independent_groups < 2:', 'if independent_groups is None or independent_groups < 1:'),
    Mutation('kelompok bukti tak diketahui dianggap cukup', P, 'if independent_groups is None or independent_groups < 2:', 'if independent_groups is not None and independent_groups < 2:'),
    Mutation('plafon terendah tidak menang', P, 'if CONFIDENCE_RANK[level] < CONFIDENCE_RANK[ceiling]:', 'if CONFIDENCE_RANK[level] > CONFIDENCE_RANK[ceiling]:'),
    Mutation('NOT_ASSESSABLE tidak selalu diizinkan', P, '    if chosen is Confidence.NOT_ASSESSABLE:\n        return True, ceiling, reasons', '    if False:\n        return True, ceiling, reasons'),
    Mutation('confidence boleh melampaui plafon', P, 'return CONFIDENCE_RANK[chosen] <= CONFIDENCE_RANK[ceiling], ceiling, reasons', 'return True, ceiling, reasons'),
    Mutation('vonis tidak ditolak', P, '    if found:', '    if False:'),
    Mutation('kata terlarang buzzer dihapus', V, '\nbuzzer\n', '\n'),
    Mutation('kata terlarang troll dihapus', V, '\ntroll\n', '\n'),
    Mutation('kata terlarang botnet dihapus', V, '\nbotnet\n', '\n'),
    Mutation('kata terlarang dikendalikan dihapus', V, '\ndikendalikan\n', '\n'),
    Mutation('kata terlarang dibayar dihapus', V, '\ndibayar\n', '\n'),
    Mutation('batas kata awal dibuang', P, 'r"(?<!\\w)(" + "|".join(_load_terms()) + r")(?!\\w)"', 'r"(" + "|".join(_load_terms()) + r")(?!\\w)"'),
    Mutation('batas kata akhir dibuang', P, 'r"(?<!\\w)(" + "|".join(_load_terms()) + r")(?!\\w)"', 'r"(?<!\\w)(" + "|".join(_load_terms()) + r")"'),
    Mutation('hasil alternatif tak divalidasi', P, '            and item.get("outcome") in {o.value for o in AlternativeOutcome}', '            and True'),
    Mutation('alasan alternatif boleh kosong', P, '            and item["reasoning"].strip()', '            and True'),
    Mutation('integritas: tanpa artefak dianggap baik', P, '    if total == 0:', '    if False:'),
    Mutation('integritas: kegagalan hash diabaikan', P, '    if problems:', '    if False:'),
    Mutation('integritas: sebagian terverifikasi dianggap semua', P, '    if facts["verified_match"] == total:', '    if facts["verified_match"] > 0:'),
    Mutation('integritas: belum diverifikasi dianggap cukup', P, '    if facts["verified_match"] == 0:', '    if False:'),
    Mutation('kelengkapan: hasil buruk diabaikan', P, '    if any(r["outcome"] in _BAD_OUTCOMES for r in runs):', '    if False:'),
    Mutation('kelengkapan: paginasi tak diketahui diabaikan', P, '    if any(r["pagination_complete"] is None for r in runs):', '    if False:'),
    Mutation('kelengkapan: paginasi tak lengkap diabaikan', P, '    if any(r["pagination_complete"] is False for r in runs):', '    if False:'),
    Mutation('kelengkapan: keterbatasan diabaikan', P, '    if any(r["limitations"] for r in runs):', '    if False:'),
    Mutation('asal: sintetis murni dianggap baik', P, '    if ms == {"synthetic_fixture"}:', '    if False:'),
    Mutation('asal: sintetis campuran dianggap baik', P, '    if "synthetic_fixture" in ms:', '    if False:'),
    Mutation('asal: dataset impor dianggap baik', P, '    if "imported_dataset" in ms:', '    if False:'),
    Mutation('sumbu bukti tidak wajib lengkap', P, '    if set(ratings) != set(AXES):', '    if False:'),
    Mutation('penilaian lebih baik dari saran tanpa override', P, '            and QUALITY_RANK[level] > QUALITY_RANK[suggested[0]]', '            and False'),
    Mutation('override_reason tidak diwajibkan', P, '            and not str(item.get("override_reason", "")).strip()', '            and False'),
    Mutation('saran NOT_ASSESSABLE ikut mengikat', P, '            and suggested[0] is not QualityLevel.NOT_ASSESSABLE\n', ''),
]
