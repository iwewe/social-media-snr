"""WP-1.1: suite kontrak dijalankan terhadap SETIAP adapter terdaftar."""

import pytest
from contract_suite import check_contract
from harnesses import HARNESSES


@pytest.mark.parametrize("factory", HARNESSES, ids=lambda f: f.__name__)
def test_adapter_satisfies_the_contract(factory) -> None:
    failures = check_contract(factory())
    assert not failures, "\n" + "\n".join(failures)


def test_at_least_one_adapter_is_registered() -> None:
    assert HARNESSES, "tidak ada adapter terdaftar: suite tidak menguji apa pun"
