"""Deterministic evidence-to-action policy and finite-look error control.

Produces proposals only. No platform traffic mutation occurs here. Sequential
bounds use independent bounded analysis units (or independent cluster means),
Hoeffding + a union bound over both arms, metrics and preregistered looks.
"""

from __future__ import annotations

import math
from copy import deepcopy

from scipy.stats import norm

from .contracts import digest, finite, integer, validate_bundle


def propose_experiment(
    *,
    metric_contract,
    mde,
    baseline_variance,
    allocation=0.5,
    alpha=0.05,
    power=0.8,
    cluster_size=1,
    icc=0.0,
    factors=(),
    checkpoints=(7, 14, 28),
    minimum_units=100,
    deadline=28,
):
    from .contracts import validate_contract
    from .experiment_designer import design_experiment

    metric = validate_contract("MetricContract", metric_contract)
    values = [
        finite(v, n)
        for v, n in zip(
            (mde, baseline_variance, allocation, alpha, power, cluster_size, icc),
            (
                "mde",
                "baseline_variance",
                "allocation",
                "alpha",
                "power",
                "cluster_size",
                "icc",
            ),
        )
    ]
    mde, variance, allocation, alpha, power, size, icc = values
    if not (
        mde > 0
        and variance > 0
        and 0 < allocation < 1
        and 0 < alpha < 1
        and 0.5 < power < 1
        and size >= 1
        and 0 <= icc <= 1
    ):
        raise ValueError("invalid sample-size parameters")
    if factors and allocation != 0.5:
        raise ValueError(
            "factorial proposal currently requires balanced main-effect contrasts"
        )
    planning_alpha = alpha / max(1, len(factors))
    design_effect = 1 + (size - 1) * icc
    n = math.ceil(
        (norm.ppf(1 - planning_alpha / 2) + norm.ppf(power)) ** 2
        * variance
        / (allocation * (1 - allocation) * mde * mde)
        * design_effect
    )
    clusters = math.ceil(n / size)
    clusters = max(
        clusters,
        math.ceil(
            integer(minimum_units, "minimum_units") / min(allocation, 1 - allocation)
        ),
    )
    if size > 1:
        clusters = max(clusters, math.ceil(20 / min(allocation, 1 - allocation)))
    policy = register_sequential_policy(
        metric_names=[metric["name"]],
        checkpoints=checkpoints,
        minimum_units=minimum_units,
        deadline=deadline,
        alpha=alpha,
        maturity_days=metric["maturity_days"],
    )
    return {
        "status": "PROPOSED",
        "requires_approval_before_activation": True,
        "metric_contract": metric,
        "mde": mde,
        "allocation": allocation,
        "planned_units": math.ceil(clusters * size),
        "planned_randomization_groups": clusters,
        "design_effect": design_effect,
        "sample_size_method": "normal fixed-horizon planning approximation; sequential boundaries may require more samples",
        "sequential_policy": policy,
        "planning_alpha_per_contrast": planning_alpha,
        "factorial_design": design_experiment(
            factors, traffic_budget=math.ceil(clusters * size)
        )
        if factors
        else None,
    }


