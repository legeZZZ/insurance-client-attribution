"""Bayesian estimation layer for attribution v5.

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

from .input_validation import validate_binomial_arm, validate_hte_segments

DEFAULT_DRAWS = 100_000


def beta_posterior(
    clicks: float, impressions: float, prior: tuple[float, float]
) -> tuple[float, float]:
    if not math.isfinite(impressions) or not math.isfinite(clicks):
        raise ValueError("impressions/clicks must be finite")
    if impressions < 0 or clicks < 0 or clicks > impressions:
        raise ValueError("invalid impressions/clicks")
    alpha, beta_ = prior
    if not math.isfinite(alpha) or not math.isfinite(beta_):
        raise ValueError("prior values must be finite")
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
    prior: tuple[float, float] | tuple[tuple[float, float], tuple[float, float]] = (
        1.0,
        1.0,
    ),
    practical_threshold: float = 0.0,
    draws: int = DEFAULT_DRAWS,
    seed: int = 20260809,
) -> dict[str, Any]:
    """Beta-Binomial comparison of two arms on a Bernoulli outcome.

    `prior` may be a single (alpha, beta) applied to both arms, or a pair
    (prior_control, prior_treatment) for experience-informed per-arm priors.
    """
    if not math.isfinite(practical_threshold) or practical_threshold < 0:
        raise ValueError("practical_threshold must be finite and non-negative")
    if not isinstance(draws, int) or isinstance(draws, bool) or draws <= 0:
        raise ValueError("draws must be a positive integer")
    control_validated = validate_binomial_arm(control, "control")
    treatment_validated = validate_binomial_arm(treatment, "treatment")
    if len(prior) == 2 and isinstance(prior[0], (tuple, list)):  # type: ignore[index]
        prior_c, prior_t = prior  # type: ignore[misc]
    else:
        prior_c = prior_t = prior  # type: ignore[assignment]
    rng = np.random.default_rng(seed)
    control_shape = beta_posterior(control["clicks"], control["impressions"], prior_c)
    treatment_shape = beta_posterior(
        treatment["clicks"], treatment["impressions"], prior_t
    )
    result = _compare_draws(
        control_shape, treatment_shape, practical_threshold, draws, rng
    )
    result.update(
        {
            "model": "beta_binomial",
            "evidence_level": "BUNDLE_EFFECT",
            "prior": {"control": list(prior_c), "treatment": list(prior_t)},
            "arm_shapes": {
                "control": list(control_shape),
                "treatment": list(treatment_shape),
            },
            "draws": draws,
            "input_validation": {
                "status": "PASS",
                "component": "bundle_compare",
                "used_sample_count": int(
                    control_validated["impressions"]
                    + treatment_validated["impressions"]
                ),
                "excluded_sample_count": 0,
                "exclusion_reasons": [],
                "checks_performed": ["finite", "count_range"],
            },
        }
    )
    return result


def _posterior_effect_draws(
    control: Mapping[str, float],
    treatment: Mapping[str, float],
    prior: tuple[float, float],
    draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw treatment effects directly on the probability-difference scale."""
    shape_c = beta_posterior(control["clicks"], control["impressions"], prior)
    shape_t = beta_posterior(treatment["clicks"], treatment["impressions"], prior)
    return rng.beta(*shape_t, size=draws) - rng.beta(*shape_c, size=draws)


def _effect_summary(draws: np.ndarray, practical_threshold: float) -> dict[str, Any]:
    interval = np.quantile(draws, [0.025, 0.975])
    return {
        "mean": float(np.mean(draws)),
        "standard_error": float(np.std(draws)),
        "credible_interval_95": [float(interval[0]), float(interval[1])],
        "probability_practical_harm": float(np.mean(draws < -practical_threshold)),
        "probability_practical_benefit": float(np.mean(draws > practical_threshold)),
    }


def _estimate_tau2(means: Sequence[float], standard_errors: Sequence[float]) -> float:
    """Estimate between-segment variance on the probability-difference scale."""
    if len(means) < 2:
        return 0.0
    y = np.asarray(means, dtype=float)
    se = np.maximum(np.asarray(standard_errors, dtype=float), 1e-9)
    variance = se**2
    weights = 1.0 / variance
    fixed_mean = float(np.sum(weights * y) / np.sum(weights))
    q = float(np.sum(weights * (y - fixed_mean) ** 2))
    denominator = float(np.sum(weights) - np.sum(weights**2) / np.sum(weights))
    return max((q - (len(y) - 1)) / max(denominator, 1e-12), 0.0)


def _legacy_tau2(
    sizes: Sequence[int], standard_errors: Sequence[float], shrinkage_strength: float
) -> float:
    """Map old pseudo-impression kappa to probability-scale variance."""
    if shrinkage_strength <= 0:
        raise ValueError("shrinkage_strength must be positive")
    implied = [
        max(float(n), 1.0) / shrinkage_strength * max(float(se), 1e-9) ** 2
        for n, se in zip(sizes, standard_errors)
    ]
    return float(np.median(implied)) if implied else 0.0


