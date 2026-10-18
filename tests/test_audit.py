"""WP-2.8: AuditEvent untuk perubahan konteks, klasifikasi, tinjauan, dan temuan (AT-16; FR-005).

Memakai dunia uji WP-2.7a (dibangun lewat jalur layanan yang sama dengan produksi) sehingga audit
yang diperiksa adalah yang ditulis oleh kode nyata, bukan data buatan.
"""

import pytest
from audit.models import AuditAction, AuditEvent, SubjectType
from django.db import connection, transaction
from django.db.utils import InternalError, ProgrammingError
from investigations import services as inv_services
from investigations.models import Issue
from test_api_analysis import _finding_body, get_json, post, world  # noqa: F401

pytestmark = pytest.mark.django_db


def events(world, **filters):
    return list(AuditEvent.objects.filter(investigation=world.inv, **filters).order_by("id"))


def test_building_context_through_services_is_audited_with_actor_and_state(world) -> None:
    issue_events = events(world, action=AuditAction.ISSUE_CONTEXT, subject_id=world.issue.pk)
    assert len(issue_events) == 1
    e = issue_events[0]
    assert e.subject_type == SubjectType.ISSUE and e.actor == world.owner
    assert e.before is None and e.after["version"] == 1
    target_events = events(world, action=AuditAction.TARGET_CONTEXT, subject_id=world.target.pk)
    assert len(target_events) == 1
    assert target_events[0].before is None
    assert target_events[0].after["stances"] == {world.prop.label: "CONTRA"}


def test_revising_a_context_records_before_and_after(world) -> None:
    inv_services.revise_issue_context(
        issue=Issue.objects.get(pk=world.issue.pk), user=world.member, definition="Definisi baru."
    )
    last = events(world, action=AuditAction.ISSUE_CONTEXT, subject_id=world.issue.pk)[-1]
    assert last.actor == world.member
    assert last.before["version"] == 1 and last.after["version"] == 2
    assert last.after["definition"] == "Definisi baru."
    res = post(
        world.clients["member"],
        f"/api/targets/{world.target.pk}/context-versions/",
        {"note": "Catatan baru untuk target."},
    )
    assert res.status_code == 201, res.content[:200]
    t = events(world, action=AuditAction.TARGET_CONTEXT, subject_id=world.target.pk)[-1]
    assert t.before["version"] == 1 and t.after["version"] == 2
    assert t.after["note"] == "Catatan baru untuk target."
    assert t.after["stances"] == {world.prop.label: "CONTRA"}  # stance dibawa ke versi baru


def test_AT16_classification_review_is_audited_with_old_new_values_and_reason(world) -> None:
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    row = next(r for r in rows if r["needs_human_review"])
    before_count = len(events(world, action=AuditAction.CLASSIFICATION_REVIEW))
    res = post(
        world.clients["member"],
        f"/api/assessments/{row['assessment_id']}/review/",
        {"reason": "Konteks percakapan menunjukkan sindiran.", "issue_stance": "PRO"},
    )
    assert res.status_code == 201, res.content[:200]
    new_id = res.json()["assessment_id"]
    reviews = events(world, action=AuditAction.CLASSIFICATION_REVIEW)
    assert len(reviews) == before_count + 1
    e = reviews[-1]
    assert e.subject_type == SubjectType.RESPONSE_ASSESSMENT and e.subject_id == new_id
    assert e.actor == world.member and e.reason == "Konteks percakapan menunjukkan sindiran."
    assert e.before["assessment_id"] == row["assessment_id"]
    assert e.before["issue_stance"] != "PRO" and e.after["issue_stance"] == "PRO"
    assert e.after["observation_id"] == row["observation"]["id"]
    assert e.after["analysis_run_id"] == world.m2.pk


def test_failed_changes_leave_no_audit_event(world) -> None:
    before = AuditEvent.objects.count()
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    rid = rows[0]["assessment_id"]
    for body in ({"reason": " "}, {"reason": "x", "issue_stance": "BUZZER"}):
        assert (
            post(world.clients["member"], f"/api/assessments/{rid}/review/", body).status_code
            == 400
        )
    bad = _finding_body(world, title="Ini pasti akun buzzer berbayar")
    assert (
        post(
            world.clients["member"], f"/api/investigations/{world.inv.pk}/findings/", bad
        ).status_code
        == 400
    )
    assert AuditEvent.objects.count() == before


