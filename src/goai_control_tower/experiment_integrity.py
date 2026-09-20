"""Fail-closed experiment integrity checks at the correct evidence unit.

Assignment checks such as SRM and allocation stability operate on unique
randomization units; exposure, funnel and temporal checks retain row-level
evidence. A metadata assertion such as ``assignment_verified=True`` is never
accepted as a substitute for the realized checks below.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

CHECK_NAMES = (
    "srm",
    "pre_treatment_balance",
    "allocation_stability",
    "contamination",
    "temporal_ordering",
    "sample_funnel",
    "cluster_integrity",
    "concurrent_experiments",
)


def _failure(reason: str, **details: Any) -> dict[str, Any]:
    return {"status": "FAIL", "passed": False, "reason_code": reason, **details}


def _success(reason: str, **details: Any) -> dict[str, Any]:
    return {"status": "PASS", "passed": True, "reason_code": reason, **details}


def _missing_columns(
    rows: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> list[str]:
    available = set().union(*(row.keys() for row in rows)) if rows else set()
    return sorted(set(columns) - available)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _missing_value_counts(
    rows: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> dict[str, int]:
    return {
        column: sum(
            1 for row in rows if column not in row or _is_missing(row.get(column))
        )
        for column in columns
        if any(column not in row or _is_missing(row.get(column)) for row in rows)
    }


def _binary_flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number) and number in {0.0, 1.0}:
            return bool(number)
    return None


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rows_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    canonical_rows = sorted(
        json.dumps(
            dict(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        for row in rows
    )
    return _canonical_digest(canonical_rows)


def _arm(value: Any) -> str:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _expected_allocation(metadata: Mapping[str, Any]) -> dict[str, float]:
    configured = metadata.get("expected_allocation")
    if isinstance(configured, Mapping) and configured:
        result = {_arm(key): float(value) for key, value in configured.items()}
    else:
        result = {
            _arm(metadata.get("control_group", 0)): 0.5,
            _arm(metadata.get("treatment_group", 1)): 0.5,
        }
    total = sum(result.values())
    if (
        len(result) < 2
        or not math.isfinite(total)
        or total <= 0
        or any(not math.isfinite(value) or value <= 0 for value in result.values())
    ):
        raise ValueError("expected_allocation must contain positive finite arm shares")
    return {key: value / total for key, value in result.items()}


def _srm_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    unit_column = str(metadata.get("randomization_unit") or "")
    missing = _missing_columns(rows, [column, unit_column] if unit_column else [column])
    if missing or not unit_column:
        return _failure("SRM_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(rows, [column, unit_column])
    if missing_values:
        return _failure("SRM_NOT_EVALUABLE", missing_value_counts=missing_values)
    expected = _expected_allocation(metadata)
    observed = {arm: 0 for arm in expected}
    unexpected: dict[str, int] = defaultdict(int)
    unit_arms: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        unit_arms[str(row.get(unit_column, ""))].add(_arm(row.get(column)))
    inconsistent_units = sorted(
        unit for unit, arms in unit_arms.items() if len(arms) != 1
    )
    if inconsistent_units:
        return _failure(
            "SRM_INCONSISTENT_UNIT_ASSIGNMENT",
            randomization_unit=unit_column,
            inconsistent_units=inconsistent_units,
        )
    for arms in unit_arms.values():
        arm = next(iter(arms))
        if arm in observed:
            observed[arm] += 1
        else:
            unexpected[arm] += 1
    n = sum(observed.values())
    if n == 0 or unexpected:
        return _failure(
            "SRM_UNEXPECTED_ARM",
            observed=observed,
            unexpected_arms=dict(unexpected),
        )
    expected_counts = {arm: n * share for arm, share in expected.items()}
    statistic = sum(
        (observed[arm] - expected_counts[arm]) ** 2 / expected_counts[arm]
        for arm in expected
    )
    # Exact chi-square survival function for the supported two-arm, df=1 case.
    if len(expected) != 2:
        return _failure(
            "SRM_NOT_EVALUABLE",
            reason="only two-arm SRM is currently supported",
            observed=observed,
        )
    p_value = math.erfc(math.sqrt(statistic / 2.0))
    alpha = float(metadata.get("srm_alpha", 0.001))
    passed = p_value >= alpha
    result = {
        "counting_unit": "randomization_unit",
        "randomization_unit": unit_column,
        "raw_row_count": len(rows),
        "randomization_unit_count": len(unit_arms),
        "observed": observed,
        "expected_counts": expected_counts,
        "chi_square": statistic,
        "degrees_of_freedom": 1,
        "p_value": p_value,
        "alpha": alpha,
    }
    return (
        _success("SRM_PASS", **result) if passed else _failure("SRM_DETECTED", **result)
    )


def _numeric(values: Sequence[Any]) -> list[float] | None:
    converted: list[float] = []
    try:
        for value in values:
            number = float(value)
            if not math.isfinite(number):
                return None
            converted.append(number)
    except (TypeError, ValueError):
        return None
    return converted


def _sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _balance_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    arm_column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    unit_column = str(metadata.get("randomization_unit") or "")
    covariates = [str(value) for value in metadata.get("baseline_covariates", [])]
    if not covariates:
        return _failure(
            "BALANCE_NOT_EVALUABLE", missing_configuration=["baseline_covariates"]
        )
    missing = _missing_columns(rows, [arm_column, unit_column, *covariates])
    if missing or not unit_column:
        return _failure("BALANCE_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(rows, [arm_column, unit_column, *covariates])
    if missing_values:
        return _failure("BALANCE_NOT_EVALUABLE", missing_value_counts=missing_values)
    expected = list(_expected_allocation(metadata))
    control_arm, treatment_arm = expected[0], expected[1]
    threshold = float(metadata.get("balance_smd_threshold", 0.10))
    proportion_threshold = float(
        metadata.get("balance_proportion_difference_threshold", 0.10)
    )
    diagnostics: dict[str, Any] = {}
    failures: list[str] = []
    unit_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        unit_rows[str(row[unit_column])].append(row)
    inconsistent_assignments: list[str] = []
    inconsistent_covariates: dict[str, list[str]] = defaultdict(list)
    unit_records: list[dict[str, Any]] = []
    for unit, observations in unit_rows.items():
        arms = {_arm(row[arm_column]) for row in observations}
        if len(arms) != 1:
            inconsistent_assignments.append(unit)
            continue
        record: dict[str, Any] = {arm_column: next(iter(arms))}
        for covariate in covariates:
            values = {
                json.dumps(
                    row[covariate],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                for row in observations
            }
            if len(values) != 1:
                inconsistent_covariates[covariate].append(unit)
            else:
                record[covariate] = observations[0][covariate]
        unit_records.append(record)
    if inconsistent_assignments or inconsistent_covariates:
        return _failure(
            "BALANCE_INCONSISTENT_RANDOMIZATION_UNIT",
            randomization_unit=unit_column,
            inconsistent_assignment_units=sorted(inconsistent_assignments),
            inconsistent_covariate_units={
                key: sorted(value) for key, value in inconsistent_covariates.items()
            },
        )
    for covariate in covariates:
        by_arm = {
            arm: [
                row[covariate] for row in unit_records if _arm(row[arm_column]) == arm
            ]
            for arm in (control_arm, treatment_arm)
        }
        numeric = {arm: _numeric(values) for arm, values in by_arm.items()}
        if any(len(values) < 2 for values in by_arm.values()):
            failures.append(covariate)
            diagnostics[covariate] = {"status": "NOT_EVALUABLE_TOO_FEW_ROWS"}
            continue
        if any(values is None for values in numeric.values()):
            categories = sorted(
                {_arm(value) for values in by_arm.values() for value in values}
            )
            differences = {
                category: (
                    sum(_arm(value) == category for value in by_arm[treatment_arm])
                    / len(by_arm[treatment_arm])
                    - sum(_arm(value) == category for value in by_arm[control_arm])
                    / len(by_arm[control_arm])
                )
                for category in categories
            }
            max_difference = max(
                (abs(value) for value in differences.values()), default=0.0
            )
            passed = max_difference <= proportion_threshold
            diagnostics[covariate] = {
                "type": "categorical",
                "category_proportion_differences": differences,
                "max_absolute_proportion_difference": max_difference,
                "threshold": proportion_threshold,
                "passed": passed,
            }
            if not passed:
                failures.append(covariate)
            continue
        control = numeric[control_arm] or []
        treatment = numeric[treatment_arm] or []
        mean_control = sum(control) / len(control)
        mean_treatment = sum(treatment) / len(treatment)
        pooled_sd = math.sqrt(
            max((_sample_variance(control) + _sample_variance(treatment)) / 2.0, 0.0)
        )
        smd = (
            (mean_treatment - mean_control) / pooled_sd
            if pooled_sd > 1e-12
            else 0.0
            if abs(mean_treatment - mean_control) <= 1e-12
            else math.inf
        )
        diagnostics[covariate] = {
            "type": "numeric",
            "control_mean": mean_control,
            "treatment_mean": mean_treatment,
            "standardized_mean_difference": smd,
            "passed": abs(smd) <= threshold,
        }
        if abs(smd) > threshold:
            failures.append(covariate)
    details = {
        "counting_unit": "randomization_unit",
        "randomization_unit": unit_column,
        "raw_row_count": len(rows),
        "randomization_unit_count": len(unit_rows),
        "threshold_absolute_smd": threshold,
        "threshold_categorical_proportion_difference": proportion_threshold,
        "covariates": diagnostics,
        "failed_covariates": failures,
    }
    return (
        _success("PRE_TREATMENT_BALANCE_PASS", **details)
        if not failures
        else _failure("PRE_TREATMENT_IMBALANCE", **details)
    )


def _allocation_stability_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    arm_column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    unit_column = str(metadata.get("randomization_unit") or "")
    period_column = str(metadata.get("assignment_period_column") or "assignment_period")
    missing = _missing_columns(rows, [arm_column, unit_column, period_column])
    if missing or not unit_column:
        return _failure("ALLOCATION_STABILITY_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(
        rows, [arm_column, unit_column, period_column]
    )
    if missing_values:
        return _failure(
            "ALLOCATION_STABILITY_NOT_EVALUABLE",
            missing_value_counts=missing_values,
        )
    assignments: dict[str, set[str]] = defaultdict(set)
    assignment_periods: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        unit = str(row.get(unit_column))
        arm = _arm(row.get(arm_column))
        assignments[unit].add(arm)
        assignment_periods[unit].add(str(row.get(period_column)))
    reassigned_units = sorted(
        unit for unit, arms in assignments.items() if len(arms) > 1
    )
    multi_period_units = sorted(
        unit
        for unit, unit_periods in assignment_periods.items()
        if len(unit_periods) > 1
    )
    periods: dict[str, list[str]] = defaultdict(list)
    for unit, arms in assignments.items():
        if len(arms) == 1 and len(assignment_periods[unit]) == 1:
            period = next(iter(assignment_periods[unit]))
            periods[period].append(next(iter(arms)))
    expected = _expected_allocation(metadata)
    configured_tolerance = float(metadata.get("allocation_stability_tolerance", 0.10))
    minimum_period_size = int(metadata.get("allocation_stability_min_period_size", 30))
    period_diagnostics: dict[str, Any] = {}
    unstable_periods: list[str] = []
    for period, arms in sorted(periods.items()):
        n = len(arms)
        counts = {arm: arms.count(arm) for arm in expected}
        deviations = {
            arm: abs(counts[arm] / n - share) for arm, share in expected.items()
        }
        enough_rows = n >= minimum_period_size
        sampling_tolerance = max(
            4.0 * math.sqrt(share * (1.0 - share) / n) for share in expected.values()
        )
        tolerance = max(configured_tolerance, sampling_tolerance)
        passed = enough_rows and max(deviations.values()) <= tolerance
        period_diagnostics[period] = {
            "count": n,
            "counting_unit": "randomization_unit",
            "arm_counts": counts,
            "max_share_deviation": max(deviations.values()),
            "tolerance": tolerance,
            "minimum_period_size": minimum_period_size,
            "enough_rows": enough_rows,
            "passed": passed,
        }
        if not passed:
            unstable_periods.append(period)
    details = {
        "counting_unit": "randomization_unit",
        "randomization_unit": unit_column,
        "raw_row_count": len(rows),
        "randomization_unit_count": len(assignments),
        "periods": period_diagnostics,
        "reassigned_units": reassigned_units,
        "units_with_multiple_assignment_periods": multi_period_units,
        "unstable_periods": unstable_periods,
    }
    return (
        _success("ALLOCATION_STABILITY_PASS", **details)
        if not reassigned_units and not multi_period_units and not unstable_periods
        else _failure("ALLOCATION_INSTABILITY", **details)
    )


def _contamination_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    assigned_column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    exposed_column = str(metadata.get("exposed_arm_column") or "exposed_treatment")
    exposure_column = str(metadata.get("exposure_column") or "exposed")
    missing = _missing_columns(rows, [assigned_column, exposed_column, exposure_column])
    if missing:
        return _failure("CONTAMINATION_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(rows, [assigned_column, exposed_column])
    invalid_flags = sum(_binary_flag(row.get(exposure_column)) is None for row in rows)
    if missing_values or invalid_flags:
        return _failure(
            "CONTAMINATION_NOT_EVALUABLE",
            missing_value_counts=missing_values,
            invalid_binary_value_counts={exposure_column: invalid_flags}
            if invalid_flags
            else {},
        )
    exposed_rows = [row for row in rows if _binary_flag(row.get(exposure_column))]
    contaminated = [
        row
        for row in exposed_rows
        if _arm(row.get(assigned_column)) != _arm(row.get(exposed_column))
    ]
    rate = len(contaminated) / len(exposed_rows) if exposed_rows else 1.0
    threshold = float(metadata.get("max_contamination_rate", 0.001))
    details = {
        "exposed_count": len(exposed_rows),
        "contaminated_count": len(contaminated),
        "contamination_rate": rate,
        "threshold": threshold,
    }
    return (
        _success("NO_MATERIAL_CROSS_ARM_CONTAMINATION", **details)
        if exposed_rows and rate <= threshold
        else _failure("CROSS_ARM_CONTAMINATION", **details)
    )


def _time_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return None
    return None


def _temporal_ordering_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    assigned_at = str(metadata.get("assigned_at_column") or "assigned_at")
    exposed_at = str(metadata.get("exposed_at_column") or "exposed_at")
    outcome_at = str(metadata.get("outcome_at_column") or "outcome_observed_at")
    missing = _missing_columns(rows, [assigned_at, exposed_at, outcome_at])
    if missing:
        return _failure("TEMPORAL_ORDER_NOT_EVALUABLE", missing_columns=missing)
    invalid = 0
    violations = 0
    for row in rows:
        times = tuple(
            _time_value(row.get(column))
            for column in (assigned_at, exposed_at, outcome_at)
        )
        if any(value is None for value in times):
            invalid += 1
        elif not (times[0] <= times[1] <= times[2]):  # type: ignore[operator]
            violations += 1
    details = {
        "row_count": len(rows),
        "invalid_timestamp_count": invalid,
        "ordering_violation_count": violations,
        "required_order": "assignment <= exposure <= outcome",
    }
    return (
        _success("TEMPORAL_ORDER_PASS", **details)
        if rows and invalid == 0 and violations == 0
        else _failure("TEMPORAL_ORDER_VIOLATION", **details)
    )


def _sample_funnel_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    arm_column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    exposure_column = str(metadata.get("exposure_column") or "exposed")
    triggered_column = str(metadata.get("triggered_column") or "triggered")
    outcome_column = str(metadata.get("outcome_observed_column") or "outcome_observed")
    missing = _missing_columns(
        rows, [arm_column, exposure_column, triggered_column, outcome_column]
    )
    if missing:
        return _failure("SAMPLE_FUNNEL_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(rows, [arm_column])
    flag_columns = [exposure_column, triggered_column, outcome_column]
    invalid_flags = {
        column: sum(_binary_flag(row.get(column)) is None for row in rows)
        for column in flag_columns
    }
    invalid_flags = {key: value for key, value in invalid_flags.items() if value}
    if missing_values or invalid_flags:
        return _failure(
            "SAMPLE_FUNNEL_NOT_EVALUABLE",
            missing_value_counts=missing_values,
            invalid_binary_value_counts=invalid_flags,
        )
    expected = _expected_allocation(metadata)
    funnel: dict[str, Any] = {}
    valid = True
    exposure_rates: list[float] = []
    outcome_rates: list[float] = []
    for arm in expected:
        group = [row for row in rows if _arm(row.get(arm_column)) == arm]
        assigned = len(group)
        exposed = sum(_binary_flag(row.get(exposure_column)) is True for row in group)
        triggered = sum(
            _binary_flag(row.get(triggered_column)) is True for row in group
        )
        outcomes = sum(_binary_flag(row.get(outcome_column)) is True for row in group)
        monotone = assigned >= exposed >= triggered and assigned >= outcomes
        valid = valid and assigned > 0 and monotone
        exposure_rate = exposed / assigned if assigned else 0.0
        outcome_rate = outcomes / assigned if assigned else 0.0
        exposure_rates.append(exposure_rate)
        outcome_rates.append(outcome_rate)
        funnel[arm] = {
            "assigned": assigned,
            "exposed": exposed,
            "triggered": triggered,
            "outcome_observed": outcomes,
            "exposure_rate": exposure_rate,
            "outcome_observation_rate": outcome_rate,
            "monotone": monotone,
        }
    max_rate_difference = float(metadata.get("max_funnel_rate_difference", 0.05))
    exposure_difference = max(exposure_rates) - min(exposure_rates)
    outcome_difference = max(outcome_rates) - min(outcome_rates)
    passed = (
        valid
        and exposure_difference <= max_rate_difference
        and outcome_difference <= max_rate_difference
    )
    details = {
        "arms": funnel,
        "exposure_rate_difference": exposure_difference,
        "outcome_observation_rate_difference": outcome_difference,
        "max_rate_difference": max_rate_difference,
    }
    return (
        _success("SAMPLE_FUNNEL_PASS", **details)
        if passed
        else _failure("DIFFERENTIAL_SAMPLE_ATTRITION", **details)
    )


def _cluster_integrity_check(
    rows: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    arm_column = str(metadata.get("assigned_arm_column") or "assigned_treatment")
    unit_column = str(metadata.get("randomization_unit") or "")
    analysis_unit = str(metric_contract.get("identity") or "")
    assignment_method = str(metadata.get("assignment_method") or "")
    cluster_column = str(metadata.get("cluster_column") or "")
    required = [arm_column, unit_column]
    if assignment_method == "cluster_randomized":
        required.append(cluster_column)
    missing = _missing_columns(rows, required)
    if missing or not unit_column or not analysis_unit:
        return _failure("CLUSTER_INTEGRITY_NOT_EVALUABLE", missing_columns=missing)
    missing_values = _missing_value_counts(rows, required)
    if missing_values:
        return _failure(
            "CLUSTER_INTEGRITY_NOT_EVALUABLE", missing_value_counts=missing_values
        )
    unit_arms: dict[str, set[str]] = defaultdict(set)
    cluster_arms: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        arm = _arm(row.get(arm_column))
        unit_arms[str(row.get(unit_column))].add(arm)
        if cluster_column:
            cluster_arms[str(row.get(cluster_column))].add(arm)
    inconsistent_units = sorted(
        unit for unit, arms in unit_arms.items() if len(arms) > 1
    )
    inconsistent_clusters = sorted(
        cluster for cluster, arms in cluster_arms.items() if len(arms) > 1
    )
    raw_estimand = str(
        metadata.get("primary_estimand")
        or metric_contract.get("primary_estimand")
        or "user_level"
    )
    estimand = raw_estimand.strip().lower().replace("-", "_").replace(" ", "_")
    automatic_methods = {
        "user": "aggregate_to_analysis_unit",
        "user_level": "aggregate_to_analysis_unit",
        "user_level_itt": "aggregate_to_analysis_unit",
        "exposure": "cluster_robust_se",
        "exposure_level": "cluster_robust_se",
        "triggered": "aggregate_to_analysis_unit",
        "triggered_user": "aggregate_to_analysis_unit",
    }
    analysis_method = automatic_methods.get(estimand)
    clustering_required = assignment_method == "cluster_randomized" or (
        unit_column != analysis_unit
    )
    cluster_adjustment_present = bool(
        metadata.get("analysis_accounts_for_clustering") is True or analysis_method
    )
    unit_matches = unit_column == analysis_unit or cluster_adjustment_present
    passed = (
        not inconsistent_units
        and not inconsistent_clusters
        and unit_matches
        and (not clustering_required or cluster_adjustment_present)
    )
    details = {
        "randomization_unit": unit_column,
        "analysis_unit": analysis_unit,
        "assignment_method": assignment_method,
        "cluster_column": cluster_column or None,
        "inconsistent_units": inconsistent_units,
        "inconsistent_clusters": inconsistent_clusters,
        "analysis_accounts_for_clustering": cluster_adjustment_present,
        "analysis_method": analysis_method,
        "primary_estimand": estimand,
    }
    return (
        _success("CLUSTER_INTEGRITY_PASS", **details)
        if passed
        else _failure("CLUSTER_RANDOMIZATION_MISMATCH", **details)
    )


def _concurrent_experiment_check(
    rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    column = str(
        metadata.get("concurrent_experiments_column") or "concurrent_experiment_ids"
    )
    missing = _missing_columns(rows, [column])
    if missing:
        return _failure("CONCURRENT_EXPERIMENTS_NOT_EVALUABLE", missing_columns=missing)
    active: set[str] = set()
    for row in rows:
        value = row.get(column)
        if value in (None, "", []):
            continue
        if isinstance(value, (list, tuple, set)):
            active.update(str(item) for item in value if str(item))
        else:
            active.add(str(value))
    current = str(metadata.get("experiment_id") or "")
    active.discard(current)
    compatible = {
        str(value) for value in metadata.get("compatible_concurrent_experiments", [])
    }
    conflicts = sorted(active - compatible)
    details = {
        "active_concurrent_experiments": sorted(active),
        "compatible_concurrent_experiments": sorted(compatible),
        "conflicting_concurrent_experiments": conflicts,
    }
    return (
        _success("NO_CONCURRENT_EXPERIMENT_CONFLICT", **details)
        if not conflicts
        else _failure("CONCURRENT_EXPERIMENT_CONFLICT", **details)
    )


def experiment_integrity_report(
    rows: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Run all realized-randomization checks and return one auditable report."""
    if not rows:
        checks = {name: _failure("NO_EXPERIMENT_ROWS") for name in CHECK_NAMES}
    else:
        checks = {
            "srm": _srm_check(rows, experiment_metadata),
            "pre_treatment_balance": _balance_check(rows, experiment_metadata),
            "allocation_stability": _allocation_stability_check(
                rows, experiment_metadata
            ),
            "contamination": _contamination_check(rows, experiment_metadata),
            "temporal_ordering": _temporal_ordering_check(rows, experiment_metadata),
            "sample_funnel": _sample_funnel_check(rows, experiment_metadata),
            "cluster_integrity": _cluster_integrity_check(
                rows, metric_contract, experiment_metadata
            ),
            "concurrent_experiments": _concurrent_experiment_check(
                rows, experiment_metadata
            ),
        }
    failed = [name for name, check in checks.items() if not check["passed"]]
    passed = not failed
    return {
        "schema_version": "1.0",
        "gate": "EXPERIMENT_INTEGRITY_GATE",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "causal_estimators_allowed": passed,
        "failed_checks": failed,
        "reason_codes": [checks[name]["reason_code"] for name in failed],
        "checks": checks,
        "input_fingerprints": {
            "rows_sha256": _rows_digest(rows),
            "metric_contract_sha256": _canonical_digest(dict(metric_contract)),
            "experiment_metadata_sha256": _canonical_digest(dict(experiment_metadata)),
        },
    }


