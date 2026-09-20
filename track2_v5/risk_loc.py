"""Weighted-risk localization with an explicit rate-panel adaptation.

Implements partition/weights, r1-r2 and coarse-to-fine removal from RiskLoc
(https://arxiv.org/abs/2205.10004). Expected clicks use baseline cell rates
at current exposures. Thus this challenger targets rate changes at fixed
current composition; the separate rate/mix ledger accounts for composition.
"""

from __future__ import annotations

import itertools
import time

import numpy as np

from .contracts import digest
from .input_validation import validate_rate_panel, validate_windows
from .rate_aware_rca import _aggregate


def _deviation(expected, actual):
    denominator = expected + actual
    return np.divide(
        2 * (expected - actual),
        denominator,
        out=np.zeros_like(expected, dtype=float),
        where=denominator != 0,
    )


def discover_risk_candidates(
    panel,
    dimensions,
    baseline_window,
    current_window,
    *,
    max_candidates=10000,
    top_k=10,
    risk_threshold=0.3,
    explanatory_fraction=0.02,
    max_seconds=None,
):
    """Return exploratory scopes; no p-values or causal eligibility assigned."""
    started = time.monotonic()
    validate_windows(baseline_window, current_window)
    for name, value in (("max_candidates", max_candidates), ("top_k", top_k)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if (
        not np.isfinite(risk_threshold)
        or not 0 <= risk_threshold < 1
        or not 0 < explanatory_fraction <= 1
    ):
        raise ValueError("invalid risk/explanatory thresholds")
    if max_seconds is not None and (not np.isfinite(max_seconds) or max_seconds <= 0):
        raise ValueError("max_seconds must be positive")
    bd = {
        int(r["day"])
        for r in panel
        if baseline_window[0] <= r["day"] <= baseline_window[1]
    }
    cd = {
        int(r["day"])
        for r in panel
        if current_window[0] <= r["day"] <= current_window[1]
    }
    if not bd or not cd:
        raise ValueError("both windows require observations")
    validation = validate_rate_panel(panel, dimensions, bd, cd)
    dims = tuple(sorted(dimensions))
    before, current = _aggregate(panel, dims, bd), _aggregate(panel, dims, cd)
    if set(before) != set(current):
        return {
            "model": "riskloc_rate_adaptation",
            "status": "DATA_INVALID",
            "reason": "cell_set_mismatch",
            "candidates": [],
        }
    keys = sorted(before)
    scopes = [dict(k) for k in keys]
    exposures = np.array([current[k]["treatment_impressions"] for k in keys])
    actual = np.array([current[k]["treatment_clicks"] for k in keys])
    expected = np.array(
        [before[k]["treatment_rate"] * e for k, e in zip(keys, exposures)]
    )
    ds = _deviation(expected, actual)
    unique = np.unique(ds)
    trimmed = unique[5:-5] if len(unique) > 10 else unique
    positive = abs(float(trimmed.min())) < abs(float(trimmed.max()))
    threshold = -float(trimmed.min()) if positive else -float(trimmed.max())
    abnormal = ds >= threshold if positive else ds <= threshold
    informative = (expected + actual) > 0
    abnormal &= informative & (abs(ds) > 1e-12)
    weights = (
        np.minimum(np.where(abnormal, abs(ds), abs(threshold - ds)), 1.0) * informative
    )
    # Common denominator at the current composition makes leaf contributions additive.
    changes = (actual - expected) / exposures.sum()
    initial_mass = float(changes[abnormal].sum())
    signed_changes = changes * (1 if initial_mass >= 0 else -1)
    minimum_mass = explanatory_fraction * abs(initial_mass)
    remaining = np.ones(len(keys), dtype=bool)
    candidates, trace = [], []
    evaluated = 0
    exhausted = False
    stop_reason = "NO_UNEXPLAINED_ABNORMAL_MASS"
    while len(candidates) < top_k and float(
        signed_changes[remaining & abnormal].sum()
    ) > max(minimum_mass, 1e-12):
        selected = None
        for depth in range(1, len(dims) + 1):
            eligible = []
            for subset in itertools.combinations(dims, depth):
                combinations = sorted(
                    {
                        tuple(s[d] for d in subset)
                        for i, s in enumerate(scopes)
                        if remaining[i]
                    }
                )
                for values in combinations:
                    if evaluated >= max_candidates or (
                        max_seconds is not None
                        and time.monotonic() - started >= max_seconds
                    ):
                        exhausted = True
                        break
                    scope = dict(zip(subset, values))
                    mask = remaining & np.array(
                        [all(s[d] == v for d, v in scope.items()) for s in scopes]
                    )
                    evaluated += 1
                    mass = float(signed_changes[mask].sum())
                    wa = float(weights[mask & abnormal].sum())
                    wn = float(weights[mask & ~abnormal].sum())
                    r1 = wa / (wa + wn + 1)
                    f, v = expected[mask], actual[mask]
                    if f.sum() > 0:
                        adjusted = f * v.sum() / f.sum()
                        denominator = float(abs(ds[mask]).sum())
                        r2 = (
                            float(abs(_deviation(adjusted, v)).sum()) / denominator
                            if denominator > 0
                            else 0.0
                        )
                    else:
                        # Zero expected totals cannot support the multiplicative ripple model.
                        r2 = 1.0
                    risk = r1 - r2
                    passes = risk >= risk_threshold and mass >= minimum_mass
                    trace.append(
                        {
                            "scope": scope,
                            "depth": depth,
                            "risk": risk,
                            "r1": r1,
                            "r2": r2,
                            "explanatory_mass": mass,
                            "status": "ELIGIBLE" if passes else "PRUNED_RISK_OR_MASS",
                        }
                    )
                    if passes:
                        eligible.append((mass, scope, mask.copy(), risk, r1, r2))
                if exhausted:
                    break
            if eligible:
                selected = max(eligible, key=lambda item: item[0])
                break
            if exhausted:
                break
        if selected is None:
            stop_reason = "BUDGET_EXHAUSTED" if exhausted else "NO_QUALIFIED_SCOPE"
            break
        mass, scope, mask, risk, r1, r2 = selected
        candidates.append(
            {
                "candidate_id": digest(
                    {
                        "scope": scope,
                        "baseline": baseline_window,
                        "current": current_window,
                    }
                ),
                "scope": scope,
                "risk": risk,
                "r1": r1,
                "r2": r2,
                "explanatory_mass": mass,
                "assigned_atom_ids": [digest(scopes[i]) for i in np.flatnonzero(mask)],
                "claim_type": "EXPLORATORY_LOCALIZATION",
            }
        )
        remaining[mask] = False
        if exhausted:
            stop_reason = "BUDGET_EXHAUSTED"
            break
    if len(candidates) == top_k and remaining.any() and not exhausted:
        stop_reason = "TOP_K_REACHED"
    return {
        "model": "riskloc_rate_adaptation",
        "status": "COMPLETED",
        "candidates": candidates,
        "input_validation": validation,
        "partition": {
            "threshold": threshold,
            "direction": "positive_deviation" if positive else "negative_deviation",
            "trimmed_unique_extremes": 5 if len(unique) > 10 else 0,
        },
        "search_manifest": {
            "max_candidates": max_candidates,
            "evaluated_candidates": evaluated,
            "max_seconds": max_seconds,
            "budget_exhausted": exhausted,
            "risk_threshold": risk_threshold,
            "explanatory_fraction": explanatory_fraction,
        },
        "stop_reason": stop_reason,
        "pruning_trace": trace,
        "runtime_seconds": time.monotonic() - started,
        "forecast_policy": "baseline_cell_rate_at_current_exposure",
        "limitations": [
            "descriptive_only",
            "fixed_current_composition",
            "multiplicative_ripple_requires_positive_forecast",
            "small_leaf_sets_do_not_trim_extremes",
        ],
    }
