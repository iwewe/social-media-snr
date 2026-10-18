"""Mutasi klasifier aturan M2 dan harness evaluasi (WP-2.2). Murni, tanpa basis data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_m2_rules.py ../tests/test_m2_evaluation.py'
CWD = '{origin}'
TIMEOUT = 300
R = 'backend/intelligence/m2/rules.py'
V = 'backend/intelligence/evaluation.py'

MUTATIONS = [
    Mutation('MIXED hanya bila salah satu', R, 'if len(pro) >= self._min and len(contra) >= self._min:', 'if len(pro) >= self._min or len(contra) >= self._min:'),
    Mutation('min_matches diabaikan (pro)', R, 'elif len(pro) >= self._min:', 'elif len(pro) >= 1:'),
    Mutation('min_matches diabaikan (kontra)', R, 'elif len(contra) >= self._min:', 'elif len(contra) >= 1:'),
    Mutation('flip stance terbalik', R, 'return IssueStance.CONTRA if stance is IssueStance.PRO else IssueStance.PRO', 'return IssueStance.PRO if stance is IssueStance.PRO else IssueStance.CONTRA'),
    Mutation('setuju+tidak setuju tetap propagasi', R, 'elif agree and not disagree and parent_stance is not None:', 'elif agree and parent_stance is not None:'),
    Mutation('parent_unknown diabaikan', R, '            and not item.parent_unknown\n', ''),
    Mutation('stance induk tak-pasti ikut propagasi', R, '            and parent.stance in (IssueStance.PRO, IssueStance.CONTRA)\n', ''),
    Mutation('kecocokan terpanjang tidak menang', R, 'and (o.end - o.start) > (m.end - m.start)', 'and (o.end - o.start) >= (m.end - m.start)'),
    Mutation('pangkas tidak dilakukan', R, '        if not inside:\n            kept.append(m)', '        kept.append(m)'),
    Mutation('alignment SUPPORT/OPPOSE tertukar', R, 'alignment = TargetAlignment.SUPPORT if same else TargetAlignment.OPPOSE', 'alignment = TargetAlignment.OPPOSE if same else TargetAlignment.SUPPORT'),
    Mutation('ancaman tanpa tinjauan', R, 'needs_review = Character.INTIMIDATION in characters', 'needs_review = False'),
    Mutation('cue simbol tidak cocok', R, 'if re.search(r"\\w", cue) is None:', 'if False:'),
    Mutation('kecocokan bukan kata utuh', R, 'pattern = rf"(?<!\\w){re.escape(cue)}(?!\\w)"', 'pattern = rf"{re.escape(cue)}"'),
    Mutation('sentimen negatif tertukar', R, 'if negative and not positive:\n            sentiment = Sentiment.NEGATIVE', 'if negative:\n            sentiment = Sentiment.NEGATIVE'),
    Mutation('teks kosong diklasifikasi', R, 'if item.text is None or not normalize(item.text):', 'if item.text is None:'),
    Mutation('NOT_RELEVANT terlalu longgar', R, 'elif char_hit & {"RC-08", "RC-09"} and not (char_hit - {"RC-08", "RC-09"}):', 'elif char_hit & {"RC-08", "RC-09"}:'),
    Mutation('kritik tidak menentang induk', R, 'alignment = TargetAlignment.OPPOSE\n                basis["rules"].append("alignment:criticism_opposes_parent")', 'alignment = TargetAlignment.UNCLEAR\n                basis["rules"].append("alignment:criticism_opposes_parent")'),
    Mutation('RC-10 tidak jadi cadangan', R, '        if not characters:\n            characters.append(Character.OTHER)', '        if not characters:\n            pass'),
    Mutation('parameter min_matches tak divalidasi', R, 'or not 1 <= min_matches <= 10', 'or False'),
    Mutation('presisi dihitung terbalik', V, 'precision = _ratio(tp, tp + fp)', 'precision = _ratio(tp, tp + fn)'),
    Mutation('recall dihitung terbalik', V, 'recall = _ratio(tp, tp + fn)', 'recall = _ratio(tp, tp + fp)'),
    Mutation('kappa tanpa koreksi kebetulan', V, 'return (observed - expected) / (1.0 - expected)', 'return observed'),
    Mutation('prediksi hilang dianggap benar', V, 'scored = [i for i in ids if i in predicted]', 'scored = ids'),
    Mutation('peringatan pilot dibuang', V, 'if len(gold) < MIN_PILOT_ITEMS:', 'if False:'),
    Mutation('dua penilai tanpa gold diterima', V, '        elif len(item.labels) == 1:', '        elif len(item.labels) >= 1:'),
]
