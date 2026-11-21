"""Organisation page: ServiceNow-style ticket list, ticket form with SLA, bot panel, activity log."""
from datetime import datetime

import pandas as pd
import streamlit as st

from sentinel_ui.common import (ON_CALL, backend_sidebar, close_problem, inject_css, learn_from_resolution, load_kb, load_live, render_problem,
                                render_retrieved, run_triage, status_badge, ticket_priority_label, ticket_type,
                                update_ticket)

inject_css()
backend_sidebar()

P_MAP = {"high": "P1", "medium": "P2", "low": "P3"}
P_BACK = {v: k for k, v in P_MAP.items()}
SLA_HOURS = {"P1": 4, "P2": 8, "P3": 24}
STATES = ["New", "Awaiting agent", "In progress", "Escalated", "On hold", "Resolved", "Closed"]
FMT = "%Y-%m-%d %H:%M"

L = {
    "en": {"title": "Organisation", "sub": "Northeastern ITS service desk", "search": "Search INC or summary",
           "inc": "INC", "summary": "Summary", "p": "P", "date": "Date", "status": "Status",
           "assigned": "Assigned to (Dept)", "tagtype": "Tag / Type", "pick": "Select a ticket to open it.",
           "body": "Customer message", "answer": "Resolution", "form": "Ticket form",
           "caller": "Caller", "state": "State", "priority": "Priority", "group": "Assignment group",
           "save": "Save changes", "saved": "Saved", "sla": "SLA", "bot": "AI assistant",
           "assignee": "Assigned to", "open_in_group": "open tickets in this group",
           "use": "Send this reply and resolve", "ask": "Ask the bot", "activity": "Activity",
           "no_activity": "No activity yet.", "evidence": "Past tickets used as evidence",
           "no_draft": "No draft: nothing in past resolutions supports this request. A human should reply."},
    "de": {"title": "Organisation", "sub": "Northeastern ITS Service Desk", "search": "INC oder Zusammenfassung suchen",
           "inc": "INC", "summary": "Zusammenfassung", "p": "P", "date": "Datum", "status": "Status",
           "assigned": "Zugewiesen an (Abt.)", "tagtype": "Tag / Typ", "pick": "Wählen Sie ein Ticket aus.",
           "body": "Kundennachricht", "answer": "Lösung", "form": "Ticketformular",
           "caller": "Anrufer", "state": "Status", "priority": "Priorität", "group": "Zuweisungsgruppe",
           "save": "Änderungen speichern", "saved": "Gespeichert", "sla": "SLA", "bot": "KI-Assistent",
           "assignee": "Zugewiesen an", "open_in_group": "offene Tickets in dieser Gruppe",
           "use": "Antwort senden und lösen", "ask": "Bot fragen", "activity": "Aktivität",
           "no_activity": "Noch keine Aktivität.", "evidence": "Verwendete frühere Tickets",
           "no_draft": "Kein Entwurf: Keine frühere Lösung stützt diese Anfrage. Ein Mensch sollte antworten."},
}


def now() -> str:
    return datetime.now().strftime(FMT)


# ------------------------------------------------------------------ top bar: title, EN/DE, profile
st.session_state.setdefault("org_lang", "en")
bar = st.columns([6, 1.3, 0.5])
with bar[1]:
    pick = st.segmented_control("lang", ["en", "de"], default=st.session_state.org_lang,
                                format_func=lambda x: {"en": "EN", "de": "DE"}[x],
                                key="org_lang_pick", label_visibility="collapsed")
    if pick:
        st.session_state.org_lang = pick
t = L[st.session_state.org_lang]
bar[0].markdown(f'<div class="ph" style="margin:0"><div><div class="t">{t["title"]}</div>'
                f'<div class="s">{t["sub"]}</div></div></div>', unsafe_allow_html=True)
