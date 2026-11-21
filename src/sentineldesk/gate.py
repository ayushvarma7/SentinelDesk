"""The escalation gate: deterministic rules, no LLM in the decision path.

Every rule returns a sentence a human can read off the badge, which is the whole
point — you can explain any escalation on stage in one line.
"""
from __future__ import annotations

import re

from . import config
from .generate import unsupported_figures  # noqa: F401  (P2 implements, gate re-exports)
from .schema import Precedent, Prediction, RootCause

_ACTION_RE = [re.compile(p, re.I) for p in config.UNSUPPORTED_ACTION_PATTERNS]
_INJECTION_RE = [re.compile(p, re.I) for p in config.PROMPT_INJECTION_PATTERNS]


def evaluate(
    text: str,
    type_: Prediction,
    queue: Prediction,
    priority: Prediction,
    precedents: list[Precedent],
    thresholds: dict | None = None,
    root_cause: RootCause | None = None,
) -> tuple[bool, list[str]]:
    """Return (escalate, reasons). Reasons are empty iff escalate is False."""
    t = thresholds or {}
    min_conf = t.get("min_confidence", config.MIN_CONFIDENCE)
    min_top1 = t.get("min_top1_similarity", config.MIN_TOP1_SIMILARITY)
    min_mean3 = t.get("min_mean_top3_similarity", config.MIN_MEAN_TOP3_SIMILARITY)

    reasons: list[str] = []

    # 1. The brief's hard rule. EDA: fires on 17.2% of tickets on its own.
    #    Incident and Problem both mean "service is broken" (Problem = the root cause of incidents),
    #    and the classifier confuses them, so both count (config.CRITICAL_TYPES).
    if priority.label == "high" and type_.label in config.CRITICAL_TYPES:
        reasons.append(f"Critical issue (high priority + {type_.label}) — on-call required")

    # 2. Low classifier confidence on any head.
    for name, pred in (("type", type_), ("queue", queue), ("priority", priority)):
        floor = min_conf.get(name, 0.5)
        if pred.confidence < floor:
            reasons.append(
                f"Low classifier confidence ({name}: {pred.confidence:.2f} < {floor:.2f})"
            )

    # 3 & 4. No precedent to ground a reply in.
    if not precedents:
        reasons.append("No historical precedent retrieved")
    else:
        top1 = precedents[0].score
        if top1 < min_top1:
            reasons.append(
                f"No sufficiently similar precedent (best match {top1:.4f} < {min_top1:.4f})"
            )
        top3 = [p.score for p in precedents[:3]]
        mean3 = sum(top3) / len(top3)
        if mean3 < min_mean3:
            reasons.append(f"Weak precedent support (mean top-3 {mean3:.3f} < {min_mean3:.3f})")

    # 5. Commitments we cannot make unless a past resolution made them too.
    if any(r.search(text) for r in _ACTION_RE):
        evidence = " ".join(p.answer.lower() for p in precedents)
        if not any(r.search(evidence) for r in _ACTION_RE):
            reasons.append("Requests an action with no supporting historical precedent")

    # 5b. Several live issues share one root cause: likely a wider outage, needs a Problem record.
    if root_cause is not None and root_cause.suggest_problem:
        reasons.append(f"Probable shared root cause: {root_cause.group_size} similar issues in the last "
                       f"{config.ROOT_CAUSE_WINDOW_MIN} min — raise a Problem record")

    # 6. Out of scope / adversarial.
    if any(r.search(text) for r in _INJECTION_RE):
        reasons.append("Out of scope: instruction-override attempt detected")

    return bool(reasons), reasons