def _student_t_logpdf(
    values: np.ndarray, location: float, scale: float, nu: float
) -> np.ndarray:
    """Log density for Student-t(location, scale, nu); scale is not its SD."""
    if nu <= 2:
        raise ValueError("student_t_nu must be greater than 2 so variance exists")
    if scale <= 0:
        raise ValueError("Student-t scale must be positive")
    constant = (
        math.lgamma((nu + 1.0) / 2.0)
        - math.lgamma(nu / 2.0)
        - 0.5 * math.log(nu * math.pi)
        - math.log(scale)
    )
    return constant - 0.5 * (nu + 1.0) * np.log1p(
        ((values - location) / scale) ** 2 / nu
    )


def _log_integral_on_grid(log_density: np.ndarray, grid: np.ndarray) -> float:
    maximum = float(np.max(log_density))
    values = np.exp(log_density - maximum)
    integral = float(np.sum((values[:-1] + values[1:]) * np.diff(grid) * 0.5))
    return maximum + math.log(max(integral, 1e-300))


def _student_t_marginal_loglikelihood(
    means: np.ndarray,
    standard_errors: np.ndarray,
    location: float,
    scale: float,
    nu: float,
    grid_points: int = 1201,
) -> float:
    """Numerically integrate Normal(y|theta,se) * t(theta|mu,tau,nu)."""
    total = 0.0
    for mean, standard_error in zip(means, standard_errors):
        radius = 14.0 * max(scale, float(standard_error), 1e-6)
        grid = np.linspace(
            min(location, mean) - radius,
            max(location, mean) + radius,
            grid_points,
        )
        log_likelihood = (
            -0.5 * ((mean - grid) / standard_error) ** 2
            - math.log(standard_error)
            - 0.5 * math.log(2.0 * math.pi)
        )
        total += _log_integral_on_grid(
            log_likelihood + _student_t_logpdf(grid, location, scale, nu), grid
        )
    return total


def _estimate_student_t_scale(
    means: Sequence[float],
    standard_errors: Sequence[float],
    location: float,
    nu: float,
) -> float:
    """Empirical-Bayes MLE of Student-t scale, including a tau=0 boundary."""
    y = np.asarray(means, dtype=float)
    se = np.maximum(np.asarray(standard_errors, dtype=float), 1e-9)
    if len(y) < 2:
        return 0.0
    residual_scale = max(float(np.std(y)), float(np.median(se)), 1e-5)
    upper = max(5.0 * residual_scale, 2.0 * float(np.max(np.abs(y - location))))
    candidates = np.geomspace(residual_scale / 100.0, max(upper, 1e-4), 64)
    scores = [
        _student_t_marginal_loglikelihood(y, se, location, float(value), nu)
        for value in candidates
    ]
    # tau=0 is the degenerate random-effects model theta_i=mu.
    zero_score = float(
        np.sum(
            -0.5 * ((y - location) / se) ** 2
            - np.log(se)
            - 0.5 * math.log(2.0 * math.pi)
        )
    )
    best = int(np.argmax(scores))
    return 0.0 if zero_score >= scores[best] else float(candidates[best])


