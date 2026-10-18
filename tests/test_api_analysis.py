"""WP-2.7a: API analisis (respons M2, graf M4, indikator, profil M3, temuan M5, jejak bukti).

Dunia uji dibangun SEKALI per modul di dalam satu transaksi (dibatalkan di akhir); tiap tes berjalan
di savepoint sendiri sehingga perubahan satu tes tidak bocor ke tes lain.
"""

import json
from datetime import timedelta

import pytest
from collection.contracts import SourceObjectType
from collection_helpers import OBSERVED, ingest, new_run, obs
from django.contrib.auth.models import User
from django.db import transaction
from django.test import Client
from intelligence import coordination_runs as cr
from intelligence import profiles, services
from intelligence.m2.example_rules import example_parameters
from intelligence.models import AnalysisRun, CoordinationEdge, Finding
from intelligence.networks import network_parameters
from investigations import services as inv_services
from investigations import team
from investigations.access import RANK
from investigations.enums import Platform, Role, TargetType
from preservation.models import ArtifactVerification, EvidenceArtifact

POST, QUOTE, REPOST = SourceObjectType.POST, SourceObjectType.QUOTE, SourceObjectType.REPOST
CUES = (["harus diaudit", "audit harus dilakukan"], ["tidak perlu diaudit"])
START, END = OBSERVED - timedelta(days=10), OBSERVED + timedelta(days=1)
PW = "Kata-sandi-uji-123!"
ALT = {
    k: {"outcome": "RULED_OUT", "reasoning": f"Dikaji: {k} tidak menjelaskan pola ini."}
    for k in ("organic_mobilization", "external_event", "public_content_copying", "sampling_bias")
}
RATING = {
    a: {"level": "ACCEPTABLE", "reason": f"alasan {a}"}
    for a in ("integrity", "provenance", "completeness", "relevance")
}
CO_PARAMS = dict(
    sync_window_seconds=120,
    sync_min_events=1,
    co_response_min_shared=1,
    similarity_ngram=3,
    similarity_threshold=0.8,
    similarity_min_chars=20,
    similarity_min_pairs=1,
    similarity_max_responses=1000,
    amplification_window_seconds=300,
    amplification_min_events=1,
    url_min_shared=1,
    phrase_words=5,
    phrase_min_shared=1,
    repeated_min_shared_targets=2,
    permutations=0,
    baseline_seed=1,
    evidence_limit=50,
    max_pair_events=5_000_000,
)


def ago(days: float):
    return OBSERVED - timedelta(days=days)


def make_user(name, **extra):
    return User.objects.create_user(name, password=PW, **extra)


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def post(c, path, data=None):
    return c.post(path, json.dumps(data or {}), content_type="application/json")


class World:
    pass


