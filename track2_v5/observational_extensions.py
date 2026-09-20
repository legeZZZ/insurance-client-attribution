"""Cohort-time DiD, ratio counterfactuals and hyperparameter-integrated BSTS."""

from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
from scipy.special import logsumexp
from scipy.stats import norm
from scipy.stats import t as student_t

from .contracts import digest, finite, integer, validate_bundle, validate_contract
from .observational_tracks import estimate_controlled_series_effect, estimate_did_effect


def _replace_report(
    base, metric, binding, *, estimate, interval, diagnostics, failures=()
):
    report = {
        k: deepcopy(v)
        for k, v in base["contracts"]["IdentificationReport"].items()
        if k != "digest"
    }
    report["support"]["data_digest"] = binding
    report["evidence_refs"] = sorted(set(report["evidence_refs"]) | {binding})
    if failures:
        report.update(
            status="NOT_IDENTIFIED",
            causal_effect_allowed=False,
            reason_codes=sorted(set(report["reason_codes"]) | set(failures)),
        )
    report = validate_contract("IdentificationReport", report)
    effect = {
        k: deepcopy(v)
        for k, v in base["contracts"]["EffectEstimate"].items()
        if k != "digest"
    }
    if report["status"] != "IDENTIFIED":
        estimate, interval = None, None
    effect.update(
        unit=metric["unit"],
        window=metric["window"],
        target_population=metric["target_population"],
        estimate=estimate,
        interval=interval,
        identification_ref=report["digest"],
        diagnostics=diagnostics,
        interval_method=diagnostics.get("interval_method", effect["interval_method"]),
    )
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


def estimate_staggered_did(
    rows,
    metric_contract,
    *,
    observed_through,
    control_eligibility,
    no_anticipation_ref,
    no_differential_shock_ref,
    parallel_trends_ref,
    trend_tolerance,
    independent_units_ref,
    simultaneous_interventions=(),
    requested_effect="individual",
):
    """Common-onset estimates per cohort, using never-treated controls.

    Aggregates cohort-window ATTs with explicit exposure weights. Covariance is
    computed from shared unit influence contributions, not independent-cohort SEs.
    """
    metric = validate_contract("MetricContract", metric_contract)
    units = sorted({r["unit_id"] for r in rows})
    days = sorted({integer(r["day"], "day") for r in rows})
    cells = {(r["unit_id"], integer(r["day"], "day")): r for r in rows}
    if (
        len(cells) != len(rows)
        or len(cells) != len(units) * len(days)
        or not np.all(np.diff(days) == 1)
    ):
        raise ValueError("complete balanced panel without duplicates required")
    if days[-1] != metric["window"][1]:
        raise ValueError("panel must end at metric window end")
    adoption = {}
    for u in units:
        a = [integer(cells[u, d]["treatment"], "treatment") for d in days]
        if any(v not in (0, 1) for v in a) or any(
            a[i] > a[i + 1] for i in range(len(a) - 1)
        ):
            raise ValueError("absorbing binary rollout required")
        adoption[u] = days[a.index(1)] if 1 in a else None
        if adoption[u] is not None and adoption[u] < metric["window"][0]:
            raise ValueError("already-treated units cannot enter this cohort adapter")
    cohorts = sorted({v for v in adoption.values() if v is not None})
    if not cohorts or cohorts[0] != metric["window"][0]:
        raise ValueError("metric window must begin at first cohort adoption")
    effects, influences, reports, failures = [], np.zeros(len(units)), [], set()
    total_treated = sum(v is not None for v in adoption.values())
    total_exposure = sum(days[-1] - v + 1 for v in adoption.values() if v is not None)
    for onset in cohorts:
        treated = [u for u in units if adoption[u] == onset]
        # Never-treated controls remain untreated throughout the full requested window.
        end = days[-1]
        controls = [u for u in units if adoption[u] is None]
        cohort_metric = {
            k: v
            for k, v in metric.items()
            if k not in {"digest", "contract_type", "schema_version"}
        }
        cohort_metric["window"] = [onset, end]
        subset = [cells[u, d] for u in treated + controls for d in days if d <= end]
        result = estimate_did_effect(
            subset,
            cohort_metric,
            intervention_day=onset,
            observed_through=observed_through,
            control_eligibility=control_eligibility,
            no_anticipation_ref=no_anticipation_ref,
            no_differential_shock_ref=no_differential_shock_ref,
            parallel_trends_ref=parallel_trends_ref,
            trend_tolerance=trend_tolerance,
            independent_units_ref=independent_units_ref,
            simultaneous_interventions=simultaneous_interventions,
            requested_effect=requested_effect,
        )
        report, effect = (
            result["contracts"]["IdentificationReport"],
            result["contracts"]["EffectEstimate"],
        )
        reports.append(
            {
                "cohort": onset,
                "treated": treated,
                "controls": controls,
                "result": result,
            }
        )
        failures.update(report["reason_codes"])
        h = end - onset + 1
        weight = (
            len(treated) * h / total_exposure
            if metric["unit"] == "rate"
            else len(treated) / total_treated
            if metric["unit"] == "currency_per_user"
            else 1.0
        )
        reports[-1].update(aggregation_weight=weight, exposure_days=h * len(treated))
        if effect["estimate"] is not None:
            effects.append(weight * effect["estimate"])
        if min(len(treated), len(controls)) >= 2:
            delta = {
                u: np.mean(
                    [
                        finite(cells[u, d]["outcome"], "outcome")
                        for d in days
                        if d >= onset
                    ]
                )
                - np.mean(
                    [
                        finite(cells[u, d]["outcome"], "outcome")
                        for d in days
                        if d < onset
                    ]
                )
                for u in treated + controls
            }
            scale = (
                h * len(treated)
                if metric["unit"] in {"count", "currency"}
                else h
                if metric["unit"] == "currency_per_user"
                else 1.0
            )
            for arm, sign in ((treated, 1), (controls, -1)):
                mean = np.mean([delta[u] for u in arm])
                for u in arm:
                    influences[units.index(u)] += (
                        weight * scale * sign * (delta[u] - mean) / len(arm)
                    )
    variance = 0.0
    for cohort in [None, *cohorts]:
        idx = [i for i, u in enumerate(units) if adoption[u] == cohort]
        if len(idx) >= 2:
            variance += len(idx) / (len(idx) - 1) * float(np.sum(influences[idx] ** 2))
    df = (
        min(sum(adoption[u] == cohort for u in units) for cohort in [None, *cohorts])
        - 1
    )
    estimate = float(sum(effects)) if not failures else None
    half = float(student_t.ppf(0.975, df) * math.sqrt(variance)) if df > 0 else 0.0
    result = _replace_report(
        reports[0]["result"],
        metric,
        digest({"rows": rows, "metric": metric["digest"], "cohorts": cohorts}),
        estimate=estimate,
        interval=[estimate - half, estimate + half] if estimate is not None else None,
        diagnostics={
            "interval_method": "cohort_shared_unit_influence_t",
            "design": "cohort-specific ATT with never-treated controls; no TWFE",
            "cohort_reports": reports,
            "treated_units": total_treated,
            "treated_unit_days": total_exposure,
            "standard_error": math.sqrt(variance),
            "covariance": "shared unit influence summed before squaring",
            "degrees_of_freedom": df,
            "interval_scope": "independent-unit cluster t approximation; cohort composition held fixed",
        },
        failures=failures,
    )
    return result


