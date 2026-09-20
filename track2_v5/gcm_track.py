"""DoWhy-GCM mechanism attribution and separately labelled intervention ATE.

Continuous additive-noise models on an explicitly accepted DAG. Distribution
Shapley values are never substituted for intervention effects. Sampling,
bootstrap, graph and structural-assumption uncertainty remain separate.
"""

from __future__ import annotations

import contextlib
import random

import networkx as nx
import numpy as np
import pandas as pd
from dowhy import gcm

from .contracts import digest, finite, integer, validate_bundle, validate_contract
from .identification import _is_dag, identify_effect


@contextlib.contextmanager
def _seeded(seed):
    state, py_state = np.random.get_state(), random.getstate()
    np.random.seed(seed)
    random.seed(seed)
    try:
        yield
    finally:
        np.random.set_state(state)
        random.setstate(py_state)


def _fit(dag, frame):
    graph = nx.DiGraph()
    graph.add_nodes_from(dag["nodes"])
    graph.add_edges_from(dag["edges"])
    model = gcm.StructuralCausalModel(graph)
    for node in graph:
        model.set_causal_mechanism(
            node,
            gcm.EmpiricalDistribution()
            if graph.in_degree(node) == 0
            else gcm.AdditiveNoiseModel(gcm.ml.create_linear_regressor()),
        )
    gcm.fit(model, frame)
    return model


