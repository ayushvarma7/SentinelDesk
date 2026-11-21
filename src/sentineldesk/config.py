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

LLM_MODEL = "gemini-2.5-flash"      # team plan is Gemini (GDG event); P2.1 checks it against the live list
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

# --- retrieval (Track B / P2) -----------------------------------------------
KB_EMB_PATH = ARTIFACTS / "kb_embeddings.npy"        # KB encoded with is_query=False, for retrieval
KB_META_PATH = ARTIFACTS / "kb_meta.parquet"         # same row order as KB_EMB_PATH
TOP_K = 5
DEDUP_SIMILARITY = 0.98             # drop a precedent this close to one already selected

# --- escalation gate --------------------------------------------------------
# EDA: the hard rule (high + Incident) alone fires on 17.2% of KB tickets, which is
# already the top of the 15-25% target band. Keep the soft thresholds tight or the
# overall escalation rate balloons past 40% and the copilot looks useless.
# Tune these in scripts/evaluate.py, do not guess them.
MIN_CONFIDENCE = {
    "type": 0.50,
    "queue": 0.45,      # 10 classes at 21x imbalance, so expect lower confidence here
    "priority": 0.55,   # EDA says priority is weakly predictable; this may need lowering
}
MIN_TOP1_SIMILARITY = 0.72
MIN_MEAN_TOP3_SIMILARITY = 0.65

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
