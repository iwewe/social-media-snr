"""WP-1.8: adapter browser pada halaman simulasi. Tiap skenario punya status sendiri (AT-14)."""

import os
import stat

import pytest
from collection.browser import prepare_profile_dir, simulated_adapter_class
from collection.contracts import (
    Capability,
    CollectionStatus,
    InspectionOutcome,
    InspectionRequest,
    LimitationCode,
)
from collection.simulation.server import SESSION_COOKIE_VALUE
from investigations.enums import Platform, TargetType

O = InspectionOutcome  # noqa: E741
POST_URL = "https://x.com/contoh_redaksi/status/5000"
REPLIES = (Capability.INSPECT_POST, Capability.INSPECT_REPLIES)
EVIDENCE = (*REPLIES, Capability.PRESERVE_SCREENSHOT, Capability.PRESERVE_DOM)


def adapter(sim, scenario="complete", **kw):
    cls = simulated_adapter_class(Platform.X)
    return cls(f"{sim.base_url}/s/{scenario}", **kw)


def inspect(sim, scenario="complete", caps=REPLIES, max_items=None, **kw):
    a = adapter(sim, scenario, **kw)
    req = InspectionRequest("run-b1", Platform.X, POST_URL, TargetType.POST, tuple(caps),
                            max_items=max_items)
    return a.inspect(req)


def ids(result):
    return [o.external_post_id for o in result.observations]


# --- jalur sukses -----------------------------------------------------------------------------


def test_complete_conversation_is_read_in_full_with_hierarchy(sim_server) -> None:
    r = inspect(sim_server)
    assert r.outcome is O.COMPLETED and r.coverage.pagination_complete is True
    assert r.coverage.platform_displayed_count == 7 and r.observed_reply_count == 7
    assert ids(r)[0] == "5000" and len(ids(r)) == 8 and len(set(ids(r))) == 8
    by_id = {o.external_post_id: o for o in r.observations}
    assert by_id["5000003"].parent_post_id == "5000002"  # balasan bertingkat
    assert by_id["5000001"].parent_post_id == "5000"
    assert {o.collection_status for o in r.observations} == {CollectionStatus.COMPLETED}
    assert {o.source_method.value for o in r.observations} == {"synthetic_fixture"}


def test_empty_post_is_a_complete_zero_reply_result_that_says_so(sim_server) -> None:
    r = inspect(sim_server, "empty_post")
    assert r.outcome is O.COMPLETED and r.coverage.platform_displayed_count == 0
    assert ids(r) == ["5000"]


def test_pagination_clicks_through_every_page(sim_server) -> None:
    # 7 balasan, 3 per halaman: dua klik "muat lebih banyak".
    r = inspect(sim_server)
    assert r.observed_reply_count == 7


def test_only_the_post_when_replies_are_not_requested(sim_server) -> None:
    r = inspect(sim_server, caps=(Capability.INSPECT_POST,))
    assert ids(r) == ["5000"] and r.outcome is O.COMPLETED
    assert r.coverage.platform_displayed_count is None


def test_actor_handle_is_information_and_identity_is_the_actor_id(sim_server) -> None:
    r = inspect(sim_server)
    obs = {o.external_post_id: o for o in r.observations}
    assert obs["5000001"].external_actor_id == "u1" and obs["5000001"].actor_handle == "akun_u1"


def test_identity_missing_needs_verification_instead_of_guessing(sim_server) -> None:
    r = inspect(sim_server, "identity_missing")
    missing = [o for o in r.observations if o.external_actor_id is None]
    assert [o.external_post_id for o in missing] == ["5000002"]
    assert missing[0].identity_needs_verification


def test_collector_version_records_playwright_and_browser(sim_server) -> None:
    r = inspect(sim_server)
    assert r.collector.name == "browser-sim"
    assert "playwright" in r.collector.version and "chromium" in r.collector.version
    assert "unknown" not in r.collector.version


# --- kegagalan: tiap kasus punya status sendiri -----------------------------------------------


@pytest.mark.parametrize(
    ("scenario", "outcome", "code"),
    [
        ("forbidden", O.ACCESS_RESTRICTED, LimitationCode.ACCESS_RESTRICTED),
        ("challenge", O.ACCESS_RESTRICTED, LimitationCode.ACCESS_RESTRICTED),
        ("not_found", O.FAILED, LimitationCode.TARGET_UNAVAILABLE),
        ("server_error", O.FAILED, LimitationCode.NETWORK_ERROR),
        ("parse_failure", O.FAILED, LimitationCode.PARSE_FAILED),
    ],
)
def test_failure_pages_are_never_zero_replies(sim_server, scenario, outcome, code) -> None:  # AT-14
    r = inspect(sim_server, scenario)
    assert r.outcome is outcome and not r.observations
    assert [lim.code for lim in r.limitations] == [code]
    assert r.coverage.pagination_complete is None


def test_challenge_is_reported_and_not_bypassed(sim_server) -> None:
    r = inspect(sim_server, "challenge")
    assert "tidak dilewati" in r.limitations[0].message


def test_slow_page_beyond_the_timeout_is_a_timeout_failure(sim_server) -> None:
    r = inspect(sim_server, "slow", timeout_ms=500)
    assert r.outcome is O.FAILED and r.limitations[0].code is LimitationCode.TIMEOUT


def test_slow_page_within_the_timeout_still_completes(sim_server) -> None:
    assert inspect(sim_server, "slow", timeout_ms=15_000).outcome is O.COMPLETED


