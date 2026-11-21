"""Shared pieces for all SentinelDesk pages."""
from __future__ import annotations

import importlib
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import mock_desk  # noqa: E402

DATA_PATH = Path(os.getenv("SENTINEL_DATA", ROOT / "data/processed/kb_train.parquet"))
LIVE_PATH = Path(os.getenv("SENTINEL_LIVE", ROOT / "data/live_tickets.json"))
# Written by scripts/evaluate.py (holdout, never used for tuning).
METRICS_PATH = Path(os.getenv("SENTINEL_METRICS", ROOT / "reports/triage_metrics.json"))
MAX_CHARS = 6000
NU_RED = "#C8102E"

# ------------------------------------------------------------------ theme
ASSETS = ROOT / "assets"

ICONS = {  # simple line icons (24px grid), stroke = currentColor
    "portal": '<path d="M4 18v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2"/><circle cx="12" cy="6" r="3.2"/><path d="M3 21h18"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 9h18M3 14h18M9 9v11"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1"/>',
    "book": '<path d="M4 4h6a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H4zM20 4h-6a3 3 0 0 0-3 3"/><path d="M20 4v13.5h-6.5A2.5 2.5 0 0 0 11 20"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="m3 7 9 6 9-6"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M15 8l2 2"/>',
    "app": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "card": '<rect x="2" y="5" width="20" height="14" rx="1.5"/><path d="M2 10h20M6 15h4"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "route": '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
}


def icon(name: str, size: int = 22) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS[name]}</svg>')


def img_uri(name: str) -> str | None:
    """Return a data URI for assets/<name> if the file exists (optional photos)."""
    import base64
    f = ASSETS / name
    if not f.exists():
        return None
    mime = "image/svg+xml" if f.suffix == ".svg" else "image/png" if f.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}"


