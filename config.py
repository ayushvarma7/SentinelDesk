"""Shared constants. FROZEN after setup — announce any change in the group chat.

PROVISIONAL: written by P2 so the retrieval work could start before the base
code landed. If Kunal's sandbox version differs, his wins — these names and
values were reconstructed from what the plan's own code imports.
"""
import os

# --- data -------------------------------------------------------------------
DATA_REPO = "Tobi-Bueck/customer-support-tickets"
DATA_FILE = "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
SEED = 42
LANGS = ("en", "de")

ARTIFACT_DIR = os.getenv("SD_ARTIFACT_DIR", "artifacts")
REPORT_DIR = os.getenv("SD_REPORT_DIR", "reports")

# The three predicted heads. Language is detected, not classified.
TARGETS = ("type", "queue", "priority")

# --- embeddings -------------------------------------------------------------
EMB_MODEL = os.getenv("SD_EMB_MODEL", "intfloat/multilingual-e5-small")
EMB_DIM = 384
# e5 wants a prefix. Ticket-to-ticket matching is symmetric, so both sides get
# the same one — mixing "query: " and "passage: " here would skew similarity.
EMB_PREFIX = "query: "
EMB_WEIGHT = float(os.getenv("SD_EMB_WEIGHT", "1.0"))

# --- generation -------------------------------------------------------------
# P2.1 verifies this against the live model list; update if it 404s.
LLM_MODEL = os.getenv("SD_LLM_MODEL", "gemini-2.5-flash")
LLM_MAX_OUTPUT_TOKENS = 1024

# --- gate (P3 owns these values) --------------------------------------------
DEFAULT_THRESHOLDS = {
    "min_sim": 0.78,          # P2.3 supplies the real number (top-1 p10)
    "min_conf_type": 0.50,
    "min_conf_queue": 0.35,   # 10 classes at 21x imbalance; loosest by design
    "min_conf_priority": 0.45,
    "burst_sim": 0.80,
    "burst_window_s": 600,
    "burst_min_tickets": 3,
}
