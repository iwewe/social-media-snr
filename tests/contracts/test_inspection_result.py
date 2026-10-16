"""WP-1.1: invarian InspectionResult, request, capabilities (FR-021, FR-024, FR-026; AT-14)."""

from datetime import UTC, datetime

import pytest
from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    Capabilities,
    Capability,
    CapabilityDeclaration,
    CapabilityStatus,
    CollectionStatus,
    CollectorInfo,
    ContractViolation,
    Coverage,
    InspectionOutcome,
    InspectionRequest,
    InspectionResult,
    Limitation,
    LimitationCode,
    Observation,
    SourceMethod,
    SourceObjectType,
    TargetUrlInfo,
    UnavailableObject,
)
from investigations.enums import Platform, TargetType

RUN = "run-1"
COLLECTOR = CollectorInfo("uji", "0.0.1")
OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
O = InspectionOutcome  # noqa: E741 - singkatan lokal agar tabel kasus mudah dibaca
L = LimitationCode


def obs(post_id: str = "p1", status=CollectionStatus.COMPLETED, **kw) -> Observation:
    base = dict(
        platform=Platform.X,
        source_object_type=SourceObjectType.REPLY,
        inspection_run_id=RUN,
        observed_at=OBSERVED,
        collection_status=status,
        source_method=SourceMethod.SYNTHETIC_FIXTURE,
        external_post_id=post_id,
        external_actor_id="a1",
        parent_post_id="p0",
    )
    base.update(kw)
    return Observation(**base)


def cov(complete=True, displayed=None) -> Coverage:
    return Coverage(
        scope=(Capability.INSPECT_REPLIES,), pagination_complete=complete,
        platform_displayed_count=displayed,
    )


def result(outcome, observations=(), limitations=(), coverage=None, **kw) -> InspectionResult:
    return InspectionResult(
        platform=kw.pop("platform", Platform.X),
        inspection_run_id=kw.pop("run", RUN),
        outcome=outcome,
        collector=COLLECTOR,
        coverage=coverage or cov(),
        observations=tuple(observations),
        limitations=tuple(limitations),
        **kw,
    )


def lim(code=L.PARSE_FAILED, msg="alasan") -> Limitation:
    return Limitation(code, msg)


PARTIAL_STATUS = CollectionStatus.PARTIAL

# --- jalur sukses ---------------------------------------------------------------------------


def test_completed_result_with_data() -> None:
    r = result(O.COMPLETED, [obs("p1"), obs("p2")], coverage=cov(True, 2))
    assert r.observed_reply_count == 2


def test_completed_may_carry_informational_limitations() -> None:
    # Screenshot tidak boleh disimpan bukan alasan untuk menyebut pengambilan tidak lengkap (FR-042).
    r = result(O.COMPLETED, [obs()], [lim(L.ARTIFACT_NOT_PERMITTED, "media tidak boleh disimpan")])
    assert r.outcome is O.COMPLETED


def test_displayed_count_and_observed_count_are_independent() -> None:
    r = result(O.COMPLETED, [obs("p1")], coverage=cov(True, displayed=50))
    assert r.coverage.platform_displayed_count == 50
    assert r.observed_reply_count == 1  # PRD bagian 9.3: dua angka berbeda


def test_genuinely_empty_post_is_completed_only_when_platform_says_zero() -> None:
    assert result(O.COMPLETED, [], coverage=cov(True, displayed=0)).observations == ()


# --- COMPLETED tidak boleh berbohong --------------------------------------------------------


@pytest.mark.parametrize("blocking_code", [c for c in LimitationCode if c.blocking])
def test_completed_with_any_blocking_limitation_is_rejected(blocking_code) -> None:
    with pytest.raises(ContractViolation, match="COMPLETED"):
        result(O.COMPLETED, [obs()], [lim(blocking_code)])


@pytest.mark.parametrize("unknown", [None, False])
def test_completed_requires_pagination_complete_true(unknown) -> None:
    with pytest.raises(ContractViolation, match="pagination_complete"):
        result(O.COMPLETED, [obs()], coverage=cov(unknown))


