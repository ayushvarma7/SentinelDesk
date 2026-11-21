"""
OWNER: P2. Retrieval sanity on 500 holdout tickets (text only; holdout answers dropped on load).
Prints top-1 similarity percentiles (P3 needs these for min_sim), label agreement, and cross-lingual share.
Run:  python retrieval_check.py
"""
import json, os
import numpy as np
import pandas as pd
from config import ARTIFACT_DIR, REPORT_DIR
from data import load_raw, official_split, ticket_text
from embed import embed
from model import Retriever

os.makedirs(REPORT_DIR, exist_ok=True)
_, test = official_split(load_raw())
test = test.drop(columns=["answer"]).sample(n=500, random_state=0).reset_index(drop=True)
kb = pd.read_parquet(f"{ARTIFACT_DIR}/kb.parquet")
ret = Retriever(np.load(f"{ARTIFACT_DIR}/kb_emb.npy"))
Q = embed([ticket_text(s, b) for s, b in zip(test["subject"], test["body"])], show=True)
D, I = ret.search(Q, 5)
top1 = kb.iloc[I[:, 0]].reset_index(drop=True)
hit_lang = kb["language"].to_numpy(dtype=object)[I]
res = {
    "top1_sim_percentiles": {f"p{q}": round(float(np.percentile(D[:, 0], q)), 4) for q in (5, 10, 25, 50, 75, 95)},
    "top1_same_queue": round(float((top1["queue"] == test["queue"]).mean()), 4),
    "top1_same_type": round(float((top1["type"] == test["type"]).mean()), 4),
    "top5_other_language_share": round(float((hit_lang != test["language"].to_numpy(dtype=object)[:, None]).mean()), 4),
}
json.dump(res, open(f"{REPORT_DIR}/retrieval_check.json", "w"), indent=2)
print(json.dumps(res, indent=2))
print("\nSuggested min_sim for P3 (p10):", res["top1_sim_percentiles"]["p10"])
