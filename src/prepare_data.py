"""Lock the 80/20 KB/holdout split exactly as the problem statement specifies.

Usage: python src/prepare_data.py [--small]
  --small  use the 20k prototyping file instead of the recommended 28.6k file
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

FULL = "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
SMALL = "dataset-tickets-multi-lang-4-20k.csv"


def main() -> None:
    src = SMALL if "--small" in sys.argv else FULL
    df = pd.read_csv(RAW / src)
    df["subject"] = df["subject"].fillna("")  # nullable subjects must not crash the pipeline

    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]

    split_idx = int(len(df) * 0.8)
    kb_train_df = df.iloc[:split_idx].copy()  # training + RAG indexing
    test_df = df.iloc[split_idx:].copy()      # holdout: never index answer/labels

    OUT.mkdir(parents=True, exist_ok=True)
    kb_train_df.to_parquet(OUT / "kb_train.parquet", index=False)
    test_df.to_parquet(OUT / "test_holdout.parquet", index=False)

    print(f"source: {src}  total={len(df)}  kb_train={len(kb_train_df)}  test={len(test_df)}")
    for col in ["type", "queue", "priority", "language"]:
        print(f"\n{col}:\n{kb_train_df[col].value_counts().to_string()}")


if __name__ == "__main__":
    main()