def _student_t_posterior_draws(
    observed_mean: float,
    observed_se: float,
    location: float,
    scale: float,
    nu: float,
    draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw theta from its explicit Normal-likelihood/Student-t-prior posterior."""
    if scale == 0:
        return np.full(draws, location, dtype=float)
    observed_se = max(float(observed_se), 1e-9)
    radius = 14.0 * max(scale, observed_se, 1e-6)
    grid = np.linspace(
        min(location, observed_mean) - radius,
        max(location, observed_mean) + radius,
        4001,
    )
    log_posterior = -0.5 * (
        (observed_mean - grid) / observed_se
    ) ** 2 + _student_t_logpdf(grid, location, scale, nu)
    probabilities = np.exp(log_posterior - float(np.max(log_posterior)))
    probabilities /= float(np.sum(probabilities))
    sampled = rng.choice(grid, size=draws, p=probabilities)
    return np.clip(sampled, -1.0, 1.0)


def _weighted_quantile(
    values: Sequence[float], weights: Sequence[float], probability: float
) -> float:
    order = np.argsort(np.asarray(values, dtype=float))
    ordered_values = np.asarray(values, dtype=float)[order]
    ordered_weights = np.asarray(weights, dtype=float)[order]
    cumulative = np.cumsum(ordered_weights) / float(np.sum(ordered_weights))
    return float(np.interp(probability, cumulative, ordered_values))


def _student_t_hyperparameter_posterior(
    means: Sequence[float],
    standard_errors: Sequence[float],
    pooled_mean: float,
    pooled_se: float,
    requested_nu: float,
    nu_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Discrete joint posterior for Student-t location, scale and degrees of freedom.

    A weakly informative half-normal prior is used for non-zero ``tau`` and a
    separate 10% prior mass is retained at the zero-heterogeneity boundary.
    The returned components are pruned only after normalization, retaining at
    least 99.5% posterior mass when that fits within 64 components.
    """
    y = np.asarray(means, dtype=float)
    se = np.maximum(np.asarray(standard_errors, dtype=float), 1e-9)
    count = max(len(y), 1)
    location_sd = max(float(pooled_se), float(np.median(se)) / math.sqrt(count), 5e-4)
    location_z = np.linspace(-3.0, 3.0, 7)
    locations = pooled_mean + location_z * location_sd
    location_log_prior = -0.5 * location_z**2
    location_log_prior -= float(
        np.max(location_log_prior)
        + math.log(
            float(np.sum(np.exp(location_log_prior - np.max(location_log_prior))))
        )
    )

    residual_scale = max(float(np.std(y)), float(np.median(se)), 1e-4)
    tau_prior_scale = max(residual_scale, 2.0 * float(np.median(se)), 0.0025)
    tau_low = max(tau_prior_scale / 50.0, 1e-5)
    tau_upper = min(
        max(
            5.0 * tau_prior_scale,
            2.0 * float(np.max(np.abs(y - pooled_mean))),
            0.02,
        ),
        0.5,
    )
    tau_values = np.geomspace(tau_low, tau_upper, 18)
    tau_widths = np.gradient(tau_values)
    tau_log_prior = (
        math.log(0.9)
        + 0.5 * math.log(2.0 / math.pi)
        - math.log(tau_prior_scale)
        - 0.5 * (tau_values / tau_prior_scale) ** 2
        + np.log(tau_widths)
    )

    degrees = sorted(
        {float(value) for value in (nu_grid or (3.0, 4.0, 5.0, 8.0, 15.0, 30.0))}
        | {float(requested_nu)}
    )
    if any(not math.isfinite(value) or value <= 2.0 for value in degrees):
        raise ValueError("nu_grid values must be finite and greater than 2")
    nu_log_prior = -math.log(len(degrees))

    components: list[dict[str, float]] = []
    for location, log_location_prior in zip(locations, location_log_prior):
        zero_log_likelihood = float(
            np.sum(
                -0.5 * ((y - location) / se) ** 2
                - np.log(se)
                - 0.5 * math.log(2.0 * math.pi)
            )
        )
        components.append(
            {
                "location": float(location),
                "scale": 0.0,
                "nu": float(requested_nu),
                "log_weight": float(
                    log_location_prior + math.log(0.1) + zero_log_likelihood
                ),
            }
        )
        for scale, log_tau_prior in zip(tau_values, tau_log_prior):
            for degrees_of_freedom in degrees:
                log_likelihood = _student_t_marginal_loglikelihood(
                    y,
                    se,
                    float(location),
                    float(scale),
                    degrees_of_freedom,
                    grid_points=401,
                )
                components.append(
                    {
                        "location": float(location),
                        "scale": float(scale),
                        "nu": degrees_of_freedom,
                        "log_weight": float(
                            log_location_prior
                            + log_tau_prior
                            + nu_log_prior
                            + log_likelihood
                        ),
                    }
                )

    log_weights = np.asarray([item["log_weight"] for item in components])
    weights = np.exp(log_weights - float(np.max(log_weights)))
    weights /= float(np.sum(weights))
    # Compress the categorical posterior with deterministic stratified
    # resampling. Unlike top-k pruning this preserves both central mass and
    # posterior tails, which are essential for calibrated intervals.
    quadrature_size = min(128, len(components))
    cumulative = np.cumsum(weights)
    positions = (np.arange(quadrature_size, dtype=float) + 0.5) / quadrature_size
    sampled_indexes = np.searchsorted(cumulative, positions)
    retained_indexes, retained_counts = np.unique(sampled_indexes, return_counts=True)
    retained_weights = retained_counts.astype(float) / quadrature_size
    retained: list[dict[str, float]] = []
    for index, weight in zip(retained_indexes, retained_weights):
        item = dict(components[int(index)])
        item.pop("log_weight")
        item["weight"] = float(weight)
        retained.append(item)

    all_scales = [item["scale"] for item in components]
    all_nu = [item["nu"] for item in components]
    all_locations = [item["location"] for item in components]
    return {
        "components": retained,
        "summary": {
            "method": "joint_discrete_hyperparameter_posterior",
            "location_prior": {
                "distribution": "normal",
                "center": float(pooled_mean),
                "standard_deviation": float(location_sd),
            },
            "tau_prior": {
                "distribution": "spike_at_zero_plus_half_normal",
                "zero_mass": 0.1,
                "half_normal_scale": float(tau_prior_scale),
            },
            "nu_grid": degrees,
            "candidate_component_count": len(components),
            "retained_component_count": len(retained),
            "posterior_quadrature_size": quadrature_size,
            "component_compression": "deterministic_stratified_resampling",
            "retained_posterior_mass": 1.0,
            "probability_tau_zero": float(
                sum(
                    weight
                    for item, weight in zip(components, weights)
                    if item["scale"] == 0.0
                )
            ),
            "location_posterior_mean": float(np.sum(weights * all_locations)),
            "tau_posterior_mean": float(np.sum(weights * all_scales)),
            "tau_credible_interval_95": [
                _weighted_quantile(all_scales, weights, 0.025),
                _weighted_quantile(all_scales, weights, 0.975),
            ],
            "nu_posterior_mean": float(np.sum(weights * all_nu)),
            "approximation": (
                "deterministic grid integration; segment likelihood integrates "
                "Normal(y|theta,se) * StudentT(theta|mu,tau,nu)"
            ),
            "required_assumption": (
                "segment effect estimates are conditionally independent given "
                "mu/tau/nu; overlapping segment definitions require a covariance-aware "
                "extension before production use"
            ),
        },
    }


def _student_t_mixture_posterior_draws(
    observed_mean: float,
    observed_se: float,
    components: Sequence[Mapping[str, float]],
    draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    weights = np.asarray([item["weight"] for item in components], dtype=float)
    weights /= float(np.sum(weights))
    counts = rng.multinomial(draws, weights)
    batches: list[np.ndarray] = []
    for component, count in zip(components, counts):
        if count == 0:
            continue
        batches.append(
            _student_t_posterior_draws(
                observed_mean,
                observed_se,
                float(component["location"]),
                float(component["scale"]),
                float(component["nu"]),
                int(count),
                rng,
            )
        )
    result = np.concatenate(batches)
    rng.shuffle(result)
    return result


def _probability_scale_shrink(
    raw_draws: np.ndarray,
    target_draws: np.ndarray,
    tau2: float,
    rng: np.random.Generator | None = None,
    method: str = "normal_normal",
) -> tuple[np.ndarray, float]:
    """Shrink probability-difference posterior draws.

    ``normal_normal`` is the production path: it applies the normal-normal
    posterior formula to the probability-difference mean and variance, then
    preserves the raw posterior shape when drawing the result.  The older
    ``draw_mixture`` mode remains available for compatibility with prior
    Evidence Packs, but its mixture variance is not the conditional posterior
    variance of a normal-normal model.
    """
    if method not in {"normal_normal", "draw_mixture"}:
        raise ValueError("method must be normal_normal or draw_mixture")
    raw_se2 = max(float(np.var(raw_draws)), 1e-18)
    target_se2 = max(float(np.var(target_draws)), 1e-18)
    weight = tau2 / (tau2 + raw_se2) if tau2 > 0 else 0.0
    if method == "draw_mixture":
        return (weight * raw_draws + (1.0 - weight) * target_draws), float(weight)

    raw_mean = float(np.mean(raw_draws))
    target_mean = float(np.mean(target_draws))
    posterior_mean = weight * raw_mean + (1.0 - weight) * target_mean
    # Conditional normal-normal variance plus uncertainty in the pooled
    # target. This is the variance to report, not weight * raw_se^2.
    conditional_var = raw_se2 * tau2 / (raw_se2 + tau2) if tau2 > 0 else 0.0
    posterior_var = conditional_var + (1.0 - weight) ** 2 * target_se2
    scale = math.sqrt(max(posterior_var, 1e-18) / raw_se2)
    shrunk = posterior_mean + scale * (raw_draws - raw_mean)
    # A probability difference is bounded even though the normal approximation
    # is not. Clipping is only active for very sparse cells.
    return np.clip(shrunk, -1.0, 1.0), float(weight)


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
    shrinkage_method: str = "normal_normal",
    nu: float = 4.0,
    tau: float | None = None,
    student_t_hyperparameter_method: str = "grid_mixture",
    student_t_nu_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Hierarchical HTE with probability-difference posterior shrinkage.

    Raw arm posteriors, pooled targets and shrunken posteriors all stay on the
    probability-difference scale. `shrinkage_strength` is retained only as a
    compatibility bridge for the old pseudo-impression control. For
    ``likelihood="student_t"``, the hierarchy is
    ``y_i | theta_i ~ Normal(theta_i, se_i)`` and
    ``theta_i ~ StudentT(nu, location=pooled_effect, scale=tau)``. Here tau is
    the Student-t scale, not its standard deviation. When ``tau`` and the
    legacy ``shrinkage_strength`` are both omitted, the default ``grid_mixture``
    method propagates uncertainty in location, tau and nu. The old plug-in
    empirical-Bayes method remains available only for replay comparison.
    """
    rng = np.random.default_rng(seed)
    input_validation = validate_hte_segments(segments)
    if not isinstance(draws, int) or isinstance(draws, bool) or draws <= 0:
        raise ValueError("draws must be a positive integer")
    if not math.isfinite(practical_threshold) or practical_threshold < 0:
        raise ValueError("practical_threshold must be finite and non-negative")
    if not math.isfinite(moderation_threshold) or moderation_threshold < 0:
        raise ValueError("moderation_threshold must be finite and non-negative")
    if likelihood not in {"gaussian", "student_t"}:
        raise ValueError("likelihood must be gaussian or student_t")
    if tau is not None and (not math.isfinite(tau) or tau < 0):
        raise ValueError("tau must be finite and non-negative")
    if likelihood == "student_t" and (not math.isfinite(nu) or nu <= 2):
        raise ValueError("nu must be finite and greater than 2")
    if student_t_hyperparameter_method not in {"grid_mixture", "plug_in"}:
        raise ValueError(
            "student_t_hyperparameter_method must be grid_mixture or plug_in"
        )
    if tau is not None and shrinkage_strength is not None:
        raise ValueError("tau and shrinkage_strength cannot both be specified")

    pooled_c = {
        "clicks": sum(s["control"]["clicks"] for s in segments),
        "impressions": sum(s["control"]["impressions"] for s in segments),
    }
    pooled_t = {
        "clicks": sum(s["treatment"]["clicks"] for s in segments),
        "impressions": sum(s["treatment"]["impressions"] for s in segments),
    }
    sizes = [
        s["control"]["impressions"] + s["treatment"]["impressions"] for s in segments
    ]
    pooled_draws = _posterior_effect_draws(pooled_c, pooled_t, prior, draws, rng)
    pooled_summary = _effect_summary(pooled_draws, practical_threshold)
    raw_draws_by_id: dict[str, np.ndarray] = {}
    raw_summaries: dict[str, dict[str, Any]] = {}
    for seg in segments:
        sid = str(seg["segment_id"])
        raw_draws = _posterior_effect_draws(
            seg["control"], seg["treatment"], prior, draws, rng
        )
        raw_draws_by_id[sid] = raw_draws
        raw_summaries[sid] = _effect_summary(raw_draws, practical_threshold)
    means = [raw_summaries[str(s["segment_id"])]["mean"] for s in segments]
    standard_errors = [
        raw_summaries[str(s["segment_id"])]["standard_error"] for s in segments
    ]
    pooled_mean = float(pooled_summary["mean"])
    hyperparameter_posterior: dict[str, Any] | None = None
    student_t_components: list[dict[str, float]] | None = None
    if likelihood == "gaussian":
        tau2 = (
            float(tau) ** 2
            if tau is not None
            else _legacy_tau2(sizes, standard_errors, shrinkage_strength)
            if shrinkage_strength is not None
            else _estimate_tau2(means, standard_errors)
        )
        tau_scale = math.sqrt(tau2)
        random_effect_variance = tau2
    else:
        if tau is not None:
            tau_scale = float(tau)
        elif shrinkage_strength is not None:
            legacy_variance = _legacy_tau2(sizes, standard_errors, shrinkage_strength)
            tau_scale = math.sqrt(legacy_variance * (nu - 2.0) / nu)
        elif student_t_hyperparameter_method == "plug_in":
            tau_scale = _estimate_student_t_scale(
                means, standard_errors, pooled_mean, nu
            )
        else:
            hyperparameter_posterior = _student_t_hyperparameter_posterior(
                means,
                standard_errors,
                pooled_mean,
                float(pooled_summary["standard_error"]),
                nu,
                student_t_nu_grid,
            )
            student_t_components = hyperparameter_posterior["components"]
            summary = hyperparameter_posterior["summary"]
            tau_scale = float(summary["tau_posterior_mean"])
            nu = float(summary["nu_posterior_mean"])
            pooled_mean = float(summary["location_posterior_mean"])
        if student_t_components is None:
            random_effect_variance = tau_scale**2 * nu / (nu - 2.0)
        else:
            random_effect_variance = float(
                sum(
                    component["weight"]
                    * component["scale"] ** 2
                    * component["nu"]
                    / (component["nu"] - 2.0)
                    for component in student_t_components
                )
            )
        tau2 = random_effect_variance

    results: list[dict[str, Any]] = []
    for seg, n in zip(segments, sizes):
        sid = str(seg["segment_id"])
        raw_effects = raw_draws_by_id[sid]
        if likelihood == "student_t":
            if student_t_components is None:
                shrunk_draws = _student_t_posterior_draws(
                    raw_summaries[sid]["mean"],
                    raw_summaries[sid]["standard_error"],
                    pooled_mean,
                    tau_scale,
                    nu,
                    draws,
                    rng,
                )
            else:
                shrunk_draws = _student_t_mixture_posterior_draws(
                    raw_summaries[sid]["mean"],
                    raw_summaries[sid]["standard_error"],
                    student_t_components,
                    draws,
                    rng,
                )
            denominator = raw_summaries[sid]["mean"] - pooled_mean
            weight = (
                (float(np.mean(shrunk_draws)) - pooled_mean) / denominator
                if abs(denominator) > 1e-12
                else 0.0
            )
        else:
            shrunk_draws, weight = _probability_scale_shrink(
                raw_effects, pooled_draws, tau2, rng=rng, method=shrinkage_method
            )
        raw_summary = raw_summaries[sid]
        shrunk_summary = _effect_summary(shrunk_draws, practical_threshold)
        moderation_raw_draws = raw_effects - pooled_draws
        moderation_shrunk_draws = shrunk_draws - pooled_draws
        results.append(
            {
                "segment_id": sid,
                "impressions": int(n),
                "effect_raw": raw_summary["mean"],
                "effect_shrunk": shrunk_summary["mean"],
                "standard_error_raw": raw_summary["standard_error"],
                "standard_error_shrunk": shrunk_summary["standard_error"],
                "shrinkage_weight": float(weight),
                "probability_practical_harm": raw_summary["probability_practical_harm"],
                "probability_practical_benefit": raw_summary[
                    "probability_practical_benefit"
                ],
                "shrunk_probability_practical_harm": shrunk_summary[
                    "probability_practical_harm"
                ],
                "shrunk_probability_practical_benefit": shrunk_summary[
                    "probability_practical_benefit"
                ],
                "moderation_raw": float(np.mean(moderation_raw_draws)),
                "moderation_shrunk": float(np.mean(moderation_shrunk_draws)),
                "prob_moderation_worse_raw": float(
                    np.mean(moderation_raw_draws < -moderation_threshold)
                ),
                "prob_moderation_worse_shrunk": float(
                    np.mean(moderation_shrunk_draws < -moderation_threshold)
                ),
                "credible_interval_raw_95": raw_summary["credible_interval_95"],
                "credible_interval_95": shrunk_summary["credible_interval_95"],
                "evidence_level": "EXPLORATORY_HETEROGENEITY"
                if discovery
                else "HETEROGENEOUS_TREATMENT_EFFECT",
            }
        )
    return {
        "model": (
            "probability_scale_joint_hyperparameter_partial_pooling"
            if likelihood == "student_t" and student_t_components is not None
            else "probability_scale_empirical_bayes_partial_pooling"
        ),
        "likelihood": "beta_binomial_posterior_draws",
        "random_effects_distribution": likelihood,
        "random_effects_parameters": {
            "location": pooled_mean,
            "nu": float(nu) if likelihood == "student_t" else None,
            "scale": float(tau_scale),
            "tau": float(tau_scale),
            "scale_equals_tau": True,
            "parameter_interpretation": (
                "posterior means across mixture components; the posterior is not "
                "a single Student-t distribution"
                if likelihood == "student_t" and student_t_components is not None
                else "single random-effects distribution"
            ),
        },
        "likelihood_requested": likelihood,
        "effect_scale": "probability_difference",
        "logit_taylor_target_used": False,
        "shrinkage_weight_definition": (
            "posterior_displacement_from_mu / observed_displacement_from_mu"
            if likelihood == "student_t"
            else "tau2_variance / (tau2_variance + raw_effect_variance)"
        ),
        "standard_error_definition": "sqrt(final_posterior_effect_variance)",
        "pooled_effect": pooled_summary["mean"],
        "pooled_standard_error": pooled_summary["standard_error"],
        "pooled_credible_interval_95": pooled_summary["credible_interval_95"],
        "tau2_probability_difference": float(tau2),
        "tau_scale_probability_difference": float(tau_scale),
        "tau_definition": (
            "posterior mean of Student-t component scales; component SD is "
            "tau*sqrt(nu/(nu-2))"
            if likelihood == "student_t" and student_t_components is not None
            else "Student-t scale; SD=tau*sqrt(nu/(nu-2))"
            if likelihood == "student_t"
            else "Gaussian random-effects standard deviation"
        ),
        "tau_source": (
            "fixed"
            if tau is not None
            else "legacy_shrinkage_strength"
            if shrinkage_strength is not None
            else "joint_hyperparameter_posterior"
            if likelihood == "student_t"
            and student_t_hyperparameter_method == "grid_mixture"
            else "empirical_bayes_marginal_likelihood"
            if likelihood == "student_t"
            else "der_simonian_laird"
        ),
        "random_effect_variance_probability_difference": float(random_effect_variance),
        "student_t_nu": float(nu) if likelihood == "student_t" else None,
        "student_t_hyperparameter_method": (
            student_t_hyperparameter_method if likelihood == "student_t" else None
        ),
        "student_t_hyperparameter_posterior": (
            hyperparameter_posterior["summary"]
            if hyperparameter_posterior is not None
            else None
        ),
        "student_t_limitations": (
            [
                (
                    "joint hyperparameter likelihood assumes conditionally independent "
                    "segment effect estimates"
                ),
                (
                    "overlapping segment definitions are validation-only until a "
                    "covariance-aware likelihood is implemented"
                ),
            ]
            if likelihood == "student_t"
            and student_t_hyperparameter_method == "grid_mixture"
            else []
        ),
        "posterior_calculation": (
            "mixture posterior integrating p(mu,tau,nu|all segments) and "
            "p(theta_i|y_i,mu,tau,nu)"
            if likelihood == "student_t" and student_t_components is not None
            else "normalized numerical posterior: Normal(y_i|theta_i,se_i) * "
            "StudentT(theta_i|mu,tau,nu)"
            if likelihood == "student_t"
            else "normal-normal empirical-Bayes update"
        ),
        "shrinkage_strength_legacy": (
            float(shrinkage_strength) if shrinkage_strength is not None else None
        ),
        "shrinkage_method": shrinkage_method,
        "discovery_mode": discovery,
        "segments": results,
        "input_validation": input_validation,
    }


def estimate_hte_nested(
    segments: Sequence[Mapping[str, Any]],
    group_of,
    prior: tuple[float, float] = (1.0, 1.0),
    practical_threshold: float = 0.005,
    moderation_threshold: float = 0.005,
    draws: int = 20_000,
    seed: int = 20260811,
    kappa_group: float | None = None,
    kappa_cell: float | None = None,
    likelihood: str = "gaussian",
    shrinkage_method: str = "normal_normal",
) -> dict[str, Any]:
    """Two-level probability-scale pooling: cell -> group -> pooled posterior."""
    rng = np.random.default_rng(seed)
    input_validation = validate_hte_segments(segments)
    if not isinstance(draws, int) or isinstance(draws, bool) or draws <= 0:
        raise ValueError("draws must be a positive integer")
    if not math.isfinite(practical_threshold) or practical_threshold < 0:
        raise ValueError("practical_threshold must be finite and non-negative")
    if not math.isfinite(moderation_threshold) or moderation_threshold < 0:
        raise ValueError("moderation_threshold must be finite and non-negative")
    if likelihood != "gaussian":
        raise ValueError(
            "estimate_hte_nested currently supports only gaussian random effects; "
            "use estimate_hte for Student-t random effects"
        )

    def agg(counts):
        c = {
            "clicks": sum(x["control"]["clicks"] for x in counts),
            "impressions": sum(x["control"]["impressions"] for x in counts),
        }
        t = {
            "clicks": sum(x["treatment"]["clicks"] for x in counts),
            "impressions": sum(x["treatment"]["impressions"] for x in counts),
        }
        return c, t, c["impressions"] + t["impressions"]

    pooled_c, pooled_t, _ = agg(list(segments))
    pooled_draws = _posterior_effect_draws(pooled_c, pooled_t, prior, draws, rng)

    groups: dict[Any, list[Mapping[str, Any]]] = {}
    for s in segments:
        groups.setdefault(group_of(s), []).append(s)
    group_raw_draws: dict[Any, np.ndarray] = {}
    group_sizes: dict[Any, int] = {}
    group_summaries: dict[Any, dict[str, Any]] = {}
    for g, members in groups.items():
        c, t, n = agg(members)
        group_raw_draws[g] = _posterior_effect_draws(c, t, prior, draws, rng)
        group_sizes[g] = n
    group_means = [float(np.mean(x)) for x in group_raw_draws.values()]
    group_ses = [float(np.std(x)) for x in group_raw_draws.values()]
    tau2_group = (
        _legacy_tau2(list(group_sizes.values()), group_ses, kappa_group)
        if kappa_group is not None
        else _estimate_tau2(group_means, group_ses)
    )
    group_shrunk_draws: dict[Any, np.ndarray] = {}
    for g, raw in group_raw_draws.items():
        shrunk, weight = _probability_scale_shrink(
            raw, pooled_draws, tau2_group, rng=rng, method=shrinkage_method
        )
        group_shrunk_draws[g] = shrunk
        group_summaries[g] = {
            **_effect_summary(shrunk, practical_threshold),
            "effect_raw": float(np.mean(raw)),
            "standard_error_raw": float(np.std(raw)),
            "shrinkage_weight": weight,
            "impressions": group_sizes[g],
        }

    cell_raw_draws: dict[str, np.ndarray] = {}
    cell_group: dict[str, Any] = {}
    cell_sizes: dict[str, int] = {}
    for seg in segments:
        sid = str(seg["segment_id"])
        c, t, n = agg([seg])
        cell_raw_draws[sid] = _posterior_effect_draws(c, t, prior, draws, rng)
        cell_group[sid] = group_of(seg)
        cell_sizes[sid] = n
    tau2_cell: dict[Any, float] = {}
    for g in groups:
        ids = [sid for sid, value in cell_group.items() if value == g]
        cell_ses = [float(np.std(cell_raw_draws[sid])) for sid in ids]
        cell_means = [float(np.mean(cell_raw_draws[sid])) for sid in ids]
        sizes_for_group = [cell_sizes[sid] for sid in ids]
        # With fewer than four cells, a positive variance estimate is usually
        # sampling noise. Keep the cell layer conservative and use the group
        # posterior as the target until there is enough within-group evidence.
        if len(ids) < 4:
            tau2_cell[g] = 0.0
        else:
            tau2_cell[g] = (
                _legacy_tau2(sizes_for_group, cell_ses, kappa_cell)
                if kappa_cell is not None
                else _estimate_tau2(cell_means, cell_ses)
            )

    results: list[dict[str, Any]] = []
    for seg in segments:
        g = group_of(seg)
        sid = str(seg["segment_id"])
        raw_effects = cell_raw_draws[sid]
        nested_draws, weight = _probability_scale_shrink(
            raw_effects,
            group_shrunk_draws[g],
            tau2_cell[g],
            rng=rng,
            method=shrinkage_method,
        )
        nested_summary = _effect_summary(nested_draws, practical_threshold)
        moderation_draws = nested_draws - pooled_draws
        results.append(
            {
                "segment_id": sid,
                "group": str(g),
                "impressions": int(cell_sizes[sid]),
                "effect_raw": float(np.mean(raw_effects)),
                "effect_nested": nested_summary["mean"],
                "standard_error_nested": nested_summary["standard_error"],
                "nested_weight": float(weight),
                "group_effect_shrunk_prob": group_summaries[g]["mean"],
                "group_standard_error": group_summaries[g]["standard_error"],
                "group_credible_interval_95": group_summaries[g][
                    "credible_interval_95"
                ],
                "moderation_nested": float(np.mean(moderation_draws)),
                "prob_moderation_worse_nested": float(
                    np.mean(moderation_draws < -moderation_threshold)
                ),
                "credible_interval_nested_95": nested_summary["credible_interval_95"],
                "evidence_level": "HETEROGENEOUS_TREATMENT_EFFECT",
            }
        )
    return {
        "model": "nested_probability_scale_empirical_bayes",
        "likelihood": "beta_binomial_posterior_draws",
        "likelihood_requested": likelihood,
        "effect_scale": "probability_difference",
        "logit_taylor_target_used": False,
        "shrinkage_weight_definition": "tau2_variance / (tau2_variance + raw_effect_variance)",
        "standard_error_definition": "sqrt(final_posterior_effect_variance)",
        "pooled_effect": float(np.mean(pooled_draws)),
        "pooled_standard_error": float(np.std(pooled_draws)),
        "tau2_group_probability_difference": float(tau2_group),
        "tau2_cell_probability_difference": {
            str(g): float(value) for g, value in tau2_cell.items()
        },
        "shrinkage_method": shrinkage_method,
        "groups": {str(g): value for g, value in group_summaries.items()},
        "segments": results,
        "input_validation": input_validation,
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
    pooled_c = {
        "clicks": sum(int(r[outcome_column]) for r in rows if r[treatment_column] == 0),
        "impressions": sum(1 for r in rows if r[treatment_column] == 0),
    }
    pooled_t = {
        "clicks": sum(int(r[outcome_column]) for r in rows if r[treatment_column] == 1),
        "impressions": sum(1 for r in rows if r[treatment_column] == 1),
    }
    pooled = bundle_compare(pooled_c, pooled_t, prior, practical_threshold, seed=seed)
    pooled_effect = pooled["effect_absolute"]

    candidates: list[dict[str, Any]] = []
    for factor in candidate_factors:
        values = sorted({str(r.get(factor, "<missing>")) for r in rows})
        for value in values:
            subset = [r for r in rows if str(r.get(factor, "<missing>")) == value]
            c = {
                "clicks": sum(
                    int(r[outcome_column]) for r in subset if r[treatment_column] == 0
                ),
                "impressions": sum(1 for r in subset if r[treatment_column] == 0),
            }
            t = {
                "clicks": sum(
                    int(r[outcome_column]) for r in subset if r[treatment_column] == 1
                ),
                "impressions": sum(1 for r in subset if r[treatment_column] == 1),
            }
            if c["impressions"] < 30 or t["impressions"] < 30:
                continue
            comp = bundle_compare(c, t, prior, practical_threshold, seed=seed)
            moderation = comp["effect_absolute"] - pooled_effect
            score = (
                max(
                    comp["probability_practical_harm"],
                    comp["probability_practical_benefit"],
                )
                * abs(moderation)
                * math.sqrt(c["impressions"] + t["impressions"])
            )
            candidates.append(
                {
                    "factor_id": factor,
                    "factor_value": value,
                    "segment_effect": comp["effect_absolute"],
                    "pooled_effect": pooled_effect,
                    "moderation": moderation,
                    "probability_practical_harm": comp["probability_practical_harm"],
                    "impressions": c["impressions"] + t["impressions"],
                    "moderation_score": score,
                    "evidence_level": "EXPLORATORY_HETEROGENEITY"
                    if discovery
                    else "HETEROGENEOUS_TREATMENT_EFFECT",
                }
            )
    return sorted(
        candidates, key=lambda item: abs(item["moderation_score"]), reverse=True
    )
