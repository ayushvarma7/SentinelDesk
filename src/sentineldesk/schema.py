"""The interface contract. Every track codes against these types.

Nothing in here imports a model, so it stays importable while the rest is
half-built. Change a field only by telling the whole team.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Prediction:
    """One classifier head's output."""
    label: str
    confidence: float
    all_probs: dict[str, float] = field(default_factory=dict)


@dataclass
class Precedent:
    """A retrieved historical ticket from the KB split."""
    ticket_id: str
    score: float
    subject: str
    body_snippet: str
    answer: str
    language: str
    queue: str


@dataclass
class TriageResult:
    """Everything the console renders for one incoming ticket."""
    language: str
    type: Prediction
    queue: Prediction
    priority: Prediction

    escalate: bool
    escalation_reasons: list[str]          # human-readable, shown on the badge

    precedents: list[Precedent]

    draft_reply: str | None                # None when escalated
    cited_ticket_ids: list[str]
    unverified_claims: list[str]           # numbers/policies absent from the evidence

    masked_pii: dict[str, int]             # {"email": 2, "ip": 1}
    latency_ms: dict[str, float]           # embed / classify / retrieve / generate / total

    # Which path produced the draft: the model name, "extractive-fallback", or
    # None when the ticket was escalated and no draft was written.
    engine: str | None = None

    @property
    def overall_confidence(self) -> float:
        """A ticket is only as trustworthy as its least certain head."""
        return min(self.type.confidence, self.queue.confidence, self.priority.confidence)
