"""Bounded exploratory C-line scanning and effect-form-aware falsification.

A watchlist is not a causal conclusion. Independent confirmation is a separate,
once-only next-window operation with a frozen family.
"""

from __future__ import annotations
from collections.abc import Sequence
from typing import Any
import numpy as np
from .association_discovery import _observed_lag, _lag_pairs, _lag_test, _series_values
from .contracts import digest, finite, integer
from .input_validation import validate_ordered_series

DEFAULT_LAGS = (0, 1, 2, 3, 7)
PLACEBO_SHIFT = 14
PLACEBO_TOLERANCE = 0.7
MIN_COVERAGE = 0.5
MIN_STRENGTH = 0.3
SHAPES = {"persistent", "onset", "pulse"}


def _identity(factor):
    return (
        str(factor["factor_id"]),
        str(factor.get("scope_id", "global")),
        str(factor.get("metric_id", "metric")),
    )


def _metric_responses(days, residual, factors, metric_series):
    ids = {str(f.get("metric_id", "metric")) for f in factors}
    if len(ids) > 1 and (metric_series is None or not ids <= set(metric_series)):
        raise ValueError(
            "multi-metric scans require a residual series for every metric"
        )
    responses = {key: (metric_series or {}).get(key, residual) for key in ids}
    for key, values in responses.items():
        validate_ordered_series(days, values, component="metric_residual:" + key)
    return responses


def hunter_scan(
    days,
    residual,
    factors,
    lags=DEFAULT_LAGS,
    budget=5,
    min_coverage=MIN_COVERAGE,
    min_strength=MIN_STRENGTH,
    budget_multipliers=None,
    *,
    test_budget=100,
    metric_series=None,
):
    validate_ordered_series(days, residual, component="watchlist")
    if (
        integer(budget, "budget") < 0
        or integer(test_budget, "test_budget") < 0
        or not 0 <= finite(min_strength, "min_strength") <= 1
        or not 0 <= finite(min_coverage, "min_coverage") <= 1
    ):
        raise ValueError("bounded scan settings required")
    lags = [integer(l, "lag") for l in lags]
    if len(set(lags)) != len(lags) or any(l < 0 for l in lags):
        raise ValueError("unique nonnegative candidate lags required")
    if len({_identity(f) for f in factors}) != len(factors):
        raise ValueError("duplicate factor/scope/metric in scan family")
    responses = _metric_responses(days, residual, factors, metric_series)
    multipliers = budget_multipliers or {}
    for factor in factors:
        fd, fv = _series_values(factor, days)
        validate_ordered_series(fd.tolist(), fv.tolist(), component="scan_factor")
        if factor.get("effect_shape", "persistent") not in SHAPES:
            raise ValueError("registered persistent/onset/pulse effect shape required")
    # Feedback changes scheduling before outcomes are read; statistics stay untouched.
    ordered = sorted(
        factors,
        key=lambda f: (
            -min(
                1.5,
                max(
                    0.5,
                    finite(multipliers.get(f.get("kind", "unknown"), 1), "multiplier"),
                ),
            ),
            _identity(f),
        ),
    )
    attempts = []
    hypotheses = []
    for factor in ordered:
        mult = min(
            1.5, max(0.5, float(multipliers.get(factor.get("kind", "unknown"), 1)))
        )
        for lag in lags:
            if len(attempts) >= test_budget:
                break
            result = _observed_lag(
                days, responses[str(factor.get("metric_id", "metric"))], factor, lag
            )
            identity = {
                "factor_id": str(factor["factor_id"]),
                "parent_factor_id": str(
                    factor.get("parent_factor_id", factor["factor_id"])
                ),
                "scope_id": str(factor.get("scope_id", "global")),
                "metric_id": str(factor.get("metric_id", "metric")),
                "lag": lag,
                "effect_shape": factor.get("effect_shape", "persistent"),
            }
            attempts.append({**identity, **result})
            if (
                result["n_pairs"] >= 6
                and result["coverage"] >= min_coverage
                and abs(result["correlation"]) >= min_strength
            ):
                hypotheses.append(
                    {
                        **identity,
                        **result,
                        "kind": factor.get("kind", "unknown"),
                        "score": abs(result["correlation"]) * result["coverage"] * mult,
                        "budget_multiplier": mult,
                    }
                )
    hypotheses.sort(key=lambda h: (-h["score"], h["factor_id"], h["lag"]))
    return {
        "hypotheses": hypotheses[:budget],
        "manifest": {
            "M": len({f.get("parent_factor_id", f["factor_id"]) for f in factors}),
            "S": len({f.get("scope_id", "global") for f in factors}),
            "K": len({f.get("metric_id", "metric") for f in factors}),
            "L": len(lags),
            "grid_size": len(factors) * len(lags),
            "tested": len(attempts),
            "test_budget": test_budget,
            "budget": budget,
            "attempts": attempts,
            "truncated": len(attempts) < len(factors) * len(lags),
            "selection_policy": "registered_order_with_feedback_priority",
            "inference": "exploratory_only",
        },
    }


