"""Empirical shadow and contiguous-subsample diagnostics, never formal q-values.

This is a TSKI-style subsampling diagnostic, not a model-X knockoff generator
or an implementation claiming TSKI FDR guarantees.
"""

from __future__ import annotations

import math

import numpy as np

from .association_screen import dependence_statistic
from .input_validation import validate_ordered_series


def _statistic(values, residual, kind):
    if kind != "categorical":
        return dependence_statistic(values, residual, "dcor")
    # Hamming distances avoid arbitrary ordinal encodings of nominal labels.
    x = np.asarray(values, dtype=str)
    a = (x[:, None] != x[None, :]).astype(float)
    y = np.asarray(residual, dtype=float)
    b = abs(y[:, None] - y[None, :])
    a = a - a.mean(axis=0) - a.mean(axis=1)[:, None] + a.mean()
    b = b - b.mean(axis=0) - b.mean(axis=1)[:, None] + b.mean()
    denominator = math.sqrt(float(np.mean(a * a) * np.mean(b * b)))
    return (
        math.sqrt(max(0.0, min(1.0, float(np.mean(a * b)) / denominator)))
        if denominator > 0
        else 0.0
    )


def diagnose_shadow_stability(
    days,
    values,
    residual,
    *,
    kind="continuous",
    block_length=5,
    replicates=39,
    subsamples=5,
    seed=20260914,
):
    if kind not in {"continuous", "categorical", "event"}:
        raise ValueError("kind must be continuous, categorical or event")
    validate_ordered_series(days, residual, component="shadow_stability")
    if len(values) != len(days):
        raise ValueError("values and days must have equal length")
    for name, value in (
        ("block_length", block_length),
        ("replicates", replicates),
        ("subsamples", subsamples),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if kind != "categorical":
        validate_ordered_series(days, values, component="shadow_factor")
    elif any(
        v is None or not isinstance(v, (str, int)) or str(v) == "" for v in values
    ):
        raise ValueError("categorical labels must be nonempty strings or integers")
    if kind == "event" and not set(values) <= {0, 1}:
        raise ValueError("event values must be binary indicators")
    result = {
        "method": "temporal_shadow_contiguous_subsample",
        "guarantee": "empirical_only",
        "formal_pvalue": None,
        "formal_qvalue": None,
        "kind": kind,
        "assumptions": [
            "regular_daily_grid",
            "approximate_stationarity_for_shadow_comparison",
        ],
        "tski_relation": "subsampling_diagnostic_only_not_theoretical_knockoffs",
    }
    n = len(days)
    if n < max(12, 3 * block_length) or any(b - a != 1 for a, b in zip(days, days[1:])):
        return {
            **result,
            "status": "NOT_APPLICABLE",
            "reason": "short_or_irregular_time_grid",
        }
    if len(set(values)) < 2:
        return {**result, "status": "NOT_APPLICABLE", "reason": "constant_factor"}
    x = np.asarray(values, dtype=str if kind == "categorical" else float)
    y = np.asarray(residual, dtype=float)
    rng = np.random.default_rng(seed)
    observed = _statistic(x, y, kind)
    shadow_scores = []
    blocks = [np.arange(i, min(i + block_length, n)) for i in range(0, n, block_length)]
    for _ in range(replicates):
        if kind == "event":
            indices = np.roll(np.arange(n), int(rng.integers(1, n)))
        else:
            indices = np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])
        shadow_scores.append(_statistic(x[indices], y, kind))
    width = max(8, int(n * 0.7))
    starts = np.unique(
        np.linspace(0, n - width, min(subsamples, n - width + 1), dtype=int)
    )
    diagnostics = []
    for start in starts:
        end = int(start) + width
        diagnostics.append(
            {
                "window": [int(days[start]), int(days[end - 1])],
                "score": _statistic(x[start:end], y[start:end], kind),
            }
        )
    return {
        **result,
        "status": "DIAGNOSTIC_ONLY",
        "observed_score": observed,
        "shadow_method": "whole_event_circular_shift"
        if kind == "event"
        else "block_order_permutation",
        "shadow_scores": shadow_scores,
        "observed_exceeds_shadow_fraction": float(
            np.mean(observed > np.array(shadow_scores))
        ),
        "subsamples": diagnostics,
        "replicates": replicates,
        "block_length": block_length,
        "seed": seed,
        "changes_claim_eligibility": False,
    }
