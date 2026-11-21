"""OWNER: P3. Picks the gate thresholds on the 10% KB validation slice P1 held out (never the holdout).

    PYTHONPATH=src python scripts/gate_sweep.py

* Validation slice = first 10% of RandomState(RANDOM_SEED).permutation(len(kb)), the exact rows
  scripts/train_classifier.py kept out of heads.joblib, so classifier confidences are honest.
* Retrieval is query ("query: ", the vector the pipeline computes) against the KB passage index
  ("passage: ", artifacts/kb_embeddings.npy, the scaffold's Track B index). Each ticket's own KB row is
  excluded, so similarity is honest too. If kb_embeddings.npy is missing it is built here and cached
  with artifacts/kb_ids.npy (same file and convention retrieve.build_index() is meant to write).
* Every combination goes through the real gate.evaluate() with the top-3 precedents and their answers.

Selection rule, fixed BEFORE the sweep ran:
  1. at least 95% of true high-priority Incidents escalated,
  2. at least 25% of tickets auto-drafted,
  3. then the highest queue accuracy among auto-drafted tickets (ties: larger auto share).

Writes reports/gate_sweep.csv and reports/gate_sweep.json (the CHOSEN values go into config.py).
"""
import itertools
import json
import time

import numpy as np
import pandas as pd

from sentineldesk import classify, config, gate
from sentineldesk.data import build_text, load_kb
from sentineldesk.schema import Precedent, Prediction

REPORTS = config.ROOT / "reports"
PASSAGE_EMB = config.ARTIFACTS / "kb_embeddings.npy"
PASSAGE_IDS = config.ARTIFACTS / "kb_ids.npy"

# The plan's 3x3x3x3 grid (type .35-.55, queue .20-.40, priority .30-.50, p5-p25) topped out at
# 93.6% high-Incident escalation with this classifier (its confidences are higher than the TF-IDF
# baseline's), so no point met rule 1. The grid was widened upward; the rule did not change.
CONF_GRID = {"type": (0.35, 0.45, 0.55, 0.65, 0.75), "queue": (0.20, 0.30, 0.40, 0.50),
             "priority": (0.30, 0.40, 0.50, 0.60, 0.70)}
SIM_PCTS = (5, 10, 25, 40)