def estimate_bsts_mixture(*, hyperparameter_grid, **request):
    """Exact finite prior over (observation variance, level variance, prior variance).

    Posterior grid weights use sequential predictive likelihood on preperiod only.
    This is actual hyperparameter integration for the declared discrete prior.
    """
    if request.get("method", "BSTS") != "BSTS" or not hyperparameter_grid:
        raise ValueError("nonempty BSTS prior grid required")
    request = {**request, "method": "BSTS"}
    y = np.asarray(request["outcome"], dtype=float)
    x = np.array([request["controls"][n] for n in sorted(request["controls"])]).T
    pre = sum(d < request["intervention_day"] for d in request["days"])
    outputs, logs = [], []
    for point in hyperparameter_grid:
        prior_mass = finite(point["prior_mass"], "prior_mass")
        if prior_mass <= 0:
            raise ValueError("grid prior masses must be positive")
        args = {
            k: point[k]
            for k in ("observation_variance", "level_variance", "prior_variance")
        }
        output = estimate_controlled_series_effect(**{**request, **args})
        outputs.append(output)
        # Exact marginal likelihood of the same conditional-on-X state-space model.
        xx = x[:pre]
        center, spread = xx.mean(axis=0), np.maximum(xx.std(axis=0), 1e-10)
        design_matrix = np.column_stack([np.ones(pre), (xx - center) / spread])
        state_mean = np.zeros(design_matrix.shape[1])
        covariance = np.eye(len(state_mean)) * args["prior_variance"]
        process = np.zeros_like(covariance)
        process[0, 0] = args["level_variance"]
        logweight = math.log(prior_mass)
        for value, f in zip(y[:pre], design_matrix):
            covariance += process
            innovation_variance = float(
                f @ covariance @ f + args["observation_variance"]
            )
            logweight += float(
                norm.logpdf(
                    value, loc=f @ state_mean, scale=np.sqrt(innovation_variance)
                )
            )
            gain = covariance @ f / innovation_variance
            state_mean += gain * (value - f @ state_mean)
            residual = np.eye(len(gain)) - np.outer(gain, f)
            covariance = (
                residual @ covariance @ residual.T
                + np.outer(gain, gain) * args["observation_variance"]
            )
        logs.append(logweight)
    weights = np.exp(np.array(logs) - logsumexp(logs))
    # Failed component diagnostics cannot be silently discarded to improve the result.
    failures = set().union(
        *(o["contracts"]["IdentificationReport"]["reason_codes"] for o in outputs)
    )
    means, variances = [], []
    for output in outputs:
        e = output["contracts"]["EffectEstimate"]
        if e["estimate"] is not None:
            means.append(e["estimate"])
            variances.append(
                float(
                    np.asarray(
                        e["diagnostics"]["counterfactual_joint_covariance"]
                    ).sum()
                )
            )
    estimate, interval = None, None
    if not failures:
        estimate = float(weights @ means)
        # Exact mixture CDF inversion, not averaged conditional interval endpoints.
        from scipy.optimize import brentq

        scales = np.sqrt(np.maximum(variances, 1e-20))
        left, right = (
            float(np.min(np.array(means) - 12 * scales)),
            float(np.max(np.array(means) + 12 * scales)),
        )

        def quantile(p):
            return float(
                brentq(
                    lambda value: (
                        float(weights @ norm.cdf((value - np.array(means)) / scales))
                        - p
                    ),
                    left,
                    right,
                )
            )

        interval = [min(estimate, quantile(0.025)), max(estimate, quantile(0.975))]
    metric = outputs[0]["contracts"]["MetricContract"]
    result = _replace_report(
        outputs[0],
        metric,
        digest({"request": request, "hyperparameter_grid": hyperparameter_grid}),
        estimate=estimate,
        interval=interval,
        diagnostics={
            "hyperparameter_grid": hyperparameter_grid,
            "posterior_weights": weights.tolist(),
            "weight_training_window": [request["days"][0], request["days"][pre - 1]],
            "components": outputs,
            "interval_scope": "exact Gaussian predictive mixture conditional on finite hyperprior",
            "between_hyperparameter_variance": float(
                weights @ ((np.array(means) - estimate) ** 2)
            )
            if estimate is not None
            else None,
        },
        failures=failures,
    )
    result["contracts"]["EffectEstimate"].pop("digest")
    result["contracts"]["EffectEstimate"]["interval_method"] = (
        "finite_hyperprior_posterior_predictive_mixture"
    )
    result["contracts"] = validate_bundle(result["contracts"])
    return result


