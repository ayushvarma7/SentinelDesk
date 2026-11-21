import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from datetime import datetime, timedelta

from sentinel_ui.common import (AUTO, METRICS_PATH, ON_CALL, REVIEW, STATUS_TEXT, header, inject_css, load_kb,
                                load_live, load_metrics, major_incidents, stat_strip, ticket_priority_label,
                                ticket_type)

inject_css()
header("Operations dashboard", "Ticket volume, urgency and routing patterns, plus how well the models perform")

kb, real = load_kb()
live = load_live()
if not real:
    st.warning("Ticket history file not found, so charts use a small sample.")

hist = kb[["type", "queue", "priority", "language"]].copy()
hist["source"] = "History"
live_df = pd.DataFrame([{
    "type": ticket_type(x), "queue": x.get("group_override") or x["triage"]["queue"]["label"],
    "priority": ticket_priority_label(x), "language": x["triage"]["language"],
    "source": "Portal", "escalated": x.get("status", ON_CALL if x["triage"]["escalation"]["escalate"] else "")
    == ON_CALL,
    "latency": x["triage"].get("wall_ms") or x["triage"].get("latency_ms", {}).get("total"),
    "status": x.get("status") or (ON_CALL if x["triage"]["escalation"]["escalate"] else AUTO),
    "opened": pd.to_datetime(x["opened"], errors="coerce"), "number": x["number"], "user": x["user"],
    "state": x.get("state", ""), "resolved_at": pd.to_datetime(x.get("resolved_at"), errors="coerce"),
    "pii": bool(x["triage"].get("pii_found")), "burst": bool((x["triage"].get("burst") or {}).get("active")),
} for x in live])

PRI_ORDER = ["high", "medium", "low"]
# Northeastern palette: red, black, warm grays
PRI_COLORS = alt.Scale(domain=PRI_ORDER, range=["#C8102E", "#3A3A38", "#B5B5B0"])
TYPE_COLORS = alt.Scale(domain=["Incident", "Problem", "Request", "Change"],
                        range=["#C8102E", "#000000", "#8A8A85", "#E8A0AB"])


STATUS_ORDER = [ON_CALL, REVIEW, AUTO]
SHORT = {ON_CALL: "On-call", REVIEW: "Human review", AUTO: "Auto-draft"}
STATUS_COLORS = alt.Scale(domain=[SHORT[s] for s in STATUS_ORDER], range=["#C8102E", "#3A3A38", "#B5B5B0"])
SLA_H = {"high": 4, "medium": 8, "low": 24}


