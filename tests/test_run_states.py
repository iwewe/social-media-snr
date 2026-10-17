"""WP-1.6: tabel transisi status run; Python dan database harus sepakat untuk semua pasangan."""

from itertools import product

import pytest
from collection_helpers import new_run, register
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction

from collection.models import InspectionRun, RunStatus
from collection.orchestrator.states import (
    FINAL_STATUSES,
    OUTCOME_STATUSES,
    TRANSITIONS,
    can_transition,
)
from investigations import services as inv_services
from investigations.enums import Platform

pytestmark = pytest.mark.django_db

ALL = [s.value for s in RunStatus]
S = RunStatus


class _Rollback(Exception):
    pass


@pytest.fixture
def user() -> User:
    return User.objects.create_user("analis", password="x")


@pytest.fixture
def target(user):
    inv = inv_services.create_investigation(user=user, name="A")
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


def run_in(status: str, target, user) -> InspectionRun:
    """Run pada `status`, dicapai lewat jalur transisi yang sah (trigger menolak jalan pintas)."""
    run = new_run(target, user)
    if status == S.PENDING:
        return run
    InspectionRun.objects.filter(pk=run.pk).update(status=S.RUNNING)
    if status != S.RUNNING:
        InspectionRun.objects.filter(pk=run.pk).update(status=status)
    run.refresh_from_db()
    return run


# --- tabel ------------------------------------------------------------------------------------


def test_every_status_has_an_entry_or_is_a_sink() -> None:
    assert set(TRANSITIONS) <= set(RunStatus)
    assert S.PENDING in TRANSITIONS and S.RUNNING in TRANSITIONS


def test_nothing_transitions_back_into_pending_or_running_after_start() -> None:
    for source, targets in TRANSITIONS.items():
        assert S.PENDING not in targets, source
        if source != S.PENDING:
            assert S.RUNNING not in targets, source


def test_final_outcomes_only_move_to_review_required() -> None:
    for status in OUTCOME_STATUSES:
        assert TRANSITIONS[status] == {S.REVIEW_REQUIRED}


def test_review_required_returns_only_to_a_final_outcome() -> None:
    assert TRANSITIONS[S.REVIEW_REQUIRED] == OUTCOME_STATUSES
    assert FINAL_STATUSES == OUTCOME_STATUSES | {S.REVIEW_REQUIRED}


def test_same_status_is_not_a_transition_but_is_allowed() -> None:
    for status in ALL:
        assert can_transition(status, status)


def test_pending_cannot_jump_to_a_successful_outcome() -> None:
    for outcome in (S.COMPLETED, S.PARTIAL, S.ACCESS_RESTRICTED, S.REVIEW_REQUIRED):
        assert not can_transition(S.PENDING, outcome)


# --- Python == database untuk semua 8 x 8 pasangan ----------------------------------------------


@pytest.mark.parametrize("source", ALL)
def test_database_guard_matches_the_python_table_for_every_target_status(
    source, target, user
) -> None:
    run = run_in(source, target, user)
    assert run.status == source
    for dest in ALL:
        try:
            with transaction.atomic():
                InspectionRun.objects.filter(pk=run.pk).update(status=dest)
                raise _Rollback  # batalkan perubahan: yang diuji hanyalah apakah DB mengizinkan
        except _Rollback:
            allowed = True
        except DatabaseError as exc:
            assert "tidak diizinkan" in str(exc), exc
            allowed = False
        assert allowed == can_transition(source, dest), f"{source} -> {dest}"
    run.refresh_from_db()
    assert run.status == source  # tidak ada perubahan yang bocor


def test_all_64_pairs_were_exercised() -> None:
    assert len(list(product(ALL, ALL))) == 64


# --- imutabilitas data hasil setelah final ----------------------------------------------------

LOCKED = [
    ("coverage", {"outcome": "diubah"}),
    ("limitations", [{"code": "TIMEOUT", "message": "x", "capability": None}]),
    ("source_method", "official_api"),
    ("collector_name", "lain"),
    ("collector_version", "9"),
]
UNLOCKED = [
    ("ingestion", {"state": "FINISHED"}),
    ("reconciliation", {"state": "DONE"}),
    ("preservation", {"state": "FINISHED"}),
    ("review", {"reasons": ["x"], "outcome": "COMPLETED", "acknowledged": None}),
    ("claimed_by", "pekerja-2"),
]


@pytest.mark.parametrize("status", sorted(FINAL_STATUSES))
def test_result_data_is_immutable_once_the_run_is_final(status, target, user) -> None:
    from django.utils import timezone

    run = run_in(status, target, user)
    for column, value in LOCKED:
        with pytest.raises(DatabaseError, match="sudah final"), transaction.atomic():
            InspectionRun.objects.filter(pk=run.pk).update(**{column: value})
    with pytest.raises(DatabaseError, match="sudah final"), transaction.atomic():
        InspectionRun.objects.filter(pk=run.pk).update(finished_at=timezone.now())
    with pytest.raises(DatabaseError, match="sudah final"), transaction.atomic():
        InspectionRun.objects.filter(pk=run.pk).update(started_at=timezone.now())


@pytest.mark.parametrize("status", sorted(FINAL_STATUSES))
def test_follow_up_columns_remain_writable_after_final(status, target, user) -> None:
    run = run_in(status, target, user)
    for column, value in UNLOCKED:
        InspectionRun.objects.filter(pk=run.pk).update(**{column: value})
    run.refresh_from_db()
    assert run.reconciliation == {"state": "DONE"} and run.claimed_by == "pekerja-2"


@pytest.mark.parametrize("status", sorted(FINAL_STATUSES))
def test_rewriting_a_locked_column_with_the_same_value_is_allowed(status, target, user) -> None:
    run = run_in(status, target, user)
    InspectionRun.objects.filter(pk=run.pk).update(
        coverage=run.coverage, limitations=run.limitations
    )


@pytest.mark.parametrize("status", [S.PENDING, S.RUNNING])
def test_result_columns_are_writable_before_the_run_is_final(status, target, user) -> None:
    run = run_in(status, target, user)
    for column, value in LOCKED:
        InspectionRun.objects.filter(pk=run.pk).update(**{column: value})


def test_final_transition_may_write_result_data_in_the_same_update(target, user) -> None:
    from django.utils import timezone

    run = run_in(S.RUNNING, target, user)
    InspectionRun.objects.filter(pk=run.pk).update(
        status=S.FAILED,
        finished_at=timezone.now(),
        coverage={"outcome": "FAILED"},
        limitations=[{"code": "TIMEOUT", "message": "x", "capability": None}],
    )
    run.refresh_from_db()
    assert run.status == S.FAILED and run.coverage == {"outcome": "FAILED"}