def test_finding_lifecycle_is_audited_end_to_end(world) -> None:
    member, owner = world.clients["member"], world.clients["owner"]
    created = post(
        member, f"/api/investigations/{world.inv.pk}/findings/", _finding_body(world)
    ).json()
    fid = created["id"]
    draft = events(world, action=AuditAction.FINDING_DRAFT, subject_id=fid)
    assert len(draft) == 1 and draft[0].before is None and draft[0].actor == world.member
    assert draft[0].after["status"] == "DRAFT" and draft[0].after["observation_count"] >= 1
    assert draft[0].after["analysis_run_ids"] and draft[0].reason

    post(owner, f"/api/findings/{fid}/endorse/", {"note": "Ditinjau dan sah."})
    endorse = events(world, action=AuditAction.FINDING_ENDORSE, subject_id=fid)
    assert len(endorse) == 1 and endorse[0].actor == world.owner
    assert endorse[0].before["status"] == "DRAFT" and endorse[0].after["status"] == "ENDORSED"
    assert endorse[0].reason == "Ditinjau dan sah."

    revised = post(
        member, f"/api/findings/{fid}/revise/", _finding_body(world, title="Revisi")
    ).json()
    rev = events(world, action=AuditAction.FINDING_REVISE, subject_id=revised["id"])
    assert len(rev) == 1 and rev[0].before["finding_id"] == fid
    assert rev[0].before["status"] == "ENDORSED" and rev[0].after["title"] == "Revisi"

    post(owner, f"/api/findings/{revised['id']}/withdraw/", {"note": "Salah sampel."})
    wd = events(world, action=AuditAction.FINDING_WITHDRAW, subject_id=revised["id"])
    assert (
        len(wd) == 1 and wd[0].before["status"] == "DRAFT" and wd[0].after["status"] == "WITHDRAWN"
    )
    assert wd[0].reason == "Salah sampel."


def test_audit_events_cannot_be_changed_or_deleted(world) -> None:
    e = events(world)[0]
    e.reason = "diubah"
    with pytest.raises(Exception, match="append-only"):
        e.save()
    with pytest.raises(Exception, match="tidak dapat dihapus"):
        e.delete()
    for sql in (
        "UPDATE audit_auditevent SET reason = 'x' WHERE id = %s",
        "DELETE FROM audit_auditevent WHERE id = %s",
    ):
        with pytest.raises((InternalError, ProgrammingError, Exception)), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [e.pk])
    assert AuditEvent.objects.filter(pk=e.pk).exists()


def test_audit_list_api_filters_orders_and_paginates(world) -> None:
    inv_services.revise_issue_context(
        issue=Issue.objects.get(pk=world.issue.pk),
        user=world.member,
        definition="Untuk uji daftar.",
    )
    url = f"/api/investigations/{world.inv.pk}/audit/"
    page = get_json(world, url, page_size=200)
    ids = [r["id"] for r in page["results"]]
    assert ids == sorted(ids, reverse=True) and page["count"] == len(ids)
    assert "hanya dapat bertambah" in page["notice"]
    first = page["results"][-1]
    assert first["actor"] and first["action_label"] and first["subject_type_label"]
    only_ctx = get_json(world, url, action="ISSUE_CONTEXT", page_size=200)["results"]
    assert only_ctx and {r["action"] for r in only_ctx} == {"ISSUE_CONTEXT"}
    one = get_json(world, url, subject_type="issue", subject_id=world.issue.pk)["results"]
    assert one and {r["subject_id"] for r in one} == {world.issue.pk}
    by_type = get_json(world, url, subject_type="target", page_size=200)["results"]
    assert by_type and {r["subject_type"] for r in by_type} == {"target"}
    by_id = get_json(world, url, subject_id=world.target.pk, page_size=200)["results"]
    assert by_id and {r["subject_id"] for r in by_id} == {world.target.pk}
    mine = get_json(world, url, actor="anggota", page_size=200)["results"]
    assert mine and {r["actor"] for r in mine} == {"anggota"}
    small = get_json(world, url, page_size=2)
    assert len(small["results"]) == 2 and small["count"] == page["count"]
    second = get_json(world, url, page_size=2, page=2)["results"]
    assert [r["id"] for r in second] == ids[2:4]
    get_json(world, url, status=400, action="TIDAK_ADA")


