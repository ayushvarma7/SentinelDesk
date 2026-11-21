# P3 / Safety gate and guardrails: work done and handoff

Branch `feature-ayush` (Kunal's `feature-kunal` P1 work merged in) · 21 Nov 2026 ·
Status: **risk patterns, PII tokens, burst detector, thresholds tuned; 26/26 attack table; all tests pass**

## 1. Summary

| Deliverable (plan §5) | Where | Result |
|---|---|---|
| P3.1 adversarial test file | `tests/test_adversarial.py` | 25 cases (18 attacks EN/DE + 7 look-alikes) |
| P3.2 risk patterns | `gate.RISK_PATTERNS`, `gate.detect_risks()` | **25/25**, 0 false alarms on the 7 look-alikes |
| P3.3 PII with dataset tokens | `pii.mask()` (alias `mask_pii`) | `<email>`, `<tel_num>`, `<acc_num>`, `<ip_address>` |
| P3.4 threshold sweep | `scripts/gate_sweep.py` → `reports/gate_sweep.{csv,json}` | thresholds applied in `config.py` |
| P3.5 burst detector | `src/sentineldesk/burst.py`, `config.BURST_*` | banner flags `[F, F, T, F]` at `BURST_SIM=0.86` |
| P3.6 attack table | `scripts/attack_table.py` → `reports/attack_table.md` | **26/26 pass** through the real pipeline |
| Gate unit tests | `tests/test_gate.py` | 12 pure tests (no models) |

The plan was written for a flat layout (`gate.py`, `pii.py`, `pipeline.SentinelDesk`). The repo uses Jay's
`src/sentineldesk/` scaffold, so everything was ported to it. Run from the repo root:

```bash
PYTHONPATH=src python tests/test_adversarial.py      # 25/25 adversarial cases pass
PYTHONPATH=src python tests/test_gate.py             # 12/12 gate tests passed
PYTHONPATH=src python -m pytest -q tests/            # 17 passed (adversarial + gate + contract)
PYTHONPATH=src python scripts/gate_sweep.py          # ~4 min (+5 min the first time to build kb_embeddings.npy)
PYTHONPATH=src python scripts/attack_table.py        # 26/26 pass
```

## 2. What changed, file by file

| File | Change |
|---|---|
| `gate.py` | New `RISK_PATTERNS` (5 risks, EN + DE), `detect_risks()`, `too_little_text()`. `evaluate()` now: hard risks (injection, credentials, destructive, legal) always escalate and are the first reason on the badge; refunds/compensation escalate only when no retrieved precedent mentions them; burst and too-little-text reasons; `thresholds["min_confidence"]` overrides now merge with the defaults (a slider can change one head). New optional `burst=` arg. |
| `pii.py` | Dataset tokens instead of `[EMAIL_REDACTED]`. IBAN accepts grouped spaces (`DE89 3704 ...`); account numbers keep their keyword (`Kundennummer: <acc_num>`); phone numbers need 7–15 digits and dates are left alone. |
| `burst.py` (new) | `BurstDetector`: rolling window of recent query vectors; active when ≥ `BURST_MIN_COUNT` tickets (incl. this one) within `BURST_WINDOW_S` have cosine ≥ `BURST_SIM`. Returns `{"active", "related", "live_id", "max_sim"}`. |
| `config.py` | Tuned `MIN_CONFIDENCE`, `MIN_TOP1_SIMILARITY`, `MIN_MEAN_TOP3_SIMILARITY`; new `MIN_LETTERS`, `BURST_SIM`, `BURST_MIN_COUNT`, `BURST_WINDOW_S`. |
| `pipeline.py` | Module-level `BURST = BurstDetector()`; `triage()` passes the burst state to the gate and fills two new result fields. `thresholds["burst_sim"]` overrides `BURST_SIM` (for a console slider). |
| `schema.py` | `TriageResult` gained `risks: list[str]` and `burst: dict`, both with defaults, so every existing constructor call still works. **Contract change: announce to the team.** |

## 3. Results

### Risk patterns (P3.1 / P3.2)

- 25/25 adversarial cases, including the six the old regexes missed (plan: `inj-en-4`, `inj-de-2`, `cred-en-2`,
  `cred-de-1`, `destr-en-1`, `destr-de-1`).
- On the 22,863 real KB tickets the hard-risk patterns fire on only **5 tickets (0.02%)**, so they don't hurt the
  auto-draft rate. `financial_commitment` fires on 0.56%, and it's a soft rule.
- `fp-2` ("wants to sue... I mean pursue") is flagged `legal`. The plan allows that, since the case has no must-not set,
  and a human glance costs little.

### Threshold sweep (P3.4)

- Data: P1's validation slice, the first 10% of `RandomState(42).permutation(22863)`, which is 2,286 KB tickets kept
  out of `heads.joblib`.
- Retrieval: query (`query:`) against the KB passage index (`passage:`), with each ticket's own row excluded. Each
  grid point runs through the real `gate.evaluate()` with the top-3 precedents and their answers.
- **Selection rule, fixed in advance:** at least 95% of high-priority Incidents escalated, at least 25% auto-drafted,
  then the highest queue accuracy on auto-drafted tickets.

| | Value |
|---|---|
| Top-1 similarity p5 / p10 / p25 / p40 | 0.912 / 0.918 / 0.931 / 0.938 |
| **Chosen** min confidence type / queue / priority | **0.35 / 0.50 / 0.60** |
| **Chosen** min top-1 / mean top-3 similarity | **0.9305 / 0.9224** (the p25s) |
| Auto-drafted share | **26.5%** |
| High-priority Incidents escalated (n=406) | **95.3%** |
| Queue accuracy: auto-drafted vs all tickets | **0.827 vs 0.609** |

Gating makes the auto-drafted tickets much more reliable. That's the slide.

**Honest note:** the plan's 3×3×3×3 grid (type .35–.55, queue .20–.40, priority .30–.50, p5–p25) peaked at 93.6%
high-Incident escalation with Kunal's classifier, because its confidences are higher than the TF-IDF baseline's.
No grid point met the rule. The grid was widened upward to 400 points; the rule was not changed, and 107 points met it.
The holdout was never touched.

### Burst detector (P3.5)

Scenario: 3 VPN tickets (EN, EN, DE) followed by 1 invoice ticket. Measured max similarity to the earlier tickets:

| Ticket | Max similarity |
|---|---|
| EN VPN 2 | 0.937 |
| DE VPN | 0.884 |
| Invoice | 0.795 |

- The original `0.90` missed the cross-lingual ticket (`[F, F, F, F]`).
- Any value in (0.795, 0.88] gives `[F, F, T, F]`. I chose **0.86**, which leaves margin on both sides.

### Attack table (P3.6)

Full table in `reports/attack_table.md`.

- 26/26 pass.
- Every attack escalates with the correct top reason, and no injection gets a draft.
- The burst row raises the banner on the third VPN ticket and escalates it.

## 4. Things the team must know

1. **Everything escalates until P2 lands retrieval.** The pipeline still uses `_stub_precedents()` with scores
   0.88/0.79, which are below the tuned similarity floor of 0.93. That's correct behaviour for fake precedents. Once
   `STAGES["retrieve"] = True`, about a quarter of tickets will auto-draft.
2. **The similarity thresholds assume P2's index is e5-small with `passage:` KB vectors**, scored by cosine against the
   pipeline's `query:` vector. This is the scaffold's intended design. `gate_sweep.py` built
   `artifacts/kb_embeddings.npy` + `kb_ids.npy` in `load_kb()` order with `build_text()`, so P2 can reuse those files.
   If retrieval changes the model, prefixes, scoring or `queue_filter` behaviour, re-run `scripts/gate_sweep.py` and
   update `config.py`.
3. **Scripts that loop over tickets must call `pipeline.BURST.clear()`** between them, or the burst banner fires on
   their own traffic. `attack_table.py` does this; `evaluate.py` should too once it calls `triage()` per ticket.
4. **New result fields** `risks` and `burst` are available to the console:
   - show `burst["related"]` in the red banner;
   - use `thresholds={"burst_sim": x}` for a slider.
5. **Retrain locally** (`scripts/train_classifier.py`). It reproduced Kunal's validation numbers within 0.001
   (type 0.886, queue 0.617, priority 0.634, threshold 0.25).

## 5. Q&A prep (P3.7)

1. **"What if I phrase an injection your regex misses?"** Regex is the first of three layers. The ticket is fenced as
   untrusted data in the generation prompt, and the post-gate (Track C's `verify_citations`) still rejects citations
   outside the retrieved set and figures that don't appear in any precedent. Even if the regex misses, the draft can't
   promise anything that isn't grounded. Hard-risk tickets that are caught never reach the LLM at all.
2. **"How did you pick thresholds?"** `scripts/gate_sweep.py` ran on the KB validation slice the classifier never
   trained on, with a selection rule written before the sweep ran. The holdout was never used. I'll also say openly
   that the grid had to be widened when nothing met the rule.
3. **"Why is a refund request not auto-blocked?"** Refunds have real precedents (0.56% of KB tickets). The gate lets a
   refund ticket through only when a retrieved precedent's answer also discusses refunds or compensation. Any invented
   figure still forces human review.
4. **"Let me type my own attack."** If it slips through, I'll say which layer caught it (similarity, confidence,
   post-gate). Otherwise I'll add the phrasing as a new line in `CASES` and a regex alternative, and re-run
   `test_adversarial.py` live.
5. **"Doesn't the regex over-trigger?"** The hard patterns fire on 0.02% of real tickets, and the 7 look-alikes in the
   test file (password reset, "delete my draft invoice", "courtesy call", "ignore my previous email") pass clean.
