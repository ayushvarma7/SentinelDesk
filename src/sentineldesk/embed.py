"""Track B owns this file.

One encoder serves the classifier, the language head and the retrieval index.
Encode the KB once, cache to artifacts/kb_embeddings.npy, and let Track A train
on the file rather than calling the model.
"""
from __future__ import annotations

import numpy as np


def encode(texts: list[str], is_query: bool = False) -> np.ndarray:
    """L2-normalized embeddings, shape (len(texts), config.EMBED_DIM).

    e5 requires the "query: " / "passage: " prefix — apply it here so no caller
    has to remember. is_query=True for an incoming ticket, False for the KB.
    """
    raise NotImplementedError("Track B")
