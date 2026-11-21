"""Fill the console's ticket store with a realistic week of portal traffic, through the REAL pipeline.

    PYTHONPATH=src python scripts/seed_demo.py            # replaces data/live_tickets.json (backup kept)

What it creates (about 60 tickets over the last 7 days):
  * everyday traffic: a random sample of holdout ticket INPUTS (subject + body only; labels and answers are
    never read), filed as incidents or requests by the demo users;
  * four incident patterns, so burst detection and the dashboard have something real to show:
      - VPN outage, 2 days ago, 5 reports in 25 minutes (English and German)
      - Outlook sign-in failures, yesterday afternoon, 4 reports in 20 minutes
      - duplicate billing charges, 4 days ago, 3 reports spread over a day (not an outage)
      - Canvas outage, 20-35 minutes ago, 4 reports: the live banners are on when the demo starts
  * agent activity: older tickets resolved (a few past their SLA), some in progress, recent ones waiting.

Every ticket goes through sentinel_ui.backend.triage_ticket with received_at = its arrival time, so the
burst and root-cause windows judge the replayed history exactly as they would live.
"""
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from sentineldesk import data, pipeline, retrieve, rootcause  # noqa: E402
from sentineldesk.text import clean_text  # noqa: E402
from sentinel_ui import backend  # noqa: E402
from sentinel_ui.common import LIVE_PATH, SERVICES, T, add_ticket, normalize_result, update_ticket  # noqa: E402

rng = random.Random(7)
NOW = datetime.now().replace(second=0, microsecond=0)
AYUSH, KUNAL = "varma.ay@northeastern.edu", "gupta.kunal@northeastern.edu"
USERS = [AYUSH, KUNAL, "demo@northeastern.edu", "nima@northeastern.edu", "prof@northeastern.edu"]
WEIGHTS = [3, 2, 1, 1, 1]          # Ayush and Kunal file most of the everyday tickets
# Who reported which scripted ticket, so each demo account has a story (Ayush: an outage, a billing issue,
# a mailbox problem, a live Canvas report).
OWNERS = {"Fee payment not showing": AYUSH, "Locked out of Student Hub": KUNAL,
          "VPN down for remote staff": AYUSH, "Outlook keeps asking for password": AYUSH,
          "Charged twice for tuition plan": AYUSH, "Canvas down during exam": AYUSH,
          "VPN-Verbindung fällt aus": KUNAL, "Cannot sign in to email": KUNAL, "Canvas outage": KUNAL,
          "Rechnung doppelt abgebucht": KUNAL}
IMPACT, URGENCY = T["en"]["impact_opts"], T["en"]["urgency_opts"]
CATEGORIES = T["en"]["categories"]
SLA_H = {"high": 4, "medium": 8, "low": 24}


