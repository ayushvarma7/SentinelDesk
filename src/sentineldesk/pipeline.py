"""The contract every track codes against: raw ticket in, TriageResult out.

Right now `triage()` returns plausible fake data so Track D can build the whole
console before a single model exists. Replace one stage at a time by flipping
its entry in STAGES — never by changing the signature.
"""
from __future__ import annotations

import time

from . import config, gate, pii
from .burst import BurstDetector
from .text import build_text
from .schema import Precedent, Prediction, TriageResult

# Flip each to True as that track lands. Keeps the app runnable the whole way.
STAGES = {
    "embed": True,       # Track A wired embed.encode (Track B owns the file)
    "classify": True,    # Track A: falls back to the stub if artifacts/heads.joblib is missing
    "retrieve": True,    # Track B: real index, stub fallback if artifacts are missing
    "generate": True,    # Track C: Gemini when a key exists, extractive fallback otherwise
}


# Live-ticket memory for the major-incident banner (P3). Scripts call BURST.clear()
# between evaluation tickets so they do not trigger it.
BURST = BurstDetector()


_LANGS = ("en", "de")
# langdetect must win by this much before it overrides the language head.
LANG_OVERRIDE_PROB = 0.90


def _detected_language(text: str) -> tuple[str, float] | None:
    """(lang, prob) from langdetect when it is confident the text is en/de, else None.

    The language head learned the dataset's label, which disagrees with the text on ~12% of
    tickets (German-labelled tickets written in English). Without this guard a plainly English
    ticket can get a German reply (the hospital VPN demo ticket: head says de at 0.61).
    """
    try:
        from langdetect import DetectorFactory, detect_langs
        DetectorFactory.seed = 0
        best = detect_langs(text)[0]
    except Exception:
        return None
    if best.lang in _LANGS and best.prob >= LANG_OVERRIDE_PROB:
        return best.lang, float(best.prob)
    return None


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
           thresholds: dict | None = None, track_burst: bool = True) -> TriageResult:
    """Triage one ticket. Safe on null subject, null body, and arbitrary length.

    track_burst=False keeps the ticket out of the burst detector. Evaluation scripts pass it so
    their own batch of (often similar) tickets cannot raise a false major-incident banner.
    """
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
    det = _detected_language(text) if len(text) >= 20 else None
    if det and det[0] != preds["language"].label:
        preds["language"] = Prediction(det[0], det[1], {**preds["language"].all_probs, "langdetect": det[1]})
    latency["classify"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    if STAGES["retrieve"] and qvec is not None:
        from . import retrieve
        if retrieve.is_ready():
            precedents = retrieve.search(qvec, config.TOP_K, preds["queue"].label,
                                         language=preds["language"].label, query_text=text)
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
        root_cause = rootcause.analyze(qvec, text, group=track_burst, queue=preds["queue"].label)
    latency["root_cause"] = (time.perf_counter() - t) * 1000

    burst = (BURST.check(qvec, sim=(thresholds or {}).get("burst_sim")) if track_burst
             else {"active": False, "related": [], "live_id": None, "max_sim": 0.0})
    if config.MAJOR_INCIDENT_SOURCE == "root_cause" and track_burst:
        # The banner follows the root-cause group (issues only, queue-aware linking), not P3's
        # flat-cosine trigger, which fired on unrelated tickets in tests/test_major_incident.py.
        # P3's detector still records every ticket and reports max_sim for the console.
        group = root_cause.group_ticket_ids if root_cause is not None else []
        active = root_cause is not None and root_cause.suggest_problem
        burst = {**burst, "active": active, "related": group[:-1] if active else [],
                 "source": "root_cause"}
    detailed = gate.evaluate_detailed(
        text, preds["type"], preds["queue"], preds["priority"], precedents, thresholds, burst,
        root_cause=root_cause
    )
    reasons = [r for _, r in detailed]
    escalate = bool(reasons)
    status, draft_allowed = gate.decide(detailed)

    # Root-cause-aware RAG: if the ticket matches a known Problem that retrieval did not already
    # return, give it to the drafter too, so the reply can cite the root cause. Added after the
    # gate so the similarity rules still judge plain retrieval only.
    if root_cause is not None and root_cause.known_problem is not None:
        if root_cause.known_problem.ticket_id not in {p.ticket_id for p in precedents}:
            precedents = precedents + [root_cause.known_problem]

    t = time.perf_counter()
    engine = None
    if not draft_allowed:
        # On-call tickets and blocked ones (attacks, legal, unsupported commitments) get no draft
        # at all: a suggested reply next to "escalate to on-call" invites someone to send it.
        # HUMAN_REVIEW tickets whose only reasons are soft (low confidence, weak precedent) still
        # get a draft, clearly marked for a human to approve.
        draft_reply, cited, unverified = None, [], []
    elif STAGES["generate"]:
        from . import generate
        d = generate.draft(masked_text, preds["language"].label, precedents)
        draft_reply = d["reply"]
        cited, unverified, engine = d["cited_ticket_ids"], d["unverified_claims"], d["engine"]
        if not d["grounded"]:
            escalate, status = True, gate.REVIEW
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
        status=status,
        escalation_reasons=reasons,
        precedents=precedents,
        draft_reply=draft_reply,
        cited_ticket_ids=cited,
        unverified_claims=unverified,
        masked_pii=masked_counts,
        latency_ms=latency,
        risks=gate.detect_risks(text),
        burst=burst,
        root_cause=root_cause,
        engine=engine,
    )


