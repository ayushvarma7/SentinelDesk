from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from sentinel_ui.common import (DEMO_USERS, ON_CALL, REVIEW, SERVICES, T, add_ticket, badge, img_uri,
                                inject_css, load_live, run_triage, ticket_priority_label, ticket_type)

inject_css()
st.session_state.setdefault("lang", "en")
st.session_state.setdefault("user", None)
st.session_state.setdefault("svc", SERVICES[0])

TILE_ICONS = {"Wi-Fi (NUwave)": ":material/wifi:", "Canvas": ":material/menu_book:",
              "Email (Outlook)": ":material/mail:", "Account or password": ":material/key:",
              "Student Hub": ":material/apps:", "Billing portal": ":material/credit_card:"}


def lang_switch(col):
    with col:
        pick = st.segmented_control("Language", ["en", "de"], key="lang_pick",
                                    default=st.session_state.lang,
                                    format_func=lambda x: {"en": "English", "de": "Deutsch"}[x],
                                    label_visibility="collapsed")
    if pick:
        st.session_state.lang = pick


def hero(kicker: str, title: str, text: str, photo: str | None, extra: str = ""):
    layer = (f'<div class="photo" style="background-image:url({photo})"></div><div class="shade"></div>'
             if photo else '<div class="bg"></div><div class="grid"></div><div class="scan"></div>')
    st.markdown(f'<div class="hero">{layer}<div class="in"><div class="k">{kicker}</div>'
                f'<div class="h">{title}</div><div class="p">{text}</div>{extra}</div></div>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------ sign-in
if not st.session_state.user:
    top = st.columns([5, 1.4])
    lang_switch(top[1])
    t = T[st.session_state.lang]
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        hero(t["portal"], t["side_h"], t["side_p"], img_uri("login.jpg"))
    with right:
        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown(f"#### {t['login']}")
            email = st.text_input(t["email"], placeholder="husky@northeastern.edu")
            pw = st.text_input(t["password"], type="password")
            if st.form_submit_button(t["signin"], type="primary", use_container_width=True):
                acct = DEMO_USERS.get(email.strip().lower())
                if acct and acct[0] == pw:
                    st.session_state.user = {"email": email.strip().lower(), "name": acct[1]}
                    st.rerun()
                else:
                    st.error(t["bad_login"])
        st.caption("Demo accounts: nima@northeastern.edu / husky2026 · demo@northeastern.edu / demo")
    st.stop()

# ------------------------------------------------------------------ signed in
user = st.session_state.user
top = st.columns([5, 1.4, 0.8, 0.5])
lang_switch(top[1])
t = T[st.session_state.lang]
if top[2].button(t["signout"], use_container_width=True):
    st.session_state.user = None
    st.rerun()
initials = "".join(w[0] for w in user["name"].split()[:2]).upper()
top[3].markdown(f'<div class="avatar">{initials}</div>', unsafe_allow_html=True)

# service status from live tickets: the burst detector fired in the last hour, or 3+ urgent incidents
live = load_live()
cutoff = datetime.now() - timedelta(hours=1)
recent = [x for x in live if datetime.strptime(x["opened"], "%Y-%m-%d %H:%M") >= cutoff]
recent_urgent = [x for x in recent if ticket_priority_label(x) == "high" and ticket_type(x) == "Incident"]
outage = len(recent_urgent) >= 3 or any((x["triage"].get("burst") or {}).get("active") for x in recent)
status_html = (f'<div style="margin-top:1.2rem;display:inline-flex;align-items:center;gap:.55rem;'
               f'background:rgba(255,255,255,.1);padding:.45rem .85rem;border-radius:999px;font-size:.92rem">'
               f'<span style="width:9px;height:9px;border-radius:50%;background:{"#F87171" if outage else "#34D399"}">'
               f'</span>{t["status_bad"] if outage else t["status_ok"]}</div>')
hero(t["hero_k"], t["hero_h"].format(name=user["name"].split()[0]), t["hero_p"],
     img_uri("portal_hero.jpg"), status_html)

st.markdown(f"<div style='height:1rem'></div><div class='ph'><div><div class='t'>{t['popular']}</div></div></div>",
            unsafe_allow_html=True)
tiles = st.columns(6)
for col, (name, ic) in zip(tiles, TILE_ICONS.items()):
    if col.button(name, icon=ic, use_container_width=True, key=f"tile_{name}"):
        st.session_state.svc = name


def submit(kind: str, subject: str, body: str, extra: dict):
    try:
        with st.spinner("…"):
            res = run_triage(subject, body)
    except ValueError:
        st.error(t["empty"])
        return
    except Exception as e:  # noqa: BLE001
        st.error(f"Something went wrong while submitting: {type(e).__name__}: {e}")
        return
    rec = add_ticket(kind, user["email"], subject, body, extra, res)
    st.success(t["submitted"].format(num=rec["number"]))
    # Problem database (Track A): reassure the customer when others already reported the same issue.
    prob = res.get("problem") or {}
    de = st.session_state.get("lang") == "de"
    if prob and not prob.get("is_new") and prob.get("occurrences", 0) >= 2:
        if prob.get("status") == "resolved" and prob.get("resolution"):
            st.info(("Dieses Problem ist bekannt und wurde bereits gelöst. Bisherige Lösung: "
                     if de else "This is a known issue that has been resolved before. Earlier resolution: ")
                    + prob["resolution"][:300])
        else:
            st.info((f"Dieses Problem wurde bereits {prob['occurrences']} Mal gemeldet. Unser Team arbeitet daran."
                     if de else f"This issue has already been reported {prob['occurrences']} times. "
                                "Our team is working on it."))
    if rec["status"] == ON_CALL:
        badge("esc", t["escalated"])
    else:
        badge("ok", t["queued"].format(queue=res["queue"]["label"]))
    # Self-help suggestions only when the gate found good precedents and nothing risky.
    sims = [r for r in res.get("retrieved", []) if r.get("answer_snippet")][:3]
    if sims and rec["status"] not in (ON_CALL,) and not res.get("risks") \
            and not (rec["status"] == REVIEW and not res.get("draft")):
        st.markdown(t["similar"])
        for r in sims:
            with st.expander(r.get("subject") or r.get("ticket_id", "")):
                st.write(r["answer_snippet"])


st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
tab_inc, tab_req, tab_my = st.tabs([t["tab_inc"], t["tab_req"], t["tab_my"]])

with tab_inc:
    with st.form("incident"):
        a, b, c = st.columns(3)
        service = a.selectbox(t["service"], SERVICES, index=SERVICES.index(st.session_state.svc))
        impact = b.selectbox(t["impact"], t["impact_opts"])
        urgency = c.selectbox(t["urgency"], t["urgency_opts"], index=1)
        subj = st.text_input(t["subject"], key="inc_subj")
        body = st.text_area(t["details"], height=150, key="inc_body")
        go = st.form_submit_button(t["submit_inc"], type="primary")
    if go:
        submit("incident", subj, body, {"service": service, "impact": impact, "user_urgency": urgency,
                                        "impact_idx": t["impact_opts"].index(impact),
                                        "urgency_idx": t["urgency_opts"].index(urgency)})

with tab_req:
    with st.form("request"):
        category = st.selectbox(t["category"], t["categories"])
        subj = st.text_input(t["subject"], key="req_subj")
        body = st.text_area(t["details"], height=150, key="req_body")
        go = st.form_submit_button(t["submit_req"], type="primary")
    if go:
        submit("request", subj, body, {"category": category})

with tab_my:
    mine = [x for x in load_live() if x["user"] == user["email"]]
    if not mine:
        st.info(t["no_tickets"])
    else:
        df = pd.DataFrame([{t["number"]: x["number"], t["opened"]: x["opened"],
                            t["subject"]: x["subject"] or x["body"][:60],
                            t["team"]: x.get("group_override") or x["triage"]["queue"]["label"],
                            t["status"]: x["state"]} for x in reversed(mine)])
        st.dataframe(df, hide_index=True, use_container_width=True)