def estimate_gcm_effect(
    old_rows,
    new_rows,
    metric_contract,
    *,
    accepted_dag,
    treatment,
    treatment_reference,
    treatment_alternative,
    causal_sufficiency_ref,
    independent_rows_ref,
    mechanism_rmse_limits,
    graph_report=None,
    functional="mean",
    bootstrap_samples=30,
    simulation_samples=1000,
    seed=20260915,
    observed_through=None,
):
    metric = validate_contract("MetricContract", metric_contract)
    target = metric["name"]
    if functional not in {"mean", "variance", "kl"}:
        raise ValueError("functional must be mean, variance or kl")
    boots, draws = (
        integer(bootstrap_samples, "bootstrap_samples"),
        integer(simulation_samples, "simulation_samples"),
    )
    if boots < 20 or draws < 200:
        raise ValueError("at least 20 bootstraps and 200 simulation draws required")
    dag_ok = _is_dag(accepted_dag, treatment, target)
    nodes = accepted_dag.get("nodes", []) if isinstance(accepted_dag, dict) else []
    if len(nodes) > 6:
        raise ValueError("exact-Shapley budget supports at most six nodes")
    frames = [pd.DataFrame(rows) for rows in (old_rows, new_rows)]
    if any(
        len(frame) < 40 or any(node not in frame for node in nodes) for frame in frames
    ):
        raise ValueError(
            "complete old/new panels with at least 40 independent rows required"
        )
    for frame in frames:
        if not np.all(np.isfinite(frame[nodes].to_numpy(dtype=float))):
            raise ValueError("all GCM nodes must be finite numeric variables")
    reference, alternative = (
        finite(treatment_reference, "treatment_reference"),
        finite(treatment_alternative, "treatment_alternative"),
    )
    if reference == alternative:
        raise ValueError("distinct interventions required")
    binding = digest(
        {
            "old_rows": old_rows,
            "new_rows": new_rows,
            "dag": accepted_dag,
            "metric": metric["digest"],
            "functional": functional,
            "bootstrap_samples": boots,
            "simulation_samples": draws,
            "seed": seed,
            "mechanism_rmse_limits": mechanism_rmse_limits,
        }
    )
    diagnostics, fitted = [], dag_ok
    if dag_ok:
        for period, frame in zip(("old", "new"), frames):
            split = int(0.7 * len(frame))
            for node in nodes:
                parents = [a for a, b in accepted_dag["edges"] if b == node]
                if not parents:
                    continue
                from sklearn.linear_model import LinearRegression

                x = frame[parents].to_numpy(dtype=float)
                full_rank = (
                    np.linalg.matrix_rank(np.column_stack([np.ones(split), x[:split]]))
                    == len(parents) + 1
                )
                limit = finite(
                    mechanism_rmse_limits.get(node, -1), "mechanism_rmse_limit"
                )
                if limit < 0:
                    raise ValueError(
                        "prespecified nonnegative RMSE limit required for every nonroot"
                    )
                prediction = (
                    LinearRegression()
                    .fit(x[:split], frame[node].iloc[:split])
                    .predict(x[split:])
                )
                rmse = float(
                    np.sqrt(
                        np.mean((frame[node].iloc[split:].to_numpy() - prediction) ** 2)
                    )
                )
                passed = bool(full_rank and rmse <= limit)
                fitted = fitted and passed
                diagnostics.append(
                    {
                        "period": period,
                        "node": node,
                        "parents_full_rank": bool(full_rank),
                        "heldout_rmse": rmse,
                        "limit": limit,
                        "passed": passed,
                    }
                )

    def check(ok):
        return {"status": "supported" if ok else "failed", "evidence_refs": [binding]}

    def assumption(ref):
        if ref is not None and (not isinstance(ref, str) or not ref.strip()):
            raise ValueError("assumption references must be text")
        return {
            "status": "assumed" if ref else "missing",
            "evidence_refs": [ref] if ref else [],
        }

    support = dag_ok and all(
        frame[treatment].min() <= min(reference, alternative)
        and frame[treatment].max() >= max(reference, alternative)
        for frame in frames
    )
    checks = {
        "data_valid": check(True),
        "outcome_mature": check(
            observed_through is not None
            and observed_through >= metric["window"][1] + metric["maturity_days"]
        ),
        "support_overlap": check(support),
        "no_extrapolation": check(support),
        "accepted_graph": check(dag_ok),
        "mechanisms_fitted": check(fitted),
        "causal_sufficiency": assumption(causal_sufficiency_ref),
        "independent_units": assumption(independent_rows_ref),
    }
    report = identify_effect(
        treatment=treatment,
        outcome=target,
        design="GCM",
        checks=checks,
        data_digest=binding,
        target_population=metric["target_population"],
        graph_report=graph_report,
        accepted_dag=accepted_dag,
    )
    attribution, ate, interval, bootstrap = None, None, None, []
    sampling_repeats = []
    if report["status"] == "IDENTIFIED":
        gcm.config.disable_progress_bars()
        config = gcm.shapley.ShapleyConfig(
            approximation_method=gcm.shapley.ShapleyApproximationMethods.EXACT, n_jobs=1
        )

        def difference(a, b):
            if functional == "mean":
                return float(np.mean(b) - np.mean(a))
            if functional == "variance":
                return float(np.var(b) - np.var(a))
            return float(gcm.divergence.auto_estimate_kl_divergence(a, b))

        def run(old, new):
            models = [_fit(accepted_dag, data) for data in (old, new)]
            attrs = gcm.distribution_change_of_graphs(
                *models,
                target,
                num_samples=draws,
                difference_estimation_func=difference,
                shapley_config=config,
            )
            effect = gcm.average_causal_effect(
                models[0],
                target,
                {treatment: lambda x: np.full_like(x, alternative, dtype=float)},
                {treatment: lambda x: np.full_like(x, reference, dtype=float)},
                num_samples_to_draw=draws,
            )
            return {str(k): float(v) for k, v in attrs.items()}, float(effect)

        with _seeded(seed):
            attribution, ate = run(*frames)
            # Separate Monte Carlo repetition on fixed observations from row bootstrap.
            for _ in range(3):
                sampling_repeats.append(run(*frames)[1])
            rng = np.random.default_rng(seed)
            for _ in range(boots):
                resampled = [
                    frame.iloc[rng.integers(0, len(frame), len(frame))].reset_index(
                        drop=True
                    )
                    for frame in frames
                ]
                attrs, value = run(*resampled)
                bootstrap.append({"ate": value, "attribution": attrs})
        low, high = np.quantile([r["ate"] for r in bootstrap], [0.025, 0.975])
        interval = [min(float(low), ate), max(float(high), ate)]
    effect = {
        "estimand": "ATE_intervention_on_old_population",
        "unit": metric["unit"],
        "estimate": ate,
        "interval": interval,
        "interval_method": "iid_row_bootstrap_with_GCM_simulation",
        "selection_status": "exploratory",
        "target_population": metric["target_population"],
        "window": metric["window"],
        "identification_ref": report["digest"],
        "diagnostics": {
            "mechanisms": diagnostics,
            "data_digest": binding,
            "bootstrap_samples": boots,
            "simulation_samples": draws,
            "sampling_ate_repeats": sampling_repeats,
            "graph_uncertainty": "conditional on accepted DAG; alternative graphs not averaged",
            "structural_uncertainty": "linear additive-noise causal sufficiency is a maintained model assumption",
            "support_scope": "observed marginal intervention range; high-dimensional transport not certified",
        },
    }
    attr_intervals = (
        {
            node: np.quantile(
                [r["attribution"].get(node, 0.0) for r in bootstrap], [0.025, 0.975]
            ).tolist()
            for node in attribution
        }
        if attribution
        else None
    )
    return {
        "track": "C",
        "status": "ESTIMATED" if ate is not None else "REFUSED",
        "contracts": validate_bundle(
            {
                "MetricContract": metric,
                "IdentificationReport": report,
                "EffectEstimate": effect,
            }
        ),
        "mechanism_attribution": {
            "functional": functional,
            "unit": metric["unit"]
            if functional == "mean"
            else "squared_metric_units"
            if functional == "variance"
            else "nats",
            "shapley_values": attribution,
            "bootstrap_intervals": attr_intervals,
            "covariance_node_order": list(attribution) if attribution else None,
            "bootstrap_covariance": np.atleast_2d(
                np.cov(
                    [
                        [r["attribution"].get(node, 0.0) for node in attribution]
                        for r in bootstrap
                    ],
                    rowvar=False,
                    ddof=1,
                )
            ).tolist()
            if attribution
            else None,
            "attributed_total": float(sum(attribution.values()))
            if attribution
            else None,
            "interpretation": "distribution mechanism change, not treatment ATE",
            "bootstrap_runs": bootstrap,
        },
    }
