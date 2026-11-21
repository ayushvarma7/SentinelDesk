#!/usr/bin/env bash
# SentinelDesk: one entry point from a fresh clone to a running console.
#
#   ./run.sh setup    venv + dependencies + dataset + split + classifier + retrieval index (skips what exists)
#   ./run.sh test     unit, contract and adversarial tests
#   ./run.sh eval     holdout metrics, attack table, retrieval check, draft quality
#   ./run.sh seed     fill the console with a realistic week of tickets (outages included)
#   ./run.sh app      start the console on http://localhost:8501
#   ./run.sh demo     seed, then start the console (run this right before a demo)
#   ./run.sh all      setup, test, seed, app
#
# Put GEMINI_API_KEY in .env (cp .env.example .env) for LLM drafts; without it drafts use the
# extractive fallback, which quotes the closest precedent. FORCE=1 ./run.sh setup rebuilds everything.
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv
PY="$VENV/bin/python"
DATA_FILE=aa_dataset-tickets-multi-lang-5-2-50-version.csv
DATA_URL="https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/$DATA_FILE"
export PYTHONPATH=src

say()  { printf '\n\033[1;31m▶\033[0m \033[1m%s\033[0m\n' "$*"; }
need() { [ "${FORCE:-0}" = 1 ] || [ ! -e "$1" ]; }

load_env() {
  if [ -f .env ]; then set -a; . ./.env; set +a; fi
  if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "  (no GEMINI_API_KEY: drafts use the extractive fallback)"
  fi
}

find_python() {
  for c in python3.12 python3; do
    if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
      command -v "$c"; return
    fi
  done
  echo "Python 3.12 is required (torch has no wheels for newer versions)." >&2
  echo "Install it, e.g.  brew install python@3.12   or   pyenv install 3.12.8" >&2
  exit 1
}

setup() {
  if [ ! -x "$PY" ]; then
    say "Creating .venv"
    "$(find_python)" -m venv "$VENV"
  fi
  say "Installing dependencies"
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r requirements.txt pytest

  if need "data/raw/$DATA_FILE"; then
    say "Downloading the dataset (Tobi-Bueck/customer-support-tickets, ~26 MB)"
    mkdir -p data/raw
    curl -fL --progress-bar -o "data/raw/$DATA_FILE" "$DATA_URL"
  fi
  if need data/processed/kb_train.parquet; then
    say "Official seed-42 80/20 split -> kb_train / test_inputs / test_labels"
    "$PY" scripts/prepare_data.py
  fi
  if need artifacts/heads.joblib; then
    say "Training the triage classifier (~1 min, +3-5 min the first time to encode the KB)"
    "$PY" scripts/train_classifier.py
  fi
  if need artifacts/kb_embeddings.npy || need artifacts/kb_meta.parquet; then
    say "Building the retrieval index (~5 min on a laptop CPU)"
    "$PY" scripts/build_kb_index.py
  fi
  say "Setup done. Next: ./run.sh demo"
}

check_setup() {
  if [ ! -x "$PY" ] || [ ! -e artifacts/heads.joblib ] || [ ! -e artifacts/kb_embeddings.npy ]; then
    echo "Not set up yet: run ./run.sh setup first." >&2; exit 1
  fi
}

run_tests() {
  check_setup
  say "Tests: contract, gate, adversarial, root cause, status"
  "$PY" -m pytest -q tests
}

run_eval() {
  check_setup; load_env
  say "Holdout metrics -> reports/triage_metrics.json (the only reader of test labels)"
  "$PY" scripts/evaluate.py
  say "Attack table -> reports/attack_table.md"
  "$PY" scripts/attack_table.py
  say "Retrieval check -> reports/retrieval_check.json"
  "$PY" scripts/retrieval_check.py
  say "Draft quality on holdout tickets -> reports/draft_eval.json"
  SD_DRAFT_N="${SD_DRAFT_N:-5}" "$PY" scripts/draft_eval.py
}

seed() {
  check_setup
  say "Seeding a week of portal tickets -> data/live_tickets.json"
  "$PY" scripts/seed_demo.py
}

app() {
  check_setup; load_env
  say "Console on http://localhost:8501  (Ctrl+C to stop)"
  exec "$VENV/bin/streamlit" run app.py --server.port "${PORT:-8501}"
}

case "${1:-help}" in
  setup) setup ;;
  test)  run_tests ;;
  eval)  run_eval ;;
  seed)  seed ;;
  app)   app ;;
  demo)  seed; app ;;
  all)   setup; run_tests; seed; app ;;
  *)     sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
