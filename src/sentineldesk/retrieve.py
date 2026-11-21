"""Track B (P2). Precedent retrieval over the KB split.

Exact cosine search with numpy, deliberately — not faiss. P1 measured that on
macOS faiss and torch each bundle libomp, and importing faiss first aborts the
process with OMP: Error #15. The pipeline imports torch, so faiss is out. At
22,863 x 384 an exact matmul is about 0.9 ms per query, so there is nothing to
gain anyway.

Two embedding files exist on purpose (docs/p1_workdone.md §5.3):
  kb_embeddings.npy        KB encoded as passages  -> this index
  kb_query_embeddings.npy  KB encoded as queries   -> the classifier's features
Never point one at the other.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .schema import Precedent
from .text import build_text

_INDEX: dict | None = None

META_COLUMNS = ["ticket_id", "subject", "body", "answer", "language", "queue", "type", "priority"]
SNIPPET_CHARS = 240


def build_index(show_progress: bool = True) -> None:
    """Encode the KB as passages and persist the index. Run once, ~5 min on an M4.

    KB order is data.load_kb() (22,863 rows, the answerless ones dropped), which
    is the order every other artifact assumes.
    """
    from . import data, embed

    kb = data.load_kb()
    texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
    print(f"[retrieve] encoding {len(texts):,} KB tickets as passages")
    emb = embed.encode(texts, is_query=False, show_progress=show_progress)

    if len(emb) != len(kb):
        raise RuntimeError(f"embedding/row mismatch: {len(emb)} vs {len(kb)}")

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    np.save(config.KB_EMB_PATH, emb)
    kb[[c for c in META_COLUMNS if c in kb.columns]].to_parquet(config.KB_META_PATH, index=False)
    print(f"[retrieve] wrote {config.KB_EMB_PATH.name} {emb.shape} and {config.KB_META_PATH.name}")


def load_index() -> dict:
    """Load once and keep it. Streamlit should call this at startup."""
    global _INDEX
    if _INDEX is None:
        if not config.KB_EMB_PATH.exists():
            raise FileNotFoundError(
                f"{config.KB_EMB_PATH} missing — run: PYTHONPATH=src python scripts/build_kb_index.py"
            )
        matrix = np.load(config.KB_EMB_PATH)
        meta = pd.read_parquet(config.KB_META_PATH)
        if len(matrix) != len(meta):
            raise RuntimeError(f"index/meta mismatch: {len(matrix)} vs {len(meta)}")
        _INDEX = {"matrix": np.ascontiguousarray(matrix, dtype=np.float32), "meta": meta}
    return _INDEX


def is_ready() -> bool:
    return config.KB_EMB_PATH.exists() and config.KB_META_PATH.exists()


def _row_to_precedent(row: pd.Series, score: float) -> Precedent:
    body = str(row.get("body") or "")
    return Precedent(
        ticket_id=str(row["ticket_id"]),
        score=float(score),
        subject=str(row.get("subject") or ""),
        body_snippet=body[:SNIPPET_CHARS] + ("…" if len(body) > SNIPPET_CHARS else ""),
        answer=str(row.get("answer") or ""),
        language=str(row.get("language") or ""),
        queue=str(row.get("queue") or ""),
    )


def search(query_vec: np.ndarray, k: int | None = None,
           queue_filter: str | None = None) -> list[Precedent]:
    """Top-k precedents, highest score first.

    Vectors are L2-normalized, so the dot product is cosine similarity.
    queue_filter narrows to a predicted department but falls back to the whole
    index whenever that would return fewer than k hits — a wrong queue
    prediction must never starve retrieval.
    """
    k = k or config.TOP_K
    idx = load_index()
    matrix, meta = idx["matrix"], idx["meta"]

    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    # Apple's Accelerate BLAS leaves FP exception flags set, so numpy reports
    # spurious divide-by-zero/overflow warnings here. Verified: inputs and
    # outputs are finite and normalized.
    with np.errstate(all="ignore"):
        sims = matrix @ q

    rows = np.arange(len(meta))
    if queue_filter:
        mask = (meta["queue"].to_numpy() == queue_filter).nonzero()[0]
        # Over-fetch before dedup, and only trust the filter if it is roomy enough.
        if len(mask) >= k * 4:
            rows = mask

    pool = min(len(rows), max(k * 6, 30))
    local = np.argpartition(-sims[rows], kth=pool - 1)[:pool]
    local = local[np.argsort(-sims[rows][local])]
    candidates = rows[local]

    # Drop near-identical precedents: templated answers make five copies of one
    # resolution look like five independent sources, which is misleading on screen.
    picked: list[int] = []
    for i in candidates:
        if len(picked) >= k:
            break
        if any(float(matrix[i] @ matrix[j]) >= config.DEDUP_SIMILARITY for j in picked):
            continue
        picked.append(int(i))

    return [_row_to_precedent(meta.iloc[i], sims[i]) for i in picked]
