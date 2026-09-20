"""Tigramite graph discovery with explicit equivalence-class uncertainty.

Graph discovery produces hypotheses, never IdentificationReport eligibility.
The caller fixes the CI-test policy and response horizon before observing results.
"""

from __future__ import annotations

import importlib.metadata
import time

import numpy as np

from .contracts import digest
from .input_validation import validate_ordered_series


def graph_variables(screened, protected, mechanisms, parent_map=None):
    parent_map = dict(parent_map or {})

    def parent(name):
        seen = set()
        while name in parent_map:
            if name in seen:
                raise ValueError("cyclic derived-variable lineage")
            seen.add(name)
            name = parent_map[name]
        if not isinstance(name, str) or not name:
            raise ValueError("graph variable names must be nonempty strings")
        return name

    return sorted(
        {parent(n) for group in (screened, protected, mechanisms) for n in group}
    )


def _edges(graph, names):
    edges = []
    for i, source in enumerate(names):
        for j, target in enumerate(names):
            for lag in range(graph.shape[2]):
                endpoint = str(graph[i, j, lag])
                if not endpoint or (lag == 0 and i > j):
                    continue
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "lag": lag,
                        "endpoints": endpoint,
                        "orientation_resolved": endpoint in {"-->", "<--"},
                    }
                )
    return edges


