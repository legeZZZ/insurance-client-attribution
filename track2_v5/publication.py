"""The deterministic publication boundary: identification, uncertainty, action.

Statistical outputs remain useful for diagnostics; only this module grants a
public causal label. No free-text statement may override its generated wording.
"""

from __future__ import annotations

from copy import deepcopy

from .contracts import REASONS, digest, finite, validate_bundle, validate_contract

DISPLAY_TYPES = (
    "DESCRIPTIVE_FACT",
    "CANDIDATE_ASSOCIATION",
    "CONDITIONAL_TEMPORAL",
    "OBSERVATIONAL_EFFECT_UNDER_ASSUMPTIONS",
    "RANDOMIZED_EFFECT",
    "COMPONENT_RANDOMIZED_EFFECT",
)
REMEDIES = {
    "DATA_INVALID": "repair_or_refresh_data",
    "INSUFFICIENT_POWER": "collect_more_mature_units",
    "NOT_IDENTIFIABLE": "preregister_identifying_design",
    "GRAPH_AMBIGUOUS": "resolve_graph_or_sensitivity_design",
    "CONTROL_CONTAMINATED": "replace_affected_controls",
    "MODEL_MISMATCH": "revise_prespecified_model",
}
STRONG_LEGACY = {
    "causal_effect",
    "L3",
    "BUNDLE_EFFECT",
    "HETEROGENEOUS_TREATMENT_EFFECT",
    "COMPONENT_EFFECT",
    "CAUSAL_READY",
    "CAUSAL_ESTIMATE",
    "CAUSAL_CONFIRMED",
    *DISPLAY_TYPES[3:],
}


