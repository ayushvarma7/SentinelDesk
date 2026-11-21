"""Track A owns this file.

Four LogisticRegression heads (type, queue, priority, language) over the shared
embeddings. class_weight="balanced" is what buys high-priority recall and keeps
the 21x-imbalanced queue head honest.
"""
from __future__ import annotations

import numpy as np

from .schema import Prediction


def train(X: np.ndarray, y: dict[str, np.ndarray]) -> None:
    """Fit one head per target and persist to artifacts/heads.joblib."""
    raise NotImplementedError("Track A")


def predict(x: np.ndarray) -> dict[str, Prediction]:
    """Return {"type": Prediction, "queue": ..., "priority": ..., "language": ...}."""
    raise NotImplementedError("Track A")
