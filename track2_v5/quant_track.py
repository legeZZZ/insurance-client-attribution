"""Identification-gated three-track estimation with explicit design routing.

Every call recomputes design checks from the supplied observations. A report
from another dataset cannot be supplied to bypass identification.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import binomtest
from scipy.stats import t as student_t
from sklearn.linear_model import Ridge

from .contracts import digest, validate_bundle, validate_contract
from .identification import identify_effect
from .observational_tracks import (
    estimate_controlled_series_effect,
    estimate_did_effect,
)


def estimate_randomized_effect(
    rows,
    metric_contract,
    *,
    assignment_ref,
    randomized,
    observed_through,
    no_interference_ref,
    method="ITT",
    features=(),
    feature_roles=None,
    propensity=0.5,
    unit_column="unit_id",
    cluster_column=None,
    folds=5,
    seed=20260914,
    selection_status="pre_registered",
):
    if method not in {"ITT", "CUPED", "CUPAC", "AIPW"}:
        raise ValueError("Track A method must be ITT, CUPED, CUPAC or AIPW")
    if method == "CUPED" and len(features) != 1:
        raise ValueError("CUPED requires exactly one pretreatment outcome covariate")
    if method == "ITT" and features:
        raise ValueError(
            "unadjusted ITT does not consume features; select CUPAC or AIPW"
        )
    if not 0 < propensity < 1 or isinstance(propensity, bool):
        raise ValueError("propensity must be a prespecified probability")
    if not isinstance(folds, int) or isinstance(folds, bool) or folds < 2:
        raise ValueError("folds must be an integer >= 2")
    metric = validate_contract("MetricContract", metric_contract)
    if not rows:
        raise ValueError("observations must be nonempty")
    if len(set(features)) != len(features):
        raise ValueError("features must be unique")
    roles = dict(feature_roles or {})
    y = np.asarray([r["outcome"] for r in rows], dtype=float)
    treatment = np.asarray([r["treatment"] for r in rows], dtype=float)
    if not np.all(np.isfinite(y)) or not np.all(np.isin(treatment, [0, 1])):
        raise ValueError("finite outcomes and binary assignments required")
    if metric["unit"] == "rate" and not np.all(np.isin(y, [0, 1])):
        raise ValueError(
            "rate RCT adapter requires one binary outcome per analysis unit"
        )
    unit_ids = [r[unit_column] for r in rows]
    if any(
        isinstance(v, bool) or not isinstance(v, (str, int)) or v == ""
        for v in unit_ids
    ):
        raise ValueError(
            "analysis units require nonempty string or integer identifiers"
        )
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError(
            "duplicate analysis units; aggregate observations before estimation"
        )
    group_ids = [r[cluster_column] for r in rows] if cluster_column else unit_ids
    if any(
        isinstance(v, bool) or not isinstance(v, (str, int)) or v == ""
        for v in group_ids
    ):
        raise ValueError(
            "randomization groups require nonempty string or integer identifiers"
        )
    unique_groups = sorted(set(group_ids), key=str)
    group_index = {g: i for i, g in enumerate(unique_groups)}
    indices = np.asarray([group_index[g] for g in group_ids])
    assignment_sets = [set(treatment[indices == i]) for i in range(len(unique_groups))]
    consistent = all(len(a) == 1 for a in assignment_sets)
    cluster_t = np.asarray([next(iter(a)) for a in assignment_sets])
    nt, nc = int(np.sum(cluster_t)), int(len(cluster_t) - np.sum(cluster_t))
    srm_p = float(binomtest(nt, len(cluster_t), propensity).pvalue)
    x = (
        np.asarray([[r[f] for f in features] for r in rows], dtype=float)
        if features
        else np.ones((len(rows), 1))
    )
    if not np.all(np.isfinite(x)):
        raise ValueError("features must be finite")
    binding = digest(
        {
            "rows": [
                {
                    unit_column: r[unit_column],
                    "cluster": g,
                    "treatment": float(t),
                    "outcome": float(v),
                    "features": a.tolist(),
                }
                for r, g, t, v, a in zip(rows, group_ids, treatment, y, x)
            ],
            "metric": metric["digest"],
            "method": method,
            "features": list(features),
            "propensity": propensity,
        }
    )

    def checked(passed, reference=binding):
        return {
            "status": "supported" if passed else "failed",
            "evidence_refs": [reference] if reference else [],
        }

    checks = {
        "data_valid": checked(True),
        "assignment_consistent": checked(consistent),
        "assignment_traceable": checked(
            randomized is True and bool(assignment_ref), assignment_ref
        ),
        "srm_pass": checked(srm_p >= 0.001),
        "outcome_mature": checked(
            observed_through is not None
            and observed_through >= metric["window"][1] + metric["maturity_days"]
        ),
        "support_overlap": checked(min(nt, nc) >= 2),
        "interference_absent": {
            "status": "assumed" if no_interference_ref else "missing",
            "evidence_refs": [no_interference_ref] if no_interference_ref else [],
        },
    }
    identification = identify_effect(
        treatment="assignment",
        outcome=metric["name"],
        design="RCT",
        checks=checks,
        data_digest=binding,
        target_population=metric["target_population"],
        adjustment_set=features,
        feature_roles=roles,
    )
    diagnostics = {
        "srm_pvalue": srm_p,
        "srm_alpha": 0.001,
        "randomization_groups": len(unique_groups),
        "treated_groups": nt,
        "control_groups": nc,
        "data_digest": binding,
        "variance_unit": cluster_column or unit_column,
        "interval_scope": "pointwise; not adjusted for adaptive subgroup selection",
    }
    estimate, interval = None, None
    if identification["status"] == "IDENTIFIED":
        if method in {"AIPW", "CUPAC", "CUPED"}:
            if min(nt, nc) < folds:
                raise ValueError("cross-fitting requires at least folds groups per arm")
            # Stratify folds by randomized clusters; all observations in a cluster stay together.
            rng = np.random.default_rng(seed)
            group_folds = np.zeros(len(unique_groups), dtype=int)
            for arm in (0, 1):
                shuffled = rng.permutation(np.flatnonzero(cluster_t == arm))
                group_folds[shuffled] = np.arange(len(shuffled)) % folds
            fold_ids = group_folds[indices]
            m0, m1, pooled = np.zeros(len(y)), np.zeros(len(y)), np.zeros(len(y))
            audit = []
            for fold in range(folds):
                test = fold_ids == fold
                train = ~test
                # Preprocessing statistics are also training-only.
                center, scale = x[train].mean(axis=0), x[train].std(axis=0)
                xx = (x - center) / np.maximum(scale, 1e-12)
                if method == "AIPW":
                    for arm, prediction in ((0, m0), (1, m1)):
                        arm_train = train & (treatment == arm)
                        prediction[test] = (
                            Ridge(alpha=1.0)
                            .fit(xx[arm_train], y[arm_train])
                            .predict(xx[test])
                        )
                else:
                    pooled[test] = (
                        Ridge(alpha=0.0 if method == "CUPED" else 1.0)
                        .fit(xx[train], y[train])
                        .predict(xx[test])
                    )
                audit.append(
                    {
                        "fold": fold,
                        "training_group_indices": np.flatnonzero(
                            group_folds != fold
                        ).tolist(),
                        "evaluation_group_indices": np.flatnonzero(
                            group_folds == fold
                        ).tolist(),
                    }
                )
            diagnostics["crossfit"] = {
                "folds": audit,
                "features": list(features),
                "seed": seed,
                "nuisance_model": "linear_CUPED_training_only"
                if method == "CUPED"
                else "ridge_alpha_1_training_only_standardization",
            }
        if method == "AIPW":
            score = (
                m1
                - m0
                + treatment * (y - m1) / propensity
                - (1 - treatment) * (y - m0) / (1 - propensity)
            )
            estimate = float(score.mean())
            influence = score - estimate
        else:
            outcome = y - pooled if method in {"CUPED", "CUPAC"} else y
            mean1, mean0 = (
                outcome[treatment == 1].mean(),
                outcome[treatment == 0].mean(),
            )
            estimate = float(mean1 - mean0)
            observed_p = treatment.mean()
            influence = treatment * (outcome - mean1) / observed_p - (1 - treatment) * (
                outcome - mean0
            ) / (1 - observed_p)
        group_sums = np.bincount(
            indices, weights=influence, minlength=len(unique_groups)
        )
        g = len(unique_groups)
        se = float(np.sqrt((g / (g - 1)) * np.sum(group_sums**2)) / len(y))
        critical = float(student_t.ppf(0.975, g - 1))
        interval = [estimate - critical * se, estimate + critical * se]
        diagnostics.update(
            standard_error=se,
            degrees_of_freedom=g - 1,
            variance_method="cluster_sum_influence_function",
        )
    effect = {
        "estimand": "ITT",
        "unit": metric["unit"],
        "estimate": estimate,
        "interval": interval,
        "interval_method": "cluster_influence_t_approximation",
        "selection_status": selection_status,
        "target_population": metric["target_population"],
        "window": metric["window"],
        "diagnostics": diagnostics,
        "identification_ref": identification["digest"],
        "method": method,
    }
    bundle = validate_bundle(
        {
            "MetricContract": metric,
            "IdentificationReport": identification,
            "EffectEstimate": effect,
        }
    )
    return {
        "track": "A",
        "status": "ESTIMATED" if estimate is not None else "REFUSED",
        "contracts": bundle,
    }


def estimate_effect(*, route, parameters):
    """Unified three-track API; routes are explicit registered designs, not model guesses."""
    from .gcm_track import estimate_gcm_effect
    from .observational_extensions import (
        estimate_bsts_mixture,
        estimate_ratio_series,
        estimate_staggered_did,
    )
    from .randomized_extensions import estimate_causal_forest, estimate_ratio_effect

    routes = {
        "A": estimate_randomized_effect,
        "A_ratio": estimate_ratio_effect,
        "A_forest": estimate_causal_forest,
        "B_DiD": estimate_did_effect,
        "B_staggered_DiD": estimate_staggered_did,
        "B_series": estimate_controlled_series_effect,
        "B_ratio": estimate_ratio_series,
        "B_BSTS_mixture": estimate_bsts_mixture,
        "C": estimate_gcm_effect,
    }
    if route not in routes or not isinstance(parameters, dict):
        raise ValueError(
            "a supported explicit causal design route and parameters are required"
        )
    return routes[route](**parameters)