def test_empty_completed_without_platform_zero_is_rejected() -> None:
    # AT-14: kegagalan tidak boleh tampil sebagai "tidak ada komentar".
    with pytest.raises(ContractViolation, match="Hasil kosong"):
        result(O.COMPLETED, [], coverage=cov(True, displayed=None))
    with pytest.raises(ContractViolation, match="Hasil kosong"):
        result(O.COMPLETED, [], coverage=cov(True, displayed=7))


# --- PARTIAL --------------------------------------------------------------------------------


def test_partial_with_reason_and_partial_observations() -> None:
    r = result(
        O.PARTIAL, [obs("p1", PARTIAL_STATUS)], [lim(L.PAGINATION_INCOMPLETE)], cov(False, 40)
    )
    assert r.outcome is O.PARTIAL


def test_partial_without_limitations_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="menjelaskan sebabnya"):
        result(O.PARTIAL, [obs("p1", PARTIAL_STATUS)], [], cov(False))


def test_partial_with_only_informational_limitation_and_complete_pagination_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="seharusnya COMPLETED"):
        result(
            O.PARTIAL, [obs("p1", PARTIAL_STATUS)], [lim(L.ARTIFACT_NOT_AVAILABLE)], cov(True)
        )


def test_partial_with_unknown_completeness_and_informational_limitation_is_allowed() -> None:
    r = result(
        O.PARTIAL, [obs("p1", PARTIAL_STATUS)], [lim(L.ARTIFACT_NOT_AVAILABLE)], cov(None)
    )
    assert r.outcome is O.PARTIAL


# --- kegagalan tidak membawa data dan wajib dijelaskan --------------------------------------


@pytest.mark.parametrize("outcome", [O.FAILED, O.ACCESS_RESTRICTED, O.UNSUPPORTED])
def test_non_data_outcomes_cannot_carry_observations(outcome) -> None:
    code = {O.FAILED: L.PARSE_FAILED, O.ACCESS_RESTRICTED: L.ACCESS_RESTRICTED}.get(
        outcome, L.UNSUPPORTED
    )
    with pytest.raises(ContractViolation, match="tidak boleh membawa observasi"):
        result(outcome, [obs("p1", PARTIAL_STATUS)], [lim(code)], cov(None))


def test_access_restricted_needs_a_matching_limitation() -> None:
    with pytest.raises(ContractViolation, match="ACCESS_RESTRICTED"):
        result(O.ACCESS_RESTRICTED, [], [lim(L.TIMEOUT)], cov(None))
    for ok in (L.ACCESS_RESTRICTED, L.AUTH_REQUIRED):
        assert result(O.ACCESS_RESTRICTED, [], [lim(ok)], cov(None)).outcome is (
            O.ACCESS_RESTRICTED
        )


def test_unsupported_needs_a_matching_limitation() -> None:
    with pytest.raises(ContractViolation, match="UNSUPPORTED"):
        result(O.UNSUPPORTED, [], [lim(L.PARSE_FAILED)], cov(None))
    assert result(O.UNSUPPORTED, [], [lim(L.UNSUPPORTED)], cov(None)).limitations


def test_failed_needs_a_blocking_explanation() -> None:
    with pytest.raises(ContractViolation, match="FAILED"):
        result(O.FAILED, [], [], cov(None))
    with pytest.raises(ContractViolation, match="FAILED"):
        result(O.FAILED, [], [lim(L.ARTIFACT_NOT_AVAILABLE)], cov(None))
    assert result(O.FAILED, [], [lim(L.PARSE_FAILED)], cov(None)).outcome is O.FAILED


def test_limitation_requires_a_readable_reason() -> None:
    with pytest.raises(ContractViolation, match="message"):
        Limitation(L.TIMEOUT, "   ")


# --- isolasi platform dan konsistensi -------------------------------------------------------


def test_observation_from_another_platform_is_rejected() -> None:
    foreign = obs("p1", platform=Platform.THREADS)
    with pytest.raises(ContractViolation, match="platform lain"):
        result(O.COMPLETED, [foreign], coverage=cov(True, 1))