def register_sequential_policy(
    *,
    metric_names,
    checkpoints,
    minimum_units,
    deadline,
    alpha=0.05,
    maturity_days=0,
    stopping_rules=None,
):
    if (
        not metric_names
        or len(set(metric_names)) != len(metric_names)
        or any(not isinstance(x, str) or not x for x in metric_names)
    ):
        raise ValueError("unique nonempty metric names required")
    looks = [integer(v, "checkpoint") for v in checkpoints]
    minimum_units, deadline, maturity_days = (
        integer(v, n)
        for v, n in zip(
            (minimum_units, deadline, maturity_days),
            ("minimum_units", "deadline", "maturity_days"),
        )
    )
    alpha = finite(alpha, "alpha")
    if (
        not looks
        or looks != sorted(set(looks))
        or looks[0] < 0
        or looks[-1] != deadline
        or minimum_units < 2
        or maturity_days < 0
        or not 0 < alpha < 1
    ):
        raise ValueError("invalid preregistered look schedule")
    if stopping_rules is not None:
        if (
            not isinstance(stopping_rules, dict)
            or stopping_rules.get("primary") not in metric_names
        ):
            raise ValueError("stopping rules require a registered primary metric")
        if set(stopping_rules.get("guardrail_limits", {})) != set(metric_names) - {
            stopping_rules["primary"]
        }:
            raise ValueError("every other metric requires a guardrail limit")
        finite(stopping_rules["threshold"], "threshold")
        for value in stopping_rules["guardrail_limits"].values():
            finite(value, "guardrail limit")
    policy = {
        "metric_names": list(metric_names),
        "checkpoints": looks,
        "minimum_units": minimum_units,
        "deadline": deadline,
        "alpha": alpha,
        "maturity_days": maturity_days,
        "stopping_rules": deepcopy(stopping_rules),
        "method": "finite_look_Hoeffding_union_bound",
        "observation_range": [0.0, 1.0],
        "assumption": "independent bounded units; aggregate dependent observations to independent cluster means",
    }
    return {**policy, "digest": digest(policy)}


def evaluate_checkpoint(policy, *, day, observed_through, samples, state=None):
    body = {k: v for k, v in policy.items() if k != "digest"}
    if policy.get("digest") != digest(body):
        raise ValueError("policy digest mismatch")
    # Validate a reconstructed schedule, not merely a self-declared digest.
    validated = register_sequential_policy(
        **{
            k: body[k]
            for k in (
                "metric_names",
                "checkpoints",
                "minimum_units",
                "deadline",
                "alpha",
                "maturity_days",
                "stopping_rules",
            )
        }
    )
    if validated != policy:
        raise ValueError("policy contains unsupported rules")
    day, observed_through = (
        integer(day, "day"),
        integer(observed_through, "observed_through"),
    )
    previous = deepcopy(
        state
        or {
            "policy_ref": policy["digest"],
            "looks": [],
            "counts": {},
            "terminal": False,
        }
    )
    if previous.get("policy_ref") != policy["digest"] or previous.get("terminal"):
        raise ValueError("policy changed or monitoring already ended")
    if day not in policy["checkpoints"] or (
        previous["looks"] and day <= max(previous["looks"])
    ):
        raise ValueError("only increasing preregistered checkpoints can be evaluated")
    if set(samples) != set(policy["metric_names"]):
        raise ValueError("all preregistered guardrails and primary metrics required")
    counts, intervals = {}, {}
    for name in policy["metric_names"]:
        arms = samples[name]
        if set(arms) != {"treatment", "control"}:
            raise ValueError("both arms required")
        bound, means = 0.0, {}
        for arm in ("treatment", "control"):
            row = arms[arm]
            n, total = integer(row["n"], "n"), finite(row["sum"], "sum")
            if (
                n <= 0
                or not 0 <= total <= n
                or n < previous["counts"].get(name, {}).get(arm, 0)
            ):
                raise ValueError("invalid or decreasing bounded sample counts")
            counts.setdefault(name, {})[arm] = n
            means[arm] = total / n
            bound += math.sqrt(
                math.log(
                    4 * len(samples) * len(policy["checkpoints"]) / policy["alpha"]
                )
                / (2 * n)
            )
        value = means["treatment"] - means["control"]
        ready = (
            min(counts[name].values()) >= policy["minimum_units"]
            and observed_through >= day + policy["maturity_days"]
        )
        intervals[name] = {
            "estimate": value if ready else None,
            "interval": [max(-1.0, value - bound), min(1.0, value + bound)]
            if ready
            else None,
            "status": "READY" if ready else "IMMATURE_OR_UNDERPOWERED",
        }
    decision = "CONTINUE"
    rules = policy.get("stopping_rules")
    if rules and all(m["interval"] is not None for m in intervals.values()):
        harm = any(
            intervals[name]["interval"][0] > limit
            for name, limit in rules["guardrail_limits"].items()
        )
        safe = all(
            intervals[name]["interval"][1] <= limit
            for name, limit in rules["guardrail_limits"].items()
        )
        low, high = intervals[rules["primary"]]["interval"]
        if harm:
            decision = "STOP_HARM"
        elif safe and low > rules["threshold"]:
            decision = "STOP_SUCCESS"
        elif rules.get("allow_futility", False) and high <= rules["threshold"]:
            decision = "STOP_FUTILITY"
    if decision == "CONTINUE" and day == policy["deadline"]:
        decision = "STOP_DEADLINE"
    previous.update(
        counts=counts,
        looks=[*previous["looks"], day],
        terminal=decision != "CONTINUE",
    )
    return {
        "decision": decision,
        "policy_ref": policy["digest"],
        "state": previous,
        "metrics": intervals,
        "status": "DEADLINE"
        if day == policy["deadline"]
        else "STOPPED"
        if previous["terminal"]
        else "CHECKPOINT",
        "error_control": "simultaneous over the finite registered looks and metrics; no p-value peeking",
    }


