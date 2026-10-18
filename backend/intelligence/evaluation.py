"""Harness evaluasi klasifikasi M2 (WP-2.2e; PRD 16.3). Murni (tanpa Django).

Memuat set anotasi, menghitung kesepakatan antar-penilai (kappa Cohen), precision/recall/F1 per
kelas, matriks kebingungan, dan analisis galat per tag (sarkasme, parent bertingkat, bahasa
informal, ...). Seluruh keluaran bersifat PILOT: ukuran contoh kecil, tanpa interval kepercayaan,
dan tidak boleh dibaca sebagai kualitas model yang terbukti (PRD 16.3). Hasil atas data sintetis
hanya menguji alur.
"""

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .m2.taxonomy import Character, IssueStance, TargetAlignment

PILOT_NOTICE = (
    "PILOT - bukan klaim kualitas. Contoh kecil, tanpa interval kepercayaan; hasil atas data "
    "sintetis hanya menguji alur. Pilihan model/penyedia (D-01) tidak boleh didasarkan pada "
    "angka ini saja."
)
MIN_PILOT_ITEMS = 50
SINGLE_DIMENSIONS = {
    "issue_stance": [m.value for m in IssueStance],
    "target_alignment": [m.value for m in TargetAlignment],
}
CHARACTER_CODES = [m.value for m in Character]
MAX_ERRORS_LISTED = 200


class AnnotationError(ValueError):
    pass


# --- format anotasi -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Labels:
    issue_stance: str
    target_alignment: str
    response_character: tuple[str, ...]

    @staticmethod
    def parse(raw: Any, where: str) -> "Labels":
        if not isinstance(raw, dict) or set(raw) != {
            "issue_stance",
            "target_alignment",
            "response_character",
        }:
            raise AnnotationError(
                f"{where}: wajib tepat issue_stance, target_alignment, response_character"
            )
        stance, alignment = raw["issue_stance"], raw["target_alignment"]
        if stance not in SINGLE_DIMENSIONS["issue_stance"]:
            raise AnnotationError(f"{where}.issue_stance tidak sah: {stance!r}")
        if alignment not in SINGLE_DIMENSIONS["target_alignment"]:
            raise AnnotationError(f"{where}.target_alignment tidak sah: {alignment!r}")
        characters = raw["response_character"]
        if (
            not isinstance(characters, list)
            or not characters
            or any(c not in CHARACTER_CODES for c in characters)
        ):
            raise AnnotationError(f"{where}.response_character: daftar kode RC-xx tidak kosong")
        return Labels(stance, alignment, tuple(sorted(set(characters))))


@dataclass(frozen=True)
class Item:
    id: str
    tags: tuple[str, ...]
    labels: Mapping[str, Labels]  # penilai -> label
    gold: Labels | None = None  # putusan akhir (adjudikasi) bila ada


def load_annotations(raw: Any) -> list[Item]:
    """`{"schema_version": 1, "items": [{"id", "tags", "labels": {penilai: {...}}, "gold"?}]}`."""
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or "items" not in raw:
        raise AnnotationError("berkas anotasi: wajib schema_version 1 dan items")
    items, seen = [], set()
    for n, entry in enumerate(raw["items"]):
        where = f"items[{n}]"
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise AnnotationError(f"{where}.id wajib string")
        if entry["id"] in seen:
            raise AnnotationError(f"{where}: id ganda {entry['id']!r}")
        seen.add(entry["id"])
        labels_raw = entry.get("labels", {})
        if not isinstance(labels_raw, dict) or not labels_raw:
            raise AnnotationError(f"{where}.labels: minimal satu penilai")
        labels = {a: Labels.parse(v, f"{where}.labels.{a}") for a, v in labels_raw.items()}
        gold = Labels.parse(entry["gold"], f"{where}.gold") if "gold" in entry else None
        tags = entry.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise AnnotationError(f"{where}.tags: daftar string")
        items.append(Item(entry["id"], tuple(tags), labels, gold))
    return items


def gold_labels(items: Iterable[Item]) -> dict[str, Labels]:
    """Putusan akhir bila ada; bila tidak, label penilai tunggal; banyak penilai harus ber-gold."""
    gold = {}
    for item in items:
        if item.gold is not None:
            gold[item.id] = item.gold
        elif len(item.labels) == 1:
            gold[item.id] = next(iter(item.labels.values()))
        else:
            raise AnnotationError(
                f"item {item.id!r}: banyak penilai tetapi tanpa 'gold' (adjudikasi diperlukan)"
            )
    return gold


# --- kesepakatan antar-penilai --------------------------------------------------------------