def triage_ticket(subject: str | None, body: str | None,
                  thresholds: dict | None = None) -> dict:
    """Dict-shaped adapter for the Streamlit console (frontend-ui).

    The UI resolves SENTINEL_BACKEND, default "sentineldesk.pipeline:triage_ticket",
    and expects the same shape mock_desk.triage_ticket returns. Without this it
    cannot import a callable by that name, catches the error, and SILENTLY falls
    back to the mock — so the console looks like it works while showing invented
    data. Keep the keys below in step with sentinel_ui.common.normalize_result().

    triage() and TriageResult remain the real contract; this is a thin projection.
    """
    r = triage(subject, body, thresholds=thresholds)

    def pred(p) -> dict:
        return {"label": p.label, "confidence": round(float(p.confidence), 4)}

    return {
        "language": r.language,
        "type": pred(r.type),
        "queue": pred(r.queue),
        "priority": pred(r.priority),
        "escalation": {"escalate": bool(r.escalate), "reasons": list(r.escalation_reasons)},
        "retrieved": [
            {"ticket_id": p.ticket_id,
             "similarity": round(float(p.score), 4),
             "language": p.language,
             "subject": p.subject,
             "answer_snippet": p.answer[:450]}
            for p in r.precedents
        ],
        "draft": r.draft_reply,
        "cited_ids": list(r.cited_ticket_ids),
        # masked_pii is {kind: count}; the UI wants a flat list of what was found.
        "pii_found": [k for k, n in (r.masked_pii or {}).items() if n],
        "latency_ms": {
            "triage": round(r.latency_ms.get("embed", 0.0) + r.latency_ms.get("classify", 0.0), 1),
            "retrieval": round(r.latency_ms.get("retrieve", 0.0), 1),
            "generation": round(r.latency_ms.get("generate", 0.0), 1),
            "total": round(r.latency_ms.get("total", 0.0), 1),
        },
        "engine": r.engine,
        "unverified_claims": list(r.unverified_claims),
    }


def resolve_ticket(subject: str | None, body: str | None, resolution: str,
                   resolved_by: str, queue: str | None = None,
                   type_: str | None = None, language: str | None = None) -> dict:
    """Close the loop: a human resolved this ticket, so it becomes a precedent.

    Call this from the agent console when an agent marks a ticket resolved and
    has written the resolution text — never on an AI draft, and never on
    submission. A ticket arriving from a form has no answer yet; indexing it
    would put questions in a store meant for answers.

    Labels are inferred from the ticket when the console does not pass them, so
    the new precedent carries the same queue/type metadata as the KB rows it
    sits beside and the queue filter keeps working.

    Returns {"ticket_id": "LIVE-00001", "indexed": True, "live_count": n}.
    """
    from . import retrieve

    resolution = (resolution or "").strip()
    if not resolution:
        raise ValueError("resolution text is empty — nothing to learn from")
    if not (resolved_by or "").strip():
        raise ValueError("resolved_by is required: precedents must trace to a person")

    if queue is None or type_ is None or language is None:
        text = build_text(subject, body)
        qvec = None
        if STAGES["embed"]:
            from . import embed
            qvec = embed.encode([text], is_query=True)[0]
        if qvec is not None and STAGES["classify"] and config.HEADS_PATH.exists():
            from . import classify
            preds = classify.predict(qvec, text)
        else:
            preds = _stub_predictions()
        queue = queue if queue is not None else preds["queue"].label
        type_ = type_ if type_ is not None else preds["type"].label
        language = language if language is not None else preds["language"].label

    ticket_id = retrieve.add_precedent(subject=subject, body=body, answer=resolution,
                                       language=language, queue=queue, type_=type_,
                                       resolved_by=resolved_by)
    return {"ticket_id": ticket_id, "indexed": True, "live_count": retrieve.live_count()}
