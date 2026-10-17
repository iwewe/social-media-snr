"""WP-1.1: suite kontrak diuji sendiri. Adapter yang melanggar HARUS gagal pada aturan yang tepat."""

import pytest
from contract_suite import REQUIRED_SCENARIOS, check_contract
from fake_adapters import (
    BadAcceptsAnyUrl,
    BadForeignPlatformData,
    BadIncompleteCapabilities,
    BadNondeterministicIds,
    BadOverridesInspect,
    BadPublishedFromObserved,
    BadSwallowsAccessRestriction,
    BadSwallowsParseFailure,
    BadUnknownQueue,
    BadUsesNetworkInValidation,
    BadWrongPlatformInCapabilities,
    FakeXAdapter,
)
from harnesses import harness_for


def rules(adapter_class) -> set[str]:
    return {f.split(":")[0] for f in check_contract(harness_for(adapter_class))}


def test_conforming_adapter_has_no_violations() -> None:
    assert check_contract(harness_for(FakeXAdapter)) == []


@pytest.mark.parametrize(
    ("adapter_class", "expected_rule"),
    [
        (BadPublishedFromObserved, "C14"),  # published_at diisi waktu pengambilan
        (BadSwallowsParseFailure, "C12"),  # parser gagal -> 'nol komentar'
        (BadSwallowsAccessRestriction, "C11"),  # akses ditolak -> hasil kosong sukses
        (BadOverridesInspect, "C06"),  # gerbang kemampuan dilewati
        (BadForeignPlatformData, "C14"),  # data platform lain
        (BadAcceptsAnyUrl, "C03"),  # menerima URL platform lain
        (BadUsesNetworkInValidation, "C05"),  # jaringan pada metode murni
        (BadNondeterministicIds, "C13"),  # ID berubah antarpemanggilan
        (BadWrongPlatformInCapabilities, "C01"),
        (BadIncompleteCapabilities, "C01"),
        (BadUnknownQueue, "C16"),  # antrean tak dilayani: run akan menggantung PENDING
    ],
)
def test_violating_adapter_is_caught_by_the_expected_rule(adapter_class, expected_rule) -> None:
    assert expected_rule in rules(adapter_class), (
        f"{adapter_class.__name__} lolos tanpa terdeteksi aturan {expected_rule}"
    )


def test_bypassing_the_capability_gate_is_also_caught_behaviourally() -> None:
    # Selain pemeriksaan struktural (C06), perilakunya pun gagal pada C07.
    assert "C07" in rules(BadOverridesInspect)


@pytest.mark.parametrize(
    ("adapter_class", "exact_rules"),
    [
        (BadSwallowsParseFailure, {"C12"}),
        (BadSwallowsAccessRestriction, {"C11"}),
        (BadNondeterministicIds, {"C13"}),
        (BadUnknownQueue, {"C16"}),
        # Menerima semua URL melanggar tiga aturan validasi sekaligus (valid-tapi-salah-jenis,
        # platform lain, dan sampah).
        (BadAcceptsAnyUrl, {"C02", "C03", "C04"}),
    ],
)
def test_violation_triggers_exactly_the_related_rules(adapter_class, exact_rules) -> None:
    # Pemeriksa tidak boleh memicu aturan yang tidak terkait (tanpa efek silang).
    assert rules(adapter_class) == exact_rules


def test_incomplete_harness_is_reported() -> None:
    harness = harness_for(FakeXAdapter)
    harness.scenarios = frozenset(REQUIRED_SCENARIOS - {"partial"})
    assert any(f.startswith("C00") for f in check_contract(harness))