def test_unreachable_host_is_a_network_failure(sim_server) -> None:
    from collection.simulation import SimulationServer

    with SimulationServer() as gone:
        pass
    a = simulated_adapter_class(Platform.X)(gone.base_url)
    r = a.inspect(InspectionRequest("run-b1", Platform.X, POST_URL, TargetType.POST, REPLIES))
    assert r.outcome is O.FAILED and r.limitations[0].code is LimitationCode.NETWORK_ERROR


# --- parsial ----------------------------------------------------------------------------------


def test_broken_pagination_is_partial_with_what_was_read(sim_server) -> None:  # FR-026
    r = inspect(sim_server, "partial")
    assert r.outcome is O.PARTIAL and r.observed_reply_count == 3
    assert r.coverage.platform_displayed_count == 7 and r.coverage.pagination_complete is False
    assert [lim.code for lim in r.limitations] == [LimitationCode.PAGINATION_INCOMPLETE]
    assert {o.collection_status for o in r.observations} == {CollectionStatus.PARTIAL}


def test_login_wall_is_partial_auth_required_and_not_bypassed(sim_server) -> None:
    r = inspect(sim_server, "login_wall")
    assert r.outcome is O.PARTIAL and r.observed_reply_count == 3
    assert [lim.code for lim in r.limitations] == [LimitationCode.AUTH_REQUIRED]


def test_max_items_truncates_and_reports(sim_server) -> None:
    r = inspect(sim_server, max_items=4)
    assert r.outcome is O.PARTIAL and r.observed_reply_count == 4
    assert LimitationCode.MAX_ITEMS_REACHED in {lim.code for lim in r.limitations}


def test_page_limit_guard_stops_endless_pagination(sim_server) -> None:
    r = inspect(sim_server, max_pages=1)
    assert r.outcome is O.PARTIAL and r.observed_reply_count == 6
    assert LimitationCode.MAX_ITEMS_REACHED in {lim.code for lim in r.limitations}


# --- konten berubah antar kunjungan -----------------------------------------------------------


def test_content_changes_between_visits(sim_server) -> None:
    first, second, third = (inspect(sim_server, "changing") for _ in range(3))
    assert len(first.observations) == 4 and len(second.observations) == 6
    texts = {o.external_post_id: o.text for o in second.observations}
    assert "diedit" in texts["5000001"]
    assert "5000002" not in ids(third) and "5000002" in ids(second)


# --- isolasi origin, artefak, profil ----------------------------------------------------------


def test_requests_to_other_origins_are_blocked_and_counted(sim_server) -> None:
    r = inspect(sim_server, "external")
    assert r.outcome is O.COMPLETED
    assert "1 permintaan ke origin lain diblokir" in r.coverage.notes
    assert "tracker.invalid" not in " ".join(r.coverage.notes)  # tanpa URL/host lengkap


def test_screenshot_and_dom_artifacts_are_captured(sim_server) -> None:
    r = inspect(sim_server, caps=EVIDENCE)
    kinds = {a.kind.value: a for a in r.artifacts}
    assert kinds["screenshot"].content.startswith(b"\x89PNG\r\n\x1a\n")
    dom = kinds["dom_snapshot"].content.decode()
    assert 'id="focal"' in dom and "Balasan sintetis 7" in dom


def test_artifacts_are_only_captured_when_requested(sim_server) -> None:
    assert inspect(sim_server).artifacts == ()


def test_failure_pages_keep_their_evidence_when_requested(sim_server) -> None:
    r = inspect(sim_server, "forbidden", caps=EVIDENCE)
    kinds = {a.kind.value for a in r.artifacts}
    assert kinds == {"screenshot", "dom_snapshot"}
    dom = next(a for a in r.artifacts if a.kind.value == "dom_snapshot").content.decode()
    assert "Akses ditolak" in dom


def test_session_cookie_never_reaches_results_or_artifacts(sim_server) -> None:
    r = inspect(sim_server, caps=EVIDENCE)
    blob = repr(r) + "".join(a.content.decode("latin-1") for a in r.artifacts)
    assert SESSION_COOKIE_VALUE not in blob


def test_disabled_capability_is_gated_without_launching_a_browser(sim_server) -> None:
    r = inspect(sim_server, disable={Capability.INSPECT_REPLIES})
    assert r.outcome is O.UNSUPPORTED and not r.observations


def test_screenshot_is_declared_supported_and_media_not() -> None:
    caps = simulated_adapter_class(Platform.X)("http://x").capabilities()
    assert caps.runnable(Capability.PRESERVE_SCREENSHOT) and not caps.runnable(Capability.PRESERVE_MEDIA)


def test_adapter_declares_the_browser_queue() -> None:
    assert simulated_adapter_class(Platform.X).execution_queue == "browser"


# --- profil -----------------------------------------------------------------------------------


def test_profile_directory_is_private_and_reused(sim_server, settings, tmp_path) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    r = inspect(sim_server, profile_name="x")
    assert r.outcome is O.COMPLETED
    profile = tmp_path / "profiles" / "x"
    assert stat.S_IMODE(os.stat(profile).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(tmp_path / "profiles").st_mode) == 0o700
    assert any(profile.iterdir())  # Chromium memakai profil itu
    assert inspect(sim_server, profile_name="x").outcome is O.COMPLETED  # dipakai ulang


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a\\b", "x\x00"])
def test_profile_names_must_be_a_simple_component(name, settings, tmp_path) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    with pytest.raises(ValueError):
        prepare_profile_dir(name)


def test_profile_symlink_is_refused(settings, tmp_path) -> None:
    settings.SNR_BROWSER_PROFILES_ROOT = tmp_path / "profiles"
    (tmp_path / "profiles").mkdir(mode=0o700)
    outside = tmp_path / "luar"
    outside.mkdir()
    (tmp_path / "profiles" / "x").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        prepare_profile_dir("x")
