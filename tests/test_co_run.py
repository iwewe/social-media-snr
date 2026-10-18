"""WP-2.5: indikator koordinasi pada AnalysisRun (FR-072/075/076/077; AT-11, AT-12, AT-13)."""

import itertools
from datetime import timedelta

import pytest
from collection.contracts import SourceObjectType
from collection.models import ActorAccount, InspectionRun
from collection_helpers import OBSERVED, ingest, new_run, obs, register
from django.db import DatabaseError, connection, transaction
from intelligence import coordination_runs as cr
from intelligence import services
from intelligence.errors import InvalidParameters
from intelligence.models import (
    AnalysisRun,
    AnalysisStatus,
    CoordinationEdge,
    CoordinationNetwork,
)
from intelligence.synthetic import generate
from investigations.enums import Platform
from test_m4_run import _dataset, _ingest_bundle, inv, user  # noqa: F401

pytestmark = pytest.mark.django_db
POST, REPOST = SourceObjectType.POST, SourceObjectType.REPOST
W_START = OBSERVED - timedelta(days=30)
W_END = OBSERVED + timedelta(days=30)
BASE = dict(
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


def params(**over):
    window = {k: over.pop(k) for k in ("window_start", "window_end") if k in over}
    return cr.coordination_parameters(
        window_start=window.get("window_start", W_START),
        window_end=window.get("window_end", W_END),
        **{**BASE, **over},
    )


def secs(n: float):
    return OBSERVED - timedelta(days=2) + timedelta(seconds=n)


def run_co(user, dataset, p=None, *, execute=True):
    run = services.create_analysis_run(
        dataset=dataset,
        method="co-indicators",
        parameters=p or params(),
        by=user,
        issue_context_version=None,
        target_context_versions=services.latest_target_contexts(dataset),
    )
    return services.execute_run(run) if execute else run


@pytest.fixture
def target(inv, user):
    return register(inv, user, Platform.X, "https://x.com/u/status/1")


@pytest.fixture
def small(inv, user, target):
    """u1 dan u2 bertindak bersama pada tiga induk; u3 bertindak sendiri."""
    run = new_run(target, user)
    items = [
        obs(run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-100))
    ]
    for n in range(3):
        items.append(
            obs(
                run,
                f"p{n}",
                actor="a0",
                parent="seed",
                text=f"induk nomor {n}",
                published_at=secs(n * 1000 - 50),
            )
        )
    claim = "Sudah dijelaskan lengkap di https://contoh.example/klarifikasi silakan baca dulu"
    for n in range(3):
        items.append(
            obs(
                run,
                f"u1-{n}",
                actor="u1",
                parent=f"p{n}",
                text=claim,
                published_at=secs(n * 1000 + 10),
            )
        )
        items.append(
            obs(
                run,
                f"u2-{n}",
                actor="u2",
                parent=f"p{n}",
                text=claim,
                published_at=secs(n * 1000 + 25),
            )
        )
    items.append(
        obs(
            run,
            "u3-0",
            actor="u3",
            parent="p0",
            text="pendapat yang sama sekali berbeda dan panjang",
            published_at=secs(90_000),
        )
    )
    ingest(run, items)
    return run


def _edges(run):
    out = {}
    for e in run.coordination.edges.select_related("actor_a", "actor_b"):
        key = (e.actor_a.external_actor_id, e.actor_b.external_actor_id, e.indicator, e.variant)
        out[key] = e
    return out


def test_pairs_acting_together_get_indicators_with_evidence_and_explanations(
    inv, user, small
) -> None:
    run = run_co(user, _dataset(inv, user, [small]))
    assert run.status == AnalysisStatus.COMPLETED, run.error
    edges = _edges(run)
    for key in (
        ("u1", "u2", "CO-01", ""),
        ("u1", "u2", "CO-02", ""),
        ("u1", "u2", "CO-03", ""),
        ("u1", "u2", "CO-05", "url"),
        ("u1", "u2", "CO-05", "phrase"),
    ):
        assert key in edges, key
    e = edges[("u1", "u2", "CO-02", "")]
    assert e.support == 3 and e.value == 3.0 and len(e.observation_ids) == 6
    assert "membalas 3 posting induk" in e.explanation and e.alternative_hypotheses
    assert not any(
        k[0] == "u3" or k[1] == "u3" for k in edges if k[2] in ("CO-02", "CO-03", "CO-05")
    )
    dataset_obs = set(run.dataset_version.members.values_list("observation_id", flat=True))
    assert set(e.observation_ids) <= dataset_obs  # bukti = observasi dalam dataset beku


