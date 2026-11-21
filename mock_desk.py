"""
mock_desk.py — stand-in for the real SentinelDesk pipeline.

The UI (app.py) only depends on the dict returned by `triage_ticket()`.
When the real pipeline is ready, make it return the same shape (or adapt it
in app.py -> normalize_result) and nothing else in the UI has to change.

Output contract
---------------
{
  "language": "en" | "de",
  "type":     {"label": str, "confidence": float},
  "queue":    {"label": str, "confidence": float},
  "priority": {"label": "high"|"medium"|"low", "confidence": float},
  "escalation": {"escalate": bool, "reasons": [str, ...]},
  "retrieved": [
      {"ticket_id": str, "similarity": float, "language": str,
       "subject": str, "answer_snippet": str}, ...
  ],
  "draft": str | None,          # None when escalated with no safe draft
  "cited_ids": [str, ...],
  "pii_found": [str, ...],      # kinds of PII masked, e.g. ["email", "phone"]
  "latency_ms": {"triage": float, "retrieval": float,
                 "generation": float, "total": float},
}
"""
from __future__ import annotations

import random
import re
import time

GERMAN_HINTS = re.compile(
    r"\b(und|nicht|ich|wir|bitte|sehr|geehrte|danke|ist|mit|für|der|die|das)\b", re.I
)
OUTAGE = re.compile(r"outage|down|not working|unreachable|ausfall|nicht erreichbar|vpn", re.I)
URGENT = re.compile(r"urgent|asap|immediately|critical|dringend|sofort", re.I)
BILLING = re.compile(r"invoice|billing|charge|refund|payment|rechnung|erstattung|zahlung", re.I)
LOGIN = re.compile(r"password|login|log in|locked|passwort|anmeld", re.I)
SALES = re.compile(r"pricing|quote|demo|license|plan|angebot|lizenz", re.I)
UNSUPPORTED = re.compile(
    r"guarantee|compensation|legal|lawsuit|sue|refund .*(double|100%)|garantie|entschädigung", re.I
)

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

KB = {
    "outage": [
        ("TKT-03774", "VPN gateway unreachable for remote clinics",
         "We identified a failed certificate on the VPN gateway, rotated it, and restored access. Please reconnect and confirm."),
        ("TKT-11902", "Network outage affecting EMR integration",
         "Our engineers rerouted traffic through the secondary link. Services were restored within 40 minutes."),
        ("TKT-07215", "Ausfall der Remote-Verbindung",
         "Wir haben den betroffenen Knoten neu gestartet und die Verbindung wiederhergestellt."),
    ],
    "billing": [
        ("TKT-05521", "Duplicate charge on invoice",
         "We confirmed the duplicate charge and issued a correction to your account. It will appear on your next statement."),
        ("TKT-09034", "Rechnung unklar",
         "Wir haben die Positionen Ihrer Rechnung geprüft und eine detaillierte Aufstellung beigefügt."),
        ("TKT-14410", "Question about billing cycle",
         "Your billing cycle starts on the date of activation. You can change it under Account settings."),
    ],
    "login": [
        ("TKT-02210", "Locked out after password reset",
         "We unlocked your account and sent a new reset link. Please use it within 24 hours."),
        ("TKT-08876", "Passwort zurücksetzen funktioniert nicht",
         "Wir haben den Link erneut gesendet. Bitte prüfen Sie auch Ihren Spam-Ordner."),
        ("TKT-12007", "SSO login loop",
         "Clearing cached credentials and re-linking the SSO account resolved the issue."),
    ],
    "sales": [
        ("TKT-04412", "Enterprise plan details",
         "Our sales team shared the enterprise plan overview and scheduled a call to discuss your needs."),
        ("TKT-10543", "Integration with Blackboard Learn",
         "We provided integration documentation and offered a technical walkthrough."),
        ("TKT-06690", "Lizenzanfrage",
         "Wir haben Ihnen die Lizenzoptionen zugesendet und einen Termin vorgeschlagen."),
    ],
    "general": [
        ("TKT-01541", "SaaS features and scalability",
         "We shared an overview of features and scalability options and offered a product demo."),
        ("TKT-13320", "Feature request for reporting",
         "Thanks for the suggestion. We logged it with the product team for review."),
        ("TKT-15801", "Allgemeine Frage zum Produkt",
         "Vielen Dank für Ihre Anfrage. Wir haben Ihnen die gewünschten Informationen zugesendet."),
    ],
}


