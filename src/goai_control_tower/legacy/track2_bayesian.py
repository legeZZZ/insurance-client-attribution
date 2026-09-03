"""Bayesian inference core for Track 2: Beta-Binomial posterior, empirical Bayes shrinkage, and decision guards."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import beta as beta_dist


# ---------------------------------------------------------------------------
# Beta-Binomial posterior
# ---------------------------------------------------------------------------

def beta_posterior(
    clicks: int,
    impressions: int,
    prior: Tuple[float, float] = (1.0, 1.0),
) -> Tuple[float, float]:
    """Return (alpha, beta) parameters for the posterior Beta distribution."""
    if impressions < 0 or clicks < 0 or clicks > impressions:
        raise ValueError("invalid impressions/clicks: %d / %d" % (clicks, impressions))
    a, b = prior
    return a + clicks, b + impressions - clicks


def posterior_summary(
    shape: Tuple[float, float],
    credible_mass: float = 0.95,
) -> Dict[str, Any]:
    """Summarize a Beta distribution: mean, mode, variance, credible interval."""
    a, b = shape
    mean = a / (a + b)
    mode = (a - 1) / (a + b - 2) if a > 1 and b > 1 else None
    variance = a * b / ((a + b) ** 2 * (a + b + 1))
    lower = (1 - credible_mass) / 2
    ci = beta_dist.ppf([lower, 1 - lower], a, b)
    return {
        "alpha": a,
        "beta": b,
        "mean": float(mean),
        "mode": float(mode) if mode is not None else None,
        "variance": float(variance),
        "std": float(math.sqrt(variance)),
        "ci_%d" % int(credible_mass * 100): [float(ci[0]), float(ci[1])],
    }


# ---------------------------------------------------------------------------
# Two-arm comparison via Monte-Carlo
# ---------------------------------------------------------------------------

def compare_groups(
    control: Dict[str, int],
    treatment: Dict[str, int],
    prior: Tuple[float, float] = (1.0, 1.0),
    threshold: float = 0.0,
    draws: int = 200_000,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Compare two groups using Beta-Binomial posterior sampling.

    Parameters
    ----------
    control : {"clicks": int, "impressions": int}
    treatment : {"clicks": int, "impressions": int}
    prior : (alpha, beta) default Beta(1,1)
    threshold : practical significance threshold (absolute)
    draws : Monte Carlo sample size
    seed : RNG seed

    Returns
    -------
    dict with effect estimates, probabilities, credible interval, and decision.
    """
    rng = np.random.default_rng(seed)
    c_shape = beta_posterior(control["clicks"], control["impressions"], prior)
    t_shape = beta_posterior(treatment["clicks"], treatment["impressions"], prior)

    c_draws = beta_dist.rvs(*c_shape, size=draws, random_state=rng)
    t_draws = beta_dist.rvs(*t_shape, size=draws, random_state=rng)
    effects = t_draws - c_draws

    prob_harm = float(np.mean(effects < 0))
    prob_practical_harm = float(np.mean(effects < -threshold))
    prob_practical_benefit = float(np.mean(effects > threshold))
    prob_equivalent = float(np.mean(np.abs(effects) <= threshold))
    ci = np.quantile(effects, [0.025, 0.975])
    mean_effect = float(np.mean(effects))
    mean_control = float(np.mean(c_draws))

    # Bayesian decision guard
    if prob_practical_harm >= 0.95:
        decision = "ROLLBACK_RECOMMENDED"
    elif prob_practical_benefit >= 0.95:
        decision = "SHIP_RECOMMENDED"
    elif prob_equivalent >= 0.90:
        decision = "PRACTICALLY_EQUIVALENT"
    else:
        decision = "CONTINUE_DATA_COLLECTION"

    return {
        "effect_absolute": round(mean_effect, 6),
        "effect_relative": round(mean_effect / max(mean_control, 1e-12), 6),
        "probability_harm": round(prob_harm, 6),
        "probability_practical_harm": round(prob_practical_harm, 6),
        "probability_practical_benefit": round(prob_practical_benefit, 6),
        "probability_practically_equivalent": round(prob_equivalent, 6),
        "credible_interval_95": [round(float(ci[0]), 6), round(float(ci[1]), 6)],
        "decision": decision,
        "posterior_control": posterior_summary(c_shape),
        "posterior_treatment": posterior_summary(t_shape),
        "prior": {"alpha": prior[0], "beta": prior[1]},
        "draws": draws,
    }


