"""WP-1.9a: pesan ramah dan keadaan data (FR-095, NFR-08). Murni, tanpa database."""

import pytest
from api import messages as m
from api.messages import run_messages
from api.runs import (
    ACCESS_FAILED,
    HAS_DATA,
    IN_PROGRESS,
    NEEDS_REVIEW,
    NO_DATA,
    NOT_INSPECTED,
    PARTIAL,
    data_state,
)
from collection.contracts import LimitationCode
from collection.models import InspectionRun, RunStatus

S = RunStatus


def run(status, *, limitations=(), coverage=None, **kw) -> InspectionRun:
    return InspectionRun(status=status, limitations=list(limitations), coverage=coverage, **kw)


def lim(code, message="teks bebas adapter"):
    return {"code": code.value, "message": message, "capability": None}


def codes(r) -> list[str]:
    return [x.code for x in run_messages(r)]


# --- kelengkapan ------------------------------------------------------------------------------


def test_every_limitation_code_has_a_friendly_message() -> None:
    assert set(m.LIMITATION_MESSAGES) == set(LimitationCode)


def test_all_message_codes_are_unique_and_levels_valid() -> None:
    every = [
        *m.LIMITATION_MESSAGES.values(), *m.REVIEW_REASON_MESSAGES.values(),
        *m.STATUS_MESSAGES.values(), *m.RECONCILIATION_MESSAGES.values(),
        m.CONTEXT_INSUFFICIENT, m.NO_REPLIES, m.RECONCILIATION_PENDING, m.INGESTION_INTERRUPTED,
        m.ARTIFACTS_REJECTED, m.COUNT_MISMATCH, m._FAILURE_FALLBACK, m._REVIEW_FALLBACK,
    ]
    assert len({x.code for x in every}) == len(every)
    assert {x.level for x in every} <= {m.INFO, m.WARNING, m.ERROR}
    for x in every:
        assert x.title.strip() and x.detail.strip()


SAYS_NOTHING_CAN_BE_CONCLUDED = {
    LimitationCode.ACCESS_RESTRICTED: "bukan berarti tidak ada balasan",
    LimitationCode.PARSE_FAILED: "bukan berarti tidak ada balasan",
    LimitationCode.NETWORK_ERROR: "bukan berarti tidak ada balasan",
    LimitationCode.TIMEOUT: "tidak lengkap",
    LimitationCode.ADAPTER_ERROR: "tidak ada kesimpulan",
    LimitationCode.TARGET_UNAVAILABLE: "tidak dapat membedakannya",
}


@pytest.mark.parametrize("code", sorted(SAYS_NOTHING_CAN_BE_CONCLUDED, key=str))
def test_failure_messages_never_imply_that_there_were_no_replies(code) -> None:
    detail = m.LIMITATION_MESSAGES[code].detail.lower()
    assert SAYS_NOTHING_CAN_BE_CONCLUDED[code] in detail
    assert m.LIMITATION_MESSAGES[code].level == m.ERROR


# --- pesan per status -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [(S.PENDING, "run_pending"), (S.RUNNING, "run_running")],
)
def test_waiting_statuses(status, expected) -> None:
    assert codes(run(status)) == [expected]


def test_completed_with_zero_replies_says_nothing_was_observed() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 0, "platform_displayed_count": 0},
            reconciliation={"state": "DONE"})
    assert codes(r) == ["run_completed", "no_replies_observed"]


def test_completed_with_matching_counts_has_no_mismatch_note() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 4, "platform_displayed_count": 4},
            reconciliation={"state": "DONE"})
    assert codes(r) == ["run_completed"]


def test_displayed_and_observed_counts_may_differ_and_are_explained() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 3, "platform_displayed_count": 5},
            reconciliation={"state": "DONE"})
    assert "count_mismatch" in codes(r)


def test_unknown_displayed_count_is_not_a_mismatch() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 3, "platform_displayed_count": None},
            reconciliation={"state": "DONE"})
    assert "count_mismatch" not in codes(r)


def test_partial_explains_and_adds_the_specific_limitation() -> None:
    r = run(S.PARTIAL, limitations=[lim(LimitationCode.PAGINATION_INCOMPLETE)],
            coverage={"observed_reply_count": 3}, reconciliation={"state": "DONE"})
    assert codes(r)[:2] == ["run_partial", "pagination_incomplete"]


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (S.ACCESS_RESTRICTED, LimitationCode.ACCESS_RESTRICTED, "access_restricted"),
        (S.FAILED, LimitationCode.PARSE_FAILED, "parse_failed"),
        (S.FAILED, LimitationCode.TIMEOUT, "timeout"),
        (S.FAILED, LimitationCode.TARGET_UNAVAILABLE, "target_unavailable"),
        (S.UNSUPPORTED, LimitationCode.UNSUPPORTED, "unsupported"),
    ],
)
def test_failures_use_the_specific_limitation_message_only(status, code, expected) -> None:
    assert codes(run(status, limitations=[lim(code)])) == [expected]