def estimate_ratio_series(
    *,
    numerator,
    denominator,
    numerator_controls,
    denominator_controls,
    numerator_eligibility,
    denominator_eligibility,
    metric_contract,
    bootstrap_samples=199,
    block_length=5,
    seed=20260915,
    **request,
):
    """Paired numerator/denominator counterfactuals; joint residual-block ratio uncertainty."""
    metric = validate_contract("MetricContract", metric_contract)
    if metric["unit"] not in {"rate", "currency_per_user"}:
        raise ValueError("ratio series requires normalized metric")
    n, d = np.array(numerator, dtype=float), np.array(denominator, dtype=float)
    if (
        n.shape != d.shape
        or not np.all(np.isfinite(n))
        or not np.all(np.isfinite(d))
        or np.any(d <= 0)
        or (metric["unit"] == "rate" and (np.any(n < 0) or np.any(n > d)))
    ):
        raise ValueError("finite valid paired numerator/denominator required")
    raw_metric = {
        k: v
        for k, v in metric.items()
        if k not in {"digest", "contract_type", "schema_version"}
    }
    raw_metric.update(unit="currency", denominator=None, aggregation="sum")
    outputs = [
        estimate_controlled_series_effect(
            outcome=values,
            controls=controls,
            control_eligibility=eligibility,
            metric_contract=raw_metric,
            seed=seed,
            **request,
        )
        for values, controls, eligibility in (
            (list(n), numerator_controls, numerator_eligibility),
            (list(d), denominator_controls, denominator_eligibility),
        )
    ]
    fails = set().union(
        *(o["contracts"]["IdentificationReport"]["reason_codes"] for o in outputs)
    )
    diags = [o["contracts"]["EffectEstimate"]["diagnostics"] for o in outputs]
    forecasts = [np.array(diag["counterfactual"]) for diag in diags]
    if np.any(forecasts[1] <= 0) or (
        metric["unit"] == "rate"
        and (np.any(forecasts[0] < 0) or np.any(forecasts[0] > forecasts[1]))
    ):
        fails.add("MODEL_MISMATCH")
    pre = sum(day < request["intervention_day"] for day in request["days"])
    h = len(n) - pre
    estimate, interval = None, None
    block, draws = (
        integer(block_length, "block_length"),
        integer(bootstrap_samples, "bootstrap_samples"),
    )
    if (
        not 1 <= block <= min(len(diag["backtest"]["prediction"]) for diag in diags)
        or draws < 199
    ):
        raise ValueError(
            "valid paired residual block and >=199 bootstrap draws required"
        )
    residuals = [
        values[pre - len(diag["backtest"]["prediction"]) : pre]
        - diag["backtest"]["prediction"]
        for values, diag in zip((n, d), diags)
    ]
    if len(residuals[0]) != len(residuals[1]):
        raise ValueError("component backtest windows must match")
    differences = []
    if not fails:
        observed = float(n[pre:].sum() / d[pre:].sum())
        predicted = float(forecasts[0].sum() / forecasts[1].sum())
        estimate = observed - predicted
        rng = np.random.default_rng(seed)
        for _ in range(draws):
            starts = rng.integers(0, len(residuals[0]), int(np.ceil(h / block)))
            idx = np.concatenate(
                [(start + np.arange(block)) % len(residuals[0]) for start in starts]
            )[:h]
            nn, dd = (
                float(forecast.sum() + residual[idx].sum())
                for forecast, residual in zip(forecasts, residuals)
            )
            if dd <= 0 or (metric["unit"] == "rate" and not 0 <= nn <= dd):
                fails.add("MODEL_MISMATCH")
                break
            differences.append(nn / dd - predicted)
        if not fails:
            half = float(np.quantile(np.abs(differences), 0.95))
            interval = [estimate - half, estimate + half]
    return _replace_report(
        outputs[0],
        metric,
        digest(
            {
                "numerator": numerator,
                "denominator": denominator,
                "component_refs": [
                    o["contracts"]["EffectEstimate"]["digest"] for o in outputs
                ],
            }
        ),
        estimate=estimate,
        interval=interval,
        failures=fails,
        diagnostics={
            "interval_method": "paired_component_residual_block_ratio_envelope",
            "component_models": outputs,
            "ratio_aggregation": "ratio_of_sums",
            "paired_residual_blocks": True,
            "bootstrap_samples": draws,
            "interval_scope": "conditional paired forecast residual-block envelope; preserves numerator-denominator covariance",
        },
    )


