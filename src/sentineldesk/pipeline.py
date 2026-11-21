"""The contract every track codes against: raw ticket in, TriageResult out.

Right now `triage()` returns plausible fake data so Track D can build the whole
console before a single model exists. Replace one stage at a time by flipping
its entry in STAGES — never by changing the signature.
"""
from __future__ import annotations

import time

from . import gate, pii
from .text import build_text
from .schema import Precedent, Prediction, TriageResult

# Flip each to True as that track lands. Keeps the app runnable the whole way.
STAGES = {
    "embed": False,
    "classify": False,
    "retrieve": False,
    "generate": False,
}


def _stub_predictions() -> dict[str, Prediction]:
    return {
        "type": Prediction("Incident", 0.81, {"Incident": 0.81, "Request": 0.11,
                                              "Problem": 0.05, "Change": 0.03}),
        "queue": Prediction("Technical Support", 0.64, {"Technical Support": 0.64,
                                                        "IT Support": 0.21}),
        "priority": Prediction("high", 0.58, {"high": 0.58, "medium": 0.30, "low": 0.12}),
        "language": Prediction("en", 0.99, {"en": 0.99, "de": 0.01}),
    }


def _stub_precedents() -> list[Precedent]:
    return [
        Precedent("TKT-01234", 0.88, "VPN connection drops",
                  "Users report the VPN tunnel dropping every few minutes...",
                  "We identified a stale IKE policy on the concentrator and rotated it. "
                  "Service was restored within 40 minutes.", "en", "Technical Support"),
        Precedent("TKT-04567", 0.79, "Remote access unavailable",
                  "Remote access has been unavailable since this morning...",
                  "Root cause was an expired certificate on the gateway. Replaced and "
                  "monitored for 24h.", "en", "IT Support"),
    ]


def triage(subject: str | None, body: str | None,
           thresholds: dict | None = None) -> TriageResult:
    """Triage one ticket. Safe on null subject, null body, and arbitrary length."""
    t0 = time.perf_counter()
    latency: dict[str, float] = {}

    text = build_text(subject, body)
    masked_text, masked_counts = pii.mask(text)

    t = time.perf_counter()
    preds = _stub_predictions()          # TODO Track A + B
    latency["classify"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    precedents = _stub_precedents()      # TODO Track B
    latency["retrieve"] = (time.perf_counter() - t) * 1000

    escalate, reasons = gate.evaluate(
        text, preds["type"], preds["queue"], preds["priority"], precedents, thresholds
    )

    t = time.perf_counter()
    if escalate:
        draft_reply, cited, unverified = None, [], []
    else:
        draft_reply = "[stub draft — Track C]"   # TODO Track C
        cited, unverified = [p.ticket_id for p in precedents], []
    latency["generate"] = (time.perf_counter() - t) * 1000
    latency["total"] = (time.perf_counter() - t0) * 1000

    return TriageResult(
        language=preds["language"].label,
        type=preds["type"],
        queue=preds["queue"],
        priority=preds["priority"],
        escalate=escalate,
        escalation_reasons=reasons,
        precedents=precedents,
        draft_reply=draft_reply,
        cited_ticket_ids=cited,
        unverified_claims=unverified,
        masked_pii=masked_counts,
        latency_ms=latency,
    )