def inject_css():
    try:
        st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "mark.svg"), size="large")
    except Exception:  # noqa: BLE001
        pass
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        :root{--ink:#0E1A2B;--ink2:#172A44;--surface:#F3F5F8;--card:#FFFFFF;--line:#DCE2EA;
              --text:#1C2735;--muted:#5A6A7E;--accent:#C8102E;--ok:#0F766E;--warn:#B45309;--info:#1D4ED8}
        html,body,.stApp,[data-testid="stMarkdownContainer"],input,textarea,button,select{
            font-family:'IBM Plex Sans',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif!important}
        .stApp{background:var(--surface)}
        header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
        .block-container{padding-top:1.1rem!important;padding-bottom:2.5rem;max-width:1440px}
        /* sidebar */
        section[data-testid="stSidebar"]{background:var(--ink)}
        section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] summary{color:#C3CEDB!important}
        [data-testid="stSidebarNav"] a{border-radius:6px}
        [data-testid="stSidebarNav"] a[aria-current="page"]{background:rgba(255,255,255,.09)}
        [data-testid="stSidebarNav"] a[aria-current="page"] span{color:#FFFFFF!important;font-weight:600}
        section[data-testid="stSidebar"] [data-testid="stExpander"] details{border-color:rgba(255,255,255,.15)}
        /* page header */
        .ph{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin:0 0 1rem}
        .ph .t{font-size:1.65rem;font-weight:600;color:var(--text);letter-spacing:-.01em;line-height:1.2}
        .ph .s{color:var(--muted);font-size:.98rem;margin-top:.2rem}
        /* hero */
        .hero{position:relative;overflow:hidden;border-radius:12px;background:var(--ink);color:#fff;
              padding:3rem 2.8rem;min-height:300px;animation:rise .7s ease-out both}
        .hero .bg{position:absolute;inset:-40%;background:
            radial-gradient(38% 38% at 72% 28%,rgba(200,16,46,.42),transparent 62%),
            radial-gradient(34% 34% at 22% 78%,rgba(37,99,235,.30),transparent 62%),
            radial-gradient(30% 30% at 88% 86%,rgba(15,118,110,.25),transparent 62%);
            animation:drift 16s ease-in-out infinite alternate}
        .hero .grid{position:absolute;inset:0;background-image:
            linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),
            linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);
            background-size:44px 44px;-webkit-mask-image:linear-gradient(100deg,transparent 30%,#000 75%);
            mask-image:linear-gradient(100deg,transparent 30%,#000 75%)}
        .hero .scan{position:absolute;left:0;right:0;height:120px;top:-120px;
            background:linear-gradient(180deg,transparent,rgba(255,255,255,.07),transparent);
            animation:scan 7s linear infinite}
        .hero .photo{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.55}
        .hero .shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(14,26,43,.96) 0%,rgba(14,26,43,.80) 45%,rgba(14,26,43,.25) 100%)}
        .hero .in{position:relative;z-index:2;max-width:680px}
        .hero .k{color:#F7B6C1;font-weight:600;font-size:.9rem;margin-bottom:.7rem}
        .hero .h{font-size:2.55rem;line-height:1.12;font-weight:700;letter-spacing:-.02em;margin:0 0 .9rem;color:#fff}
        .hero .p{color:#C9D4E1;font-size:1.08rem;line-height:1.55;max-width:56ch}
        @keyframes drift{from{transform:translate(0,0) rotate(0)}to{transform:translate(7%,-5%) rotate(10deg)}}
        @keyframes scan{to{top:110%}}
        @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
        /* stat strip with count-up */
        @property --n{syntax:'<integer>';initial-value:0;inherits:false}
        .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:0;background:var(--card);
               border:1px solid var(--line);border-radius:12px;margin:1rem 0 1.4rem;animation:rise .7s .15s ease-out both}
        .stats>div{padding:1.15rem 1.4rem;border-left:1px solid var(--line)}
        .stats>div:first-child{border-left:0}
        .num{font-size:2rem;font-weight:700;color:var(--ink);line-height:1.1}
        .num .c{animation:count 1.8s .3s ease-out both;counter-reset:n var(--n)}
        .num .c::after{content:counter(n)}
        @keyframes count{from{--n:0}to{--n:var(--to)}}
        .lbl{color:var(--muted);font-size:.9rem;margin-top:.25rem}
        /* cards */
        .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.3rem 1.4rem;
              height:100%;transition:transform .18s ease,box-shadow .18s ease}
        .card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(14,26,43,.08)}
        .card .ic{width:40px;height:40px;border-radius:9px;display:flex;align-items:center;justify-content:center;
                  background:#FCE8EC;color:var(--accent);margin-bottom:.8rem}
        .card .ct{font-weight:600;font-size:1.08rem;color:var(--text);margin-bottom:.3rem}
        .card .cd{color:var(--muted);font-size:.95rem;line-height:1.5}
        .steps{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}
        .step .n{font-size:.85rem;font-weight:700;color:var(--accent)}
        /* status + badges */
        .badge{display:flex;gap:.55rem;align-items:flex-start;padding:.65rem .9rem;border-radius:8px;
               font-weight:500;margin:.25rem 0 .9rem;font-size:.95rem}
        .badge .dot{width:9px;height:9px;border-radius:50%;margin-top:.42rem;flex:none}
        .ok{background:#E7F5F2;color:#0B4F4A}.ok .dot{background:var(--ok)}
        .esc{background:#FCEBEC;color:#7A1020}.esc .dot{background:var(--accent);animation:pulse 1.6s infinite}
        .badge.warn{background:#FEF3E2;color:#7C3A06}.badge.warn .dot{background:var(--warn)}
        @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(200,16,46,.5)}70%{box-shadow:0 0 0 8px rgba(200,16,46,0)}100%{box-shadow:0 0 0 0 rgba(200,16,46,0)}}
        .pill{display:inline-block;padding:.12rem .6rem;border-radius:999px;font-size:.82rem;font-weight:600;
              background:#EEF1F5;color:#334155;margin:0 .25rem .25rem 0}
        .avatar{width:38px;height:38px;border-radius:50%;background:var(--ink);color:#fff;font-weight:600;
                display:flex;align-items:center;justify-content:center;font-size:.9rem;margin-left:auto}
        .topbar{display:flex;align-items:center;gap:1rem;background:var(--ink);color:#fff;border-radius:10px;
                padding:.75rem 1.1rem;margin-bottom:1rem}
        .topbar .tt{font-weight:600;font-size:1.05rem}.topbar .ts{color:#A9B7C8;font-size:.9rem}
        .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1rem 1.2rem}
        div[data-testid="stForm"]{background:var(--card);border:1px solid var(--line);border-radius:12px}
        [data-testid="stMetric"]{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem}
        @media (max-width:900px){.stats,.steps{grid-template-columns:repeat(2,1fr)}.hero .h{font-size:2rem}}
        @media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}
            .num .c{--n:var(--to)}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="ph"><div><div class="t">{title}</div><div class="s">{subtitle}</div></div></div>',
                unsafe_allow_html=True)


def stat_strip(items: list[tuple[int, str, str]]):
    """items: (number, suffix, label).

    The number is real text. It used to exist only as a CSS counter animation, which showed 0 under
    prefers-reduced-motion, in background tabs and to screen readers.
    """
    cells = "".join(
        f'<div><div class="num"><span>{int(n):,}</span>{suf}</div>'
        f'<div class="lbl">{lbl}</div></div>' for n, suf, lbl in items)
    st.markdown(f'<div class="stats">{cells}</div>', unsafe_allow_html=True)


def badge(kind: str, text: str):
    st.markdown(f'<div class="badge {kind}"><span class="dot"></span><span>{text}</span></div>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------ i18n
T = {
    "en": {
        "portal": "Northeastern IT Service Portal",
        "hero_k": "Northeastern University Information Technology Services",
        "hero_h": "Hi {name}, how can we help today?",
        "hero_p": "Report a problem or ask for something. Your request is routed to the right team in seconds, in English or German.",
        "status_ok": "All services operating normally",
        "status_bad": "Possible outage: several urgent incidents reported in the last hour",
        "popular": "Popular services",
        "side_h": "IT help for students, faculty and staff",
        "side_p": "Report an outage, reset a password or request software. Track every ticket in one place.",
        "pick_service": "Selected service",
        "portal_sub": "Report a problem or request help from Northeastern ITS",
        "login": "Sign in with your Northeastern account",
        "email": "Northeastern email", "password": "Password", "signin": "Sign in",
        "bad_login": "That email and password don't match a demo account.",
        "hello": "Hello", "signout": "Sign out",
        "tab_inc": "Report an incident", "tab_req": "Request something", "tab_my": "My tickets",
        "service": "What isn't working?", "impact": "Who is affected?",
        "impact_opts": ["Just me", "My class or team", "A whole department or building"],
        "urgency": "How urgent is it for you?", "urgency_opts": ["Low", "Medium", "High"],
        "category": "What do you need?",
        "categories": ["Account or password", "Software or access", "Billing or payments",
                       "Product information", "Something else"],
        "subject": "Short summary", "details": "Describe it in your own words (English or German)",
        "submit_inc": "Submit incident", "submit_req": "Submit request",
        "empty": "Add a description so we know how to help.",
        "submitted": "Ticket {num} submitted.",
        "escalated": "This looks urgent, so it went straight to the on-call team. They will contact you soon.",
        "queued": "Your ticket is with the {queue} team. A support agent will reply shortly.",
        "similar": "These similar issues were solved before. One of them might help right away:",
        "no_tickets": "You haven't submitted any tickets yet.",
        "number": "Number", "opened": "Opened", "status": "Status", "team": "Team",
    },
    "de": {
        "portal": "Northeastern IT-Serviceportal",
        "hero_k": "Northeastern University IT-Services",
        "hero_h": "Hallo {name}, wie können wir helfen?",
        "hero_p": "Melden Sie ein Problem oder stellen Sie eine Anfrage. Ihr Anliegen erreicht in Sekunden das richtige Team, auf Deutsch oder Englisch.",
        "status_ok": "Alle Dienste laufen normal",
        "status_bad": "Mögliche Störung: mehrere dringende Vorfälle in der letzten Stunde",
        "popular": "Beliebte Dienste",
        "side_h": "IT-Hilfe für Studierende, Lehrende und Mitarbeitende",
        "side_p": "Störung melden, Passwort zurücksetzen oder Software anfordern. Alle Tickets an einem Ort verfolgen.",
        "pick_service": "Ausgewählter Dienst",
        "portal_sub": "Melden Sie ein Problem oder fordern Sie Hilfe von Northeastern ITS an",
        "login": "Mit Ihrem Northeastern-Konto anmelden",
        "email": "Northeastern-E-Mail", "password": "Passwort", "signin": "Anmelden",
        "bad_login": "E-Mail und Passwort passen zu keinem Demo-Konto.",
        "hello": "Hallo", "signout": "Abmelden",
        "tab_inc": "Störung melden", "tab_req": "Anfrage stellen", "tab_my": "Meine Tickets",
        "service": "Was funktioniert nicht?", "impact": "Wer ist betroffen?",
        "impact_opts": ["Nur ich", "Mein Kurs oder Team", "Eine ganze Abteilung oder ein Gebäude"],
        "urgency": "Wie dringend ist es für Sie?", "urgency_opts": ["Niedrig", "Mittel", "Hoch"],
        "category": "Was benötigen Sie?",
        "categories": ["Konto oder Passwort", "Software oder Zugriff", "Rechnung oder Zahlung",
                       "Produktinformationen", "Etwas anderes"],
        "subject": "Kurze Zusammenfassung",
        "details": "Beschreiben Sie es mit eigenen Worten (Deutsch oder Englisch)",
        "submit_inc": "Störung absenden", "submit_req": "Anfrage absenden",
        "empty": "Bitte fügen Sie eine Beschreibung hinzu.",
        "submitted": "Ticket {num} wurde übermittelt.",
        "escalated": "Das wirkt dringend und wurde direkt an das Bereitschaftsteam weitergeleitet. Sie werden bald kontaktiert.",
        "queued": "Ihr Ticket liegt beim Team {queue}. Ein Support-Mitarbeiter antwortet in Kürze.",
        "similar": "Ähnliche Fälle wurden bereits gelöst. Vielleicht hilft Ihnen einer davon sofort:",
        "no_tickets": "Sie haben noch keine Tickets eingereicht.",
        "number": "Nummer", "opened": "Erstellt", "status": "Status", "team": "Team",
    },
}

SERVICES = ["Wi-Fi (NUwave)", "Canvas", "Email (Outlook)", "Account or password",
            "VPN or campus network", "Student Hub", "Billing portal", "Printing", "Other"]
SERVICE_TILES = [("Wi-Fi (NUwave)", "wifi"), ("Canvas", "book"), ("Email (Outlook)", "mail"),
                 ("Account or password", "key"), ("Student Hub", "app"), ("Billing portal", "card")]

# Demo-only accounts. Not real authentication.
DEMO_USERS = {
    "nima@northeastern.edu": ("husky2026", "Nima"),
    "demo@northeastern.edu": ("demo", "Demo Student"),
    "prof@northeastern.edu": ("demo", "Professor Demo"),
}

# ------------------------------------------------------------------ backend
@st.cache_resource(show_spinner="Loading models…")
def _load_real_backend():
    target = os.getenv("SENTINEL_BACKEND", "sentinel_ui.backend:triage_ticket")
    mod_name, fn_name = target.split(":")
    mod = importlib.import_module(mod_name)
    if hasattr(mod, "warm_up"):
        mod.warm_up()          # load encoder, classifier and index once, before the first ticket
    return getattr(mod, fn_name), target


def get_backend():
    if st.session_state.get("force_mock"):
        return mock_desk.triage_ticket, "mock"
    try:
        return _load_real_backend()
    except Exception as e:  # noqa: BLE001
        st.session_state["backend_error"] = f"{type(e).__name__}: {e}"
        return mock_desk.triage_ticket, "mock (real backend not available)"


def _pred(x):
    if isinstance(x, dict):
        return {"label": str(x.get("label", "?")), "confidence": float(x.get("confidence", 0))}
    return {"label": str(x), "confidence": 0.0}


ON_CALL, REVIEW, AUTO = "ESCALATE_ONCALL", "HUMAN_REVIEW", "AUTO_DRAFT_READY"
STATUS_TEXT = {ON_CALL: "Escalate to on-call engineer", REVIEW: "Needs human review",
               AUTO: "Auto-draft ready for agent review"}


def normalize_result(r: dict) -> dict:
    """Map the backend's output to the UI contract. Edit here if key names differ."""
    esc = r.get("escalation", {})
    if isinstance(esc, bool):
        esc = {"escalate": esc, "reasons": []}
    status = r.get("status")
    if status not in STATUS_TEXT:   # mock / older backends only say escalate yes or no
        oncall = any("incident" in x.lower() for x in esc.get("reasons", []))
        status = (ON_CALL if oncall else REVIEW) if esc.get("escalate") else AUTO
    return {
        "status": status,
        "risks": list(r.get("risks", [])),
        "burst": r.get("burst") or {},
        "root_cause": r.get("root_cause"),
        "problem": r.get("problem"),             # problem database entry (Track A, store.py)
        "engine": r.get("engine"),
        "unverified": list(r.get("unverified", [])),
        "language": r.get("language", "?"),
        "type": _pred(r.get("type")),
        "queue": _pred(r.get("queue")),
        "priority": _pred(r.get("priority")),
        "escalation": {"escalate": bool(esc.get("escalate")), "reasons": list(esc.get("reasons", []))},
        "retrieved": list(r.get("retrieved", [])),
        "draft": r.get("draft"),
        "cited_ids": list(r.get("cited_ids", [])),
        "pii_found": list(r.get("pii_found", [])),
        "latency_ms": r.get("latency_ms", {}),
    }


def run_triage(subject: str | None, body: str, live: bool = True) -> dict:
    """Validate input, call the pipeline, and return a normalized result (raises on bad input).

    live=False: replay without recording (no burst, no root-cause grouping, no problem database)."""
    body = (body or "").strip()
    if not any(ch.isalnum() for ch in body):
        raise ValueError("empty")
    body = body[:MAX_CHARS]
    fn, _ = get_backend()
    t0 = datetime.now()
    try:
        raw = fn((subject or "").strip() or None, body, live=live)
    except TypeError:                      # mock / older backends take no live flag
        raw = fn((subject or "").strip() or None, body)
    res = normalize_result(raw)
    res["wall_ms"] = round((datetime.now() - t0).total_seconds() * 1000, 1)
    return res


def close_problem(rec: dict, reply: str, agent: str, live_id: str | None = None) -> int | None:
    """Ticket resolved in the console: mark its problem resolved in the problem database (store.py).

    Unlike the precedent store, this also records an approved AI draft: the problem IS resolved, and
    the record says who approved what. Returns the problem_id, or None (mock backend / no problem)."""
    pid = ((rec.get("triage") or {}).get("problem") or {}).get("problem_id")
    if pid is None or not (reply or "").strip() or "mock" in get_backend()[1]:
        return None
    from sentineldesk import store
    store.resolve_problem(pid, reply, agent, precedent_id=live_id)
    return pid


def learn_from_resolution(rec: dict, reply: str, ai_draft: str | None, agent: str) -> str | None:
    """Turn a human resolution into a live precedent (pipeline.resolve_ticket, P2's learning loop).

    Only when a person actually wrote or changed the reply: an unedited AI draft is not indexed, so
    the system never learns from its own output. Skipped on the mock backend. Returns the LIVE id.
    """
    if (reply or "").strip() == (ai_draft or "").strip() or "mock" in get_backend()[1]:
        return None
    from sentineldesk.pipeline import resolve_ticket
    res = rec["triage"]
    out = resolve_ticket(rec.get("subject") or None, rec["body"], reply, resolved_by=agent,
                         queue=rec.get("group_override") or res["queue"]["label"],
                         type_=rec.get("ticket_type") or res["type"]["label"], language=res["language"])
    return out["ticket_id"]


def backend_sidebar():
    with st.sidebar:
        st.toggle("Use mock backend", key="force_mock")
        _, name = get_backend()
        st.caption(f"Backend: **{name}**")
        if "mock" in name and not st.session_state.get("force_mock") \
                and st.session_state.get("backend_error"):
            with st.expander("Why the mock?"):
                st.code(st.session_state["backend_error"])


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner="Loading ticket history…")
def load_kb() -> tuple[pd.DataFrame, bool]:
    """Historical (80% split) tickets. Returns (df, is_real_data)."""
    if DATA_PATH.exists():
        df = pd.read_parquet(DATA_PATH)
        # same KB as the pipeline (sentineldesk.data.load_kb): drop the rows with no answer
        df = df[df["answer"].notna() & (df["answer"].astype(str).str.strip() != "")].reset_index(drop=True)
        real = True
    else:  # tiny stand-in so the UI still works before the data file exists
        rows = []
        for topic, items in mock_desk.KB.items():
            for tid, subj, ans in items:
                rows.append({"ticket_id": tid, "subject": subj, "body": subj, "answer": ans,
                             "type": "Incident" if topic == "outage" else "Request",
                             "queue": {"outage": "Technical Support", "billing": "Billing and Payments",
                                       "login": "IT Support", "sales": "Sales and Pre-Sales"}.get(
                                 topic, "Customer Service"),
                             "priority": "high" if topic == "outage" else "medium",
                             "language": "de" if mock_desk.GERMAN_HINTS.search(ans) else "en",
                             "tag_1": topic.title()})
        df, real = pd.DataFrame(rows), False
    subj = df["subject"].fillna("").astype(str).str.strip()
    df["subject"] = subj.where(subj != "", None)
    if "ticket_id" not in df:
        df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    return df, real


_lock = threading.Lock()


def load_live() -> list[dict]:
    if not LIVE_PATH.exists():
        return []
    try:
        return json.loads(LIVE_PATH.read_text())
    except json.JSONDecodeError:
        return []


def save_live(tickets: list[dict]):
    LIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_PATH.write_text(json.dumps(tickets, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ ticket record rules
# Users can only open Incidents and Requests (Problems and Changes are raised by the organisation
# from incidents), so the form's choice is the ticket type of record. The model's type is kept as
# triage["type"] and shown as the AI's opinion.
KIND_TYPE = {"incident": "Incident", "request": "Request"}
PRI_RANK = {"high": 0, "medium": 1, "low": 2}


def form_priority(impact_idx: int | None, urgency_idx: int | None) -> str | None:
    """ITIL impact x urgency matrix (each 0=low .. 2=high) -> high / medium / low."""
    if impact_idx is None or urgency_idx is None:
        return None
    score = impact_idx + urgency_idx
    return "high" if score >= 3 else "medium" if score == 2 else "low"


def ticket_priority(kind: str, model_priority: str, user_priority: str | None) -> str:
    """Incidents take the more urgent of the model and the impact x urgency matrix (a missed outage
    costs more than a false alarm). Requests keep the model's priority."""
    if kind == "incident" and user_priority:
        return min(model_priority, user_priority, key=lambda p: PRI_RANK.get(p, 2))
    return model_priority


def add_ticket(kind: str, user: str, subject: str, body: str, extra: dict, res: dict) -> dict:
    with _lock:
        tickets = load_live()
        prefix = "INC" if kind == "incident" else "REQ"
        n = sum(t["number"].startswith(prefix) for t in tickets) + 1
        status = res.get("status", ON_CALL if res["escalation"]["escalate"] else AUTO)
        user_p = form_priority(extra.get("impact_idx"), extra.get("urgency_idx"))
        rec = {
            "number": f"{prefix}{n:07d}",
            "kind": kind, "ticket_type": KIND_TYPE.get(kind, "Request"), "user": user,
            "opened": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "subject": subject, "body": body, **extra,
            "user_priority": user_p,
            # The gate's on-call decision outranks both: a critical incident is P1.
            "priority": "high" if status == ON_CALL else ticket_priority(kind, res["priority"]["label"], user_p),
            "status": status,
            "state": "Escalated" if status == ON_CALL else "Awaiting agent",
            # Assignment: on-call for critical tickets, otherwise the predicted queue's group.
            "assigned_to": "On-call engineer" if status == ON_CALL else "",
            "triage": res,
        }
        tickets.append(rec)
        save_live(tickets)
    return rec


def update_ticket(number: str, **fields):
    with _lock:
        tickets = load_live()
        for t in tickets:
            if t["number"] == number:
                t.update(fields)
        save_live(tickets)


def load_metrics() -> dict | None:
    """Holdout metrics in the dashboard's shape, read from scripts/evaluate.py's report."""
    if not METRICS_PATH.exists():
        return None
    try:
        m = json.loads(METRICS_PATH.read_text())
    except json.JSONDecodeError:
        return None
    if "n_holdout" not in m:          # already in the dashboard's own shape
        return m
    hi, pipe = m.get("high_priority_incident", {}), m.get("pipeline", {})
    return {
        "n_test": m["n_holdout"],
        **{h: m[h] for h in ("type", "queue", "priority", "language") if h in m},
        "high_priority_incident_recall": hi.get("recall_gate_hard_rule", hi.get("recall_predicted_high")),
        "latency_ms": {"p50": pipe.get("latency_ms_p50_all"), "p95": pipe.get("latency_ms_p95_all"),
                       "p50_drafted": pipe.get("latency_ms_p50_drafted")},
        "confusion": m.get("confusion") or {},
        # extra real numbers from scripts/evaluate.py (Track A)
        "high_incident_recall_classifier": hi.get("recall_predicted_high"),
        "high_incident_support": hi.get("support"),
        "per_language": m.get("per_language") or {},
        "pipeline": pipe,
    }


def ticket_type(x: dict) -> str:
    """Type of record for a live ticket (the form's choice); older records fall back to the model."""
    return x.get("ticket_type") or x["triage"]["type"]["label"]


def ticket_priority_label(x: dict) -> str:
    """Effective priority of a live ticket: agent override, else the stored ticket priority."""
    return x.get("priority_override") or x.get("priority") or x["triage"]["priority"]["label"]


# ------------------------------------------------------------------ rendering
def status_badge(res: dict):
    status = res.get("status", AUTO)
    why = "; ".join(res["escalation"]["reasons"])
    kind = {ON_CALL: "esc", REVIEW: "warn", AUTO: "ok"}.get(status, "esc")
    badge(kind, STATUS_TEXT.get(status, status) + (f": {why}" if why else ""))


def render_triage(res: dict, show_draft: bool = True, draft_key: str = "draft"):
    status_badge(res)

    c = st.columns(5)
    for col, key, title in [(c[0], "type", "Type"), (c[1], "queue", "Queue"),
                            (c[2], "priority", "Priority")]:
        col.metric(title, res[key]["label"].title() if key == "priority" else res[key]["label"],
                   f"{res[key]['confidence']:.0%} sure", delta_color="off")
    c[3].metric("Language", {"en": "English", "de": "German"}.get(res["language"], res["language"]))
    lat = res.get("wall_ms") or res.get("latency_ms", {}).get("total", 0)
    c[4].metric("Latency", f"{lat:,.0f} ms")
    if res.get("pii_found"):
        st.caption(f"Masked before processing: {', '.join(res['pii_found'])}")
    render_problem(res.get("problem"))

    left, right = st.columns(2)
    if show_draft:
        with left:
            st.markdown("**Draft reply**")
            if res.get("draft"):
                st.text_area("Draft", res["draft"], height=230, key=draft_key,
                             label_visibility="collapsed")
                if res.get("cited_ids"):
                    st.caption("Based on: " + ", ".join(res["cited_ids"]))
            else:
                st.warning("No draft. Nothing in past resolutions supports this request, "
                           "so a human should answer it.")
    with (right if show_draft else left):
        st.markdown("**Matching past tickets**")
        render_retrieved(res.get("retrieved", []))


def render_problem(p: dict | None):
    """Where this ticket sits in the problem database (Track A, store.py)."""
    if not p:
        return
    if p["is_new"]:
        badge("warn", f"New problem: added to the problem database as #{p['problem_id']}")
    else:
        state = "resolved" if p["status"] == "resolved" else "still open"
        badge("esc" if p["occurrences"] >= 3 and p["status"] != "resolved" else "ok",
              f"Known problem #{p['problem_id']} ({state}), reported {p['occurrences']} times. "
              f"Closest match {p['similarity']:.2f}")
        if p.get("resolution"):
            st.caption(f"Earlier resolution: {p['resolution'][:300]}")
    if p.get("related"):
        st.caption("Most related problems already in the database: " + "; ".join(
            f"#{x['problem_id']} {x['title'][:50]} ({x['similarity']:.2f}, {x['occurrences']}x, {x['status']})"
            for x in p["related"]))


def render_retrieved(items: list[dict]):
    if not items:
        st.info("No similar past tickets found.")
        return
    df = pd.DataFrame(items)
    cols = [c for c in ["ticket_id", "similarity", "language", "subject", "answer_snippet"]
            if c in df.columns]
    st.dataframe(df[cols], hide_index=True, use_container_width=True,
                 column_config={"similarity": st.column_config.ProgressColumn(
                     "similarity", min_value=0.0, max_value=1.0, format="%.2f")})
