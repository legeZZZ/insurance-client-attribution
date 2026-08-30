"""Association-factor discovery for Line B.

This module is deliberately associational. It does not infer causality from
an event timestamp. It turns unexplained residual windows into ranked,
traceable candidates from internal events, external events and factor series.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .fdr import benjamini_hochberg
from .input_validation import (
    validate_discovery_holdout,
    validate_ordered_series,
)
from .temporal_null import detrend_series, max_t_pvalues, moving_block_indices


def factor_series_from_snapshots(
    snapshots: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize raw factor snapshots into the series contract.

    Adapters enumerate observable internal and authorized external snapshots
    first. The detector ranks those candidates; it cannot name a factor for
    which no data source exists.
    """
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    signatures: set[tuple[str, str, int]] = set()
    for snapshot in snapshots:
        factor_id = str(snapshot["factor_id"])
        scope_id = str(snapshot.get("scope_id", "global"))
        day = int(snapshot["day"])
        value = float(snapshot["value"])
        if not math.isfinite(value):
            raise ValueError("factor snapshot values must be finite")
        signature = (factor_id, scope_id, day)
        if signature in signatures:
            raise ValueError(f"duplicate factor snapshot: {signature}")
        signatures.add(signature)
        key = (factor_id, scope_id)
        item = grouped.setdefault(
            key,
            {
                "factor_id": factor_id,
                "scope_id": scope_id,
                "source_type": snapshot.get("source_type", "factor_series"),
                "kind": snapshot.get("kind"),
                "scope_match": snapshot.get("scope_match", 0.5),
                "source_reliability": snapshot.get("source_reliability", 0.5),
                "days": [],
                "values": [],
            },
        )
        item["days"].append(day)
        item["values"].append(value)
    series = list(grouped.values())
    for item in series:
        ordered = sorted(zip(item["days"], item["values"]), key=lambda pair: pair[0])
        item["days"] = [day for day, _ in ordered]
        item["values"] = [value for _, value in ordered]
    return series


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 4 or np.std(x) <= 1e-12 or np.std(y) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _series_values(
    factor: Mapping[str, Any], days: Sequence[int]
) -> tuple[np.ndarray, np.ndarray]:
    factor_days = factor.get("days", days)
    values = factor.get("values")
    if values is None:
        raise ValueError("factor series requires values")
    if isinstance(values, Mapping):
        lookup = {int(day): float(value) for day, value in values.items()}
        paired = [
            (int(day), lookup[int(day)]) for day in factor_days if int(day) in lookup
        ]
    else:
        paired = list(
            zip([int(day) for day in factor_days], [float(v) for v in values])
        )
    if not paired:
        return np.asarray([], dtype=int), np.asarray([], dtype=float)
    return np.asarray([day for day, _ in paired]), np.asarray(
        [value for _, value in paired]
    )


def _detrend(
    values: np.ndarray, days: np.ndarray, seasonal_period: int | None = 7
) -> np.ndarray:
    """Remove a linear level/trend before testing association.

    The weekly seasonal basis is a default for daily operating metrics.  A
    metric contract can disable it or supply another period; the period is
    recorded in the search manifest.
    """
    if len(values) < 3 or np.std(values) <= 1e-12:
        return values - np.mean(values) if len(values) else values
    return detrend_series(values, days, seasonal_period)


def _rolling_median(values: np.ndarray, window: int = 3) -> np.ndarray:
    """Apply a small causal-safe robust smoother before differencing."""
    if len(values) < 3 or window <= 1:
        return values.astype(float, copy=True)
    width = max(3, int(window))
    if width % 2 == 0:
        width += 1
    half = width // 2
    padded = np.pad(values.astype(float), (half, half), mode="edge")
    return np.asarray([np.median(padded[i : i + width]) for i in range(len(values))])


