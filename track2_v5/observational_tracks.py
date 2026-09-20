"""Track B: qualified controls, preperiod diagnostics and gated estimates.

DiD supports common adoption, balanced independent-unit panels only. SCM uses
convex preperiod weights and conditional residual block uncertainty. BSTS is an
exact Gaussian local-level regression with explicitly fixed hyperparameters;
it is not the full CausalImpact spike-and-slab/hyperparameter sampler.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm
from scipy.stats import t as student_t

from .contracts import digest, finite, integer, validate_bundle, validate_contract
from .identification import identify_effect


def _ref(value, name):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} must be a nonempty evidence reference or null")
    return value


def _check(passed, ref):
    return {"status": "supported" if passed else "failed", "evidence_refs": [ref]}


def _external(ref, name, *, assumed=False):
    _ref(ref, name)
    return {
        "status": ("assumed" if assumed else "supported") if ref else "missing",
        "evidence_refs": [ref] if ref else [],
    }


def _positive(value, name, *, zero=False):
    value = finite(value, name)
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")
    return value


def _calendar(days, metric, intervention_day):
    days = np.asarray([integer(d, "day") for d in days], dtype=int)
    onset = integer(intervention_day, "intervention_day")
    if len(days) < 6 or not np.all(np.diff(days) == 1):
        raise ValueError("complete increasing daily panel with >=6 days required")
    npre = int(np.sum(days < onset))
    if npre < 4 or npre >= len(days):
        raise ValueError("at least four preperiod days and one postperiod day required")
    if metric["window"] != [onset, int(days[-1])]:
        raise ValueError(
            "MetricContract.window must exactly match the effect postperiod"
        )
    return days, npre


def _mature(observed_through, metric):
    return observed_through is not None and integer(
        observed_through, "observed_through"
    ) >= (metric["window"][1] + metric["maturity_days"])


def _qualify(controls, eligibility):
    if not isinstance(eligibility, dict):
        raise ValueError("control_eligibility must map each control to design evidence")
    refs, rejected = [], []
    for name in controls:
        record = eligibility.get(name, {})
        if not isinstance(record, dict):
            raise ValueError("malformed control eligibility")
        ref = _ref(record.get("evidence_ref"), "control evidence_ref")
        ok = record.get("unaffected") is True and record.get("eligible") is True and ref
        if ok:
            refs.append(ref)
        else:
            rejected.append(name)
    return refs, rejected


def _result(
    metric,
    design,
    binding,
    checks,
    diagnostics,
    estimate,
    interval,
    method,
    selection_status,
    simultaneous_interventions,
    requested_effect,
):
    if requested_effect not in {"individual", "bundle"}:
        raise ValueError("requested_effect must be individual or bundle")
    if (
        not isinstance(simultaneous_interventions, (tuple, list))
        or any(
            not isinstance(x, str) or not x.strip() for x in simultaneous_interventions
        )
        or len(set(simultaneous_interventions)) != len(simultaneous_interventions)
    ):
        raise ValueError(
            "simultaneous_interventions requires unique nonempty event names"
        )
    report = identify_effect(
        treatment="registered_intervention",
        outcome=metric["name"],
        design=design,
        checks=checks,
        data_digest=binding,
        target_population=metric["target_population"],
        simultaneous_interventions=simultaneous_interventions,
        requested_effect=requested_effect,
    )
    if report["status"] != "IDENTIFIED":
        estimate, interval = None, None
    effect = {
        "estimand": "ATT_bundle" if requested_effect == "bundle" else "ATT",
        "unit": metric["unit"],
        "estimate": estimate,
        "interval": interval,
        "interval_method": method,
        "selection_status": selection_status,
        "target_population": metric["target_population"],
        "window": metric["window"],
        "diagnostics": {**diagnostics, "data_digest": binding},
        "identification_ref": report["digest"],
        "method": design,
    }
    return {
        "track": "B",
        "status": "ESTIMATED" if estimate is not None else "REFUSED",
        "contracts": validate_bundle(
            {
                "MetricContract": metric,
                "IdentificationReport": report,
                "EffectEstimate": effect,
            }
        ),
    }


def _difference(a, b, alpha=0.05):
    center = float(np.mean(a) - np.mean(b))
    if min(len(a), len(b)) < 2:
        return center, None, None
    va, vb = float(np.var(a, ddof=1) / len(a)), float(np.var(b, ddof=1) / len(b))
    se = float(np.sqrt(va + vb))
    df = (
        (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
        if se
        else len(a) + len(b) - 2
    )
    half = float(student_t.ppf(1 - alpha / 2, df) * se)
    return center, [center - half, center + half], se


def estimate_did_effect(
    rows,
    metric_contract,
    *,
    intervention_day,
    observed_through,
    control_eligibility,
    no_anticipation_ref,
    no_differential_shock_ref,
    parallel_trends_ref,
    trend_tolerance,
    independent_units_ref,
    selection_status="pre_registered",
    simultaneous_interventions=(),
    requested_effect="individual",
    seed=20260915,
):
    """Equal-unit common-onset DiD; rows: unit_id, day, treatment, outcome.

    treatment is actual exposure (zero for all preperiod rows). No staggered
    adoption, switching, changing panel composition or cross-unit clustering.
    Rate inputs are binary per unit/day; no implicit unequal-denominator rates.
    """
    metric = validate_contract("MetricContract", metric_contract)
    tolerance = _positive(trend_tolerance, "trend_tolerance")
    if not rows:
        raise ValueError("nonempty panel required")
    cells, units, times = {}, set(), set()
    for row in rows:
        unit = row["unit_id"]
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError("unit_id must be a nonempty string")
        day = integer(row["day"], "day")
        key = (unit, day)
        if key in cells:
            raise ValueError("duplicate unit/day observation")
        outcome = finite(row["outcome"], "outcome")
        assignment = integer(row["treatment"], "treatment")
        if assignment not in (0, 1):
            raise ValueError("treatment must be binary")
        if metric["unit"] == "rate" and outcome not in (0, 1):
            raise ValueError("rate DiD requires binary outcome per analysis unit/day")
        cells[key] = (outcome, assignment)
        units.add(unit)
        times.add(day)
    units = sorted(units)
    days, pre = _calendar(sorted(times), metric, intervention_day)
    if len(cells) != len(units) * len(days):
        raise ValueError("balanced complete panel required")
    y = np.asarray([[cells[u, d][0] for d in days] for u in units])
    exposure = np.asarray([[cells[u, d][1] for d in days] for u in units])
    treated = np.any(exposure == 1, axis=1)
    nt, nc = int(treated.sum()), int((~treated).sum())
    expected = treated[:, None] * (days[None, :] >= intervention_day)
    compatible = bool(np.array_equal(exposure, expected))
    refs, rejected = _qualify(
        [u for u, t in zip(units, treated) if not t], control_eligibility
    )
    binding = digest(
        {
            "rows": rows,
            "metric": metric["digest"],
            "intervention_day": intervention_day,
            "trend_tolerance": tolerance,
            "control_eligibility": control_eligibility,
            "parallel_trends_ref": parallel_trends_ref,
            "independent_units_ref": independent_units_ref,
            "seed": seed,
        }
    )
    event_study = []
    if min(nt, nc) >= 2:
        for k in range(1, pre):
            changes = y[:, k] - y[:, 0]
            value, bounds, _ = _difference(
                changes[treated], changes[~treated], alpha=0.05 / (pre - 1)
            )
            event_study.append(
                {
                    "day": int(days[k]),
                    "difference": value,
                    "simultaneous_interval": bounds,
                    "within_tolerance": bounds[0] > -tolerance
                    and bounds[1] < tolerance,
                }
            )
    trend_pass = bool(event_study) and all(e["within_tolerance"] for e in event_study)
    checks = {
        "data_valid": _check(True, binding),
        "outcome_mature": _check(_mature(observed_through, metric), binding),
        "support_overlap": _check(min(nt, nc) >= 2, binding),
        "rollout_design_compatible": _check(compatible, binding),
        "parallel_trends": _check(trend_pass, binding),
        "parallel_trends_extrapolation": _external(
            parallel_trends_ref, "parallel_trends_ref", assumed=True
        ),
        "independent_units": _external(
            independent_units_ref, "independent_units_ref", assumed=True
        ),
        "no_anticipation": _external(no_anticipation_ref, "no_anticipation_ref"),
        "no_differential_shock": _external(
            no_differential_shock_ref, "no_differential_shock_ref", assumed=True
        ),
        "unaffected_controls": {
            "status": "supported" if refs and not rejected else "failed",
            "evidence_refs": refs,
        },
    }
    estimate, interval, se = None, None, None
    h = len(days) - pre
    scale = (
        h * nt
        if metric["unit"] in {"count", "currency"}
        else h
        if metric["unit"] == "currency_per_user"
        else 1
    )
    if min(nt, nc) >= 2:
        delta = y[:, pre:].mean(axis=1) - y[:, :pre].mean(axis=1)
        value, bounds, se = _difference(delta[treated], delta[~treated])
        estimate, interval = value * scale, [v * scale for v in bounds]
    rng = np.random.default_rng(seed)
    cuts = list(range(2, pre - h + 1))
    cuts = (
        sorted(rng.choice(cuts, min(20, len(cuts)), replace=False).tolist())
        if cuts
        else []
    )
    placebos = []
    if min(nt, nc) >= 2:
        for cut in cuts:
            delta = y[:, cut : cut + h].mean(axis=1) - y[:, :cut].mean(axis=1)
            value, bounds, _ = _difference(delta[treated], delta[~treated])
            placebos.append(
                {
                    "day": int(days[cut]),
                    "descriptive_difference": value,
                    "pointwise_interval": bounds,
                }
            )
    diagnostics = {
        "treated_units": nt,
        "control_units": nc,
        "rejected_controls": rejected,
        "preperiod_event_study": event_study,
        "trend_tolerance": tolerance,
        "trend_rule": "all Bonferroni 95% preperiod contrasts inside prespecified equivalence margin",
        "trend_scope": "preperiod diagnostic; future parallel trends is a separate maintained assumption",
        "variance_unit": "independent unit_id; repeated days collapsed before Welch inference",
        "standard_error": se * scale if se is not None else None,
        "scale_multiplier": scale,
        "aggregation": "treated-unit total over window"
        if metric["unit"] in {"count", "currency"}
        else "equal-unit window outcome",
        "interval_scope": "pointwise Welch approximation; conditional on design and preperiod selection",
        "time_placebos": {
            "requested": 20,
            "executed": len(placebos),
            "runs": placebos,
            "formal_pvalue": None,
            "scope": "overlapping exploratory diagnostics; no independent-test claim",
        },
    }
    return _result(
        metric,
        "DiD",
        binding,
        checks,
        diagnostics,
        estimate,
        interval,
        "independent_unit_change_Welch_t",
        selection_status,
        simultaneous_interventions,
        requested_effect,
    )


def _convex_fit(y, x):
    p = x.shape[1]
    normalizer = max(float(np.std(y)), float(np.std(x)), 1e-8)
    xx, yy = x / normalizer, y / normalizer
    result = minimize(
        lambda w: float(np.mean((xx @ w - yy) ** 2)),
        np.full(p, 1 / p),
        jac=lambda w: 2 * xx.T @ (xx @ w - yy) / len(y),
        method="SLSQP",
        bounds=[(0, 1)] * p,
        constraints={
            "type": "eq",
            "fun": lambda w: w.sum() - 1,
            "jac": lambda w: np.ones(p),
        },
        options={"maxiter": 1000, "ftol": 1e-12},
    )
    if not result.success or abs(result.x.sum() - 1) > 1e-6:
        raise ValueError("SCM convex fit did not converge")
    return result.x


def _gaussian_forecast(
    y, x, future, observation_variance, level_variance, prior_variance
):
    # p(theta_0)=N(0, prior_variance I); level evolves, regression coefficients fixed.
    center, spread = x.mean(axis=0), np.maximum(x.std(axis=0), 1e-10)
    design = np.column_stack([np.ones(len(x)), (x - center) / spread])
    target = np.column_stack([np.ones(len(future)), (future - center) / spread])
    size = design.shape[1]
    mean, covariance = np.zeros(size), np.eye(size) * prior_variance
    process = np.zeros((size, size))
    process[0, 0] = level_variance
    for value, f in zip(y, design):
        covariance = covariance + process
        innovation_var = float(f @ covariance @ f + observation_variance)
        gain = covariance @ f / innovation_var
        mean = mean + gain * (value - f @ mean)
        # Joseph update retains positive semidefiniteness.
        residual = np.eye(size) - np.outer(gain, f)
        covariance = (
            residual @ covariance @ residual.T
            + np.outer(gain, gain) * observation_variance
        )
    h = len(future)
    steps = np.arange(1, h + 1)
    joint = target @ covariance @ target.T + level_variance * np.minimum.outer(
        steps, steps
    )
    joint += np.eye(h) * observation_variance
    return (
        target @ mean,
        joint,
        {
            "state_mean": mean.tolist(),
            "state_covariance": covariance.tolist(),
            "control_center": center.tolist(),
            "control_scale": spread.tolist(),
        },
    )


def estimate_controlled_series_effect(
    days,
    outcome,
    controls,
    metric_contract,
    *,
    method,
    intervention_day,
    observed_through,
    control_eligibility,
    backtest_rmse_limit,
    relationship_ref,
    min_backtest_gain=0.0,
    no_spillover_ref=None,
    prefit_rmse_limit=None,
    loo_effect_limit=None,
    max_weight=None,
    block_length=5,
    bootstrap_samples=999,
    observation_variance=None,
    level_variance=None,
    prior_variance=None,
    selection_status="pre_registered",
    simultaneous_interventions=(),
    requested_effect="individual",
    seed=20260915,
):
    """SCM/BSTS on a prespecified aggregate daily outcome and donor/control series.

    Current adapter supports count/currency totals only: ratio series require a
    numerator/denominator model and cannot be silently averaged with equal days.
    """
    if method not in {"SCM", "BSTS"}:
        raise ValueError("method must be SCM or BSTS")
    metric = validate_contract("MetricContract", metric_contract)
    if metric["unit"] not in {"count", "currency"}:
        raise ValueError(
            "controlled-series adapter currently requires daily count/currency totals"
        )
    days, pre = _calendar(days, metric, intervention_day)
    if (
        not isinstance(controls, dict)
        or not controls
        or any(not isinstance(n, str) or not n.strip() for n in controls)
    ):
        raise ValueError("named control series required")
    names = sorted(controls)
    y = np.asarray(outcome, dtype=float)
    x = np.asarray([controls[n] for n in names], dtype=float).T
    if (
        y.shape != (len(days),)
        or x.shape != (len(days), len(names))
        or not np.all(np.isfinite(y))
        or not np.all(np.isfinite(x))
    ):
        raise ValueError("finite complete aligned outcome and controls required")
    h = len(days) - pre
    # Residual bootstrap also needs multiple held-out blocks, even for short effects.
    validation_horizon = (
        max(h, 20, 4 * integer(block_length, "block_length")) if method == "SCM" else h
    )
    if pre - validation_horizon < max(4, len(names) + 2):
        raise ValueError(
            "insufficient preperiod for horizon-matched backtest and training"
        )
    backtest_limit = _positive(backtest_rmse_limit, "backtest_rmse_limit", zero=True)
    gain_limit = _positive(min_backtest_gain, "min_backtest_gain", zero=True)
    refs, rejected = _qualify(names, control_eligibility)
    config = {
        "method": method,
        "backtest_rmse_limit": backtest_limit,
        "min_backtest_gain": gain_limit,
        "prefit_rmse_limit": prefit_rmse_limit,
        "loo_effect_limit": loo_effect_limit,
        "max_weight": max_weight,
        "block_length": block_length,
        "bootstrap_samples": bootstrap_samples,
        "observation_variance": observation_variance,
        "level_variance": level_variance,
        "prior_variance": prior_variance,
        "seed": seed,
    }
    binding = digest(
        {
            "days": days.tolist(),
            "outcome": outcome,
            "controls": controls,
            "metric": metric["digest"],
            "config": config,
            "control_eligibility": control_eligibility,
            "relationship_ref": relationship_ref,
        }
    )
    checks = {
        "data_valid": _check(True, binding),
        "outcome_mature": _check(_mature(observed_through, metric), binding),
        "support_overlap": _check(bool(len(names)) and not rejected, binding),
    }
    diagnostics = {
        "configuration": config,
        "control_names": names,
        "rejected_controls": rejected,
        "training_window": [int(days[0]), int(days[pre - 1])],
        "aggregation": "sum of daily aggregate effects over the metric window",
        "control_selection": "prespecified; not selected from root-cause candidates",
    }
    if method == "SCM":
        prefit_limit = _positive(prefit_rmse_limit, "prefit_rmse_limit", zero=True)
        loo_limit = _positive(loo_effect_limit, "loo_effect_limit", zero=True)
        weight_limit = _positive(max_weight, "max_weight")
        block = integer(block_length, "block_length")
        draws = integer(bootstrap_samples, "bootstrap_samples")
        if (
            len(names) < 2
            or weight_limit > 1
            or not 1 <= block <= pre - h
            or draws < 199
        ):
            raise ValueError(
                "SCM needs >=2 donors, max_weight<=1, valid block length and >=199 draws"
            )

        def predict(cut, horizon):
            weights = _convex_fit(y[:cut], x[:cut])
            return x[cut : cut + horizon] @ weights

        weights = _convex_fit(y[:pre], x[:pre])
        forecast = x[pre:] @ weights
        prefit = float(np.sqrt(np.mean((y[:pre] - x[:pre] @ weights) ** 2)))
        loo = []
        for j, name in enumerate(names):
            keep = [k for k in range(len(names)) if k != j]
            w = _convex_fit(y[:pre], x[:pre, keep])
            change = float(np.sum(forecast - x[pre:, keep] @ w))
            loo.append({"omitted": name, "total_effect_change": change})
        backtest_prediction = predict(pre - validation_horizon, validation_horizon)
        baseline_prediction = np.full(
            validation_horizon, y[pre - validation_horizon - 1]
        )
        residuals = y[pre - validation_horizon : pre] - backtest_prediction
        # Held-out residuals avoid using in-sample fit errors as forecast uncertainty.
        if block > len(residuals):
            raise ValueError("block_length cannot exceed held-out residual window")
        rng = np.random.default_rng(seed)
        empirical_errors = residuals
        totals = []
        for _ in range(draws):
            starts = rng.integers(
                0, len(empirical_errors), size=int(np.ceil(h / block))
            )
            sample = np.concatenate(
                [
                    empirical_errors[(s + np.arange(block)) % len(empirical_errors)]
                    for s in starts
                ]
            )[:h]
            totals.append(float(sample.sum()))
        half = float(np.quantile(np.abs(totals), 0.95))
        diagnostics.update(
            weights=dict(zip(names, weights.tolist())),
            prefit_rmse=prefit,
            leave_one_out=loo,
            backtest_residual_mean=float(residuals.mean()),
            interval_scope="conditional stationary residual-block approximation; excludes donor-selection, weight and design uncertainty",
            interval_assumption="held-out residual process (including its mean) transports to postperiod",
        )
        checks.update(
            {
                "donor_eligibility": {
                    "status": "supported" if refs and not rejected else "failed",
                    "evidence_refs": refs,
                },
                "preperiod_fit": _check(prefit <= prefit_limit, binding),
                "leave_one_out_stable": _check(
                    all(abs(r["total_effect_change"]) <= loo_limit for r in loo),
                    binding,
                ),
                "weight_concentration_acceptable": _check(
                    float(weights.max()) <= weight_limit + 1e-8, binding
                ),
                "no_spillover": _external(
                    no_spillover_ref, "no_spillover_ref", assumed=True
                ),
                "stable_relationship": _external(
                    relationship_ref, "relationship_ref", assumed=True
                ),
            }
        )
        interval_method = (
            "conditional_heldout_residual_circular_block_95_absolute_quantile"
        )
    else:
        r = _positive(observation_variance, "observation_variance")
        q = _positive(level_variance, "level_variance", zero=True)
        prior = _positive(prior_variance, "prior_variance")

        def predict(cut, horizon):
            return _gaussian_forecast(
                y[:cut], x[:cut], x[cut : cut + horizon], r, q, prior
            )[0]

        forecast, joint, state = _gaussian_forecast(
            y[:pre], x[:pre], x[pre:], r, q, prior
        )
        backtest_prediction = predict(pre - validation_horizon, validation_horizon)
        baseline_prediction = _gaussian_forecast(
            y[: pre - validation_horizon],
            np.empty((pre - validation_horizon, 0)),
            np.empty((validation_horizon, 0)),
            r,
            q,
            prior,
        )[0]
        half = float(norm.ppf(0.975) * np.sqrt(max(float(joint.sum()), 0)))
        diagnostics.update(
            posterior_state=state,
            counterfactual_joint_covariance=joint.tolist(),
            interval_scope="Gaussian posterior predictive interval conditional on fixed hyperparameters and unaffected controls",
            model="local level random walk + static Gaussian regression; no spike-and-slab or hyperparameter integration",
        )
        checks.update(
            {
                "unaffected_controls": {
                    "status": "supported" if refs and not rejected else "failed",
                    "evidence_refs": refs,
                },
                "stable_relationship": _external(
                    relationship_ref, "relationship_ref", assumed=True
                ),
            }
        )
        interval_method = "fixed_hyperparameter_Gaussian_posterior_predictive_95"
    backtest_rmse = float(
        np.sqrt(np.mean((y[pre - validation_horizon : pre] - backtest_prediction) ** 2))
    )
    baseline_rmse = float(
        np.sqrt(np.mean((y[pre - validation_horizon : pre] - baseline_prediction) ** 2))
    )
    gain = baseline_rmse - backtest_rmse
    checks["control_predictive_gain"] = _check(gain > gain_limit, binding)
    checks["preperiod_backtest"] = _check(backtest_rmse <= backtest_limit, binding)
    diagnostics["backtest"] = {
        "window": [int(days[pre - validation_horizon]), int(days[pre - 1])],
        "prediction": backtest_prediction.tolist(),
        "rmse": backtest_rmse,
        "limit": backtest_limit,
        "baseline_rmse": baseline_rmse,
        "rmse_gain": gain,
        "minimum_gain": gain_limit,
        "baseline": "last training observation"
        if method == "SCM"
        else "same local-level model without controls",
    }
    # Unique earlier cut points, each with the same horizon, none sees real postperiod y.
    cuts = list(range(max(4, len(names) + 2), pre - h + 1))
    rng = np.random.default_rng(seed)
    cuts = (
        sorted(rng.choice(cuts, min(20, len(cuts)), replace=False).tolist())
        if cuts
        else []
    )
    placebos = [
        {
            "day": int(days[cut]),
            "descriptive_total_difference": float(
                np.sum(y[cut : cut + h] - predict(cut, h))
            ),
        }
        for cut in cuts
    ]
    diagnostics["time_placebos"] = {
        "requested": 20,
        "executed": len(placebos),
        "runs": placebos,
        "formal_pvalue": None,
        "scope": "overlapping empirical diagnostics, not independent randomized inference",
    }
    diagnostics["counterfactual"] = forecast.tolist()
    estimate = float(np.sum(y[pre:] - forecast))
    return _result(
        metric,
        method,
        binding,
        checks,
        diagnostics,
        estimate,
        [estimate - half, estimate + half],
        interval_method,
        selection_status,
        simultaneous_interventions,
        requested_effect,
    )
