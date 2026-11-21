"""OWNER: P2. Build the retrieval knowledge base from the 80% KB split.

Writes artifacts/kb.parquet, artifacts/kb_emb.npy and artifacts/test.parquet.
The holdout's answer column is dropped before anything is written, so no
downstream consumer can read it by accident.

Run:  python build_kb_index.py                 # full index, 22,863 tickets
      SD_KB_LIMIT=3000 python build_kb_index.py  # dev index, about 1 minute
"""
import os

import numpy as np

from config import ARTIFACT_DIR
from data import load_raw, official_split, ticket_text
from embed import embed

KB_COLUMNS = ["ticket_id", "subject", "body", "answer", "language", "type", "queue", "priority"]


def main() -> None:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    kb, test = official_split(load_raw())
    test = test.drop(columns=["answer"], errors="ignore")   # leakage guard

    limit = os.getenv("SD_KB_LIMIT")
    if limit:
        kb = kb.head(int(limit)).reset_index(drop=True)
        print(f"[kb] SD_KB_LIMIT={limit} -> dev index only, do NOT upload this build")

    kb = kb[[c for c in KB_COLUMNS if c in kb.columns]].reset_index(drop=True)
    texts = [ticket_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
    print(f"[kb] embedding {len(texts):,} tickets")
    emb = embed(texts, show=True)

    assert len(emb) == len(kb), f"embedding/row mismatch: {len(emb)} vs {len(kb)}"

    kb.to_parquet(f"{ARTIFACT_DIR}/kb.parquet", index=False)
    np.save(f"{ARTIFACT_DIR}/kb_emb.npy", emb)
    test.to_parquet(f"{ARTIFACT_DIR}/test.parquet", index=False)

    print(f"[kb] embeddings {emb.shape}, holdout {len(test):,} rows")
    print(f"[kb] wrote kb.parquet, kb_emb.npy, test.parquet to {ARTIFACT_DIR}/")


if __name__ == "__main__":
    main()