def cohen_kappa(a: Sequence[Any], b: Sequence[Any]) -> float | None:
    """Kappa Cohen; None bila tak terdefinisi (tanpa data, atau kesepakatan kebetulan = 1)."""
    if len(a) != len(b):
        raise ValueError("panjang tidak sama")
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if expected >= 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def inter_annotator_agreement(items: Sequence[Item], annotator_a: str, annotator_b: str) -> dict:
    both = [i for i in items if annotator_a in i.labels and annotator_b in i.labels]
    out: dict[str, Any] = {"annotators": [annotator_a, annotator_b], "items": len(both)}
    for dim in SINGLE_DIMENSIONS:
        xs = [getattr(i.labels[annotator_a], dim) for i in both]
        ys = [getattr(i.labels[annotator_b], dim) for i in both]
        out[dim] = {
            "observed_agreement": _ratio(
                sum(x == y for x, y in zip(xs, ys, strict=True)), len(both)
            ),
            "kappa": cohen_kappa(xs, ys),
        }
    per_code = {}
    for code in CHARACTER_CODES:
        xs = [code in i.labels[annotator_a].response_character for i in both]
        ys = [code in i.labels[annotator_b].response_character for i in both]
        if any(xs) or any(ys):
            per_code[code] = {"kappa": cohen_kappa(xs, ys), "present_in": sum(xs) + sum(ys)}
    out["response_character"] = {
        "exact_set_agreement": _ratio(
            sum(
                i.labels[annotator_a].response_character == i.labels[annotator_b].response_character
                for i in both
            ),
            len(both),
        ),
        "per_code": per_code,
    }
    return out


# --- evaluasi prediksi ------------------------------------------------------------------------


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else (2 * precision * recall / (precision + recall))
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": tp + fn,
        "predicted": tp + fp,
    }


@dataclass
class Report:
    items: int
    missing_predictions: list[str]
    dimensions: dict[str, Any]
    response_character: dict[str, Any]
    by_tag: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    notice: str = PILOT_NOTICE
    pilot_size_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "notice": self.notice,
            "pilot_size_warning": self.pilot_size_warning,
            "items": self.items,
            "missing_predictions": self.missing_predictions,
            "dimensions": self.dimensions,
            "response_character": self.response_character,
            "by_tag": self.by_tag,
            "errors": self.errors,
        }


