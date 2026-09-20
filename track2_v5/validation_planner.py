"""Turn a discovered factor into an auditable validation plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def plan_validation(
    candidate: Mapping[str, Any],
    metric_contract: Mapping[str, Any],
    *,
    discovery_window: Sequence[int],
    holdout_window: Sequence[int] | None = None,
    experiment_design_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_type = str(candidate.get("source_type", "factor_series"))
    factor_id = str(candidate.get("factor_id", "unknown"))
    derived_layer = str(candidate.get("derived_layer", "level"))
    derived_feature_id = str(candidate.get("derived_feature_id", factor_id))
    experimentability = str(candidate.get("experimentability", ""))
    is_controllable = (
        source_type == "internal_event" or experimentability == "controllable"
    )
    if is_controllable:
        route = "targeted_abtest_or_gray_release"
        design = "within_scope_randomized_intervention"
    elif source_type == "external_event":
        route = "stratified_quasi_experiment"
        design = "control_series_or_synthetic_control_with_holdout"
    else:
        route = "holdout_then_quasi_experiment"
        design = "lagged_association_as_screen_only_then_intervention"
    holdout = list(holdout_window) if holdout_window is not None else None
    target_scope = (
        candidate.get("target_scope")
        or candidate.get("scope")
        or {"scope_id": candidate.get("scope_id", "global")}
    )
    target_window = None
    if holdout is not None:
        target_window = [int(holdout[-1]) + 1, int(holdout[-1]) + 14]
    experiment_spec = None
    if is_controllable:
        experiment_spec = {
            "template_id": "targeted_factor_validation",
            "candidate_id": candidate.get("candidate_id"),
            "factor_id": factor_id,
            "parent_factor_id": candidate.get("parent_factor_id", factor_id),
            "derived_feature_id": derived_feature_id,
            "derived_layer": derived_layer,
            "target_scope": target_scope,
            "randomization_unit": "hashed_subject_id",
            "stable_randomization_unit": "hashed_subject_id",
            "treatment": "candidate_intervention_or_flag_on",
            "control": "current_behavior_or_flag_off",
            "metric": metric_contract.get("name"),
            "metric_contract": dict(metric_contract),
            "traffic_plan": [5, 10, 25],
            "planned_window": target_window,
            "guardrails": ["error_rate", "latency_p95", "complaint_rate"],
            "pre_registration_required": True,
            "causal_claim_allowed": False,
        }
    elif source_type in {"external_event", "factor_series"}:
        # External variables cannot be randomized. The next-window A/B tests
        # the operator's mitigation, while the factor itself uses a quasi-
        # experimental route.
        experiment_spec = {
            "template_id": "external_factor_mitigation_abtest",
            "candidate_id": candidate.get("candidate_id"),
            "factor_id": factor_id,
            "parent_factor_id": candidate.get("parent_factor_id", factor_id),
            "derived_feature_id": derived_feature_id,
            "derived_layer": derived_layer,
            "target_scope": target_scope,
            "randomization_unit": "hashed_subject_id",
            "treatment": "mitigation_strategy_on",
            "control": "current_strategy",
            "metric": metric_contract.get("name"),
            "metric_contract": dict(metric_contract),
            "traffic_plan": [5, 10, 25],
            "planned_window": target_window,
            "guardrails": ["error_rate", "latency_p95", "complaint_rate"],
            "factor_itself_randomizable": False,
            "factor_validation_route": route,
            "pre_registration_required": True,
            "causal_claim_allowed": False,
        }
    requires_evidence = candidate.get("claim_type") == "WATCHLIST" or candidate.get(
        "confirmation_status"
    ) in {"HOLDOUT_FAILED", "INSUFFICIENT_HOLDOUT"}
    if requires_evidence:
        route = "collect_independent_confirmation_evidence"
        design = "frozen_candidate_new_holdout"
        experiment_spec = None
    if experiment_spec is not None and experiment_design_parameters is not None:
        from .action_interface import propose_experiment

        prospective_metric = {
            k: v
            for k, v in metric_contract.items()
            if k not in {"digest", "schema_version", "contract_type"}
        }
        if target_window is not None:
            prospective_metric["window"] = target_window
        experiment_spec["governed_design"] = propose_experiment(
            metric_contract=prospective_metric, **experiment_design_parameters
        )
        experiment_spec["requires_approval_before_activation"] = True
    return {
        "plan_id": f"validation:{factor_id}:{derived_layer}",
        "factor_id": factor_id,
        "parent_factor_id": candidate.get("parent_factor_id", factor_id),
        "derived_feature_id": derived_feature_id,
        "derived_layer": derived_layer,
        "route": route,
        "design": design,
        "metric_contract": dict(metric_contract),
        "discovery_window": list(discovery_window),
        "holdout_window": holdout,
        "selected_lag_days": candidate.get("lag_days"),
        "target_scope": target_scope,
        "target_window": target_window,
        "experimentability": "controllable"
        if is_controllable
        else "external_or_observational",
        "next_window_action": (
            "collect_independent_confirmation_evidence"
            if requires_evidence
            else "run_targeted_abtest"
            if is_controllable
            else "run_mitigation_abtest_and_quasi_experiment"
            if experiment_spec
            else route
        ),
        "experiment_spec": experiment_spec,
        "primary_estimand": metric_contract.get("estimand", "rate difference"),
        "gates": [
            "候选必须来自授权数据入口并保留 content_digest/license_ref。",
            "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
            "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
            "验证数据不能与候选搜索窗口复用。",
        ],
        "expected_outputs": [
            "holdout_survives",
            "effect_estimate",
            "interval_or_posterior",
            "assumptions",
            "claim_type",
            "evidence_refs",
        ],
        "claim_type_before_validation": candidate.get("claim_type", "WATCHLIST"),
        "requires_confirmation": requires_evidence,
        "causal_claim_allowed": False,
    }