def test_failure_without_any_limitation_falls_back_to_a_generic_message() -> None:
    assert codes(run(S.FAILED)) == ["run_failed_unspecified"]


def test_duplicate_limitation_codes_are_listed_once() -> None:
    r = run(S.FAILED, limitations=[lim(LimitationCode.TIMEOUT)] * 3)
    assert codes(r) == ["timeout"]


def test_unknown_limitation_codes_are_ignored_not_crashed() -> None:
    r = run(S.FAILED, limitations=[{"code": "KODE_BARU", "message": "x", "capability": None}])
    assert codes(r) == ["run_failed_unspecified"]


def test_review_required_lists_known_reasons_and_a_fallback_for_unknown_ones() -> None:
    r = run(S.REVIEW_REQUIRED, review={"reasons": ["ingestion_failed_batches", "baru_belum_dikenal"],
                                       "outcome": "COMPLETED", "acknowledged": None},
            reconciliation={"state": "BLOCKED"})
    got = codes(r)
    assert got[0] == "run_review_required"
    assert "review_ingestion_failed_batches" in got and "review_other" in got
    assert "reconciliation_blocked" in got


def test_reconciliation_pending_only_for_observing_final_runs() -> None:
    assert "reconciliation_pending" in codes(run(S.COMPLETED, coverage={"observed_reply_count": 1}))
    assert "reconciliation_pending" not in codes(
        run(S.FAILED, limitations=[lim(LimitationCode.TIMEOUT)]))
    assert "reconciliation_pending" not in codes(run(S.RUNNING))


def test_reconciliation_error_is_visible() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 1},
            reconciliation={"state": "ERROR", "reason": "ValueError"})
    assert "reconciliation_error" in codes(r)


def test_interrupted_ingestion_is_flagged_only_after_the_run_is_final() -> None:
    interrupted = {"state": "IN_PROGRESS"}
    assert "ingestion_interrupted" in codes(run(S.PARTIAL, ingestion=interrupted,
                                                coverage={"observed_reply_count": 1}))
    assert "ingestion_interrupted" not in codes(run(S.RUNNING, ingestion=interrupted))


def test_rejected_artifacts_are_reported_without_naming_them() -> None:
    r = run(S.COMPLETED, coverage={"observed_reply_count": 1}, reconciliation={"state": "DONE"},
            preservation={"state": "FINISHED", "report": {"rejected": [{"filename": "rahasia.html"}]}})
    msgs = run_messages(r)
    assert "artifacts_rejected" in [x.code for x in msgs]
    assert "rahasia.html" not in str([x.to_dict() for x in msgs])


def test_free_text_from_adapters_never_reaches_friendly_messages() -> None:
    secret = "ISI-RAHASIA-TOKEN-XYZ"
    r = run(S.FAILED, limitations=[lim(LimitationCode.ADAPTER_ERROR, secret)],
            review={"reasons": [secret], "outcome": "FAILED", "acknowledged": None})
    assert secret not in str([x.to_dict() for x in run_messages(r)])


def test_messages_are_ordered_most_important_first() -> None:
    r = run(S.PARTIAL, limitations=[lim(LimitationCode.PAGINATION_INCOMPLETE)],
            coverage={"observed_reply_count": 2}, reconciliation={"state": "DONE"})
    assert run_messages(r)[0].code == "run_partial"


# --- keadaan data (NFR-08) --------------------------------------------------------------------


def test_data_state_matrix() -> None:
    assert data_state(None) == NOT_INSPECTED
    assert data_state(run(S.PENDING)) == IN_PROGRESS and data_state(run(S.RUNNING)) == IN_PROGRESS
    for failed in (S.ACCESS_RESTRICTED, S.FAILED, S.UNSUPPORTED):
        assert data_state(run(failed)) == ACCESS_FAILED
    assert data_state(run(S.REVIEW_REQUIRED)) == NEEDS_REVIEW
    assert data_state(run(S.PARTIAL, coverage={"observed_reply_count": 0})) == PARTIAL
    assert data_state(run(S.COMPLETED, coverage={"observed_reply_count": 3})) == HAS_DATA
    assert data_state(run(S.COMPLETED, coverage={"observed_reply_count": 0})) == NO_DATA


def test_unknown_observed_count_is_never_called_no_data() -> None:
    assert data_state(run(S.COMPLETED, coverage=None)) == HAS_DATA
    assert data_state(run(S.COMPLETED, coverage={})) == HAS_DATA


def test_failed_access_is_a_different_state_from_no_data() -> None:
    assert data_state(run(S.FAILED)) != data_state(run(S.COMPLETED, coverage={"observed_reply_count": 0}))
    assert data_state(None) not in (ACCESS_FAILED, NO_DATA)