def evaluate(
    gold: Mapping[str, Labels],
    predicted: Mapping[str, Labels],
    tags: Mapping[str, Sequence[str]] | None = None,
) -> Report:
    tags = tags or {}
    ids = sorted(gold)
    missing = [i for i in ids if i not in predicted]
    scored = [i for i in ids if i in predicted]
    dims: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for dim, classes in SINGLE_DIMENSIONS.items():
        confusion: dict[str, Counter] = defaultdict(Counter)  # hanya dibaca lewat .get
        for i in scored:
            confusion[getattr(gold[i], dim)][getattr(predicted[i], dim)] += 1
            if getattr(gold[i], dim) != getattr(predicted[i], dim):
                errors.append(
                    {
                        "id": i,
                        "dimension": dim,
                        "gold": getattr(gold[i], dim),
                        "predicted": getattr(predicted[i], dim),
                        "tags": list(tags.get(i, [])),
                    }
                )
        per_class = {}
        for c in classes:
            row = confusion.get(c, Counter())
            tp = row[c]
            fn = sum(row.values()) - tp
            fp = sum(r[c] for g, r in confusion.items() if g != c)
            if tp + fn + fp:
                per_class[c] = _prf(tp, fp, fn)
        supported = [v["f1"] for v in per_class.values() if v["support"] and v["f1"] is not None]
        dims[dim] = {
            "accuracy": _ratio(sum(confusion.get(c, Counter())[c] for c in classes), len(scored)),
            "macro_f1": (sum(supported) / len(supported)) if supported else None,
            "per_class": per_class,
            "confusion": {g: dict(sorted(p.items())) for g, p in sorted(confusion.items())},
        }
    per_code, tp_all, fp_all, fn_all = {}, 0, 0, 0
    for code in CHARACTER_CODES:
        tp = sum(
            code in gold[i].response_character and code in predicted[i].response_character
            for i in scored
        )
        fp = sum(
            code not in gold[i].response_character and code in predicted[i].response_character
            for i in scored
        )
        fn = sum(
            code in gold[i].response_character and code not in predicted[i].response_character
            for i in scored
        )
        if tp + fp + fn:
            per_code[code] = _prf(tp, fp, fn)
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
    exact = sum(gold[i].response_character == predicted[i].response_character for i in scored)
    for i in scored:
        if gold[i].response_character != predicted[i].response_character:
            errors.append(
                {
                    "id": i,
                    "dimension": "response_character",
                    "gold": list(gold[i].response_character),
                    "predicted": list(predicted[i].response_character),
                    "tags": list(tags.get(i, [])),
                }
            )
    supported_f1 = [v["f1"] for v in per_code.values() if v["support"] and v["f1"] is not None]
    character = {
        "exact_set_match": _ratio(exact, len(scored)),
        "micro": _prf(tp_all, fp_all, fn_all),
        "macro_f1": (sum(supported_f1) / len(supported_f1)) if supported_f1 else None,
        "per_code": per_code,
    }
    by_tag: dict[str, Any] = {}
    for tag in sorted({t for i in scored for t in tags.get(i, [])}):
        members = [i for i in scored if tag in tags.get(i, [])]
        by_tag[tag] = {
            "items": len(members),
            "issue_stance_accuracy": _ratio(
                sum(gold[i].issue_stance == predicted[i].issue_stance for i in members),
                len(members),
            ),
            "target_alignment_accuracy": _ratio(
                sum(gold[i].target_alignment == predicted[i].target_alignment for i in members),
                len(members),
            ),
            "character_exact_match": _ratio(
                sum(gold[i].response_character == predicted[i].response_character for i in members),
                len(members),
            ),
        }
    warning = None
    if len(gold) < MIN_PILOT_ITEMS:
        warning = (
            f"hanya {len(gold)} respons teranotasi; pilot PRD menyarankan {MIN_PILOT_ITEMS}-100"
        )
    return Report(
        len(scored),
        missing,
        dims,
        character,
        by_tag,
        errors[:MAX_ERRORS_LISTED],
        pilot_size_warning=warning,
    )


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def format_report(report: Report) -> str:
    lines = [report.notice, ""]
    if report.pilot_size_warning:
        lines += [f"PERINGATAN: {report.pilot_size_warning}", ""]
    lines.append(
        f"Respons dinilai: {report.items}; tanpa prediksi: {len(report.missing_predictions)}"
    )
    for dim, data in report.dimensions.items():
        lines += ["", f"{dim}: akurasi {_pct(data['accuracy'])}, macro-F1 {_pct(data['macro_f1'])}"]
        for cls, v in data["per_class"].items():
            lines.append(
                f"  {cls:<13} P {_pct(v['precision']):>6}  R {_pct(v['recall']):>6}  "
                f"F1 {_pct(v['f1']):>6}  (gold {v['support']}, prediksi {v['predicted']})"
            )
    c = report.response_character
    lines += [
        "",
        f"response_character: kecocokan himpunan {_pct(c['exact_set_match'])}, "
        f"micro-F1 {_pct(c['micro']['f1'])}, macro-F1 {_pct(c['macro_f1'])}",
    ]
    for code, v in c["per_code"].items():
        lines.append(
            f"  {code}  P {_pct(v['precision']):>6}  R {_pct(v['recall']):>6}  "
            f"F1 {_pct(v['f1']):>6}  (gold {v['support']}, prediksi {v['predicted']})"
        )
    if report.by_tag:
        lines += ["", "Analisis galat per tag (akurasi stance / alignment / karakter):"]
        for tag, v in report.by_tag.items():
            lines.append(
                f"  {tag:<22} n={v['items']:<4} {_pct(v['issue_stance_accuracy']):>6} / "
                f"{_pct(v['target_alignment_accuracy']):>6} / {_pct(v['character_exact_match']):>6}"
            )
    lines += [
        "",
        f"Galat tercatat: {len(report.errors)} (maks {MAX_ERRORS_LISTED} ditampilkan di JSON)",
    ]
    return "\n".join(lines)


def load_predictions(raw: Any) -> dict[str, Labels]:
    if not isinstance(raw, dict):
        raise AnnotationError("prediksi: objek {id: label}")
    return {k: Labels.parse(v, f"prediksi.{k}") for k, v in raw.items()}


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluasi klasifikasi M2 (pilot).")
    parser.add_argument("--gold", type=Path, help="berkas anotasi (schema_version 1)")
    parser.add_argument("--pred", type=Path, help="berkas prediksi {id: label}")
    parser.add_argument("--agreement", nargs=2, metavar=("PENILAI_A", "PENILAI_B"))
    parser.add_argument(
        "--synthetic", action="store_true", help="evaluasi baseline atas data sintetis"
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.synthetic:
        from .m2.synthetic_eval import evaluate_synthetic

        report = evaluate_synthetic(args.seed)
    else:
        if not args.gold:
            parser.error("--gold wajib (atau --synthetic)")
        items = load_annotations(json.loads(args.gold.read_text(encoding="utf-8")))
        if args.agreement:
            print(json.dumps(inter_annotator_agreement(items, *args.agreement), indent=2))
            return 0
        if not args.pred:
            parser.error("--pred wajib untuk evaluasi")
        report = evaluate(
            gold_labels(items),
            load_predictions(json.loads(args.pred.read_text(encoding="utf-8"))),
            {i.id: i.tags for i in items},
        )
    print(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        if args.json
        else format_report(report)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