def test_co_amplification_is_read_from_repost_and_quote_relations(inv, user, target) -> None:
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(
                run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-4000)
            ),
            obs(run, "o1", kind=POST, actor="a0", text="objek satu", published_at=secs(-3000)),
            obs(run, "o2", kind=POST, actor="a0", text="objek dua", published_at=secs(-2900)),
            obs(
                run,
                "x1",
                kind=REPOST,
                actor="u1",
                parent=None,
                reposted_post_id="o1",
                text=None,
                published_at=secs(0),
            ),
            obs(
                run,
                "x2",
                kind=REPOST,
                actor="u2",
                parent=None,
                reposted_post_id="o1",
                text=None,
                published_at=secs(60),
            ),
            obs(
                run,
                "q1",
                kind=SourceObjectType.QUOTE,
                actor="u1",
                parent=None,
                quoted_post_id="o2",
                text="kutipan pertama",
                published_at=secs(100),
            ),
            obs(
                run,
                "q2",
                kind=SourceObjectType.QUOTE,
                actor="u2",
                parent=None,
                quoted_post_id="o2",
                text="kutipan kedua berbeda",
                published_at=secs(130),
            ),
            obs(
                run,
                "x3",
                kind=REPOST,
                actor="u3",
                parent=None,
                reposted_post_id="o1",
                text=None,
                published_at=secs(9000),
            ),
        ],
    )
    out = run_co(user, _dataset(inv, user, [run]))
    assert out.status == AnalysisStatus.COMPLETED, out.error
    edge = _edges(out)[("u1", "u2", "CO-04", "")]
    assert edge.support == 2 and len(edge.observation_ids) == 4
    assert ("u1", "u3", "CO-04", "") not in _edges(out)  # di luar jendela waktu


def test_every_edge_lists_the_alternative_hypotheses_and_the_result_is_not_a_finding(
    inv, user, small
) -> None:
    run = run_co(user, _dataset(inv, user, [small]))
    for e in run.coordination.edges.all():
        assert (
            len(e.alternative_hypotheses) == 5
            and "mobilisasi organik" in e.alternative_hypotheses[0]
        )
        assert e.baseline == {"status": "NOT_COMPUTED"}
    d = run.coordination.definition
    assert d["stance_used"] is False and "bukan temuan" in d["notice"].lower()
    assert len(d["alternative_hypotheses"]) == 4 and d["parameters"]["permutations"] == 0
    names = {f.name for m in (CoordinationNetwork, CoordinationEdge) for f in m._meta.get_fields()}
    for word in (
        "finding",
        "temuan",
        "verdict",
        "vonis",
        "buzzer",
        "score",
        "skor",
        "label",
        "confidence",
    ):
        assert not any(word in n for n in names), word


def test_pair_summary_marks_dependent_evidence(inv, user, small) -> None:
    run = run_co(user, _dataset(inv, user, [small]))
    (pair,) = [
        k
        for k in run.coordination.pair_summary
        if "indicators" in run.coordination.pair_summary[k]
        and "CO-02" in run.coordination.pair_summary[k]["indicators"]
    ]
    groups = run.coordination.pair_summary[pair]["independent_evidence_groups"]
    assert any(
        {"CO-01", "CO-02"} <= set(g) for g in groups
    )  # induk dan balasan yang sama: satu bukti
    edge = _edges(run)[("u1", "u2", "CO-01", "")]
    assert "CO-02" in edge.overlaps_with


