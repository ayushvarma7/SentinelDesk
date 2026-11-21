"""Adapter: the real SentinelDesk pipeline -> the dict contract the UI renders (see mock_desk.py).

The UI never touches TriageResult directly; everything it needs is mapped here, so a change in
the pipeline's dataclass only has to be absorbed in one place.

Default backend for the console (sentinel_ui.common.get_backend). Override with
SENTINEL_BACKEND=module:function, or tick "Use mock backend" in the sidebar.
"""
from __future__ import annotations

from sentineldesk import config, pii, pipeline
from sentineldesk.generate import scrub
from sentineldesk.text import build_text

ON_CALL, REVIEW, AUTO = "ESCALATE_ONCALL", "HUMAN_REVIEW", "AUTO_DRAFT_READY"


def _pred(p) -> dict:
    return {"label": str(p.label), "confidence": round(float(p.confidence), 4)}


def _precedent(p) -> dict:
    return {"ticket_id": p.ticket_id, "similarity": round(float(p.score), 4), "language": p.language,
            "subject": p.subject, "queue": p.queue, "answer_snippet": scrub(p.answer)[:600]}


def reset_outage_detector() -> None:
    """Forget recent live tickets, so an outage drill starts from a clean 30-minute window."""
    pipeline.BURST.clear()


def prime_outage_detector(tickets: list[dict]) -> int:
    """Replay the stored tickets from the last burst window into the in-memory detector.

    The detector lives in the server process, so after a restart it would forget an outage that is still
    in progress; priming it means the next matching report joins that outage. Returns how many replayed.
    """
    import time
    from datetime import datetime

    from sentineldesk import embed
    now, n = time.time(), 0
    for t in sorted(tickets, key=lambda x: x.get("opened", "")):
        try:
            ts = datetime.strptime(t["opened"], "%Y-%m-%d %H:%M").timestamp()
        except (KeyError, ValueError):
            continue
        if now - ts <= config.BURST_WINDOW_S:
            vec = embed.encode([build_text(t.get("subject"), t.get("body"))], is_query=True)[0]
            pipeline.BURST.check(vec, now=ts)
            n += 1
    return n


def warm_up() -> None:
    """Load the encoder, classifier and index once, so the first real ticket is not slow."""
    pipeline.triage("warm-up", "warm-up ticket to load the models", track_burst=False)


def triage_ticket(subject: str | None, body: str, live: bool = True,
                  received_at: float | None = None) -> dict:
    """live=True for a real incoming ticket (counted by the burst detector, root-cause grouping and
    the problem database). live=False replays a ticket (e.g. an agent asking the AI about a
    historical KB ticket) without recording it anywhere. received_at (epoch seconds) replays a
    ticket at its own arrival time (scripts/seed_demo.py)."""
    r = pipeline.triage(subject, body, track_burst=live, received_at=received_at)
    # Exactly what an external LLM call receives: the pipeline masks this same text before generate.draft().
    masked_text, _ = pii.mask(build_text(subject, body))
    lat = r.latency_ms
    rc = r.root_cause
    return {
        "language": r.language,
        "type": _pred(r.type),
        "queue": _pred(r.queue),
        "priority": _pred(r.priority),
        "status": r.status or (ON_CALL if r.escalate else AUTO),
        "escalation": {"escalate": bool(r.escalate), "reasons": list(r.escalation_reasons)},
        "retrieved": [_precedent(p) for p in r.precedents],
        "draft": r.draft_reply,
        "cited_ids": list(r.cited_ticket_ids),
        "unverified": list(r.unverified_claims),
        "pii_found": sorted(r.masked_pii),
        "pii_counts": dict(r.masked_pii),
        "masked_text": masked_text,
        "risks": list(r.risks),
        "burst": {"active": bool(r.burst.get("active")), "related": list(r.burst.get("related", [])),
                  "live_id": r.burst.get("live_id"), "max_sim": r.burst.get("max_sim", 0.0),
                  "window_min": config.BURST_WINDOW_S // 60, "min_count": config.BURST_MIN_COUNT},
        "root_cause": None if rc is None else {
            "group": list(rc.group_ticket_ids), "suggest_problem": bool(rc.suggest_problem),
            "known_problem": rc.known_problem.ticket_id if rc.known_problem else None,
            "known_change": rc.known_change.ticket_id if rc.known_change else None},
        "engine": r.engine,
        # Track A problem database (store.py): matched an existing problem or added a new one
        "problem": None if r.problem is None else {
            "problem_id": r.problem.problem_id, "is_new": r.problem.is_new, "title": r.problem.title,
            "occurrences": r.problem.occurrences, "status": r.problem.status,
            "resolution": r.problem.resolution, "similarity": r.problem.similarity,
            "related": [{"problem_id": x.problem_id, "title": x.title, "similarity": x.similarity,
                         "occurrences": x.occurrences, "status": x.status} for x in r.problem.related],
            "log_id": r.problem.log_id},
        "latency_ms": {"triage": round(lat.get("embed", 0) + lat.get("classify", 0), 1),
                       "retrieval": round(lat.get("retrieve", 0), 1),
                       "generation": round(lat.get("generate", 0), 1),
                       "total": round(lat.get("total", 0), 1)},
    }