def derive_factor_layers(
    factor: Mapping[str, Any],
    *,
    smoothing_window: int = 3,
    layers: Sequence[str] = ("level", "velocity", "acceleration"),
) -> list[dict[str, Any]]:
    """Expand one observed factor into level, velocity and acceleration views.

    The parent factor and the transformation lineage remain explicit. These
    are candidate-generation features, not separate causal variables.
    """
    factor_days, raw_values = _series_values(factor, factor.get("days", []))
    if len(raw_values) < 3:
        layers = tuple(layer for layer in layers if layer == "level")
    smoothed = _rolling_median(raw_values, smoothing_window)
    velocity = np.diff(smoothed, prepend=smoothed[0])
    acceleration = np.diff(velocity, prepend=velocity[0])
    values_by_layer = {
        "level": smoothed,
        "velocity": velocity,
        "acceleration": acceleration,
    }
    units = {
        "level": factor.get("unit", "source_unit"),
        "velocity": f"delta_per_day({factor.get('unit', 'source_unit')})",
        "acceleration": f"delta2_per_day2({factor.get('unit', 'source_unit')})",
    }
    parent_id = str(factor.get("parent_factor_id", factor.get("factor_id")))
    output: list[dict[str, Any]] = []
    for layer in layers:
        if layer not in values_by_layer:
            raise ValueError(f"unsupported derived layer: {layer}")
        item = dict(factor)
        item.update(
            {
                "factor_id": f"{parent_id}.{layer}",
                "parent_factor_id": parent_id,
                "derived_layer": layer,
                "transform": "identity"
                if layer == "level"
                else (
                    "first_difference" if layer == "velocity" else "second_difference"
                ),
                "unit": units[layer],
                "smoothing": f"rolling_median_{smoothing_window}",
                "days": factor_days.tolist(),
                "values": values_by_layer[layer].tolist(),
            }
        )
        output.append(item)
    return output