def publish_conclusion(
    contracts, *, practical_threshold=0.0, component_design=None, action_policy=None
):
    bundle = validate_bundle(contracts)
    if not all(
        k in bundle
        for k in ("MetricContract", "IdentificationReport", "EffectEstimate")
    ):
        raise ValueError(
            "publication requires metric, identification and effect contracts"
        )
    threshold = finite(practical_threshold, "practical_threshold")
    if threshold < 0:
        raise ValueError("practical threshold must be nonnegative")
    metric, identification, effect = (
        bundle[k] for k in ("MetricContract", "IdentificationReport", "EffectEstimate")
    )
    reasons = set(identification["reason_codes"])
    if identification["status"] != "IDENTIFIED" or effect["estimate"] is None:
        interpretation, display = "UNTRUSTWORTHY", "CANDIDATE_ASSOCIATION"
        reasons.add("NOT_IDENTIFIABLE") if not reasons else None
        estimate, interval = None, None
        statement = "当前设计未满足识别条件，不能发布因果效应。"
    elif effect["selection_status"] == "exploratory":
        interpretation, display = (
            "NEEDS_INDEPENDENT_CONFIRMATION",
            "CANDIDATE_ASSOCIATION",
        )
        estimate, interval = None, None
        statement = "探索分析产生了待独立确认的候选，不作为已确认因果效应。"
    else:
        estimate, interval = effect["estimate"], effect["interval"]
        low, high = interval
        if low >= -threshold and high <= threshold:
            interpretation = "PRACTICALLY_EQUIVALENT"
        elif low > threshold or high < -threshold:
            interpretation = "PRACTICAL_EFFECT"
        else:
            interpretation = "INCONCLUSIVE"
            reasons.add("INSUFFICIENT_POWER")
        display = (
            "RANDOMIZED_EFFECT"
            if identification["design"] == "RCT"
            else "OBSERVATIONAL_EFFECT_UNDER_ASSUMPTIONS"
        )
        if component_design is not None:
            required = (
                "independent_randomization",
                "design_code_traceable",
                "stable_randomization_unit",
            )
            if (
                display != "RANDOMIZED_EFFECT"
                or not all(component_design.get(k) is True for k in required)
                or component_design.get("assignment_provenance")
                not in {"experiment_platform", "signed_config"}
            ):
                raise ValueError(
                    "component publication requires randomized identifiable design evidence"
                )
            display = "COMPONENT_RANDOMIZED_EFFECT"
        prefix = (
            "随机实验" if identification["design"] == "RCT" else "在已列出的识别假设下"
        )
        phrase = {
            "PRACTICALLY_EQUIVALENT": "区间位于预设实质等价界内",
            "PRACTICAL_EFFECT": "区间超过预设实质阈值",
            "INCONCLUSIVE": "区间尚不能区分实质效应与可忽略效应",
        }[interpretation]
        statement = f"{prefix}估计{metric['name']}的{effect['estimand']}为{estimate:.6g}，{phrase}。"
    if not reasons <= REASONS:
        raise ValueError("unsupported refusal reason")
    if action_policy is not None and interpretation not in {
        "UNTRUSTWORTHY",
        "NEEDS_INDEPENDENT_CONFIRMATION",
    }:
        from .action_interface import decide_action

        action = decide_action(bundle, practical_threshold=threshold, **action_policy)
    else:
        action = {
            "action": "INDEPENDENT_EXPERIMENT"
            if interpretation == "NEEDS_INDEPENDENT_CONFIRMATION"
            else "COLLECT_EVIDENCE"
            if reasons
            else "REVIEW_POLICY",
            "practical_threshold": threshold,
            "requires_approval_before_activation": True,
        }
    value = {
        "schema_version": "publication/1",
        "execution_status": "COMPLETED",
        "claim_type": display,
        "interpretation": interpretation,
        "statement": statement,
        "identification": {
            "design": identification["design"],
            "estimand": effect["estimand"],
            "status": identification["status"],
            "assumptions": identification["assumptions"],
            "ref": identification["digest"],
        },
        "statistical_uncertainty": {
            "effect": estimate,
            "interval": interval,
            "interval_method": effect["interval_method"],
            "selection_status": effect["selection_status"],
            "pvalue": None,
            "qvalue": None,
            "posterior_probability": None,
            "effect_ref": effect["digest"],
        },
        "action_policy": action,
        "reason_codes": sorted(reasons),
        "remedies": [REMEDIES[r] for r in sorted(reasons)],
        "contracts": bundle,
        "publication_options": {
            "practical_threshold": threshold,
            "component_design": deepcopy(component_design),
            "action_policy": deepcopy(action_policy),
        },
    }
    value["digest"] = digest(value)
    return value


def verify_publication(value):
    if not isinstance(value, dict) or value.get("schema_version") != "publication/1":
        raise ValueError("canonical publication required")
    expected = publish_conclusion(value["contracts"], **value["publication_options"])
    if expected != value:
        raise ValueError("publication content or digest does not match its contracts")
    return expected


def publish_association(result):
    family = result.get("test_family_contract")
    if family:
        family = validate_contract("TestFamilyContract", family)
    return [
        {
            "claim_type": "CONDITIONAL_TEMPORAL"
            if family
            and c.get("holdout", {}).get("survives") is True
            and c["holdout"].get("adjusted_pvalue", 1) <= family["alpha"]
            else "CANDIDATE_ASSOCIATION",
            "statement": "观察到经留出确认的条件时序关联；尚非干预效应。"
            if family
            and c.get("holdout", {}).get("survives") is True
            and c["holdout"].get("adjusted_pvalue", 1) <= family["alpha"]
            else "发现待验证的关联候选。",
            "factor_id": c.get("factor_id"),
            "identification": {"status": "NOT_IDENTIFIED"},
            "statistical_uncertainty": {
                "pvalue": c.get("holdout", {}).get("adjusted_pvalue")
                if family
                else None,
                "qvalue": None,
                "test_family_ref": family["digest"] if family else None,
                "effect": None,
                "interval": None,
            },
            "action_policy": {"action": "INDEPENDENT_EXPERIMENT"},
            "execution_status": "COMPLETED",
        }
        for c in result.get("candidates", [])
    ]


