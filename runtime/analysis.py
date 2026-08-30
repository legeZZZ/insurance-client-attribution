"""Deterministic feature extraction and causal-readiness skills for attribution."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from statistics import NormalDist
from typing import Any

from .experiment_integrity import experiment_integrity_report, require_integrity_pass

FUNNEL_FIELDS = ("active", "quoted", "applied", "paid", "issued")
RANDOMIZED_ASSIGNMENTS = {"randomized", "stratified_randomized", "cluster_randomized"}
REQUIRED_EXPERIMENT_FIELDS = (
    "experiment_id",
    "activity_config",
    "assignment_method",
    "assignment_provenance",
    "assignment_verified",
    "treatment_column",
    "control_group",
    "treatment_group",
    "window_closed",
    "outcome_complete",
)

ESTIMAND_ALIASES = {
    "user": "user_level",
    "user_level": "user_level",
    "user_level_itt": "user_level",
    "exposure": "exposure_level",
    "exposure_level": "exposure_level",
    "triggered": "triggered_user",
    "triggered_user": "triggered_user",
}


def _primary_estimand(
    metric_contract: Mapping[str, Any], experiment_metadata: Mapping[str, Any]
) -> str:
    raw = str(
        experiment_metadata.get("primary_estimand")
        or metric_contract.get("primary_estimand")
        or "user_level"
    )
    normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in ESTIMAND_ALIASES:
        raise ValueError(
            "primary_estimand must be user_level, exposure_level, or triggered_user"
        )
    return ESTIMAND_ALIASES[normalized]


def _outcome_aggregation(
    outcome: str,
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
) -> str:
    configured = {
        **dict(metric_contract.get("outcome_aggregations", {})),
        **dict(experiment_metadata.get("outcome_aggregations", {})),
    }
    method = str(
        configured.get(
            outcome,
            "max" if outcome in {"issued", "converted", "conversion"} else "sum",
        )
    ).lower()
    if method not in {"sum", "mean", "max", "min"}:
        raise ValueError(
            f"unsupported aggregation for {outcome}: use sum, mean, max, or min"
        )
    return method


def _aggregate_values(values: Sequence[float], method: str) -> float:
    if method == "sum":
        return sum(values)
    if method == "mean":
        return sum(values) / len(values)
    if method == "max":
        return max(values)
    return min(values)


def prepare_analysis_rows(
    rows: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
    outcomes: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the declared estimand sample without treating repeat rows as IID."""
    estimand = _primary_estimand(metric_contract, experiment_metadata)
    treatment_column = str(
        experiment_metadata.get("treatment_column")
        or metric_contract.get("treatment")
        or "treatment"
    )
    randomization_unit = str(experiment_metadata.get("randomization_unit") or "")
    if not randomization_unit:
        raise ValueError("randomization_unit is required for causal analysis")
    assignment_method = str(experiment_metadata.get("assignment_method") or "")
    cluster_column = str(experiment_metadata.get("cluster_column") or "")
    inference_unit = (
        cluster_column
        if assignment_method == "cluster_randomized" and cluster_column
        else randomization_unit
    )
    analysis_unit = str(
        experiment_metadata.get("analysis_unit")
        or (
            metric_contract.get("identity")
            if assignment_method == "cluster_randomized"
            else randomization_unit
        )
    )
    selected_outcomes = tuple(
        str(value)
        for value in (
            outcomes or metric_contract.get("outcomes", ("issued", "net_premium"))
        )
    )
    required = {
        treatment_column,
        randomization_unit,
        inference_unit,
        *selected_outcomes,
    }
    if estimand != "exposure_level":
        required.add(analysis_unit)
    available = set().union(*(set(row) for row in rows)) if rows else set()
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"analysis columns missing: {', '.join(missing)}")

    exposure_column = str(experiment_metadata.get("exposure_column") or "exposed")
    triggered_column = str(experiment_metadata.get("triggered_column") or "triggered")
    selected = list(rows)
    selection = "all assigned randomization units (ITT)"
    if estimand == "exposure_level":
        if exposure_column not in available:
            raise ValueError(f"analysis columns missing: {exposure_column}")
        selected = [row for row in rows if bool(row.get(exposure_column))]
        selection = "exposed observations only"
    elif estimand == "triggered_user":
        if triggered_column not in available:
            raise ValueError(f"analysis columns missing: {triggered_column}")
        selected = [row for row in rows if bool(row.get(triggered_column))]
        selection = "triggered users only (post-assignment conditional estimand)"
    if not selected:
        raise ValueError(f"{estimand} analysis has no eligible observations")

    unit_arms: dict[str, set[Any]] = defaultdict(set)
    for row in rows:
        unit_arms[str(row[randomization_unit])].add(row.get(treatment_column))
    if any(len(arms) != 1 for arms in unit_arms.values()):
        raise ValueError("randomization units have inconsistent treatment assignments")

    if estimand == "exposure_level":
        analysis_rows = [dict(row) for row in selected]
        aggregation = {outcome: "none" for outcome in selected_outcomes}
        estimator = "exposure-weighted difference in means"
    else:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in selected:
            grouped[str(row[analysis_unit])].append(row)
        analysis_rows = []
        aggregation = {
            outcome: _outcome_aggregation(outcome, metric_contract, experiment_metadata)
            for outcome in selected_outcomes
        }
        for unit, unit_rows in grouped.items():
            arms = {row.get(treatment_column) for row in unit_rows}
            clusters = {str(row.get(inference_unit)) for row in unit_rows}
            if len(arms) != 1 or len(clusters) != 1:
                raise ValueError(
                    "analysis units cross treatment arms or inference clusters"
                )
            aggregate = {
                key: value
                for key, value in unit_rows[0].items()
                if key not in selected_outcomes
                and all(row.get(key) == value for row in unit_rows[1:])
            }
            aggregate.update(
                {
                    analysis_unit: unit,
                    inference_unit: next(iter(clusters)),
                    treatment_column: next(iter(arms)),
                }
            )
            for outcome in selected_outcomes:
                try:
                    values = [float(row.get(outcome, 0.0) or 0.0) for row in unit_rows]
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{outcome} must contain numeric values") from exc
                if any(not math.isfinite(value) for value in values):
                    raise ValueError(f"{outcome} must contain finite values")
                aggregate[outcome] = _aggregate_values(values, aggregation[outcome])
            analysis_rows.append(aggregate)
        estimator = "equal-weighted analysis-unit difference in means"

    cluster_counts = Counter(str(row.get(inference_unit)) for row in analysis_rows)
    remaining_clustered_rows = sum(count - 1 for count in cluster_counts.values())
    randomization_unit_count = len(
        {str(row.get(randomization_unit)) for row in selected}
    )
    inference_method = (
        "cluster-robust SE (CR1)"
        if remaining_clustered_rows > 0 or estimand == "exposure_level"
        else "independent randomization-unit SE"
    )
    diagnostics = {
        "primary_estimand": estimand,
        "estimand_population": {
            "user_level": "all assigned users, equally weighted",
            "exposure_level": "qualified exposures, exposure weighted",
            "triggered_user": "users satisfying the post-assignment trigger, equally weighted",
        }[estimand],
        "is_itt": estimand == "user_level",
        "selection": selection,
        "raw_observation_count": len(rows),
        "eligible_observation_count": len(selected),
        "analysis_row_count": len(analysis_rows),
        "analysis_unit": "exposure" if estimand == "exposure_level" else analysis_unit,
        "randomization_unit": randomization_unit,
        "randomization_unit_count": randomization_unit_count,
        "inference_unit": inference_unit,
        "inference_cluster_count": len(cluster_counts),
        "repeated_observation_count": len(selected) - randomization_unit_count,
        "remaining_clustered_row_count": remaining_clustered_rows,
        "outcome_aggregations": aggregation,
        "estimator": estimator,
        "inference_method": inference_method,
    }
    return analysis_rows, diagnostics


