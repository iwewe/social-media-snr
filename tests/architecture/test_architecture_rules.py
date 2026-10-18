"""WP-0.6: aturan arsitektur dijalankan terhadap kode backend yang sebenarnya."""

from pathlib import Path

import pytest
from arch_checker import (
    PLATFORMS,
    check_imports,
    default_import_rules,
    find_forbidden_identifiers,
    find_identifier_usage,
    module_name,
    python_files,
)
from django.apps import apps
from django.conf import settings

BACKEND = Path(settings.BASE_DIR)


def fmt(violations) -> str:
    return "\n".join(f"{v.module}:{v.line} [{v.rule}] {v.detail}" for v in violations)


@pytest.fixture(scope="module")
def modules() -> set[str]:
    return {module_name(BACKEND, p) for p in python_files(BACKEND)}


def test_scan_is_not_vacuous(modules: set[str]) -> None:
    # Pengaman: pemeriksa harus benar-benar melihat kode aplikasi.
    assert len(modules) >= 40
    for expected in (
        "preservation.storage",
        "collection.adapters.x",
        "collection.adapters.facebook",
        "intelligence.network",
        "investigations.services",
        "api.views",
    ):
        assert expected in modules, expected


def test_every_import_rule_matches_at_least_one_source_module(modules: set[str]) -> None:
    for rule in default_import_rules():
        assert any(
            m == s or m.startswith(s + ".") for m in modules for s in rule.sources
        ), f"aturan tak punya modul sumber (kosong): {rule.name}"


def test_import_rules_hold_for_the_real_codebase() -> None:
    violations = check_imports(BACKEND)
    assert not violations, "\n" + fmt(violations)


def test_no_buzzer_bot_or_coordination_score_identifiers_in_code() -> None:
    violations = find_forbidden_identifiers(BACKEND)
    assert not violations, "\n" + fmt(violations)


def test_no_forbidden_names_in_models_fields_or_tables() -> None:
    from arch_checker import forbidden_in

    offenders = []
    for model in apps.get_models():
        names = [model.__name__, model._meta.db_table]
        names += [f.name for f in model._meta.get_fields()]
        names += [getattr(f, "column", "") for f in model._meta.get_fields()]
        offenders += [(model.__name__, n) for n in names if n and forbidden_in(n)]
    assert not offenders, offenders
    assert len(list(apps.get_models())) >= 8  # tidak kosong


@pytest.mark.parametrize("setting", ["SNR_EVIDENCE_ROOT", "SNR_BROWSER_PROFILES_ROOT"])
def test_storage_roots_are_only_touched_by_the_storage_layer(setting: str) -> None:
    allowed = {"config.settings", "preservation.storage", "preservation.checks"}
    users = {mod for mod, _line in find_identifier_usage(BACKEND, setting)}
    assert users, f"{setting} tidak dipakai di mana pun (pemeriksa tak efektif?)"
    assert users <= allowed, f"{setting} disentuh di luar lapisan penyimpanan: {users - allowed}"


def test_platform_list_matches_the_adapter_packages(modules: set[str]) -> None:
    adapters = {m.split(".")[2] for m in modules if m.startswith("collection.adapters.")}
    # `pending` adalah dasar bersama adapter nonaktif (WP-3.0), bukan paket platform.
    assert adapters - {"pending"} == set(PLATFORMS)


def test_unchecked_policy_is_never_used_by_production_code() -> None:
    """UncheckedPolicy menerima semua artefak (termasuk rahasia); hanya modul kebijakan yang boleh
    mendefinisikannya. Kode produksi lain tidak boleh merujuknya (WP-1.5)."""
    users = {mod for mod, _line in find_identifier_usage(BACKEND, "UncheckedPolicy")}
    assert users, "UncheckedPolicy tidak ditemukan (pemeriksa tak efektif?)"
    assert users <= {"preservation.policy"}, users - {"preservation.policy"}
