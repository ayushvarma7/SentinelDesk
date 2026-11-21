"""OWNER: P2. The single encoder used for both the KB index and live queries.

Ticket-to-ticket matching is symmetric, so the same e5 prefix goes on both
sides. Vectors come back L2-normalized, which makes cosine similarity a plain
dot product and lets Retriever use inner-product search.
"""
from __future__ import annotations

import os

import numpy as np

from config import EMB_DIM, EMB_MODEL, EMB_PREFIX

_model = None


def get_model():
    """Load once. Streamlit and the eval scripts both call embed() repeatedly."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        device = os.getenv("SD_DEVICE") or None  # None lets ST pick mps/cuda/cpu
        _model = SentenceTransformer(EMB_MODEL, device=device)
    return _model


def embed(texts, show: bool = False) -> np.ndarray:
    """(n, EMB_DIM) float32, L2-normalized. Empty input returns an empty array."""
    texts = [t if isinstance(t, str) else "" for t in texts]
    if not texts:
        return np.zeros((0, EMB_DIM), dtype="float32")
    vecs = get_model().encode(
        [EMB_PREFIX + t for t in texts],
        batch_size=int(os.getenv("SD_BATCH", "64")),
        show_progress_bar=show,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return np.asarray(vecs, dtype="float32")
