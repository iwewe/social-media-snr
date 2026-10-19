"""Mutasi penanda negasi M2 (A3; ADR 0044)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mutate import Mutation  # noqa: E402

COMMAND = "cd {root}/backend && /home/bagong/social-media-snr/backend/.venv/bin/python -m pytest -c pyproject.toml -q -x -p no:cacheprovider ../tests/test_m2_rules.py"
CWD = "{origin}"
TIMEOUT = 300
R = "backend/intelligence/m2/rules.py"

MUTATIONS = [
    Mutation("pro tak diperiksa", R, "for m in (*pro, *contra, *agree, *disagree)", "for m in (*contra, *agree, *disagree)"),
    Mutation("kontra tak diperiksa", R, "for m in (*pro, *contra, *agree, *disagree)", "for m in (*pro, *agree, *disagree)"),
    Mutation("setuju tak diperiksa", R, "for m in (*pro, *contra, *agree, *disagree)", "for m in (*pro, *contra, *disagree)"),
    Mutation("tidak setuju tak diperiksa", R, "for m in (*pro, *contra, *agree, *disagree)", "for m in (*pro, *contra, *agree)"),
    Mutation("tanda tinjauan tidak dipasang", R, "        if negated:\n            needs_review = True", "        if negated:\n            needs_review = False"),
    Mutation("rule tidak dicatat", R, "            basis[\"rules\"].append(\"review:negation_near_stance_cue\")", "            pass"),
    Mutation("basis negasi tidak dicatat", R, "            basis[\"matched\"][\"negation\"] = negated", "            pass"),
    Mutation("jendela bergeser", R, "split()[-self._negation_window :]", "split()[-self._negation_window - 1 :]"),
    Mutation("jendela menyempit", R, "split()[-self._negation_window :]", "split()[-self._negation_window + 1 :]"),
    Mutation("negasi bukan kata utuh", R, "if f\" {cue} \" in tail", "if cue in tail"),
    Mutation("teks setelah cue ikut dicek", R, "text[: match.start].split()", "text[: match.end].split()"),
    Mutation("fitur selalu mati", R, "if not self._negation or self._negation_window <= 0:", "if True:"),
    Mutation("jendela nol tetap dihitung", R, "or self._negation_window <= 0:", "or self._negation_window < 0:", equivalent="jendela 0 tidak lolos validasi; split()[-0:] hanya terjangkau lewat kelas tanpa parameter, yang cue-nya kosong"),
    Mutation("batas jendela 10 ditolak", R, "not 1 <= window <= _MAX_NEGATION_WINDOW", "not 1 <= window < _MAX_NEGATION_WINDOW"),
    Mutation("batas jendela 1 ditolak", R, "not 1 <= window <= _MAX_NEGATION_WINDOW", "not 1 < window <= _MAX_NEGATION_WINDOW"),
    Mutation("jendela bool diterima", R, "isinstance(window, bool)\n            or ", ""),
    Mutation("jendela non-int diterima", R, "or not isinstance(window, int)\n            or ", "or "),
    Mutation("cue negasi tak divalidasi", R, "        _cue_list(parameters[\"negation_cues\"], \"negation_cues\")\n        window", "        window"),
    Mutation("pasangan parsial diterima", R, "negation_keys not in (set(), _NEGATION_KEYS)", "False"),
    Mutation("kunci asing diterima", R, "keys - _NEGATION_KEYS != _PARAM_KEYS", "not _PARAM_KEYS <= keys"),
]
