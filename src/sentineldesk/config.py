"""Single source of truth for paths, model names and thresholds.

Announce changes to the team — every track imports this.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"

# --- models -----------------------------------------------------------------
# e5 requires the "query: " / "passage: " prefixes; skipping them costs real accuracy.
EMBED_MODEL = "intfloat/multilingual-e5-small"
EMBED_DIM = 384
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

LLM_MODEL = "claude-haiku-5-5"      # switch to claude-sonnet-5-5 if German quality disappoints
LLM_MAX_TOKENS = 1024

# --- triage classifier (Track A) ------------------------------------------------
# Frozen on the KB validation slice (docs/p1_workdone.md): word TF-IDF || e5 query embedding.
HEADS_PATH = ARTIFACTS / "heads.joblib"
KB_QUERY_EMB_PATH = ARTIFACTS / "kb_query_embeddings.npy"   # KB encoded with is_query=True, for the classifier
CLASSIFIER_C = 32.0
CLASSIFIER_EMB_WEIGHT = 1.0
HIGH_PRIORITY_TARGET_RECALL = 0.80   # P(high) threshold is the highest one reaching this on validation
HIGH_PRIORITY_THRESHOLD = 0.25       # value tuned by scripts/train_classifier.py (also stored in heads.joblib)
VAL_FRACTION = 0.10                  # first 10% of RandomState(RANDOM_SEED).permutation(len(kb)); gate tuning reuses it

# --- retrieval --------------------------------------------------------------
TOP_K = 5
DEDUP_SIMILARITY = 0.98             # drop a precedent this close to one already selected

# --- escalation gate --------------------------------------------------------
# EDA: the hard rule (high + Incident) alone fires on 17.2% of KB tickets, which is
# already the top of the 15-25% target band. Keep the soft thresholds tight or the
# overall escalation rate balloons past 40% and the copilot looks useless.
# Owned by P3. Chosen by scripts/gate_sweep.py on the 10% KB validation slice (never the holdout)
# with a rule fixed before the sweep: >=95% of high-priority Incidents escalated, >=25% auto-drafted,
# then max queue accuracy on auto-drafted tickets. Result (reports/gate_sweep.json): 26.5% auto-drafted,
# 95.3% of high Incidents escalated, auto-drafted queue accuracy 0.827 vs 0.609 overall.
MIN_CONFIDENCE = {
    "type": 0.35,
    "queue": 0.50,      # 10 classes at 21x imbalance; queue ECE 0.012, so this floor is meaningful
    "priority": 0.60,   # catches true high tickets the P(high)=0.25 rule labelled medium/low
}
# e5 query->passage cosine on the KB index sits in a narrow high band (p5 0.912, p25 0.931).
# These are the validation p25 of top-1 and mean top-3 similarity. They assume Track B's index is
# config.EMBED_MODEL with "passage: " KB vectors (artifacts/kb_embeddings.npy); re-run
# scripts/gate_sweep.py if retrieval changes model, prefixes or scoring.
MIN_TOP1_SIMILARITY = 0.9305
MIN_MEAN_TOP3_SIMILARITY = 0.9224

# Requests that imply a commitment we cannot make without precedent.
UNSUPPORTED_ACTION_PATTERNS = [
    r"\brefund\b", r"\berstattung\b", r"\brückerstattung\b",
    r"\bcancel (my )?(contract|subscription)\b", r"\bkündig",
    r"\bsla\b", r"\bcompensation\b", r"\bentschädigung\b",
    r"\bchargeback\b", r"\blegal\b", r"\brechtlich\b",
    r"\bgdpr\b", r"\bdsgvo\b", r"\bdelete my (data|account)\b",
    r"\bwire transfer\b", r"\büberweisung\b",
]

# --- safety gate (P3) ------------------------------------------------------
# Risk regexes live in gate.RISK_PATTERNS (owned by P3, tested by tests/test_adversarial.py).
MIN_LETTERS = 3                      # fewer letters than this (emoji only, bare URL) -> human

# Burst / major-incident detector (burst.py). A ticket is part of a burst when at least
# BURST_MIN_COUNT tickets (itself included) within BURST_WINDOW_S have pairwise cosine
# >= BURST_SIM to it. e5 query-vs-query cosines sit in a narrow high band, so this is high.
# Tuned by scripts/attack_table.py: the German VPN ticket scores 0.884 against the English
# ones and the invoice ticket 0.795, so any value in (0.795, 0.88] works; 0.86 keeps margin
# on both sides (0.90 missed the cross-lingual ticket).
BURST_SIM = 0.86
BURST_MIN_COUNT = 3
BURST_WINDOW_S = 30 * 60

# Legacy list, kept for anything that still imports it; the gate uses gate.RISK_PATTERNS.
PROMPT_INJECTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above) instructions",
    r"disregard (all |your |the )?(previous|prior|above)",
    r"you are now\b", r"system prompt", r"reveal your (prompt|instructions)",
]

# --- data -------------------------------------------------------------------
RANDOM_SEED = 42
TRAIN_FRACTION = 0.8
TARGETS = ["type", "queue", "priority", "language"]
