"""SentinelDesk API: FastAPI wrapper around sentineldesk.pipeline.triage.

Run from the repo root:
    SD_MOCK=1 .venv/bin/uvicorn api.main:app --reload --port 8000

Mode:
  real  - sentineldesk.pipeline imports AND artifacts/heads.joblib + kb_embeddings.npy exist AND SD_MOCK != 1
  mock  - otherwise. Same TriageResult shape; uses the real gate/PII/figure-check code (api/mock_engine.py).
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mock_engine  # noqa: E402
from seed_data import AGENTS, SEEDS  # noqa: E402
from sentineldesk import config  # noqa: E402

MAX_CHARS = 20_000  # hard cap per field; the pipeline is length-safe but the browser is not

# ---------------------------------------------------------------- mode selection
MODE = "mock"
MODE_REASON = ""
_pipeline = None
if os.environ.get("SD_MOCK", "0") == "1":
    MODE_REASON = "SD_MOCK=1"
else:
    try:
        from sentineldesk import pipeline as _pipeline  # noqa: E402
        missing = [p.name for p in (config.HEADS_PATH, config.KB_EMB_PATH) if not p.exists()]
        if missing:
            MODE_REASON = f"artifacts missing: {', '.join(missing)}"
            _pipeline = None
        else:
            MODE, MODE_REASON = "real", "pipeline + artifacts found"
    except Exception as exc:  # torch/numpy/sklearn not installed, etc.
        MODE_REASON = f"pipeline import failed: {type(exc).__name__}: {exc}"[:200]
        _pipeline = None


def run_triage(subject: str, body: str, now: float | None = None, track_burst: bool = True):
    """Returns (TriageResult, engine_mode). Falls back to mock if the real pipeline throws."""
    if MODE == "real" and _pipeline is not None:
        try:
            return _pipeline.triage(subject, body, track_burst=track_burst), "real"
        except Exception as exc:
            print(f"[api] real triage failed, using mock: {exc!r}", file=sys.stderr)
    return mock_engine.mock_triage(subject, body, now=now, track_burst=track_burst), "mock"


def result_to_dict(res) -> dict:
    d = dataclasses.asdict(res)
    d["overall_confidence"] = round(res.overall_confidence, 4)
    return d


# ---------------------------------------------------------------- agent trace
def _ms(x: float) -> float:
    return round(float(x), 1)


def build_trace(r: dict, text_len: int) -> list[dict]:
    lat = r.get("latency_ms", {})
    esc = r["escalate"]
    pii = r.get("masked_pii", {}) or {}
    precs = r.get("precedents", []) or []
    reasons = r.get("escalation_reasons", []) or []
    unverified = r.get("unverified_claims", []) or []
    cited = r.get("cited_ticket_ids", []) or []
    phases = []

    def add(name, status, dur, logs):
        phases.append({"phase": name, "status": status, "duration_ms": _ms(dur), "logs": logs})

    if pii:
        pii_logs = [f"Masked {v} {k}" for k, v in pii.items()]
        pii_logs.append("Masked text used for every external call")
    else:
        pii_logs = ["No PII found (email, phone, IBAN, card, IP, account)"]
    add("PII Mask", "done", 0.2 + text_len / 8000, pii_logs)

    add("Triage", "done", lat.get("embed", 0) + lat.get("classify", 0), [
        f"Embedded query (e5-small) in {lat.get('embed', 0):.1f} ms",
        f"type={r['type']['label']} ({r['type']['confidence']:.2f})",
        f"queue={r['queue']['label']} ({r['queue']['confidence']:.2f})",
        f"priority={r['priority']['label']} ({r['priority']['confidence']:.2f})",
        f"language={r['language']}",
    ])

    risks = r.get("risks", []) or []
    gate_logs = [f"Risk detected: {x}" for x in risks]
    gate_logs += [f"Rule fired: {x}" for x in reasons if "precedent" not in x.lower()]
    if r.get("burst", {}).get("active"):
        gate_logs.append(f"Burst active: related {', '.join(r['burst'].get('related', []))}")

    pre_reasons = [x for x in reasons if "precedent" not in x.lower() and "grounded" not in x.lower()]
    add("Safety Gate", "escalated" if pre_reasons else "done", 0.4,
        gate_logs or ["All deterministic rules passed"])

    top = ", ".join(f"{p['ticket_id']} ({p['score']:.3f})" for p in precs[:5])
    add("Retrieve Precedents", "done" if precs else "warning", lat.get("retrieve", 0),
        [f"Top-{len(precs)}: {top}" if precs else "No precedents retrieved",
         f"Cross-lingual: {sum(1 for p in precs if p['language'] != r['language'])} in other language"])

    if precs:
        top1 = precs[0]["score"]
        mean3 = sum(p["score"] for p in precs[:3]) / len(precs[:3])
        ok = top1 >= config.MIN_TOP1_SIMILARITY and mean3 >= config.MIN_MEAN_TOP3_SIMILARITY
        add("Grade Evidence", "done" if ok else "warning", 0.2, [
            f"top-1 {top1:.3f} vs floor {config.MIN_TOP1_SIMILARITY:.3f}",
            f"mean top-3 {mean3:.3f} vs floor {config.MIN_MEAN_TOP3_SIMILARITY:.3f}",
            "Evidence sufficient" if ok else "Evidence too weak to ground a reply"])
    else:
        add("Grade Evidence", "warning", 0.1, ["No evidence to grade"])

    if esc:
        add("Draft Reply", "skipped", 0, ["Escalated tickets get no customer draft (by design)"])
        add("Verify Citations", "skipped", 0, ["Nothing to verify"])
        add("Resolve/Escalate", "escalated", 0.1,
            [f"Escalated: {len(reasons)} reason(s)"] + reasons[:4])
    else:
        add("Draft Reply", "done", lat.get("generate", 0),
            [f"Engine: {r.get('engine') or 'n/a'}", f"Draft {len(r.get('draft_reply') or '')} chars"])
        add("Verify Citations", "warning" if unverified else "done", 1.1,
            [f"Cited: {', '.join(cited) or 'none'} (all in retrieved set)"]
            + ([f"Unverified: {u}" for u in unverified] or ["All figures found in evidence"]))
        add("Resolve/Escalate", "done", 0.1, ["Auto-resolved: draft ready to send"])
    return phases


# ---------------------------------------------------------------- store
LOCK = threading.Lock()
TICKETS: dict[str, dict] = {}
_SEQ = [10000]
PREFIX = {"Incident": "INC", "Request": "REQ", "Problem": "PRB", "Change": "CHG"}
SLA_HOURS = {"high": 4, "medium": 24, "low": 72}


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _summary(subject: str, body: str) -> str:
    # Length cut at a word boundary, not a sentence split ("St. Mary's" broke that).
    s = re.sub(r"\s+", " ", (body or subject or "(no text)")).strip()
    if len(s) <= 200:
        return s
    return s[:200].rsplit(" ", 1)[0] + "…"


def _tags(r: dict) -> list[str]:
    tags = [r["queue"]["label"].split()[0].lower(), r["language"]]
    tags += [x.replace("_", "-") for x in r.get("risks", [])]
    if r.get("masked_pii"):
        tags.append("pii-masked")
    if r.get("burst", {}).get("active"):
        tags.append("major-incident")
    if r.get("unverified_claims"):
        tags.append("unverified")
    return list(dict.fromkeys(tags))


def _copilot(subject: str, body: str, r: dict) -> dict:
    """Recommended resolution for the human (escalated tickets have no customer draft)."""
    if r.get("draft_reply"):
        return {"text": r["draft_reply"], "cited_ids": r["cited_ticket_ids"],
                "unverified": r["unverified_claims"], "source": "draft"}
    text = f"{subject}\n{body}"
    none = {"text": None, "cited_ids": [], "unverified": [], "source": "none"}
    if any("Too little text" in x for x in r.get("escalation_reasons", [])):
        return none  # nothing to resolve; the human has to read it
    if set(r.get("risks", [])) & {"prompt_injection", "credential_request", "destructive_action", "legal"}:
        return none  # never hand the operator a ready-to-send reply to an attack or legal threat
    lang = r["language"]
    sug = mock_engine.suggestion(text, lang)
    precs = r.get("precedents", [])
    if not sug and precs:
        # Quote the closest same-language precedent, like generate.py's extractive fallback.
        p = next((x for x in precs if x["language"] == lang), precs[0])
        sug = f"{p['answer']} [{p['ticket_id']}]"
    if not sug:
        return none
    from sentineldesk.generate import unsupported_figures
    ids = list(dict.fromkeys(re.findall(r"(?:TKT|LIVE)-\d{5}", sug)))
    unverified = unsupported_figures(sug, " ".join(p["answer"] for p in precs))
    return {"text": sug, "cited_ids": ids, "unverified": unverified, "source": "suggestion"}


def make_ticket(subject: str, body: str, name: str, email: str, created: float,
                status_hint: str | None = None, channel: str = "portal",
                track_burst: bool = True) -> dict:
    subject = (subject or "")[:MAX_CHARS]
    body = (body or "")[:MAX_CHARS]
    res, engine_mode = run_triage(subject, body, now=created, track_burst=track_burst)
    r = result_to_dict(res)
    prio, typ, esc = r["priority"]["label"], r["type"]["label"], r["escalate"]

    with LOCK:
        _SEQ[0] += 1
        tid = f"{PREFIX.get(typ, 'TKT')}-{_SEQ[0]}"
    h = int(mock_engine._h(subject + body, "agent") * 1000)
    if status_hint:
        status = status_hint
        if esc and status == "Auto-Resolved":
            status = "In Progress"
    elif esc:
        status = "Escalated" if prio == "high" else ("New" if h % 2 else "In Progress")
    else:
        status = "Auto-Resolved"
    if status == "Auto-Resolved":
        assigned = "SentinelDesk Agent"
    elif status == "New":
        assigned = "Unassigned"
    elif status == "Escalated":
        assigned = f"On-call: {AGENTS[h % len(AGENTS)]}"
    else:
        assigned = AGENTS[h % len(AGENTS)]

    ticket = {
        "id": tid,
        "subject": subject or "(no subject)",
        "body": mock_engine.masked(body),
        "summary": _summary(subject, mock_engine.masked(body)),
        "requester": {"name": name or "Customer", "email": email or ""},
        "channel": channel,
        "created_at": _iso(created),
        "sla_due": _iso(created + SLA_HOURS.get(prio, 24) * 3600),
        "status": status,
        "assigned_to": assigned,
        "tags": _tags(r),
        "priority": prio,
        "type": typ,
        "queue": r["queue"]["label"],
        "language": r["language"],
        "confidence": r["overall_confidence"],
        "escalated": esc,
        "engine_mode": engine_mode,
        "triage": r,
        "agent_trace": build_trace(r, len(subject) + len(body)),
        "copilot": _copilot(subject, body, r),
        "final_reply": r["draft_reply"] if status in ("Auto-Resolved", "Closed") and not esc else None,
        "history": [{"at": _iso(created), "actor": "SentinelDesk",
                     "action": "Escalated to human" if esc else "Auto-resolved with grounded draft"}],
    }
    with LOCK:
        TICKETS[tid] = ticket
    return ticket


def seed() -> None:
    now = time.time()
    rows = sorted(SEEDS, key=lambda s: -s[4])  # oldest first so ids increase with time
    for subj, body, name, email, age_min, hint, burst_seed in rows:
        make_ticket(subj, body, name, email, now - age_min * 60, hint,
                    channel="email" if age_min % 2 else "portal",
                    track_burst=burst_seed or MODE == "mock")


seed()

# ---------------------------------------------------------------- app
app = FastAPI(title="SentinelDesk API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",   # agent console
                   "http://localhost:5174", "http://127.0.0.1:5174"],  # customer-portal app
    allow_methods=["*"], allow_headers=["*"],
)


class TriageIn(BaseModel):
    subject: Optional[str] = ""
    body: Optional[str] = ""


class TicketIn(TriageIn):
    name: Optional[str] = "Customer"
    email: Optional[str] = ""
    kind: Optional[str] = "incident"   # incident | request (portal card that was used)


class ActionIn(BaseModel):
    agent: Optional[str] = "You"
    reply: Optional[str] = None
    reason: Optional[str] = None


def _get(tid: str) -> dict:
    t = TICKETS.get(tid)
    if not t:
        raise HTTPException(404, f"ticket {tid} not found")
    return t


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mode": MODE, "reason": MODE_REASON, "tickets": len(TICKETS)}


@app.post("/triage")
def triage(inp: TriageIn) -> dict:
    res, engine_mode = run_triage((inp.subject or "")[:MAX_CHARS], (inp.body or "")[:MAX_CHARS],
                                  track_burst=False)
    d = result_to_dict(res)
    d["mode"] = engine_mode
    return d


@app.get("/tickets")
def list_tickets(email: Optional[str] = None, requester: Optional[str] = None) -> list[dict]:
    """All tickets, newest first. ?email= (customer portal) filters by requester email, case-insensitive.
    ?requester= is the older alias. An empty value means no filter."""
    items = list(TICKETS.values())
    who = (email if email is not None else requester or "").strip().lower()
    if who:
        items = [t for t in items if t["requester"]["email"].lower() == who]
    return sorted(items, key=lambda t: t["created_at"], reverse=True)


@app.get("/tickets/{tid}")
def get_ticket(tid: str) -> dict:
    return _get(tid)


@app.post("/tickets")
def create_ticket(inp: TicketIn) -> dict:
    return make_ticket(inp.subject or "", inp.body or "", inp.name or "Customer", inp.email or "",
                       time.time(), channel="portal")


def _log(t: dict, actor: str, action: str) -> None:
    t["history"].append({"at": _iso(time.time()), "actor": actor, "action": action})


@app.post("/tickets/{tid}/approve")
def approve(tid: str, inp: ActionIn | None = None) -> dict:
    inp = inp or ActionIn()
    t = _get(tid)
    reply = inp.reply or t["copilot"].get("text") or t["triage"].get("draft_reply")
    if not reply:
        raise HTTPException(400, "no draft to send; pass 'reply'")
    t["final_reply"] = reply[:MAX_CHARS]
    t["status"] = "Closed"
    t["assigned_to"] = inp.agent or "You"
    _log(t, inp.agent or "You", "Approved & sent reply" + (" (edited)" if inp.reply else ""))
    return t


@app.post("/tickets/{tid}/reject")
def reject(tid: str, inp: ActionIn | None = None) -> dict:
    inp = inp or ActionIn()
    t = _get(tid)
    t["status"] = "In Progress"
    t["final_reply"] = None
    t["assigned_to"] = inp.agent or "You"
    _log(t, inp.agent or "You", f"Rejected AI draft{': ' + inp.reason if inp.reason else ''}")
    return t


@app.post("/tickets/{tid}/assign")
def assign(tid: str, inp: ActionIn | None = None) -> dict:
    inp = inp or ActionIn()
    t = _get(tid)
    t["assigned_to"] = inp.agent or "You"
    if t["status"] == "New":
        t["status"] = "In Progress"
    _log(t, inp.agent or "You", "Assigned to self")
    return t


def _read_json(name: str) -> dict:
    try:
        return json.loads((ROOT / "reports" / name).read_text())
    except Exception:
        return {}


@app.get("/metrics")
def metrics() -> dict:
    items = list(TICKETS.values())
    by_priority: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    by_queue: dict[str, int] = {}
    by_status: dict[str, int] = {}
    lat = []
    for t in items:
        by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
        by_queue[t["queue"]] = by_queue.get(t["queue"], 0) + 1
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        lat.append(t["triage"]["latency_ms"].get("total", 0))
    total = len(items)
    escalated = sum(1 for t in items if t["escalated"])
    auto = total - escalated
    tm, gs = _read_json("triage_metrics.json"), _read_json("gate_sweep.json")
    burst_ids = [t["id"] for t in items if t["triage"].get("burst", {}).get("active")]
    return {
        "mode": MODE,
        "total": total,
        "auto_resolved": auto,
        "escalated": escalated,
        "escalation_rate": round(escalated / total, 4) if total else 0,
        "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else 0,
        "by_priority": by_priority,
        "by_queue": dict(sorted(by_queue.items(), key=lambda kv: -kv[1])),
        "by_status": by_status,
        "kpi": {
            "high_priority_incident_recall":
                tm.get("high_priority_incident", {}).get("recall_predicted_high_and_incident"),
            "high_incident_escalated": gs.get("chosen", {}).get("high_incident_escalated"),
            "auto_share_validation": gs.get("chosen", {}).get("auto_share"),
        },
        "major_incident": {"active": bool(burst_ids), "ticket_ids": burst_ids},
    }
