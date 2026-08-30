"""Deterministic feature extraction and causal-readiness skills."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

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


def _rate(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def sanitize_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove evaluator-only fields before data reaches an Agent or UI."""
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]


def aggregate_funnel(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    active = sum(int(row.get("active", 0) or 0) for row in rows)
    quoted = sum(int(row.get("quoted", 0) or 0) for row in rows)
    applied = sum(int(row.get("applied", 0) or 0) for row in rows)
    paid = sum(int(row.get("paid", 0) or 0) for row in rows)
    issued = sum(int(row.get("issued", 0) or 0) for row in rows)
    net_premium = round(sum(float(row.get("net_premium", 0.0) or 0.0) for row in rows), 2)
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
            values[outcome] = round(
                sum(float(row.get(outcome, 0.0) or 0.0) for row in group) / len(group), 6
            ) if group else 0.0
        result[str(arm)] = values
    return result


def extract_features(
    rows: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    experiment_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build auditable business, quality and experiment-design features."""
    identity = str(metric_contract.get("identity", "user_id"))
    treatment_column = str(experiment_metadata.get("treatment_column") or metric_contract.get("treatment") or "treatment")
    outcomes = [str(value) for value in metric_contract.get("outcomes", ["issued", "net_premium"])]
    required_row_fields = set(FUNNEL_FIELDS) | {identity, treatment_column, "net_premium"} | set(outcomes)
    available_fields = set().union(*(set(row.keys()) for row in rows)) if rows else set()
    missing_row_fields = sorted(required_row_fields - available_fields)
    null_counts = {
        field: sum(1 for row in rows if row.get(field) is None)
        for field in sorted(required_row_fields & available_fields)
    }
    identities = [row.get(identity) for row in rows if row.get(identity) is not None]
    duplicate_count = len(identities) - len(set(identities))
    missing_metadata = sorted(
        field for field in REQUIRED_EXPERIMENT_FIELDS
        if field not in experiment_metadata or experiment_metadata.get(field) is None
    )
    metrics = aggregate_funnel(rows)
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
                sum(float(row.get("product_mix", 0.0) or 0.0) for row in rows) / len(rows), 6
            ) if rows else 0.0,
        },
        "treatment": {
            "column": treatment_column,
            "group_counts": _distribution(rows, treatment_column),
            "group_outcomes": _group_outcomes(rows, treatment_column, outcomes),
        },
        "data_quality": {
            "missing_row_fields": missing_row_fields,
            "missing_experiment_fields": missing_metadata,
            "null_counts": null_counts,
            "duplicate_count": duplicate_count,
            "duplicate_rate": round(duplicate_count / len(rows), 6) if rows else 0.0,
            "window_closed": experiment_metadata.get("window_closed"),
            "outcome_complete": experiment_metadata.get("outcome_complete"),
        },
    }


def _metric_contract_missing(metric_contract: Mapping[str, Any]) -> list[str]:
    required = ("metric_id", "version", "identity", "funnel", "outcomes", "treatment", "window", "owner")
    return sorted(field for field in required if not metric_contract.get(field))


def _power_screen(features: Mapping[str, Any], experiment_metadata: Mapping[str, Any]) -> dict[str, Any]:
    treatment = features["treatment"]
    groups = treatment["group_outcomes"]
    control = groups.get("0", {})
    treatment_group = groups.get("1", {})
    baseline_rate = float(control.get("issued", 0.0))
    mde = float(experiment_metadata.get("minimum_detectable_effect") or 0.05)
    alpha = float(experiment_metadata.get("alpha") or 0.05)
    target_power = float(experiment_metadata.get("target_power") or 0.80)
    # Normal approximation for a balanced two-arm binary-outcome experiment.
    z_alpha = 1.96 if alpha == 0.05 else 1.96
    z_power = 0.84 if target_power == 0.80 else 0.84
    variance = max(baseline_rate * (1.0 - baseline_rate), 0.01)
    required_per_arm = math.ceil(2.0 * (z_alpha + z_power) ** 2 * variance / max(mde ** 2, 1e-9))
    actual_per_arm = min(int(control.get("count", 0)), int(treatment_group.get("count", 0)))
    return {
        "method": "two-arm binary normal approximation",
        "alpha": alpha,
        "target_power": target_power,
        "minimum_detectable_effect": mde,
        "baseline_rate": round(baseline_rate, 6),
        "required_per_arm": required_per_arm,
        "actual_min_arm": actual_per_arm,
        "passed": actual_per_arm >= required_per_arm,
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

    data_missing = list(quality["missing_row_fields"]) + list(quality["missing_experiment_fields"])
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
        "trusted_assignment_provenance": experiment_metadata.get("assignment_provenance") in {"experiment_platform", "signed_config"},
        "both_arms_present": int(group_counts.get("0", 0)) > 0 and int(group_counts.get("1", 0)) > 0,
        "randomization_unit_matches": experiment_metadata.get("randomization_unit") == features.get("observation_unit"),
    }
    design_passed = all(design_checks.values())
    power = _power_screen(features, experiment_metadata)
    statistics_passed = design_passed and power["passed"]

    governance_checks = {
        "approval_required": experiment_metadata.get("approval_required") is True,
        "guardrails_defined": bool(experiment_metadata.get("guardrails")),
        "stop_rule_defined": bool(experiment_metadata.get("stop_rule")),
        "production_auto_action_disabled": experiment_metadata.get("production_auto_action") is False,
    }
    governance_passed = all(governance_checks.values())
    gates = [
        {"name": "semantic", "passed": semantic_passed, "reason_code": "SEMANTIC_DEFINED" if semantic_passed else "METRIC_CONTRACT_INCOMPLETE"},
        {"name": "data", "passed": data_passed, "reason_code": "DATA_COMPLETE" if data_passed else "DATA_INSUFFICIENT"},
        {"name": "design", "passed": design_passed, "reason_code": "RANDOM_ASSIGNMENT_VERIFIED" if design_passed else "CAUSAL_DESIGN_NOT_VERIFIED"},
        {"name": "statistics", "passed": statistics_passed, "reason_code": "POWER_SCREEN_PASS" if statistics_passed else "POWER_NOT_ESTABLISHED"},
        {"name": "governance", "passed": governance_passed, "reason_code": "GOVERNANCE_READY" if governance_passed else "GOVERNANCE_INCOMPLETE"},
    ]
    if not semantic_passed or not data_passed:
        outcome = "DATA_INSUFFICIENT"
    elif all(gate["passed"] for gate in gates):
        outcome = "CAUSAL_READY"
    else:
        outcome = "DESCRIPTIVE_ONLY"
    return {
        "outcome": outcome,
        "estimand": "ITT on issued and net_premium" if outcome == "CAUSAL_READY" else None,
        "observation_unit": features.get("observation_unit"),
        "attribution_window": metric_contract.get("window"),
        "identification_strategy": assignment_method if design_passed else "not identified",
        "assumptions": ["stable metric contract", "no cross-unit interference", "complete outcome window"] if design_passed else ["observational co-movement only"],
        "diagnostics": {
            "sample_size": features.get("row_count"),
            "group_counts": group_counts,
            "contract_missing_fields": contract_missing,
            "missing_evidence": data_missing,
            "design_checks": design_checks,
            "power": power,
            "governance_checks": governance_checks,
        },
        "gates": gates,
        "evidence_level": "L3" if outcome == "CAUSAL_READY" else "L1/L2",
        "reason_codes": [gate["reason_code"] for gate in gates if not gate["passed"]],
        "allowed_claim_type": "causal_effect" if outcome == "CAUSAL_READY" else "descriptive_only",
    }


def estimate_itt(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcomes: Sequence[str] = ("issued", "net_premium"),
) -> dict[str, Any]:
    groups = {arm: [row for row in rows if row.get(treatment_column) == arm] for arm in (0, 1)}
    if not groups[0] or not groups[1]:
        raise ValueError("ITT requires non-empty control and treatment groups")
    output: dict[str, Any] = {"estimator": "difference in means (ITT)", "confidence": 0.95}
    for outcome in outcomes:
        means = {arm: sum(float(row.get(outcome, 0.0) or 0.0) for row in group) / len(group) for arm, group in groups.items()}
        variances = {
            arm: sum((float(row.get(outcome, 0.0) or 0.0) - means[arm]) ** 2 for row in group) / max(1, len(group) - 1)
            for arm, group in groups.items()
        }
        effect = means[1] - means[0]
        standard_error = math.sqrt(variances[1] / len(groups[1]) + variances[0] / len(groups[0]))
        margin = 1.96 * standard_error
        output[outcome] = {
            "control_mean": round(means[0], 6),
            "treatment_mean": round(means[1], 6),
            "estimate": round(effect, 6),
            "standard_error": round(standard_error, 6),
            "ci95": [round(effect - margin, 6), round(effect + margin, 6)],
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
        "causal_readiness": readiness,
        "claim": build_claim(readiness),
    }
    if readiness["outcome"] == "CAUSAL_READY":
        result["estimate"] = estimate_itt(rows, str(experiment_metadata.get("treatment_column") or "treatment"))
    return result
