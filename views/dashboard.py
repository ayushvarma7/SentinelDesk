import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from sentinel_ui.common import METRICS_PATH, header, inject_css, load_kb, load_live, load_metrics, stat_strip

inject_css()
header("Operations dashboard", "Ticket volume, urgency and routing patterns, plus how well the models perform")

kb, real = load_kb()
live = load_live()
if not real:
    st.warning("Ticket history file not found, so charts use a small sample.")

hist = kb[["type", "queue", "priority", "language"]].copy()
hist["source"] = "History"
live_df = pd.DataFrame([{
    "type": x["triage"]["type"]["label"], "queue": x["triage"]["queue"]["label"],
    "priority": x["triage"]["priority"]["label"], "language": x["triage"]["language"],
    "source": "Portal", "escalated": x["triage"]["escalation"]["escalate"],
    "latency": x["triage"].get("wall_ms") or x["triage"].get("latency_ms", {}).get("total"),
} for x in live])

include_live = st.toggle("Include tickets submitted through the portal", value=True,
                         disabled=live_df.empty)
df = pd.concat([hist, live_df[hist.columns]], ignore_index=True) \
    if include_live and not live_df.empty else hist

PRI_ORDER = ["high", "medium", "low"]
PRI_COLORS = alt.Scale(domain=PRI_ORDER, range=["#C8102E", "#E2A33B", "#9AA6B5"])

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
        color=alt.Color("type:N", title="Type"), tooltip=["language", "type", "tickets"],
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
    c[3].metric("High-priority incident recall", f"{rec:.1%}" if rec is not None else "n/a",
                help="Of the truly urgent incidents, how many we flagged. The number that matters most.")
    p95 = (m.get("latency_ms") or {}).get("p95")
    c[4].metric("Latency p95", f"{p95:,.0f} ms" if p95 is not None else "n/a")
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

# ------------------------------------------------------------------ live operations
if not live_df.empty:
    st.subheader("Live portal tickets")
    c = st.columns(3)
    c[0].metric("Escalated to on-call", f"{live_df.escalated.mean():.0%}")
    lat = live_df["latency"].dropna()
    c[1].metric("Median latency", f"{lat.median():,.0f} ms" if len(lat) else "n/a")
    c[2].metric("p95 latency", f"{lat.quantile(.95):,.0f} ms" if len(lat) else "n/a")
