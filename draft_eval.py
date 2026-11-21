"""
OWNER: P2. Runs 20 holdout tickets (10 en + 10 de) end to end and scores the drafts.
Holdout answers are dropped on load; only subject + body go in.
Run:  python draft_eval.py          (SD_DRAFT_N=5 for a quicker pass)
"""
import os, re, json
import pandas as pd
from config import REPORT_DIR
from data import load_raw, official_split
from pipeline import SentinelDesk, detect_language
from gate import unsupported_figures

N = int(os.getenv("SD_DRAFT_N", "10"))
os.makedirs(REPORT_DIR, exist_ok=True)
_, test = official_split(load_raw())
test = test.drop(columns=["answer"])
sample = pd.concat([test[test["language"] == lang].sample(n=N, random_state=7) for lang in ("en", "de")])
desk = SentinelDesk()
rows = []
for _, t in sample.iterrows():
    r = desk.triage(t["subject"], t["body"])
    d = r["draft"]
    reply = d.get("reply") or ""
    ids = {h["ticket_id"] for h in r["retrieved"]}
    cited = set(re.findall(r"TKT-\d{5}", reply))
    evidence = " ".join(h["answer"] for h in r["retrieved"])
    rows.append({"lang": t["language"], "engine": d.get("engine"), "status": r["status"],
                 "has_citation": bool(cited), "fake_citation": bool(cited - ids),
                 "invented_figures": bool(unsupported_figures(reply, evidence)),
                 "right_language": bool(reply) and detect_language(reply) == t["language"],
                 "placeholder_leak": bool(re.search(r"<[A-Za-z_ -]{2,20}>", reply)),
                 "words": len(reply.split()), "latency_ms": r["latency_ms"]["total"], "reply": reply[:300]})
    desk.recent.clear()      # eval tickets must not trigger the burst detector
df = pd.DataFrame(rows)
df.to_csv(f"{REPORT_DIR}/draft_eval.csv", index=False)
summary = {c: round(float(df[c].mean()), 3)
           for c in ("has_citation", "fake_citation", "invented_figures", "right_language", "placeholder_leak")}
summary.update({"median_words": float(df["words"].median()), "p50_latency_ms": float(df["latency_ms"].median()),
                "n": len(df), "engine": str(df["engine"].mode().iloc[0])})
json.dump(summary, open(f"{REPORT_DIR}/draft_eval.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
