"""WP-0.6: invarian isolasi pada compose.yaml (PRD bagian 10 dan 13; ADR 0001/0002).

Membaca compose.yaml apa adanya, jadi perubahan yang melanggar isolasi langsung gagal di CI.
"""

import re
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "compose.yaml"
PROFILES_TARGET = "/srv/snr/browser-profiles"
EVIDENCE_TARGET = "/srv/snr/evidence"


@pytest.fixture(scope="module")
def services() -> dict:
    assert COMPOSE.is_file(), f"compose.yaml tidak ditemukan di {COMPOSE}"
    return yaml.safe_load(COMPOSE.read_text())["services"]


_VOLUME = re.compile(r"^(?P<src>.+):(?P<tgt>/[^:]*)(?::(?:ro|rw))?$")


def volumes(service: dict) -> list[tuple[str, str]]:
    """(sumber, tujuan) tiap volume. Sumber boleh memuat ':' (mis. ${VAR:-bawaan})."""
    result = []
    for v in service.get("volumes", []):
        match = _VOLUME.match(str(v))
        assert match, f"format volume tak dikenali: {v}"
        result.append((match["src"], match["tgt"]))
    return result


def test_volume_parser_handles_env_defaults_and_modes() -> None:
    assert volumes({"volumes": ["${A:-./d}/browser-profiles:/srv/snr/browser-profiles"]}) == [
        ("${A:-./d}/browser-profiles", "/srv/snr/browser-profiles")
    ]
    assert volumes({"volumes": ["./compose.yaml:/compose.yaml:ro"]}) == [
        ("./compose.yaml", "/compose.yaml")
    ]


def test_all_expected_services_exist(services: dict) -> None:
    assert {"postgres", "valkey", "web", "worker-analysis", "worker-browser", "frontend"} <= set(
        services
    )


def test_only_worker_browser_mounts_browser_profiles(services: dict) -> None:
    mounting = {
        name
        for name, svc in services.items()
        if any("browser-profiles" in src or PROFILES_TARGET in tgt for src, tgt in volumes(svc))
    }
    assert mounting == {"worker-browser"}, mounting
    # Anti-kosong: worker-browser memang memasang evidence dan profil sekaligus.
    targets = {tgt for _src, tgt in volumes(services["worker-browser"])}
    assert {EVIDENCE_TARGET, PROFILES_TARGET} <= targets


def test_browser_profiles_are_not_mounted_under_evidence_or_vice_versa(services: dict) -> None:
    for name, svc in services.items():
        for _src, tgt in volumes(svc):
            if tgt.startswith(EVIDENCE_TARGET + "/"):
                assert "browser-profiles" not in tgt, (name, tgt)
            if tgt.startswith(PROFILES_TARGET + "/") or tgt == PROFILES_TARGET:
                assert not tgt.startswith(EVIDENCE_TARGET), (name, tgt)


def test_evidence_and_profiles_come_from_different_host_directories(services: dict) -> None:
    sources = {}
    for svc in services.values():
        for src, tgt in volumes(svc):
            if tgt == EVIDENCE_TARGET:
                sources["evidence"] = src
            if tgt == PROFILES_TARGET:
                sources["profiles"] = src
    assert set(sources) == {"evidence", "profiles"}, sources
    assert sources["evidence"] != sources["profiles"]
    assert not sources["profiles"].startswith(sources["evidence"] + "/")
    assert not sources["evidence"].startswith(sources["profiles"] + "/")


def test_database_and_broker_are_not_published_to_the_host(services: dict) -> None:
    for name in ("postgres", "valkey", "worker-analysis", "worker-browser"):
        assert "ports" not in services[name], name


def test_published_ports_are_bound_to_loopback_only(services: dict) -> None:
    for name, svc in services.items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), (name, port)


def test_secrets_have_no_inline_defaults(services: dict) -> None:
    text = COMPOSE.read_text()
    assert "${DJANGO_SECRET_KEY:?" in text
    assert "${POSTGRES_PASSWORD:?" in text
