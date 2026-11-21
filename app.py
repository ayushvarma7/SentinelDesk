"""
SentinelDesk. Run with:  streamlit run app.py

  /home       Overview
  /customer   Northeastern customer portal (sign-in, EN/DE, incident + request forms)
  /agent      Organisation console (ServiceNow-style list, ticket form, SLA, AI assistant)
  /dashboard  Analytics and model performance
  /problems   Problem database: every logged ticket, distinct problems, search, resolve
"""
import streamlit as st

st.set_page_config(page_title="SentinelDesk", page_icon=":material/shield:", layout="wide")

pages = [
    st.Page("views/home.py", title="Overview", icon=":material/dashboard_customize:", url_path="home", default=True),
    st.Page("views/customer.py", title="Customer portal", icon=":material/support_agent:", url_path="customer"),
    st.Page("views/agent.py", title="Organisation", icon=":material/table_view:", url_path="agent"),
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/monitoring:", url_path="dashboard"),
    st.Page("views/problems.py", title="Problems", icon=":material/database:", url_path="problems"),
]
st.navigation(pages).run()
