"""WP-1.1: model Observation (PRD bagian 5, 7.1, 9.3)."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest
from collection.contracts import (
    CollectionStatus,
    ContractViolation,
    Observation,
    SourceMethod,
    SourceObjectType,
)
from investigations.enums import Platform

OBSERVED = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
PUBLISHED = datetime(2026, 10, 16, 1, 30, tzinfo=UTC)

# Contoh persis dari PRD bagian 7.1 (nilai sintetis).
PRD_EXAMPLE = {
    "platform": "x",
    "source_object_type": "reply",
    "external_post_id": "sample-reply-id",
    "external_actor_id": "sample-actor-id",
    "parent_post_id": "sample-parent-id",
    "published_at": "2026-10-16T01:30:00Z",
    "observed_at": "2026-10-16T01:32:00Z",
    "text": "Contoh isi respons",
    "inspection_run_id": "sample-run-id",
    "collection_status": "PARTIAL",
    "source_method": "authorized_observation",
}


def make(**overrides) -> Observation:
    base = dict(
        platform=Platform.X,
        source_object_type=SourceObjectType.REPLY,
        inspection_run_id="run-1",
        observed_at=OBSERVED,
        collection_status=CollectionStatus.COMPLETED,
        source_method=SourceMethod.SYNTHETIC_FIXTURE,
        external_post_id="p1",
        external_actor_id="a1",
        parent_post_id="p0",
        published_at=PUBLISHED,
        text="isi",
    )
    base.update(overrides)
    return Observation(**base)


# --- contoh PRD dan serialisasi ------------------------------------------------------------


def test_prd_example_parses_as_is() -> None:
    obs = Observation.from_dict(PRD_EXAMPLE)
    assert obs.platform is Platform.X
    assert obs.source_object_type is SourceObjectType.REPLY
    assert obs.collection_status is CollectionStatus.PARTIAL
    assert obs.source_method is SourceMethod.AUTHORIZED_OBSERVATION
    assert obs.published_at == datetime(2026, 10, 16, 1, 30, tzinfo=UTC)
    assert obs.published_at != obs.observed_at


def test_roundtrip_through_dict_preserves_everything() -> None:
    obs = make(mentioned_actor_ids=("m1", "m2"), actor_handle="@u", actor_display_name="U")
    assert Observation.from_dict(obs.to_dict()) == obs


def test_to_dict_is_json_friendly() -> None:
    import json

    json.dumps(make().to_dict())  # tidak boleh raise


def test_from_dict_rejects_unknown_keys() -> None:
    with pytest.raises(ContractViolation, match="tidak dikenal"):
        Observation.from_dict({**PRD_EXAMPLE, "stance": "PRO"})


def test_from_dict_rejects_missing_required_fields() -> None:
    data = {k: v for k, v in PRD_EXAMPLE.items() if k != "observed_at"}
    with pytest.raises(ContractViolation):
        Observation.from_dict(data)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("platform", "myspace"),
        ("source_object_type", "story"),
        ("collection_status", "DONE"),
        ("source_method", "scraped"),
    ],
)
def test_invalid_enum_values_name_the_allowed_ones(field: str, bad: str) -> None:
    with pytest.raises(ContractViolation, match=field):
        Observation.from_dict({**PRD_EXAMPLE, field: bad})


def test_invalid_datetime_string_is_a_contract_violation() -> None:
    with pytest.raises(ContractViolation, match="observed_at"):
        Observation.from_dict({**PRD_EXAMPLE, "observed_at": "kemarin"})


# --- waktu: published_at tidak pernah berasal dari waktu pengambilan -----------------------


def test_published_at_none_is_allowed_and_means_unknown() -> None:
    assert make(published_at=None).published_at is None


def test_published_at_equal_to_observed_at_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="waktu pengambilan tidak boleh"):
        make(published_at=OBSERVED)


def test_published_at_equal_to_captured_at_is_rejected() -> None:
    captured = OBSERVED + timedelta(seconds=5)
    with pytest.raises(ContractViolation, match="waktu pengambilan"):
        make(published_at=captured, captured_at=captured)


def test_equal_instants_in_different_timezones_are_still_rejected() -> None:
    wib = timezone(timedelta(hours=7))
    with pytest.raises(ContractViolation):
        make(published_at=OBSERVED.astimezone(wib))


def test_published_in_the_future_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="lebih baru"):
        make(published_at=OBSERVED + timedelta(minutes=1))


@pytest.mark.parametrize("field", ["observed_at", "published_at", "captured_at"])
def test_naive_datetimes_are_rejected(field: str) -> None:
    naive = datetime(2026, 10, 16, 0, 0, 0)
    kwargs = {field: naive}
    if field == "observed_at":
        kwargs["published_at"] = None
    with pytest.raises(ContractViolation, match="zona waktu"):
        make(**kwargs)


def test_observed_at_is_required() -> None:
    with pytest.raises(ContractViolation):
        make(observed_at=None)


# --- identitas (PRD bagian 5) ---------------------------------------------------------------


@pytest.mark.parametrize("field", ["external_post_id", "external_actor_id"])
def test_missing_stable_id_requires_the_verification_flag(field: str) -> None:
    with pytest.raises(ContractViolation, match="identity_needs_verification"):
        make(**{field: None})
    flagged = make(**{field: None}, identity_needs_verification=True)
    assert flagged.identity_needs_verification is True


def test_flag_may_be_set_even_when_ids_exist() -> None:
    assert make(identity_needs_verification=True).external_post_id == "p1"


@pytest.mark.parametrize("bad", ["", "   ", " p1", "p1 ", "\t", "x" * 257])
def test_malformed_ids_are_rejected(bad: str) -> None:
    with pytest.raises(ContractViolation):
        make(external_post_id=bad)
    with pytest.raises(ContractViolation):
        make(external_actor_id=bad)


def test_username_is_information_not_identity() -> None:
    a = make(actor_handle="@lama")
    b = make(actor_handle="@baru")
    assert a.external_actor_id == b.external_actor_id  # identitas tetap sama


# --- hubungan -------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [SourceObjectType.REPLY, SourceObjectType.COMMENT])
def test_reply_needs_a_parent_or_an_explicit_unknown(kind: SourceObjectType) -> None:
    with pytest.raises(ContractViolation, match="parent_post_id"):
        make(source_object_type=kind, parent_post_id=None)
    assert make(source_object_type=kind, parent_post_id=None, parent_unknown=True).parent_unknown


def test_parent_and_unknown_flag_contradict() -> None:
    with pytest.raises(ContractViolation, match="bertentangan"):
        make(parent_post_id="p0", parent_unknown=True)


def test_non_reply_types_cannot_have_a_parent() -> None:
    with pytest.raises(ContractViolation, match="hanya untuk reply"):
        make(source_object_type=SourceObjectType.POST, parent_post_id="p0")
    with pytest.raises(ContractViolation):
        make(source_object_type=SourceObjectType.POST, parent_post_id=None, parent_unknown=True)


def test_object_cannot_be_its_own_parent() -> None:
    with pytest.raises(ContractViolation, match="induknya sendiri"):
        make(external_post_id="p1", parent_post_id="p1")


def test_quote_requires_quoted_id_and_only_quotes_may_have_it() -> None:
    quote = make(
        source_object_type=SourceObjectType.QUOTE, parent_post_id=None, quoted_post_id="q1"
    )
    assert quote.quoted_post_id == "q1"
    with pytest.raises(ContractViolation, match="quoted_post_id"):
        make(source_object_type=SourceObjectType.QUOTE, parent_post_id=None)
    with pytest.raises(ContractViolation, match="quoted_post_id"):
        make(quoted_post_id="q1")


def test_repost_requires_reposted_id_and_only_reposts_may_have_it() -> None:
    repost = make(
        source_object_type=SourceObjectType.REPOST, parent_post_id=None, reposted_post_id="r1"
    )
    assert repost.reposted_post_id == "r1"
    with pytest.raises(ContractViolation, match="reposted_post_id"):
        make(source_object_type=SourceObjectType.REPOST, parent_post_id=None)
    with pytest.raises(ContractViolation, match="reposted_post_id"):
        make(reposted_post_id="r1")


def test_mentioned_actors_are_validated() -> None:
    assert make(mentioned_actor_ids=["m1"]).mentioned_actor_ids == ("m1",)
    with pytest.raises(ContractViolation):
        make(mentioned_actor_ids=("m1", ""))
    with pytest.raises(ContractViolation):
        make(mentioned_actor_ids=(None,))


# --- teks dan bentuk ------------------------------------------------------------------------


def test_none_text_and_empty_text_are_different() -> None:
    assert make(text=None).text is None  # tidak tersedia / tidak teramati
    assert make(text="").text == ""  # ada, tetapi kosong


def test_text_limits() -> None:
    with pytest.raises(ContractViolation):
        make(text="x" * 200_001)
    with pytest.raises(ContractViolation):
        make(text=123)  # type: ignore[arg-type]


def test_observation_is_immutable() -> None:
    obs = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.text = "diubah"  # type: ignore[misc]


def test_observation_carries_source_data_only_no_interpretation() -> None:
    # Observe first, interpret later (PRD bagian 3.3): tidak ada field label/stance/skor.
    names = {f.name for f in dataclasses.fields(Observation)}
    for forbidden in ("stance", "label", "sentiment", "score", "alignment", "character"):
        assert not any(forbidden in n for n in names), forbidden
