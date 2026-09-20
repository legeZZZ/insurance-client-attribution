"""Fixed-seed clustered RCT probe for ITT, CUPAC and AIPW; not full T32."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.quant_track import estimate_randomized_effect


def probe(repetitions=100):
    records = {method: [] for method in ("ITT", "CUPAC", "AIPW")}
    contract = {
        "name": "conversion",
        "numerator": "converted",
        "denominator": "users",
        "aggregation": "ratio_of_sums",
        "unit": "rate",
        "analysis_unit": "user",
        "target_population": "eligible_users",
        "timezone": "UTC",
        "window": [0, 9],
        "maturity_days": 2,
        "deduplication": "unit_id",
    }
    for seed in range(repetitions):
        rng = np.random.default_rng(seed)
        assignment = rng.permutation([0] * 50 + [1] * 50)
        cluster_shock = rng.choice([-1, 1], size=100) * 0.08
        x = rng.uniform(-1, 1, 400)
        groups = np.arange(400) // 4
        t = assignment[groups]
        outcome = rng.binomial(1, 0.25 + 0.1 * t + 0.1 * x + cluster_shock[groups])
        rows = [
            {
                "unit_id": i,
                "cluster": int(g),
                "treatment": int(a),
                "outcome": int(y),
                "x": float(v),
            }
            for i, (g, a, y, v) in enumerate(zip(groups, t, outcome, x))
        ]
        for method in records:
            result = estimate_randomized_effect(
                rows,
                contract,
                assignment_ref=f"simulation:{seed}",
                randomized=True,
                observed_through=11,
                no_interference_ref="simulation:independent_clusters",
                method=method,
                features=[] if method == "ITT" else ["x"],
                feature_roles={"x": "pre_treatment"},
                cluster_column="cluster",
            )
            effect = result["contracts"]["EffectEstimate"]
            if result["status"] != "ESTIMATED":
                raise RuntimeError("unexpected refusal in balanced RCT probe")
            low, high = effect["interval"]
            records[method].append(
                {
                    "seed": seed,
                    "error": effect["estimate"] - 0.1,
                    "covered": low <= 0.1 <= high,
                    "width": high - low,
                }
            )
    summaries = {}
    for method, cases in records.items():
        errors = np.array([c["error"] for c in cases])
        covered = sum(c["covered"] for c in cases)
        p = covered / repetitions
        z = 1.96
        n = repetitions
        center = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        summaries[method] = {
            "bias": float(errors.mean()),
            "rmse": float(np.sqrt(np.mean(errors**2))),
            "coverage": p,
            "coverage_wilson_95": [float(center - half), float(center + half)],
            "mean_interval_width": float(np.mean([c["width"] for c in cases])),
        }
    return {
        "scope": "balanced_cluster_randomized_binary_outcome_probe",
        "seeds": [0, repetitions - 1],
        "clusters": 100,
        "units_per_cluster": 4,
        "true_ATE": 0.1,
        "summaries": summaries,
        "limitations": [
            "not_causal_forest_challenger",
            "not_ratio_of_session_counts",
            "not_adaptive_subgroup_selection",
            "not_full_T32",
        ],
        "runs": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    if args.repetitions < 2:
        parser.error("at least two repetitions required")
    print(json.dumps(probe(args.repetitions), indent=2))
