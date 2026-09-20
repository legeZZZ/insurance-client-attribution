"""Additional genuine GCM, HTE and sequential-control exercises."""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_observational_tracks import metric as series_metric
from tools.check_stage_b_acceptance import wilson
from track2_v5.action_interface import evaluate_checkpoint, register_sequential_policy
from track2_v5.gcm_track import estimate_gcm_effect
from track2_v5.persistence import atomic_json
from track2_v5.randomized_extensions import estimate_causal_forest


def evaluate(repetitions):
    result = {"gcm": [], "forest_hte": [], "sequential": []}
    metric = {
        "name": "conversion",
        "numerator": "converted",
        "denominator": "users",
        "unit": "rate",
        "aggregation": "ratio_of_sums",
        "analysis_unit": "user",
        "target_population": "users",
        "timezone": "UTC",
        "window": [0, 9],
        "maturity_days": 0,
        "deduplication": "unit_id",
    }
    for i in range(repetitions):
        rng = np.random.default_rng(43000 + i)
        frames = []
        for shift in (0.0, 0.5):
            x = rng.normal(size=200) + shift
            frames.append(
                [
                    {"x": float(a), "revenue": float(2 * a + e)}
                    for a, e in zip(x, rng.normal(scale=0.1, size=200))
                ]
            )
        r = estimate_gcm_effect(
            *frames,
            series_metric(),
            accepted_dag={"nodes": ["x", "revenue"], "edges": [["x", "revenue"]]},
            treatment="x",
            treatment_reference=0.0,
            treatment_alternative=1.0,
            causal_sufficiency_ref="known linear DAG",
            independent_rows_ref="iid DGP",
            mechanism_rmse_limits={"revenue": 0.3},
            observed_through=81,
            bootstrap_samples=30,
            simulation_samples=500,
            seed=43000 + i,
        )
        effect = r["contracts"]["EffectEstimate"]
        result["gcm"].append(
            {
                "seed": 43000 + i,
                "estimate": effect["estimate"],
                "interval": effect["interval"],
                "covered": effect["interval"][0] <= 2 <= effect["interval"][1]
                if effect["interval"]
                else None,
                "status": r["status"],
            }
        )
        rows = []
        for u in range(800):
            x = float(rng.uniform(-1, 1))
            t = u % 2
            rows.append(
                {
                    "unit_id": u,
                    "treatment": t,
                    "x": x,
                    "outcome": int(rng.random() < 0.3 + 0.05 * x + t * (0.1 + 0.2 * x)),
                }
            )
        r = estimate_causal_forest(
            rows,
            metric,
            features=["x"],
            feature_roles={"x": "pre_treatment"},
            query_features=[[-0.8], [0.8]],
            assignment_ref="balanced randomization",
            randomized=True,
            no_interference_ref="independent users",
            observed_through=9,
            n_estimators=100,
            seed=43000 + i,
        )
        d = r["contracts"]["EffectEstimate"]["diagnostics"]
        result["forest_hte"].append(
            {
                "seed": 43000 + i,
                "cate": d["cate"],
                "intervals": d["cate_intervals"],
                "truth": [-0.06, 0.26],
                "covered": [
                    lo <= truth <= hi
                    for (lo, hi), truth in zip(d["cate_intervals"], [-0.06, 0.26])
                ],
            }
        )
    # Cumulative samples at all registered looks, including early stopping.
    policy = register_sequential_policy(
        metric_names=["primary"],
        checkpoints=[1, 2, 3],
        minimum_units=100,
        deadline=3,
        stopping_rules={"primary": "primary", "threshold": 0.0, "guardrail_limits": {}},
    )
    for i in range(1000):
        rng = np.random.default_rng(44000 + i)
        state = None
        totals = {"control": 0, "treatment": 0}
        for look in (1, 2, 3):
            for arm in totals:
                totals[arm] += int(rng.binomial(500, 0.3))
            r = evaluate_checkpoint(
                policy,
                day=look,
                observed_through=look,
                state=state,
                samples={
                    "primary": {
                        arm: {"n": 500 * look, "sum": total}
                        for arm, total in totals.items()
                    }
                },
            )
            state = r["state"]
            if state["terminal"]:
                break
        result["sequential"].append(
            {"seed": 44000 + i, "decision": r["decision"], "looks": state["looks"]}
        )
    errors = sum(r["decision"] == "STOP_SUCCESS" for r in result["sequential"])
    result["summary"] = {
        "gcm_coverage": sum(r["covered"] is True for r in result["gcm"]) / repetitions,
        "gcm_refused": sum(r["status"] == "REFUSED" for r in result["gcm"]),
        "forest_cate_coverage": np.mean(
            [r["covered"] for r in result["forest_hte"]], axis=0
        ).tolist(),
        "forest_order_correct": float(
            np.mean([r["cate"][1] > r["cate"][0] for r in result["forest_hte"]])
        ),
        "sequential_false_stop": errors / 1000,
        "sequential_false_stop_wilson95": wilson(errors, 1000),
    }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repetitions", type=int, default=100)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.repetitions < 1:
        p.error("positive repetitions required")
    out = evaluate(a.repetitions)
    atomic_json(a.output, out)
    print(out["summary"])
