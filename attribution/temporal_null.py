"""Trend-aware moving-block null distributions for time-series screening."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def detrend_series(
    values: np.ndarray, days: np.ndarray, seasonal_period: int | None = 7
) -> np.ndarray:
    """Remove level, linear trend and an optional Fourier seasonal basis."""
    if values.ndim != 1 or days.ndim != 1 or len(values) != len(days):
        raise ValueError("values and days must be equal-length one-dimensional arrays")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(days)):
        raise ValueError("values and days must be finite")
    if len(np.unique(days)) != len(days) or np.any(np.diff(days) <= 0):
        raise ValueError("days must be unique and strictly increasing")
    if len(values) < 3:
        return values - np.mean(values) if len(values) else values
    x = days.astype(float)
    x = (x - np.mean(x)) / max(np.std(x), 1e-12)
    columns = [np.ones(len(x)), x]
    if seasonal_period and seasonal_period >= 2 and len(values) >= 2 * seasonal_period:
        phase = 2.0 * math.pi * days.astype(float) / float(seasonal_period)
        columns.extend([np.sin(phase), np.cos(phase)])
    design = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    return values - design @ coefficients


def moving_block_indices(
    n: int, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """Sample contiguous non-wrapping blocks, preserving local dependence."""
    if n <= 0:
        raise ValueError("n must be positive")
    if block_length <= 0:
        raise ValueError("block_length must be positive")
    length = max(1, min(int(block_length), n))
    starts = np.arange(0, max(n - length + 1, 1))
    indices: list[int] = []
    while len(indices) < n:
        start = int(rng.choice(starts))
        indices.extend(range(start, min(start + length, n)))
    return np.asarray(indices[:n], dtype=int)


def independent_block_null(
    x: np.ndarray,
    y: np.ndarray,
    block_length: int,
    reps: int,
    statistic,
    rng: np.random.Generator,
) -> np.ndarray:
    """Break cross-series alignment while retaining within-series blocks."""
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) == 0:
        raise ValueError(
            "x and y must be non-empty equal-length one-dimensional arrays"
        )
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("x and y must be finite")
    if block_length <= 0 or reps <= 0:
        raise ValueError("block_length and reps must be positive")
    result = np.zeros(max(int(reps), 1), dtype=float)
    for index in range(len(result)):
        ix = moving_block_indices(len(x), block_length, rng)
        iy = moving_block_indices(len(y), block_length, rng)
        result[index] = float(statistic(x[ix], y[iy]))
    return result


def max_t_pvalues(
    observed: Sequence[float], null_statistics: Sequence[Sequence[float]]
) -> list[float]:
    """Westfall-Young style max-T p-values for a locked test family."""
    if not observed:
        return []
    observed_values = np.asarray(observed, dtype=float)
    if not np.all(np.isfinite(observed_values)):
        raise ValueError("observed statistics must be finite")
    if len(null_statistics) != len(observed):
        raise ValueError("one null-statistic series is required per observed statistic")
    rows = [np.asarray(row, dtype=float) for row in null_statistics]
    if not rows or any(row.ndim != 1 or len(row) == 0 for row in rows):
        raise ValueError("null-statistic series must be non-empty and one-dimensional")
    if len({len(row) for row in rows}) != 1 or any(
        not np.all(np.isfinite(row)) for row in rows
    ):
        raise ValueError("null-statistic series must be finite and equal-length")
    null = np.abs(np.vstack(rows))
    max_null = np.max(null, axis=0)
    return [
        float((1.0 + np.sum(max_null >= abs(float(value)))) / (len(max_null) + 1.0))
        for value in observed
    ]


__all__ = [
    "detrend_series",
    "independent_block_null",
    "max_t_pvalues",
    "moving_block_indices",
]