@pytest.fixture(scope="module")
def world(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        atomic = transaction.atomic()
        atomic.__enter__()
        try:
            yield _build()
        finally:
            transaction.set_rollback(True)
            atomic.__exit__(None, None, None)


def _build() -> World:
    w = World()
    w.owner = make_user("pemilik")
    w.member = make_user("anggota")
    w.viewer = make_user("pembaca")
    w.outsider = make_user("orang-luar")
    w.admin = make_user("admin", is_superuser=True, is_staff=True)
    w.inv = inv_services.create_investigation(user=w.owner, name="Analisis")
    for user, role in ((w.member, Role.MEMBER), (w.viewer, Role.VIEWER)):
        team.grant(investigation=w.inv, user=user, role=role, added_by=w.owner)
    issue = inv_services.create_issue(investigation=w.inv, user=w.owner, title="Kebakaran hutan")
    w.prop = inv_services.add_proposition(
        issue=issue, user=w.owner, statement="Perusahaan perlu diaudit."
    )
    w.issue = issue
    w.target = inv_services.register_target(
        investigation=w.inv,
        user=w.owner,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        stances={w.prop: "CONTRA"},
    )
    w.other_target = inv_services.register_target(  # tidak pernah diperiksa: cakupan sebagian
        investigation=w.inv,
        user=w.owner,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/2",
    )
    run = new_run(w.target, w.owner)
    claim = "Sudah dijelaskan lengkap di https://contoh.example/klarifikasi silakan baca dulu"
    same = [
        obs(
            run,
            f"s{i}",
            actor=f"same{i}",
            parent="seed",
            text="Justru audit harus dilakukan.",
            published_at=ago(5 - i * 0.1),
        )
        for i in range(1, 4)
    ]
    ingest(
        run,
        [
            obs(
                run,
                "seed",
                kind=POST,
                actor="a0",
                text="Perusahaan tidak perlu diaudit.",
                published_at=ago(9),
            ),
            obs(
                run,
                "r1",
                actor="u1",
                parent="seed",
                text="Justru audit harus dilakukan.",
                published_at=ago(3),
            ),
            obs(
                run,
                "r2",
                actor="u2",
                parent="seed",
                text="Perusahaan itu tidak perlu diaudit.",
                published_at=ago(2.5),
            ),
            obs(run, "r3", actor="u1", parent="r2", text="Penulis ini bodoh.", published_at=ago(2)),
            obs(run, "r4", actor="u3", parent="r1", text="Setuju sekali!", published_at=ago(1.8)),
            obs(
                run,
                "q1",
                kind=QUOTE,
                actor="u3",
                parent=None,
                quoted_post_id="r1",
                text="Setuju sekali!",
                published_at=ago(1.5),
            ),
            obs(
                run,
                "rp1",
                kind=REPOST,
                actor="u2",
                parent=None,
                reposted_post_id="r1",
                text=None,
                published_at=ago(1.2),
            ),
            obs(
                run,
                "r5",
                actor="u4",
                parent="seed",
                mentioned_actor_ids=("u2",),
                text="Apa buktinya?",
                published_at=ago(1),
            ),
            obs(run, "r6", actor="u5", parent="seed", text=claim, published_at=ago(0.9)),
            obs(
                run,
                "r7",
                actor="u6",
                parent="seed",
                text=claim,
                published_at=ago(0.9) + timedelta(seconds=30),
            ),
            obs(
                run,
                "r8",
                actor="u7",
                parent="seed",
                text="Awas ya, urusannya bisa panjang.",
                published_at=ago(0.5),
            ),
            obs(
                run,
                "r9",
                actor="u8",
                parent="seed",
                text="Balasan tanpa waktu publikasi yang diketahui.",
                published_at=None,
            ),
            *same,
        ],
    )
    w.run = run
    dataset = services.create_dataset_version(investigation=w.inv, runs=[run], by=w.owner)
    w.dataset = dataset

    def analysis(method, params):
        r = services.create_analysis_run(
            dataset=dataset,
            method=method,
            parameters=params,
            by=w.owner,
            issue_context_version=services.latest_issue_context(issue),
            target_context_versions=services.latest_target_contexts(dataset),
        )
        done = services.execute_run(r)
        assert done.status == "COMPLETED", (method, done.error)
        return done

    w.m2 = analysis("m2-rules", example_parameters({w.prop.pk: CUES}))
    w.m3 = analysis(
        "m3-profile",
        profiles.m3_parameters(
            source_run=w.m2,
            proposition=w.prop,
            period_start=START,
            period_end=END,
            min_responses=2,
            bucket_hours=24,
            min_active_buckets=2,
            narrative_min_texts=2,
        ),
    )
    w.m4 = analysis(
        "m4-network",
        network_parameters(
            window_start=START,
            window_end=END,
            unknown_time="include",
            relation_types=["reply_to", "quote_of", "repost_of", "mentions"],
            weighting="count",
            resolution=1.0,
            seed=3,
            compute_betweenness=True,
            metrics_max_nodes=1000,
            stability_seeds=0,
            source_run=w.m2,
            proposition=w.prop,
        ),
    )
    w.co = analysis(
        "co-indicators", cr.coordination_parameters(window_start=START, window_end=END, **CO_PARAMS)
    )
    w.artifact = EvidenceArtifact.objects.create(
        run=run,
        kind="screenshot",
        relative_path=f"uji/{run.pk}/a.png",
        sha256="a" * 64,
        size_bytes=10,
        content_type="image/png",
        post=None,
    )
    ArtifactVerification.objects.create(
        artifact=w.artifact,
        verified_by=w.owner,
        purpose="verify",
        result="MATCH",
        expected_sha256="a" * 64,
        expected_size=10,
        actual_sha256="a" * 64,
        actual_size=10,
    )
    w.clients = {
        n: client_for(getattr(w, n)) for n in ("owner", "member", "viewer", "outsider", "admin")
    }
    return w


pytestmark = pytest.mark.django_db


def get_json(world, path, who="viewer", status=200, **params):
    res = world.clients[who].get(path, params)
    assert res.status_code == status, (path, res.status_code, res.content[:200])
    return res.json()


def keys_of(value, found=None):
    found = found if found is not None else set()
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(str(k).lower())
            keys_of(v, found)
    elif isinstance(value, list):
        for v in value:
            keys_of(v, found)
    return found


# --- matriks otorisasi -----------------------------------------------------------------------


def endpoints(w: World):
    inv, m2 = w.inv.pk, w.m2.pk
    some_assessment = w.m2.assessments.first().pk
    some_finding = _ensure_finding(w)
    obs_id = w.m2.assessments.first().observation_id
    return [
        ("run: daftar", "get", f"/api/investigations/{inv}/analysis-runs/", None, Role.VIEWER),
        ("audit: jejak", "get", f"/api/investigations/{inv}/audit/", None, Role.VIEWER),
        ("run: detail", "get", f"/api/analysis-runs/{m2}/", None, Role.VIEWER),
        ("respons", "get", f"/api/analysis-runs/{m2}/responses/", None, Role.VIEWER),
        (
            "klasifikasi: riwayat",
            "get",
            f"/api/assessments/{some_assessment}/history/",
            None,
            Role.VIEWER,
        ),
        (
            "klasifikasi: tinjau",
            "post",
            f"/api/assessments/{some_assessment}/review/",
            {"reason": "uji"},
            Role.MEMBER,
        ),
        ("graf", "get", f"/api/analysis-runs/{w.m4.pk}/graph/", None, Role.VIEWER),
        ("indikator", "get", f"/api/analysis-runs/{w.co.pk}/coordination/", None, Role.VIEWER),
        ("profil: daftar", "get", f"/api/analysis-runs/{w.m3.pk}/profiles/", None, Role.VIEWER),
        ("profil: detail", "get", f"/api/profiles/{w.m3.profiles.first().pk}/", None, Role.VIEWER),
        ("temuan: daftar", "get", f"/api/investigations/{inv}/findings/", None, Role.VIEWER),
        ("temuan: buat", "post", f"/api/investigations/{inv}/findings/", {}, Role.MEMBER),
        (
            "temuan: saran bukti",
            "post",
            f"/api/investigations/{inv}/findings/evidence/",
            {"observation_ids": [obs_id]},
            Role.MEMBER,
        ),
        ("temuan: detail", "get", f"/api/findings/{some_finding}/", None, Role.VIEWER),
        ("temuan: revisi", "post", f"/api/findings/{some_finding}/revise/", {}, Role.MEMBER),
        ("temuan: sahkan", "post", f"/api/findings/{some_finding}/endorse/", {}, Role.MEMBER),
        ("temuan: tarik", "post", f"/api/findings/{some_finding}/withdraw/", {}, Role.MEMBER),
        ("observasi: jejak", "get", f"/api/observations/{obs_id}/", None, Role.VIEWER),
    ]


_FINDING: dict[str, int] = {}


def _finding_body(w, **over):
    edges = list(w.co.coordination.edges.filter(indicator="CO-02")[:1])
    body = {
        "analysis_run_ids": [w.co.pk],
        "indicator_edge_ids": [e.pk for e in edges],
        "observation_ids": [],
        "title": "Pola waktu dan teks serupa",
        "statement": "Dua akun membalas posting yang sama dalam waktu berdekatan dengan teks yang hampir sama.",
        "interpretation": "Indikator waktu dan teks menunjukkan pola bersama pada posting target.",
        "evidence_ratings": RATING,
        "alternatives": ALT,
        "confidence": "LOW",
        "confidence_reason": "Data sintetis dan bukti belum independen.",
    }
    body.update(over)
    return body


def _ensure_finding(w) -> int:
    if "id" not in _FINDING or not Finding.objects.filter(pk=_FINDING["id"]).exists():
        res = post(
            w.clients["owner"], f"/api/investigations/{w.inv.pk}/findings/", _finding_body(w)
        )
        assert res.status_code == 201, res.content[:300]
        _FINDING["id"] = res.json()["id"]
    return _FINDING["id"]


ROLES = ["viewer", "member", "owner", "admin", "outsider"]
EFFECTIVE = {"viewer": 1, "member": 2, "owner": 3, "admin": 99, "outsider": 0}


def test_every_new_endpoint_enforces_its_minimum_role(world) -> None:
    checked = 0
    for name, method, path, body, minimum in endpoints(world):
        for role in ROLES:
            c = world.clients[role]
            res = c.get(path) if method == "get" else post(c, path, body)
            allowed = EFFECTIVE[role] >= RANK[minimum]
            if role == "outsider":
                assert res.status_code == 404 and res.json()["code"] == "not_found", (
                    name,
                    role,
                    res.status_code,
                )
            elif not allowed:
                assert res.status_code == 403 and res.json()["code"] == "insufficient_role", (
                    name,
                    role,
                    res.status_code,
                )
            else:
                assert res.status_code not in (401, 403, 404), (
                    name,
                    role,
                    res.status_code,
                    res.content[:200],
                )
            checked += 1
    assert checked == len(endpoints(world)) * len(ROLES)


def test_the_matrix_covers_every_new_object_route(world) -> None:
    from api.urls import urlpatterns

    new = {str(p.pattern) for p in urlpatterns if "<int:" in str(p.pattern)} - {
        # rute lama dicakup test_authorization.py
        "investigations/<int:pk>/",
        "investigations/<int:pk>/issues/",
        "issues/<int:pk>/propositions/",
        "investigations/<int:pk>/targets/",
        "targets/<int:pk>/context-versions/",
        "targets/<int:pk>/inspections/",
        "inspections/<int:pk>/",
        "inspections/<int:pk>/observations/",
        "inspections/<int:pk>/acknowledge-review/",
        "inspections/<int:pk>/verify-artifacts/",
        "artifacts/<int:pk>/verify/",
        "artifacts/<int:pk>/content/",
        "investigations/<int:pk>/members/",
        "investigations/<int:pk>/members/<int:user_id>/role/",
        "investigations/<int:pk>/members/<int:user_id>/revoke/",
        "users/<int:pk>/activation/",
        "users/<int:pk>/password/",
    }
    covered = {
        "investigations/<int:pk>/analysis-runs/",
        "analysis-runs/<int:pk>/",
        "analysis-runs/<int:pk>/responses/",
        "assessments/<int:pk>/history/",
        "assessments/<int:pk>/review/",
        "analysis-runs/<int:pk>/graph/",
        "analysis-runs/<int:pk>/coordination/",
        "analysis-runs/<int:pk>/profiles/",
        "profiles/<int:pk>/",
        "investigations/<int:pk>/findings/",
        "investigations/<int:pk>/findings/evidence/",
        "investigations/<int:pk>/audit/",
        "findings/<int:pk>/",
        "findings/<int:pk>/revise/",
        "findings/<int:pk>/endorse/",
        "findings/<int:pk>/withdraw/",
        "observations/<int:pk>/",
    }
    assert new == covered, new ^ covered
    assert len(endpoints(world)) == 18  # satu entri per rute (daftar/buat memakai rute yang sama)


# --- run analisis ------------------------------------------------------------------------------------


def test_run_list_and_detail_expose_method_parameters_dataset_and_tier(world) -> None:
    body = get_json(world, f"/api/investigations/{world.inv.pk}/analysis-runs/")
    methods = {r["method"] for r in body["results"]}
    assert methods == {"m2-rules", "m3-profile", "m4-network", "co-indicators"}
    only = get_json(
        world, f"/api/investigations/{world.inv.pk}/analysis-runs/", method="m4-network"
    )
    assert [r["method"] for r in only["results"]] == ["m4-network"]
    detail = get_json(world, f"/api/analysis-runs/{world.m2.pk}/")
    assert detail["parameters"]["min_matches"] == 1 and detail["dataset"]["platform"] == "x"
    assert detail["tier"]["tier"] == 2 and detail["tier"]["category"] == "machine_result"
    assert detail["output"]["assessments"] > 0 and detail["issue_context_version"] == 1
    assert detail["target_contexts"][0]["target_id"] == world.target.pk
    assert get_json(world, f"/api/analysis-runs/{world.co.pk}/")["tier"]["tier"] == 3


# --- respons M2 (FR-091) ----------------------------------------------------------------------------------


def test_responses_list_carries_labels_parent_chain_evidence_and_category(world) -> None:
    body = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/")
    assert body["total"] == len(body["results"]) and body["total"] >= 12
    row = next(
        r for r in body["results"] if r["observation"]["external_post_id"] == "r4"
    )  # "Setuju sekali!" membalas r1
    assert row["labels"]["issue_stance"] == "PRO" and row["labels"]["target_alignment"] == "SUPPORT"
    assert [c["observation_id"] for c in row["parent_chain"]][0] == next(
        r["observation"]["id"]
        for r in body["results"]
        if r["observation"]["external_post_id"] == "r1"
    )
    assert (
        row["parent_chain"][0]["stance"] == "PRO"
        and row["parent_chain"][0]["text"] == "Justru audit harus dilakukan."
    )
    assert row["parent_chain"][-1]["text"] == "Perusahaan tidak perlu diaudit."  # posting target
    assert row["source"] == "MACHINE" and row["review"] is None and row["versions"] == 1
    assert row["category"] == "machine_result" and row["tier"] == 2
    assert row["labels"]["response_character"][0]["code"].startswith("RC-")
    assert "matched" in row["basis"] and row["observation"]["author"]["external_actor_id"] == "u3"
    assert "dimensi berbeda" in body["notice"]


def test_responses_filters_and_pagination(world) -> None:
    base = f"/api/analysis-runs/{world.m2.pk}/responses/"
    allrows = get_json(world, base, page_size=200)["results"]
    pro = get_json(world, base, stance="PRO")
    assert pro["total"] == sum(1 for r in allrows if r["labels"]["issue_stance"] == "PRO") > 0
    assert all(r["labels"]["issue_stance"] == "PRO" for r in pro["results"])
    assert get_json(world, base, alignment="OPPOSE")["total"] == sum(
        1 for r in allrows if r["labels"]["target_alignment"] == "OPPOSE"
    )
    attack = get_json(world, base, character="RC-05", page_size=200)
    assert 1 <= attack["total"] < len(allrows)
    assert all(
        "RC-05" in [c["code"] for c in r["labels"]["response_character"]] for r in attack["results"]
    )
    flagged = get_json(world, base, needs_review="true")
    assert flagged["total"] >= 1 and all(r["needs_human_review"] for r in flagged["results"])
    clean = get_json(world, base, needs_review="false", page_size=200)
    assert clean["total"] == len(allrows) - flagged["total"]
    assert not any(r["needs_human_review"] for r in clean["results"])
    actor = allrows[0]["observation"]["author"]["id"]
    assert all(
        r["observation"]["author"]["id"] == actor
        for r in get_json(world, base, actor=actor)["results"]
    )
    first = get_json(world, base, page=1, page_size=3)
    second = get_json(world, base, page=2, page_size=3)
    assert len(first["results"]) == 3 and first["page_size"] == 3
    assert not {r["assessment_id"] for r in first["results"]} & {
        r["assessment_id"] for r in second["results"]
    }
    assert get_json(world, base, origin="human")["total"] == 0
    get_json(world, base, status=400, stance="BUZZER")
    get_json(world, base, status=400, page_size=500)


def test_wrong_analysis_method_is_a_clear_conflict(world) -> None:
    for path in (
        f"/api/analysis-runs/{world.m4.pk}/responses/",
        f"/api/analysis-runs/{world.m2.pk}/graph/",
        f"/api/analysis-runs/{world.m2.pk}/coordination/",
        f"/api/analysis-runs/{world.m2.pk}/profiles/",
    ):
        body = get_json(world, path, status=409)
        assert body["code"] == "wrong_analysis_method"


def test_AT16_review_via_api_is_traceable_and_keeps_the_machine_result(world) -> None:
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    target = next(r for r in rows if r["observation"]["external_post_id"] == "r8")  # ancaman
    assert target["needs_human_review"] and "RC-07" in [
        c["code"] for c in target["labels"]["response_character"]
    ]
    res = post(
        world.clients["member"],
        f"/api/assessments/{target['assessment_id']}/review/",
        {"reason": "Hanya sindiran, bukan ancaman.", "response_character": ["RC-06"]},
    )
    assert res.status_code == 201
    new = res.json()
    assert (
        new["source"] == "HUMAN"
        and new["review"]["by"] == "anggota"
        and new["category"] == "human_reviewed"
    )
    assert (
        new["labels"]["response_character"][0]["code"] == "RC-06"
        and new["needs_human_review"] is False
    )
    again = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)[
        "results"
    ]
    row = next(r for r in again if r["observation"]["external_post_id"] == "r8")
    assert (
        row["assessment_id"] == new["assessment_id"]
        and row["source"] == "HUMAN"
        and row["versions"] == 2
    )
    assert (
        row["category"] == "human_reviewed" and row["tier"] == 2
    )  # juga pada daftar, bukan hanya respons POST
    assert (
        next(r for r in again if r["observation"]["external_post_id"] == "r7")["category"]
        == "machine_result"
    )
    assert row["review"]["reason"].startswith("Hanya sindiran")
    history = get_json(world, f"/api/assessments/{new['assessment_id']}/history/")["results"]
    assert [h["source"] for h in history] == ["MACHINE", "HUMAN"]
    assert (
        history[0]["labels"]["response_character"][0]["code"] == "RC-07"
    )  # hasil mesin tak berubah
    stale = post(
        world.clients["member"],
        f"/api/assessments/{target['assessment_id']}/review/",
        {"reason": "lagi", "issue_stance": "PRO"},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "already_reviewed"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": " "},
        {"reason": "x"},
        {"reason": "x", "issue_stance": "BUZZER"},
        {"reason": "x", "response_character": []},
        {"reason": "x", "response_character": ["RC-99"]},
    ],
)
def test_invalid_reviews_are_400_with_a_code(world, body) -> None:
    a = world.m2.assessments.filter(superseded_by__isnull=True).first()
    res = post(world.clients["member"], f"/api/assessments/{a.pk}/review/", body)
    assert res.status_code == 400
    if body.get("reason", "").strip():
        assert res.json()["code"] == "invalid_review"


