"""Reproducible Stage B statistical acceptance matrix with all attempts retained."""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.association_discovery import discover_association_factors
from track2_v5.persistence import atomic_json
from track2_v5.quant_track import estimate_randomized_effect
from track2_v5.randomized_extensions import estimate_causal_forest


def wilson(k, n):
    if not n:
        return None
    z = 1.95996398454
    center = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, float(center - half)), min(1.0, float(center + half))]


def associations(repetitions):
    output = {}
    for mode in ("iid_null", "ar_null", "ar_signal"):
        for correction in ("holm", "max_t"):
            runs = []
            for i in range(repetitions):
                seed = 41000 + i
                rng = np.random.default_rng(seed)
                xs = rng.normal(size=(3, 180))
                y = rng.normal(size=180)
                if mode.startswith("ar"):
                    for t in range(1, 180):
                        xs[:, t] += 0.6 * xs[:, t - 1]
                        y[t] += 0.6 * y[t - 1]
                if mode == "ar_signal":
                    y += 1.5 * xs[0]
                start = time.perf_counter()
                r = discover_association_factors(
                    list(range(180)),
                    y.tolist(),
                    [],
                    factor_series=[
                        {
                            "factor_id": str(j),
                            "days": list(range(180)),
                            "values": xs[j].tolist(),
                        }
                        for j in range(3)
                    ],
                    discovery_days=list(range(85)),
                    holdout_days=list(range(100, 180)),
                    max_lag=1,
                    derived_layers=("level", "velocity"),
                    smoothing_window=2,
                    seasonal_period=None,
                    block_length=8,
                    bootstrap_reps=199,
                    seed=seed,
                    min_abs_correlation=0.1,
                    confirmation_max_t_threshold=2 if correction == "max_t" else 100,
                )
                selected = {
                    c["parent_factor_id"]
                    if "parent_factor_id" in c
                    else c["factor_id"].split("::")[0]
                    for c in r["candidates"]
                    if c["holdout"]["survives"]
                }
                # Inspect original factor lineage, rather than count correlated derived views as new causes.
                true = {"0"} if mode == "ar_signal" else set()
                false = selected - true
                runs.append(
                    {
                        "seed": seed,
                        "selected": sorted(selected),
                        "false_discoveries": len(false),
                        "fdp": len(false) / max(len(selected), 1),
                        "detected_signal": bool(selected & true),
                        "seconds": time.perf_counter() - start,
                    }
                )
            errors = sum(r["false_discoveries"] > 0 for r in runs)
            output[f"{mode}/{correction}"] = {
                "fwer": errors / repetitions,
                "fwer_wilson95": wilson(errors, repetitions),
                "mean_fdp": float(np.mean([r["fdp"] for r in runs])),
                "power": float(np.mean([r["detected_signal"] for r in runs]))
                if mode == "ar_signal"
                else None,
                "runs": runs,
                "scope": "conditional-X moving-block empirical calibration, not finite-sample theorem",
            }
    return output


def randomized(repetitions):
    output = {}
    metric = {
        "name": "conversion",
        "numerator": "successes",
        "denominator": "users",
        "unit": "rate",
        "aggregation": "ratio_of_sums",
        "analysis_unit": "user",
        "target_population": "trial users",
        "timezone": "UTC",
        "window": [0, 9],
        "maturity_days": 0,
        "deduplication": "unit",
    }
    design = dict(
        assignment_ref="synthetic randomized",
        randomized=True,
        observed_through=9,
        no_interference_ref="independent groups",
        cluster_column="cluster",
    )
    for effect_size in (0.0, 0.1):
        for method in ("ITT", "CUPED", "CUPAC", "AIPW", "FOREST"):
            runs = []
            for i in range(repetitions):
                rng = np.random.default_rng(42000 + i)
                x = rng.uniform(-1, 1, 200)
                shock = rng.normal(0, 0.03, 200)
                treatment = np.tile([0, 1], 100)
                rng.shuffle(treatment)
                rows = []
                for u in range(800):
                    g = u // 4
                    rows.append(
                        {
                            "unit_id": u,
                            "cluster": g,
                            "treatment": int(treatment[g]),
                            "x": float(x[g]),
                            "outcome": int(
                                rng.random()
                                < 0.3
                                + 0.1 * x[g]
                                + shock[g]
                                + effect_size * treatment[g]
                            ),
                        }
                    )
                kwargs = (
                    dict(features=["x"], feature_roles={"x": "pre_treatment"})
                    if method != "ITT"
                    else {}
                )
                start = time.perf_counter()
                result = (
                    estimate_causal_forest(
                        rows,
                        metric,
                        query_features=[[0.0]],
                        n_estimators=40,
                        **kwargs,
                        **design,
                    )
                    if method == "FOREST"
                    else estimate_randomized_effect(
                        rows, metric, method=method, **kwargs, **design
                    )
                )
                e = result["contracts"]["EffectEstimate"]
                lo, hi = e["interval"] if e["interval"] else (None, None)
                runs.append(
                    {
                        "seed": 42000 + i,
                        "status": result["status"],
                        "estimate": e["estimate"],
                        "interval": e["interval"],
                        "covered": lo <= effect_size <= hi if lo is not None else None,
                        "rejected_zero": not lo <= 0 <= hi if lo is not None else False,
                        "seconds": time.perf_counter() - start,
                    }
                )
            accepted = [r for r in runs if r["estimate"] is not None]
            covered = sum(r["covered"] for r in accepted)
            output[f"{effect_size}/{method}"] = {
                "refused": repetitions - len(accepted),
                "coverage": covered / len(accepted) if accepted else None,
                "coverage_wilson95": wilson(covered, len(accepted)),
                "bias": float(np.mean([r["estimate"] - effect_size for r in accepted]))
                if accepted
                else None,
                "rmse": float(
                    np.sqrt(
                        np.mean([(r["estimate"] - effect_size) ** 2 for r in accepted])
                    )
                )
                if accepted
                else None,
                "type_i_error" if effect_size == 0 else "power": sum(
                    r["rejected_zero"] for r in runs
                )
                / repetitions,
                "average_seconds": float(np.mean([r["seconds"] for r in runs])),
                "runs": runs,
            }
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("positive repetitions required")
    result = {
        "repetitions": args.repetitions,
        "stage": "B",
        "associations": associations(args.repetitions),
    }
    atomic_json(args.output, result)
    result["randomized"] = randomized(args.repetitions)
    atomic_json(args.output, result)
    print("Completed all fixed seeds; raw runs retained:", args.output)
