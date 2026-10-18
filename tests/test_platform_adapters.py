"""WP-3.0 s.d. 3.5: adapter platform yang dinonaktifkan (validasi URL, kemampuan, gerbang) dan dokumen kelayakan."""

from pathlib import Path

import pytest
from collection.adapters.facebook import FacebookAdapter
from collection.adapters.instagram import InstagramAdapter
from collection.adapters.threads import ThreadsAdapter
from collection.adapters.tiktok import TikTokAdapter
from collection.adapters.x import XAdapter
from collection.contracts import (
    Capability,
    CapabilityStatus,
    ContractViolation,
    InspectionOutcome,
    InspectionRequest,
    LimitationCode,
)
from collection.orchestrator import registry
from django.test import override_settings
from investigations.enums import Platform, TargetType
from investigations.errors import InvalidTargetURL

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = [XAdapter, ThreadsAdapter, TikTokAdapter, InstagramAdapter, FacebookAdapter]
P, A = TargetType.POST, TargetType.ACCOUNT

# (kelas, url, jenis target, external_id)
VALID = [
    (XAdapter, "https://x.com/someuser/status/1234567890", P, "1234567890"),
    (XAdapter, "https://twitter.com/SomeUser/status/1234567890?s=20", P, "1234567890"),
    (XAdapter, "https://mobile.x.com/someuser/status/9/", P, "9"),
    (XAdapter, "https://x.com/someuser", A, None),
    (ThreadsAdapter, "https://www.threads.net/@some.user/post/CuXyZ1234ab", P, None),
    (ThreadsAdapter, "https://threads.com/@some.user", A, None),
    (TikTokAdapter, "https://www.tiktok.com/@some.user/video/7234567890123456789", P, "7234567890123456789"),
    (TikTokAdapter, "https://vm.tiktok.com/ZMabc12345", P, None),
    (TikTokAdapter, "https://vt.tiktok.com/ZSabc12345/", P, None),
    (TikTokAdapter, "https://tiktok.com/@some.user", A, None),
    (InstagramAdapter, "https://www.instagram.com/p/CuXyZ1234ab/", P, None),
    (InstagramAdapter, "https://instagram.com/reel/CuXyZ1234ab/?igsh=abc", P, None),
    (InstagramAdapter, "https://instagram.com/some.user/p/CuXyZ1234ab", P, None),
    (InstagramAdapter, "https://instagram.com/some.user/", A, None),
    (FacebookAdapter, "https://www.facebook.com/SomePage/posts/pfbid02abcDEF123", P, None),
    (FacebookAdapter, "https://facebook.com/permalink.php?story_fbid=1234567&id=7654321&fbclid=x", P, None),
    (FacebookAdapter, "https://facebook.com/groups/some.group/posts/1234567890", P, None),
    (FacebookAdapter, "https://facebook.com/watch/?v=1234567890", P, None),
    (FacebookAdapter, "https://fb.watch/abCd123xYz", P, None),
    (FacebookAdapter, "https://facebook.com/share/p/1AbCdEfGh", P, None),
    (FacebookAdapter, "https://facebook.com/SomePage", A, None),
    (FacebookAdapter, "https://facebook.com/profile.php?id=100012345678", A, None),
]
INVALID = [
    (XAdapter, "https://x.com/"),
    (XAdapter, "https://x.com/home"),
    (XAdapter, "https://x.com/explore"),
    (XAdapter, "https://x.com/someuser/status/abc"),
    (XAdapter, "https://x.com/someuser/likes"),
    (XAdapter, "https://x.com/abcdefghijklmnop"),  # 16 karakter: melebihi batas handle
    (XAdapter, "https://tiktok.com/@u/video/1"),
    (ThreadsAdapter, "https://threads.com/"),
    (ThreadsAdapter, "https://threads.com/someuser"),
    (ThreadsAdapter, "https://x.com/someuser/status/1"),
    (TikTokAdapter, "https://tiktok.com/"),
    (TikTokAdapter, "https://tiktok.com/abcdefgh"),  # tautan pendek hanya di host pendek
    (TikTokAdapter, "https://vm.tiktok.com/@u/video/1"),
    (TikTokAdapter, "https://vm.tiktok.com/"),
    (InstagramAdapter, "https://instagram.com/"),
    (InstagramAdapter, "https://instagram.com/explore"),
    (InstagramAdapter, "https://instagram.com/accounts/login"),
    (InstagramAdapter, "https://instagram.com/p/ab"),
    (FacebookAdapter, "https://facebook.com/"),
    (FacebookAdapter, "https://facebook.com/login"),
    (FacebookAdapter, "https://facebook.com/permalink.php?story_fbid=1234567"),
    (FacebookAdapter, "https://facebook.com/watch"),
    (FacebookAdapter, "https://fb.watch/"),
    (FacebookAdapter, "https://fb.watch/SomePage/posts/123456"),
    (FacebookAdapter, "https://facebook.com/SomePage/posts/"),
]
GARBAGE = ["", "   ", "bukan url", "javascript:alert(1)", "ftp://x.com/u/status/1", "https://user:pw@x.com/u/status/1"]


@pytest.mark.parametrize(("adapter", "url", "kind", "external_id"), VALID)
def test_valid_urls_are_classified_and_only_stable_ids_are_extracted(adapter, url, kind, external_id) -> None:
    info = adapter().validate_target_url(url)
    assert info.platform is adapter.platform
    assert info.target_type is kind
    assert info.external_id == external_id
    assert info.normalized_url.startswith("https://")
    assert "utm_" not in info.normalized_url and "fbclid" not in info.normalized_url


