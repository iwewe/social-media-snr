"""Rantai percakapan nyata untuk M2 (FR-050; AT-08): induk SESUNGGUHNYA, bukan selalu seed.

Membaca observasi dan relasi `reply_to` yang sudah tersimpan untuk satu dataset beku; tidak
mengambil data dari platform (FR-041).
"""

from collections.abc import Iterable
from dataclasses import dataclass

from collection.models import PostObservation, PostRelation, RelationType

MAX_DEPTH = 50


@dataclass(frozen=True)
class Node:
    observation_id: int
    post_id: int
    run_id: int
    run_sequence: int
    source_type: str
    text: str | None
    parent_unknown: bool


@dataclass(frozen=True)
class Chain:
    """`parents`: induk terdekat lebih dulu; `parent_unknown` bila induk tidak dapat dilacak."""

    parents: tuple[Node, ...]
    parent_unknown: bool

    @property
    def depth(self) -> int:
        return len(self.parents)


class ConversationIndex:
    def __init__(self, observation_ids: Iterable[int]) -> None:
        ids = list(observation_ids)
        self.nodes: dict[int, Node] = {}
        by_post: dict[int, list[Node]] = {}
        rows = PostObservation.objects.filter(id__in=ids).values_list(
            "id",
            "post_id",
            "run_id",
            "run__sequence",
            "source_object_type",
            "text",
            "parent_unknown",
        )
        for oid, post_id, run_id, seq, kind, text, unknown in rows:
            node = Node(oid, post_id, run_id, seq, kind, text, unknown)
            self.nodes[oid] = node
            by_post.setdefault(post_id, []).append(node)
        self._by_post = {
            post: sorted(nodes, key=lambda n: (n.run_sequence, n.observation_id))
            for post, nodes in by_post.items()
        }
        run_ids = {n.run_id for n in self.nodes.values()}
        self._parent_post: dict[tuple[int, int], int] = {
            (run, frm): to
            for run, frm, to in PostRelation.objects.filter(
                run_id__in=run_ids, relation_type=RelationType.REPLY_TO
            ).values_list("run_id", "from_post_id", "to_post_id")
            if to is not None
        }

    def parent_post_id(self, observation_id: int) -> int | None:
        node = self.nodes[observation_id]
        return self._parent_post.get((node.run_id, node.post_id))

    def _parent_of(self, node: Node) -> Node | None:
        parent_post = self._parent_post.get((node.run_id, node.post_id))
        if parent_post is None:
            return None
        candidates = self._by_post.get(parent_post, [])
        same_run = [c for c in candidates if c.run_id == node.run_id]
        pool = same_run or candidates
        return pool[-1] if pool else None

    def chain(self, observation_id: int) -> Chain:
        node = self.nodes[observation_id]
        parents: list[Node] = []
        seen = {node.post_id}
        unknown = node.parent_unknown
        current = node
        while len(parents) < MAX_DEPTH:
            has_relation = (current.run_id, current.post_id) in self._parent_post
            parent = self._parent_of(current)
            if parent is None:
                # tanpa induk teramati: tidak dapat dilacak bila respons itu sendiri tak punya
                # relasi induk, atau relasinya menunjuk induk yang tidak ada di dataset
                unknown = unknown or current is node or has_relation
                break
            if parent.post_id in seen:  # lingkaran: berhenti, tandai tidak dapat dilacak
                unknown = True
                break
            seen.add(parent.post_id)
            parents.append(parent)
            current = parent
        else:
            unknown = True
        return Chain(tuple(parents), unknown)