def test_observation_from_another_run_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="inspection_run_id"):
        result(O.COMPLETED, [obs("p1", inspection_run_id="run-lain")], coverage=cov(True, 1))


def test_observation_status_must_match_the_outcome() -> None:
    with pytest.raises(ContractViolation, match="collection_status"):
        result(O.COMPLETED, [obs("p1", PARTIAL_STATUS)], coverage=cov(True, 1))
    with pytest.raises(ContractViolation, match="collection_status"):
        result(O.PARTIAL, [obs("p1", CollectionStatus.COMPLETED)], [lim()], cov(False))


def test_duplicate_external_ids_in_one_result_are_rejected() -> None:
    with pytest.raises(ContractViolation, match="ganda"):
        result(O.COMPLETED, [obs("p1"), obs("p1")], coverage=cov(True, 2))


def test_objects_without_ids_are_not_deduplicated() -> None:
    a = obs(None, identity_needs_verification=True)
    b = obs(None, identity_needs_verification=True)
    assert result(O.COMPLETED, [a, b], coverage=cov(True, 2)).observed_reply_count == 0


def test_artifact_filenames_must_be_unique_and_simple() -> None:
    shot = ArtifactCapture(ArtifactKind.SCREENSHOT, "a.png", b"x", "image/png")
    with pytest.raises(ContractViolation, match="unik"):
        result(O.COMPLETED, [obs()], artifacts=(shot, shot))
    for bad in ("", "../a.png", "dir/a.png", "a\\b.png", ".."):
        with pytest.raises(ContractViolation):
            ArtifactCapture(ArtifactKind.OTHER, bad, b"x", "text/plain")


def test_result_is_immutable_and_sequences_are_tuples() -> None:
    r = result(O.COMPLETED, [obs()], coverage=cov(True, 1))
    assert isinstance(r.observations, tuple)
    with pytest.raises(AttributeError):
        r.outcome = O.FAILED  # type: ignore[misc]


# --- request, coverage, target ---------------------------------------------------------------


def test_request_validation() -> None:
    ok = InspectionRequest(
        RUN, Platform.X, "https://x.com/u/status/1", TargetType.POST, (Capability.INSPECT_POST,)
    )
    assert ok.max_items is None
    base = (RUN, Platform.X, "https://x.com/u/status/1", TargetType.POST)
    with pytest.raises(ContractViolation):
        InspectionRequest(*base, requested=())
    with pytest.raises(ContractViolation, match="ganda"):
        InspectionRequest(*base, requested=(Capability.INSPECT_POST, Capability.INSPECT_POST))
    with pytest.raises(ContractViolation):
        InspectionRequest(*base, requested=(Capability.INSPECT_POST,), max_items=0)
    with pytest.raises(ContractViolation):
        InspectionRequest(" ", *base[1:], requested=(Capability.INSPECT_POST,))


def test_coverage_rejects_negative_displayed_count() -> None:
    with pytest.raises(ContractViolation):
        Coverage(scope=(), pagination_complete=True, platform_displayed_count=-1)


def test_target_info_rules() -> None:
    TargetUrlInfo(Platform.X, TargetType.POST, "https://x.com/u/status/1", "1")
    TargetUrlInfo(Platform.TIKTOK, TargetType.POST, "https://vt.tiktok.com/ZSabc")  # tanpa ID
    with pytest.raises(ContractViolation):
        TargetUrlInfo(Platform.X, TargetType.POST, "http://x.com/u")
    with pytest.raises(ContractViolation):
        TargetUrlInfo(Platform.X, TargetType.POST, "https://x.com/u", external_id=" ")


def test_collector_info_requires_name_and_version() -> None:
    with pytest.raises(ContractViolation):
        CollectorInfo("", "1")
    with pytest.raises(ContractViolation):
        CollectorInfo("x", " ")


# --- capabilities ---------------------------------------------------------------------------


def declarations(**overrides) -> dict:
    base = {c: CapabilityDeclaration(CapabilityStatus.SUPPORTED) for c in Capability}
    base.update(overrides)
    return base


