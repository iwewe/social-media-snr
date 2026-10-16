"""WP-1.4: rekonsiliasi antar-run (FR-034, FR-035, FR-036; AT-01..AT-05; PRD bagian 9.2)."""

import threading
import time
import pytest
from collection import ingestion
from collection.contracts import (
    ArtifactCapture,
    ArtifactKind,
    Limitation,
    LimitationCode,
    SourceObjectType,
)
from collection.ingestion import ingest_result
from collection.models import (
    InspectionRun,
    ObservationReconciliation,
    Post,
    PostObservation,
    RunStatus,
)
from collection.reconciliation import reconcile_run
from collection_helpers import (
    O,
    ingest,
    make_result,
    new_run,
    obs,
    recon_rows,
    register,
    replies,
    statuses,
)
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, connection, connections, transaction
from django.test.utils import CaptureQueriesContext
from investigations import services as inv_services
from investigations.enums import Platform

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def inv(user):
    return inv_services.create_investigation(user=user, name="Investigasi")


@pytest.fixture
def target(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


@pytest.fixture
def run1(target, user) -> InspectionRun:
    return new_run(target, user)


def counts_of(result) -> dict[str, int]:
    return {k: v for k, v in result.counts.items() if v}


# =============================== skenario dasar ===============================


def test_first_run_everything_is_new(run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2", "r3"]), displayed=3)
    result = reconcile_run(run1)
    assert result.done and result.baseline_runs == []
    assert counts_of(result) == {"NEW": 3}
    assert set(statuses(run1).values()) == {"NEW"}


def test_prd_rule_20_old_plus_5_new_adds_5_identities_not_25(target, user, run1) -> None:
    """PRD bagian 9.2 / AT-02 / AT-03."""
    old = [f"r{i}" for i in range(20)]
    new = [f"n{i}" for i in range(5)]
    ingest(run1, replies(run1, old), displayed=20)
    reconcile_run(run1)
    posts_before = Post.objects.count()

    run2 = new_run(target, user)
    ingest(run2, replies(run2, old + new), displayed=25)
    result = reconcile_run(run2)

    assert counts_of(result) == {"NEW": 5, "UNCHANGED": 20}
    assert Post.objects.count() == posts_before + 5  # bukan +25
    rows = statuses(run2)
    assert {k for k, v in rows.items() if v == "NEW"} == set(new)
    assert {k for k, v in rows.items() if v == "UNCHANGED"} == set(old)
    # Observasi dan bukti masing-masing run tetap tersedia.
    assert PostObservation.objects.filter(run=run1).count() == 20
    assert PostObservation.objects.filter(run=run2).count() == 25


def test_AT01_reinspection_keeps_one_target_and_adds_runs(target, user, run1) -> None:
    from investigations.models import CollectionTarget

    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1)
    reconcile_run(run2)
    assert CollectionTarget.objects.count() == 1
    assert InspectionRun.objects.filter(target=target).count() == 2


def test_summary_is_stored_on_the_run(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    reconcile_run(run1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1", "r2"]), displayed=2)
    reconcile_run(run2)
    run2.refresh_from_db()
    summary = run2.reconciliation
    assert summary["state"] == "DONE"
    assert summary["counts"]["NEW"] == 1 and summary["counts"]["UNCHANGED"] == 1
    assert summary["baseline_runs"] == [1]


# =============================== AT-04: tidak terlihat bukan terhapus ===============================


def test_AT04_object_missing_from_a_partial_run_is_not_observed_never_deleted(
    target, user, run1
) -> None:
    ingest(run1, replies(run1, [f"r{i}" for i in range(6)]), displayed=6)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r0", "r1", "r2"]), partial=True, displayed=40)
    result = reconcile_run(run2)

    assert counts_of(result) == {"UNCHANGED": 3, "NOT_OBSERVED": 3}
    rows = statuses(run2)
    assert {k for k, v in rows.items() if v == "NOT_OBSERVED"} == {"r3", "r4", "r5"}
    assert "DELETED" not in set(rows.values())
    for external in ("r3", "r4", "r5"):  # objek dan observasi lama utuh
        assert Post.objects.filter(external_post_id=external).exists()
        assert PostObservation.objects.filter(post__external_post_id=external, run=run1).exists()


def test_missing_from_a_completed_run_is_also_only_not_observed(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2"]), displayed=2)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1)
    assert statuses_after(run2)["r2"] == "NOT_OBSERVED"  # tanpa pernyataan eksplisit adapter


def statuses_after(run) -> dict[str, str]:
    reconcile_run(run)
    return statuses(run)


def test_not_observed_row_links_to_the_last_known_observation_only(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r2"]), displayed=1)
    reconcile_run(run2)
    row = recon_rows(run2)["r1"]
    assert row.current_observation_id is None
    assert row.previous_observation.run_id == run1.pk
    assert row.evidence == ""


# =============================== AT-05: perubahan isi ===============================


def test_AT05_edited_text_is_modified_and_history_is_kept(target, user, run1) -> None:
    ingest(run1, [obs(run1, "r1", text="versi awal")], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", text="versi diedit")], displayed=1)
    result = reconcile_run(run2)

    assert counts_of(result) == {"MODIFIED": 1}
    row = recon_rows(run2)["r1"]
    assert row.changed_fields == ["text"]
    assert row.previous_observation.text == "versi awal"
    assert row.current_observation.text == "versi diedit"
    assert PostObservation.objects.filter(post__external_post_id="r1").count() == 2


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"actor": "a-baru"}, ["author"]),
        ({"parent": "induk-lain"}, ["parent"]),
        ({"parent": None, "parent_unknown": True}, ["parent"]),
        ({"mentioned_actor_ids": ("m1",)}, ["mentions"]),
        ({"text": "lain", "actor": "a-baru"}, ["text", "author"]),
    ],
)
def test_changed_fields_are_reported_per_attribute(target, user, run1, change, expected) -> None:
    ingest(run1, [obs(run1, "r1")], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", **change)], displayed=1)
    reconcile_run(run2)
    assert recon_rows(run2)["r1"].changed_fields == expected


def test_quoted_and_reposted_target_changes_are_detected(target, user, run1) -> None:
    q = dict(kind=SourceObjectType.QUOTE, parent=None)
    ingest(run1, [obs(run1, "q1", quoted_post_id="orig-1", **q)], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "q1", quoted_post_id="orig-2", **q)], displayed=1)
    reconcile_run(run2)
    assert recon_rows(run2)["q1"].changed_fields == ["quoted"]


@pytest.mark.parametrize(
    "edited",
    [
        "isi  dengan   spasi ganda",
        "isi dengan spasi ganda\r\n",
        " isi dengan spasi ganda ",
        "isi​ dengan spasi ganda",
    ],
)
def test_render_only_differences_are_not_modifications(target, user, run1, edited) -> None:
    ingest(run1, [obs(run1, "r1", text="isi dengan spasi ganda")], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", text=edited)], displayed=1)
    reconcile_run(run2)
    assert recon_rows(run2)["r1"].status == "UNCHANGED"


def test_none_text_versus_empty_text_is_a_modification(target, user, run1) -> None:
    ingest(run1, [obs(run1, "r1", text=None)], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", text="")], displayed=1)
    reconcile_run(run2)
    assert recon_rows(run2)["r1"].changed_fields == ["text"]


def test_handle_and_display_name_changes_alone_are_not_modifications(target, user, run1) -> None:
    ingest(run1, [obs(run1, "r1", actor_handle="@lama", actor_display_name="Lama")], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", actor_handle="@baru", actor_display_name="Baru")], displayed=1)
    reconcile_run(run2)
    assert recon_rows(run2)["r1"].status == "UNCHANGED"


def test_published_at_rules(target, user, run1) -> None:
    ingest(
        run1,
        [obs(run1, "known", ago=60), obs(run1, "none", published_at=None),
         obs(run1, "later-none", ago=60), obs(run1, "same", ago=60)],
        displayed=4,
    )
    run2 = new_run(target, user)
    ingest(
        run2,
        [obs(run2, "known", ago=999),  # keduanya diketahui dan berbeda -> MODIFIED
         obs(run2, "none", ago=30),  # None -> nilai: informasi baru, bukan perubahan
         obs(run2, "later-none", published_at=None),  # nilai -> None: tidak dihitung
         obs(run2, "same", ago=60)],
        displayed=4,
    )
    reconcile_run(run2)
    rows = recon_rows(run2)
    assert (rows["known"].status, rows["known"].changed_fields) == ("MODIFIED", ["published_at"])
    assert rows["none"].status == "UNCHANGED"
    assert rows["later-none"].status == "UNCHANGED"
    assert rows["same"].status == "UNCHANGED"


# =============================== pembanding = observasi terbaru ===============================


def test_comparison_uses_the_latest_earlier_observation(target, user, run1) -> None:
    ingest(run1, [obs(run1, "r1", text="A")], displayed=1)
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "r1", text="B")], displayed=1)
    reconcile_run(run2)
    run3 = new_run(target, user)
    ingest(run3, [obs(run3, "r1", text="B")], displayed=1)
    reconcile_run(run3)
    run4 = new_run(target, user)
    ingest(run4, [obs(run4, "r1", text="A")], displayed=1)
    reconcile_run(run4)

    assert recon_rows(run3)["r1"].status == "UNCHANGED"  # dibanding run2 (B), bukan run1 (A)
    assert recon_rows(run3)["r1"].previous_observation.run_id == run2.pk
    assert recon_rows(run4)["r1"].status == "MODIFIED"  # A vs B terbaru


def test_object_that_reappears_is_compared_not_new(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2"]), displayed=2)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1)
    assert statuses_after(run2)["r2"] == "NOT_OBSERVED"
    run3 = new_run(target, user)
    ingest(run3, replies(run3, ["r1", "r2"]), displayed=2)
    reconcile_run(run3)
    row = recon_rows(run3)["r2"]
    assert row.status == "UNCHANGED"  # dibanding run1; bukan NEW
    assert row.previous_observation.run_id == run1.pk


def test_run_gaps_are_handled_when_old_runs_have_no_observations(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    failed = make_result(
        run2, [], O.FAILED, limitations=[Limitation(LimitationCode.PARSE_FAILED, "x")], complete=None
    )
    assert ingest_result(run2, failed).ok
    run3 = new_run(target, user)
    ingest(run3, replies(run3, ["r1"]), displayed=1)
    result = reconcile_run(run3)
    assert counts_of(result) == {"UNCHANGED": 1}
    assert result.baseline_runs == [1, 2]


# =============================== CONFIRMED_UNAVAILABLE ===============================


def test_confirmed_unavailable_needs_explicit_adapter_statement(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2", "r3"]), displayed=3)
    run2 = new_run(target, user)
    ingest(
        run2, replies(run2, ["r1"]), displayed=1,
        confirmed=[("r2", "halaman objek mengembalikan 'komentar dihapus'")],
    )
    reconcile_run(run2)
    rows = recon_rows(run2)
    assert rows["r2"].status == "CONFIRMED_UNAVAILABLE"
    assert rows["r2"].evidence == "halaman objek mengembalikan 'komentar dihapus'"
    assert rows["r3"].status == "NOT_OBSERVED"  # absen dari daftar saja
    assert rows["r2"].current_observation_id is None


def test_confirmed_unavailable_for_never_seen_object_is_reported_not_stored(
    target, user, run1
) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1, confirmed=[("tak-pernah-terlihat", "404")])
    result = reconcile_run(run2)
    assert result.unmatched_confirmed_unavailable == ["tak-pernah-terlihat"]
    assert "tak-pernah-terlihat" not in statuses(run2)


def test_a_partial_result_cannot_claim_unavailability(run1) -> None:
    from collection.contracts import ContractViolation

    with pytest.raises(ContractViolation, match="COMPLETED"):
        from collection_helpers import make_result as mk

        mk(run1, [], O.PARTIAL, confirmed=[("r2", "x")], complete=False,
           limitations=[Limitation(LimitationCode.PAGINATION_INCOMPLETE, "x")])


# =============================== dilewati dan diblokir ===============================


@pytest.mark.parametrize(
    ("outcome", "code"),
    [(O.ACCESS_RESTRICTED, LimitationCode.ACCESS_RESTRICTED), (O.FAILED, LimitationCode.PARSE_FAILED),
     (O.UNSUPPORTED, LimitationCode.UNSUPPORTED)],
)
def test_runs_without_observations_are_skipped_and_do_not_flag_everything(
    target, user, run1, outcome, code
) -> None:
    ingest(run1, replies(run1, ["r1", "r2"]), displayed=2)
    run2 = new_run(target, user)
    assert ingest_result(
        run2, make_result(run2, [], outcome, limitations=[Limitation(code, "x")], complete=None)
    ).ok
    result = reconcile_run(run2)
    assert result.state == "SKIPPED" and outcome.value in result.reason
    assert ObservationReconciliation.objects.filter(run=run2).count() == 0  # tidak ada NOT_OBSERVED palsu


def test_interrupted_ingestion_blocks_reconciliation_until_completed(monkeypatch, target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2"]), displayed=2)
    run2 = new_run(target, user)
    result2 = make_result(run2, replies(run2, ["r1", "r2"]), displayed=2)
    monkeypatch.setattr(ingestion, "_chunks", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        ingest_result(run2, result2)
    monkeypatch.undo()

    blocked = reconcile_run(run2)
    assert blocked.state == "BLOCKED" and "belum selesai" in blocked.reason
    assert ObservationReconciliation.objects.filter(run=run2).count() == 0

    assert ingest_result(run2, result2).ok  # ingestion dilanjutkan
    done = reconcile_run(run2)  # BLOCKED bukan status akhir
    assert done.done and counts_of(done) == {"UNCHANGED": 2}


def test_failed_batches_block_reconciliation_so_missing_rows_are_not_misread(
    monkeypatch, target, user, run1
) -> None:
    ingest(run1, replies(run1, [f"r{i}" for i in range(6)]), displayed=6)
    run2 = new_run(target, user)
    real = ingestion._write_relations
    state = {"n": 0}

    def flaky(*args, **kwargs):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("gangguan")
        return real(*args, **kwargs)

    monkeypatch.setattr(ingestion, "_write_relations", flaky)
    report = ingest_result(run2, make_result(run2, replies(run2, [f"r{i}" for i in range(6)]), displayed=6),
                           batch_size=2)
    monkeypatch.undo()
    assert not report.ok
    blocked = reconcile_run(run2)
    assert blocked.state == "BLOCKED" and "batch" in blocked.reason
    # Tanpa pemblokiran, 2 objek akan salah ditandai NOT_OBSERVED.
    assert ObservationReconciliation.objects.filter(run=run2).count() == 0


def test_conflicts_block_reconciliation(target, user, run1) -> None:
    ingest(run1, [obs(run1, "r1", text="asli")], displayed=1)
    bad = ingest_result(run1, make_result(run1, [obs(run1, "r1", text="beda")], displayed=1))
    assert not bad.ok
    assert reconcile_run(run1).state == "BLOCKED"


def test_unfinished_baseline_run_blocks_later_reconciliation(monkeypatch, target, user, run1) -> None:
    run2 = new_run(target, user)
    monkeypatch.setattr(ingestion, "_chunks", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        ingest_result(run2, make_result(run2, replies(run2, ["r1"]), displayed=1))
    monkeypatch.undo()
    run3 = new_run(target, user)
    ingest(run3, replies(run3, ["r1"]), displayed=1)
    blocked = reconcile_run(run3)
    assert blocked.state == "BLOCKED" and "run pembanding 2" in blocked.reason


def test_never_executed_pending_run_does_not_block(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    new_run(target, user)  # run 2: PENDING, tidak pernah dijalankan
    run3 = new_run(target, user)
    ingest(run3, replies(run3, ["r1"]), displayed=1)
    assert reconcile_run(run3).done


def test_running_but_not_ingested_baseline_run_blocks(target, user, run1) -> None:
    run2 = new_run(target, user)
    InspectionRun.objects.filter(pk=run2.pk).update(status=RunStatus.RUNNING)
    run3 = new_run(target, user)
    ingest(run3, replies(run3, ["r1"]), displayed=1)
    assert reconcile_run(run3).state == "BLOCKED"


def test_run_never_ingested_is_blocked(run1) -> None:
    assert reconcile_run(run1).state == "BLOCKED"


def test_artifact_notice_does_not_block(target, user, run1) -> None:
    shot = ArtifactCapture(ArtifactKind.SCREENSHOT, "a.png", b"x", "image/png")
    report = ingest_result(run1, make_result(run1, replies(run1, ["r1"]), displayed=1, artifacts=[shot]))
    assert "ARTIFACTS_NOT_PERSISTED" in report.problem_codes()
    assert reconcile_run(run1).done  # artefak bukan soal kelengkapan observasi


# =============================== idempoten, kandidat, cakupan ===============================


def test_reconcile_is_idempotent(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1", "r2"]), displayed=2)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1", "r3"]), displayed=2)
    first = reconcile_run(run2)
    rows_before = list(ObservationReconciliation.objects.filter(run=run2).values_list("id", flat=True))
    second = reconcile_run(run2)
    assert first == second
    assert list(ObservationReconciliation.objects.filter(run=run2).values_list("id", flat=True)) == rows_before


def test_candidates_without_id_are_not_reconciled_only_counted(target, user, run1) -> None:
    def candidate(run):
        return obs(run, None, actor=None, text="Bagus!", actor_handle="@anon",
                   identity_needs_verification=True)

    ingest(run1, [candidate(run1), obs(run1, "r1")], displayed=2)
    run2 = new_run(target, user)
    ingest(run2, [candidate(run2), obs(run2, "r1")], displayed=2)
    result = reconcile_run(run2)
    assert counts_of(result) == {"UNCHANGED": 1}  # kandidat lama tidak membanjiri NOT_OBSERVED
    assert result.unmatched_candidates_current == 1
    assert result.unmatched_candidates_baseline == 1


def test_scope_is_the_target_not_the_platform(inv, user, target, run1) -> None:
    other = register(inv, user, Platform.X, "https://x.com/v/status/2")
    run_other = new_run(other, user)
    ingest(run_other, replies(run_other, ["shared"]), displayed=1)
    ingest(run1, replies(run1, ["shared"]), displayed=1)
    result = reconcile_run(run1)
    assert counts_of(result) == {"NEW": 1}  # baru bagi riwayat TARGET ini
    assert result.baseline_runs == []
    assert Post.objects.filter(external_post_id="shared").count() == 1  # identitas tidak digandakan


def test_other_targets_runs_never_count_as_baseline(inv, user, target, run1) -> None:
    """`sequence` dihitung per target, jadi kebocoran lintas target hanya terlihat bila run yang
    direkonsiliasi bernomor LEBIH BESAR daripada run target lain."""
    other = register(inv, user, Platform.X, "https://x.com/v/status/2")
    ingest(run1, replies(run1, ["a", "shared"]), displayed=2)  # target A, run 1
    run_other1 = new_run(other, user)
    ingest(run_other1, replies(run_other1, ["b-lama"]), displayed=1)  # target B, run 1
    run_other2 = new_run(other, user)  # target B, run 2: sequence 2 > sequence 1 milik target A
    ingest(run_other2, replies(run_other2, ["b-lama", "shared"]), displayed=2)
    result = reconcile_run(run_other2)

    assert result.baseline_runs == [1]  # hanya run 1 milik target B
    assert statuses(run_other2) == {"shared": "NEW", "b-lama": "UNCHANGED"}
    assert "a" not in statuses(run_other2)  # milik target A: tidak jadi NOT_OBSERVED


def test_legacy_observations_without_hash_fall_back_to_raw_comparison(monkeypatch, target, user, run1) -> None:
    monkeypatch.setattr(ingestion, "observation_content_hash", lambda o: "")
    monkeypatch.setattr(ingestion, "CONTENT_HASH_VERSION", 0)
    ingest(run1, [obs(run1, "same", text="isi"), obs(run1, "edit", text="awal")], displayed=2)
    monkeypatch.undo()
    run2 = new_run(target, user)
    ingest(run2, [obs(run2, "same", text="isi  "), obs(run2, "edit", text="diubah")], displayed=2)
    reconcile_run(run2)
    rows = recon_rows(run2)
    assert rows["same"].status == "UNCHANGED"  # hash beda versi dihitung ulang dari data mentah
    assert (rows["edit"].status, rows["edit"].changed_fields) == ("MODIFIED", ["text"])


# =============================== integritas di database ===============================


def _row(**kw):
    return ObservationReconciliation(**kw)


def test_reconciliation_rows_are_append_only(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    reconcile_run(run1)
    row = ObservationReconciliation.objects.get()
    from collection.errors import AppendOnlyViolation

    with pytest.raises(AppendOnlyViolation):
        row.save()
    with pytest.raises(AppendOnlyViolation):
        row.delete()
    for action in (
        lambda: ObservationReconciliation.objects.filter(pk=row.pk).update(status="MODIFIED"),
        lambda: ObservationReconciliation.objects.filter(pk=row.pk)._raw_delete(
            ObservationReconciliation.objects.db),
    ):
        with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
            action()


def test_database_rejects_inconsistent_reconciliation_rows(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1)
    cur = PostObservation.objects.get(run=run2)
    prev = PostObservation.objects.get(run=run1)
    post = cur.post

    def attempt(**kw):
        with pytest.raises(IntegrityError), transaction.atomic():
            ObservationReconciliation.objects.create(run=run2, post=post, **kw)

    attempt(status="NEW", previous_observation=prev, current_observation=cur)  # NEW tak punya pembanding
    attempt(status="UNCHANGED", previous_observation=None, current_observation=cur)
    attempt(status="NOT_OBSERVED", previous_observation=prev, current_observation=cur)
    attempt(status="NOT_OBSERVED", previous_observation=None, current_observation=None)
    attempt(status="CONFIRMED_UNAVAILABLE", previous_observation=prev, evidence="")  # tanpa bukti
    attempt(status="DELETED", previous_observation=prev)  # status di luar PRD


def test_database_rejects_comparison_from_wrong_run_or_target(inv, user, target, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, ["r1"]), displayed=1)
    cur = PostObservation.objects.get(run=run2)
    prev = PostObservation.objects.get(run=run1)
    post = cur.post

    def reject(match, **kw):
        with pytest.raises(DatabaseError, match=match), transaction.atomic():
            ObservationReconciliation.objects.create(**kw)

    # Pembanding dari run yang sama atau yang lebih baru tidak sah.
    reject("run sebelumnya", run=run2, post=post, status="UNCHANGED",
           previous_observation=cur, current_observation=cur)
    reject("run sebelumnya", run=run1, post=post, status="UNCHANGED",
           previous_observation=cur, current_observation=prev)
    # Observasi 'saat ini' harus milik run yang direkonsiliasi.
    reject("observasi saat ini", run=run2, post=post, status="UNCHANGED",
           previous_observation=prev, current_observation=prev)
    # Pembanding dari target lain tidak sah.
    other = register(inv, user, Platform.X, "https://x.com/v/status/2")
    run_o = new_run(other, user)
    ingest(run_o, replies(run_o, ["r1"]), displayed=1)
    other_obs = PostObservation.objects.get(run=run_o)
    reject("target yang sama", run=run2, post=post, status="UNCHANGED",
           previous_observation=other_obs, current_observation=cur)


def test_one_reconciliation_per_post_per_run(target, user, run1) -> None:
    ingest(run1, replies(run1, ["r1"]), displayed=1)
    reconcile_run(run1)
    row = ObservationReconciliation.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        ObservationReconciliation.objects.create(
            run=run1, post=row.post, status="NEW", current_observation=row.current_observation
        )


# =============================== skala dan balapan ===============================


def test_query_count_is_independent_of_the_number_of_objects(inv, user) -> None:
    """Tiap kasus memakai TARGET sendiri sehingga jumlah baris rekonsiliasi benar-benar sama dengan
    jumlah objek (kasus kecil tidak diam-diam menghasilkan ratusan baris NOT_OBSERVED)."""

    def queries_for(n_objects: int, edited: bool, tag: str) -> int:
        tgt = register(inv, user, Platform.X, f"https://x.com/u/status/{tag}")
        first = new_run(tgt, user)
        ids = [f"{tag}-{i}" for i in range(n_objects)]
        ingest(first, replies(first, ids), displayed=n_objects)
        second = new_run(tgt, user)
        items = [
            obs(second, i, actor=f"actor-{n % 5}", text=("diubah " + i) if edited else f"balasan {i}")
            for n, i in enumerate(ids)
        ]
        ingest(second, items, displayed=n_objects)
        with CaptureQueriesContext(connection) as ctx:
            assert reconcile_run(second).done
        assert ObservationReconciliation.objects.filter(run=second).count() == n_objects
        return len(ctx)

    small, large = queries_for(20, False, "11"), queries_for(400, False, "12")
    small_mod, large_mod = queries_for(20, True, "13"), queries_for(400, True, "14")
    assert large <= small + 10, (small, large)  # tanpa N+1 pada jalur UNCHANGED
    assert large_mod <= small_mod + 10, (small_mod, large_mod)  # dan pada jalur MODIFIED


def test_large_reconciliation_is_correct_and_fast(target, user, run1) -> None:
    n = 3000
    ids = [f"big-{i}" for i in range(n)]
    ingest(run1, replies(run1, ids), displayed=n)
    run2 = new_run(target, user)
    edited = {ids[0], ids[1]}
    items = [obs(run2, i, actor=f"actor-{k % 5}", text="diubah" if i in edited else f"balasan {i}")
             for k, i in enumerate(ids[:2900])] + replies(run2, [f"baru-{i}" for i in range(50)])
    ingest(run2, items, displayed=2950)
    started = time.perf_counter()
    result = reconcile_run(run2)
    elapsed = time.perf_counter() - started
    assert counts_of(result) == {"NEW": 50, "UNCHANGED": 2898, "MODIFIED": 2, "NOT_OBSERVED": 100}
    assert elapsed < 60, f"rekonsiliasi {n} objek memakan {elapsed:.1f}s"


@pytest.mark.django_db(transaction=True)
def test_concurrent_reconciliation_of_one_run_produces_one_consistent_result(target, user) -> None:
    run1 = new_run(target, user)
    ingest(run1, replies(run1, [f"r{i}" for i in range(40)]), displayed=40)
    run2 = new_run(target, user)
    ingest(run2, replies(run2, [f"r{i}" for i in range(20, 60)]), displayed=40)
    results, errors = [], []
    barrier = threading.Barrier(3)

    def worker() -> None:
        try:
            barrier.wait()
            results.append(reconcile_run(InspectionRun.objects.get(pk=run2.pk)))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not errors, errors
    assert len(results) == 3 and all(r == results[0] for r in results)
    assert counts_of(results[0]) == {"NEW": 20, "UNCHANGED": 20, "NOT_OBSERVED": 20}
    assert ObservationReconciliation.objects.filter(run=run2).count() == 60