bar[2].markdown('<div class="avatar">IT</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ data
kb, real = load_kb()
if not real:
    st.warning("Ticket history file not found, so a small sample is shown.")
live = load_live()
tag_cols = [c for c in kb.columns if c.startswith("tag_")]

if tag_cols:
    first_tag = kb[tag_cols].bfill(axis=1).iloc[:, 0].fillna("")
else:
    first_tag = pd.Series("", index=kb.index)


def live_group(x):
    return x.get("group_override") or x["triage"]["queue"]["label"]


def live_priority(x):
    return P_MAP.get(ticket_priority_label(x), "P3")


live_rows = pd.DataFrame([{
    t["inc"]: x["number"], t["summary"]: x["subject"] or x["body"][:80],
    t["p"]: live_priority(x), t["date"]: x["opened"], t["status"]: x["state"],
    t["assigned"]: live_group(x),
    t["tagtype"]: ticket_type(x) + (f" · {x['service']}" if x.get("service") else ""),
} for x in reversed(live)])

hist_rows = pd.DataFrame({
    t["inc"]: kb["ticket_id"],
    t["summary"]: kb["subject"].fillna(kb["body"].str[:80]),
    t["p"]: kb["priority"].map(P_MAP),
    t["date"]: "—", t["status"]: "Resolved", t["assigned"]: kb["queue"],
    t["tagtype"]: kb["type"] + first_tag.map(lambda s: f" · {s}" if s else ""),
})
table = pd.concat([live_rows, hist_rows], ignore_index=True)

open_live = [x for x in live if x["state"] not in ("Resolved", "Closed")]
k = st.columns(4)
k[0].metric("Open tickets", len(open_live))
k[1].metric("Escalated", sum(x["state"] == "Escalated" for x in open_live))
k[2].metric("P1 open", sum(live_priority(x) == "P1" for x in open_live))
k[3].metric("Knowledge base", f"{len(kb):,}")

# ------------------------------------------------------------------ search + filters
f = st.columns([3, 1, 1.4, 2])
q = f[0].text_input("search", placeholder=t["search"], label_visibility="collapsed")
pf = f[1].multiselect(t["p"], ["P1", "P2", "P3"], placeholder=t["p"], label_visibility="collapsed")
sf = f[2].multiselect(t["status"], STATES, placeholder=t["status"], label_visibility="collapsed")
gf = f[3].multiselect(t["assigned"], sorted(table[t["assigned"]].dropna().unique()),
                      placeholder=t["assigned"], label_visibility="collapsed")
view = table
if q:
    view = view[view[t["summary"]].fillna("").str.contains(q, case=False, regex=False)
                | view[t["inc"]].str.contains(q, case=False, regex=False)]
if pf:
    view = view[view[t["p"]].isin(pf)]
if sf:
    view = view[view[t["status"]].isin(sf)]
if gf:
    view = view[view[t["assigned"]].isin(gf)]

event = st.dataframe(view, hide_index=True, use_container_width=True, height=330,
                     on_select="rerun", selection_mode="single-row", key="org_table")
rows = event.selection.rows if event and event.selection else []
if not rows:
    st.caption(t["pick"])
    st.stop()

number = view.iloc[rows[0]][t["inc"]]
rec = next((x for x in live if x["number"] == number), None)


# ------------------------------------------------------------------ helpers
def sla_status(p, opened, state, resolved_at):
    target = SLA_HOURS[p]
    try:
        start = datetime.strptime(opened, FMT)
    except (TypeError, ValueError):
        return 1.0, "Met (historical)", "#16a34a"
    end = datetime.strptime(resolved_at, FMT) if resolved_at else datetime.now()
    hours = (end - start).total_seconds() / 3600
    used, left = hours / target, target - hours
    if state in ("Resolved", "Closed"):
        ok = used <= 1
        return min(used, 1.0), "Met" if ok else "Breached", "#16a34a" if ok else "#dc2626"
    color = "#16a34a" if used < .5 else "#F2A900" if used < .9 else "#dc2626"
    label = f"{left:.1f} h left of {target} h" if left > 0 else f"Breached by {-left:.1f} h"
    return min(used, 1.0), label, color


def sla_bar(frac, label, color):
    st.markdown(
        f"""<div style="font-size:.9rem;margin:.6rem 0 .25rem"><b>{t['sla']}</b> · {label}</div>
        <div style="background:#e5e7eb;border-radius:4px;height:12px">
          <div style="width:{max(frac, .03)*100:.0f}%;background:{color};height:12px;border-radius:4px"></div>
        </div>""", unsafe_allow_html=True)


def log(text, current):
    return list(current or []) + [{"at": now(), "text": text}]


st.divider()

# ------------------------------------------------------------------ preview: body + answer
if rec:
    summary, body, answer = rec["subject"] or "(no subject)", rec["body"], rec.get("reply") or ""
    res = rec["triage"]
    row = None
else:
    row = kb[kb["ticket_id"] == number].iloc[0]
    summary = row["subject"] if isinstance(row["subject"], str) and row["subject"] else "(no subject)"
    body, answer = row["body"], row.get("answer") or ""
    res = st.session_state.get(f"bot_{number}")

st.subheader(f"{number} · {summary}")
pv = st.columns(2)
pv[0].text_area(t["body"], body, height=130, disabled=True)
pv[1].text_area(t["answer"], answer, height=130, disabled=True)

# ------------------------------------------------------------------ form (left) + assignee/bot (right)
left, right = st.columns([1.1, 1], gap="large")

with left:
    st.markdown(f"#### {t['form']}")
    if rec:
        p_now, g_now = live_priority(rec), live_group(rec)
        with st.form(f"form_{number}"):
            a, b = st.columns(2)
            a.text_input(t["inc"], number, disabled=True)
            b.text_input(t["caller"], rec["user"], disabled=True)
            a, b = st.columns(2)
            state = a.selectbox(t["state"], STATES,
                                index=STATES.index(rec["state"]) if rec["state"] in STATES else 0)
            prio = b.selectbox(t["priority"], ["P1", "P2", "P3"], index=["P1", "P2", "P3"].index(p_now))
            groups = sorted(kb["queue"].dropna().unique())
            group = st.selectbox(t["group"], groups, index=groups.index(g_now) if g_now in groups else 0)
            if st.form_submit_button(t["save"], type="primary"):
                changes, acts = {}, rec.get("activity", [])
                if state != rec["state"]:
                    changes["state"] = state
                    acts = log(f"State changed to {state}", acts)
                    if state in ("Resolved", "Closed"):
                        changes["resolved_at"] = now()
                if prio != p_now:
                    changes["priority_override"] = P_BACK[prio]
                    acts = log(f"Priority changed to {prio}", acts)
                if group != g_now:
                    changes["group_override"] = group
                    acts = log(f"Reassigned to {group}", acts)
                if changes:
                    update_ticket(number, **changes, activity=acts)
                    st.toast(t["saved"])
                    st.rerun()
        sla_bar(*sla_status(p_now, rec["opened"], rec["state"], rec.get("resolved_at")))
    else:
        a, b = st.columns(2)
        a.text_input(t["inc"], number, disabled=True)
        b.text_input(t["caller"], "Customer", disabled=True)
        a, b = st.columns(2)
        a.text_input(t["state"], "Resolved", disabled=True)
        b.text_input(t["priority"], P_MAP.get(row["priority"], "P3"), disabled=True)
        st.text_input(t["group"], row["queue"], disabled=True)
        sla_bar(*sla_status(P_MAP.get(row["priority"], "P3"), "", "Resolved", None))

with right:
    group_now = live_group(rec) if rec else row["queue"]
    who = (rec.get("assigned_to") or group_now) if rec else group_now
    open_n = sum(1 for x in live
                 if x["state"] not in ("Resolved", "Closed") and live_group(x) == group_now)
    st.markdown(
        f"""<div class="panel" style="display:flex;gap:.9rem;align-items:center;margin-bottom:1rem">
        <div class="avatar" style="margin:0">{''.join(w[0] for w in str(who).split()[:2]).upper()}</div>
        <div><div style="font-size:.82rem;color:var(--muted)">{t['assignee']}</div>
        <div style="font-size:1.05rem;font-weight:600">{who}</div>
        <div style="font-size:.85rem;color:var(--muted)">{group_now} · {open_n} {t['open_in_group']}</div></div></div>""",
        unsafe_allow_html=True)

    st.markdown(f"#### {t['bot']}")
    if res is None:
        if st.button(t["ask"]):
            try:
                st.session_state[f"bot_{number}"] = run_triage(   # history replay: not recorded
                    None if summary == "(no subject)" else summary, body, live=False)
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Pipeline failed: {type(e).__name__}: {e}")
    else:
        status_badge(res)
        ai_type = res["type"]["label"]
        if rec and ai_type != ticket_type(rec):
            ai_type = f"{ticket_type(rec)} (AI reads it as {ai_type})"
        st.caption(f"{ai_type} | {res['queue']['label']} | "
                   f"{P_MAP.get(res['priority']['label'], '?')} | "
                   f"{res['priority']['confidence']:.0%} sure | {res['language'].upper()}"
                   + (f" | {res['engine']}" if res.get("engine") else ""))
        if rec and rec.get("user_priority"):
            st.caption(f"Customer impact x urgency: {P_MAP.get(rec['user_priority'])} · "
                       f"model: {P_MAP.get(res['priority']['label'])} · ticket: {live_priority(rec)}")
        render_problem(res.get("problem"))       # problem database: new or known, count, related
        rc = res.get("root_cause") or {}
        if rc.get("suggest_problem"):
            st.info(f"Probable shared root cause across {len(rc['group'])} live issues: raise a Problem record"
                    + (f" (closest known Problem: {rc['known_problem']})" if rc.get("known_problem") else ""))
        if res.get("draft"):
            draft = st.text_area("draft", res["draft"], height=180, key=f"draft_{number}",
                                 label_visibility="collapsed")
            if res.get("cited_ids"):
                st.caption("Based on: " + ", ".join(res["cited_ids"]))
            if rec and rec["state"] not in ("Resolved", "Closed"):
                if st.button(t["use"], type="primary"):
                    acts = log("Reply sent, ticket resolved", rec.get("activity", []))
                    try:
                        live_id = learn_from_resolution(rec, draft, res.get("draft"), agent="IT service desk")
                    except Exception as e:  # noqa: BLE001  (never block resolving on the learning step)
                        live_id = None
                        acts = log(f"Could not add the resolution to the knowledge base: {e}", acts)
                    if live_id:
                        acts = log(f"Edited resolution added to the knowledge base as {live_id}", acts)
                    try:
                        pid = close_problem(rec, draft, agent="IT service desk", live_id=live_id)
                        if pid is not None:
                            acts = log(f"Problem #{pid} marked resolved in the problem database", acts)
                    except Exception as e:  # noqa: BLE001
                        acts = log(f"Could not update the problem database: {e}", acts)
                    update_ticket(number, state="Resolved", reply=draft, resolved_at=now(), activity=acts)
                    st.rerun()
        else:
            st.warning(t["no_draft"])
            # No AI draft (escalated, blocked, or withdrawn as ungrounded): the agent writes the reply.
            # A human-written reply is exactly what the learning loop wants, so it becomes a precedent
            # and the ticket's problem is marked resolved in the problem database.
            if rec and rec["state"] not in ("Resolved", "Closed"):
                manual = st.text_area("Your reply to the customer", height=160, key=f"manual_{number}",
                                      placeholder="Write the resolution the customer should receive")
                if st.button(t["use"], type="primary", key=f"send_manual_{number}",
                             disabled=not manual.strip()):
                    acts = log("Agent wrote the reply, ticket resolved", rec.get("activity", []))
                    try:
                        live_id = learn_from_resolution(rec, manual, None, agent="IT service desk")
                    except Exception as e:  # noqa: BLE001
                        live_id = None
                        acts = log(f"Could not add the resolution to the knowledge base: {e}", acts)
                    if live_id:
                        acts = log(f"Resolution added to the knowledge base as {live_id}", acts)
                    try:
                        pid = close_problem(rec, manual, agent="IT service desk", live_id=live_id)
                        if pid is not None:
                            acts = log(f"Problem #{pid} marked resolved in the problem database", acts)
                    except Exception as e:  # noqa: BLE001
                        acts = log(f"Could not update the problem database: {e}", acts)
                    update_ticket(number, state="Resolved", reply=manual, resolved_at=now(), activity=acts)
                    st.rerun()
        with st.expander(t["evidence"]):
            render_retrieved(res.get("retrieved", []))

# ------------------------------------------------------------------ activity log (bottom bar)
st.divider()
st.markdown(f"#### {t['activity']}")
acts = []
if rec:
    first = "Escalated to on-call" if rec.get("status", "") == ON_CALL \
        or (not rec.get("status") and rec["triage"]["escalation"]["escalate"]) \
        else "Sent to " + rec["triage"]["queue"]["label"]
    acts = [{"at": rec["opened"], "text": f"Opened by {rec['user']} via portal. {first}."}] + \
        list(rec.get("activity", []))
if acts:
    for a in reversed(acts):
        st.markdown(f"- `{a['at']}` {a['text']}")
else:
    st.caption(t["no_activity"])
