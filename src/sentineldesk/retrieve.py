"""Track B owns this file.

faiss-cpu over L2-normalized vectors. If faiss misbehaves on arm64, do not debug
it: a 23k x 384 numpy matmul is sub-millisecond. Keep both behind this interface.
"""
from __future__ import annotations

import numpy as np

from .schema import Precedent


def build_index() -> None:
    """Index the KB split, persist to artifacts/."""
    raise NotImplementedError("Track B")


def search(query_vec: np.ndarray, k: int | None = None,
           queue_filter: str | None = None) -> list[Precedent]:
    """Top-k precedents, highest score first.

    queue_filter narrows to a predicted department but must fall back to the
    unfiltered index when it yields fewer than k hits.
    """
    raise NotImplementedError("Track B")
