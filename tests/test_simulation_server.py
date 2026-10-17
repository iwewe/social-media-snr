"""WP-1.8: server simulasi itu sendiri (tanpa browser): kontrak halaman yang dijanjikan ke adapter."""

import json
import urllib.error
import urllib.request

import pytest
from collection.simulation import ID_SCENARIOS, SCENARIOS, SimulationServer


@pytest.fixture(scope="module")
def sim():
    with SimulationServer() as server:
        yield server


@pytest.fixture(autouse=True)
def _reset(sim):
    sim.reset()


def get(sim, path):
    try:
        with urllib.request.urlopen(sim.base_url + path, timeout=10) as r:  # noqa: S310 - loopback
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


def test_server_binds_to_loopback_by_default(sim) -> None:
    assert sim.base_url.startswith("http://127.0.0.1:")


@pytest.mark.parametrize(
    ("scenario", "status"),
    [("complete", 200), ("forbidden", 403), ("not_found", 404), ("server_error", 500),
     ("challenge", 200), ("parse_failure", 200), ("empty_post", 200)],
)
def test_scenario_status_codes(sim, scenario, status) -> None:
    assert get(sim, f"/s/{scenario}/u/status/77")[0] == status


def test_complete_page_has_the_structure_the_adapter_relies_on(sim) -> None:
    _, html, _ = get(sim, "/s/complete/u/status/77")
    for marker in ('id="focal"', 'id="replies"', 'id="load-more"', 'data-displayed-count="7"',
                   'data-post-id="77"', "data-parent-id="):
        assert marker in html
    assert html.count('class="reply"') == 3  # halaman pertama saja


def test_challenge_page_has_no_conversation_and_offers_no_bypass(sim) -> None:
    _, html, _ = get(sim, "/s/challenge/u/status/77")
    assert "data-snr-challenge" in html and 'id="focal"' not in html and "<form" not in html


def test_api_pages_cover_all_replies_exactly_once(sim) -> None:
    get(sim, "/s/complete/u/status/77")
    seen, page = [], 2
    while page:
        _, body, _ = get(sim, f"/api/replies?post=77&page={page}&s=complete")
        data = json.loads(body)
        seen += [p for p in data["html"].split('data-reply-id="')[1:]]
        page = data["next"]
    assert len(seen) == 4  # 7 balasan - 3 di halaman pertama


def test_partial_and_login_wall_fail_on_the_second_page(sim) -> None:
    assert get(sim, "/api/replies?post=77&page=2&s=partial")[0] == 500
    assert get(sim, "/api/replies?post=77&page=2&s=login_wall")[0] == 401
    assert get(sim, "/api/replies?post=77&page=1&s=partial")[0] == 200


def test_bad_page_parameter_is_a_client_error(sim) -> None:
    assert get(sim, "/api/replies?post=77&page=abc&s=complete")[0] == 400


def displayed(html: str) -> int:
    return int(html.split('data-displayed-count="')[1].split('"')[0])


def test_changing_scenario_differs_per_visit_and_reset_restarts_it(sim) -> None:
    counts = [displayed(get(sim, "/s/changing/u/status/77")[1]) for _ in range(3)]
    assert counts == [3, 5, 4]  # tumbuh, lalu satu balasan tidak tampil
    assert displayed(get(sim, "/s/changing/u/status/78")[1]) == 3  # kunjungan per pos
    urllib.request.urlopen(  # noqa: S310 - loopback
        urllib.request.Request(sim.base_url + "/__reset", method="POST"), timeout=5
    )
    assert displayed(get(sim, "/s/changing/u/status/77")[1]) == 3


def test_id_table_selects_the_scenario_without_prefix(sim) -> None:
    for post, scenario in ID_SCENARIOS.items():
        status = get(sim, f"/u/status/{post}")[0]
        assert status == {"forbidden": 403, "not_found": 404}.get(scenario, 200), (post, scenario)


def test_unknown_id_and_unknown_scenario_are_404(sim) -> None:
    assert get(sim, "/u/status/424242")[0] == 404
    assert get(sim, "/s/tidak-ada/u/status/1")[0] == 404
    assert get(sim, "/bukan/rute")[0] == 404


def test_every_scenario_name_is_servable(sim) -> None:
    for scenario in SCENARIOS:
        if scenario == "slow":
            continue
        assert get(sim, f"/s/{scenario}/u/status/5")[0] in (200, 403, 404, 500), scenario


def test_text_is_html_escaped(sim) -> None:
    from collection.simulation.server import _li

    li = _li({"id": "1", "author": "a", "handle": "h", "parent": "0", "published": "2026-10-15T08:01:00Z",
              "text": "<script>alert(1)</script>"})
    assert "<script>" not in li and "&lt;script&gt;" in li


def test_pages_are_not_cacheable(sim) -> None:
    assert get(sim, "/s/complete/u/status/1")[2]["Cache-Control"] == "no-store"
