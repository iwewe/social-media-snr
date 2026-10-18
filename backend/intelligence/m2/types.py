"""Tipe masukan/keluaran klasifier M2. Murni (tanpa Django): dapat diuji dan dievaluasi tanpa basis
data."""

from dataclasses import dataclass, field
from typing import Any

from .taxonomy import Character, IssueStance, NarrativeFunction, Sentiment, TargetAlignment


@dataclass(frozen=True)
class ParentTurn:
    """Satu giliran pada rantai induk. `stance` = stance giliran itu terhadap proposition yang
    sedang
    dinilai (stance awal target untuk posting target; hasil klasifikasi untuk balasan); None = tidak
    diketahui."""

    text: str | None
    stance: IssueStance | None = None
    observation_id: int | None = None


@dataclass(frozen=True)
class PropositionRef:
    label: str
    statement: str
    id: int | None = None


@dataclass(frozen=True)
class ClassifierInput:
    """Rantai induk terdekat lebih dulu: induk langsung, induknya, ... sampai posting target."""

    text: str | None
    parent_chain: tuple[ParentTurn, ...]
    proposition: PropositionRef
    parent_unknown: bool = False

    @property
    def direct_parent(self) -> ParentTurn | None:
        return self.parent_chain[0] if self.parent_chain else None


@dataclass(frozen=True)
class Assessment:
    issue_stance: IssueStance
    target_alignment: TargetAlignment
    response_character: tuple[Character, ...]
    expression_sentiment: Sentiment | None = None
    narrative_function: NarrativeFunction | None = None
    needs_human_review: bool = False
    basis: dict[str, Any] = field(default_factory=dict)
