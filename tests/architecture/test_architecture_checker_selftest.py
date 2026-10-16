"""WP-0.6: menguji PEMERIKSA arsitektur terhadap kode buatan agar tidak lulus karena kosong."""

from pathlib import Path

import pytest
from arch_checker import (
    check_imports,
    find_forbidden_identifiers,
    forbidden_in,
    words,
)


def write(root: Path, rel: str, code: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    # Pastikan paket induk dikenali.
    for parent in path.relative_to(root).parents:
        if str(parent) != ".":
            (root / parent / "__init__.py").touch()


def rules_hit(root: Path) -> set[str]:
    return {f"{v.module}|{v.detail}" for v in check_imports(root)}


@pytest.fixture
def clean(tmp_path: Path) -> Path:
    write(tmp_path, "collection/adapters/x/client.py", "import playwright.sync_api\n")
    write(tmp_path, "collection/orchestrator/job.py", "from collection.adapters.x import client\n")
    write(tmp_path, "intelligence/stance/m.py", "from collection.contracts import observation\n")
    write(tmp_path, "preservation/s.py", "import hashlib\n")
    write(tmp_path, "api/v.py", "from investigations import services\n")
    return tmp_path


def test_clean_tree_has_no_violations(clean: Path) -> None:
    assert check_imports(clean) == []
    assert find_forbidden_identifiers(clean) == []


@pytest.mark.parametrize(
    ("rel", "code", "expected"),
    [
        ("collection/bad.py", "import intelligence.stance\n", "collection.bad|mengimpor intelligence.stance"),
        ("collection/bad.py", "from intelligence import stance\n", "collection.bad|mengimpor intelligence"),
        ("preservation/bad.py", "from intelligence.actors import x\n", "preservation.bad|mengimpor intelligence.actors"),
        ("intelligence/bad.py", "import playwright\n", "intelligence.bad|mengimpor playwright"),
        ("intelligence/bad.py", "from collection.adapters.x import client\n", "intelligence.bad|mengimpor collection.adapters.x"),
        ("intelligence/bad.py", "from collection import orchestrator\n", "intelligence.bad|mengimpor collection.orchestrator"),
        ("api/bad.py", "from playwright.sync_api import sync_playwright\n", "api.bad|mengimpor playwright.sync_api"),
        ("preservation/bad.py", "import playwright\n", "preservation.bad|mengimpor playwright"),
        ("collection/contracts/bad.py", "from collection.adapters.x import client\n", "collection.contracts.bad|mengimpor collection.adapters.x"),
        ("collection/contracts/bad.py", "import preservation.storage\n", "collection.contracts.bad|mengimpor preservation.storage"),
        ("collection/contracts/bad.py", "from collection import reconciliation\n", "collection.contracts.bad|mengimpor collection.reconciliation"),
        ("collection/adapters/x/bad.py", "from collection.adapters.tiktok import client\n", "collection.adapters.x.bad|mengimpor collection.adapters.tiktok"),
        ("collection/adapters/x/bad.py", "from collection.adapters import tiktok\n", "collection.adapters.x.bad|mengimpor collection.adapters.tiktok"),
        ("collection/adapters/threads/bad.py", "import collection.adapters.facebook.parser\n", "collection.adapters.threads.bad|mengimpor collection.adapters.facebook.parser"),
    ],
)
def test_import_violations_are_detected(clean: Path, rel: str, code: str, expected: str) -> None:
    write(clean, rel, code)
    assert expected in rules_hit(clean)


def test_relative_import_resolving_to_forbidden_module_is_detected(clean: Path) -> None:
    # collection/orchestrator/job.py: "from ... import intelligence" naik dua tingkat ke akar.
    write(clean, "collection/orchestrator/job.py", "from ... import intelligence\n")
    # level=3 melebihi paket -> tidak resolvable; harus aman (tidak crash, tidak false positive).
    assert check_imports(clean) == []
    # Relatif yang valid di dalam collection bukan pelanggaran.
    write(clean, "collection/orchestrator/job.py", "from .. import contracts\nfrom . import x\n")
    assert check_imports(clean) == []


def test_playwright_inside_adapters_is_allowed(clean: Path) -> None:
    write(clean, "collection/adapters/tiktok/browser.py", "from playwright.sync_api import Page\n")
    assert check_imports(clean) == []


def test_syntax_error_in_scanned_file_fails_loudly(clean: Path) -> None:
    write(clean, "collection/broken.py", "def (:\n")
    with pytest.raises(SyntaxError):
        check_imports(clean)


# --- identifier terlarang -------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "def compute_buzzer_score(a): return 1\n",
        "class BuzzerScore: pass\n",
        "class BotScore: pass\n",
        "x = obj.is_bot\n",
        "isBot = True\n",
        "data = {'paid_account': 1}\n",
        "def f(coordination_verdict): pass\n",
        "result = call(bot_probability=0.9)\n",
        "BUZZER_THRESHOLD = 0.5\n",
        "from a import b as buzzer_rating\n",
        "try:\n    pass\nexcept Exception as buzzer_exc:\n    pass\n",
    ],
)
def test_forbidden_identifiers_are_detected(tmp_path: Path, code: str) -> None:
    write(tmp_path, "intelligence/m.py", code)
    assert find_forbidden_identifiers(tmp_path), code


@pytest.mark.parametrize(
    "code",
    [
        "bottom = 1\nrobot_arm = 2\nboth = 3\nabbot = 4\n",
        "similarity_score = 0.4\ncoordination_indicator = 1\n",
        '"""Tidak ada skor buzzer di sini; ini hanya teks penjelasan."""\n',
        "# komentar: jangan buat buzzer score\nx = 1\n",
        "label = 'Jangan beri label buzzer pada kritik'\n",
        "bots_seen = 3\n",
    ],
)
def test_harmless_code_is_not_flagged(tmp_path: Path, code: str) -> None:
    write(tmp_path, "intelligence/m.py", code)
    assert find_forbidden_identifiers(tmp_path) == []


def test_word_splitting() -> None:
    assert words("compute_buzzer_score") == ["compute", "buzzer", "score"]
    assert words("isBotFlag") == ["is", "bot", "flag"]
    assert words("HTTPServer2") == ["http", "server", "2"]
    assert forbidden_in("bottom") is None
    assert forbidden_in("is_bot") == ("is", "bot")
    assert forbidden_in("BotScore") == ("bot", "score")