def require_integrity_pass(
    report: Mapping[str, Any] | None,
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    metric_contract: Mapping[str, Any] | None = None,
    experiment_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Refuse causal estimation unless a complete generated report passed."""
    if not report:
        raise PermissionError(
            "causal estimation requires an Experiment Integrity Report"
        )
    checks = report.get("checks")
    complete = isinstance(checks, Mapping) and set(CHECK_NAMES).issubset(checks)
    checks_pass = complete and all(
        isinstance(checks[name], Mapping) and checks[name].get("passed") is True
        for name in CHECK_NAMES
    )
    if (
        report.get("gate") != "EXPERIMENT_INTEGRITY_GATE"
        or report.get("passed") is not True
        or report.get("causal_estimators_allowed") is not True
        or not checks_pass
    ):
        failed = report.get("failed_checks", [])
        raise PermissionError(f"Experiment Integrity Gate did not pass: {failed}")
    fingerprints = report.get("input_fingerprints")
    if not isinstance(fingerprints, Mapping):
        raise PermissionError("Experiment Integrity Report has no input fingerprints")
    expected = {
        "rows_sha256": _rows_digest(rows) if rows is not None else None,
        "metric_contract_sha256": _canonical_digest(dict(metric_contract))
        if metric_contract is not None
        else None,
        "experiment_metadata_sha256": _canonical_digest(dict(experiment_metadata))
        if experiment_metadata is not None
        else None,
    }
    mismatches = [
        name
        for name, digest in expected.items()
        if digest is not None and fingerprints.get(name) != digest
    ]
    if mismatches:
        raise PermissionError(
            "Experiment Integrity Report input mismatch: " + ", ".join(mismatches)
        )