# --- graf M4 dan indikator (FR-092; AT-12) ---------------------------------------------------------------


def test_graph_payload_has_nodes_edges_attributes_and_tier(world) -> None:
    g = get_json(world, f"/api/analysis-runs/{world.m4.pk}/graph/")
    assert g["platform"] == "x" and g["category"] == "machine_result" and g["tier"] == 3
    assert {e["kind"] for e in g["edges"]} == {"interaction"}
    assert {e["type"] for e in g["edges"]} == {"reply_to", "quote_of", "repost_of", "mentions"}
    node = next(n for n in g["nodes"] if n["actor"]["external_actor_id"] == "u1")
    assert node["label"] == "akun_u1" or node["label"]
    assert node["attributes"]["stance_summary"] in {"PRO", "CONTRA", "MIXED", "UNDETERMINED"}
    assert {"in_degree", "out_degree", "community"} <= set(node["metrics"])
    assert "bukan penentu pengendali" in g["notice"] and g["definition"]["stance_view"] is True
    assert g["total_nodes"] == len(g["nodes"]) and g["truncated"] is False
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
    assert all(e["observation_ids"] for e in g["edges"])


def test_graph_filters_by_relation_type_time_stance_and_node_limit(world) -> None:
    base = f"/api/analysis-runs/{world.m4.pk}/graph/"
    quotes = get_json(world, base, relation_types="quote_of")
    assert {e["type"] for e in quotes["edges"]} == {"quote_of"} and quotes["filters"][
        "relation_types"
    ] == ["quote_of"]
    replies_mentions = get_json(world, base, relation_types="reply_to,mentions")
    assert {e["type"] for e in replies_mentions["edges"]} == {"reply_to", "mentions"}
    late = get_json(world, base, since=(ago(1.0)).isoformat())
    known = [e for e in late["edges"] if e["last_published_at"] is not None]
    assert known and all(e["last_published_at"] >= ago(1.0).isoformat() for e in known)
    assert any(
        e["last_published_at"] is None for e in late["edges"]
    )  # waktu tak diketahui ikut (bawaan)
    assert len(late["edges"]) < len(get_json(world, base)["edges"])
    early = get_json(world, base, until=ago(2.6).isoformat())
    assert all(
        e["first_published_at"] is None or e["first_published_at"] < ago(2.6).isoformat()
        for e in early["edges"]
    )
    pro = get_json(world, base, stance="PRO")
    assert pro["nodes"] and all(n["attributes"]["stance_summary"] == "PRO" for n in pro["nodes"])
    ids = {n["id"] for n in pro["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in pro["edges"])
    capped = get_json(world, base, max_nodes=3)
    assert len(capped["nodes"]) == 3 and capped["truncated"] is True and capped["total_nodes"] > 3
    full = get_json(world, base)
    strength: dict[int, int] = {}
    for e in full["edges"]:
        for end in (e["source"], e["target"]):
            strength[end] = strength.get(end, 0) + e["weight"]
    top = sorted(strength, key=lambda a: (-strength[a], a))[:3]
    assert {n["id"] for n in capped["nodes"]} == set(
        top
    )  # yang dipertahankan: tertaut paling banyak
    assert all(e["source"] in {n["id"] for n in capped["nodes"]} for e in capped["edges"])
    exact = get_json(world, base, max_nodes=full["total_nodes"])
    assert (
        exact["truncated"] is False and len(exact["nodes"]) == full["total_nodes"]
    )  # tepat di batas: tak dipotong
    assert get_json(world, base, max_nodes=full["total_nodes"] - 1)["truncated"] is True
    get_json(world, base, status=400, stance="BUZZER")
    get_json(world, base, status=400, max_nodes=0)


def test_graph_unknown_time_policy_is_explicit_and_default_is_to_include(world) -> None:
    base = f"/api/analysis-runs/{world.m4.pk}/graph/"

    def from_u8(payload):
        u8 = next(n["id"] for n in payload["nodes"] if n["actor"]["external_actor_id"] == "u8")
        return [e for e in payload["edges"] if e["source"] == u8]

    default = get_json(world, base)
    assert from_u8(default) and default["filters"]["include_unknown_time"] is True
    assert from_u8(default)[0]["first_published_at"] is None
    assert from_u8(get_json(world, base, include_unknown_time="true"))
    excluded = get_json(world, base, include_unknown_time="false")
    assert excluded["filters"]["include_unknown_time"] is False
    assert not [e for e in excluded["edges"] if e["first_published_at"] is None]
    assert len(excluded["edges"]) < len(default["edges"])


def test_AT12_interaction_edges_and_similarity_edges_are_kept_apart(world) -> None:
    graph = get_json(world, f"/api/analysis-runs/{world.m4.pk}/graph/")
    co = get_json(world, f"/api/analysis-runs/{world.co.pk}/coordination/")
    assert {e["kind"] for e in graph["edges"]} == {"interaction"}
    assert {r["kind"] for r in co["results"]} == {"behavioral_similarity"}
    assert "source" not in co["results"][0] and "actor_a" in co["results"][0]
    assert (
        co["notice"].startswith("Indikator, bukan temuan")
        and len(co["alternative_hypotheses"]) == 4
    )
    row = co["results"][0]
    assert (
        row["explanation"]
        and row["observation_ids"]
        and row["baseline"] == {"status": "NOT_COMPUTED"}
    )
    assert len(row["alternative_hypotheses"]) == 5 and row["indicator"].startswith("CO-")
    assert co["category"] == "machine_result" and co["tier"] == 3 and co["platform"] == "x"


def test_coordination_filters_and_pagination(world) -> None:
    base = f"/api/analysis-runs/{world.co.pk}/coordination/"
    allrows = get_json(world, base, page_size=200)
    assert allrows["total"] >= 4
    sync = get_json(world, base, indicator="CO-02")
    assert sync["total"] >= 1 and {r["indicator"] for r in sync["results"]} == {"CO-02"}
    assert get_json(world, base, min_support=99)["total"] == 0
    assert get_json(world, base, beyond_baseline="false")["total"] == allrows["total"]
    assert get_json(world, base, beyond_baseline="true")["total"] == 0  # baseline tidak dihitung
    actor = allrows["results"][0]["actor_a"]["id"]
    assert all(
        actor in (r["actor_a"]["id"], r["actor_b"]["id"])
        for r in get_json(world, base, actor=actor)["results"]
    )
    only_b = next(
        r["actor_b"]["id"]
        for r in allrows["results"]
        if not any(x["actor_a"]["id"] == r["actor_b"]["id"] for x in allrows["results"])
    )  # akun yang hanya pernah muncul sebagai pihak B
    as_b = get_json(world, base, actor=only_b, page_size=200)
    assert as_b["total"] >= 1 and all(only_b == r["actor_b"]["id"] for r in as_b["results"])
    expected = [r for r in allrows["results"] if only_b in (r["actor_a"]["id"], r["actor_b"]["id"])]
    assert as_b["total"] == len(expected)
    p1 = get_json(world, base, page=1, page_size=2)
    p2 = get_json(world, base, page=2, page_size=2)
    assert len(p1["results"]) == 2 and not {r["id"] for r in p1["results"]} & {
        r["id"] for r in p2["results"]
    }
    assert set(p1["pair_summary"]) <= {
        f"{r['actor_a']['id']}-{r['actor_b']['id']}" for r in p1["results"]
    }
    get_json(world, base, status=400, indicator="CO-09")


def test_absent_boolean_query_parameters_do_not_filter_anything() -> None:
    """DRF mengubah BooleanField yang tidak dikirim (input HTML/query) menjadi False; itu tidak boleh terjadi."""
    from api.serializers import CoordinationInput, GraphInput, ResponseListInput
    from django.http import QueryDict

    for serializer, name in (
        (ResponseListInput, "needs_review"),
        (CoordinationInput, "beyond_baseline"),
        (GraphInput, "include_unknown_time"),
    ):
        s = serializer(data=QueryDict(""))
        assert s.is_valid(), s.errors
        assert s.validated_data.get(name) is None, (serializer.__name__, name)
        given = serializer(data=QueryDict(f"{name}=false"))
        assert given.is_valid() and given.validated_data[name] is False


# --- profil M3 (FR-093) ------------------------------------------------------------------------------------


def test_profile_list_and_detail_lead_with_the_coverage_statement(world) -> None:
    listing = get_json(world, f"/api/analysis-runs/{world.m3.pk}/profiles/")
    assert listing["total"] >= 1 and "bukan seluruh aktivitas akun" in listing["notice"]
    first = listing["results"][0]
    assert (
        "bukan seluruh aktivitas akun" in first["coverage_statement"]
        and first["partial_coverage"] is True
    )
    assert first["participation"]["status"] == "OK" and first["actor"]["external_actor_id"]
    detail = get_json(world, f"/api/profiles/{first['id']}/")
    assert detail["platform"] == "x" and detail["level"] == "A" and detail["coverage"]["statement"]
    assert set(detail["dimensions"]) >= {
        "participation",
        "stance_distribution",
        "target_concentration",
    }
    assert detail["dimensions"]["target_concentration"]["status"] == "INSUFFICIENT_DATA"
    assert detail["category"] == "machine_result" and detail["period"]["start"]


# --- temuan M5 --------------------------------------------------------------------------------------------------


def test_finding_lifecycle_through_the_api(world) -> None:
    owner, member = world.clients["owner"], world.clients["member"]
    created = post(member, f"/api/investigations/{world.inv.pk}/findings/", _finding_body(world))
    assert created.status_code == 201, created.content[:300]
    f = created.json()
    assert f["status"] == "DRAFT" and f["category"] == "reviewed_finding" and f["tier"] == 4
    assert f["synthetic_data"] is True and "Bukan vonis" in f["notice"]
    assert set(f["evidence_quality"]) >= {"integrity", "provenance", "completeness", "relevance"}
    assert f["observation_count"] >= 1 and f["runs"][0]["id"] == world.co.pk and f["indicator_ids"]
    listing = get_json(world, f"/api/investigations/{world.inv.pk}/findings/")["results"]
    assert f["id"] in [x["id"] for x in listing]
    endorsed = post(owner, f"/api/findings/{f['id']}/endorse/", {"note": "Ditinjau."})
    assert endorsed.status_code == 200 and endorsed.json()["status"] == "ENDORSED"
    assert endorsed.json()["reviews"][0]["reviewer"] == "pemilik"
    revised = post(member, f"/api/findings/{f['id']}/revise/", _finding_body(world, title="Revisi"))
    assert revised.status_code == 201 and revised.json()["supersedes"] == f["id"]
    nf = revised.json()["id"]
    assert (
        post(owner, f"/api/findings/{nf}/endorse/", {"note": "Penerus disahkan."}).status_code
        == 200
    )
    old = get_json(world, f"/api/findings/{f['id']}/")
    assert old["status"] == "SUPERSEDED" and old["superseded_by"] == nf
    assert [h["id"] for h in get_json(world, f"/api/findings/{nf}/")["history"]] == [f["id"], nf]
    withdrawn = post(owner, f"/api/findings/{nf}/withdraw/", {"note": "Salah sampel."})
    assert withdrawn.json()["status"] == "WITHDRAWN"


def test_finding_creation_errors_are_clear(world) -> None:
    member, url = world.clients["member"], f"/api/investigations/{world.inv.pk}/findings/"
    verdict = post(member, url, _finding_body(world, statement="Ini jelas akun buzzer."))
    assert (
        verdict.status_code == 400
        and verdict.json()["code"] == "invalid_finding"
        and "FR-079" in verdict.json()["detail"]
    )
    high = post(member, url, _finding_body(world, confidence="HIGH"))
    assert (
        high.status_code == 400
        and high.json()["code"] == "confidence_above_ceiling"
        and "plafon" in high.json()["detail"]
    )
    assert post(member, url, _finding_body(world, title="")).status_code == 400
    foreign = post(member, url, _finding_body(world, analysis_run_ids=[999_999_999]))
    assert foreign.status_code == 400 and foreign.json()["code"] == "invalid_finding"
    # satu id sah bercampur dengan id asing: TIDAK boleh diam-diam diabaikan
    mixed_runs = post(
        member, url, _finding_body(world, analysis_run_ids=[world.co.pk, 999_999_999])
    )
    assert mixed_runs.status_code == 400 and "tidak ditemukan" in mixed_runs.json()["detail"]
    valid_edge = world.co.coordination.edges.filter(indicator="CO-02").first().pk
    mixed_edges = post(
        member, url, _finding_body(world, indicator_edge_ids=[valid_edge, 999_999_999])
    )
    assert mixed_edges.status_code == 400 and "tidak ditemukan" in mixed_edges.json()["detail"]


def test_incomplete_alternatives_cannot_be_endorsed_through_the_api(world) -> None:
    partial = {k: v for k, v in ALT.items() if k != "sampling_bias"}
    f = post(
        world.clients["member"],
        f"/api/investigations/{world.inv.pk}/findings/",
        _finding_body(world, alternatives=partial),
    ).json()
    res = post(world.clients["owner"], f"/api/findings/{f['id']}/endorse/", {"note": "coba"})
    assert res.status_code == 400 and "sampling_bias" in res.json()["detail"]
    assert (
        post(world.clients["owner"], f"/api/findings/{f['id']}/endorse/", {}).status_code == 400
    )  # catatan wajib


def test_findings_cannot_reference_another_investigations_objects(world) -> None:
    other = inv_services.create_investigation(user=world.owner, name="Lain")
    body = _finding_body(world)
    res = post(world.clients["owner"], f"/api/investigations/{other.pk}/findings/", body)
    assert (
        res.status_code == 400 and res.json()["code"] == "invalid_finding"
    )  # tidak membocorkan keberadaan objek
    suggestion = post(
        world.clients["owner"],
        f"/api/investigations/{other.pk}/findings/evidence/",
        {"observation_ids": [world.m2.assessments.first().observation_id]},
    )
    assert suggestion.status_code == 400


def test_evidence_suggestions_come_from_system_facts(world) -> None:
    ids = list(world.m2.assessments.values_list("observation_id", flat=True)[:5])
    res = post(
        world.clients["member"],
        f"/api/investigations/{world.inv.pk}/findings/evidence/",
        {"observation_ids": ids},
    )
    body = res.json()
    assert res.status_code == 200 and body["axes"] == [
        "integrity",
        "provenance",
        "completeness",
        "relevance",
    ]
    assert body["suggestions"]["integrity"]["level"] == "GOOD"  # artefak run terverifikasi MATCH
    assert (
        body["suggestions"]["relevance"]["level"] == "NOT_ASSESSABLE"
        and body["facts"]["synthetic"] is True
    )
    assert (
        post(
            world.clients["member"], f"/api/investigations/{world.inv.pk}/findings/evidence/", {}
        ).status_code
        == 400
    )


# --- jejak bukti (FR-005) ----------------------------------------------------------------------------------------


def test_observation_trail_links_parent_chain_artifacts_assessments_and_findings(world) -> None:
    rows = get_json(world, f"/api/analysis-runs/{world.m2.pk}/responses/", page_size=200)["results"]
    r4 = next(r for r in rows if r["observation"]["external_post_id"] == "r4")
    body = get_json(world, f"/api/observations/{r4['observation']['id']}/")
    assert body["category"] == "observed_fact" and body["tier"] == 1
    assert body["observation"]["text"] == "Setuju sekali!" and body["run"]["status"]
    assert [p["external_post_id"] for p in body["parent_chain"]] == ["r1", "seed"]
    assert (
        body["artifacts"][0]["last_verification"]["result"] == "MATCH"
        and body["artifacts"][0]["sha256"]
    )
    assert body["assessments"][0]["labels"]["issue_stance"] == "PRO"
    f = post(
        world.clients["member"],
        f"/api/investigations/{world.inv.pk}/findings/",
        _finding_body(world, observation_ids=[r4["observation"]["id"]]),
    ).json()
    again = get_json(world, f"/api/observations/{r4['observation']['id']}/")
    assert f["id"] in again["finding_ids"]


# --- penjaga nama dan kategori -----------------------------------------------------------------------------------


def test_no_payload_exposes_scores_rankings_or_suspicion_keys(world) -> None:
    paths = [
        f"/api/analysis-runs/{world.m2.pk}/responses/",
        f"/api/analysis-runs/{world.m4.pk}/graph/",
        f"/api/analysis-runs/{world.co.pk}/coordination/",
        f"/api/analysis-runs/{world.m3.pk}/profiles/",
        f"/api/profiles/{world.m3.profiles.first().pk}/",
        f"/api/analysis-runs/{world.m2.pk}/",
    ]
    fid = _ensure_finding(world)
    paths.append(f"/api/findings/{fid}/")
    keys: set[str] = set()
    for p in paths:
        keys_of(get_json(world, p), keys)
    for word in (
        "score",
        "skor",
        "rank",
        "peringkat",
        "suspicious",
        "mencurigakan",
        "buzzer",
        "verdict",
        "vonis",
        "probab",
    ):
        assert not any(word in k for k in keys), (word, sorted(k for k in keys if word in k))


def test_every_payload_declares_its_tier_and_category(world) -> None:
    fid = _ensure_finding(world)
    cases = [
        (f"/api/analysis-runs/{world.m2.pk}/responses/", "results", "machine_result", 2),
        (f"/api/analysis-runs/{world.m4.pk}/graph/", None, "machine_result", 3),
        (f"/api/analysis-runs/{world.co.pk}/coordination/", None, "machine_result", 3),
        (f"/api/analysis-runs/{world.m3.pk}/profiles/", None, "machine_result", 3),
        (f"/api/findings/{fid}/", None, "reviewed_finding", 4),
    ]
    for path, nested, category, tier in cases:
        body = get_json(world, path)
        target = body["results"][0] if nested else body
        assert (target["category"], target["tier"]) == (category, tier), path
        assert target["category_label"] and target["tier_label"]
