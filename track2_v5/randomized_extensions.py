"""Real honest EconML forest challenger and cluster-aware ratio ITT."""

from __future__ import annotations

import numpy as np
from scipy.stats import t as student_t

from .contracts import digest, finite, validate_bundle, validate_contract
from .quant_track import estimate_randomized_effect


def estimate_ratio_effect(rows, metric_contract, **design):
    """Ratio of sums, influence numerator - arm ratio*denominator, cluster sums.

    One row per analysis unit, possibly multiple units per randomized cluster.
    Requires numerator and denominator observations for each unit, not daily ratios.
    """
    metric = validate_contract("MetricContract", metric_contract)
    if metric["unit"] not in {"rate", "currency_per_user"}:
        raise ValueError("ratio adapter requires a normalized metric")
    if design.get("method", "ITT") != "ITT" or design.get("features"):
        raise ValueError("ratio adapter implements ITT without outcome adjustment")
    num = np.array([finite(r["numerator"], "numerator") for r in rows])
    den = np.array([finite(r["denominator"], "denominator") for r in rows])
    if np.any(den < 0) or (
        metric["unit"] == "rate" and (np.any(num < 0) or np.any(num > den))
    ):
        raise ValueError("invalid ratio components")
    raw_metric = {
        k: v
        for k, v in metric.items()
        if k not in {"digest", "schema_version", "contract_type"}
    }
    raw_metric.update(unit="currency", aggregation="sum", denominator=None)
    surrogate = [{**r, "outcome": float(n)} for r, n in zip(rows, num)]
    base = estimate_randomized_effect(surrogate, raw_metric, **design)
    report = {
        k: v
        for k, v in base["contracts"]["IdentificationReport"].items()
        if k != "digest"
    }
    binding = digest({"rows": rows, "metric": metric["digest"], "design": design})
    report["support"]["data_digest"] = binding
    report["evidence_refs"].append(binding)
    t = np.array([r["treatment"] for r in rows])
    ratios, influence = {}, np.zeros(len(rows))
    estimable = all(np.sum(den[t == a]) > 0 for a in (0, 1))
    if not estimable:
        report.update(
            status="NOT_IDENTIFIED",
            causal_effect_allowed=False,
            reason_codes=sorted(set(report["reason_codes"]) | {"NOT_IDENTIFIABLE"}),
        )
        report["supplemental_evidence_needed"].append("positive arm denominators")
    report = validate_contract("IdentificationReport", report)
    estimate, interval = None, None
    diagnostics = {
        "data_digest": binding,
        "linearization": "numerator - arm_ratio*denominator",
        "interval_scope": "cluster delta-method t approximation; not exact for sparse denominators",
    }
    if report["status"] == "IDENTIFIED":
        for arm, sign in ((1, 1), (0, -1)):
            mask = t == arm
            ratio = float(num[mask].sum() / den[mask].sum())
            ratios[str(arm)] = ratio
            influence[mask] = sign * (num[mask] - ratio * den[mask]) / den[mask].sum()
        key = design.get("cluster_column") or design.get("unit_column", "unit_id")
        groups = sorted({r[key] for r in rows}, key=str)
        sums = np.array(
            [
                sum(influence[i] for i, r in enumerate(rows) if r[key] == g)
                for g in groups
            ]
        )
        se = float(np.sqrt(len(groups) / (len(groups) - 1) * np.sum(sums * sums)))
        estimate = ratios["1"] - ratios["0"]
        half = float(student_t.ppf(0.975, len(groups) - 1)) * se
        interval = [estimate - half, estimate + half]
        diagnostics.update(arm_ratios=ratios, standard_error=se, variance_unit=key)
    effect = {
        "estimand": "ITT_ratio_of_sums",
        "unit": metric["unit"],
        "estimate": estimate,
        "interval": interval,
        "interval_method": "cluster_ratio_delta_t",
        "selection_status": design.get("selection_status", "pre_registered"),
        "target_population": metric["target_population"],
        "window": metric["window"],
        "diagnostics": diagnostics,
        "identification_ref": report["digest"],
        "method": "ratio_ITT",
    }
    return {
        "track": "A",
        "status": "ESTIMATED" if estimate is not None else "REFUSED",
        "contracts": validate_bundle(
            {
                "MetricContract": metric,
                "IdentificationReport": report,
                "EffectEstimate": effect,
            }
        ),
    }