def live_operations():
    if live_df.empty:
        st.info("No portal tickets yet. File one in the Customer portal or Live triage, or run "
                "`PYTHONPATH=src python scripts/seed_demo.py` for a realistic week of traffic.")
        return
    d = live_df.copy()
    d["outcome"] = d["status"].map(SHORT)
    d["day"] = d["opened"].dt.strftime("%a %d %b")
    d["day_sort"] = d["opened"].dt.normalize()
    now = datetime.now()
    open_ = ~d["state"].isin(["Resolved", "Closed"])
    sla = d["priority"].map(SLA_H).fillna(24)
    end = d["resolved_at"].fillna(pd.Timestamp(now))
    breached = (end - d["opened"]).dt.total_seconds() / 3600 > sla
    incidents = major_incidents(live)
    active = [i for i in incidents if i["active"]]

    stat_strip([(len(d), "", f"portal tickets since {d['opened'].min():%a %d %b}"),
                (round((d.status == AUTO).mean() * 100), "%", "auto-draft ready"),
                (round((d.status == ON_CALL).mean() * 100), "%", "escalated to on-call"),
                (len(incidents), "", "major incidents detected")])
    c = st.columns(4)
    c[0].metric("Open now", int(open_.sum()))
    c[1].metric("Needs human review", f"{(d.status == REVIEW).mean():.0%}")
    c[2].metric("SLA breached", int(breached.sum()), help="P1 4 h, P2 8 h, P3 24 h from opening to resolution")
    c[3].metric("Tickets with PII masked", f"{d.pii.mean():.0%}")

    st.markdown("#### Major incidents (burst detection)")
    st.caption("Three or more near-identical reports within 30 minutes, in any language, become one major "
               "incident and go to the on-call engineer.")
    if incidents:
        st.dataframe(pd.DataFrame([{
            "Status": "ACTIVE" if i["active"] else "Over", "Started": f"{i['start']:%a %d %b %H:%M}",
            "Last report": f"{i['end']:%H:%M}", "Reports": i["count"], "Service": ", ".join(i["services"]) or "-",
            "First report": i["title"], "Tickets": ", ".join(i["numbers"])} for i in reversed(incidents)]),
            hide_index=True, use_container_width=True)
    else:
        st.caption("None detected yet.")

    l, r = st.columns(2)
    daily = d.groupby(["day_sort", "day", "outcome"]).size().reset_index(name="tickets")
    l.altair_chart(alt.Chart(daily).mark_bar().encode(
        x=alt.X("day:N", sort=alt.SortField("day_sort"), title=None),
        y=alt.Y("tickets:Q", title="Tickets"),
        color=alt.Color("outcome:N", scale=STATUS_COLORS, title="Gate decision"),
        tooltip=["day", "outcome", "tickets"]).properties(title="Tickets per day by gate decision", height=300),
        use_container_width=True)
    team = d.groupby(["queue", "outcome"]).size().reset_index(name="tickets")
    r.altair_chart(alt.Chart(team).mark_bar().encode(
        y=alt.Y("queue:N", sort="-x", title=None), x=alt.X("tickets:Q", title="Tickets"),
        color=alt.Color("outcome:N", scale=STATUS_COLORS, title="Gate decision"),
        tooltip=["queue", "outcome", "tickets"]).properties(title="Routing: team and gate decision", height=300),
        use_container_width=True)

    l, r = st.columns(2)
    hourly = d.assign(hour=d["opened"].dt.floor("h")).groupby(["hour", "burst"]).size().reset_index(name="tickets")
    hourly["kind"] = hourly["burst"].map({True: "Part of a major incident", False: "Normal"})
    l.altair_chart(alt.Chart(hourly).mark_bar(width=6).encode(
        x=alt.X("hour:T", title=None), y=alt.Y("tickets:Q", title="Tickets", stack=True),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["Part of a major incident", "Normal"],
                                                  range=["#C8102E", "#B5B5B0"]), title=None),
        tooltip=[alt.Tooltip("hour:T", format="%a %H:%M"), "kind", "tickets"]).properties(
        title="Arrivals per hour: outage spikes stand out", height=260), use_container_width=True)
    users = d.groupby(["user", "type"]).size().reset_index(name="tickets")
    r.altair_chart(alt.Chart(users).mark_bar().encode(
        y=alt.Y("user:N", sort="-x", title=None), x=alt.X("tickets:Q", title="Tickets"),
        color=alt.Color("type:N", scale=alt.Scale(domain=["Incident", "Request"], range=["#C8102E", "#3A3A38"]),
                        title="Filed as"),
        tooltip=["user", "type", "tickets"]).properties(title="Who files what", height=260),
        use_container_width=True)

    lat = d["latency"].dropna()
    c = st.columns(3)
    c[0].metric("Median latency", f"{lat.median():,.0f} ms" if len(lat) else "n/a")
    c[1].metric("p95 latency", f"{lat.quantile(.95):,.0f} ms" if len(lat) else "n/a")
    c[2].metric("Languages", " / ".join(f"{k.upper()} {v:.0%}" for k, v in
                                       d["language"].value_counts(normalize=True).items()))


tab_live, tab_hist, tab_model = st.tabs(["Live operations", "Ticket history (knowledge base)",
                                         "Model performance (holdout)"])
with tab_live:
    live_operations()