# ---------------------------------------------------------------------------
# Empirical Bayes shrinkage for small subgroups
# ---------------------------------------------------------------------------

def empirical_bayes_prior(
    groups: Sequence[Dict[str, Any]],
    weight_field: str = "impressions",
) -> Tuple[float, float]:
    """Estimate a Beta prior from pooled group data using method of moments.

    This is useful when many subgroups have small sample sizes.
    The pooled prior pulls extreme small-group estimates toward the global mean.
    """
    total_clicks = sum(g["clicks"] for g in groups)
    total_impressions = sum(g[weight_field] for g in groups)
    if total_impressions == 0:
        return (1.0, 1.0)
    p_pool = total_clicks / total_impressions
    # Method of moments for Beta(a, b) given mean and overdispersion heuristic
    # We use a conservative prior strength equivalent to ~100 impressions
    strength = max(100.0, total_impressions / len(groups) if groups else 100.0)
    a = p_pool * strength
    b = (1 - p_pool) * strength
    return (max(a, 0.5), max(b, 0.5))


def shrunken_subgroup_estimate(
    group: Dict[str, Any],
    global_prior: Tuple[float, float],
    weight_field: str = "impressions",
) -> Dict[str, Any]:
    """Compute a shrunken posterior for a subgroup using empirical Bayes.

    The shrinkage weight increases with sample size:
        w = n / (n + prior_strength)
    """
    n = group.get(weight_field, 0)
    clicks = group.get("clicks", 0)
    prior_a, prior_b = global_prior
    prior_strength = prior_a + prior_b

    # Shrinkage weight
    w = n / (n + prior_strength) if (n + prior_strength) > 0 else 0.0

    # Posterior with empirical Bayes prior
    post_a, post_b = beta_posterior(clicks, n, global_prior)
    summary = posterior_summary((post_a, post_b))
    summary["shrinkage_weight"] = round(w, 6)
    summary["raw_rate"] = round(clicks / n, 6) if n > 0 else 0.0
    summary["subgroup_size"] = n
    return summary


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------