def load_or_encode(path, ids_path, kb, texts, is_query):
    ids = kb["ticket_id"].to_numpy(dtype=str)
    if path.exists() and ids_path.exists() and np.array_equal(np.load(ids_path), ids):
        print(f"[sweep] reusing {path.name}")
        return np.load(path)
    from sentineldesk.embed import encode
    print(f"[sweep] encoding {len(texts):,} KB tickets (is_query={is_query}) -> {path.name}")
    E = encode(list(texts), is_query=is_query, show_progress=True)
    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    np.save(path, E)
    np.save(ids_path, ids)
    return E


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    kb = load_kb()
    texts = np.array([build_text(s, b) for s, b in zip(kb["subject"], kb["body"])], dtype=object)
    Eq = load_or_encode(config.KB_QUERY_EMB_PATH, config.KB_QUERY_EMB_PATH.with_name("kb_query_ids.npy"),
                        kb, texts, is_query=True)
    Ep = load_or_encode(PASSAGE_EMB, PASSAGE_IDS, kb, texts, is_query=False)

    perm = np.random.RandomState(config.RANDOM_SEED).permutation(len(kb))
    val = perm[: max(1, int(config.VAL_FRACTION * len(kb)))]        # same slice as train_classifier.py
    v = kb.iloc[val].reset_index(drop=True)
    vt = list(texts[val])
    print(f"[sweep] validation slice: {len(val):,} KB tickets (held out of heads.joblib)")

    bundle = classify.load()
    preds = {}
    for h, (classes, P) in classify.predict_proba(bundle, Eq[val], vt).items():
        idx = classify.decide(classes, P, h, bundle["high_threshold"])
        preds[h] = (classes[idx], P[np.arange(len(idx)), idx])

    # query -> passage retrieval, excluding the ticket's own row
    with np.errstate(all="ignore"):     # macOS Accelerate emits spurious matmul warnings
        S = Eq[val] @ Ep.T
    S[np.arange(len(val)), val] = -np.inf
    top = np.argsort(-S, axis=1)[:, : config.TOP_K]
    top_s = np.take_along_axis(S, top, axis=1)
    top1, mean3 = top_s[:, 0], top_s[:, :3].mean(1)

    precs = [[Precedent(str(kb.at[j, "ticket_id"]), float(top_s[i, r]), str(kb.at[j, "subject"] or ""),
                        "", str(kb.at[j, "answer"]), str(kb.at[j, "language"]), str(kb.at[j, "queue"]))
              for r, j in enumerate(top[i, :3])] for i in range(len(val))]
    heads = [{h: Prediction(str(preds[h][0][i]), float(preds[h][1][i])) for h in ("type", "queue", "priority")}
             for i in range(len(val))]

    pct1 = {q: float(np.percentile(top1, q)) for q in SIM_PCTS}
    pct3 = {q: float(np.percentile(mean3, q)) for q in SIM_PCTS}
    print("[sweep] top-1 similarity percentiles:", {f"p{q}": round(x, 4) for q, x in pct1.items()})
    print("[sweep] mean top-3 similarity percentiles:", {f"p{q}": round(x, 4) for q, x in pct3.items()})

    true_hi = ((v["priority"] == "high") & (v["type"] == "Incident")).to_numpy()
    queue_ok = preds["queue"][0] == v["queue"].to_numpy(dtype=object)

    rows = []
    t0 = time.time()
    for ct, cq, cp, q in itertools.product(*CONF_GRID.values(), SIM_PCTS):
        th = {"min_confidence": {"type": ct, "queue": cq, "priority": cp},
              "min_top1_similarity": pct1[q], "min_mean_top3_similarity": pct3[q]}
        esc = np.array([gate.evaluate(vt[i], heads[i]["type"], heads[i]["queue"], heads[i]["priority"],
                                      precs[i], th)[0] for i in range(len(val))])
        auto = ~esc
        rows.append({"type": ct, "queue": cq, "priority": cp, "min_sim_pct": q,
                     "min_top1_similarity": round(pct1[q], 4), "min_mean_top3_similarity": round(pct3[q], 4),
                     "auto_share": round(float(auto.mean()), 3),
                     "high_incident_escalated": round(float(esc[true_hi].mean()), 3),
                     "auto_queue_accuracy": round(float(queue_ok[auto].mean()), 3) if auto.any() else 0.0})
    print(f"[sweep] {len(rows)} combinations in {time.time() - t0:.0f}s")

    df = pd.DataFrame(rows)
    ok = df[(df.high_incident_escalated >= 0.95) & (df.auto_share >= 0.25)]
    if len(ok):
        best = ok.sort_values(["auto_queue_accuracy", "auto_share"], ascending=False).iloc[0]
    else:   # nothing meets the rule: safety first, take the most high-Incident escalation
        print("[sweep] WARNING: no combination meets the rule; picking max high_incident_escalated")
        best = df.sort_values(["high_incident_escalated", "auto_share"], ascending=False).iloc[0]
    df.sort_values("auto_queue_accuracy", ascending=False).to_csv(REPORTS / "gate_sweep.csv", index=False)

    summary = {
        "n_val": int(len(val)),
        "rule": "high_incident_escalated >= 0.95 and auto_share >= 0.25, then max auto_queue_accuracy",
        "n_meeting_rule": int(len(ok)),
        "top1_sim_percentiles": {f"p{q}": round(x, 4) for q, x in pct1.items()},
        "mean_top3_sim_percentiles": {f"p{q}": round(x, 4) for q, x in pct3.items()},
        "overall_queue_accuracy": round(float(queue_ok.mean()), 3),
        "true_high_incidents": int(true_hi.sum()),
        "chosen": {k: (v_.item() if hasattr(v_, "item") else v_) for k, v_ in best.to_dict().items()},
    }
    (REPORTS / "gate_sweep.json").write_text(json.dumps(summary, indent=2))
    print(df.sort_values("auto_queue_accuracy", ascending=False).head(10).to_string(index=False))
    print("\nCHOSEN:", json.dumps(summary["chosen"], indent=2))
    print(f"overall queue accuracy {summary['overall_queue_accuracy']} vs auto-drafted "
          f"{summary['chosen']['auto_queue_accuracy']}")


if __name__ == "__main__":
    main()