def test_every_capability_must_be_declared_explicitly() -> None:
    partial = declarations()
    del partial[Capability.PRESERVE_MEDIA]
    with pytest.raises(ContractViolation, match="preserve_media"):
        Capabilities(Platform.X, partial)


def test_non_supported_capability_needs_a_reason() -> None:
    with pytest.raises(ContractViolation, match="alasan"):
        CapabilityDeclaration(CapabilityStatus.UNTESTED)
    CapabilityDeclaration(CapabilityStatus.UNTESTED, "belum diuji")


def test_only_supported_and_limited_are_runnable() -> None:
    caps = Capabilities(
        Platform.X,
        declarations(
            **{
                Capability.INSPECT_REPLIES: CapabilityDeclaration(CapabilityStatus.LIMITED, "login"),
                Capability.INSPECT_ACCOUNT: CapabilityDeclaration(CapabilityStatus.UNTESTED, "baru"),
                Capability.PRESERVE_MEDIA: CapabilityDeclaration(CapabilityStatus.UNSUPPORTED, "x"),
            }
        ),
    )
    assert caps.runnable(Capability.INSPECT_POST)
    assert caps.runnable(Capability.INSPECT_REPLIES)
    assert not caps.runnable(Capability.INSPECT_ACCOUNT)
    assert not caps.runnable(Capability.PRESERVE_MEDIA)


def test_declarations_are_read_only() -> None:
    caps = Capabilities(Platform.X, declarations())
    with pytest.raises(TypeError):
        caps.declarations[Capability.INSPECT_POST] = CapabilityDeclaration(  # type: ignore[index]
            CapabilityStatus.UNSUPPORTED, "x"
        )


# --- confirmed_unavailable (WP-1.4) ---------------------------------------------------------


def test_confirmed_unavailable_is_allowed_on_a_complete_result() -> None:
    r = result(
        O.COMPLETED, [obs("p1")], coverage=cov(True, 1),
        confirmed_unavailable=(UnavailableObject("p9", "halaman objek: komentar dihapus"),),
    )
    assert r.confirmed_unavailable[0].external_post_id == "p9"


@pytest.mark.parametrize("outcome", [O.PARTIAL, O.FAILED, O.ACCESS_RESTRICTED, O.UNSUPPORTED])
def test_confirmed_unavailable_is_rejected_unless_the_result_is_completed(outcome) -> None:
    code = {O.PARTIAL: L.PAGINATION_INCOMPLETE, O.FAILED: L.PARSE_FAILED,
            O.ACCESS_RESTRICTED: L.ACCESS_RESTRICTED, O.UNSUPPORTED: L.UNSUPPORTED}[outcome]
    observations = [obs("p1", PARTIAL_STATUS)] if outcome is O.PARTIAL else []
    with pytest.raises(ContractViolation, match="hanya boleh pada hasil COMPLETED"):
        result(outcome, observations, [lim(code)], cov(False if outcome is O.PARTIAL else None),
               confirmed_unavailable=(UnavailableObject("p9", "bukti"),))


def test_object_cannot_be_both_observed_and_unavailable() -> None:
    with pytest.raises(ContractViolation, match="sekaligus teramati"):
        result(O.COMPLETED, [obs("p1")], coverage=cov(True, 1),
               confirmed_unavailable=(UnavailableObject("p1", "bukti"),))


def test_duplicate_unavailable_ids_are_rejected() -> None:
    dup = (UnavailableObject("p9", "a"), UnavailableObject("p9", "b"))
    with pytest.raises(ContractViolation, match="ganda"):
        result(O.COMPLETED, [obs("p1")], coverage=cov(True, 1), confirmed_unavailable=dup)


@pytest.mark.parametrize(("post_id", "evidence"), [("", "x"), (" p9", "x"), ("p9", ""), ("p9", "  ")])
def test_unavailable_object_needs_an_id_and_evidence(post_id, evidence) -> None:
    with pytest.raises(ContractViolation):
        UnavailableObject(post_id, evidence)
