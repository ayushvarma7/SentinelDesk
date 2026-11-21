"""
SentinelDesk. Run with:  streamlit run app.py

  /home       Overview
  /triage     Live triage console (paste any ticket; judges' view)
  /customer   Northeastern customer portal (sign-in, EN/DE, incident + request forms)
  /agent      Organisation console (ServiceNow-style list, ticket form, SLA, AI assistant)
  /dashboard  Analytics and model performance
  /problems   Problem database: every logged ticket, distinct problems, search, resolve
"""
from pathlib import Path

import streamlit as st

# Red Northeastern shield (assets/favicon.png, drawn from assets/mark.svg) in the browser tab.
st.set_page_config(page_title="SentinelDesk", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"),
                   layout="wide")

pages = [
    st.Page("views/home.py", title="Overview", icon=":material/dashboard_customize:", url_path="home", default=True),
    st.Page("views/triage.py", title="Live triage", icon=":material/bolt:", url_path="triage"),
    st.Page("views/customer.py", title="Customer portal", icon=":material/support_agent:", url_path="customer"),
    st.Page("views/agent.py", title="Organisation", icon=":material/table_view:", url_path="agent"),
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/monitoring:", url_path="dashboard"),
    st.Page("views/problems.py", title="Problems", icon=":material/database:", url_path="problems"),
]
st.navigation(pages).run()
