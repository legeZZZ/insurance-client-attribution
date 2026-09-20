"""Fixed dependence statistics shared by discovery and confirmation.

Distance correlation uses double-centered Euclidean distance matrices, the
usual biased sample estimator. A positive sample value alone is not a test.
Reference: https://dcor.readthedocs.io/en/latest/theory.html
"""

from __future__ import annotations

import numpy as np

METHODS = ("pearson", "spearman", "dcor")


def _average_ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    start = 0
    while start < len(x):
        end = start + 1
        while end < len(x) and x[order[end]] == x[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2 + 1
        start = end
    return ranks


def _centered_distances(x: np.ndarray) -> np.ndarray:
    distances = np.abs(x[:, None] - x[None, :])
    return (
        distances
        - distances.mean(axis=0)[None, :]
        - distances.mean(axis=1)[:, None]
        + distances.mean()
    )


def dependence_statistic(x, y, method: str = "pearson") -> float:
    """Return signed Pearson/Spearman or unsigned sample distance correlation."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("dependence inputs must be equally sized vectors")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("dependence inputs must be finite")
    if len(x) < 4 or np.std(x) <= 1e-12 or np.std(y) <= 1e-12:
        return 0.0
    if method == "spearman":
        x, y = _average_ranks(x), _average_ranks(y)
    if method != "dcor":
        return float(np.corrcoef(x, y)[0, 1])
    a, b = _centered_distances(x), _centered_distances(y)
    denominator = np.sqrt(np.mean(a * a) * np.mean(b * b))
    if denominator <= 0:
        return 0.0
    return float(np.sqrt(np.clip(np.mean(a * b) / denominator, 0, 1)))
