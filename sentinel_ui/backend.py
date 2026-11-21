"""Adapter: the real SentinelDesk pipeline -> the dict contract the UI renders (see mock_desk.py).

The UI never touches TriageResult directly; everything it needs is mapped here, so a change in
the pipeline's dataclass only has to be absorbed in one place.

Default backend for the console (sentinel_ui.common.get_backend). Override with
SENTINEL_BACKEND=module:function, or tick "Use mock backend" in the sidebar.
"""
from __future__ import annotations

from sentineldesk import pipeline
from sentineldesk.generate import scrub

ON_CALL, REVIEW, AUTO = "ESCALATE_ONCALL", "HUMAN_REVIEW", "AUTO_DRAFT_READY"


def _pred(p) -> dict:
    return {"label": str(p.label), "confidence": round(float(p.confidence), 4)}


def _precedent(p) -> dict:
    return {"ticket_id": p.ticket_id, "similarity": round(float(p.score), 4), "language": p.language,
            "subject": p.subject, "queue": p.queue, "answer_snippet": scrub(p.answer)[:600]}


def warm_up() -> None:
    """Load the encoder, classifier and index once, so the first real ticket is not slow."""
    pipeline.triage("warm-up", "warm-up ticket to load the models", track_burst=False)


def triage_ticket(subject: str | None, body: str, live: bool = True) -> dict:
    """live=True for a real incoming ticket (counted by the burst detector, root-cause grouping and
    the problem database). live=False replays a ticket (e.g. an agent asking the AI about a
    historical KB ticket) without recording it anywhere."""
    r = pipeline.triage(subject, body, track_burst=live)
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
        "risks": list(r.risks),
        "burst": {"active": bool(r.burst.get("active")), "related": list(r.burst.get("related", []))},
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