def decide_action(
    contracts,
    *,
    practical_threshold,
    business_value_per_unit,
    exposure,
    implementation_cost,
    guardrails,
    primary_direction="increase",
):
    bundle = validate_bundle(contracts)
    effect = bundle["EffectEstimate"]
    threshold, value, exposure, cost = (
        finite(v, n)
        for v, n in zip(
            (
                practical_threshold,
                business_value_per_unit,
                exposure,
                implementation_cost,
            ),
            (
                "practical_threshold",
                "business_value_per_unit",
                "exposure",
                "implementation_cost",
            ),
        )
    )
    if min(threshold, value, exposure, cost) < 0 or primary_direction not in {
        "increase",
        "decrease",
    }:
        raise ValueError("invalid business policy")
    report = bundle["IdentificationReport"]
    if report["status"] != "IDENTIFIED" or effect["estimate"] is None:
        return {
            "action": "COLLECT_EVIDENCE",
            "reason_codes": report["reason_codes"],
            "missing": report.get("supplemental_evidence_needed", []),
            "effect_ref": effect["digest"],
        }
    if effect["selection_status"] == "exploratory":
        return {
            "action": "INDEPENDENT_EXPERIMENT",
            "effect_ref": effect["digest"],
            "reason": "exploratory selection",
        }
    unknown, harmed = [], []
    if not guardrails:
        raise ValueError("explicit joint guardrail policy required")
    for name, rule in guardrails.items():
        limit = finite(rule["max_harm"], "max_harm")
        ci = rule.get("interval")
        if ci is None:
            unknown.append(name)
            continue
        if len(ci) != 2:
            raise ValueError("guardrail requires interval")
        low, high = (finite(v, "guardrail interval") for v in ci)
        if low > high:
            raise ValueError("reversed guardrail interval")
        if not rule.get("simultaneous_evidence_ref"):
            unknown.append(name)
        elif low > limit:
            harmed.append(name)
        elif high > limit:
            unknown.append(name)
    low, high = effect["interval"]
    if primary_direction == "decrease":
        low, high = -high, -low
    worst_gain = low * value * exposure - cost
    action = (
        "ROLLBACK_PROPOSAL"
        if harmed
        else "COLLECT_EVIDENCE"
        if unknown
        else "LAUNCH_PROPOSAL"
        if low > threshold and worst_gain > 0
        else "KEEP_BASELINE"
        if high <= threshold
        else "INDEPENDENT_EXPERIMENT"
    )
    return {
        "action": action,
        "effect_ref": effect["digest"],
        "guardrails_harmed": harmed,
        "guardrails_unknown": unknown,
        "worst_case_net_value": worst_gain,
        "policy": "joint guardrails + practical threshold + interval worst-case loss",
        "requires_approval_before_activation": action
        in {"ROLLBACK_PROPOSAL", "LAUNCH_PROPOSAL"},
    }