def falsify(
    hypothesis, days, residual, factor, *, negative_controls=(), test_budget=20
):
    lag = integer(hypothesis["lag"], "lag")
    observed = finite(hypothesis["correlation"], "correlation")
    shape = factor.get("effect_shape", hypothesis.get("effect_shape", "persistent"))
    if shape not in SHAPES:
        raise ValueError("unsupported registered effect shape")
    spent = 0

    def observe(ds, ys, fs, ls):
        nonlocal spent
        if spent >= test_budget:
            return {
                "correlation": 0.0,
                "n_pairs": 0,
                "coverage": 0.0,
                "budget_exhausted": True,
            }
        spent += 1
        return _observed_lag(ds, ys, fs, ls)

    lookup = dict(zip(days, residual))
    shifted = [d for d in days if d + PLACEBO_SHIFT in lookup]
    placebo = observe(
        shifted, [lookup[d + PLACEBO_SHIFT] for d in shifted], factor, lag
    )
    applicable = shape == "persistent" and factor.get("placebo_applicable", True)
    insufficient = placebo["n_pairs"] < 6
    placebo_kill = (
        applicable
        and not insufficient
        and abs(placebo["correlation"]) >= PLACEBO_TOLERANCE * abs(observed)
    )
    reverse = observe(days, residual, factor, -lag) if lag > 0 else None
    reverse_applicable = lag > 0 and factor.get(
        "reversal_applicable", shape == "persistent"
    )
    reverse_kill = bool(
        reverse_applicable
        and reverse["n_pairs"] >= 6
        and abs(reverse["correlation"]) >= abs(observed)
    )
    mid = len(days) // 2
    halves = (
        [
            observe(days[:mid], residual[:mid], factor, lag),
            observe(days[mid:], residual[mid:], factor, lag),
        ]
        if shape == "persistent"
        else []
    )
    split_applicable = shape == "persistent"
    # Near-zero later evidence is insufficient, not a sign-reversal counterexample.
    split_enough = bool(
        halves
        and all(h["n_pairs"] >= 6 and abs(h["correlation"]) >= 0.15 for h in halves)
    )
    split_kill = (
        split_enough and halves[0]["correlation"] * halves[1]["correlation"] < 0
    )
    negatives = []
    for control in negative_controls:
        result = observe(days, residual, control, lag)
        negatives.append(
            {
                "factor_id": control["factor_id"],
                **result,
                "kill": result["n_pairs"] >= 6
                and abs(result["correlation"]) >= PLACEBO_TOLERANCE * abs(observed),
            }
        )
    tests = {
        "placebo": {
            **placebo,
            "correlation": abs(placebo["correlation"]),
            "kill": placebo_kill,
            "insufficient_data": insufficient,
            "applicable": applicable,
            "status": "INSUFFICIENT_DATA"
            if insufficient
            else "TESTED"
            if applicable
            else "NOT_APPLICABLE",
        },
        "lead_lag_reversal": {
            "correlation": abs(reverse["correlation"]) if reverse else None,
            "kill": reverse_kill,
            "skipped": not reverse_applicable,
            "applicable": reverse_applicable,
        },
        "split_half": {
            "first": halves[0]["correlation"] if halves else None,
            "second": halves[1]["correlation"] if halves else None,
            "kill": split_kill,
            "applicable": split_applicable,
            "status": "NOT_APPLICABLE"
            if not split_applicable
            else "TESTED"
            if split_enough
            else "INSUFFICIENT_DATA",
        },
        "negative_controls": negatives,
    }
    killed = (
        placebo_kill or reverse_kill or split_kill or any(n["kill"] for n in negatives)
    )
    exhausted = (
        placebo.get("budget_exhausted", False)
        or any(h.get("budget_exhausted", False) for h in halves)
        or any(n.get("budget_exhausted", False) for n in negatives)
        or bool(reverse and reverse.get("budget_exhausted", False))
    )
    insufficient_any = exhausted or (
        (applicable and insufficient)
        or (split_applicable and not split_enough)
        or any(n["n_pairs"] < 6 for n in negatives)
    )
    return {
        "survived": not killed and not insufficient_any,
        "killed": killed,
        "status": "FALSIFIED"
        if killed
        else "INSUFFICIENT_EVIDENCE"
        if insufficient_any
        else "SURVIVED_EXPLORATORY",
        "tests": tests,
        "tests_spent": spent,
        "effect_shape": shape,
        "reason_codes": ["INSUFFICIENT_POWER"] if insufficient_any else [],
        "inapplicable_tests_do_not_reject": True,
    }


