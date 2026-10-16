"""Pemeriksa arsitektur SNR (WP-0.6). Statis, memakai AST; tidak mengimpor kode yang diperiksa.

Aturan berasal dari PRD:
- Observasi dipisahkan dari interpretasi (bagian 3.3): collection dan preservation tidak boleh
  bergantung pada intelligence.
- Analisis ulang tidak mengambil data (FR-041): intelligence tidak boleh memakai browser/adapter.
- Browser hanya di adapter (FR-022, FR-025).
- Adapter per platform terpisah (FR-024).
- Tidak ada skor atau vonis buzzer/bot/koordinasi otomatis (bagian 1, FR-075, FR-079).
- Akar evidence dan sesi browser hanya disentuh lewat preservation.storage (FR-039, bagian 10).
"""

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_DIRS = {
    ".venv",
    "__pycache__",
    "staticfiles",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
PLATFORMS = ("x", "threads", "tiktok", "instagram", "facebook")


@dataclass(frozen=True)
class Violation:
    rule: str
    module: str
    line: int
    detail: str


@dataclass(frozen=True)
class ImportRule:
    """Berkas di bawah `sources` tidak boleh mengimpor apa pun di bawah `forbidden`."""

    name: str
    sources: tuple[str, ...]
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class ConfinedImportRule:
    """`module` hanya boleh diimpor oleh berkas di bawah `allowed_in`."""

    name: str
    module: str
    allowed_in: tuple[str, ...]


def default_import_rules() -> list[ImportRule]:
    rules = [
        ImportRule(
            "collection tidak bergantung pada intelligence (observasi vs interpretasi)",
            ("collection",),
            ("intelligence",),
        ),
        ImportRule(
            "preservation tidak bergantung pada intelligence",
            ("preservation",),
            ("intelligence",),
        ),
        ImportRule(
            "kontrak observasi tidak bergantung pada implementasinya (adapter, orchestrator, "
            "rekonsiliasi, analisis, preservasi)",
            ("collection.contracts",),
            (
                "collection.adapters",
                "collection.orchestrator",
                "collection.reconciliation",
                "intelligence",
                "preservation",
            ),
        ),
        ImportRule(
            "intelligence tidak mengambil data (FR-041)",
            ("intelligence",),
            ("playwright", "collection.adapters", "collection.orchestrator"),
        ),
    ]
    for p in PLATFORMS:
        rules.append(
            ImportRule(
                f"adapter {p} tidak mengimpor adapter platform lain (FR-024)",
                (f"collection.adapters.{p}",),
                tuple(f"collection.adapters.{q}" for q in PLATFORMS if q != p),
            )
        )
    return rules


def default_confined_rules() -> list[ConfinedImportRule]:
    return [
        ConfinedImportRule(
            "Playwright hanya di adapter koleksi", "playwright", ("collection.adapters",)
        )
    ]


# --- penelusuran berkas dan impor -----------------------------------------------------------


def python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        if not EXCLUDED_DIRS & set(path.relative_to(root).parts):
            yield path


def module_parts(root: Path, path: Path) -> list[str]:
    parts = list(path.relative_to(root).with_suffix("").parts)
    return parts[:-1] if parts and parts[-1] == "__init__" else parts


def module_name(root: Path, path: Path) -> str:
    return ".".join(module_parts(root, path))


def _package_parts(root: Path, path: Path) -> list[str]:
    parts = module_parts(root, path)
    return parts if path.name == "__init__.py" else parts[:-1]


def imported_modules(root: Path, path: Path) -> list[tuple[str, int]]:
    """Semua modul yang diimpor (absolut), termasuk kandidat `from X import Y` sebagai `X.Y`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                package = _package_parts(root, path)
                keep = len(package) - (node.level - 1)
                if keep < 0:
                    continue
                base = ".".join(package[:keep] + ([node.module] if node.module else []))
            if base:
                found.append((base, node.lineno))
                found.extend((f"{base}.{alias.name}", node.lineno) for alias in node.names)
    return found


def matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def check_imports(
    root: Path,
    import_rules: list[ImportRule] | None = None,
    confined_rules: list[ConfinedImportRule] | None = None,
) -> list[Violation]:
    import_rules = default_import_rules() if import_rules is None else import_rules
    confined_rules = default_confined_rules() if confined_rules is None else confined_rules
    violations: list[Violation] = []
    for path in python_files(root):
        mod = module_name(root, path)
        imports = imported_modules(root, path)
        for rule in import_rules:
            if not any(matches(mod, s) for s in rule.sources):
                continue
            for imported, line in imports:
                if any(matches(imported, f) for f in rule.forbidden):
                    violations.append(Violation(rule.name, mod, line, f"mengimpor {imported}"))
        for crule in confined_rules:
            if any(matches(mod, a) for a in crule.allowed_in):
                continue
            for imported, line in imports:
                if matches(imported, crule.module):
                    violations.append(Violation(crule.name, mod, line, f"mengimpor {imported}"))
    return violations


# --- identifier terlarang -------------------------------------------------------------------

# Urutan kata (hasil pemecahan snake_case/camelCase) yang dilarang. Alasan: PRD bagian 1 dan
# FR-079 melarang skor/vonis otomatis "buzzer", "bot", akun bayaran, atau koordinasi.
FORBIDDEN_WORDS: tuple[tuple[str, ...], ...] = (
    ("buzzer",),
    ("botscore",),
    ("bot", "score"),
    ("bot", "probability"),
    ("is", "bot"),
    ("paid", "account"),
    ("coordination", "score"),
    ("coordination", "verdict"),
)
_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
_IDENTIFIER_LIKE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def words(identifier: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(identifier)]


def forbidden_in(identifier: str) -> tuple[str, ...] | None:
    """Urutan kata terlarang yang termuat dalam identifier, atau None."""
    ws = words(identifier)
    for seq in FORBIDDEN_WORDS:
        if len(seq) == 1:
            if any(w.startswith(seq[0]) for w in ws):
                return seq
        elif any(tuple(ws[i : i + len(seq)]) == seq for i in range(len(ws) - len(seq) + 1)):
            return seq
    return None


def python_identifiers(path: Path) -> Iterator[tuple[str, int]]:
    """Identifier pada kode: nama, atribut, definisi, argumen, serta string bergaya identifier
    (nama field, kunci dict). Teks bebas (docstring, kalimat) tidak ikut."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Name):
            yield node.id, line
        elif isinstance(node, ast.Attribute):
            yield node.attr, line
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield node.name, line
        elif isinstance(node, ast.arg):
            yield node.arg, line
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.arg, line
        elif isinstance(node, ast.alias):
            yield from ((part, line) for part in (node.asname or node.name).split("."))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            yield node.name, line
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _IDENTIFIER_LIKE.fullmatch(node.value)
        ):
            yield node.value, line


def find_forbidden_identifiers(root: Path) -> list[Violation]:
    violations = []
    for path in python_files(root):
        for name, line in python_identifiers(path):
            seq = forbidden_in(name)
            if seq:
                violations.append(
                    Violation(
                        "tidak ada skor/vonis buzzer, bot, atau koordinasi otomatis",
                        module_name(root, path),
                        line,
                        f"identifier '{name}' memuat {'_'.join(seq)}",
                    )
                )
    return violations


def find_identifier_usage(root: Path, name: str) -> list[tuple[str, int]]:
    """Modul dan baris yang memakai identifier persis `name`."""
    return [
        (module_name(root, path), line)
        for path in python_files(root)
        for ident, line in python_identifiers(path)
        if ident == name
    ]
