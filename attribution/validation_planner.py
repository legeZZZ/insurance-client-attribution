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
) -> dict[str, Any]:
    source_type = str(candidate.get("source_type", "factor_series"))
    factor_id = str(candidate.get("factor_id", "unknown"))
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
            "derived_layer": candidate.get("derived_layer", "level"),
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
            "derived_layer": candidate.get("derived_layer", "level"),
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
    return {
        "plan_id": f"validation:{factor_id}",
        "factor_id": factor_id,
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
            "run_targeted_abtest"
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
        "claim_type_before_validation": "FACTOR_CANDIDATE",
        "causal_claim_allowed": False,
    }
