"""WP-1.4: isi kanonik dan hash isi (definisi 'perubahan relevan', FR-035, AT-05)."""

import pytest
from collection import ingestion
from collection.content import (
    CONTENT_HASH_VERSION,
    canonical,
    canonical_from_observation,
    normalize_text,
    observation_content_hash,
)
from collection.contracts import SourceObjectType
from collection.models import PostObservation, PostRelation
from collection.reconciliation.service import _canonical_from_row
from collection_helpers import ingest, make_result, new_run, obs, register  # noqa: F401
from django.contrib.auth.models import User
from investigations import services as inv_services
from investigations.enums import Platform


def base(**kw):
    values = dict(object_type="reply", text="isi", author="a1", parent="p0", parent_unknown=False)
    values.update(kw)
    return canonical(**values)


# --- normalisasi teks -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("halo  dunia", "halo dunia"),
        ("  halo\tdunia  ", "halo dunia"),
        ("a\r\nb", "a\nb"),
        ("a\rb", "a\nb"),
        ("a   \n   b", "a\nb"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("\n\nhalo\n\n", "halo"),
        ("hal​o", "halo"),
        ("﻿halo", "halo"),
        ("na me", "na me"),  # spasi tak-terputus disamakan
        ("é", "é"),  # NFC: e + aksen gabung = é
        ("", ""),
    ],
)
def test_text_normalisation(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_none_is_distinct_from_empty_text() -> None:
    assert normalize_text(None) is None
    assert normalize_text("") == ""
    assert base(text=None).digest() != base(text="").digest()


def test_zwj_and_zwnj_are_kept_because_they_are_meaningful() -> None:
    assert normalize_text("a‍b") == "a‍b"
    assert normalize_text("a‌b") == "a‌b"


def test_substantive_whitespace_free_edits_are_kept() -> None:
    assert normalize_text("Setuju") != normalize_text("Tidak setuju")


# --- hash -------------------------------------------------------------------------------------


def test_render_differences_do_not_change_the_hash() -> None:
    a = base(text="Perusahaan  tidak perlu\r\ndiaudit ")
    b = base(text="Perusahaan tidak perlu\ndiaudit")
    assert a.digest() == b.digest()
    assert a.diff(b) == []


def test_each_relevant_attribute_changes_the_hash_and_is_named() -> None:
    reference = base(quoted=None, reposted=None, mentions=("m1",))
    variants = {
        "type": base(object_type="comment", mentions=("m1",)),
        "text": base(text="isi berbeda", mentions=("m1",)),
        "author": base(author="a2", mentions=("m1",)),
        "parent": base(parent="p9", mentions=("m1",)),
        "quoted": base(quoted="q1", mentions=("m1",)),
        "reposted": base(reposted="r1", mentions=("m1",)),
        "mentions": base(mentions=("m1", "m2")),
    }
    for name, variant in variants.items():
        assert variant.digest() != reference.digest(), name
        assert reference.diff(variant) == [name]


def test_parent_unknown_differs_from_a_known_parent_and_from_no_parent() -> None:
    unknown = base(parent=None, parent_unknown=True)
    assert unknown.digest() != base(parent=None, parent_unknown=False).digest()
    assert unknown.digest() != base(parent="p0").digest()
    assert base(parent="p0").diff(unknown) == ["parent"]


def test_mentions_are_order_and_duplicate_insensitive() -> None:
    assert base(mentions=("b", "a", "a")).digest() == base(mentions=("a", "b")).digest()


def test_hash_is_stable_hex_and_versioned() -> None:
    digest = base().digest()
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    assert digest == base().digest()
    assert CONTENT_HASH_VERSION == 1


def test_times_and_handles_are_not_part_of_the_content() -> None:
    from datetime import timedelta

    a = obs_for("r1", actor_handle="@lama", actor_display_name="Lama")
    b = obs_for("r1", actor_handle="@baru", actor_display_name="Baru")
    # observed_at/published_at/captured_at berbeda pun tidak mengubah isi.
    from collection.contracts import Observation

    c = Observation(**{**b.__dict__, "observed_at": b.observed_at + timedelta(days=3),
                       "published_at": None, "captured_at": b.observed_at + timedelta(days=3)})
    assert observation_content_hash(a) == observation_content_hash(b) == observation_content_hash(c)


def obs_for(post_id, **kw):
    """Observasi tanpa DB (run tiruan)."""
    from datetime import UTC, datetime, timedelta

    from collection.contracts import (
        CollectionStatus,
        Observation,
        SourceMethod,
    )

    observed = datetime(2026, 10, 16, 1, 32, tzinfo=UTC)
    fields = dict(
        platform=Platform.X, source_object_type=SourceObjectType.REPLY, inspection_run_id="run",
        observed_at=observed, collection_status=CollectionStatus.COMPLETED,
        source_method=SourceMethod.SYNTHETIC_FIXTURE, external_post_id=post_id,
        external_actor_id="a1", parent_post_id="p0", published_at=observed - timedelta(hours=1),
        text="isi",
    )
    fields.update(kw)
    return Observation(**fields)


def test_published_at_is_not_in_the_hash() -> None:
    from datetime import timedelta

    a = obs_for("r1")
    b = obs_for("r1", published_at=a.published_at - timedelta(days=9))
    assert observation_content_hash(a) == observation_content_hash(b)


# --- konsistensi jalur ingestion vs jalur baris (DB) -----------------------------------------


@pytest.mark.django_db
def test_hash_computed_at_ingestion_equals_hash_rebuilt_from_stored_rows() -> None:
    """Dua jalur penghitungan harus sepakat; kalau tidak, UNCHANGED akan salah menjadi MODIFIED."""
    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="A")
    target = register(inv, user, Platform.X, "https://x.com/u/status/1")
    run = new_run(target, user)

    samples = [
        obs(run, "r1", text="Perusahaan  tidak perlu\r\ndiaudit", mentioned_actor_ids=("m2", "m1")),
        obs(run, "r2", text=None, parent=None, parent_unknown=True),
        obs(run, "q1", kind=SourceObjectType.QUOTE, parent=None, quoted_post_id="orig", text=""),
        obs(run, "rp1", kind=SourceObjectType.REPOST, parent=None, reposted_post_id="orig"),
        obs(run, "p1", kind=SourceObjectType.POST, text="Judul\n\n\n\nisi", actor="a9"),
        obs(run, "r3", actor=None, identity_needs_verification=True, text="tanpa penulis"),
    ]
    ingest(run, samples)

    for sample in samples:
        row = PostObservation.objects.select_related("author").get(
            run=run, post__external_post_id=sample.external_post_id
        )
        relations = list(PostRelation.objects.filter(run=run, from_post=row.post).select_related(
            "to_post", "to_actor"))
        rebuilt = _canonical_from_row(row, relations)
        assert rebuilt == canonical_from_observation(sample), sample.external_post_id
        assert row.content_hash == rebuilt.digest() == observation_content_hash(sample)
        assert row.content_hash_version == CONTENT_HASH_VERSION