def _rate(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def sanitize_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove evaluator-only fields before data reaches an Agent or UI."""
    return [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in rows
    ]


def aggregate_funnel(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    active = sum(int(row.get("active", 0) or 0) for row in rows)
    quoted = sum(int(row.get("quoted", 0) or 0) for row in rows)
    applied = sum(int(row.get("applied", 0) or 0) for row in rows)
    paid = sum(int(row.get("paid", 0) or 0) for row in rows)
    issued = sum(int(row.get("issued", 0) or 0) for row in rows)
    net_premium = round(
        sum(float(row.get("net_premium", 0.0) or 0.0) for row in rows), 2
    )
    return {
        "active": active,
        "quoted": quoted,
        "applied": applied,
        "paid": paid,
        "issued": issued,
        "net_premium": net_premium,
        "quote_rate": _rate(quoted, active),
        "apply_rate": _rate(applied, quoted),
        "paid_rate": _rate(paid, applied),
        "issue_rate": _rate(issued, paid),
        "issued_user_rate": _rate(issued, active),
        "avg_premium": round(net_premium / issued, 2) if issued else 0.0,
    }


def _distribution(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field, "<missing>")) for row in rows)
    return dict(sorted(counts.items()))


def _group_outcomes(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str,
    outcomes: Sequence[str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for arm in (0, 1):
        group = [row for row in rows if row.get(treatment_column) == arm]
        values: dict[str, float] = {"count": float(len(group))}
        for outcome in outcomes:
            values[outcome] = (
                round(
                    sum(float(row.get(outcome, 0.0) or 0.0) for row in group)
                    / len(group),
                    6,
                )
                if group
                else 0.0
            )
        result[str(arm)] = values
    return result


def extract_features(
    rows: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build auditable business, quality and experiment-design features."""
    identity = str(metric_contract.get("identity", "user_id"))
    treatment_column = str(
        experiment_metadata.get("treatment_column")
        or metric_contract.get("treatment")
        or "treatment"
    )
    outcomes = [
        str(value)
        for value in metric_contract.get("outcomes", ["issued", "net_premium"])
    ]
    required_row_fields = (
        set(FUNNEL_FIELDS) | {identity, treatment_column, "net_premium"} | set(outcomes)
    )
    available_fields = (
        set().union(*(set(row.keys()) for row in rows)) if rows else set()
    )
    missing_row_fields = sorted(required_row_fields - available_fields)
    null_counts = {
        field: sum(1 for row in rows if row.get(field) is None)
        for field in sorted(required_row_fields & available_fields)
    }
    identities = [row.get(identity) for row in rows if row.get(identity) is not None]
    duplicate_count = len(identities) - len(set(identities))
    missing_metadata = sorted(
        field
        for field in REQUIRED_EXPERIMENT_FIELDS
        if field not in experiment_metadata or experiment_metadata.get(field) is None
    )
    metrics = aggregate_funnel(rows)
    integrity = experiment_integrity_report(rows, metric_contract, experiment_metadata)
    try:
        analysis_rows, analysis = prepare_analysis_rows(
            rows, metric_contract, experiment_metadata, outcomes
        )
        analysis_error = None
    except (TypeError, ValueError) as exc:
        analysis_rows = []
        analysis = None
        analysis_error = str(exc)
    return {
        "schema_version": "1.0",
        "row_count": len(rows),
        "observation_unit": identity,
        "available_fields": sorted(available_fields),
        "funnel": metrics,
        "segments": {
            "channel_distribution": _distribution(rows, "channel"),
            "assignment_distribution": _distribution(rows, "assignment"),
            "average_product_mix": round(
                sum(float(row.get("product_mix", 0.0) or 0.0) for row in rows)
                / len(rows),
                6,
            )
            if rows
            else 0.0,
        },
        "treatment": {
            "column": treatment_column,
            "group_counts": _distribution(analysis_rows, treatment_column),
            "group_outcomes": _group_outcomes(
                analysis_rows, treatment_column, outcomes
            ),
        },
        "analysis": analysis,
        "data_quality": {
            "missing_row_fields": missing_row_fields,
            "missing_experiment_fields": missing_metadata,
            "null_counts": null_counts,
            "duplicate_count": duplicate_count,
            "duplicate_rate": round(duplicate_count / len(rows), 6) if rows else 0.0,
            "window_closed": experiment_metadata.get("window_closed"),
            "outcome_complete": experiment_metadata.get("outcome_complete"),
            "analysis_error": analysis_error,
        },
        "experiment_integrity": integrity,
    }


def _metric_contract_missing(metric_contract: Mapping[str, Any]) -> list[str]:
    required = (
        "metric_id",
        "version",
        "identity",
        "funnel",
        "outcomes",
        "treatment",
        "window",
        "owner",
    )
    return sorted(field for field in required if not metric_contract.get(field))


def _power_screen(
    features: Mapping[str, Any], experiment_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Plan/check power from the declared estimand without silent defaults."""
    treatment = features["treatment"]
    groups = treatment["group_outcomes"]
    control = groups.get("0", {})
    treatment_group = groups.get("1", {})
    baseline_rate = float(control.get("issued", 0.0))
    if not 0.0 < baseline_rate < 1.0:
        raise ValueError("binary power calculation requires baseline_rate in (0, 1)")
    try:
        mde = float(experiment_metadata["minimum_detectable_effect"])
        mde_type = str(experiment_metadata["minimum_detectable_effect_type"])
        alpha = float(experiment_metadata["alpha"])
        target_power = float(experiment_metadata["target_power"])
    except KeyError as exc:
        raise ValueError(
            f"power configuration missing required field: {exc.args[0]}"
        ) from exc
    if not math.isfinite(mde) or mde <= 0:
        raise ValueError("minimum_detectable_effect must be positive and finite")
    if mde_type == "absolute":
        absolute_mde = mde
    elif mde_type == "relative":
        absolute_mde = baseline_rate * mde
    else:
        raise ValueError(
            "minimum_detectable_effect_type must be 'absolute' or 'relative'"
        )
    if not 0.0 < absolute_mde < 1.0:
        raise ValueError("absolute MDE/margin must be in (0, 1)")
    if not math.isfinite(alpha) or not 0.0 < alpha < 0.5:
        raise ValueError("alpha must be finite and in (0, 0.5)")
    if not math.isfinite(target_power) or not 0.5 < target_power < 1.0:
        raise ValueError("target_power must be finite and in (0.5, 1)")

    design = str(experiment_metadata.get("power_design", "superiority"))
    sidedness = str(
        experiment_metadata.get(
            "test_sidedness", "two_sided" if design == "superiority" else "one_sided"
        )
    )
    if design not in {"superiority", "noninferiority", "equivalence"}:
        raise ValueError(
            "power_design must be superiority, noninferiority, or equivalence"
        )
    if sidedness not in {"one_sided", "two_sided"}:
        raise ValueError("test_sidedness must be one_sided or two_sided")
    if design in {"noninferiority", "equivalence"} and sidedness != "one_sided":
        raise ValueError(f"{design} planning requires one_sided component tests")
    assumed_effect = float(experiment_metadata.get("assumed_effect_absolute", 0.0))
    if not math.isfinite(assumed_effect):
        raise ValueError("assumed_effect_absolute must be finite")
    if design == "superiority":
        detectable_distance = absolute_mde
    elif design == "noninferiority":
        detectable_distance = absolute_mde + assumed_effect
    else:
        detectable_distance = absolute_mde - abs(assumed_effect)
    if detectable_distance <= 0:
        raise ValueError(
            "assumed effect must lie inside the declared noninferiority/equivalence margin"
        )

    configured_allocation = experiment_metadata.get(
        "expected_allocation", {"0": 0.5, "1": 0.5}
    )
    if not isinstance(configured_allocation, Mapping):
        raise TypeError("expected_allocation must map arm labels to positive shares")
    allocation = {
        str(key): float(value) for key, value in configured_allocation.items()
    }
    if set(allocation) != {"0", "1"} or any(
        not math.isfinite(value) or value <= 0 for value in allocation.values()
    ):
        raise ValueError("power calculation currently requires positive 0/1 allocation")
    allocation_total = sum(allocation.values())
    allocation = {key: value / allocation_total for key, value in allocation.items()}

    alpha_tail = alpha / 2.0 if sidedness == "two_sided" else alpha
    z_alpha = NormalDist().inv_cdf(1.0 - alpha_tail)
    z_power = NormalDist().inv_cdf(target_power)
    variance = baseline_rate * (1.0 - baseline_rate)
    required_analyzable_total = math.ceil(
        (z_alpha + z_power) ** 2
        * variance
        * (1.0 / allocation["0"] + 1.0 / allocation["1"])
        / detectable_distance**2
    )

    assignment_method = str(experiment_metadata.get("assignment_method") or "")
    if assignment_method == "cluster_randomized":
        if "cluster_average_size" not in experiment_metadata or (
            "intracluster_correlation" not in experiment_metadata
        ):
            raise ValueError(
                "cluster_randomized power requires cluster_average_size and "
                "intracluster_correlation"
            )
        cluster_size = float(experiment_metadata["cluster_average_size"])
        icc = float(experiment_metadata["intracluster_correlation"])
        if not math.isfinite(cluster_size) or cluster_size < 1:
            raise ValueError("cluster_average_size must be finite and >= 1")
        if not math.isfinite(icc) or not 0 <= icc < 1:
            raise ValueError("intracluster_correlation must be finite and in [0, 1)")
        design_effect = 1.0 + (cluster_size - 1.0) * icc
    else:
        cluster_size = 1.0
        icc = 0.0
        design_effect = 1.0

    attrition_config = experiment_metadata.get("expected_attrition_rate", 0.0)
    if isinstance(attrition_config, Mapping):
        attrition = {arm: float(attrition_config.get(arm, 0.0)) for arm in ("0", "1")}
    else:
        attrition = {"0": float(attrition_config), "1": float(attrition_config)}
    if any(
        not math.isfinite(value) or not 0 <= value < 1 for value in attrition.values()
    ):
        raise ValueError("expected_attrition_rate must be finite and in [0, 1)")
    required_by_arm = {
        arm: math.ceil(
            required_analyzable_total
            * allocation[arm]
            * design_effect
            / (1.0 - attrition[arm])
        )
        for arm in ("0", "1")
    }
    actual_by_arm = {
        "0": int(control.get("count", 0)),
        "1": int(treatment_group.get("count", 0)),
    }
    passed = all(actual_by_arm[arm] >= required_by_arm[arm] for arm in ("0", "1"))
    analysis = features.get("analysis") or {}
    eligible_observations = int(
        analysis.get("eligible_observation_count", features["row_count"])
    )
    return {
        "status": "PASS" if passed else "INSUFFICIENT_SAMPLE",
        "method": "two-arm binary normal approximation with explicit design contract",
        "power_design": design,
        "test_sidedness": sidedness,
        "alpha": alpha,
        "z_alpha": z_alpha,
        "target_power": target_power,
        "z_power": z_power,
        "minimum_detectable_effect": mde,
        "minimum_detectable_effect_type": mde_type,
        "absolute_effect_distance": absolute_mde,
        "detectable_distance_from_null_boundary": detectable_distance,
        "assumed_effect_absolute": assumed_effect,
        "baseline_rate": round(baseline_rate, 6),
        "expected_allocation": allocation,
        "cluster_average_size": cluster_size,
        "intracluster_correlation": icc,
        "cluster_design_effect": design_effect,
        "expected_attrition_rate": attrition,
        "required_analyzable_total_before_inflation": required_analyzable_total,
        "required_assigned_by_arm": required_by_arm,
        "actual_by_arm": actual_by_arm,
        "required_per_arm": max(required_by_arm.values()),
        "actual_min_arm": min(actual_by_arm.values()),
        "used_sample_count": sum(actual_by_arm.values()),
        "raw_observation_count": int(features["row_count"]),
        "aggregated_repeat_count": int(analysis.get("repeated_observation_count", 0)),
        "excluded_sample_count": int(features["row_count"]) - eligible_observations,
        "exclusion_reasons": [],
        "passed": passed,
    }


def causal_readiness(
    features: Mapping[str, Any],
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Grade evidence from observable contracts and metadata, never a case label."""
    contract_missing = _metric_contract_missing(metric_contract)
    quality = features["data_quality"]
    semantic_passed = not contract_missing

    data_missing = list(quality["missing_row_fields"]) + list(
        quality["missing_experiment_fields"]
    )
    data_missing.extend(
        f"non_null_{field}"
        for field, count in quality.get("null_counts", {}).items()
        if int(count) > 0
    )
    if quality.get("analysis_error"):
        data_missing.append("valid_randomization_unit_analysis")
    if quality.get("window_closed") is not True:
        data_missing.append("closed_experiment_window")
    if quality.get("outcome_complete") is not True:
        data_missing.append("complete_outcome_observation")
    data_missing = sorted(set(data_missing))
    data_passed = not data_missing and int(features["row_count"]) > 0

    assignment_method = experiment_metadata.get("assignment_method")
    group_counts = features["treatment"]["group_counts"]
    design_checks = {
        "randomized_assignment": assignment_method in RANDOMIZED_ASSIGNMENTS,
        "assignment_verified": experiment_metadata.get("assignment_verified") is True,
        "trusted_assignment_provenance": experiment_metadata.get(
            "assignment_provenance"
        )
        in {"experiment_platform", "signed_config"},
        "both_arms_present": int(group_counts.get("0", 0)) > 0
        and int(group_counts.get("1", 0)) > 0,
        "randomization_unit_accounted_for": features.get("analysis") is not None,
        "realized_experiment_integrity": features.get("experiment_integrity", {}).get(
            "passed"
        )
        is True,
    }
    design_passed = all(design_checks.values())
    try:
        power = _power_screen(features, experiment_metadata)
    except (TypeError, ValueError) as exc:
        power = {
            "status": "REFUSED_INVALID_CONFIGURATION",
            "passed": False,
            "reason_code": "POWER_CONFIGURATION_INVALID",
            "error": str(exc),
            "used_sample_count": int(features["row_count"]),
            "excluded_sample_count": 0,
            "exclusion_reasons": [],
        }
    statistics_passed = design_passed and power["passed"]

    governance_checks = {
        "approval_required": experiment_metadata.get("approval_required") is True,
        "guardrails_defined": bool(experiment_metadata.get("guardrails")),
        "stop_rule_defined": bool(experiment_metadata.get("stop_rule")),
        "production_auto_action_disabled": experiment_metadata.get(
            "production_auto_action"
        )
        is False,
    }
    governance_passed = all(governance_checks.values())
    gates = [
        {
            "name": "semantic",
            "passed": semantic_passed,
            "reason_code": "SEMANTIC_DEFINED"
            if semantic_passed
            else "METRIC_CONTRACT_INCOMPLETE",
        },
        {
            "name": "data",
            "passed": data_passed,
            "reason_code": "DATA_COMPLETE" if data_passed else "DATA_INSUFFICIENT",
        },
        {
            "name": "design",
            "passed": design_passed,
            "reason_code": "RANDOM_ASSIGNMENT_VERIFIED"
            if design_passed
            else "CAUSAL_DESIGN_NOT_VERIFIED",
        },
        {
            "name": "experiment_integrity",
            "passed": features.get("experiment_integrity", {}).get("passed") is True,
            "reason_code": "EXPERIMENT_INTEGRITY_PASS"
            if features.get("experiment_integrity", {}).get("passed") is True
            else "EXPERIMENT_INTEGRITY_FAILED",
        },
        {
            "name": "statistics",
            "passed": statistics_passed,
            "reason_code": "POWER_SCREEN_PASS"
            if statistics_passed
            else "POWER_NOT_ESTABLISHED",
        },
        {
            "name": "governance",
            "passed": governance_passed,
            "reason_code": "GOVERNANCE_READY"
            if governance_passed
            else "GOVERNANCE_INCOMPLETE",
        },
    ]
    if not semantic_passed or not data_passed:
        outcome = "DATA_INSUFFICIENT"
    elif all(gate["passed"] for gate in gates):
        outcome = "CAUSAL_READY"
    else:
        outcome = "DESCRIPTIVE_ONLY"
    return {
        "outcome": outcome,
        "estimand": features.get("analysis", {}).get("primary_estimand")
        if outcome == "CAUSAL_READY" and features.get("analysis")
        else None,
        "observation_unit": features.get("observation_unit"),
        "attribution_window": metric_contract.get("window"),
        "identification_strategy": assignment_method
        if design_passed
        else "not identified",
        "assumptions": [
            "stable metric contract",
            "no cross-unit interference",
            "complete outcome window",
        ]
        if design_passed
        else ["observational co-movement only"],
        "diagnostics": {
            "sample_size": features.get("row_count"),
            "analysis": features.get("analysis"),
            "group_counts": group_counts,
            "contract_missing_fields": contract_missing,
            "missing_evidence": data_missing,
            "design_checks": design_checks,
            "power": power,
            "governance_checks": governance_checks,
            "experiment_integrity": features.get("experiment_integrity"),
        },
        "gates": gates,
        "evidence_level": "L3" if outcome == "CAUSAL_READY" else "L1/L2",
        "reason_codes": [gate["reason_code"] for gate in gates if not gate["passed"]],
        "allowed_claim_type": "causal_effect"
        if outcome == "CAUSAL_READY"
        else "descriptive_only",
    }


def estimate_itt(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcomes: Sequence[str] = ("issued", "net_premium"),
    integrity_report: Mapping[str, Any] | None = None,
    metric_contract: Mapping[str, Any] | None = None,
    experiment_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    require_integrity_pass(integrity_report)
    contract = dict(metric_contract or {})
    metadata = dict(experiment_metadata or {})
    if not metadata:
        cluster_check = dict(
            integrity_report.get("checks", {}).get("cluster_integrity", {})
        )
        metadata = {
            "treatment_column": treatment_column,
            "randomization_unit": cluster_check.get("randomization_unit"),
            "analysis_unit": cluster_check.get("analysis_unit"),
            "assignment_method": cluster_check.get("assignment_method"),
            "cluster_column": cluster_check.get("cluster_column"),
            "primary_estimand": cluster_check.get("primary_estimand") or "user_level",
        }
        contract = {"outcomes": list(outcomes)}
    analysis_rows, analysis = prepare_analysis_rows(rows, contract, metadata, outcomes)
    groups = {
        arm: [row for row in analysis_rows if row.get(treatment_column) == arm]
        for arm in (0, 1)
    }
    if not groups[0] or not groups[1]:
        raise ValueError("ITT requires non-empty control and treatment groups")
    output: dict[str, Any] = {
        "estimator": analysis.get("estimator", "difference in means (ITT)"),
        "confidence": 0.95,
        "estimand": analysis,
    }
    for outcome in outcomes:
        means = {
            arm: sum(float(row.get(outcome, 0.0) or 0.0) for row in group) / len(group)
            for arm, group in groups.items()
        }
        variances = {
            arm: sum(
                (float(row.get(outcome, 0.0) or 0.0) - means[arm]) ** 2 for row in group
            )
            / max(1, len(group) - 1)
            for arm, group in groups.items()
        }
        effect = means[1] - means[0]
        inference_unit = analysis.get("inference_unit")
        if inference_unit:
            arm_variances: dict[int, float] = {}
            arm_cluster_counts: dict[int, int] = {}
            for arm, group in groups.items():
                scores: dict[str, float] = defaultdict(float)
                for row in group:
                    scores[str(row.get(inference_unit))] += (
                        float(row.get(outcome, 0.0) or 0.0) - means[arm]
                    )
                cluster_count = len(scores)
                arm_cluster_counts[arm] = cluster_count
                correction = (
                    cluster_count / (cluster_count - 1) if cluster_count > 1 else 1.0
                )
                arm_variances[arm] = (
                    correction
                    * sum(score**2 for score in scores.values())
                    / len(group) ** 2
                )
            if min(arm_cluster_counts.values()) < 2:
                raise ValueError(
                    "cluster-robust inference requires at least two clusters per arm"
                )
            standard_error = math.sqrt(arm_variances[1] + arm_variances[0])
        else:
            arm_cluster_counts = {arm: len(group) for arm, group in groups.items()}
            standard_error = math.sqrt(
                variances[1] / len(groups[1]) + variances[0] / len(groups[0])
            )
        margin = 1.96 * standard_error
        output[outcome] = {
            "control_mean": round(means[0], 6),
            "treatment_mean": round(means[1], 6),
            "estimate": round(effect, 6),
            "standard_error": round(standard_error, 6),
            "ci95": [round(effect - margin, 6), round(effect + margin, 6)],
            "analysis_rows_by_arm": {"0": len(groups[0]), "1": len(groups[1])},
            "inference_clusters_by_arm": {
                "0": arm_cluster_counts[0],
                "1": arm_cluster_counts[1],
            },
        }
    return output


def build_claim(readiness: Mapping[str, Any]) -> dict[str, Any]:
    if readiness["outcome"] == "CAUSAL_READY":
        return {
            "claim_id": "claim-001",
            "claim_type": "causal_effect",
            "evidence_level": "L3",
            "allowed_verbs": ["估计", "在本实验中提升"],
            "prohibited_actions": ["未经审批上线排序"],
            "uncertainty": "95% CI attached",
            "statement": "经验证的随机分配满足因果门禁，可报告本实验中的 ITT 估计与置信区间。",
        }
    if readiness["outcome"] == "DATA_INSUFFICIENT":
        return {
            "claim_id": "claim-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": ["当前缺少", "需要补充"],
            "prohibited_actions": ["声称导致", "自动触达个人", "直接上线配置"],
            "uncertainty": "required evidence is missing",
            "statement": "当前证据不足，必须补齐实验配置、观察窗口或结果数据后才能评估因果效应。",
        }
    return {
        "claim_id": "claim-001",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "allowed_verbs": ["观察到", "同时出现", "对应"],
        "prohibited_actions": ["声称导致", "自动触达个人", "直接上线配置"],
        "uncertainty": "causal identification unavailable",
        "statement": "当前只能说明指标变化与候选因素同时出现，不能断言因果。",
    }


def evaluate_public_dataset(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Public worker entry point. Hidden seeds and potential outcomes are not accepted."""
    rows = sanitize_rows(bundle.get("rows", []))
    metric_contract = dict(bundle.get("metric_contract", {}))
    experiment_metadata = dict(bundle.get("experiment_metadata", {}))
    features = extract_features(rows, metric_contract, experiment_metadata)
    readiness = causal_readiness(features, metric_contract, experiment_metadata)
    result: dict[str, Any] = {
        "benchmark_id": bundle.get("benchmark_id"),
        "features": features,
        "experiment_integrity": features["experiment_integrity"],
        "causal_readiness": readiness,
        "claim": build_claim(readiness),
    }
    if readiness["outcome"] == "CAUSAL_READY":
        result["estimate"] = estimate_itt(
            rows,
            str(experiment_metadata.get("treatment_column") or "treatment"),
            integrity_report=features["experiment_integrity"],
            metric_contract=metric_contract,
            experiment_metadata=experiment_metadata,
        )
    return result