def test_repeated_inspections_of_the_same_posts_do_not_double_count(
    inv, user, target, small
) -> None:
    again = new_run(target, user)
    ingest(
        again,
        [
            obs(
                again, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-100)
            ),
            *[
                obs(
                    again,
                    f"u1-{n}",
                    actor="u1",
                    parent=f"p{n}",
                    text="Sudah dijelaskan lengkap di sini baca dulu",
                    published_at=secs(n * 1000 + 10),
                )
                for n in range(3)
            ],
            *[
                obs(
                    again,
                    f"u2-{n}",
                    actor="u2",
                    parent=f"p{n}",
                    text="Sudah dijelaskan lengkap di sini baca dulu",
                    published_at=secs(n * 1000 + 25),
                )
                for n in range(3)
            ],
        ],
    )
    run = run_co(user, _dataset(inv, user, [small, again]))
    assert (
        run.coordination.responses_considered == 10
    )  # 10 Post berbeda (bukan 10 + 6 observasi ulang)
    assert _edges(run)[("u1", "u2", "CO-02", "")].support == 3


def test_the_latest_observation_of_a_post_is_the_one_analysed(inv, user, target, small) -> None:
    edited = new_run(target, user)
    ingest(
        edited,
        [
            obs(
                edited,
                "seed",
                kind=POST,
                actor="a0",
                text="posting target",
                published_at=secs(-100),
            ),
            *[
                obs(
                    edited,
                    f"u2-{n}",
                    actor="u2",
                    parent=f"p{n}",
                    text=f"suntingan sepenuhnya berbeda nomor {n * 7}",
                    published_at=secs(n * 1000 + 25),
                )
                for n in range(3)
            ],
        ],
    )
    before = run_co(user, _dataset(inv, user, [small]))
    after = run_co(user, _dataset(inv, user, [small, edited]))
    assert ("u1", "u2", "CO-03", "") in _edges(before) and ("u1", "u2", "CO-05", "url") in _edges(
        before
    )
    assert ("u1", "u2", "CO-03", "") not in _edges(after)  # teks terbaru u2 tidak lagi mirip
    assert ("u1", "u2", "CO-05", "url") not in _edges(after)
    assert ("u1", "u2", "CO-02", "") in _edges(after)  # waktu balasan tidak berubah


def test_window_unknown_time_and_missing_author_are_counted_not_hidden(inv, user, target) -> None:
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(
                run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-4000)
            ),
            obs(
                run,
                "in1",
                actor="u1",
                parent="seed",
                text="balasan satu cukup panjang",
                published_at=secs(0),
            ),
            obs(
                run,
                "in2",
                actor="u2",
                parent="seed",
                text="balasan dua cukup panjang",
                published_at=None,
            ),
            obs(
                run,
                "early",
                actor="u4",
                parent="seed",
                text="balasan awal cukup panjang",
                published_at=secs(-3000),
            ),
            obs(
                run,
                "edge",
                actor="u5",
                parent="seed",
                text="balasan tepat di batas akhir",
                published_at=secs(1000),
            ),
            obs(
                run,
                "anon",
                actor=None,
                parent="seed",
                identity_needs_verification=True,
                text="anonim cukup panjang",
                published_at=secs(1),
            ),
        ],
    )
    out = run_co(
        user, _dataset(inv, user, [run]), params(window_start=secs(-500), window_end=secs(1000))
    )
    ex = out.coordination.exclusions
    assert (
        ex["responses_outside_window"] == 2
    )  # terlalu awal, dan tepat pada batas akhir (eksklusif)
    assert ex["responses_without_author"] == 1
    assert ex["sync_unknown_time"] == 1
    assert out.coordination.responses_considered == 2
    assert ("u1", "u2", "CO-01", "") in _edges(
        out
    )  # waktu tak diketahui tak menghalangi indikator non-waktu
    assert ("u1", "u2", "CO-02", "") not in _edges(out)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("permutations"),
        lambda p: p.update(extra=1),
        lambda p: p.update(window_start="2026-10-01T00:00:00"),
        lambda p: p.update(window_end=p["window_start"]),
        lambda p: p.update(sync_window_seconds=0),
        lambda p: p.update(sync_window_seconds=86_401),
        lambda p: p.update(sync_min_events=0),
        lambda p: p.update(co_response_min_shared=True),
        lambda p: p.update(similarity_ngram=1),
        lambda p: p.update(similarity_threshold=0),
        lambda p: p.update(similarity_threshold=1.5),
        lambda p: p.update(similarity_threshold=True),
        lambda p: p.update(similarity_threshold=-0.2),
        lambda p: p.update(similarity_max_responses=1),
        lambda p: p.update(amplification_window_seconds=0),
        lambda p: p.update(url_min_shared=0),
        lambda p: p.update(phrase_words=1),
        lambda p: p.update(phrase_words=13),
        lambda p: p.update(phrase_min_shared=0),
        lambda p: p.update(repeated_min_shared_targets=1),
        lambda p: p.update(permutations=5),
        lambda p: p.update(permutations=1001),
        lambda p: p.update(baseline_seed=-1),
        lambda p: p.update(evidence_limit=0),
        lambda p: p.update(max_pair_events=10),
    ],
)
def test_parameters_are_validated_strictly(inv, user, small, mutate) -> None:
    p = params()
    mutate(p)
    with pytest.raises(InvalidParameters):
        run_co(user, _dataset(inv, user, [small]), p, execute=False)