@pytest.mark.django_db
def test_legacy_observations_without_hash_are_allowed_by_the_database(monkeypatch) -> None:
    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="A")
    target = register(inv, user, Platform.X, "https://x.com/u/status/1")
    run = new_run(target, user)
    monkeypatch.setattr(ingestion, "observation_content_hash", lambda o: "")
    monkeypatch.setattr(ingestion, "CONTENT_HASH_VERSION", 0)
    ingest(run, [obs(run, "r1")])
    row = PostObservation.objects.get()
    assert (row.content_hash, row.content_hash_version) == ("", 0)


# --- rencana query: indeks parsial kandidat dapat dipakai --------------------------------------


@pytest.mark.django_db
def test_candidate_lookup_can_use_the_partial_index() -> None:
    """Pencarian kandidat per run tidak boleh bergantung pada statistik tabel (lihat ADR 0009).
    Dengan seq scan dimatikan, indeks parsial harus dipakai: membuktikan indeks cocok dengan query."""
    from collection.models import Post
    from django.db import connection

    user = User.objects.create_user("analis", password="x")
    inv = inv_services.create_investigation(user=user, name="A")
    target = register(inv, user, Platform.X, "https://x.com/u/status/1")
    run = new_run(target, user)
    ingest(run, [obs(run, None, actor=None, identity_needs_verification=True, text="anon")])

    sql, params = (
        Post.objects.filter(external_post_id__isnull=True, first_seen_run=run).values("pk").query.sql_with_params()
    )
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("EXPLAIN " + sql, params)
        plan = "\n".join(row[0] for row in cursor.fetchall())
    assert "post_candidates_by_run_idx" in plan, plan