with tab_hist:
    include_live = st.toggle("Include tickets submitted through the portal", value=True,
                             disabled=live_df.empty)
    df = pd.concat([hist, live_df[hist.columns]], ignore_index=True) \
        if include_live and not live_df.empty else hist

    # ------------------------------------------------------------------ KPIs
    stat_strip([(len(df), "", "tickets"),
                (round(df.priority.eq("high").mean() * 100), "%", "high priority"),
                (round((df.priority.eq("high") & df.type.eq("Incident")).mean() * 100), "%",
                 "high-priority incidents, escalated to on-call"),
                (round(df.language.eq("de").mean() * 100), "%", "German tickets")])

    # ------------------------------------------------------------------ charts
    st.subheader("Where the work goes")
    l, r = st.columns(2)
    qp = df.groupby(["queue", "priority"]).size().reset_index(name="tickets")
    l.altair_chart(
        alt.Chart(qp).mark_bar().encode(
            y=alt.Y("queue:N", sort="-x", title=None),
            x=alt.X("tickets:Q", title="Tickets"),
            color=alt.Color("priority:N", scale=PRI_COLORS, sort=PRI_ORDER, title="Priority"),
            order=alt.Order("priority_rank:Q"),
            tooltip=["queue", "priority", "tickets"],
        ).transform_calculate(
            priority_rank="indexof(['high','medium','low'], datum.priority)"
        ).properties(title="Volume by team and priority", height=340),
        use_container_width=True)

    tp = df.groupby(["type", "priority"]).size().reset_index(name="tickets")
    tp["share"] = tp["tickets"] / tp["tickets"].sum()
    r.altair_chart(
        (alt.Chart(tp).mark_rect().encode(
            x=alt.X("priority:N", sort=PRI_ORDER, title="Priority"),
            y=alt.Y("type:N", title=None),
            color=alt.Color("share:Q", scale=alt.Scale(scheme="reds"), legend=None),
            tooltip=["type", "priority", "tickets", alt.Tooltip("share:Q", format=".1%")],
        ) + alt.Chart(tp).mark_text(fontSize=13).encode(
            x=alt.X("priority:N", sort=PRI_ORDER), y="type:N",
            text=alt.Text("share:Q", format=".0%"),
            color=alt.condition("datum.share > 0.12", alt.value("white"), alt.value("black")),
        )).properties(title="Type by priority (share of all tickets)", height=340),
        use_container_width=True)

    l, r = st.columns(2)
    lt = df.groupby(["language", "type"]).size().reset_index(name="tickets")
    l.altair_chart(
        alt.Chart(lt).mark_bar().encode(
            x=alt.X("language:N", title="Language"), y=alt.Y("tickets:Q", stack="normalize",
                                                             title="Share", axis=alt.Axis(format="%")),
            color=alt.Color("type:N", title="Type", scale=TYPE_COLORS), tooltip=["language", "type", "tickets"],
        ).properties(title="Ticket types by language", height=300),
        use_container_width=True)

    tag_cols = [c for c in kb.columns if c.startswith("tag_")]
    if tag_cols:
        tags = kb[tag_cols].stack().astype(str).str.strip().value_counts().head(15).reset_index()
        tags.columns = ["tag", "tickets"]
        r.altair_chart(
            alt.Chart(tags).mark_bar(color="#C8102E").encode(
                y=alt.Y("tag:N", sort="-x", title=None), x=alt.X("tickets:Q", title="Tickets"),
                tooltip=["tag", "tickets"],
            ).properties(title="Most common issue tags", height=300),
            use_container_width=True)


with tab_model:
    # ------------------------------------------------------------------ model performance
    st.subheader("Model performance on the 20% holdout")
    m = load_metrics()
    if not m:
        st.info(f"No metrics file yet. When the evaluation script writes `{METRICS_PATH.name}`, "
                "the scores appear here automatically.")
        st.code('{\n  "n_test": 5718,\n  "type": {"macro_f1": 0.0},\n  "queue": {"macro_f1": 0.0},\n'
                '  "priority": {"macro_f1": 0.0},\n  "high_priority_incident_recall": 0.0,\n'
                '  "latency_ms": {"p50": 0, "p95": 0},\n'
                '  "confusion": {"priority": {"labels": ["high","medium","low"], "matrix": [[0,0,0],[0,0,0],[0,0,0]]}}\n}',
                language="json")
    else:
        c = st.columns(5)
        for col, key in zip(c[:3], ["type", "queue", "priority"]):
            v = (m.get(key) or {}).get("macro_f1")
            col.metric(f"{key.title()} Macro-F1", f"{v:.3f}" if v is not None else "n/a")
        rec = m.get("high_priority_incident_recall")
        c[3].metric("Urgent recall", f"{rec:.1%}" if rec is not None else "n/a",
                    help="Of the truly urgent incidents, how many we flagged. The number that matters most.")
        p95 = (m.get("latency_ms") or {}).get("p95")
        c[4].metric("Latency p95", (f"{p95 / 1000:.1f} s" if p95 >= 1000 else f"{p95:,.0f} ms") if p95 is not None else "n/a")
        if m.get("n_test"):
            st.caption(f"Evaluated on {m['n_test']:,} unseen tickets.")

        conf = m.get("confusion") or {}
        if conf:
            tabs = st.tabs([f"{k.title()} confusion" for k in conf])
            for tab, (name, cm) in zip(tabs, conf.items()):
                labels, mat = cm["labels"], np.array(cm["matrix"])
                cdf = pd.DataFrame([{"actual": labels[i], "predicted": labels[j], "n": int(mat[i, j]),
                                     "row_share": mat[i, j] / max(mat[i].sum(), 1)}
                                    for i in range(len(labels)) for j in range(len(labels))])
                tab.altair_chart(
                    (alt.Chart(cdf).mark_rect().encode(
                        x=alt.X("predicted:N", sort=labels), y=alt.Y("actual:N", sort=labels),
                        color=alt.Color("row_share:Q", scale=alt.Scale(scheme="reds"), legend=None),
                        tooltip=["actual", "predicted", "n", alt.Tooltip("row_share:Q", format=".1%")])
                     + alt.Chart(cdf).mark_text().encode(
                        x=alt.X("predicted:N", sort=labels), y=alt.Y("actual:N", sort=labels),
                        text="n:Q")).properties(height=320),
                    use_container_width=True)