def test_oversized_pair_counts_fail_the_run_instead_of_truncating(inv, user, target) -> None:
    run = new_run(target, user)
    items = [
        obs(run, "seed", kind=POST, actor="a0", text="posting target", published_at=secs(-100))
    ]
    items += [
        obs(
            run,
            f"r{n}",
            actor=f"w{n}",
            parent="seed",
            text=f"teks berbeda nomor {n} untuk uji",
            published_at=secs(n),
        )
        for n in range(50)
    ]
    ingest(run, items)
    failed = run_co(user, _dataset(inv, user, [run]), params(max_pair_events=1000))
    assert failed.status == AnalysisStatus.FAILED and "max_pair_events" in failed.error
    assert not CoordinationNetwork.objects.exists()


def test_baseline_is_stored_with_the_edges_and_is_reproducible(inv, user, small) -> None:
    dataset = _dataset(inv, user, [small])
    a = run_co(user, dataset, params(permutations=30, baseline_seed=4))
    b = run_co(user, dataset, params(permutations=30, baseline_seed=4))
    c = run_co(user, dataset, params(permutations=30, baseline_seed=5))
    assert a.coordination.baseline["CO-02"]["permutations"] == 30
    edge = _edges(a)[("u1", "u2", "CO-02", "")]
    assert edge.baseline["permutations"] == 30 and edge.baseline["statistic"] == "support"
    assert 0 < edge.baseline["p_max_ge"] <= 1 and "exceeds_baseline_p95" in edge.baseline
    assert (
        a.output["result_digest"] == b.output["result_digest"]
        and a.output_digest == b.output_digest
    )
    assert a.coordination.baseline != c.coordination.baseline
    assert a.output["notice"].startswith("Indikator, bukan temuan")


def test_stance_and_m2_play_no_part_so_results_do_not_depend_on_them(inv, user, small) -> None:
    keys = set(params())
    assert not any("stance" in k or "source_run" in k or "assessments" in k for k in keys)