@pytest.mark.parametrize(("adapter", "url"), INVALID)
def test_unrecognised_or_foreign_urls_are_rejected(adapter, url) -> None:
    with pytest.raises(InvalidTargetURL):
        adapter().validate_target_url(url)


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("url", GARBAGE)
def test_garbage_is_rejected(adapter, url) -> None:
    with pytest.raises(InvalidTargetURL):
        adapter().validate_target_url(url)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_every_capability_is_declared_untested_with_a_reason_pointing_at_the_feasibility_doc(adapter) -> None:
    caps = adapter().capabilities()
    assert set(caps.declarations) == set(Capability)
    for cap in Capability:
        decl = caps.declarations[cap]
        assert decl.status is CapabilityStatus.UNTESTED and not caps.runnable(cap)
        assert "dinonaktifkan" in (decl.reason or "") and adapter.feasibility_doc in (decl.reason or "")
    assert (ROOT / adapter.feasibility_doc).is_file()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_the_gate_answers_unsupported_with_the_reason_for_every_requested_capability(adapter) -> None:
    request = InspectionRequest(
        inspection_run_id="11111111-1111-4111-8111-111111111111",
        platform=adapter.platform,
        target_url="https://example.invalid/",
        target_type=TargetType.POST,
        requested=tuple(Capability),
        run_sequence=1,
    )
    result = adapter().inspect(request)
    assert result.outcome is InspectionOutcome.UNSUPPORTED
    assert {lim.capability for lim in result.limitations} == set(Capability)
    assert all(lim.code is LimitationCode.UNSUPPORTED for lim in result.limitations)
    assert all(adapter.feasibility_doc in lim.message for lim in result.limitations)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_collect_can_never_run_even_if_called_directly(adapter) -> None:
    request = InspectionRequest(
        inspection_run_id="11111111-1111-4111-8111-111111111111",
        platform=adapter.platform,
        target_url="https://example.invalid/",
        target_type=TargetType.POST,
        requested=(Capability.INSPECT_POST,),
        run_sequence=1,
    )
    with pytest.raises(ContractViolation, match="dinonaktifkan"):
        adapter().collect(request)


def test_each_platform_has_exactly_one_pending_adapter_with_its_own_collector() -> None:
    assert {a.platform for a in ADAPTERS} == set(Platform)
    assert len({a.collector.name for a in ADAPTERS}) == len(ADAPTERS)


def test_adapters_can_be_listed_in_snr_adapters_and_show_their_reason_through_the_registry() -> None:
    registry.clear()
    dotted = [f"{a.__module__}.{a.__name__}" for a in ADAPTERS]
    try:
        with override_settings(SNR_ADAPTERS=dotted):
            registry.load_from_settings()
        assert registry.platforms() == sorted(p.value for p in Platform)
        adapter = registry.get(Platform.X)
        assert isinstance(adapter, XAdapter)
    finally:
        registry.clear()


def test_the_feasibility_documents_state_the_decision_and_the_standing_rules() -> None:
    readme = (ROOT / "docs/adapters/README.md").read_text()
    for needle in ("CAPTCHA", "tidak menyimpulkan legalitas", "DISABLED", "ACTIVE"):
        assert needle in readme, needle
    for adapter in ADAPTERS:
        text = (ROOT / adapter.feasibility_doc).read_text()
        for section in ("Jalur perolehan yang sah", "Kemampuan teruji", "Ketahanan parser", "Batasan", "Keputusan"):
            assert section in text, (adapter.feasibility_doc, section)
        assert "`DISABLED`" in text and "bukan keputusan hukum" in text


def test_disabled_adapters_fill_only_the_platforms_without_an_adapter() -> None:
    from collection.adapters import DISABLED_ADAPTERS, register_disabled_adapters

    assert {a.platform for a in DISABLED_ADAPTERS} == set(Platform)
    registry.clear()
    try:
        registry.register(Platform.X, XAdapter)  # sudah ada adapter untuk X: tidak ditimpa
        added = register_disabled_adapters(registry)
        assert sorted(added) == sorted(p.value for p in Platform if p is not Platform.X)
        assert registry.platforms() == sorted(p.value for p in Platform)
        assert register_disabled_adapters(registry) == []  # idempoten
    finally:
        registry.clear()


@pytest.mark.django_db
def test_a_run_for_a_platform_without_access_reports_the_reason_not_a_generic_message(
    settings, tmp_path
) -> None:
    from collection import services
    from collection.models import InspectionRun
    from collection.orchestrator import request_inspection, run_inspection
    from django.contrib.auth.models import User
    from investigations import services as inv_services

    registry.clear()
    registry.register(Platform.THREADS, ThreadsAdapter)
    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="Uji")
    target = inv_services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.THREADS,
        target_type=TargetType.POST,
        url="https://threads.com/@some.user/post/CuXyZ1234ab",
    )
    try:
        run = request_inspection(target=target, user=user, enqueue=False)
        run_inspection(run.pk)
        run = InspectionRun.objects.get(pk=run.pk)
    finally:
        registry.clear()
    assert run.status == "UNSUPPORTED"
    assert any("threads-feasibility.md" in str(lim) for lim in run.limitations)
    assert services is not None
