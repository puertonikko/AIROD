"""Core data structures shared across the system.

These are plain dataclasses; persistence lives in ``memory.py``. Keeping them
free of storage concerns makes them easy to pass between agents and to serialize
for prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ClaimStatus(str, Enum):
    """Where a claim stands after the Judge has scored it."""

    SUPPORTED = "supported"
    CONTESTED = "contested"
    UNSUPPORTED = "unsupported"


class HypothesisStatus(str, Enum):
    ACTIVE = "active"        # still in play
    ADVANCED = "advanced"    # had a supported claim this round
    OPEN_QUESTION = "open_question"  # demoted; needs data we don't have
    REJECTED = "rejected"    # judged not worth pursuing


@dataclass
class Evidence:
    """A quoted passage that bears on a claim. Quote, not summary."""

    source: str          # where it came from (filename / url)
    quote: str           # the exact supporting text
    relevance: str = ""  # one line on why it matters

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Claim:
    """A single assertion inside a hypothesis, scored against its evidence."""

    text: str
    evidence: list[Evidence] = field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNSUPPORTED

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Critique:
    """An objection raised by the Critic or Skeptic."""

    author_role: str     # "critic" | "skeptic" (kept out of the Judge's view)
    text: str
    leverage: int = 0    # how load-bearing the attacked assumption is (higher = worse)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Hypothesis:
    """One proposed answer under investigation."""

    statement: str
    prediction: str = ""           # the specific, checkable prediction
    claims: list[Claim] = field(default_factory=list)
    critiques: list[Critique] = field(default_factory=list)
    confidence: float = 0.0        # Judge's 0-1 confidence
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    round_index: int = 0
    id: int | None = None
    # Optional machine-runnable artifact + its oracle result (e.g. a trading
    # strategy spec and its backtest metrics). Empty for non-tool missions.
    strategy: dict[str, Any] = field(default_factory=dict)
    backtest: dict[str, Any] = field(default_factory=dict)

    def supported_claims(self) -> list[Claim]:
        return [c for c in self.claims if c.status == ClaimStatus.SUPPORTED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "prediction": self.prediction,
            "claims": [c.to_dict() for c in self.claims],
            "critiques": [c.to_dict() for c in self.critiques],
            "confidence": self.confidence,
            "status": self.status.value,
            "round_index": self.round_index,
            "strategy": self.strategy,
            "backtest": self.backtest,
        }


@dataclass
class Mission:
    """The central task the R&D team works toward."""

    title: str
    goal: str
    success_criteria: list[str] = field(default_factory=list)
    budget_usd: float = 5.0
    stall_rounds: int = 2
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
