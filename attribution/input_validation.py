"""Shared fail-fast contracts for statistical entry points."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def validation_report(
    component: str,
    used_sample_count: int,
    *,
    excluded_sample_count: int = 0,
    exclusion_reasons: Sequence[str] = (),
    checks: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "status": "PASS",
        "component": component,
        "used_sample_count": int(used_sample_count),
        "excluded_sample_count": int(excluded_sample_count),
        "exclusion_reasons": list(exclusion_reasons),
        "checks_performed": list(checks),
    }


def validate_binomial_arm(arm: Mapping[str, Any], label: str) -> dict[str, float]:
    if not isinstance(arm, Mapping):
        raise TypeError(f"{label} must be a mapping")
    if "clicks" not in arm or "impressions" not in arm:
        raise ValueError(f"{label} requires clicks and impressions")
    clicks = _finite_number(arm["clicks"], f"{label}.clicks")
    impressions = _finite_number(arm["impressions"], f"{label}.impressions")
    if not clicks.is_integer() or not impressions.is_integer():
        raise ValueError(
            f"{label} clicks and impressions must be integer-valued counts"
        )
    if impressions < 0 or clicks < 0 or clicks > impressions:
        raise ValueError(f"{label} requires 0 <= clicks <= impressions")
    return {"clicks": clicks, "impressions": impressions}


def validate_hte_segments(
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not segments:
        raise ValueError("segments must be non-empty")
    identifiers: list[str] = []
    used = 0
    for index, segment in enumerate(segments):
        if "segment_id" not in segment:
            raise ValueError(f"segments[{index}] requires segment_id")
        identifier = str(segment["segment_id"])
        if not identifier:
            raise ValueError(f"segments[{index}].segment_id must be non-empty")
        identifiers.append(identifier)
        control = validate_binomial_arm(
            segment.get("control", {}), f"{identifier}.control"
        )
        treatment = validate_binomial_arm(
            segment.get("treatment", {}), f"{identifier}.treatment"
        )
        used += int(control["impressions"] + treatment["impressions"])
    duplicates = sorted(
        {value for value in identifiers if identifiers.count(value) > 1}
    )
    if duplicates:
        raise ValueError(f"segment_id must be unique; duplicates={duplicates}")
    return validation_report(
        "hte_segments",
        used,
        checks=("finite", "count_range", "non_empty", "unique_segment_id"),
    )


def validate_ordered_series(
    days: Sequence[Any],
    *series: Sequence[Any],
    component: str = "time_series",
) -> dict[str, Any]:
    if not days:
        raise ValueError("days must be non-empty")
    parsed_days = [
        _finite_number(value, f"days[{index}]") for index, value in enumerate(days)
    ]
    if any(not value.is_integer() for value in parsed_days):
        raise ValueError("days must be integer-valued")
    if len(set(parsed_days)) != len(parsed_days):
        raise ValueError("days must be unique")
    if any(right <= left for left, right in pairwise(parsed_days)):
        raise ValueError("days must be strictly increasing")
    for series_index, values in enumerate(series):
        if len(values) != len(days):
            raise ValueError("days and all statistical series must have equal length")
        for value_index, value in enumerate(values):
            _finite_number(value, f"series[{series_index}][{value_index}]")
    return validation_report(
        component,
        len(days),
        checks=("finite", "equal_length", "unique_days", "strictly_increasing_days"),
    )


def validate_discovery_holdout(
    all_days: Sequence[int],
    discovery_days: Sequence[int],
    holdout_days: Sequence[int],
) -> None:
    all_set = set(all_days)
    discovery = list(discovery_days)
    holdout = list(holdout_days)
    if not set(discovery).issubset(all_set) or not set(holdout).issubset(all_set):
        raise ValueError("discovery/holdout days must be contained in days")
    if set(discovery) & set(holdout):
        raise ValueError("discovery_days and holdout_days must be disjoint")
    if holdout and discovery and max(discovery) >= min(holdout):
        raise ValueError("holdout window must occur strictly after discovery window")


def validate_windows(
    baseline_window: tuple[int, int], current_window: tuple[int, int]
) -> None:
    if len(baseline_window) != 2 or len(current_window) != 2:
        raise ValueError("windows must contain exactly (start, end)")
    if baseline_window[0] > baseline_window[1] or current_window[0] > current_window[1]:
        raise ValueError("window start must be <= end")
    if baseline_window[1] >= current_window[0]:
        raise ValueError(
            "baseline and current windows must be ordered and non-overlapping"
        )


def validate_rate_panel(
    panel: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
    baseline_days: set[int],
    current_days: set[int],
) -> dict[str, Any]:
    if not panel:
        raise ValueError("panel must be non-empty")
    if not dimensions or len(set(dimensions)) != len(dimensions):
        raise ValueError("dimensions must be non-empty and unique")
    signatures: set[tuple[Any, ...]] = set()
    universe = {"baseline": set(), "current": set()}
    used = 0
    for index, row in enumerate(panel):
        day_value = _finite_number(row.get("day"), f"panel[{index}].day")
        if not day_value.is_integer():
            raise ValueError(f"panel[{index}].day must be integer-valued")
        day = int(day_value)
        scope = row.get("scope")
        if not isinstance(scope, Mapping):
            raise TypeError(f"panel[{index}].scope must be a mapping")
        cell = tuple(
            (dimension, str(scope.get(dimension, "<missing>")))
            for dimension in dimensions
        )
        signature = (day, *cell)
        if signature in signatures:
            raise ValueError(f"duplicate day/cell row: {signature}")
        signatures.add(signature)
        for arm in ("control", "treatment"):
            counts = validate_binomial_arm(row.get(arm, {}), f"panel[{index}].{arm}")
            used += int(counts["impressions"])
        if day in baseline_days:
            universe["baseline"].add(cell)
        if day in current_days:
            universe["current"].add(cell)
    if universe["baseline"] != universe["current"]:
        missing_current = sorted(map(str, universe["baseline"] - universe["current"]))
        missing_baseline = sorted(map(str, universe["current"] - universe["baseline"]))
        raise ValueError(
            "baseline/current cell universe mismatch; "
            f"missing_current={missing_current}, missing_baseline={missing_baseline}"
        )
    return validation_report(
        "rate_panel",
        used,
        checks=(
            "finite",
            "count_range",
            "unique_day_cell",
            "ordered_non_overlapping_windows",
            "common_cell_universe",
        ),
    )


def validate_experiment_estimates(
    experiments: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    for experiment_id, estimate in experiments.items():
        _finite_number(estimate.get("att_estimate"), f"{experiment_id}.att_estimate")
        standard_error = _finite_number(
            estimate.get("att_se"), f"{experiment_id}.att_se"
        )
        if standard_error <= 0:
            raise ValueError(f"{experiment_id}.att_se must be positive")
    return validation_report(
        "experiment_estimates",
        len(experiments),
        checks=("finite", "positive_standard_error", "unique_experiment_id"),
    )


__all__ = [
    "validate_binomial_arm",
    "validate_discovery_holdout",
    "validate_experiment_estimates",
    "validate_hte_segments",
    "validate_ordered_series",
    "validate_rate_panel",
    "validate_windows",
    "validation_report",
]
