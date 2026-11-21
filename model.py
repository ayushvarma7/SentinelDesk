"""Retriever only.

OWNERSHIP NOTE: the plan assigns model.py to P1, who adds features() and
predict_heads() here. P2 needs Retriever for build_kb_index.py and
retrieval_check.py, so it is written here first. When P1's version lands, keep
theirs and re-add this class if it is missing — do not overwrite their file.
"""
from __future__ import annotations

import numpy as np


class Retriever:
    """Exact nearest-neighbour search over L2-normalized vectors.

    faiss if available, numpy otherwise. At 23k x 384 the numpy path is
    sub-millisecond, so a missing faiss (common on Apple Silicon) costs nothing.
    """

    def __init__(self, matrix: np.ndarray):
        self.matrix = np.ascontiguousarray(matrix, dtype="float32")
        self.index = None
        try:
            import faiss

            self.index = faiss.IndexFlatIP(self.matrix.shape[1])
            self.index.add(self.matrix)
            self.backend = "faiss"
        except Exception:
            self.backend = "numpy"

    def __len__(self) -> int:
        return len(self.matrix)

    def search(self, queries: np.ndarray, k: int = 5):
        """Return (D, I): similarities and row indices, best first."""
        q = np.ascontiguousarray(np.atleast_2d(queries), dtype="float32")
        k = min(k, len(self.matrix))
        if self.index is not None:
            return self.index.search(q, k)
        sims = q @ self.matrix.T
        idx = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
        order = np.argsort(-np.take_along_axis(sims, idx, axis=1), axis=1)
        idx = np.take_along_axis(idx, order, axis=1)
        return np.take_along_axis(sims, idx, axis=1), idx