def run_c_line(
    days,
    residual,
    factors,
    lags=DEFAULT_LAGS,
    budget=5,
    budget_multipliers=None,
    *,
    test_budget=200,
    negative_controls=(),
    window_id=None,
    metric_series=None,
):
    test_budget = integer(test_budget, "test_budget")
    if test_budget < 1:
        raise ValueError("positive total scan budget required")
    responses = _metric_responses(days, residual, factors, metric_series)
    hunted = hunter_scan(
        days,
        residual,
        factors,
        lags,
        budget,
        budget_multipliers=budget_multipliers,
        test_budget=max(1, test_budget // 2),
        metric_series=metric_series,
    )
    by_id = {_identity(f): f for f in factors}
    spent = hunted["manifest"]["tested"]
    watchlist = []
    killed = []
    deferred = []
    window_id = window_id or digest({"days": list(days)})
    for h in hunted["hypotheses"]:
        factor = by_id[(h["factor_id"], h["scope_id"], h["metric_id"])]
        verdict = falsify(
            h,
            days,
            responses[h["metric_id"]],
            factor,
            negative_controls=negative_controls,
            test_budget=max(0, test_budget - spent),
        )
        spent += verdict["tests_spent"]
        record = {
            **h,
            "falsification": verdict["tests"],
            "falsification_status": verdict["status"],
            "claim_type": "WATCHLIST",
            "grade": "REVIEW" if verdict["survived"] else "NEEDS_DATA",
            "alert_id": digest(
                {"factor": _identity(factor), "lag": h["lag"], "window": window_id}
            ),
            "window_id": window_id,
            "discovery_window": [min(days), max(days)],
            "next_step": "仅下一独立窗口确认可晋级；人工标签只进入验证队列",
        }
        (
            killed
            if verdict["killed"]
            else watchlist
            if verdict["survived"]
            else deferred
        ).append(record)
    return {
        "claim_type": "WATCHLIST",
        "watchlist": watchlist,
        "deferred": deferred,
        "killed": killed,
        "killed_count": len(killed),
        "manifest": {
            **hunted["manifest"],
            "total_tests_spent": spent,
            "total_test_budget": test_budget,
        },
        "policy": "exploratory_only_no_cross_time_error_control_claim",
        "data_digest": digest(
            {
                "days": list(days),
                "residual": list(residual),
                "factors": factors,
                "metric_series": metric_series,
            }
        ),
    }


def confirm_watchlist(
    items,
    days,
    residual,
    factors,
    *,
    metric_series=None,
    alpha=0.05,
    bootstrap_reps=199,
    block_length=3,
    seed=20260915,
):
    from .fdr import holm

    if (
        not 0 < finite(alpha, "alpha") < 1
        or not 19 <= integer(bootstrap_reps, "bootstrap_reps") <= 9999
        or integer(block_length, "block_length") < 1
    ):
        raise ValueError("registered confirmation settings required")
    validate_ordered_series(days, residual, component="next_window")
    responses = _metric_responses(days, residual, factors, metric_series)
    by_id = {_identity(f): f for f in factors}
    results = []
    rng = np.random.default_rng(seed)
    for item in items:
        if min(days) <= item["discovery_window"][1] + abs(item["lag"]) + 2:
            raise ValueError(
                "confirmation window must follow discovery with isolation gap"
            )
        factor = by_id.get(
            (
                item["factor_id"],
                item.get("scope_id", "global"),
                item.get("metric_id", "metric"),
            )
        )
        if factor is None:
            results.append(
                {
                    "alert_id": item["alert_id"],
                    "raw_pvalue": 1.0,
                    "reason_codes": ["DATA_INVALID"],
                }
            )
            continue
        fd, fv = _series_values(factor, days)
        pd, x, y = _lag_pairs(
            days, responses[item.get("metric_id", "metric")], fd, fv, item["lag"]
        )
        if len(x) < max(10, 2 * block_length):
            results.append(
                {
                    "alert_id": item["alert_id"],
                    "raw_pvalue": 1.0,
                    "reason_codes": ["INSUFFICIENT_POWER"],
                }
            )
            continue
        test = _lag_test(pd, x, y, block_length, bootstrap_reps, rng, None)
        same_sign = test["correlation"] * item["correlation"] > 0
        results.append(
            {
                "alert_id": item["alert_id"],
                "raw_pvalue": test["raw_pvalue"] if same_sign else 1.0,
                "correlation": test["correlation"],
                "reason_codes": [],
            }
        )
    for result, adjusted in zip(results, holm([r["raw_pvalue"] for r in results])):
        result.update(
            adjusted_pvalue=adjusted,
            claim_type="FACTOR_CANDIDATE" if adjusted <= alpha else "WATCHLIST",
            confirmed=adjusted <= alpha,
        )
    return {
        "results": results,
        "alpha": alpha,
        "correction": "holm",
        "family_digest": digest(items),
        "window": [min(days), max(days)],
        "inference": "independent_frozen_family_empirical_block_null",
        "causal_eligible": False,
    }


def run_demo(output_path=None) -> dict[str, Any]:
    """Deterministic demo: one planted lag-2 driver must survive; noise must die."""
    rng = np.random.default_rng(20260914)
    n = 60
    days = list(range(n))
    driver = rng.normal(0.0, 1.0, n)
    residual = np.zeros(n)
    for t in range(2, n):
        residual[t] = 0.8 * driver[t - 2] + rng.normal(0.0, 0.4)
    noise = rng.normal(0.0, 1.0, n)
    factors = [
        {
            "factor_id": "demo.planted_driver",
            "kind": "internal_event",
            "days": days,
            "values": [float(v) for v in driver],
        },
        {
            "factor_id": "demo.noise",
            "kind": "external_event",
            "days": days,
            "values": [float(v) for v in noise],
        },
    ]
    result = run_c_line(days, residual.tolist(), factors, budget=4)
    if output_path:
        import json
        from pathlib import Path

        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
