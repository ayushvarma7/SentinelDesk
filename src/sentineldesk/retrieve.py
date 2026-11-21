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
_LIVE: dict | None = None

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


# --------------------------------------------------------------------------
# Live store: precedents learned during a session.
#
# Kept in its own files, never merged into the frozen index, for three reasons:
#   1. reproducibility — scripts/evaluate.py and retrieval_check.py pass
#      include_live=False, so published metrics never depend on session state;
#   2. leakage — a holdout ticket appended during a demo would otherwise end up
#      answering its own question in the next evaluation run;
#   3. it can be wiped between demo runs without rebuilding anything.
#
# Live ids are LIVE-xxxxx, deliberately distinct from the KB's TKT-xxxxx, so a
# citation in a draft shows at a glance whether it came from history or from
# something a human resolved minutes ago.
# --------------------------------------------------------------------------

def _empty_live() -> dict:
    return {"matrix": np.zeros((0, config.EMBED_DIM), dtype=np.float32),
            "meta": pd.DataFrame(columns=META_COLUMNS)}


def load_live() -> dict:
    global _LIVE
    if _LIVE is None:
        if config.LIVE_EMB_PATH.exists() and config.LIVE_META_PATH.exists():
            _LIVE = {"matrix": np.load(config.LIVE_EMB_PATH).astype(np.float32),
                     "meta": pd.read_parquet(config.LIVE_META_PATH)}
        else:
            _LIVE = _empty_live()
    return _LIVE


def live_count() -> int:
    return len(load_live()["meta"])


def clear_live() -> None:
    """Wipe the session store. Does not touch the frozen index."""
    global _LIVE
    _LIVE = _empty_live()
    for p in (config.LIVE_EMB_PATH, config.LIVE_META_PATH):
        p.unlink(missing_ok=True)


def add_precedent(subject: str | None, body: str | None, answer: str,
                  language: str, queue: str = "", type_: str = "") -> str:
    """Add a resolved ticket to the live store and return its LIVE-xxxxx id.

    This is the escalation loop closing: the gate says "no precedent", a human
    resolves it, and the resolution becomes retrievable for the next ticket.
    Costs one encode (~11 ms) — there is no index to rebuild.
    """
    from . import embed

    answer = (answer or "").strip()
    if not answer:
        raise ValueError("a precedent needs an answer; that is the whole point of it")

    live = load_live()
    ticket_id = f"LIVE-{len(live['meta']) + 1:05d}"
    text = build_text(subject, body)
    vec = embed.encode([text], is_query=False)[0]

    row = {"ticket_id": ticket_id, "subject": subject or "", "body": body or "",
           "answer": answer, "language": language, "queue": queue, "type": type_,
           "priority": ""}
    live["matrix"] = np.vstack([live["matrix"], vec[None, :]]).astype(np.float32)
    live["meta"] = pd.concat([live["meta"], pd.DataFrame([row])], ignore_index=True)

    config.LIVE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.LIVE_EMB_PATH, live["matrix"])
    live["meta"].to_parquet(config.LIVE_META_PATH, index=False)
    return ticket_id


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


def _candidates(store: dict, q: np.ndarray, k: int, queue_filter: str | None):
    """Top candidates from one store as a list of (score, row_index)."""
    matrix, meta = store["matrix"], store["meta"]
    if len(matrix) == 0:
        return []
    # Apple's Accelerate BLAS leaves FP exception flags set, so numpy reports
    # spurious divide-by-zero/overflow warnings here. Verified: inputs and
    # outputs are finite and normalized.
    with np.errstate(all="ignore"):
        sims = matrix @ q

    rows = np.arange(len(meta))
    if queue_filter:
        mask = (meta["queue"].to_numpy() == queue_filter).nonzero()[0]
        # Only trust the filter if it leaves room; a wrong queue prediction
        # (macro-F1 0.61) must never starve retrieval.
        if len(mask) >= k * 4:
            rows = mask

    pool = min(len(rows), max(k * 6, 30))
    local = np.argpartition(-sims[rows], kth=pool - 1)[:pool]
    local = local[np.argsort(-sims[rows][local])]
    return [(float(sims[i]), int(i)) for i in rows[local]]


def search(query_vec: np.ndarray, k: int | None = None,
           queue_filter: str | None = None,
           include_live: bool = True) -> list[Precedent]:
    """Top-k precedents across the frozen KB and the live store, best first.

    Vectors are L2-normalized, so the dot product is cosine similarity.

    include_live=False is mandatory for anything that produces a published
    number — scripts/evaluate.py, scripts/retrieval_check.py — so metrics never
    depend on what someone typed into the console.
    """
    k = k or config.TOP_K
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)

    frozen = load_index()
    pools = [(frozen, s, i) for s, i in _candidates(frozen, q, k, queue_filter)]
    if include_live:
        live = load_live()
        pools += [(live, s, i) for s, i in _candidates(live, q, k, queue_filter)]
    pools.sort(key=lambda t: -t[1])

    # Drop near-identical precedents: templated answers make five copies of one
    # resolution look like five independent sources, which misleads on screen.
    picked: list[tuple[dict, float, int]] = []
    for store, score, i in pools:
        if len(picked) >= k:
            break
        vec = store["matrix"][i]
        if any(float(vec @ s2["matrix"][j]) >= config.DEDUP_SIMILARITY
               for s2, _, j in picked):
            continue
        picked.append((store, score, i))

    return [_row_to_precedent(store["meta"].iloc[i], score) for store, score, i in picked]
