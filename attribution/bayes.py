"""Bayesian estimation layer.

Implements, with numpy only:
- Beta-Binomial bundle A/B with harm/benefit/equivalence decision rules
- Hierarchical partial-pooling HTE across segments (analytic shrinkage)
- Treatment x factor moderation scan with prior shrinkage (exploratory vs confirmatory)

I/O contract of `bundle_compare` matches the MVP bayes_update.py script,
minus the scipy dependency.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

DEFAULT_DRAWS = 100_000


def beta_posterior(clicks: float, impressions: float, prior: tuple[float, float]) -> tuple[float, float]:
    if impressions < 0 or clicks < 0 or clicks > impressions:
        raise ValueError("invalid impressions/clicks")
    alpha, beta_ = prior
    if alpha <= 0 or beta_ <= 0:
        raise ValueError("prior must contain two positive values")
    return alpha + clicks, beta_ + impressions - clicks


def _compare_draws(
    control_shape: tuple[float, float],
    treatment_shape: tuple[float, float],
    threshold: float,
    draws: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    control_draws = rng.beta(*control_shape, size=draws)
    treatment_draws = rng.beta(*treatment_shape, size=draws)
    effects = treatment_draws - control_draws
    probability_harm = float(np.mean(effects < 0))
    probability_practical_harm = float(np.mean(effects < -threshold))
    probability_practical_benefit = float(np.mean(effects > threshold))
    equivalent = float(np.mean(np.abs(effects) <= threshold))
    interval = np.quantile(effects, [0.025, 0.975])
    if probability_practical_harm >= 0.95:
        decision = "ROLLBACK_RECOMMENDED"
    elif probability_practical_benefit >= 0.95:
        decision = "SHIP_RECOMMENDED"
    elif equivalent >= 0.90:
        decision = "PRACTICALLY_EQUIVALENT"
    else:
        decision = "CONTINUE_DATA_COLLECTION"
    mean_control = max(float(np.mean(control_draws)), 1e-12)
    return {
        "effect_absolute": float(np.mean(effects)),
        "effect_relative": float(np.mean(effects) / mean_control),
        "probability_harm": probability_harm,
        "probability_practical_harm": probability_practical_harm,
        "probability_practical_benefit": probability_practical_benefit,
        "probability_practically_equivalent": equivalent,
        "credible_interval_95": [float(interval[0]), float(interval[1])],
        "decision": decision,
    }


def bundle_compare(
    control: Mapping[str, float],
    treatment: Mapping[str, float],
    prior: tuple[float, float] | tuple[tuple[float, float], tuple[float, float]] = (1.0, 1.0),
    practical_threshold: float = 0.0,
    draws: int = DEFAULT_DRAWS,
    seed: int = 20260809,
) -> dict[str, Any]:
    """Beta-Binomial comparison of two arms on a Bernoulli outcome.

    `prior` may be a single (alpha, beta) applied to both arms, or a pair
    (prior_control, prior_treatment) for experience-informed per-arm priors.
    """
    if practical_threshold < 0:
        raise ValueError("practical_threshold must be non-negative")
    if len(prior) == 2 and isinstance(prior[0], (tuple, list)):  # type: ignore[index]
        prior_c, prior_t = prior  # type: ignore[misc]
    else:
        prior_c = prior_t = prior  # type: ignore[assignment]
    rng = np.random.default_rng(seed)
    control_shape = beta_posterior(control["clicks"], control["impressions"], prior_c)
    treatment_shape = beta_posterior(treatment["clicks"], treatment["impressions"], prior_t)
    result = _compare_draws(control_shape, treatment_shape, practical_threshold, draws, rng)
    result.update({
        "model": "beta_binomial",
        "evidence_level": "BUNDLE_EFFECT",
        "prior": {"control": list(prior_c), "treatment": list(prior_t)},
        "arm_shapes": {"control": list(control_shape), "treatment": list(treatment_shape)},
        "draws": draws,
    })
    return result


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _student_t_logpdf(x: float, df: float) -> float:
    return (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
            - 0.5 * math.log(df * math.pi) - (df + 1) / 2 * math.log(1 + x * x / df))


def _student_t_cdf(t: float, df: float = 5.0) -> float:
    """Student-t CDF by Simpson integration (no scipy dependency).

    Heavy-tailed likelihood for moderation decisions under structural
    mismatch: tails decay polynomially, so outlying segments inflate the
    interval instead of shifting its center — the 'right value, wrong
    interval' failure mode of the Gaussian approximation.
    """
    if t <= 0:
        return 1.0 - _student_t_cdf(-t, df)
    n = 1200  # even number of Simpson panels; error << 1e-6 for df>=3
    h = t / n
    total = math.exp(_student_t_logpdf(0.0, df)) + math.exp(_student_t_logpdf(t, df))
    for i in range(1, n):
        weight = 4.0 if i % 2 else 2.0
        total += weight * math.exp(_student_t_logpdf(i * h, df))
    return min(1.0, 0.5 + total * h / 3.0)


def estimate_hte(
    segments: Sequence[Mapping[str, Any]],
    prior: tuple[float, float] = (1.0, 1.0),
    practical_threshold: float = 0.005,
    moderation_threshold: float = 0.005,
    draws: int = 50_000,
    seed: int = 20260809,
    discovery: bool = False,
    shrinkage_strength: float | None = None,
    likelihood: str = "gaussian",
) -> dict[str, Any]:
    """Hierarchical partial-pooling HTE across segments.

    Each segment supplies {"segment_id", "control": {clicks, impressions},
    "treatment": {...}}. Segment effects are shrunk toward the pooled
    effect in logit space with strength kappa (pseudo-impressions; default
    500, so a 200-impression segment keeps only ~29% of its raw estimate).

    discovery=True marks results as EXPLORATORY_HETEROGENEITY: the same data
    was used to select segments, so claims cannot be promoted.
    """
    rng = np.random.default_rng(seed)
    if not segments:
        raise ValueError("segments must be non-empty")

    # Pooled effect anchor.
    pooled_c = {"clicks": sum(s["control"]["clicks"] for s in segments),
                "impressions": sum(s["control"]["impressions"] for s in segments)}
    pooled_t = {"clicks": sum(s["treatment"]["clicks"] for s in segments),
                "impressions": sum(s["treatment"]["impressions"] for s in segments)}
    pooled_shape_c = beta_posterior(pooled_c["clicks"], pooled_c["impressions"], prior)
    pooled_shape_t = beta_posterior(pooled_t["clicks"], pooled_t["impressions"], prior)
    pooled_rate_c = pooled_shape_c[0] / sum(pooled_shape_c)
    pooled_rate_t = pooled_shape_t[0] / sum(pooled_shape_t)
    pooled_effect_logit = _logit(pooled_rate_t) - _logit(pooled_rate_c)
    # logit -> probability first-order derivative at the pooled baseline rate.
    scale = pooled_rate_c * (1.0 - pooled_rate_c)

    sizes = [s["control"]["impressions"] + s["treatment"]["impressions"] for s in segments]
    if shrinkage_strength is None:
        shrinkage_strength = 500.0
    if likelihood not in ("gaussian", "student_t"):
        raise ValueError("likelihood must be 'gaussian' or 'student_t'")
    tail_cdf = _normal_cdf if likelihood == "gaussian" else _student_t_cdf

    pooled_effect_prob = pooled_rate_t - pooled_rate_c
    pooled_draws_c = rng.beta(*pooled_shape_c, size=draws)
    pooled_draws_t = rng.beta(*pooled_shape_t, size=draws)
    pooled_draws = pooled_draws_t - pooled_draws_c

    results: list[dict[str, Any]] = []
    for seg, n in zip(segments, sizes):
        shape_c = beta_posterior(seg["control"]["clicks"], seg["control"]["impressions"], prior)
        shape_t = beta_posterior(seg["treatment"]["clicks"], seg["treatment"]["impressions"], prior)
        raw_logit = _logit(shape_t[0] / sum(shape_t)) - _logit(shape_c[0] / sum(shape_c))
        weight = n / (n + shrinkage_strength)
        weight * raw_logit + (1 - weight) * pooled_effect_logit

        # Posterior draws for the raw segment effect (probability scale).
        draws_c = rng.beta(*shape_c, size=draws)
        draws_t = rng.beta(*shape_t, size=draws)
        raw_effects = draws_t - draws_c
        raw_mean = float(np.mean(raw_effects))
        raw_se = float(np.std(raw_effects))
        # Shrunk posterior on the probability scale: mean = weight*raw +
        # (1-weight)*pooled; se deflates with the same weight.
        shrunk_effect = weight * raw_mean + (1 - weight) * (pooled_effect_logit * scale)
        shrunk_se = max(weight * raw_se, 1e-9)
        interval = np.quantile(raw_effects, [0.025, 0.975])
        # Moderation: does this segment differ from the pooled effect?
        moderation_raw = raw_mean - pooled_effect_prob
        moderation_shrunk = shrunk_effect - pooled_effect_prob
        results.append({
            "segment_id": seg["segment_id"],
            "impressions": int(n),
            "effect_raw": raw_mean,
            "effect_shrunk": float(shrunk_effect),
            "standard_error_raw": raw_se,
            "standard_error_shrunk": float(shrunk_se),
            "shrinkage_weight": float(weight),
            "probability_practical_harm": float(np.mean(raw_effects < -practical_threshold)),
            "probability_practical_benefit": float(np.mean(raw_effects > practical_threshold)),
            "shrunk_probability_practical_harm": tail_cdf((-practical_threshold - shrunk_effect) / shrunk_se),
            "moderation_raw": float(moderation_raw),
            "moderation_shrunk": float(moderation_shrunk),
            "prob_moderation_worse_raw": float(np.mean((raw_effects - pooled_draws) < -moderation_threshold)),
            "prob_moderation_worse_shrunk": tail_cdf((-moderation_threshold - moderation_shrunk) / shrunk_se),
            "credible_interval_95": [float(interval[0]), float(interval[1])],
            "evidence_level": "EXPLORATORY_HETEROGENEITY" if discovery else "HETEROGENEOUS_TREATMENT_EFFECT",
        })
    return {
        "model": "hierarchical_beta_binomial_partial_pooling",
        "likelihood": likelihood,
        "pooled_effect_logit": float(pooled_effect_logit),
        "shrinkage_strength": float(shrinkage_strength),
        "discovery_mode": discovery,
        "segments": results,
    }


def estimate_hte_nested(
    segments: Sequence[Mapping[str, Any]],
    group_of,
    prior: tuple[float, float] = (1.0, 1.0),
    practical_threshold: float = 0.005,
    moderation_threshold: float = 0.005,
    draws: int = 20_000,
    seed: int = 20260811,
    kappa_group: float = 1000.0,
    kappa_cell: float = 500.0,
    likelihood: str = "gaussian",
) -> dict[str, Any]:
    """Nested (two-level) partial pooling: cell -> factor-group marginal -> pooled.

    Flat pooling shrinks every cell toward the grand mean, which over-shrinks
    cells whose factor group genuinely deviates. The nested layer first
    shrinks each group's marginal effect toward the pooled effect (kappa_group),
    then shrinks each cell toward its own group's shrunk effect (kappa_cell).
    When true moderation lives at the group level, cells inside the harmful
    group keep the signal while unrelated small cells still collapse to ~0.
    """
    rng = np.random.default_rng(seed)
    if not segments:
        raise ValueError("segments must be non-empty")
    tail_cdf = _normal_cdf if likelihood == "gaussian" else _student_t_cdf

    def rate(shape):
        return shape[0] / sum(shape)

    def agg(counts):
        c = {"clicks": sum(x["control"]["clicks"] for x in counts),
             "impressions": sum(x["control"]["impressions"] for x in counts)}
        t = {"clicks": sum(x["treatment"]["clicks"] for x in counts),
             "impressions": sum(x["treatment"]["impressions"] for x in counts)}
        sc = beta_posterior(c["clicks"], c["impressions"], prior)
        st = beta_posterior(t["clicks"], t["impressions"], prior)
        return sc, st, c["impressions"] + t["impressions"]

    sc0, st0, _ = agg(list(segments))
    pooled_logit = _logit(rate(st0)) - _logit(rate(sc0))
    pooled_prob = rate(st0) - rate(sc0)
    scale = rate(sc0) * (1 - rate(sc0))

    groups: dict[Any, list[Mapping[str, Any]]] = {}
    for s in segments:
        groups.setdefault(group_of(s), []).append(s)
    group_shrunk_logit: dict[Any, float] = {}
    group_sizes: dict[Any, int] = {}
    for g, members in groups.items():
        sc, st, n = agg(members)
        raw = _logit(rate(st)) - _logit(rate(sc))
        w = n / (n + kappa_group)
        group_shrunk_logit[g] = w * raw + (1 - w) * pooled_logit
        group_sizes[g] = n

    results: list[dict[str, Any]] = []
    for seg in segments:
        g = group_of(seg)
        n = seg["control"]["impressions"] + seg["treatment"]["impressions"]
        sc = beta_posterior(seg["control"]["clicks"], seg["control"]["impressions"], prior)
        st = beta_posterior(seg["treatment"]["clicks"], seg["treatment"]["impressions"], prior)
        raw_logit = _logit(rate(st)) - _logit(rate(sc))
        w = n / (n + kappa_cell)
        w * raw_logit + (1 - w) * group_shrunk_logit[g]

        draws_c = rng.beta(*sc, size=draws)
        draws_t = rng.beta(*st, size=draws)
        raw_effects = draws_t - draws_c
        raw_mean, raw_se = float(np.mean(raw_effects)), float(np.std(raw_effects))
        nested_effect = w * raw_mean + (1 - w) * (group_shrunk_logit[g] * scale)
        nested_se = max(w * raw_se, 1e-9)
        moderation = nested_effect - pooled_prob
        results.append({
            "segment_id": seg["segment_id"],
            "group": str(g),
            "impressions": int(n),
            "effect_raw": raw_mean,
            "effect_nested": float(nested_effect),
            "standard_error_nested": float(nested_se),
            "nested_weight": float(w),
            "group_effect_shrunk_prob": float(group_shrunk_logit[g] * scale),
            "moderation_nested": float(moderation),
            "prob_moderation_worse_nested": tail_cdf((-moderation_threshold - moderation) / nested_se),
            "evidence_level": "HETEROGENEOUS_TREATMENT_EFFECT",
        })
    return {
        "model": "nested_two_level_partial_pooling",
        "likelihood": likelihood,
        "pooled_effect_logit": float(pooled_logit),
        "kappa_group": float(kappa_group),
        "kappa_cell": float(kappa_cell),
        "groups": {str(g): {"shrunk_logit": group_shrunk_logit[g], "impressions": group_sizes[g]}
                   for g in groups},
        "segments": results,
    }


def moderation_scan(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str,
    outcome_column: str,
    candidate_factors: Sequence[str],
    prior: tuple[float, float] = (1.0, 1.0),
    practical_threshold: float = 0.005,
    seed: int = 20260809,
    discovery: bool = True,
) -> list[dict[str, Any]]:
    """Scan T x Z moderation for candidate binary/categorical factors.

    For each factor value, estimate the within-level treatment effect and
    shrink toward the pooled effect. Returns candidates sorted by a score
    combining practical-harm probability, effect size and coverage.
    """
    pooled_c = {"clicks": sum(int(r[outcome_column]) for r in rows if r[treatment_column] == 0),
                "impressions": sum(1 for r in rows if r[treatment_column] == 0)}
    pooled_t = {"clicks": sum(int(r[outcome_column]) for r in rows if r[treatment_column] == 1),
                "impressions": sum(1 for r in rows if r[treatment_column] == 1)}
    pooled = bundle_compare(pooled_c, pooled_t, prior, practical_threshold, seed=seed)
    pooled_effect = pooled["effect_absolute"]

    candidates: list[dict[str, Any]] = []
    for factor in candidate_factors:
        values = sorted({str(r.get(factor, "<missing>")) for r in rows})
        for value in values:
            subset = [r for r in rows if str(r.get(factor, "<missing>")) == value]
            c = {"clicks": sum(int(r[outcome_column]) for r in subset if r[treatment_column] == 0),
                 "impressions": sum(1 for r in subset if r[treatment_column] == 0)}
            t = {"clicks": sum(int(r[outcome_column]) for r in subset if r[treatment_column] == 1),
                 "impressions": sum(1 for r in subset if r[treatment_column] == 1)}
            if c["impressions"] < 30 or t["impressions"] < 30:
                continue
            comp = bundle_compare(c, t, prior, practical_threshold, seed=seed)
            moderation = comp["effect_absolute"] - pooled_effect
            score = (
                max(comp["probability_practical_harm"], comp["probability_practical_benefit"])
                * abs(moderation)
                * math.sqrt(c["impressions"] + t["impressions"])
            )
            candidates.append({
                "factor_id": factor,
                "factor_value": value,
                "segment_effect": comp["effect_absolute"],
                "pooled_effect": pooled_effect,
                "moderation": moderation,
                "probability_practical_harm": comp["probability_practical_harm"],
                "impressions": c["impressions"] + t["impressions"],
                "moderation_score": score,
                "evidence_level": "EXPLORATORY_HETEROGENEITY" if discovery else "HETEROGENEOUS_TREATMENT_EFFECT",
            })
    return sorted(candidates, key=lambda item: abs(item["moderation_score"]), reverse=True)