def estimate_causal_forest(
    rows,
    metric_contract,
    *,
    features,
    feature_roles,
    query_features,
    n_estimators=100,
    seed=20260915,
    **design,
):
    from econml.dml import CausalForestDML
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.model_selection import StratifiedKFold

    if not features or n_estimators < 40 or n_estimators % 4:
        raise ValueError(
            "forest needs features and at least 40 trees, multiple of four"
        )
    # Reuse actual randomized-design diagnostics and adjustment eligibility.
    base = estimate_randomized_effect(
        rows,
        metric_contract,
        features=features,
        feature_roles=feature_roles,
        method="AIPW",
        seed=seed,
        **design,
    )
    if base["status"] != "ESTIMATED":
        base["challenger"] = "EconML_CausalForestDML"
        return base
    key = design.get("cluster_column") or design.get("unit_column", "unit_id")
    groups = sorted({r[key] for r in rows}, key=str)
    blocks = [[r for r in rows if r[key] == g] for g in groups]
    if len({len(block) for block in blocks}) != 1:
        raise ValueError(
            "forest cluster adapter requires equal-size clusters for unit-weighted target"
        )
    if any(
        any(any(r[f] != block[0][f] for f in features) for r in block)
        for block in blocks
    ):
        raise ValueError(
            "cluster forest covariates must be constant within each randomization group"
        )
    x = np.array([[r[0][f] for f in features] for r in blocks], dtype=float)
    y = np.array([np.mean([v["outcome"] for v in block]) for block in blocks])
    treatment = np.array([block[0]["treatment"] for block in blocks])
    query = np.asarray(query_features, dtype=float)
    if (
        query.ndim != 2
        or query.shape[1] != len(features)
        or not np.all(np.isfinite(query))
    ):
        raise ValueError("query_features must be a finite matrix matching features")
    if np.any(query < x.min(axis=0)) or np.any(query > x.max(axis=0)):
        raise ValueError("query lies outside observed feature support")
    forest = CausalForestDML(
        model_y=Ridge(alpha=1.0),
        model_t=LogisticRegression(max_iter=1000),
        discrete_treatment=True,
        cv=StratifiedKFold(3, shuffle=True, random_state=seed),
        n_estimators=n_estimators,
        min_samples_leaf=5,
        honest=True,
        inference=True,
        n_jobs=1,
        random_state=seed,
    )
    forest.fit(y, treatment, X=x)
    mean = float(forest.ate(x))
    low, high = (float(v) for v in forest.ate_interval(x))
    cate = forest.effect(query).tolist()
    ci = forest.effect_interval(query)
    metric, report = (
        base["contracts"]["MetricContract"],
        base["contracts"]["IdentificationReport"],
    )
    effect = {**base["contracts"]["EffectEstimate"]}
    effect.pop("digest")
    effect.update(
        estimate=mean,
        interval=[min(low, mean), max(high, mean)],
        method="EconML_CausalForestDML",
        interval_method="honest_forest_BLB_approximation",
        selection_status="exploratory",
        diagnostics={
            "honest": True,
            "n_estimators": n_estimators,
            "variance_unit": key,
            "training_groups": len(groups),
            "seed": seed,
            "interval_scope": "pointwise honest forest approximation, not adaptive subgroup confirmation",
            "query_features": query.tolist(),
            "cate": cate,
            "cate_intervals": np.column_stack(ci).tolist(),
        },
    )
    return {
        "track": "A",
        "status": "ESTIMATED",
        "challenger": "EconML_CausalForestDML",
        "contracts": validate_bundle(
            {
                "MetricContract": metric,
                "IdentificationReport": report,
                "EffectEstimate": effect,
            }
        ),
    }