def _detect_language(text: str) -> str:
    return "de" if len(GERMAN_HINTS.findall(text)) >= 2 else "en"


def _mask_pii(text: str) -> tuple[str, list[str]]:
    found = []
    for kind, pat in PII_PATTERNS.items():
        if pat.search(text):
            found.append(kind)
            text = pat.sub(f"[{kind.upper()}]", text)
    return text, found


def triage_ticket(subject: str | None, body: str) -> dict:
    t0 = time.perf_counter()
    subject = (subject or "").strip()
    body = (body or "").strip()
    text = f"{subject} {body}".strip()
    masked, pii_found = _mask_pii(text)
    lang = _detect_language(masked)

    # --- triage (keyword heuristics stand in for the classifier) ---
    if OUTAGE.search(masked):
        topic, ttype, queue = "outage", "Incident", "Technical Support"
    elif BILLING.search(masked):
        topic, ttype, queue = "billing", "Problem", "Billing and Payments"
    elif LOGIN.search(masked):
        topic, ttype, queue = "login", "Request", "IT Support"
    elif SALES.search(masked):
        topic, ttype, queue = "sales", "Request", "Sales and Pre-Sales"
    else:
        topic, ttype, queue = "general", "Request", "Customer Service"

    if OUTAGE.search(masked) or URGENT.search(masked):
        priority = "high"
    elif topic in ("billing", "login"):
        priority = "medium"
    else:
        priority = "low"

    conf = 0.55 if topic == "general" else round(random.uniform(0.78, 0.94), 2)
    t1 = time.perf_counter()

    # --- retrieval ---
    sim_base = 0.48 if topic == "general" else 0.82
    retrieved = [
        {"ticket_id": tid, "similarity": round(sim_base - i * 0.05, 2),
         "language": "de" if GERMAN_HINTS.search(snip) else "en",
         "subject": subj, "answer_snippet": snip}
        for i, (tid, subj, snip) in enumerate(KB[topic])
    ]
    t2 = time.perf_counter()

    # --- escalation gate ---
    reasons = []
    if priority == "high" and ttype == "Incident":
        reasons.append("High-priority incident")
    if conf < 0.6:
        reasons.append(f"Low classifier confidence ({conf:.2f})")
    if retrieved[0]["similarity"] < 0.55:
        reasons.append("No close historical precedent")
    if UNSUPPORTED.search(masked):
        reasons.append("Asks for a guarantee or policy not found in past resolutions")
    escalate = bool(reasons)

    # --- grounded draft ---
    cited = [r["ticket_id"] for r in retrieved[:2]]
    if lang == "de":
        draft = (f"Guten Tag,\n\nvielen Dank für Ihre Nachricht. In vergleichbaren Fällen "
                 f"({', '.join(cited)}) haben wir das Problem wie folgt gelöst: "
                 f"{retrieved[0]['answer_snippet']}\n\nMit freundlichen Grüßen\nIhr Support-Team")
    else:
        draft = (f"Hello,\n\nthank you for reaching out. In similar past cases "
                 f"({', '.join(cited)}), this was resolved as follows: "
                 f"{retrieved[0]['answer_snippet']}\n\nBest regards,\nSupport Team")
    if UNSUPPORTED.search(masked):
        draft = None  # refuse to invent policy
        cited = []
    time.sleep(0.3)  # pretend generation time
    t3 = time.perf_counter()

    ms = lambda a, b: round((b - a) * 1000, 1)
    return {
        "language": lang,
        "type": {"label": ttype, "confidence": conf},
        "queue": {"label": queue, "confidence": round(conf - 0.05, 2)},
        "priority": {"label": priority, "confidence": round(conf - 0.08, 2)},
        "escalation": {"escalate": escalate, "reasons": reasons},
        "retrieved": retrieved,
        "draft": draft,
        "cited_ids": cited,
        "pii_found": pii_found,
        "latency_ms": {"triage": ms(t0, t1), "retrieval": ms(t1, t2),
                       "generation": ms(t2, t3), "total": ms(t0, t3)},
    }