def at(days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


# (when, subject, body, service, impact 0-2, urgency 0-2)
PATTERNS = [
    # VPN outage, 2 days ago 09:10-09:35
    *[(at(days=2, hours=h, minutes=m), s, b, "VPN or campus network", 2, 2) for h, m, s, b in [
        (5, 0, "VPN down for remote staff", "Since this morning none of our remote staff can connect to the VPN. "
                                            "The client times out at authentication."),
        (4, 54, "VPN keeps disconnecting", "The VPN drops every few minutes and then fails to reconnect with an "
                                           "authentication timeout. Our whole team is affected."),
        (4, 47, "VPN-Verbindung fällt aus", "Seit heute früh kann sich niemand aus unserem Team per VPN verbinden, "
                                            "Zeitüberschreitung bei der Anmeldung."),
        (4, 41, "Cannot reach campus network over VPN", "VPN login times out for everyone in the lab, we cannot "
                                                         "reach any internal systems."),
        (4, 35, "Urgent: VPN outage", "VPN is down for the entire department, authentication timeout on every "
                                      "attempt. Please escalate immediately."),
    ]],
    # Outlook sign-in failures, yesterday 14:00-14:20
    *[(at(days=1, hours=h, minutes=m), s, b, "Email (Outlook)", i, u) for h, m, s, b, i, u in [
        (3, 0, "Outlook keeps asking for password", "Outlook keeps prompting for my password and rejects it, "
                                                    "I cannot open my mailbox since lunch.", 0, 2),
        (2, 54, "Cannot sign in to email", "Sign-in to Outlook fails with an authentication error, both desktop "
                                           "and web. Colleagues have the same issue.", 1, 2),
        (2, 47, "Outlook Anmeldung schlägt fehl", "Ich kann mich seit Mittag nicht mehr bei Outlook anmelden, das "
                                                  "Passwort wird immer wieder abgefragt.", 0, 1),
        (2, 40, "Email login loop", "Outlook web is stuck in a login loop after entering my password.", 0, 2),
    ]],
    # Duplicate billing charges, 4 days ago over the day (similar topic, not a burst)
    *[(at(days=4, hours=h), s, b, "Billing portal", 0, 1) for h, s, b in [
        (9, "Charged twice for tuition plan", "My card was charged twice for the March payment plan instalment. "
                                              "Please check and reverse the duplicate."),
        (6, "Rechnung doppelt abgebucht", "Uns wurde die Rechnung für März zweimal abgebucht. Bitte prüfen Sie das."),
        (2, "Duplicate charge on invoice", "The billing portal shows the same invoice paid twice from my account."),
    ]],
    # Tickets carrying personal data, so the PII guardrail has something to show
    (at(days=3, hours=5), "Fee payment not showing",
     "I yesterday paid my fees through account number: 72942442 from chase bank reference number: #42400, "
     "but the student account still shows the balance as unpaid.", "Billing portal", 0, 1),
    (at(days=2, hours=1), "Locked out of Student Hub",
     "I am locked out of Student Hub after the password reset. Please call me at +1 617 555 0142 or email "
     "kunal.g@example.com.", "Student Hub", 0, 2),
    (at(days=1, hours=7), "Printer queue stuck",
     "The printer at 10.12.4.21 in Snell Library keeps rejecting jobs. My Kundennummer: AB98231.", "Printing", 1, 1),
    # Canvas outage, live right now (20-35 minutes ago)
    *[(at(minutes=m), s, b, "Canvas", i, 2) for m, s, b, i in [
        (35, "Canvas not loading", "Canvas shows a 503 error for every course page, students cannot submit the "
                                   "assignment due tonight.", 1),
        (30, "Canvas down during exam", "Canvas is down in the middle of our online exam, nobody in the class can "
                                        "load the quiz. Please fix immediately.", 2),
        (26, "Canvas ist nicht erreichbar", "Canvas ist seit einer halben Stunde nicht erreichbar, alle Kurse zeigen "
                                            "einen Fehler.", 1),
        (21, "Canvas outage", "Canvas returns an error for the whole department, no course pages load.", 2),
    ]],
]


def everyday(n: int):
    """Holdout inputs only (ticket_id, subject, body): what a portal user might type."""
    inputs = data.load_test_inputs().sample(n=n, random_state=11)
    out = []
    for _, row in inputs.iterrows():
        when = NOW - timedelta(days=rng.uniform(0.1, 7), minutes=rng.randint(0, 59))
        out.append((when, clean_text(row["subject"]), clean_text(row["body"]), None,
                    rng.randint(0, 2), rng.randint(0, 2)))
    return out


def main() -> None:
    if LIVE_PATH.exists():
        shutil.copy(LIVE_PATH, LIVE_PATH.with_suffix(".json.bak"))
        LIVE_PATH.unlink()
    pipeline.BURST.clear()
    rootcause.GROUPER.reset()
    retrieve.clear_live()
    backend.warm_up()

    tickets = sorted(PATTERNS + everyday(46), key=lambda x: x[0])     # replay in arrival order
    print(f"[seed] replaying {len(tickets)} tickets from {tickets[0][0]:%a %H:%M} to {tickets[-1][0]:%a %H:%M}")
    for i, (when, subject, body, service, imp, urg) in enumerate(tickets, 1):
        res = backend.triage_ticket(subject or None, body, received_at=when.timestamp())
        res = normalize_result(res)
        is_incident = service is not None or res["type"]["label"] in ("Incident", "Problem")
        user = OWNERS.get(subject) or rng.choices(USERS, WEIGHTS)[0]
        if is_incident:
            extra = {"service": service or rng.choice(SERVICES), "impact": IMPACT[imp], "user_urgency": URGENCY[urg],
                     "impact_idx": imp, "urgency_idx": urg}
            rec = add_ticket("incident", user, subject, body, extra, res, opened=when)
        else:
            rec = add_ticket("request", user, subject, body, {"category": rng.choice(CATEGORIES)}, res, opened=when)

        age_h = (NOW - when).total_seconds() / 3600
        sla = SLA_H.get(rec["priority"], 24)
        if age_h > 30 or (age_h > 6 and rng.random() < .6):           # older work is mostly done
            took = sla * rng.uniform(.2, .9) if rng.random() < .85 else sla * rng.uniform(1.1, 2.0)
            done = min(when + timedelta(hours=took), NOW)
            update_ticket(rec["number"], state=rng.choice(["Resolved", "Resolved", "Closed"]),
                          resolved_at=done.strftime("%Y-%m-%d %H:%M"),
                          activity=[{"at": done.strftime("%Y-%m-%d %H:%M"), "text": "Resolved by IT service desk"}])
        elif age_h > 2 and rng.random() < .5:
            update_ticket(rec["number"], state="In progress")
        flag = "BURST " if res["burst"].get("active") else ""
        print(f"[seed] {i:2d} {rec['number']} {when:%a %H:%M} {flag}{res['status']:<17} "
              f"{rec['priority']:<6} {(subject or body)[:48]}")

    pipeline.BURST.clear()          # live traffic starts from a clean detector; the store keeps the history
    rootcause.GROUPER.reset()
    import json
    from collections import Counter
    per_user = Counter(t["user"] for t in json.loads(LIVE_PATH.read_text()))
    print(f"[seed] wrote {LIVE_PATH.relative_to(ROOT)}; tickets per user: {dict(per_user)}")


if __name__ == "__main__":
    main()
