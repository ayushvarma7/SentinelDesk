"""The contract every track codes against: raw ticket in, TriageResult out.

Right now `triage()` returns plausible fake data so Track D can build the whole
console before a single model exists. Replace one stage at a time by flipping
its entry in STAGES — never by changing the signature.
"""
from __future__ import annotations

import time

from . import config, gate, pii
from .text import build_text
from .schema import Precedent, Prediction, TriageResult

# Flip each to True as that track lands. Keeps the app runnable the whole way.
STAGES = {
    "embed": True,       # Track A wired embed.encode (Track B owns the file)
    "classify": True,    # Track A: falls back to the stub if artifacts/heads.joblib is missing
    "retrieve": True,    # Track B: real index, stub fallback if artifacts are missing
    "generate": True,    # Track C: Gemini when a key exists, extractive fallback otherwise
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

    # Embed once; the same query vector feeds the classifier and (later) retrieval.
    # Classification runs locally on the unmasked text; masking matters before external LLM calls.
    qvec = None
    t = time.perf_counter()
    if STAGES["embed"]:
        from . import embed
        qvec = embed.encode([text], is_query=True)[0]
    latency["embed"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    if STAGES["classify"] and qvec is not None and config.HEADS_PATH.exists():
        from . import classify
        preds = classify.predict(qvec, text)
    else:
        preds = _stub_predictions()
    latency["classify"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    if STAGES["retrieve"] and qvec is not None:
        from . import retrieve
        if retrieve.is_ready():
            precedents = retrieve.search(qvec, config.TOP_K, preds["queue"].label,
                                         language=preds["language"].label)
        else:
            precedents = _stub_precedents()   # index not built yet
    else:
        precedents = _stub_precedents()
    latency["retrieve"] = (time.perf_counter() - t) * 1000

    # Root cause (Track A): only for issues (Incident/Problem), only with a real embedding.
    root_cause = None
    t = time.perf_counter()
    if qvec is not None and preds["type"].label in config.CRITICAL_TYPES:
        from . import rootcause
        root_cause = rootcause.analyze(qvec, text)
    latency["root_cause"] = (time.perf_counter() - t) * 1000

    escalate, reasons = gate.evaluate(
        text, preds["type"], preds["queue"], preds["priority"], precedents, thresholds, root_cause
    )

    # Root-cause-aware RAG: if the ticket matches a known Problem that retrieval did not already
    # return, give it to the drafter too, so the reply can cite the root cause. Added after the
    # gate so the similarity rules still judge plain retrieval only.
    if root_cause is not None and root_cause.known_problem is not None:
        if root_cause.known_problem.ticket_id not in {p.ticket_id for p in precedents}:
            precedents = precedents + [root_cause.known_problem]

    t = time.perf_counter()
    engine = None
    if escalate:
        # An escalated ticket gets no draft at all. Showing the operator a
        # suggested reply next to "escalate to on-call" invites them to send it.
        draft_reply, cited, unverified = None, [], []
    elif STAGES["generate"]:
        from . import generate
        d = generate.draft(masked_text, preds["language"].label, precedents)
        draft_reply = d["reply"]
        cited, unverified, engine = d["cited_ticket_ids"], d["unverified_claims"], d["engine"]
        if not d["grounded"]:
            escalate = True
            reasons.append("Draft not grounded in the retrieved precedents")
            draft_reply, cited = None, []
    else:
        draft_reply, cited, unverified = "[stub draft]", [p.ticket_id for p in precedents], []
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
        root_cause=root_cause,
        engine=engine,
    )
