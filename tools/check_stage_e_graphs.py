"""Actual graph pressure, L0 transfer coverage and historical hidden benchmark replay."""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tools.check_stage_e_statistics import (
    effect_request,
    full_pipeline,
    summarize_effect,
)
from track2_v5.baseline_attribution import attribute_baseline
from track2_v5.causal_discovery import discover_causal_graph
from track2_v5.evaluation import binomial_interval, mean_interval
from track2_v5.persistence import atomic_json


def run(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    protocol = {
        "graph_seeds": list(range(81000, 81020)),
        "graph_cases": [
            "lagged",
            "latent_common",
            "nonlinear",
            "deterministic",
            "selection",
        ],
        "transfer_seeds": list(range(82000, 82100)),
        "ci_tests": "both PCMCI+ and LPCMCI; nonlinear uses CMIknn",
        "max_ci_tests": 3000,
        "shuffle_samples": 99,
        "hidden_seeds": [101, 211, 307, 401, 503, 601, 701, 809],
    }
    atomic_json(out / "protocol.json", protocol)
    report = {}
    for case in protocol["graph_cases"]:
        runs = []
        for seed in protocol["graph_seeds"]:
            rng = np.random.default_rng(seed)
            n = 100
            x = rng.normal(size=n)
            y = rng.normal(size=n)
            truth = set()
            if case == "lagged":
                y = 0.9 * np.roll(x, 1) + 0.25 * y
                truth = {("x", "y", 1)}
            elif case == "latent_common":
                z = rng.normal(size=n)
                x = z + 0.3 * x
                y = z + 0.3 * y
            elif case == "nonlinear":
                y = np.roll(x, 1) ** 2 + 0.1 * y
                truth = {("x", "y", 1)}
            elif case == "deterministic":
                y = -x
            else:
                # Conditioning on a common effect induces selection dependence.
                pairs = rng.normal(size=(1000, 2))
                pairs = pairs[np.abs(pairs.sum(axis=1)) < 0.3][:100]
                x, y = pairs.T
                n = len(x)
            with contextlib.redirect_stdout(io.StringIO()):
                result = discover_causal_graph(
                    list(range(n)),
                    {"x": x.tolist(), "y": y.tolist()},
                    screened_candidates=["x", "y"],
                    tau_max=1,
                    response_window_basis="frozen generated lag horizon",
                    test_policy="cmiknn" if case == "nonlinear" else "parcorr",
                    max_condition_dim=2,
                    shuffle_samples=99,
                    max_ci_tests=3000,
                    seed=seed,
                )
            directed = {
                (e["source"][0], e["target"][0], e["target"][1] - e["source"][1])
                for e in result.get("consensus_time_expanded_edges", [])
            }
            runs.append(
                {
                    "seed": seed,
                    "status": result["status"],
                    "truth_edges": sorted(truth),
                    "selected_edges": sorted(directed),
                    "fdp": len(directed - truth) / max(1, len(directed)),
                    "power": len(directed & truth) / len(truth) if truth else None,
                    "reason_codes": result.get("reason_codes", []),
                    "ambiguities": result.get("ambiguities", []),
                    "ci_tests_spent": result.get("ci_tests_spent", 0),
                    "causal_effect_allowed": result["causal_effect_allowed"],
                    "result": result,
                }
            )
        report[case] = {
            "runs": runs,
            "summary": {
                "orientation_fdp": mean_interval(
                    [r["fdp"] for r in runs], bounded=True
                ),
                "power": mean_interval(
                    [r["power"] for r in runs if r["power"] is not None], bounded=True
                ),
                "ambiguity_rate": mean_interval(
                    [float(bool(r["ambiguities"])) for r in runs], bounded=True
                ),
                "false_causal_assertion_rate": sum(
                    r["causal_effect_allowed"] for r in runs
                )
                / len(runs),
                "false_causal_mc_interval_95": binomial_interval(
                    sum(r["causal_effect_allowed"] for r in runs), len(runs)
                ),
            },
        }
        atomic_json(out / "graphs.json", report)
        print("graph", case, flush=True)
    transfer = []
    for seed in protocol["transfer_seeds"]:
        req, truth, _ = effect_request("A_signal", seed)
        result, _ = full_pipeline(req)
        effect = result["result"]["contracts"]["EffectEstimate"]
        m = req["parameters"]["metric_contract"]
        m["window"] = [0, 19]
        estimate = effect["estimate"]
        if estimate is None:
            transfer.append(
                {"seed": seed, "truth": truth * 0.5, "estimate": None, "interval": None}
            )
            continue
        change = {
            "change_id": "a",
            "start_day": 0,
            "end_day": 19,
            "coverage": 0.5,
            "target_population": m["target_population"],
            "experiment_id": "e",
        }
        source = {
            "att_estimate": estimate,
            "att_se": effect["diagnostics"]["standard_error"],
            "unit": m["unit"],
            "target_population": m["target_population"],
            "evidence_ref": effect["digest"],
        }
        baseline = attribute_baseline(
            list(range(20)),
            [10.0] * 20,
            [10.0 + truth * 0.5] * 20,
            [change],
            [],
            {"e": source},
            metric_contract=m,
        )
        lo, hi = baseline["explained_uncertainty"]["interval_95"][10]
        transfer.append(
            {
                "seed": seed,
                "truth": truth * 0.5,
                "estimate": baseline["series"]["explained_registered"][10],
                "interval": [lo, hi],
                "covered": lo <= truth * 0.5 <= hi,
                "published_estimate": baseline["series"]["explained_registered"][10],
                "published_interval": [lo, hi],
            }
        )
    atomic_json(
        out / "transfer.json",
        {
            "runs": transfer,
            "summary": summarize_effect(transfer),
            "scope": "A estimator through registered coverage/time response and L0 covariance propagation; fixed transfer assumptions, not estimated coverage uncertainty",
        },
    )
    from goai_control_tower.track2_benchmark import run_hidden_benchmark

    hidden = run_hidden_benchmark(seeds=protocol["hidden_seeds"], n=1200)
    hidden["scope"] = (
        "actual restored historical baseline; retain all failed gates, no pass-label rewriting"
    )
    atomic_json(out / "historical_hidden.json", hidden)
    print("historical_hidden", hidden["metrics"], flush=True)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "outputs/stage_e/graphs")
