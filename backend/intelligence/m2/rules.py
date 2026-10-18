"""Klasifier M2 berbasis aturan yang dapat diperiksa (WP-2.2; keputusan D-01 belum diambil).

Ini BASELINE untuk menguji seluruh alur dan harness evaluasi, bukan klaim kualitas model.
Seluruh "pengetahuan" (cue stance per proposition, cue persetujuan/ketidaksetujuan, cue karakter,
cue sentimen, jumlah kecocokan minimum) datang dari parameter eksplisit AnalysisRun yang ditulis
analis; tidak ada daftar bawaan tersembunyi. Setiap hasil membawa `basis`: cue yang cocok, asal
propagasi dari induk, dan aturan yang terpakai.

Aturan (urut):
1. Kecocokan = frasa utuh (huruf kecil, tanda baca diratakan). Kecocokan yang terkandung dalam
   kecocokan lain yang lebih panjang dibuang ("tidak perlu diaudit" mengalahkan "diaudit").
2. Stance dari cue proposition: hanya pro -> PRO; hanya kontra -> CONTRA; keduanya -> MIXED.
3. Tanpa cue stance: persetujuan/ketidaksetujuan terhadap induk langsung menurunkan stance dari
   stance induk (setuju -> sama; tidak setuju -> berlawanan) HANYA bila stance induk PRO/CONTRA
   dan induk diketahui.
4. Selain itu UNDETERMINED (atau NOT_RELEVANT bila hanya cue pengalih/promosi). Teks tidak
   tersedia -> UNDETERMINED.
5. Target alignment dinilai terhadap INDUK LANGSUNG, terpisah dari stance isu.
6. Karakter multi-label dari cue; RC-10 bila tak ada. RC-07 selalu menandai tinjauan manusia.
Sarkasme tidak dideteksi di luar cue yang diberikan analis; ketidakmampuan itu dicatat di
evaluasi, bukan disembunyikan.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .taxonomy import Character, IssueStance, Sentiment, TargetAlignment
from .types import Assessment, ClassifierInput

_CHARACTER_CUE_CODES = ("RC-02", "RC-04", "RC-05", "RC-06", "RC-07", "RC-08", "RC-09")
_MAX_CUES = 500
_MAX_CUE_LEN = 200
_PARAM_KEYS = {
    "propositions",
    "agree_cues",
    "disagree_cues",
    "character_cues",
    "sentiment_cues",
    "min_matches",
}


class RulesParameterError(ValueError):
    pass


def normalize(text: str) -> str:
    """Huruf kecil; tanda baca selain '?' diratakan jadi spasi; spasi dirapatkan."""
    lowered = text.casefold()
    flattened = re.sub(r"[^\w?]+", " ", lowered, flags=re.UNICODE).replace("_", " ")
    return re.sub(r"\s+", " ", flattened).strip()


@dataclass(frozen=True)
class _Match:
    klass: str
    cue: str
    start: int
    end: int


def _cue_list(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > _MAX_CUES:
        raise RulesParameterError(f"{where}: harus daftar string (maks {_MAX_CUES})")
    out = []
    for cue in value:
        if not isinstance(cue, str) or not normalize(cue) or len(cue) > _MAX_CUE_LEN:
            raise RulesParameterError(
                f"{where}: cue harus string tidak kosong (maks {_MAX_CUE_LEN})"
            )
        out.append(normalize(cue))
    return tuple(dict.fromkeys(out))


def validate_parameters(parameters: Mapping[str, Any]) -> None:
    if set(parameters) != _PARAM_KEYS:
        raise RulesParameterError(f"parameter wajib tepat: {sorted(_PARAM_KEYS)}")
    min_matches = parameters["min_matches"]
    if (
        isinstance(min_matches, bool)
        or not isinstance(min_matches, int)
        or not 1 <= min_matches <= 10
    ):
        raise RulesParameterError("min_matches harus bilangan bulat 1..10")
    props = parameters["propositions"]
    if not isinstance(props, dict) or not props:
        raise RulesParameterError("propositions: minimal satu proposition")
    for key, spec in props.items():
        if (
            not str(key).isdigit()
            or not isinstance(spec, dict)
            or set(spec) != {"pro_cues", "contra_cues"}
        ):
            raise RulesParameterError(
                "propositions: kunci id proposition dengan pro_cues dan contra_cues"
            )
        _cue_list(spec["pro_cues"], f"propositions.{key}.pro_cues")
        _cue_list(spec["contra_cues"], f"propositions.{key}.contra_cues")
    _cue_list(parameters["agree_cues"], "agree_cues")
    _cue_list(parameters["disagree_cues"], "disagree_cues")
    chars = parameters["character_cues"]
    if not isinstance(chars, dict) or set(chars) != set(_CHARACTER_CUE_CODES):
        raise RulesParameterError(f"character_cues: wajib tepat {list(_CHARACTER_CUE_CODES)}")
    for code, cues in chars.items():
        _cue_list(cues, f"character_cues.{code}")
    sentiments = parameters["sentiment_cues"]
    if not isinstance(sentiments, dict) or set(sentiments) != {"POSITIVE", "NEGATIVE"}:
        raise RulesParameterError("sentiment_cues: wajib tepat POSITIVE dan NEGATIVE")
    for name, cues in sentiments.items():
        _cue_list(cues, f"sentiment_cues.{name}")


def _find(text: str, cue: str, klass: str) -> list[_Match]:
    if re.search(r"\w", cue) is None:  # cue simbol murni (mis. "?") dicocokkan sebagai substring
        return [_Match(klass, cue, m.start(), m.end()) for m in re.finditer(re.escape(cue), text)]
    pattern = rf"(?<!\w){re.escape(cue)}(?!\w)"
    return [_Match(klass, cue, m.start(), m.end()) for m in re.finditer(pattern, text)]


def _prune(matches: list[_Match]) -> list[_Match]:
    """Buang kecocokan yang seluruhnya terkandung dalam kecocokan lain yang lebih panjang."""
    kept = []
    for m in matches:
        inside = any(
            o is not m
            and o.start <= m.start
            and m.end <= o.end
            and (o.end - o.start) > (m.end - m.start)
            for o in matches
        )
        if not inside:
            kept.append(m)
    return kept


def _flip(stance: IssueStance) -> IssueStance:
    return IssueStance.CONTRA if stance is IssueStance.PRO else IssueStance.PRO


class RulesClassifier:
    """`classify(input) -> Assessment`. Murni dan deterministik atas parameter yang diberikan."""

    name = "m2-rules"
    version = "1"

    def __init__(self, parameters: Mapping[str, Any]) -> None:
        validate_parameters(parameters)
        self._min = int(parameters["min_matches"])
        self._props = {
            int(k): (_cue_list(v["pro_cues"], k), _cue_list(v["contra_cues"], k))
            for k, v in parameters["propositions"].items()
        }
        self._agree = _cue_list(parameters["agree_cues"], "agree_cues")
        self._disagree = _cue_list(parameters["disagree_cues"], "disagree_cues")
        self._chars = {
            c: _cue_list(parameters["character_cues"][c], c) for c in _CHARACTER_CUE_CODES
        }
        self._sent = {
            k: _cue_list(parameters["sentiment_cues"][k], k) for k in ("POSITIVE", "NEGATIVE")
        }

    def _proposition_cues(
        self, proposition_id: int | None
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if proposition_id is None or proposition_id not in self._props:
            raise RulesParameterError(f"proposition {proposition_id} tidak ada dalam parameter")
        return self._props[proposition_id]

    def classify(self, item: ClassifierInput) -> Assessment:
        basis: dict[str, Any] = {"method": f"{self.name} v{self.version}", "rules": []}
        if item.text is None or not normalize(item.text):
            basis["rules"].append("text_unavailable")
            return Assessment(
                IssueStance.UNDETERMINED,
                TargetAlignment.UNCLEAR,
                (Character.OTHER,),
                basis=basis,
            )
        text = normalize(item.text)
        pro_cues, contra_cues = self._proposition_cues(item.proposition.id)
        stance_matches = _prune(
            [m for cue in pro_cues for m in _find(text, cue, "pro")]
            + [m for cue in contra_cues for m in _find(text, cue, "contra")]
        )
        pro = [m for m in stance_matches if m.klass == "pro"]
        contra = [m for m in stance_matches if m.klass == "contra"]
        # persetujuan dan ketidaksetujuan dipangkas bersama: "tidak sependapat" > "sependapat"
        agreement = _prune(
            [m for cue in self._agree for m in _find(text, cue, "agree")]
            + [m for cue in self._disagree for m in _find(text, cue, "disagree")]
        )
        agree = [m for m in agreement if m.klass == "agree"]
        disagree = [m for m in agreement if m.klass == "disagree"]
        char_matches = {
            code: _prune([m for cue in cues for m in _find(text, cue, code)])
            for code, cues in self._chars.items()
        }
        char_hit = {code for code, found in char_matches.items() if found}
        parent = item.direct_parent
        parent_stance = (
            parent.stance
            if parent is not None
            and not item.parent_unknown
            and parent.stance in (IssueStance.PRO, IssueStance.CONTRA)
            else None
        )

        stance: IssueStance
        if len(pro) >= self._min and len(contra) >= self._min:
            stance = IssueStance.MIXED
            basis["rules"].append("stance:pro_and_contra_cues")
        elif len(pro) >= self._min:
            stance = IssueStance.PRO
            basis["rules"].append("stance:pro_cue")
        elif len(contra) >= self._min:
            stance = IssueStance.CONTRA
            basis["rules"].append("stance:contra_cue")
        elif agree and not disagree and parent_stance is not None:
            stance = parent_stance
            basis["rules"].append("stance:agree_with_parent")
            basis["propagated_from"] = "direct_parent"
        elif disagree and not agree and parent_stance is not None:
            stance = _flip(parent_stance)
            basis["rules"].append("stance:disagree_with_parent")
            basis["propagated_from"] = "direct_parent"
        elif char_hit & {"RC-08", "RC-09"} and not (char_hit - {"RC-08", "RC-09"}):
            stance = IssueStance.NOT_RELEVANT
            basis["rules"].append("stance:diversion_or_promotion_only")
        else:
            stance = IssueStance.UNDETERMINED
            basis["rules"].append("stance:no_decisive_cue")
            if (agree or disagree) and parent_stance is None:
                basis["rules"].append("agreement_without_known_parent_stance")

        decided = stance in (IssueStance.PRO, IssueStance.CONTRA)
        if decided and parent_stance is not None:
            same = stance is parent_stance
            alignment = TargetAlignment.SUPPORT if same else TargetAlignment.OPPOSE
            basis["rules"].append("alignment:stance_vs_parent")
        else:
            alignment = TargetAlignment.UNCLEAR

        characters: list[Character] = []
        supports = bool(agree and not disagree) or (decided and stance is parent_stance)
        opposes = bool(disagree and not agree) or (
            decided and parent_stance is not None and stance is not parent_stance
        )
        if supports:
            characters.append(Character.SUPPORT)
        if "RC-02" in char_hit:
            characters.append(Character.SUBSTANTIVE_CRITICISM)
        if opposes:
            characters.append(Character.COUNTERARGUMENT)
        for code in ("RC-04", "RC-05", "RC-06", "RC-07", "RC-08", "RC-09"):
            if code in char_hit:
                characters.append(Character(code))
        if not characters:
            characters.append(Character.OTHER)
        if alignment is TargetAlignment.UNCLEAR:
            critical = (Character.SUBSTANTIVE_CRITICISM, Character.COUNTERARGUMENT)
            if any(c in characters for c in critical):
                alignment = TargetAlignment.OPPOSE
                basis["rules"].append("alignment:criticism_opposes_parent")
            elif Character.SUPPORT in characters:
                alignment = TargetAlignment.SUPPORT
                basis["rules"].append("alignment:agreement_supports_parent")

        sentiment: Sentiment | None = None
        negative = [m for cue in self._sent["NEGATIVE"] for m in _find(text, cue, "NEGATIVE")]
        positive = [m for cue in self._sent["POSITIVE"] for m in _find(text, cue, "POSITIVE")]
        if negative and not positive:
            sentiment = Sentiment.NEGATIVE
        elif positive and not negative:
            sentiment = Sentiment.POSITIVE

        needs_review = Character.INTIMIDATION in characters
        if needs_review:
            basis["rules"].append("review:intimidation_requires_human")
        basis["matched"] = {
            "pro": sorted({m.cue for m in pro}),
            "contra": sorted({m.cue for m in contra}),
            "agree": sorted({m.cue for m in agree}),
            "disagree": sorted({m.cue for m in disagree}),
            "characters": {
                c: sorted({m.cue for m in found}) for c, found in char_matches.items() if found
            },
            "sentiment": sorted({m.cue for m in negative + positive}),
        }
        basis["parent_chain_length"] = len(item.parent_chain)
        return Assessment(
            issue_stance=stance,
            target_alignment=alignment,
            response_character=tuple(dict.fromkeys(characters)),
            expression_sentiment=sentiment,
            needs_human_review=needs_review,
            basis=basis,
        )
