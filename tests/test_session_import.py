"""Impor sesi operator: penguraian cookie, penyaringan domain, dan tidak bocornya nilai (PRD 13)."""

import json
from datetime import UTC, datetime

import pytest
from collection.browser.session_import import (
    SessionImportError,
    load_cookie_file,
    parse_cookies,
    summarize,
)

SECRET = "nilai-rahasia-cookie-1234567890"


def cookie(name="auth_token", domain=".x.com", **over):
    return {"name": name, "value": SECRET, "domain": domain, "path": "/", **over}


def test_storage_state_and_extension_export_shapes_are_both_accepted() -> None:
    a, _ = parse_cookies({"cookies": [cookie()], "origins": []}, "x")
    b, _ = parse_cookies([cookie()], "x")
    assert a == b and a[0]["name"] == "auth_token" and a[0]["domain"] == ".x.com"


def test_only_platform_domains_are_kept_and_foreign_ones_counted() -> None:
    kept, foreign = parse_cookies(
        [
            cookie("a", ".x.com"),
            cookie("b", "api.twitter.com"),
            cookie("c", ".facebook.com"),
            cookie("d", "evilx.com"),
            cookie("e", "x.com.evil.test"),
        ],
        "x",
    )
    assert [c["name"] for c in kept] == ["a", "b"] and foreign == 3


def test_nothing_is_imported_when_no_cookie_matches_the_platform() -> None:
    with pytest.raises(SessionImportError, match="tidak ada cookie untuk domain x"):
        parse_cookies([cookie(domain=".facebook.com")], "x")


@pytest.mark.parametrize("raw", [[], {}, {"cookies": []}, "teks", 5, None, {"cookies": "x"}])
def test_empty_or_wrongly_shaped_input_is_rejected(raw) -> None:
    with pytest.raises(SessionImportError):
        parse_cookies(raw, "x")


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "", "value": "v", "domain": ".x.com"},
        {"name": "n", "value": "", "domain": ".x.com"},
        {"name": "n", "value": 5, "domain": ".x.com"},
        {"name": "n", "value": "v"},
        {"name": "n", "value": "v", "domain": ""},
        "bukan objek",
    ],
)
def test_malformed_cookies_are_rejected(bad) -> None:
    with pytest.raises(SessionImportError):
        parse_cookies([bad], "x")


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(SessionImportError, match="platform"):
        parse_cookies([cookie()], "myspace")


def test_error_messages_never_contain_cookie_values() -> None:
    for raw in (
        [cookie(domain=".facebook.com")],
        [{**cookie(), "name": ""}],
        [{**cookie(), "domain": ""}],
    ):
        with pytest.raises(SessionImportError) as info:
            parse_cookies(raw, "x")
        assert SECRET not in str(info.value)
    with pytest.raises(SessionImportError) as info:
        load_cookie_file('{"cookies": [{"value": "' + SECRET + '"')  # secret-scan: allow
    assert SECRET not in str(info.value) and "baris" in str(info.value)


def test_field_normalisation_expiry_samesite_and_flags() -> None:
    kept, _ = parse_cookies(
        [
            cookie(
                "a",
                expirationDate=1_900_000_000.5,
                sameSite="no_restriction",
                httpOnly=True,
                secure=True,
            ),
            cookie("b", expires=-1, sameSite="lax"),
            cookie("c", expires=0, sameSite="unspecified"),
            cookie("d", expires=1_800_000_000, sameSite="Strict", http_only=True),
            {"name": "e", "value": "v", "domain": ".x.com"},
        ],
        "x",
    )
    a, b, c, d, e = kept
    assert (
        a["expires"] == 1_900_000_000.5
        and a["sameSite"] == "None"
        and a["httpOnly"]
        and a["secure"]
    )
    assert "expires" not in b and b["sameSite"] == "Lax"
    assert "expires" not in c and "sameSite" not in c
    assert d["expires"] == 1_800_000_000 and d["sameSite"] == "Strict" and d["httpOnly"]
    assert e["path"] == "/" and not e["secure"] and not e["httpOnly"] and "sameSite" not in e


def test_session_cookies_get_an_explicit_lifetime_only_when_asked() -> None:
    now = datetime(2026, 10, 19, tzinfo=UTC)
    raw = [cookie("sesi"), cookie("tetap", expires=1_900_000_000)]
    plain, _ = parse_cookies(raw, "x", now=now)
    assert "expires" not in plain[0]
    zero, _ = parse_cookies(raw, "x", session_days=0, now=now)
    assert "expires" not in zero[0]
    kept, _ = parse_cookies(raw, "x", session_days=7, now=now)
    assert kept[0]["expires"] == now.timestamp() + 7 * 86400
    assert kept[1]["expires"] == 1_900_000_000  # yang sudah berkedaluwarsa tidak diubah


def test_summary_has_names_counts_and_earliest_expiry_but_no_values() -> None:
    kept, foreign = parse_cookies(
        [cookie("b", expires=1_900_000_000), cookie("a", expires=1_800_000_000), cookie("s")], "x"
    )
    s = summarize(kept, foreign + 2)
    assert s.accepted == 3 and s.rejected_foreign_domain == 2 and s.names == ("a", "b", "s")
    assert s.earliest_expiry == datetime.fromtimestamp(1_800_000_000, UTC)
    assert SECRET not in repr(s)
    assert summarize([cookie("only")], 0).earliest_expiry is None  # semua cookie sesi


def test_load_cookie_file_parses_json_and_reports_position_only_on_error() -> None:
    assert load_cookie_file(json.dumps([cookie()]))[0]["name"] == "auth_token"
    with pytest.raises(SessionImportError, match="bukan JSON"):
        load_cookie_file("{rusak")


def test_domain_matching_is_case_insensitive_and_ignores_the_leading_dot() -> None:
    kept, foreign = parse_cookies(
        [cookie("a", ".X.COM"), cookie("b", "API.Twitter.Com"), cookie("c", "x.com")], "x"
    )
    assert [c["name"] for c in kept] == ["a", "b", "c"] and foreign == 0


@pytest.mark.parametrize("domain", [None, ""])
def test_missing_or_empty_domain_is_reported_as_such(domain) -> None:
    item = {"name": "n", "value": "v"} | ({} if domain is None else {"domain": domain})
    with pytest.raises(SessionImportError, match="domain wajib"):
        parse_cookies([item], "x")


def test_boolean_expiry_is_not_treated_as_a_timestamp() -> None:
    kept, _ = parse_cookies([cookie("a", expires=True), cookie("b", expirationDate=False)], "x")
    assert all("expires" not in c for c in kept)
