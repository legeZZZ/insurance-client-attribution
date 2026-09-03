"""Experiment designer: select next experiments based on information gain, cost, and business loss."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .track2_bayesian import beta_posterior, compare_groups, expected_information_gain


# ---------------------------------------------------------------------------
# Experiment design candidate
# ---------------------------------------------------------------------------

def design_factorial_experiment(
    factors: Sequence[Dict[str, Any]],
    base_rate: float = 0.1,
    mde: float = 0.05,
    alpha: float = 0.05,
    target_power: float = 0.80,
    max_factors: int = 4,
) -> Dict[str, Any]:
    """Design a factorial or partial factorial experiment from ranked factors.

    Selects top factors and computes required sample size per arm.
    """
    # Select top factors that are experimentable
    selected = [f for f in factors if f.get("experimentability", 0) >= 0.5][:max_factors]

    # Normal approximation for binary outcome
    z_alpha = 1.96 if alpha == 0.05 else 1.96
    z_power = 0.84 if target_power == 0.80 else 0.84
    variance = max(base_rate * (1.0 - base_rate), 0.01)
    required_per_arm = int(math.ceil(2.0 * (z_alpha + z_power) ** 2 * variance / max(mde ** 2, 1e-9)))

    designs = []
    if len(selected) <= 3:
        # Full factorial: 2^k arms
        design_type = "full_factorial"
        num_arms = 2 ** len(selected)
        total_required = required_per_arm * num_arms
    else:
        # Partial factorial or sequential
        design_type = "sequential_pairwise"
        num_arms = 2 * len(selected)  # Each factor tested independently in pairs
        total_required = required_per_arm * 2 * len(selected)

    for factor in selected:
        designs.append({
            "factor_id": factor["factor_id"],
            "factor_name": factor.get("factor_name", factor["factor_id"]),
            "expected_effect": factor.get("shrunken_effect", factor.get("raw_effect", 0)),
            "experimentability": factor.get("experimentability", 0.5),
        })

    return {
        "design_type": design_type,
        "num_arms": num_arms,
        "required_per_arm": required_per_arm,
        "total_sample_required": total_required,
        "selected_factors": designs,
        "alpha": alpha,
        "target_power": target_power,
        "mde": mde,
        "recommendation": "Run %s experiment with %d arms, %d per arm" % (design_type, num_arms, required_per_arm),
    }


# ---------------------------------------------------------------------------
# Optimal experiment selection via information gain
# ---------------------------------------------------------------------------

def select_next_experiment(
    candidates: Sequence[Dict[str, Any]],
    control_stats: Dict[str, int],
    prior: Tuple[float, float] = (1.0, 1.0),
    lambda_business_loss: float = 1.0,
    mu_experiment_cost: float = 0.1,
    max_n_per_arm: int = 100_000,
) -> Dict[str, Any]:
    """Select the best next experiment by maximizing:

        design_score = EIG - lambda * expected_business_loss - mu * experiment_cost

    Parameters
    ----------
    candidates : list of factor candidates with control/treatment stats
    control_stats : {"clicks": int, "impressions": int}
    prior : Beta prior for baseline
    lambda_business_loss : weight on expected business loss
    mu_experiment_cost : weight on experiment cost per sample
    max_n_per_arm : maximum samples to consider

    Returns
    -------
    dict with ranked experiment proposals
    """
    c_clicks = control_stats["clicks"]
    c_impressions = control_stats["impressions"]
    prior_control = beta_posterior(c_clicks, c_impressions, prior)

    proposals = []
    for candidate in candidates:
        treat = candidate["treatment"]
        prior_treatment = beta_posterior(treat["clicks"], treat["impressions"], prior)

        # Try different sample sizes
        best_score = float("-inf")
        best_n = None
        best_eig = None

        for n_per_arm in [1000, 5000, 10_000, 20_000, 50_000]:
            if n_per_arm > max_n_per_arm:
                continue
            eig = expected_information_gain(prior_control, prior_treatment, n_per_arm)
            info_gain = eig["information_gain_ratio"]

            # Expected business loss: if we ship and it's harmful
            raw_effect = candidate.get("shrunken_effect", candidate.get("raw_effect", 0))
            prob_harm = candidate.get("probability_practical_harm", 0.5)
            expected_loss = prob_harm * abs(raw_effect) * n_per_arm * 2  # rough proxy

            # Experiment cost
            experiment_cost = mu_experiment_cost * n_per_arm * 2

            score = info_gain - lambda_business_loss * expected_loss / 1e6 - experiment_cost / 1e6
            if score > best_score:
                best_score = score
                best_n = n_per_arm
                best_eig = eig

        proposals.append({
            "factor_id": candidate["factor_id"],
            "factor_name": candidate.get("factor_name", candidate["factor_id"]),
            "best_n_per_arm": best_n,
            "expected_information_gain": best_eig["information_gain_ratio"] if best_eig else None,
            "design_score": round(best_score, 6),
            "expected_effect": raw_effect,
        })

    proposals.sort(key=lambda x: x["design_score"], reverse=True)
    return {
        "proposals": proposals,
        "top_proposal": proposals[0] if proposals else None,
        "selection_criteria": "maximize information gain - business loss - experiment cost",
    }


# ---------------------------------------------------------------------------
# Assurance computation
# ---------------------------------------------------------------------------

def compute_assurance(
    prior_control: Tuple[float, float],
    prior_treatment: Tuple[float, float],
    proposed_n_per_arm: int,
    true_effect: Optional[float] = None,
    threshold: float = 0.0,
    n_simulations: int = 10_000,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute assurance metrics for an experimental design.

    Simulates the experiment under the prior predictive distribution
    and reports the probability of correct decisions.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    a_c, b_c = prior_control
    a_t, b_t = prior_treatment

    p_c = a_c / (a_c + b_c)
    p_t = a_t / (a_t + b_t)

    # If true effect not provided, use prior mean difference
    if true_effect is None:
        true_effect = p_t - p_c

    decisions = []
    ci_covers = []
    detected_harm = []
    detected_benefit = []

    for _ in range(n_simulations):
        # Simulate data under prior predictive
        ctrl_clicks = rng.binomial(proposed_n_per_arm, p_c)
        treat_clicks = rng.binomial(proposed_n_per_arm, p_t)

        # Posterior after simulated data
        post_c = beta_posterior(ctrl_clicks, proposed_n_per_arm, prior_control)
        post_t = beta_posterior(treat_clicks, proposed_n_per_arm, prior_treatment)

        # Sample from posterior
        c_samp = rng.beta(*post_c)
        t_samp = rng.beta(*post_t)
        effect = t_samp - c_samp

        # Decision
        if true_effect < -threshold:
            correct = effect < 0
        elif true_effect > threshold:
            correct = effect > 0
        else:
            correct = abs(effect) <= threshold
        decisions.append(correct)

        # CI coverage (approximate)
        se = math.sqrt(
            post_c[0] * post_c[1] / ((post_c[0] + post_c[1]) ** 2 * (post_c[0] + post_c[1] + 1)) +
            post_t[0] * post_t[1] / ((post_t[0] + post_t[1]) ** 2 * (post_t[0] + post_t[1] + 1))
        )
        ci_lower = effect - 1.96 * se
        ci_upper = effect + 1.96 * se
        ci_covers.append(ci_lower <= true_effect <= ci_upper)

        detected_harm.append(effect < -threshold)
        detected_benefit.append(effect > threshold)

    return {
        "n_simulations": n_simulations,
        "proposed_n_per_arm": proposed_n_per_arm,
        "true_effect": true_effect,
        "assurance_correct_decision": round(sum(decisions) / len(decisions), 6),
        "assurance_ci_coverage": round(sum(ci_covers) / len(ci_covers), 6),
        "prob_detect_harm": round(sum(detected_harm) / len(detected_harm), 6),
        "prob_detect_benefit": round(sum(detected_benefit) / len(detected_benefit), 6),
    }