def test_audit_list_is_scoped_to_its_investigation(world) -> None:
    other = inv_services.create_investigation(user=world.owner, name="Lain")
    inv_services.create_issue(investigation=other, user=world.owner, title="Isu lain")
    mine = get_json(world, f"/api/investigations/{world.inv.pk}/audit/", page_size=200)["results"]
    theirs = get_json(world, f"/api/investigations/{other.pk}/audit/", who="owner")["results"]
    assert len(theirs) == 1 and theirs[0]["subject_type"] == "issue"
    assert not {r["id"] for r in mine} & {r["id"] for r in theirs}


def test_audit_list_filters_by_observation_across_classification_versions(world) -> None:
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    row = next(r for r in rows if r["versions"] == 1)
    obs_id = row["observation"]["id"]
    stances = [x for x in ("PRO", "CONTRA", "MIXED") if x != row["labels"]["issue_stance"]]
    url = f"/api/investigations/{world.inv.pk}/audit/"
    assert get_json(world, url, observation=obs_id)["results"] == []
    first = post(
        world.clients["member"],
        f"/api/assessments/{row['assessment_id']}/review/",
        {"reason": "Koreksi pertama.", "issue_stance": stances[0]},
    ).json()
    post(
        world.clients["member"],
        f"/api/assessments/{first['assessment_id']}/review/",
        {"reason": "Koreksi kedua.", "issue_stance": stances[1]},
    )
    trail = get_json(world, url, observation=obs_id)["results"]
    assert [e["reason"] for e in trail] == ["Koreksi kedua.", "Koreksi pertama."]
    assert {e["subject_type"] for e in trail} == {"response_assessment"}
    other = next(r for r in rows if r["observation"]["id"] != obs_id)
    assert get_json(world, url, observation=other["observation"]["id"])["results"] == []


def test_observation_trail_includes_its_classification_audit_trail(world) -> None:
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    row = next(r for r in rows if r["versions"] == 1)
    obs_id = row["observation"]["id"]
    new_stance = next(x for x in ("MIXED", "PRO") if x != row["labels"]["issue_stance"])
    assert get_json(world, f"/api/observations/{obs_id}/")["classification_trail"] == []
    other = next(r for r in rows if r["observation"]["id"] != obs_id and r["versions"] == 1)
    other_stance = next(x for x in ("MIXED", "PRO") if x != other["labels"]["issue_stance"])
    post(
        world.clients["member"],
        f"/api/assessments/{other['assessment_id']}/review/",
        {"reason": "Observasi lain.", "issue_stance": other_stance},
    )
    assert get_json(world, f"/api/observations/{obs_id}/")["classification_trail"] == []
    post(
        world.clients["member"],
        f"/api/assessments/{row['assessment_id']}/review/",
        {"reason": "Dikoreksi dari jejak.", "issue_stance": new_stance},
    )
    trail = get_json(world, f"/api/observations/{obs_id}/")["classification_trail"]
    assert len(trail) == 1 and trail[0]["actor"] == "anggota"
    assert trail[0]["reason"] == "Dikoreksi dari jejak."
    assert trail[0]["before"]["issue_stance"] != new_stance
    assert trail[0]["after"]["issue_stance"] == new_stance
    latest = trail[0]["after"]["assessment_id"]
    second = next(x for x in ("CONTRA", "UNDETERMINED") if x != new_stance)
    post(
        world.clients["owner"],
        f"/api/assessments/{latest}/review/",
        {"reason": "Koreksi lanjutan.", "issue_stance": second},
    )
    trail = get_json(world, f"/api/observations/{obs_id}/")["classification_trail"]
    assert [e["reason"] for e in trail] == ["Koreksi lanjutan.", "Dikoreksi dari jejak."]
    assert trail[0]["actor"] == "pemilik"
