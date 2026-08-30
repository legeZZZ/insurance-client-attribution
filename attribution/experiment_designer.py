"""FactorialExperimentDesigner: turn factor candidates into identifiable designs.

- K <= 3 factors: full factorial (2^K arms).
- K = 4..5: Resolution-IV fractional factorial (2^(K-1) arms).
- Each arm records its design code so component effects remain traceable.
- Expected information gain ranks which factor set to test next.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from typing import Any


def _full_factorial(k: int) -> list[list[int]]:
    return [list(bits) for bits in itertools.product((0, 1), repeat=k)]


def _fractional_resolution_iv(k: int) -> list[list[int]]:
    """2^(K-1) design: last factor = product (XOR) of the first K-1."""
    base = _full_factorial(k - 1)
    design = []
    for bits in base:
        parity = 0
        for bit in bits:
            parity ^= bit
        design.append(bits + [parity])
    return design


def design_experiment(
    factor_ids: Sequence[str],
    max_arms: int = 16,
    traffic_budget: int = 100_000,
    guardrail_risk: Mapping[str, float] | None = None,
    engineering_cost: Mapping[str, float] | None = None,
    uncertainty: Mapping[str, float] | None = None,
    business_loss_weight: float = 1.0,
) -> dict[str, Any]:
    if not factor_ids:
        raise ValueError("factor_ids must be non-empty")
    k = len(factor_ids)
    if k <= 3:
        matrix = _full_factorial(k)
        design_type = "full_factorial"
    elif k <= 5:
        matrix = _fractional_resolution_iv(k)
        design_type = "fractional_factorial_resolution_iv"
    else:
        raise ValueError("more than 5 factors: run a screening stage first")

    if len(matrix) > max_arms:
        matrix = matrix[:max_arms]
        design_type += "_truncated"

    guardrail_risk = guardrail_risk or {}
    engineering_cost = engineering_cost or {}
    uncertainty = uncertainty or {}

    arms = []
    per_arm = max(traffic_budget // len(matrix), 1)
    for index, bits in enumerate(matrix):
        arms.append({
            "arm_id": f"arm-{index:02d}",
            "design_code": {factor: bit for factor, bit in zip(factor_ids, bits)},
            "planned_impressions": per_arm,
            "is_control": all(bit == 0 for bit in bits),
        })

    # Expected value score per factor: uncertainty x distinguishability - costs.
    factor_scores = {}
    for factor in factor_ids:
        info_gain = float(uncertainty.get(factor, 1.0))
        risk = float(guardrail_risk.get(factor, 0.1))
        cost = float(engineering_cost.get(factor, 0.1))
        factor_scores[factor] = round(info_gain - business_loss_weight * risk - cost, 4)

    return {
        "design_type": design_type,
        "factors": list(factor_ids),
        "arm_count": len(arms),
        "arms": arms,
        "factor_value_scores": factor_scores,
        "requirements": [
            "independent randomization per design code",
            "traceable assignment provenance",
            "stable randomization unit",
            "consistent exposure and outcome windows",
        ],
    }


def estimate_component_effects(
    arm_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    arms: Sequence[Mapping[str, Any]],
    factor_ids: Sequence[str],
    outcome_column: str = "clicked",
    practical_threshold: float = 0.005,
) -> list[dict[str, Any]]:
    """Estimate main effects from a (fractional) factorial experiment.

    Effect of factor j = CTR(arms with bit 1) - CTR(arms with bit 0),
    which stays unbiased for main effects in a Resolution-IV design.
    """
    results: list[dict[str, Any]] = []
    for j, factor in enumerate(factor_ids):
        clicks = {0: 0, 1: 0}
        impressions = {0: 0, 1: 0}
        for arm in arms:
            bit = arm["design_code"][factor]
            rows = arm_rows.get(arm["arm_id"], [])
            impressions[bit] += len(rows)
            clicks[bit] += sum(int(r[outcome_column]) for r in rows)
        if not impressions[0] or not impressions[1]:
            continue
        ctr0 = clicks[0] / impressions[0]
        ctr1 = clicks[1] / impressions[1]
        effect = ctr1 - ctr0
        se = math.sqrt(
            ctr0 * (1 - ctr0) / impressions[0] + ctr1 * (1 - ctr1) / impressions[1]
        )
        z = abs(effect) / max(se, 1e-12)
        significant = z > 1.96 and abs(effect) > practical_threshold
        results.append({
            "factor_id": factor,
            "ctr_level_0": round(ctr0, 6),
            "ctr_level_1": round(ctr1, 6),
            "component_effect": round(effect, 6),
            "standard_error": round(se, 6),
            "significant": significant,
            "evidence_level": "COMPONENT_EFFECT" if significant else "EXPERIMENT_INCONCLUSIVE",
        })
    return results
