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

import numpy as np


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
    if len(set(factor_ids)) != len(factor_ids) or any(
        not str(value) for value in factor_ids
    ):
        raise ValueError("factor_ids must be non-empty and unique")
    if (
        not isinstance(traffic_budget, int)
        or isinstance(traffic_budget, bool)
        or traffic_budget <= 0
    ):
        raise ValueError("traffic_budget must be a positive integer")
    k = len(factor_ids)
    if k <= 3:
        matrix = _full_factorial(k)
        design_type = "full_factorial"
    elif k <= 5:
        matrix = _fractional_resolution_iv(k)
        design_type = "fractional_factorial_resolution_iv"
    else:
        raise ValueError("more than 5 factors: run a screening stage first")

    if max_arms < 1:
        raise ValueError("max_arms must be positive")
    if len(matrix) > max_arms:
        raise ValueError(
            f"max_arms={max_arms} cannot support the required {len(matrix)}-arm "
            f"{design_type}; refusing a non-identifiable truncated design"
        )

    coded = np.asarray(matrix, dtype=float) * 2.0 - 1.0
    design_matrix = np.column_stack((np.ones(len(matrix)), coded))
    rank = int(np.linalg.matrix_rank(design_matrix))
    condition_number = float(np.linalg.cond(design_matrix))
    correlations = np.corrcoef(coded, rowvar=False) if k > 1 else np.asarray([[1.0]])
    balance = {
        factor: {
            "level_0": int(sum(row[j] == 0 for row in matrix)),
            "level_1": int(sum(row[j] == 1 for row in matrix)),
        }
        for j, factor in enumerate(factor_ids)
    }
    aliases = []
    for left in range(k):
        for right in range(left + 1, k):
            correlation = float(correlations[left, right])
            if abs(correlation) > 1.0 - 1e-12:
                aliases.append(
                    {
                        "left": factor_ids[left],
                        "right": factor_ids[right],
                        "relationship": "identical" if correlation > 0 else "opposite",
                    }
                )

    guardrail_risk = guardrail_risk or {}
    engineering_cost = engineering_cost or {}
    uncertainty = uncertainty or {}

    arms = []
    per_arm = max(traffic_budget // len(matrix), 1)
    for index, bits in enumerate(matrix):
        arms.append(
            {
                "arm_id": f"arm-{index:02d}",
                "design_code": {factor: bit for factor, bit in zip(factor_ids, bits)},
                "planned_impressions": per_arm,
                "is_control": all(bit == 0 for bit in bits),
            }
        )

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
        "design_diagnostics": {
            "model_columns": ["intercept", *factor_ids],
            "rank": rank,
            "full_column_rank": rank == k + 1,
            "factor_balance": balance,
            "factor_correlation_matrix": correlations.tolist(),
            "condition_number": condition_number,
            "main_effect_aliases": aliases,
        },
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
    """Estimate adjusted main effects with the complete Binomial-GLM matrix."""
    if not arms or not factor_ids:
        raise ValueError("arms and factor_ids must be non-empty")
    if len(set(factor_ids)) != len(factor_ids):
        raise ValueError("factor_ids must be unique")
    if not math.isfinite(practical_threshold) or practical_threshold < 0:
        raise ValueError("practical_threshold must be finite and non-negative")
    design_rows: list[list[float]] = []
    successes: list[float] = []
    totals: list[float] = []
    for arm in arms:
        try:
            design_rows.append(
                [
                    1.0,
                    *(
                        2.0 * float(arm["design_code"][factor]) - 1.0
                        for factor in factor_ids
                    ),
                ]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid design code: {exc}") from exc
        rows = arm_rows.get(arm["arm_id"], [])
        outcomes = [row.get(outcome_column) for row in rows]
        if any(value not in (0, 1) for value in outcomes):
            raise ValueError(f"{outcome_column} must be binary 0/1 in every arm")
        totals.append(float(len(rows)))
        successes.append(float(sum(int(value) for value in outcomes)))
    x = np.asarray(design_rows, dtype=float)
    y = np.asarray(successes, dtype=float)
    n = np.asarray(totals, dtype=float)
    if np.any(n <= 0):
        raise ValueError("every design arm must contain outcome rows")
    if int(np.linalg.matrix_rank(x)) < x.shape[1]:
        raise ValueError(
            "component effects are not estimable: design matrix is rank deficient"
        )

    # Aggregated-binomial IRLS with a small ridge used only for numerical
    # stability under near-separation. The intercept is not penalized.
    coefficients = np.zeros(x.shape[1], dtype=float)
    ridge = np.diag([0.0, *([1e-10] * len(factor_ids))])
    for _ in range(100):
        eta = np.clip(x @ coefficients, -30.0, 30.0)
        probability = 1.0 / (1.0 + np.exp(-eta))
        weights = np.maximum(n * probability * (1.0 - probability), 1e-9)
        working = eta + (y - n * probability) / weights
        information = x.T @ (weights[:, None] * x) + ridge
        updated = np.linalg.solve(information, x.T @ (weights * working))
        if float(np.max(np.abs(updated - coefficients))) < 1e-10:
            coefficients = updated
            break
        coefficients = updated
    eta = np.clip(x @ coefficients, -30.0, 30.0)
    probability = 1.0 / (1.0 + np.exp(-eta))
    weights = np.maximum(n * probability * (1.0 - probability), 1e-9)
    covariance = np.linalg.inv(x.T @ (weights[:, None] * x) + ridge)

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
        low = x.copy()
        high = x.copy()
        low[:, j + 1] = -1.0
        high[:, j + 1] = 1.0
        adjusted_low = 1.0 / (1.0 + np.exp(-np.clip(low @ coefficients, -30.0, 30.0)))
        adjusted_high = 1.0 / (1.0 + np.exp(-np.clip(high @ coefficients, -30.0, 30.0)))
        effect = float(np.mean(adjusted_high - adjusted_low))
        log_odds_ratio = 2.0 * float(coefficients[j + 1])
        log_odds_standard_error = 2.0 * math.sqrt(
            max(float(covariance[j + 1, j + 1]), 0.0)
        )
        z = abs(log_odds_ratio) / max(log_odds_standard_error, 1e-12)
        significant = z > 1.96 and abs(effect) > practical_threshold
        results.append(
            {
                "factor_id": factor,
                "ctr_level_0": round(ctr0, 6),
                "ctr_level_1": round(ctr1, 6),
                "component_effect": round(effect, 6),
                "standard_error": round(log_odds_standard_error, 6),
                "standard_error_scale": "log_odds_ratio",
                "log_odds_ratio": round(log_odds_ratio, 6),
                "analysis_model": "aggregated_binomial_logistic_glm_full_design_matrix",
                "design_matrix_rank": int(np.linalg.matrix_rank(x)),
                "significant": significant,
                "evidence_level": "COMPONENT_EFFECT"
                if significant
                else "EXPERIMENT_INCONCLUSIVE",
            }
        )
    return results
