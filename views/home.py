import streamlit as st

from sentinel_ui.common import icon, inject_css, load_kb, load_live, stat_strip

inject_css()
kb, _ = load_kb()
live = load_live()

st.markdown(
    """
    <div class="hero"><div class="bg"></div><div class="grid"></div><div class="scan"></div>
      <div class="in">
        <div class="k">AI service management for Northeastern ITS</div>
        <div class="h">Every ticket triaged in seconds. Every reply backed by evidence.</div>
        <div class="p">SentinelDesk reads incoming tickets in English and German, routes them to the right team,
        escalates real outages immediately, and drafts replies grounded only in how past tickets were solved.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

hi_inc = int(round(((kb.priority == "high") & (kb.type == "Incident")).mean() * 100))
stat_strip([(len(kb), "", "resolved tickets in the knowledge base"),
            (kb["queue"].nunique(), "", "support teams routed automatically"),
            (2, "", "languages understood and answered"),
            (hi_inc, "%", "of tickets escalated straight to on-call")])

cards = [("portal", "Customer portal", "Students and staff sign in, report incidents or request help, and track every ticket.",
          "views/customer.py", "Open customer portal"),
         ("table", "Organisation", "A ServiceNow-style queue with predicted team, priority, SLA timers and an AI assistant.",
          "views/agent.py", "Open organisation console"),
         ("chart", "Dashboard", "Volume, urgency and routing patterns, plus model accuracy on unseen tickets.",
          "views/dashboard.py", "Open dashboard")]
cols = st.columns(3, gap="medium")
for col, (ic, title, desc, page, label) in zip(cols, cards):
    with col:
        st.markdown(f'<div class="card"><div class="ic">{icon(ic)}</div><div class="ct">{title}</div>'
                    f'<div class="cd">{desc}</div></div>', unsafe_allow_html=True)
        st.page_link(page, label=label, icon=":material/arrow_forward:")

st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
st.markdown('<div class="ph"><div><div class="t">How a ticket moves through SentinelDesk</div></div></div>',
            unsafe_allow_html=True)
steps = [("search", "Understand", "Detect the language and mask personal data before anything else runs."),
         ("route", "Classify and route", "Predict type, team and priority, each with a confidence score."),
         ("shield", "Safety gate", "Send outages, low-confidence and unsupported requests to a human."),
         ("spark", "Grounded draft", "Reply in the customer's language using only cited past resolutions.")]
html = "".join(f'<div class="card step"><div class="ic">{icon(i)}</div><div class="n">Step {k}</div>'
               f'<div class="ct">{t}</div><div class="cd">{d}</div></div>'
               for k, (i, t, d) in enumerate(steps, 1))
st.markdown(f'<div class="steps">{html}</div>', unsafe_allow_html=True)
st.caption(f"{len(live)} tickets submitted through the portal in this demo.")
