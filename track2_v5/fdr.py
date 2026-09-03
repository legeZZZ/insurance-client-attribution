"""Multiple-testing helpers used only after the candidate set is locked."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def benjamini_hochberg(pvalues: Sequence[float]) -> list[float]:
    """Return BH q-values in input order; callers must record the search set."""
    if not pvalues:
        return []
    values = np.asarray(pvalues, dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("pvalues must be finite and in [0, 1]")
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    running = 1.0
    for rank in range(len(values), 0, -1):
        position = int(order[rank - 1])
        running = min(running, values[position] * len(values) / rank)
        adjusted[position] = running
    return adjusted.tolist()


__all__ = ["benjamini_hochberg"]
