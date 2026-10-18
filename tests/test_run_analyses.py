"""WP-2.7a: perintah operator run_analyses."""

from io import StringIO

import pytest
from collection.contracts import SourceObjectType
from collection_helpers import ingest, new_run, obs, register
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from intelligence.models import AnalysisRun
from investigations import services as inv_services
from investigations.enums import Platform, TargetType

pytestmark = pytest.mark.django_db
POST = SourceObjectType.POST


@pytest.fixture
def world():
    user = User.objects.create_user("operator", password="x")
    inv = inv_services.create_investigation(user=user, name="Demo")
    issue = inv_services.create_issue(investigation=inv, user=user, title="Isu")
    prop = inv_services.add_proposition(issue=issue, user=user, statement="Perlu diaudit.")
    target = inv_services.register_target(
        investigation=inv,
        user=user,
        platform=Platform.X,
        target_type=TargetType.POST,
        url="https://x.com/u/status/1",
        stances={prop: "CONTRA"},
    )
    run = new_run(target, user)
    ingest(
        run,
        [
            obs(run, "seed", kind=POST, actor="a0", text="Perusahaan tidak perlu diaudit."),
            obs(run, "r1", actor="u1", parent="seed", text="Justru audit harus dilakukan."),
            obs(run, "r2", actor="u2", parent="seed", text="Perusahaan itu tidak perlu diaudit."),
        ],
    )
    return user, inv, prop


def call(inv, prop, *extra, user="operator"):
    out = StringIO()
    call_command(
        "run_analyses",
        "--investigation",
        str(inv.pk),
        "--proposition",
        str(prop.pk),
        "--user",
        user,
        *extra,
        stdout=out,
    )
    return out.getvalue()


def test_runs_the_four_analyses_with_explicit_example_parameters(world) -> None:
    _, inv, prop = world
    output = call(
        inv,
        prop,
        "--exploratory",
        "--pro-cue",
        "audit harus dilakukan",
        "--contra-cue",
        "tidak perlu diaudit",
    )
    assert "CONTOH" in output
    runs = {r.method: r for r in AnalysisRun.objects.filter(investigation=inv)}
    assert set(runs) == {"m2-rules", "m3-profile", "m4-network", "co-indicators"}
    assert all(r.status == "COMPLETED" for r in runs.values())
    assert runs["m2-rules"].parameters["propositions"][str(prop.pk)]["pro_cues"] == [
        "audit harus dilakukan"
    ]
    assert runs["m4-network"].parameters["stability_seeds"] == 10
    assert runs["co-indicators"].parameters["permutations"] == 100
    assert len({r.dataset_version_id for r in runs.values()}) == 1


def test_refuses_without_the_exploratory_acknowledgement_and_without_cues(world) -> None:
    _, inv, prop = world
    with pytest.raises(CommandError, match="--exploratory"):
        call(inv, prop, "--pro-cue", "x")
    with pytest.raises(CommandError, match="pro-cue"):
        call(inv, prop, "--exploratory")
    assert not AnalysisRun.objects.exists()


def test_rejects_unknown_objects_and_investigations_without_ingested_runs(world) -> None:
    user, inv, prop = world
    with pytest.raises(CommandError, match="tidak ditemukan"):
        call(inv, prop, "--exploratory", "--pro-cue", "x", user="tidak-ada")
    other = inv_services.create_investigation(user=user, name="Kosong")
    other_issue = inv_services.create_issue(investigation=other, user=user, title="Isu lain")
    other_prop = inv_services.add_proposition(issue=other_issue, user=user, statement="Klaim lain")
    with pytest.raises(CommandError, match="Tidak ada pemeriksaan"):
        call(other, other_prop, "--exploratory", "--pro-cue", "x")
    with pytest.raises(CommandError, match="tidak ditemukan"):
        call(
            inv, other_prop, "--exploratory", "--pro-cue", "x"
        )  # proposition milik investigasi lain
    _ = register
