"""Fixed-design Monte Carlo, including refusals; never conditionalize away failures."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.persistence import atomic_json
from track2_v5.quant_track import estimate_controlled_series_effect, estimate_did_effect


def metric():
    return {
        "name": "revenue",
        "numerator": "revenue",
        "denominator": None,
        "aggregation": "sum",
        "unit": "currency",
        "analysis_unit": "unit",
        "target_population": "treated units",
        "timezone": "UTC",
        "window": [60, 79],
        "maturity_days": 2,
        "deduplication": "unit/day",
    }


def request(method, seed):
    rng = np.random.default_rng(seed)
    if method == "DiD":
        rows = [
            {
                "unit_id": str(u),
                "day": d,
                "treatment": int(u < 20 and d >= 60),
                "outcome": float(
                    10
                    + u / 20
                    + 0.1 * d
                    + rng.normal(scale=0.5)
                    + 0.5 * (u < 20 and d >= 60)
                ),
            }
            for u in range(40)
            for d in range(80)
        ]
        return {
            "operation": "did_effect",
            "parameters": {
                "rows": rows,
                "metric_contract": metric(),
                "intervention_day": 60,
                "observed_through": 81,
                "control_eligibility": {
                    str(u): {
                        "eligible": True,
                        "unaffected": True,
                        "evidence_ref": "synthetic:untreated",
                    }
                    for u in range(20, 40)
                },
                "no_anticipation_ref": "synthetic:no anticipation",
                "no_differential_shock_ref": "synthetic:common shocks",
                "parallel_trends_ref": "synthetic:parallel DGP",
                "trend_tolerance": 3,
                "independent_units_ref": "synthetic:independent units",
            },
        }, 200.0
    x = rng.normal(size=80) * 2 + 10
    z = rng.normal(size=80)
    controls = {"c1": (x + z).tolist(), "c2": (x - z).tolist(), "c3": x.tolist()}
    level = (
        np.cumsum(rng.normal(scale=0.05, size=80)) if method == "BSTS" else np.zeros(80)
    )
    y = x + level + rng.normal(scale=0.1, size=80)
    y[60:] += 0.5
    return {
        "operation": "controlled_series_effect",
        "parameters": {
            "days": list(range(80)),
            "outcome": y.tolist(),
            "controls": controls,
            "metric_contract": metric(),
            "method": method,
            "intervention_day": 60,
            "observed_through": 81,
            "control_eligibility": {
                name: {
                    "eligible": True,
                    "unaffected": True,
                    "evidence_ref": "synthetic:" + name,
                }
                for name in controls
            },
            "backtest_rmse_limit": 1.0,
            "relationship_ref": "synthetic:stable coefficients",
            "no_spillover_ref": "synthetic:no spillover",
            "prefit_rmse_limit": 0.3,
            "loo_effect_limit": 3.0,
            "max_weight": 0.8,
            "bootstrap_samples": 999,
            "block_length": 2,
            "observation_variance": 0.01,
            "level_variance": 0.0025,
            "prior_variance": 1000.0,
        },
    }, 10.0


def evaluate(repetitions, methods=("DiD", "SCM", "BSTS")):
    result = {
        "scope": "three fixed synthetic designs; not full T32 stress calibration",
        "repetitions": repetitions,
        "seeds": [20260915 + i for i in range(repetitions)],
        "methods": {},
    }
    for method in methods:
        runs = []
        for seed in result["seeds"]:
            req, truth = request(method, seed)
            function = (
                estimate_did_effect
                if method == "DiD"
                else estimate_controlled_series_effect
            )
            output = function(**req["parameters"])
            effect = output["contracts"]["EffectEstimate"]
            estimate, interval = effect["estimate"], effect["interval"]
            runs.append(
                {
                    "seed": seed,
                    "truth": truth,
                    "status": output["status"],
                    "estimate": estimate,
                    "interval": interval,
                    "error": estimate - truth if estimate is not None else None,
                    "covered": interval[0] <= truth <= interval[1]
                    if interval
                    else None,
                    "reason_codes": output["contracts"]["IdentificationReport"][
                        "reason_codes"
                    ],
                }
            )
        accepted = [r for r in runs if r["estimate"] is not None]
        coverage = (
            float(np.mean([r["covered"] for r in accepted])) if accepted else None
        )
        n = len(accepted)
        if n:
            z = 1.95996398454
            center = (coverage + z * z / (2 * n)) / (1 + z * z / n)
            half = (
                z
                * np.sqrt(coverage * (1 - coverage) / n + z * z / (4 * n * n))
                / (1 + z * z / n)
            )
            wilson = [float(center - half), float(center + half)]
        else:
            wilson = None
        result["methods"][method] = {
            "estimated": n,
            "refused": repetitions - n,
            "conditional_coverage": coverage,
            "coverage_wilson_95": wilson,
            "bias": float(np.mean([r["error"] for r in accepted]))
            if accepted
            else None,
            "rmse": float(np.sqrt(np.mean([r["error"] ** 2 for r in accepted])))
            if accepted
            else None,
            "mean_width": float(
                np.mean([r["interval"][1] - r["interval"][0] for r in accepted])
            )
            if accepted
            else None,
            "runs": runs,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=["DiD", "SCM", "BSTS"],
        default=["DiD", "SCM", "BSTS"],
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    output = evaluate(args.repetitions, args.methods)
    atomic_json(args.output, output)
    print(
        json.dumps(
            {
                m: {k: v for k, v in r.items() if k != "runs"}
                for m, r in output["methods"].items()
            },
            indent=2,
        )
    )