def _moving_block_indices(
    n: int, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """Sample contiguous blocks without circularly shifting the series."""
    return moving_block_indices(n, block_length, rng)


def _lag_pairs(
    days: Sequence[int],
    residual: Sequence[float],
    factor_days: np.ndarray,
    factor_values: np.ndarray,
    lag: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual_lookup = {int(day): float(value) for day, value in zip(days, residual)}
    pairs = [
        (int(day), float(value), residual_lookup[int(day + lag)])
        for day, value in zip(factor_days, factor_values)
        if int(day + lag) in residual_lookup
    ]
    if not pairs:
        return (
            np.asarray([], dtype=int),
            np.asarray([], dtype=float),
            np.asarray([], dtype=float),
        )
    return (
        np.asarray([item[0] for item in pairs], dtype=int),
        np.asarray([item[1] for item in pairs], dtype=float),
        np.asarray([item[2] for item in pairs], dtype=float),
    )


def _lag_test(
    pair_days: np.ndarray,
    factor_values: np.ndarray,
    residual_values: np.ndarray,
    block_length: int,
    bootstrap_reps: int,
    rng: np.random.Generator,
    seasonal_period: int | None,
) -> dict[str, Any]:
    x = _detrend(factor_values, pair_days, seasonal_period)
    y = _detrend(residual_values, pair_days, seasonal_period)
    observed = _corr(x, y)
    null = np.zeros(max(bootstrap_reps, 1), dtype=float)
    # Independent block resampling breaks cross-series alignment while
    # preserving within-series serial dependence.  It is the null used for
    # both the lag-level p-value and the later max-T correction.
    for index in range(len(null)):
        x_indices = _moving_block_indices(len(x), block_length, rng)
        y_indices = _moving_block_indices(len(y), block_length, rng)
        null[index] = _corr(x[x_indices], y[y_indices])
    pvalue = (1.0 + float(np.sum(np.abs(null) >= abs(observed)))) / (len(null) + 1.0)
    return {
        "correlation": float(observed),
        "raw_pvalue": float(pvalue),
        "null_statistics": null,
        "n_pairs": len(x),
    }


def _observed_lag(
    days: Sequence[int],
    residual: Sequence[float],
    factor: Mapping[str, Any],
    lag: int,
    seasonal_period: int | None = 7,
) -> dict[str, Any]:
    factor_days, values = _series_values(factor, days)
    pair_days, x, y = _lag_pairs(days, residual, factor_days, values, lag)
    if len(x) < 6:
        return {"correlation": 0.0, "coverage": 0.0, "n_pairs": len(x)}
    return {
        "correlation": _corr(
            _detrend(x, pair_days, seasonal_period),
            _detrend(y, pair_days, seasonal_period),
        ),
        "coverage": len(x) / max(len(days), 1),
        "n_pairs": len(x),
    }


def _event_candidate(
    event: Mapping[str, Any],
    days: Sequence[int],
    residual: Sequence[float],
    anomaly_windows: Sequence[Mapping[str, int]],
    max_lag: int,
) -> dict[str, Any]:
    start = int(event["start_day"])
    end = int(event.get("end_day", start))
    best_alignment = 0.0
    best_window: Mapping[str, int] | None = None
    best_distance = max_lag + 1
    for window in anomaly_windows:
        w_start, w_end = int(window["start_day"]), int(window["end_day"])
        overlap = max(0, min(end, w_end) - max(start, w_start) + 1)
        if overlap:
            alignment = overlap / max(min(end - start + 1, w_end - w_start + 1), 1)
            distance = 0
        else:
            distance = min(abs(start - w_end), abs(w_start - end))
            alignment = math.exp(-distance / max(max_lag, 1))
        if alignment > best_alignment:
            best_alignment, best_window, best_distance = alignment, window, distance

    residual_lookup = {int(day): float(value) for day, value in zip(days, residual)}
    event_values = [
        residual_lookup[day] for day in residual_lookup if start <= day <= end
    ]
    window_shift = float(np.mean(event_values)) if event_values else 0.0
    reliability = float(event.get("source_reliability", 0.5))
    scope_match = float(event.get("scope_match", 0.5))
    score = (
        best_alignment
        * max(0.0, min(reliability, 1.0))
        * max(0.0, min(scope_match, 1.0))
    )
    source_type = str(event.get("source_type", "external_event"))
    claim_type = (
        "TEMPORAL_ASSOCIATION"
        if source_type == "external_event"
        else "FACTOR_CANDIDATE"
    )
    return {
        "factor_id": str(event["factor_id"]),
        "source_type": source_type,
        "kind": event.get("kind"),
        "scope": event.get("scope"),
        "source_uri": event.get("source_uri"),
        "content_digest": event.get("content_digest"),
        "license_ref": event.get("license_ref"),
        "start_day": start,
        "end_day": end,
        "matched_window": dict(best_window) if best_window else None,
        "distance_days": int(best_distance),
        "alignment_score": round(best_alignment, 6),
        "window_residual_mean": round(window_shift, 6),
        "scope_match": round(scope_match, 6),
        "source_reliability": round(reliability, 6),
        "association_score": round(score, 6),
        "claim_type": claim_type,
        "evidence_level": claim_type,
        "validation_route": (
            "line_a_or_gray_release"
            if source_type == "internal_event"
            else "stratified_quasi_experiment"
        ),
    }


def discover_association_factors(
    days: Sequence[int],
    residual: Sequence[float],
    anomaly_windows: Sequence[Mapping[str, int]],
    events: Sequence[Mapping[str, Any]] = (),
    factor_series: Sequence[Mapping[str, Any]] = (),
    max_lag: int = 7,
    min_abs_correlation: float = 0.25,
    discovery_days: Sequence[int] | None = None,
    holdout_days: Sequence[int] | None = None,
    block_length: int | None = None,
    bootstrap_reps: int = 199,
    seed: int = 20260827,
    seasonal_period: int | None = 7,
    derived_layers: Sequence[str] = ("level", "velocity", "acceleration"),
    smoothing_window: int = 3,
) -> dict[str, Any]:
    """Rank internal/external factor candidates against unexplained residuals.

    Event candidates use temporal alignment and scope/source reliability.
    Series candidates use detrended lagged correlation and moving-block null
    resampling. All outputs remain FACTOR_CANDIDATE or TEMPORAL_ASSOCIATION.
    When a holdout window is supplied, it is the primary selection safeguard;
    discovery p-values are not treated as post-selection causal evidence.
    """
    input_validation = validate_ordered_series(
        days, residual, component="association_discovery"
    )
    if max_lag < 0:
        raise ValueError("max_lag must be non-negative")
    if bootstrap_reps <= 0:
        raise ValueError("bootstrap_reps must be positive")
    if block_length is not None and block_length <= 0:
        raise ValueError("block_length must be positive")
    all_days = [int(day) for day in days]
    discovery_set = {
        int(day) for day in (discovery_days if discovery_days is not None else all_days)
    }
    holdout_set = {int(day) for day in (holdout_days or [])}
    validate_discovery_holdout(all_days, sorted(discovery_set), sorted(holdout_set))
    previous_end: int | None = None
    for index, window in enumerate(anomaly_windows):
        start, end = int(window["start_day"]), int(window["end_day"])
        if start > end:
            raise ValueError(f"anomaly_windows[{index}] start_day must be <= end_day")
        if start not in set(all_days) or end not in set(all_days):
            raise ValueError(f"anomaly_windows[{index}] must be contained in days")
        if previous_end is not None and start <= previous_end:
            raise ValueError("anomaly_windows must be sorted and non-overlapping")
        previous_end = end
    series_signatures: set[tuple[str, str]] = set()
    for index, factor in enumerate(factor_series):
        if "factor_id" not in factor:
            raise ValueError(f"factor_series[{index}] requires factor_id")
        signature = (
            str(factor["factor_id"]),
            str(factor.get("scope_id", factor.get("scope", "global"))),
        )
        if signature in series_signatures:
            raise ValueError(f"duplicate factor series: {signature}")
        series_signatures.add(signature)
        factor_days, factor_values = _series_values(factor, all_days)
        validate_ordered_series(
            factor_days.tolist(),
            factor_values.tolist(),
            component=f"factor_series[{index}]",
        )
    event_ids: set[str] = set()
    for index, event in enumerate(events):
        event_id = str(event.get("factor_id", ""))
        if not event_id or event_id in event_ids:
            raise ValueError("event factor_id values must be non-empty and unique")
        event_ids.add(event_id)
        start = int(event["start_day"])
        end = int(event.get("end_day", start))
        if start > end:
            raise ValueError(f"events[{index}] start_day must be <= end_day")
    discovery_days_ordered = [day for day in all_days if day in discovery_set]
    if len(discovery_days_ordered) < 6:
        raise ValueError("discovery window must contain at least 6 observations")
    lag_values = list(range(-max_lag, max_lag + 1))
    expanded_series: list[dict[str, Any]] = []
    for factor in factor_series:
        expanded_series.extend(
            derive_factor_layers(
                factor, smoothing_window=smoothing_window, layers=derived_layers
            )
        )
    candidate_series_count = len(expanded_series)
    selected_tests: list[dict[str, Any]] = []
    test_records: list[dict[str, Any]] = []
    rng = np.random.default_rng(seed)
    inferred_block = block_length or max(
        2, round(len(discovery_days_ordered) ** (1.0 / 3.0))
    )
    for series_index, factor in enumerate(expanded_series):
        calendar_factor_days, calendar_values = _series_values(factor, all_days)
        discovery_mask = np.asarray(
            [int(day) in discovery_set for day in calendar_factor_days]
        )
        factor_days = calendar_factor_days[discovery_mask]
        values = calendar_values[discovery_mask]
        best_test: dict[str, Any] | None = None
        for lag in lag_values:
            pair_days, x, y = _lag_pairs(
                discovery_days_ordered,
                [residual[all_days.index(day)] for day in discovery_days_ordered],
                factor_days,
                values,
                lag,
            )
            if len(x) < 6:
                continue
            test = _lag_test(
                pair_days, x, y, inferred_block, bootstrap_reps, rng, seasonal_period
            )
            record = {
                "series_index": series_index,
                "factor_id": str(factor["factor_id"]),
                "scope_id": str(factor.get("scope_id", factor.get("scope", "global"))),
                "lag_days": lag,
                "correlation": test["correlation"],
                "raw_pvalue": test["raw_pvalue"],
                "n_pairs": test["n_pairs"],
                "null_statistics": test["null_statistics"],
            }
            test_records.append(record)
            if best_test is None or abs(record["correlation"]) > abs(
                best_test["correlation"]
            ):
                best_test = record
        if best_test is not None:
            selected_tests.append(best_test)

    raw_q_values = benjamini_hochberg([record["raw_pvalue"] for record in test_records])
    for record, qvalue in zip(test_records, raw_q_values):
        record["bh_q"] = float(qvalue)
    if test_records:
        max_t = max_t_pvalues(
            [record["correlation"] for record in test_records],
            [record["null_statistics"] for record in test_records],
        )
        for record, pvalue in zip(test_records, max_t):
            record["max_t_pvalue"] = pvalue
    candidates: list[dict[str, Any]] = []
    for selected in selected_tests:
        factor = expanded_series[int(selected["series_index"])]
        correlation = float(selected["correlation"])
        if abs(correlation) < min_abs_correlation:
            continue
        reliability = float(factor.get("source_reliability", 0.5))
        scope_match = float(factor.get("scope_match", 0.5))
        holdout = None
        if holdout_set:
            holdout_days_ordered = [day for day in all_days if day in holdout_set]
            holdout_residual = [
                residual[all_days.index(day)] for day in holdout_days_ordered
            ]
            holdout_factor_days, holdout_values = _series_values(factor, all_days)
            holdout_factor = {
                **dict(factor),
                "days": holdout_factor_days.tolist(),
                "values": holdout_values.tolist(),
            }
            holdout = _observed_lag(
                holdout_days_ordered,
                holdout_residual,
                holdout_factor,
                int(selected["lag_days"]),
                seasonal_period,
            )
            holdout["survives"] = bool(
                holdout["n_pairs"] >= 6
                and abs(float(holdout["correlation"])) >= min_abs_correlation
                and np.sign(float(holdout["correlation"])) == np.sign(correlation)
            )
        max_t_pvalue = float(selected.get("max_t_pvalue", 1.0))
        bh_q = float(selected.get("bh_q", 1.0))
        score = (
            abs(correlation)
            * (1.0 - max_t_pvalue)
            * max(0.0, min(reliability, 1.0))
            * max(0.0, min(scope_match, 1.0))
        )
        candidates.append(
            {
                "factor_id": str(factor["factor_id"]),
                "parent_factor_id": str(
                    factor.get("parent_factor_id", factor["factor_id"])
                ),
                "derived_layer": str(factor.get("derived_layer", "level")),
                "transform": factor.get("transform", "identity"),
                "unit": factor.get("unit"),
                "direction": "positive" if correlation > 0 else "negative",
                "source_type": str(factor.get("source_type", "factor_series")),
                "kind": factor.get("kind"),
                "scope": factor.get("scope"),
                "target_scope": factor.get("target_scope"),
                "experimentability": factor.get(
                    "experimentability", "external_or_observational"
                ),
                "scope_id": str(factor.get("scope_id", factor.get("scope", "global"))),
                "correlation": correlation,
                "lag_days": int(selected["lag_days"]),
                "coverage": round(
                    selected["n_pairs"] / max(len(discovery_days_ordered), 1), 6
                ),
                "n_pairs": int(selected["n_pairs"]),
                "raw_pvalue": float(selected["raw_pvalue"]),
                "bh_q": bh_q,
                "max_t_pvalue": max_t_pvalue,
                "holdout": holdout,
                "scope_match": round(scope_match, 6),
                "source_reliability": round(reliability, 6),
                "source_uri": factor.get("source_uri"),
                "content_digest": factor.get("content_digest"),
                "license_ref": factor.get("license_ref"),
                "association_score": round(score, 6),
                "claim_type": "FACTOR_CANDIDATE",
                "evidence_level": "FACTOR_CANDIDATE",
                "validation_route": "stratified_quasi_experiment",
            }
        )
    for event in events:
        candidate = _event_candidate(event, days, residual, anomaly_windows, max_lag)
        if candidate["matched_window"] is not None:
            candidates.append(candidate)
    candidates.sort(key=lambda item: item["association_score"], reverse=True)
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidate_id"] = f"cand-{index:03d}"
    event_count = len(event_ids)
    mapped = sum(
        1
        for item in candidates
        if item["factor_id"] in event_ids
        and item["claim_type"] in {"FACTOR_CANDIDATE", "TEMPORAL_ASSOCIATION"}
    )
    holdout_factor_candidates = [
        item
        for item in candidates
        if isinstance(item.get("holdout"), Mapping)
        and item["holdout"].get("survives") is True
    ]
    factors_considered = len(
        {str(f.get("parent_factor_id", f["factor_id"])) for f in factor_series}
    )
    derived_layers_considered = len(
        {str(f.get("derived_layer", "level")) for f in expanded_series}
    )
    scopes_considered = len(
        {str(f.get("scope_id", f.get("scope", "global"))) for f in expanded_series}
    )
    full_grid_comparisons = (
        factors_considered
        * derived_layers_considered
        * scopes_considered
        * len(lag_values)
    )
    selection_set = {
        "factor_ids": sorted(
            {str(f.get("parent_factor_id", f["factor_id"])) for f in factor_series}
        ),
        "derived_layers": sorted(
            {str(f.get("derived_layer", "level")) for f in expanded_series}
        ),
        "scope_ids": sorted(
            {str(f.get("scope_id", f.get("scope", "global"))) for f in expanded_series}
        ),
        "lags": lag_values,
        "metric": "detrended_residual_correlation",
        "discovery_window": sorted(discovery_set),
    }
    selection_set_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(selection_set, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()[:16]
    )
    return {
        "model": "line_b_association_factor_discovery",
        "claim_policy": "association_only_until_randomized_or_quasi_experimental_validation",
        "candidate_generation": (
            "source adapters enumerate observable internal and authorized external "
            "snapshots; ranking does not invent unobserved factor names."
        ),
        "anomaly_windows": [dict(window) for window in anomaly_windows],
        "candidate_count": len(candidates),
        "input_validation": {
            **input_validation,
            "factor_series_count": len(factor_series),
            "event_count": len(events),
            "anomaly_window_count": len(anomaly_windows),
            "checks_performed": [
                *input_validation["checks_performed"],
                "forward_discovery_holdout",
                "sorted_non_overlapping_anomaly_windows",
                "unique_factor_series",
                "unique_events",
            ],
        },
        "search_manifest": {
            "factors_considered": factors_considered,
            "scopes_considered": scopes_considered,
            "lags_considered": len(lag_values),
            "metrics_considered": 1,
            "M": factors_considered,
            "D": derived_layers_considered,
            "S": scopes_considered,
            "L": len(lag_values),
            "K": 1,
            "candidate_series_considered": candidate_series_count,
            "comparisons": full_grid_comparisons,
            "N": full_grid_comparisons,
            "candidate_series_comparisons": candidate_series_count * len(lag_values),
            "valid_comparisons": len(test_records),
            "block_length": inferred_block,
            "bootstrap_replicates": bootstrap_reps,
            "bootstrap_method": "detrended_moving_block_independent_null_max_t",
            "seasonal_period": seasonal_period,
            "derived_layers": list(derived_layers),
            "smoothing_window": smoothing_window,
            "selection_policy": "discovery_then_holdout_then_validation",
            "selection_set_digest": selection_set_digest,
            "bh_is_auxiliary": True,
            "post_selection_warning": (
                "BH 仅报告锁定候选集合内的辅助 q 值；跨 lag 选择后的可信防线是 holdout。"
            ),
        },
        "tested_lag_count": len(test_records),
        "bh_q_survivors": sum(
            1 for record in test_records if float(record.get("bh_q", 1.0)) <= 0.05
        ),
        "holdout_survivors": len(holdout_factor_candidates),
        "holdout_window": [min(holdout_set), max(holdout_set)] if holdout_set else None,
        "discovery_window": [min(discovery_set), max(discovery_set)]
        if discovery_set
        else [],
        "event_candidate_coverage": round(mapped / max(event_count, 1), 6),
        "candidates": candidates,
    }


def run_demo(output_path=None) -> dict[str, Any]:
    """Run the offline Line B association fixture and optionally persist it."""
    from .baseline_attribution import (
        attribute_baseline,
        change_registry_entry,
        external_event_entry,
        simulate_panel,
    )

    panel = simulate_panel()
    registry = [
        change_registry_entry(
            "chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"
        ),
        change_registry_entry(
            "chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"
        ),
    ]
    external = [
        external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")
    ]
    baseline = attribute_baseline(
        panel["days"],
        panel["control"],
        panel["treated"],
        registry,
        external,
        panel["experiments"],
    )
    windows = [
        {
            "start_day": max(panel["days"][0], alert["onset_day"] - 2),
            "end_day": min(panel["days"][-1], alert["onset_day"] + 2),
        }
        for alert in baseline["unregistered_alerts"]
    ]
    events = [
        {
            "factor_id": "internal.audit.unregistered_release",
            "source_type": "internal_event",
            "kind": "release_audit",
            "start_day": 40,
            "end_day": 40,
            "scope_match": 0.85,
            "source_reliability": 0.90,
        },
        {
            "factor_id": "external.competitor_campaign",
            "source_type": "external_event",
            "kind": "competitor_marketing",
            "start_day": 51,
            "end_day": 54,
            "scope_match": 0.60,
            "source_reliability": 0.65,
        },
    ]
    result = discover_association_factors(
        panel["days"],
        baseline["series"]["residual"],
        windows,
        events=events,
        factor_series=[
            {
                "factor_id": "external.fx_rate_usd_cny",
                "source_type": "factor_series",
                "kind": "macro",
                "days": panel["days"],
                "values": [1.0 + (0.02 if day >= 50 else 0.0) for day in panel["days"]],
                "scope_match": 0.45,
                "source_reliability": 0.70,
            }
        ],
    )
    result["input_policy"] = (
        "fixture feeds demonstrate the adapter contract; production requires "
        "authorized sources with scope and provenance."
    )
    if output_path is not None:
        import json
        from pathlib import Path

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result["output_path"] = str(path)
    return result


if __name__ == "__main__":
    from pathlib import Path

    output = (
        Path(__file__).resolve().parent.parent
        / "outputs"
        / "lineB_association_discovery.json"
    )
    print(run_demo(output))
