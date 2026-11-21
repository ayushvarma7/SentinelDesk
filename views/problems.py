"""Problem database (Track A, src/sentineldesk/store.py).

Every live ticket is logged; a ticket that matches no stored problem is added as a new one, and a
repeat raises the count. Here an agent can search it, open a problem to see every ticket attached to
it, resolve or reopen it, and read the triage log.
"""
import pandas as pd
import streamlit as st

from sentinel_ui.common import badge, header, inject_css, stat_strip

inject_css()
header("Problem database", "Every ticket the system has handled, grouped into distinct problems")

try:
    from sentineldesk import config, store
    stats = store.stats()
except Exception as e:  # noqa: BLE001
    st.error(f"Problem database unavailable: {type(e).__name__}: {e}")
    st.stop()

stat_strip([(stats["tickets_logged"], "", "tickets logged"),
            (stats["problems"], "", "distinct problems"),
            (stats["recurring_problems"], "", "reported more than once"),
            (stats["open_problems"], "", "open"),
            (stats["resolved_problems"], "", "resolved")])

tab_search, tab_problems, tab_log = st.tabs(["Search", "Problems", "Triage log"])

# ------------------------------------------------------------------ search (read-only)
with tab_search:
    st.caption("Check whether a problem is already known before raising it. Searching records nothing.")
    q = st.text_area("Describe the problem", height=90, key="pdb_query",
                     placeholder="e.g. Outlook stopped receiving new emails this morning")
    if st.button("Search", type="primary", disabled=not q.strip()):
        from sentineldesk import retrieve
        from sentineldesk.embed import encode
        vec = encode([q.strip()], is_query=True)[0]
        hits = store.search(vec, k=5)
        if hits and hits[0]["same_problem"]:
            h = hits[0]
            badge("ok" if h["status"] == "resolved" else "warn",
                  f"Known problem #{h['problem_id']}: {h['title']} ({h['status']}, reported {h['occurrences']} times)")
            if h.get("resolution"):
                st.caption(f"Resolution: {h['resolution'][:400]}")
        else:
            badge("warn", "Not in the problem database yet. It will be added when a ticket like this is submitted.")
        if hits:
            st.markdown("**Most related problems in the database**")
            st.dataframe(pd.DataFrame(hits)[["problem_id", "title", "similarity", "occurrences", "status"]],
                         hide_index=True, use_container_width=True,
                         column_config={"similarity": st.column_config.ProgressColumn(
                             "similarity", min_value=0.0, max_value=1.0, format="%.2f")})
        prec = retrieve.search(vec, 5, include_live=True, query_text=q.strip()) if retrieve.is_ready() else []
        if prec:
            st.markdown("**Most related resolved tickets (knowledge base)**")
            st.dataframe(pd.DataFrame([{"ticket_id": p.ticket_id, "similarity": round(p.score, 3),
                                        "language": p.language, "subject": p.subject,
                                        "answer": p.answer[:200]} for p in prec]),
                         hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ problems
with tab_problems:
    rows = store.problems(limit=500)
    if not rows:
        st.info("No problems yet. Submit a ticket in the customer portal and it appears here.")
    else:
        df = pd.DataFrame(rows)
        f1, f2 = st.columns([1, 2])
        status = f1.selectbox("Status", ["all", "open", "resolved"])
        text = f2.text_input("Filter by title", "")
        view = df if status == "all" else df[df["status"] == status]
        if text.strip():
            view = view[view["title"].str.contains(text.strip(), case=False, na=False)]
        st.dataframe(view[["problem_id", "title", "type", "queue", "priority", "occurrences", "status",
                           "first_seen", "last_seen"]], hide_index=True, use_container_width=True)

        pid = st.selectbox("Open a problem", view["problem_id"].tolist(),
                           format_func=lambda i: f"#{i} · {df.loc[df.problem_id == i, 'title'].iloc[0][:70]}")
        p = store.get_problem(pid) if pid is not None else None
        if p:
            st.markdown(f"### #{p['problem_id']} · {p['title']}")
            c = st.columns(4)
            c[0].metric("Reported", f"{p['occurrences']}x")
            c[1].metric("Status", p["status"].title())
            c[2].metric("Team", p["queue"] or "?")
            c[3].metric("Priority", (p["priority"] or "?").title())
            st.text_area("First report (PII masked)", p["text"], height=100, disabled=True)
            if p["status"] == "resolved":
                badge("ok", f"Resolved by {p['resolved_by']} at {p['resolved_at']}"
                            + (f" · knowledge base precedent {p['precedent_id']}" if p.get("precedent_id") else ""))
                st.caption(p["resolution"] or "")
                if st.button("Reopen problem"):
                    store.reopen_problem(pid)
                    st.rerun()
            else:
                with st.form(f"resolve_{pid}"):
                    res_text = st.text_area("Resolution", height=90)
                    who = st.text_input("Resolved by", "IT service desk")
                    if st.form_submit_button("Mark problem resolved", type="primary"):
                        try:
                            store.resolve_problem(pid, res_text, who)
                            st.toast(f"Problem #{pid} resolved")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            st.markdown("**Tickets attached to this problem**")
            st.dataframe(pd.DataFrame(store.problem_tickets(pid)), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ triage log
with tab_log:
    logs = store.recent_logs(limit=500)
    if not logs:
        st.info("Nothing logged yet.")
    else:
        st.dataframe(pd.DataFrame(logs), hide_index=True, use_container_width=True)
    with st.expander("Reset the problem database (demo)"):
        st.caption(f"Deletes every logged ticket and problem in `{config.DB_PATH.name}`. "
                   "The knowledge base and learned precedents are not touched.")
        if st.checkbox("I understand this cannot be undone") and st.button("Reset", type="secondary"):
            store.reset()
            st.toast("Problem database cleared")
            st.rerun()