def govern_output(value, *, registry=None):
    """Recursively guard legacy report/artifact boundaries and verify new outputs.

    Unsupported legacy causal labels are explicitly downgraded and their causal
    numbers/text withheld. Ordinary descriptive and diagnostic fields stay data.
    """
    if isinstance(value, list):
        return [govern_output(v, registry=registry) for v in value]
    if not isinstance(value, dict):
        return value
    if value.get("schema_version") == "publication/1":
        verify_publication(value)
        return deepcopy(value)
    out = deepcopy(value)
    if registry is None and out.get("publication_ref") and out.get("registry_path"):
        from .hypothesis_registry import HypothesisRegistry

        active_registry = HypothesisRegistry(out["registry_path"])
        try:
            return govern_output(out, registry=active_registry)
        finally:
            active_registry.close()
    if out.get("publication_ref") and registry:
        current = registry.asset(out["publication_ref"])
        if current["status"] != "VALID":
            return {
                "publication_ref": out["publication_ref"],
                "publication_status": current["status"],
                **current["body"],
            }
    contracts = out.get("contracts")
    qualified = isinstance(contracts, dict) and all(
        k in contracts
        for k in ("MetricContract", "IdentificationReport", "EffectEstimate")
    )
    if qualified:
        if out.get("publication"):
            canonical = verify_publication(out["publication"])
            if canonical["contracts"] != validate_bundle(contracts):
                raise ValueError("publication and enclosing contracts disagree")
        else:
            canonical = publish_conclusion(contracts)
        out["publication"] = canonical
        for key in ("claim_type", "claim", "evidence_level", "outcome"):
            if key in out:
                out[key] = canonical["claim_type"]
        for key in ("statement", "summary", "conclusion"):
            if key in out:
                out[key] = canonical["statement"]
        # The raw EffectEstimate is preserved as the auditable estimator artifact;
        # all published interpretation comes from its verified publication object.
        out["publication_status"] = out["publication"]["interpretation"]
    unsupported = (
        any(
            any(
                label in out.get(k, "").replace("+", " ").replace("/", " ").split()
                for label in STRONG_LEGACY
            )
            for k in ("claim_type", "claim", "evidence_level", "outcome")
            if isinstance(out.get(k), str)
        )
        and not qualified
    )
    if unsupported:
        old = {
            k: out[k]
            for k in ("claim_type", "claim", "evidence_level", "outcome")
            if k in out
        }
        for k in old:
            if isinstance(out[k], str) and any(
                label in out[k].replace("+", " ").replace("/", " ").split()
                for label in STRONG_LEGACY
            ):
                out[k] = "ASSOCIATION_ONLY"
        for k in ("statement", "summary", "conclusion"):
            if k in out:
                out[k] = "原条目缺少统一识别契约，已降为待验证的探索结果。"
        for k in (
            "estimate",
            "effect",
            "effect_absolute",
            "component_effect",
            "credible_interval_95",
            "credible_interval",
            "interval",
            "posterior_probability",
        ):
            if k in out:
                out[k] = None
        out["publication_guard"] = {
            "status": "DOWNGRADED",
            "reason_codes": ["NOT_IDENTIFIABLE"],
            "original_labels": old,
            "effect_estimate": None,
        }
    for k, v in list(out.items()):
        if k not in {"contracts", "publication", "publication_guard"}:
            out[k] = govern_output(v, registry=registry)
    return out


def persist_publication(registry, contracts, *, dependencies, **options):
    result = publish_conclusion(contracts, **options)
    ref = registry.add_asset("claim", result, dependencies=dependencies)
    return {
        "publication_ref": ref,
        "publication": result,
        "publication_status": "VALID",
        **(
            {"registry_path": str(__import__("pathlib").Path(registry.path).resolve())}
            if registry.path != ":memory:"
            else {}
        ),
    }