def test_failed_method_leaves_no_rows(inv, user, small, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("rusak")

    monkeypatch.setattr(cr, "run_indicators", boom)
    run = run_co(user, _dataset(inv, user, [small]))
    assert run.status == AnalysisStatus.FAILED and not CoordinationNetwork.objects.exists()


# --- satu platform (AT-13) -----------------------------------------------------------------


def test_AT13_each_network_stays_on_one_platform(inv, user, small) -> None:
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/9")
    trun = new_run(tiktok, user)
    claim = "Sudah dijelaskan lengkap di https://contoh.example/klarifikasi silakan baca dulu"
    ingest(
        trun,
        [
            obs(trun, "root", kind=POST, actor="t0", text="video", published_at=secs(-100)),
            obs(
                trun,
                "c1",
                kind=SourceObjectType.COMMENT,
                actor="u1",
                parent="root",
                text=claim,
                published_at=secs(5),
            ),
            obs(
                trun,
                "c2",
                kind=SourceObjectType.COMMENT,
                actor="u2",
                parent="root",
                text=claim,
                published_at=secs(9),
            ),
        ],
    )
    x = run_co(user, _dataset(inv, user, [small]))
    tt = run_co(user, _dataset(inv, user, [trun]))
    assert x.coordination.platform == "x" and tt.coordination.platform == "tiktok"
    x_actors = {a for e in x.coordination.edges.all() for a in (e.actor_a_id, e.actor_b_id)}
    tt_actors = {a for e in tt.coordination.edges.all() for a in (e.actor_a_id, e.actor_b_id)}
    assert (
        x_actors and tt_actors and not x_actors & tt_actors
    )  # "u1"/"u2" di X dan TikTok = akun berbeda
    assert {ActorAccount.objects.get(pk=a).platform for a in x_actors} == {"x"}
    assert {ActorAccount.objects.get(pk=a).platform for a in tt_actors} == {"tiktok"}


# --- penjaga database -------------------------------------------------------------------------


def _running(user, dataset, method="co-indicators"):
    if method == "co-indicators":
        run = run_co(user, dataset, execute=False)
    else:
        run = services.create_analysis_run(
            dataset=dataset,
            method=method,
            parameters={"top_authors": 1},
            by=user,
            issue_context_version=None,
            target_context_versions=services.latest_target_contexts(dataset),
        )
    AnalysisRun.objects.filter(pk=run.pk).update(status=AnalysisStatus.RUNNING)
    run.refresh_from_db()
    return run


def _network(run, **over):
    fields = dict(
        analysis_run=run,
        platform="x",
        definition={},
        baseline={},
        exclusions={},
        pair_summary={},
        responses_considered=0,
        events=0,
        edge_count=0,
    )
    fields.update(over)
    return CoordinationNetwork(**fields)


def test_network_requires_a_running_coordination_run_and_the_datasets_platform(
    inv, user, small
) -> None:
    dataset = _dataset(inv, user, [small])
    done = run_co(user, dataset)
    with pytest.raises(DatabaseError), transaction.atomic():
        _network(done).save()  # COMPLETED (dan sudah punya jaringan)
    pending = run_co(user, dataset, execute=False)
    with pytest.raises(DatabaseError), transaction.atomic():
        _network(pending).save()
    with pytest.raises(DatabaseError), transaction.atomic():
        _network(
            _running(user, dataset, "dataset-summary")
        ).save()  # RUNNING tetapi bukan indikator
    running = _running(user, dataset)
    with pytest.raises(DatabaseError), transaction.atomic():
        _network(running, platform="tiktok").save()
    _network(running).save()  # kontrol


def test_edges_need_a_running_run_and_same_platform_actors_and_obey_constraints(
    inv, user, small
) -> None:
    dataset = _dataset(inv, user, [small])
    run = _running(user, dataset)
    network = _network(run)
    network.save()
    own = list(ActorAccount.objects.filter(platform="x").order_by("pk"))
    tiktok = register(inv, user, Platform.TIKTOK, "https://www.tiktok.com/@u/video/7")
    trun = new_run(tiktok, user)
    ingest(trun, [obs(trun, "t1", actor="tt-1", parent="tt-root", text="halo")])
    foreign = ActorAccount.objects.get(platform="tiktok", external_actor_id="tt-1")
    xrun = new_run(inv.targets.get(platform="x"), user)
    ingest(
        xrun,
        [obs(xrun, "late", actor="late-x", parent="seed", text="akun x yang dibuat belakangan")],
    )
    late_x = ActorAccount.objects.get(platform="x", external_actor_id="late-x")
    assert (
        foreign.pk < late_x.pk
    )  # agar urutan pasangan (a < b) sah dan yang menolak adalah trigger platform

    def edge(**over):
        fields = dict(
            network=network,
            actor_a=own[0],
            actor_b=own[1],
            indicator="CO-02",
            variant="",
            value=1.0,
            support=1,
            observation_ids=[1],
            detail={},
            explanation="x",
            baseline={},
            overlaps_with=[],
            alternative_hypotheses=[],
        )
        fields.update(over)
        return CoordinationEdge(**fields)

    for bad in (
        {"actor_b": foreign},
        {"actor_a": foreign, "actor_b": late_x},  # akun platform lain (B dan A)
        {"actor_a": own[1], "actor_b": own[0]},  # urutan pasangan
        {"actor_b": own[0]},  # diri sendiri
        {"indicator": "CO-09"},
        {"indicator": "CO-05"},
        {"variant": "url"},  # indikator/varian
        {"support": 0},
        {"value": -1.0},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            edge(**bad).save()
    edge().save()
    edge(indicator="CO-05", variant="url").save()
    with pytest.raises(DatabaseError), transaction.atomic():
        edge().save()  # ganda
    AnalysisRun.objects.filter(pk=run.pk).update(
        status=AnalysisStatus.COMPLETED, output={}, output_digest="a" * 64
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        edge(indicator="CO-06").save()  # run sudah tidak RUNNING


def test_coordination_tables_are_append_only(inv, user, small) -> None:
    run = run_co(user, _dataset(inv, user, [small]))
    ids = {
        "intelligence_coordinationnetwork": run.coordination.pk,
        "intelligence_coordinationedge": run.coordination.edges.first().pk,
    }
    for table, pk in ids.items():
        for sql in (
            f"UPDATE {table} SET id = id WHERE id = %s",
            f"DELETE FROM {table} WHERE id = %s",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute(sql, [pk])


def test_guard_functions_do_not_freeze_a_seqscan_plan() -> None:
    names = ["snr_coordination_network_guard", "snr_coordination_edge_guard"]
    with connection.cursor() as cur:
        cur.execute("SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(%s)", [names])
        found = dict(cur.fetchall())
    assert set(found) == set(names) and all("enable_seqscan=off" in c for c in found.values())


# --- ujung ke ujung pada dataset sintetis WP-2.0 -------------------------------------------------

SYNTH = dict(BASE, permutations=200, baseline_seed=1)


@pytest.fixture(scope="module")
def _bundle():
    return generate()


def test_synthetic_planted_pattern_versus_organic_hard_negatives(inv, user, _bundle) -> None:
    """Parameter ditetapkan SEBELUM melihat hasil. Hasil adalah pilot pada data sintetis, bukan klaim kualitas."""
    runs = _ingest_bundle(inv, user, _bundle)
    out = run_co(user, _dataset(inv, user, runs["x"]), params(**{k: v for k, v in SYNTH.items()}))
    assert out.status == AnalysisStatus.COMPLETED, out.error
    ext = {a.pk: a.external_actor_id for a in ActorAccount.objects.filter(platform="x")}
    group = set(_bundle.ground_truth["accounts"]["planted_group_K"])
    planted = {tuple(sorted(p)) for p in itertools.combinations(sorted(group), 2)}
    flagged: dict[tuple[str, str], set[str]] = {}
    for e in out.coordination.edges.all():
        if e.baseline["exceeds_baseline_p95"]:
            pair = tuple(sorted((ext[e.actor_a_id], ext[e.actor_b_id])))
            flagged.setdefault(pair, set()).add(
                e.indicator + (f":{e.variant}" if e.variant else "")
            )
    timing = {p for p, kinds in flagged.items() if kinds & {"CO-02", "CO-04"}}
    assert (
        timing and timing <= planted
    )  # waktu/amplifikasi serentak hanya melampaui baseline pada kelompok yang ditanam
    assert len(timing) >= 5
    # hard negative organik: ledakan balasan awal (CO-02) dan tautan populer (CO-05:url) tidak melampaui baseline
    truth = {
        oid: v
        for t in _bundle.ground_truth["targets"].values()
        for oid, v in t["observations"].items()
    }
    shared_url_actors = {v["actor"] for v in truth.values() if v["group"] == "organic-shared-url"}
    assert not any(
        "CO-05:url" in kinds and set(p) <= shared_url_actors for p, kinds in flagged.items()
    )
    # BATAS YANG DIKETAHUI: templat klaim yang sama pada akun organik membuat CO-05:phrase melampaui baseline
    # (hipotesis alternatif "penyalinan konten publik"); inilah mengapa indikator bukan temuan.
    non_planted = {p: k for p, k in flagged.items() if p not in planted}
    assert all(kinds == {"CO-05:phrase"} for kinds in non_planted.values())
    assert out.output["beyond_baseline_edges"] > 0
    again = run_co(user, _dataset(inv, user, runs["x"]), params(**SYNTH))
    assert again.output["result_digest"] == out.output["result_digest"]
    # platform lain: tidak ada indikator lintas platform
    tt = run_co(user, _dataset(inv, user, runs["tiktok"]), params(**{**SYNTH, "permutations": 20}))
    assert tt.coordination.platform == "tiktok"
    tt_actors = {a for e in tt.coordination.edges.all() for a in (e.actor_a_id, e.actor_b_id)}
    assert not tt_actors & set(ext)