def prior_sensitivity(
    control: Dict[str, int],
    treatment: Dict[str, int],
    priors: Optional[Sequence[Tuple[float, float]]] = None,
    threshold: float = 0.0,
    draws: int = 50_000,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run the same comparison under multiple priors to assess robustness."""
    if priors is None:
        # Uninformative, weakly informative, moderately informative
        priors = [(1.0, 1.0), (5.0, 5.0), (10.0, 10.0), (50.0, 50.0)]
    results = []
    rng = np.random.default_rng(seed)
    for prior in priors:
        result = compare_groups(control, treatment, prior, threshold, draws, seed=int(rng.integers(0, 2**31)))
        results.append({
            "prior_alpha": prior[0],
            "prior_beta": prior[1],
            "decision": result["decision"],
            "effect_absolute": result["effect_absolute"],
            "probability_practical_harm": result["probability_practical_harm"],
            "probability_practical_benefit": result["probability_practical_benefit"],
        })
    return results


# ---------------------------------------------------------------------------
# Heterogeneous treatment effect (HTE) ranking for factor candidates
# ---------------------------------------------------------------------------

def rank_factor_candidates(
    factors: Sequence[Dict[str, Any]],
    global_prior: Tuple[float, float] = (1.0, 1.0),
    threshold: float = 0.0,
    draws: int = 100_000,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Rank factor candidates by their posterior probability of practical harm/benefit.

    Each factor must provide:
        factor_id, control {clicks, impressions}, treatment {clicks, impressions},
        stability (0-1), experimentability (0-1)
    """
    rng = np.random.default_rng(seed)
    ranked = []
    for factor in factors:
        comp = compare_groups(
            factor["control"],
            factor["treatment"],
            global_prior,
            threshold,
            draws,
            int(rng.integers(0, 2**31)),
        )
        eligible = factor["control"]["impressions"] + factor["treatment"]["impressions"]
        stability = float(factor.get("stability", 1.0))
        experimentability = float(factor.get("experimentability", 1.0))

        # Factor score: probability of practical harm * expected absolute impact * stability * experimentability
        expected_abs_impact = abs(comp["effect_absolute"]) * eligible
        factor_score = (
            max(comp["probability_practical_harm"], comp["probability_practical_benefit"])
            * expected_abs_impact
            * stability
            * experimentability
        )

        ranked.append({
            "factor_id": factor["factor_id"],
            "factor_name": factor.get("factor_name", factor["factor_id"]),
            "effect_absolute": comp["effect_absolute"],
            "effect_relative": comp["effect_relative"],
            "probability_harm": comp["probability_harm"],
            "probability_practical_harm": comp["probability_practical_harm"],
            "probability_practical_benefit": comp["probability_practical_benefit"],
            "credible_interval_95": comp["credible_interval_95"],
            "eligible_impressions": eligible,
            "expected_absolute_impact": round(expected_abs_impact, 2),
            "stability": stability,
            "experimentability": experimentability,
            "factor_score": round(factor_score, 2),
            "evidence_level": "HETEROGENEITY_CANDIDATE",
            "decision": comp["decision"],
        })

    return sorted(ranked, key=lambda x: x["factor_score"], reverse=True)


# ---------------------------------------------------------------------------
# Experiment design: expected information gain
# ---------------------------------------------------------------------------

def expected_information_gain(
    prior_shape_control: Tuple[float, float],
    prior_shape_treatment: Tuple[float, float],
    proposed_n_per_arm: int,
    true_effect: Optional[float] = None,
) -> Dict[str, Any]:
    """Estimate the expected information gain from running an experiment.

    Uses prior predictive simulation to estimate how much the posterior
    precision will improve after collecting proposed_n_per_arm observations.
    """
    a_c, b_c = prior_shape_control
    a_t, b_t = prior_shape_treatment

    # Prior predictive mean rates
    p_c = a_c / (a_c + b_c)
    p_t = a_t / (a_t + b_t)
    prior_effect = p_t - p_c

    # Prior precision (inverse variance)
    var_c_prior = a_c * b_c / ((a_c + b_c) ** 2 * (a_c + b_c + 1))
    var_t_prior = a_t * b_t / ((a_t + b_t) ** 2 * (a_t + b_t + 1))
    prior_precision = 1.0 / (var_c_prior + var_t_prior)

    # Expected posterior precision after proposed_n_per_arm
    # For Binomial, posterior variance ≈ p(1-p) / n
    var_c_post = p_c * (1 - p_c) / proposed_n_per_arm
    var_t_post = p_t * (1 - p_t) / proposed_n_per_arm
    post_precision = 1.0 / (var_c_post + var_t_post)

    # Information gain
    information_gain = post_precision / max(prior_precision, 1e-12)

    # Probability of reaching a decision (practical harm or benefit)
    if true_effect is not None:
        # Simulate outcomes under assumed true effect
        # This is a simplified approximation
        se = math.sqrt(p_c * (1 - p_c) / proposed_n_per_arm + p_t * (1 - p_t) / proposed_n_per_arm)
        z_threshold = 1.96  # 95% credible
        prob_detect = 1.0 if abs(true_effect) > z_threshold * se else abs(true_effect) / (z_threshold * se)
        prob_detect = min(1.0, max(0.0, prob_detect))
    else:
        prob_detect = None

    return {
        "proposed_n_per_arm": proposed_n_per_arm,
        "prior_effect": round(prior_effect, 6),
        "prior_precision": round(prior_precision, 6),
        "expected_post_precision": round(post_precision, 6),
        "information_gain_ratio": round(information_gain, 6),
        "prob_detect_practical_effect": round(prob_detect, 6) if prob_detect is not None else None,
    }