def discover_causal_graph(
    days,
    columns,
    *,
    screened_candidates,
    protected_covariates=(),
    known_mechanism_nodes=(),
    parent_map=None,
    tau_max,
    response_window_basis,
    test_policy="parcorr",
    alpha=0.05,
    max_condition_dim=3,
    max_variables=12,
    seed=20260914,
    shuffle_samples=99,
    shuffle_block_length=5,
    max_ci_tests=100000,
):
    if test_policy not in {"parcorr", "cmiknn", "both"}:
        raise ValueError("test_policy must be fixed to parcorr, cmiknn or both")
    if not isinstance(tau_max, int) or isinstance(tau_max, bool) or tau_max < 0:
        raise ValueError("tau_max must be a nonnegative integer")
    if not isinstance(response_window_basis, str) or not response_window_basis.strip():
        raise ValueError("response horizon requires a declared basis")
    if (
        not 0 < alpha < 1
        or not isinstance(max_condition_dim, int)
        or max_condition_dim < 0
    ):
        raise ValueError("invalid alpha or conditioning budget")
    if not isinstance(shuffle_samples, int) or shuffle_samples < 9:
        raise ValueError("shuffle_samples must be at least 9")
    if (
        not isinstance(shuffle_block_length, int)
        or isinstance(shuffle_block_length, bool)
        or shuffle_block_length < 1
    ):
        raise ValueError("shuffle_block_length must be a positive integer")
    names = graph_variables(
        screened_candidates, protected_covariates, known_mechanism_nodes, parent_map
    )
    if not 2 <= len(names) <= max_variables:
        raise ValueError("graph variable count outside declared budget")
    missing = set(names) - set(columns)
    if missing:
        raise ValueError(f"missing graph variables: {sorted(missing)}")
    validate_ordered_series(
        days, *[columns[n] for n in names], component="causal_graph"
    )
    if any(b - a != 1 for a, b in zip(days, days[1:])):
        raise ValueError("Tigramite graph adapter requires a regular daily grid")
    matrix = np.column_stack([columns[n] for n in names]).astype(float)
    manifest = {
        "variables": names,
        "protected_covariates": list(protected_covariates),
        "known_mechanism_nodes": list(known_mechanism_nodes),
        "parent_map": dict(parent_map or {}),
        "tau_max": tau_max,
        "response_window_basis": response_window_basis,
        "test_policy": test_policy,
        "alpha": alpha,
        "max_condition_dim": max_condition_dim,
        "shuffle_samples": shuffle_samples,
        "shuffle_block_length": shuffle_block_length,
        "seed": seed,
        "data_digest": digest(
            {
                "days": [int(d) for d in days],
                "columns": {n: matrix[:, i].tolist() for i, n in enumerate(names)},
            }
        ),
    }
    base = {
        "model": "tigramite_pcmciplus_lpcmci",
        "selection_manifest": manifest,
        "claim_type": "CAUSAL_GRAPH_HYPOTHESIS",
        "causal_effect_allowed": False,
        "assumptions": [
            "causal_stationarity",
            "Markov_and_faithfulness",
            "CI_test_model_applicability",
        ],
        "notes": [
            "PCMCI+ additionally assumes causal sufficiency",
            "PAG circles are unresolved endpoints, not proof of latent confounding",
        ],
    }
    if len(days) < max(30, 2 * tau_max + 10):
        return {
            **base,
            "status": "INSUFFICIENT_EVIDENCE",
            "reason_codes": ["INSUFFICIENT_POWER"],
            "runs": [],
            "ambiguities": ["short_series"],
        }
    constants = [n for n in names if np.std(matrix[:, names.index(n)]) <= 1e-12]
    if constants or np.linalg.matrix_rank(matrix - matrix.mean(axis=0)) < len(names):
        return {
            **base,
            "status": "INSUFFICIENT_EVIDENCE",
            "reason_codes": ["MODEL_MISMATCH"],
            "runs": [],
            "ambiguities": ["constant_or_deterministically_dependent_variables"],
            "constant_variables": constants,
        }
    from tigramite import data_processing
    from tigramite.independence_tests.parcorr import ParCorr
    from tigramite.lpcmci import LPCMCI
    from tigramite.pcmci import PCMCI

    if not isinstance(max_ci_tests, int) or max_ci_tests < 1:
        raise ValueError("positive CI test budget required")
    attempted_tests = []

    def counted(base, policy, algorithm):
        class CountedTest(base):
            def run_test(self, *args, **kwargs):
                if len(attempted_tests) >= max_ci_tests:
                    error = ValueError("CI test budget exhausted")
                    error.attempted_tests = attempted_tests
                    raise error
                entry = {
                    "algorithm": algorithm,
                    "policy": policy,
                    "X": kwargs.get("X", args[0] if args else []),
                    "Y": kwargs.get("Y", args[1] if len(args) > 1 else []),
                    "Z": kwargs.get("Z", []),
                    "status": "ATTEMPTED",
                }
                for key in ("X", "Y", "Z"):
                    entry[key] = [[int(v) for v in pair] for pair in (entry[key] or [])]
                attempted_tests.append(entry)
                result = super().run_test(*args, **kwargs)
                entry.update(
                    statistic=float(result[0]),
                    raw_pvalue=float(result[1]),
                    status="COMPLETED",
                )
                return result

        return CountedTest

    frame = data_processing.DataFrame(matrix, var_names=names)
    policies = ("parcorr", "cmiknn") if test_policy == "both" else (test_policy,)
    runs, arrays = [], []
    for policy in policies:
        for algorithm in ("PCMCI+", "LPCMCI"):
            if policy == "parcorr":
                test = counted(ParCorr, policy, algorithm)(significance="analytic")
            else:
                from tigramite.independence_tests.cmiknn import CMIknn

                test = counted(CMIknn, policy, algorithm)(
                    significance="shuffle_test",
                    sig_samples=shuffle_samples,
                    sig_blocklength=shuffle_block_length,
                    workers=1,
                    seed=seed,
                )
            started = time.monotonic()
            if algorithm == "PCMCI+":
                result = PCMCI(
                    dataframe=frame, cond_ind_test=test, verbosity=0
                ).run_pcmciplus(
                    tau_min=0,
                    tau_max=tau_max,
                    pc_alpha=alpha,
                    max_conds_dim=max_condition_dim,
                )
            else:
                result = LPCMCI(
                    dataframe=frame, cond_ind_test=test, verbosity=0
                ).run_lpcmci(
                    tau_min=0,
                    tau_max=tau_max,
                    pc_alpha=alpha,
                    max_p_global=max_condition_dim,
                )
            graph = result["graph"]
            arrays.append(graph)
            runs.append(
                {
                    "algorithm": algorithm,
                    "ci_test": policy,
                    "edges": _edges(graph, names),
                    "graph": graph.tolist(),
                    "p_matrix": np.where(
                        np.isfinite(result["p_matrix"]), result["p_matrix"], None
                    ).tolist(),
                    "val_matrix": np.where(
                        np.isfinite(result["val_matrix"]), result["val_matrix"], None
                    ).tolist(),
                    "runtime_seconds": time.monotonic() - started,
                }
            )
    ambiguities = []
    for run in runs:
        for edge in run["edges"]:
            if not edge["orientation_resolved"]:
                ambiguities.append(
                    f"{run['algorithm']}/{run['ci_test']}:{edge['source']}:{edge['target']}:{edge['lag']}:{edge['endpoints']}"
                )
    disagreements = []
    for index in np.ndindex(arrays[0].shape):
        labels = [str(a[index]) for a in arrays]
        if len(set(labels)) > 1:
            disagreements.append(
                {
                    "source": names[index[0]],
                    "target": names[index[1]],
                    "lag": index[2],
                    "endpoints_by_run": labels,
                }
            )
    if disagreements:
        ambiguities.append("algorithm_or_CI_test_disagreement")
    # Expose time-expanded edges only when every run agrees on a direction.
    expanded = []
    for edge in runs[0]["edges"]:
        i, j, lag = (
            names.index(edge["source"]),
            names.index(edge["target"]),
            edge["lag"],
        )
        if (
            len({str(a[i, j, lag]) for a in arrays}) != 1
            or not edge["orientation_resolved"]
        ):
            continue
        for t in range(-tau_max + lag, 1):
            source, target = (edge["source"], t - lag), (edge["target"], t)
            if edge["endpoints"] == "<--":
                source, target = target, source
            expanded.append({"source": list(source), "target": list(target)})
    report = {
        **base,
        "status": "COMPLETED",
        "attempted_tests": attempted_tests,
        "ci_tests_spent": len(attempted_tests),
        "runs": runs,
        "ambiguities": sorted(set(ambiguities)),
        "disagreements": disagreements,
        "consensus_time_expanded_edges": expanded,
        "tigramite_version": importlib.metadata.version("tigramite"),
        "graph_discovery_does_not_certify_identification": True,
    }
    report["digest"] = digest(report)
    return report
