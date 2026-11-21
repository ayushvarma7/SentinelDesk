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

LLM_MODEL = "gemini-3.5-flash-lite"   # P2.1: 2.5-* are retired (404); 3.5-flash 504s on capacity
LLM_MAX_TOKENS = 1024
LLM_TIMEOUT_MS = 20000   # past this, fall back to extractive rather than stall the UI

# --- triage classifier (Track A) ------------------------------------------------
# Frozen on the KB validation slice (docs/p1_workdone.md): word TF-IDF || e5 query embedding.
HEADS_PATH = ARTIFACTS / "heads.joblib"
KB_QUERY_EMB_PATH = ARTIFACTS / "kb_query_embeddings.npy"   # KB encoded with is_query=True, for the classifier
CLASSIFIER_C = 32.0
CLASSIFIER_EMB_WEIGHT = 1.0
HIGH_PRIORITY_TARGET_RECALL = 0.80   # P(high) threshold is the highest one reaching this on validation
HIGH_PRIORITY_THRESHOLD = 0.25       # value tuned by scripts/train_classifier.py (also stored in heads.joblib)
VAL_FRACTION = 0.10                  # first 10% of RandomState(RANDOM_SEED).permutation(len(kb)); gate tuning reuses it

# --- root cause (Track A, ITIL: many Incidents -> one Problem -> fixed by Changes) ----
# Incident vs Problem is a relationship, not a wording difference (712 of 760 type errors are
# Incident<->Problem), so the critical-escalation rule treats both as "service is broken".
# Validation: high-priority Incident recall 0.803 (Incident only) -> 0.882 (Incident or Problem).
CRITICAL_TYPES = ("Incident", "Problem")
# Similarity (e5 query vectors) above which two issues are treated as the same root cause.
# Calibrated on KB issue pairs from different queues with no shared tag: p90=0.891, p99=0.917.
ROOT_CAUSE_GROUP_SIM = 0.89
ROOT_CAUSE_MIN_GROUP = 3             # this many similar live issues -> suggest raising a Problem
ROOT_CAUSE_WINDOW_MIN = 30           # live issues older than this drop out of grouping
ROOT_CAUSE_MIN_WORDS = 3             # too-short tickets ("help", emoji) are never grouped
# Known KB Problem/Change links search the retrieval (passage) index with the query vector, a
# different scale from query-vs-query. Unrelated issue->Problem/Change pairs: p90=0.849, p99=0.883;
# KB issues' best related Problem: p10=0.899, median 0.923. 0.89 sits just above unrelated p99.
ROOT_CAUSE_LINK_MIN_SIM = 0.89

# --- retrieval (Track B / P2) -----------------------------------------------
KB_EMB_PATH = ARTIFACTS / "kb_embeddings.npy"        # KB encoded with is_query=False, for retrieval
KB_META_PATH = ARTIFACTS / "kb_meta.parquet"         # same row order as KB_EMB_PATH

# Live store: precedents added during a session (see retrieve.add_precedent).
# Separate from the frozen index on purpose — evaluation passes include_live=False.
LIVE_DIR = ARTIFACTS / "live"
LIVE_EMB_PATH = LIVE_DIR / "live_embeddings.npy"
LIVE_META_PATH = LIVE_DIR / "live_meta.parquet"
TOP_K = 5
DEDUP_SIMILARITY = 0.98             # drop a precedent this close to one already selected

# Places in the top-k reserved for a precedent in the OTHER language. e5 does
# not bridge languages on its own: by DETECTED language only 1-3% of hits cross
# over. 0 disables; evaluation passes 0 so metrics measure unaided retrieval.
CROSS_LINGUAL_SLOTS = 1

# --- escalation gate --------------------------------------------------------
# EDA: the hard rule (high + Incident) alone fires on 17.2% of KB tickets, which is
# already the top of the 15-25% target band. Keep the soft thresholds tight or the
# overall escalation rate balloons past 40% and the copilot looks useless.
# Tune these in scripts/evaluate.py, do not guess them.
MIN_CONFIDENCE = {
    "type": 0.55,
    "queue": 0.30,       # 10 classes at 21x imbalance; confidences genuinely sit 0.3-0.5
    "priority": 0.50,    # recall-tuned P(high)=0.25 means "high" can carry low confidence
}
# Calibrated on HAND-TYPED tickets, not holdout percentiles. The holdout p10 is
# 0.9186, but the dataset is synthetic and its own tickets sit unusually close
# to the KB: 8/8 hand-written tickets scored below that, so a holdout-derived
# threshold escalates 100% of judge input. Measured bands with hand-typed text:
#   in-domain 0.869-0.906 | off-domain 0.855-0.864 | gibberish 0.833
# The margin is thin (~0.005), so treat similarity as a WEAK signal. P3 to sweep.
MIN_TOP1_SIMILARITY = 0.8650
MIN_MEAN_TOP3_SIMILARITY = 0.8450   # hand-typed mean top-3 sits ~0.86-0.87; P3 to sweep

# Requests that imply a commitment we cannot make without precedent.
UNSUPPORTED_ACTION_PATTERNS = [
    r"\brefund\b", r"\berstattung\b", r"\brückerstattung\b",
    r"\bcancel (my )?(contract|subscription)\b", r"\bkündig",
    r"\bsla\b", r"\bcompensation\b", r"\bentschädigung\b",
    r"\bchargeback\b", r"\blegal\b", r"\brechtlich\b",
    r"\bgdpr\b", r"\bdsgvo\b", r"\bdelete my (data|account)\b",
    r"\bwire transfer\b", r"\büberweisung\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above) instructions",
    r"disregard (all |your |the )?(previous|prior|above)",
    r"you are now\b", r"system prompt", r"reveal your (prompt|instructions)",
]

# --- data -------------------------------------------------------------------
RANDOM_SEED = 42
TRAIN_FRACTION = 0.8
TARGETS = ["type", "queue", "priority", "language"]
