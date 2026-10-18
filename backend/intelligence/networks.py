"""Jaringan interaksi + tampilan stance sebagai metode AnalysisRun (WP-2.4; ADR 0028).

Membaca relasi yang SUDAH tersimpan pada dataset beku (tanpa mengambil data). Bila `source_run`
(run M2 selesai) diberikan, stance respons ditambahkan sebagai ATRIBUT node/edge; hash penilaian
dikunci pada parameter seperti M3 agar run dapat diulang persis. Semua aturan (jenis relasi, bobot,
jendela waktu, kebijakan waktu tak diketahui, parameter komunitas) adalah parameter eksplisit.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from collection.models import ActorAccount, PostObservation, PostRelation
from investigations.models import Proposition

from .assessment import current_assessments
from .digest import digest_ids, digest_json
from .errors import InvalidParameters
from .m4 import (
    RELATION_TYPES,
    UNKNOWN_TIME_POLICIES,
    WEIGHTINGS,
    NetworkParams,
    RelationRecord,
    build_network,
    stance_summary,
)
from .models import AnalysisRun, AnalysisStatus, GraphEdge, GraphNode, GraphProjection
from .profiles import current_assessment_ids

_KEYS = {
    "source_run",
    "assessments_digest",
    "proposition_id",
    "window_start",
    "window_end",
    "unknown_time",
    "relation_types",
    "weighting",
    "resolution",
    "seed",
    "compute_betweenness",
    "metrics_max_nodes",
    "stability_seeds",
}
_BATCH = 1000


def network_parameters(
    *,
    window_start: datetime,
    window_end: datetime,
    unknown_time: str,
    relation_types: list[str],
    weighting: str,
    resolution: float,
    seed: int,
    compute_betweenness: bool,
    metrics_max_nodes: int,
    stability_seeds: int,
    source_run: AnalysisRun | None = None,
    proposition: Proposition | None = None,
) -> dict[str, Any]:
    """Susun parameter run M4. Dengan `source_run`, hash penilaian M2 yang berlaku ikut dikunci."""
    stance_view = source_run is not None and proposition is not None
    return {
        "source_run": source_run.pk if stance_view and source_run else None,
        "assessments_digest": (
            digest_ids(current_assessment_ids(source_run, proposition.pk))
            if stance_view and source_run and proposition
            else None
        ),
        "proposition_id": proposition.pk if stance_view and proposition else None,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "unknown_time": unknown_time,
        "relation_types": relation_types,
        "weighting": weighting,
        "resolution": resolution,
        "seed": seed,
        "compute_betweenness": compute_betweenness,
        "metrics_max_nodes": metrics_max_nodes,
        "stability_seeds": stability_seeds,
    }


def _time(parameters: Mapping[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(parameters[key]))
    except ValueError:
        raise InvalidParameters(f"{key} bukan waktu ISO-8601") from None
    if value.tzinfo is None:
        raise InvalidParameters(f"{key} wajib memuat zona waktu")
    return value


def _parse(
    parameters: Mapping[str, Any],
) -> tuple[NetworkParams, int | None, int | None, str | None]:
    if set(parameters) != _KEYS:
        raise InvalidParameters(f"parameter wajib tepat: {sorted(_KEYS)}")
    stance_keys = [parameters[k] for k in ("source_run", "assessments_digest", "proposition_id")]
    if any(v is None for v in stance_keys) and not all(v is None for v in stance_keys):
        raise InvalidParameters(
            "source_run, assessments_digest, proposition_id harus diisi semua atau kosong semua"
        )
    source_run, digest, proposition_id = stance_keys
    if source_run is not None:
        for key, value in (("source_run", source_run), ("proposition_id", proposition_id)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise InvalidParameters(f"{key} harus bilangan bulat positif")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise InvalidParameters("assessments_digest harus SHA-256 heksadesimal")
    start, end = _time(parameters, "window_start"), _time(parameters, "window_end")
    if end <= start:
        raise InvalidParameters("window_end harus setelah window_start")
    if parameters["unknown_time"] not in UNKNOWN_TIME_POLICIES:
        raise InvalidParameters(f"unknown_time harus salah satu dari {UNKNOWN_TIME_POLICIES}")
    types = parameters["relation_types"]
    if (
        not isinstance(types, list)
        or not types
        or len(set(types)) != len(types)
        or any(t not in RELATION_TYPES for t in types)
    ):
        raise InvalidParameters(f"relation_types: subset tak kosong dari {RELATION_TYPES}")
    if parameters["weighting"] not in WEIGHTINGS:
        raise InvalidParameters(f"weighting harus salah satu dari {WEIGHTINGS}")
    resolution = parameters["resolution"]
    if (
        isinstance(resolution, bool)
        or not isinstance(resolution, int | float)
        or not 0.1 <= resolution <= 10
    ):
        raise InvalidParameters("resolution harus angka 0.1..10")
    seed = parameters["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
        raise InvalidParameters("seed harus bilangan bulat 0..2^31-1")
    if not isinstance(parameters["compute_betweenness"], bool):
        raise InvalidParameters("compute_betweenness harus boolean")
    limit = parameters["metrics_max_nodes"]
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100_000:
        raise InvalidParameters("metrics_max_nodes harus bilangan bulat 1..100000")
    stability = parameters["stability_seeds"]
    if (
        isinstance(stability, bool)
        or not isinstance(stability, int)
        or not (stability == 0 or 2 <= stability <= 100)
    ):
        raise InvalidParameters("stability_seeds harus 0 (tidak diukur) atau bilangan bulat 2..100")
    return (
        NetworkParams(
            window_start=start,
            window_end=end,
            unknown_time=parameters["unknown_time"],
            relation_types=tuple(types),
            weighting=parameters["weighting"],
            resolution=float(resolution),
            seed=seed,
            compute_betweenness=parameters["compute_betweenness"],
            metrics_max_nodes=limit,
            stability_seeds=stability,
        ),
        source_run,
        proposition_id,
        digest,
    )


def validate_m4_parameters(parameters: Mapping[str, Any]) -> None:
    _parse(parameters)


def _stances(source_id: int, proposition_id: int, digest: str, run: AnalysisRun) -> dict[int, str]:
    source = AnalysisRun.objects.filter(pk=source_id).first()
    if (
        source is None
        or not source.method.startswith("m2-")
        or source.status != AnalysisStatus.COMPLETED
        or source.dataset_version_id != run.dataset_version_id
    ):
        raise InvalidParameters("source_run harus run M2 selesai pada dataset yang sama")
    if not Proposition.objects.filter(pk=proposition_id).exists():
        raise InvalidParameters(f"proposition tidak ditemukan: {proposition_id}")
    rows = list(
        current_assessments(source)
        .filter(proposition_id=proposition_id)
        .values_list("pk", "observation_id", "issue_stance")
    )
    if digest_ids(pk for pk, _, _ in rows) != digest:
        raise InvalidParameters(
            "penilaian M2 berubah sejak run dibuat (mis. ada tinjauan baru); buat run baru"
        )
    return {obs: stance for _, obs, stance in rows}


def run_m4_network(frozen: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    params, source_id, proposition_id, digest = _parse(parameters)
    run = AnalysisRun.objects.select_related("dataset_version").get(pk=frozen.run_id)
    dataset = run.dataset_version
    stance_by_obs: dict[int, str] = {}
    if source_id is not None and proposition_id is not None and digest is not None:
        stance_by_obs = _stances(source_id, proposition_id, digest, run)
    stance_view = source_id is not None

    observations: list[dict[str, Any]] = [
        dict(o)
        for o in PostObservation.objects.filter(id__in=frozen.observation_ids).values(
            "id", "post_id", "run_id", "run__sequence", "author_id", "published_at"
        )
    ]
    by_run_post = {(o["run_id"], o["post_id"]): o for o in observations}
    latest_by_post: dict[int, dict[str, Any]] = {}
    for o in sorted(observations, key=lambda o: (o["run__sequence"], o["id"])):
        latest_by_post[o["post_id"]] = o
    author_ids = {o["author_id"] for o in observations if o["author_id"] is not None}
    platform_ok = set(
        ActorAccount.objects.filter(pk__in=author_ids, platform=dataset.platform).values_list(
            "pk", flat=True
        )
    )
    if author_ids - platform_ok:
        raise InvalidParameters("akun dari platform lain tidak boleh masuk graf ini")

    # semua jenis relasi dibaca; yang tidak dipilih dihitung sebagai pengecualian
    relations = PostRelation.objects.filter(run_id__in={o["run_id"] for o in observations}).values(
        "id", "run_id", "from_post_id", "relation_type", "to_post_id", "to_actor_id"
    )
    records: list[RelationRecord] = []
    outside_dataset = 0
    for rel in relations:
        origin = by_run_post.get((rel["run_id"], rel["from_post_id"]))
        if origin is None:
            outside_dataset += 1
            continue
        if rel["to_actor_id"] is not None:
            to_actor = rel["to_actor_id"]
        else:
            parent = by_run_post.get((rel["run_id"], rel["to_post_id"])) or latest_by_post.get(
                rel["to_post_id"]
            )
            to_actor = parent["author_id"] if parent else None
        records.append(
            RelationRecord(
                relation_id=rel["id"],
                relation_type=rel["relation_type"],
                from_actor=origin["author_id"],
                to_actor=to_actor,
                from_observation_id=origin["id"],
                published_at=origin["published_at"],
                stance=stance_by_obs.get(origin["id"]),
            )
        )

    node_attributes: dict[int, dict[str, Any]] = {}
    stance_counts: dict[int, Counter] = defaultdict(Counter)
    per_actor = Counter(o["author_id"] for o in observations if o["author_id"] is not None)
    for o in observations:
        if o["author_id"] is not None and o["id"] in stance_by_obs:
            stance_counts[o["author_id"]][stance_by_obs[o["id"]]] += 1
    for actor, count in per_actor.items():
        attrs: dict[str, Any] = {"observations": count}
        if stance_view:
            counts = dict(sorted(stance_counts[actor].items()))
            attrs.update(
                responses_assessed=sum(counts.values()),
                stance_counts=counts,
                stance_summary=stance_summary(counts),
            )
        node_attributes[actor] = attrs

    network = build_network(records, sorted(per_actor), node_attributes, params)
    unknown_actors = ActorAccount.objects.filter(pk__in=network.nodes).exclude(
        platform=dataset.platform
    )
    if unknown_actors.exists():
        raise InvalidParameters("akun dari platform lain tidak boleh masuk graf ini")
    exclusions = dict(sorted(network.exclusions.items()))
    if outside_dataset:
        exclusions["relation_origin_not_in_dataset"] = outside_dataset
    definition = {
        "node": "ActorAccount pada satu platform (penulis dalam dataset, akun yang dituju)",
        "edge": "relasi teramati dari penulis ke akun yang dituju; digabung per (dari, ke, jenis)",
        "direction": "dari akun penulis ke akun yang dituju",
        "relation_types": list(params.relation_types),
        "weighting": params.weighting,
        "weight_rule": (
            "jumlah observasi berbeda pembentuk edge"
            if params.weighting == "count"
            else "1 per edge"
        ),
        "window": {"start": params.window_start.isoformat(), "end": params.window_end.isoformat()},
        "unknown_time": params.unknown_time,
        "stance_view": stance_view,
        "stance_rule": "stance hanya atribut node/edge; stance yang sama tidak membuat edge",
        "proposition_id": proposition_id,
        "source_analysis_run": source_id,
        "dataset_version": dataset.number,
        "parameters": parameters,
    }
    projection = GraphProjection.objects.create(
        analysis_run=run,
        platform=dataset.platform,
        definition=definition,
        metrics=network.metrics,
        exclusions=exclusions,
        node_count=len(network.nodes),
        edge_count=len(network.edges),
    )
    nodes = {
        actor: GraphNode(
            projection=projection,
            actor_id=actor,
            attributes={k: v for k, v in attrs.items() if k != "metrics"},
            metrics=attrs.get("metrics", {}),
        )
        for actor, attrs in network.nodes.items()
    }
    GraphNode.objects.bulk_create(nodes.values(), batch_size=_BATCH)
    GraphEdge.objects.bulk_create(
        (
            GraphEdge(
                projection=projection,
                from_node=nodes[e.from_actor],
                to_node=nodes[e.to_actor],
                relation_type=e.relation_type,
                weight=e.weight,
                observation_ids=list(e.observation_ids),
                stance_counts=e.stance_counts,
                first_published_at=e.first_published_at,
                last_published_at=e.last_published_at,
            )
            for e in network.edges
        ),
        batch_size=_BATCH,
    )
    signature = (
        [
            (e.from_actor, e.to_actor, e.relation_type, e.weight, list(e.observation_ids))
            for e in network.edges
        ],
        {a: (n.get("stance_summary"), n["metrics"]) for a, n in sorted(network.nodes.items())},
    )
    return {
        "nodes": len(network.nodes),
        "edges": len(network.edges),
        "exclusions": exclusions,
        "stance_view": stance_view,
        "community_detection": network.metrics["community_detection"],
        "graph_digest": digest_json(signature),
    }


def register() -> None:
    from .methods import REGISTRY, Method

    REGISTRY["m4-network"] = Method("m4-network", "1", validate_m4_parameters, run_m4_network)
