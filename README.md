# SentinelDesk

**Autonomous incident triage and grounded resolution copilot.** For each support ticket (subject + body, English or German),
SentinelDesk does four things:

1. **Triage:** predicts `type`, `queue`, `priority` and `language`, each with a confidence.
2. **Escalation gate:** decides with deterministic, explainable rules whether the ticket gets an AI draft or goes to a human.
3. **Precedent retrieval:** finds the most similar resolved tickets, across both languages.
4. **Grounded reply:** drafts a reply in the customer's language that cites those tickets and invents nothing.

Data: `Tobi-Bueck/customer-support-tickets`, file `aa_dataset-tickets-multi-lang-5-2-50-version.csv`
(28,587 tickets, EN 57% / DE 43%), with the official seed-42 80/20 split.

## Layout

```
src/sentineldesk/        the package (import with PYTHONPATH=src)
  schema.py              interface contract: Prediction, Precedent, TriageResult
  pipeline.py            triage(subject, body) -> TriageResult; STAGES flags switch stubs to real stages
  config.py              paths, model names, thresholds (shared; announce changes)
  data.py, text.py       data access (leakage-safe) and build_text()
  embed.py               e5 encoder with query:/passage: prefixes          [Track B]
  classify.py            triage heads                                       [Track A, done]
  retrieve.py            KB index + search                                  [Track B, todo]
  generate.py            grounded draft + citation verification             [Track C, todo]
  gate.py, pii.py        escalation rules, PII masking
scripts/
  prepare_data.py        writes data/processed/{kb_train,test_inputs,test_labels}.parquet
  train_classifier.py    trains the triage heads, tunes the P(high) threshold
  evaluate.py            holdout metrics (the only reader of test labels)
tests/test_contract.py   edge cases that must never crash
notebooks/01_eda.ipynb   EDA (KB split only)
docs/p1_workdone.md      Track A results + takeover guide for retrieval/generation
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# put aa_dataset-tickets-multi-lang-5-2-50-version.csv in data/raw/
python scripts/prepare_data.py
PYTHONPATH=src python scripts/train_classifier.py   # ~1 min, plus 3-5 min the first time to encode the KB
PYTHONPATH=src python scripts/evaluate.py           # holdout metrics -> reports/triage_metrics.json
PYTHONPATH=src python tests/test_contract.py
```

## Pipeline status

| Stage | Status |
|---|---|
| PII masking, escalation gate | rules in place; thresholds still need tuning (see [docs/p1_workdone.md §6](docs/p1_workdone.md#6-findings-the-gate-owner-must-act-on)) |
| Embed | live: `multilingual-e5-small`, about 11 ms per ticket after warm-up |
| Classify | live: frozen model, metrics below |
| Retrieve | stub, Track B |
| Generate | stub, Track C |

## Triage model

- **Features:** word TF-IDF (1–2 grams) next to the ticket's e5 query embedding.
- **Heads:** one `LogisticRegression(C=32, class_weight="balanced")` per head.
- **Priority rule:** priority is labelled `high` whenever P(high) ≥ 0.25. The threshold was tuned on a KB validation slice to catch
  at least 80% of high-priority tickets, which feed the escalation gate.
- **Model selection:** every setting was chosen on that validation slice (10 runs; table in
  [docs/p1_workdone.md](docs/p1_workdone.md#4-results)).

### Holdout metrics (5,718 tickets, never used for selection)

| Metric | TF-IDF baseline | **Final model** |
|---|---|---|
| Type macro-F1 | 0.8747 | **0.8777** |
| Queue macro-F1 | 0.5718 | **0.6109** |
| Priority macro-F1 | 0.5974 | **0.6195** |
| Language macro-F1 | n/a | **0.9666** |
| ECE type / queue / priority / language | 0.050 / 0.144 / 0.039 / n/a | 0.028 / 0.012 / 0.082 / 0.003 |
| High-priority Incident recall: predicted high (n=995) | 0.8563 | 0.8523 |
| High-priority Incident recall: predicted high **and** Incident | 0.7658 | **0.7729** |
| High-priority Incident recall: escalated by gate | pending (needs retrieval + generation) | |
| Latency p50 / p95 | pending | |

Priority ECE rises because the recall-oriented threshold labels tickets with P(high) as low as 0.25 as `high`.
The trade is deliberate: a missed outage costs more than a false alarm.

## Leakage guarantees

- **Holdout split by file.** `prepare_data.py` writes the holdout as two files: `test_inputs.parquet` (ticket_id, subject, body)
  and `test_labels.parquet`. Only `scripts/evaluate.py` reads the labels.
- **Training data.** The classifier, its threshold and all hyperparameters come from the 80% KB split; tuning uses a 10% slice of it.
- **Retrieval and prompts.** Only KB answers may be retrieved or shown.
- **No mixing of files.** The 20k CSV is never mixed in, because it shares 8,399 bodies with the main file.
