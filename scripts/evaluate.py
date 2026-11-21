"""Holdout evaluation. The ONLY legitimate caller of data.load_test_labels().

    PYTHONPATH=src python scripts/evaluate.py

Run once per frozen model, never to pick settings (settings are chosen on the KB validation slice
by scripts/train_classifier.py).

Current sections:
  * triage heads: macro-F1, accuracy, ECE per head; high-priority Incident recall
TODO (needs Track B retrieve + Track C generate): gate escalation recall, retrieval stats, latency p50/p95.

Writes reports/triage_metrics.json.
"""
import json

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score

from sentineldesk import classify, config
from sentineldesk.data import build_text, load_test_inputs, load_test_labels
from sentineldesk.embed import encode

REPORTS = config.ROOT / "reports"


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def main() -> None:
    inputs = load_test_inputs()                       # ticket_id, subject, body only
    texts = [build_text(s, b) for s, b in zip(inputs["subject"], inputs["body"])]
    X = encode(texts, is_query=True, show_progress=True)

    bundle = classify.load()
    proba = classify.predict_proba(bundle, X, texts)
    pred = {}
    for h, (classes, P) in proba.items():
        idx = classify.decide(classes, P, h, bundle["high_threshold"])
        pred[h] = (classes[idx], P[np.arange(len(idx)), idx])

    labels = load_test_labels().set_index("ticket_id").loc[inputs["ticket_id"]]   # align by id
    res = {"n_holdout": len(inputs), "high_threshold": bundle["high_threshold"], "C": bundle["C"]}
    for h, (lab, conf) in pred.items():
        y = labels[h].to_numpy()
        res[h] = {"macro_f1": round(f1_score(y, lab, average="macro"), 4),
                  "accuracy": round(accuracy_score(y, lab), 4),
                  "ece": round(ece(conf, (y == lab).astype(float)), 4)}
        print(f"\n=== {h} ===\n" + classification_report(y, lab, digits=3, zero_division=0))

    true_hi = (labels["priority"].to_numpy() == "high") & (labels["type"].to_numpy() == "Incident")
    pred_hi = pred["priority"][0] == "high"
    pred_inc = pred["type"][0] == "Incident"
    pred_crit = np.isin(pred["type"][0], config.CRITICAL_TYPES)        # the gate's hard rule
    res["high_priority_incident"] = {
        "support": int(true_hi.sum()),
        "recall_predicted_high": round(float(pred_hi[true_hi].mean()), 4),
        "recall_predicted_high_and_incident": round(float((pred_hi & pred_inc)[true_hi].mean()), 4),
        "recall_gate_hard_rule": round(float((pred_hi & pred_crit)[true_hi].mean()), 4),
        "gate_hard_rule_types": list(config.CRITICAL_TYPES),
        "share_of_tickets_hard_escalated": round(float((pred_hi & pred_crit).mean()), 4)}

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "triage_metrics.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