def apply_negative_controls(result, *, checks):
    """Attach prespecified negative-control equivalence bounds, fail closed.

    checks: estimate, interval, tolerance, evidence_ref, prespecified_ref. Bounds
    must be independently produced (e.g. the same estimator on a negative outcome).
    """
    if not checks:
        raise ValueError("nonempty negative-control checks required")
    failures = []
    for check in checks:
        tol = finite(check["tolerance"], "negative control tolerance")
        ci = check.get("interval")
        passed = bool(
            ci is not None
            and len(ci) == 2
            and tol > 0
            and -tol
            < finite(ci[0], "low")
            <= finite(check["estimate"], "estimate")
            <= finite(ci[1], "high")
            < tol
            and check.get("evidence_ref")
            and check.get("prespecified_ref")
        )
        if not passed:
            failures.append("MODEL_MISMATCH")
    metric, effect = (
        result["contracts"]["MetricContract"],
        result["contracts"]["EffectEstimate"],
    )
    return _replace_report(
        result,
        metric,
        digest({"source": effect["digest"], "checks": checks}),
        estimate=effect["estimate"],
        interval=effect["interval"],
        failures=failures,
        diagnostics={**effect["diagnostics"], "negative_control_checks": checks},
    )


def run_negative_control_suite(primary_result, *, negative_requests):
    """Execute prespecified negative-outcome estimators before applying equivalence gates."""
    functions = {
        "did": estimate_did_effect,
        "series": estimate_controlled_series_effect,
        "staggered_did": estimate_staggered_did,
        "ratio_series": estimate_ratio_series,
        "bsts_mixture": estimate_bsts_mixture,
    }
    checks, runs = [], []
    for request in negative_requests:
        if request.get("operation") not in functions or not request.get(
            "prespecified_ref"
        ):
            raise ValueError("registered negative-control estimator required")
        result = functions[request["operation"]](**request["parameters"])
        effect = result["contracts"]["EffectEstimate"]
        runs.append(result)
        checks.append(
            {
                "estimate": effect["estimate"],
                "interval": effect["interval"],
                "tolerance": request["tolerance"],
                "evidence_ref": effect["digest"],
                "prespecified_ref": request["prespecified_ref"],
            }
        )
    output = apply_negative_controls(primary_result, checks=checks)
    output["negative_control_runs"] = runs
    return output
