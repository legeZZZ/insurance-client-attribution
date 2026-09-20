"""Reproducible, bounded calibration probe; not the full T32 acceptance suite."""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.association_discovery import discover_association_factors
from track2_v5.bayes import estimate_high_dimensional_hte


def wilson(hits, n):
    z = 1.96
    p = hits / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [center - width, center + width]


def run(repetitions=100):
    if repetitions < 2:
        raise ValueError("at least two repetitions required")
    coverage = 0
    errors, widths = [], []
    family_false_positives = 0
    for seed in range(repetitions):
        rng = np.random.default_rng(seed)
        n = 600
        x = rng.integers(0, 2, n)
        t = rng.binomial(1, 0.5, n)
        y = rng.binomial(1, 0.2 + 0.1 * t * x)
        rows = [{"t": int(a), "y": int(b), "x": int(c)} for a, b, c in zip(t, y, x)]
        hte = estimate_high_dimensional_hte(
            rows,
            "t",
            "y",
            ["x"],
            [],
            [{"id": "fixed", "condition": {"x": 1}}],
            propensity=0.5,
            ridge_alpha=1e6,
        )
        g = hte["subgroups"][0]
        errors.append(g["estimate"] - 0.1)
        lo, hi = g["interval_95"]
        coverage += lo <= 0.1 <= hi
        widths.append(hi - lo)
        # Correlated null factors, fixed discovery/holdout, no trend or serial dependence.
        null_x, null_y = rng.normal(size=(2, 100))
        factors = [
            {"factor_id": name, "days": list(range(100)), "values": null_x.tolist()}
            for name in ("original", "duplicate")
        ]
        r = discover_association_factors(
            list(range(100)),
            null_y.tolist(),
            [],
            factor_series=factors,
            discovery_days=list(range(60)),
            holdout_days=list(range(65, 100)),
            max_lag=1,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=99,
            seed=seed,
        )
        family_false_positives += any(
            c.get("confirmation_status") == "CONFIRMED_ASSOCIATION"
            for c in r["candidates"]
        )
    return {
        "scope": "preliminary_probe_not_full_T32_acceptance",
        "seeds": [0, repetitions - 1],
        "repetitions": repetitions,
        "hte": {
            "population_effect": 0.1,
            "predefined_subgroup": True,
            "rows": 600,
            "bias": float(np.mean(errors)),
            "rmse": float(np.sqrt(np.mean(np.square(errors)))),
            "coverage": coverage / repetitions,
            "coverage_wilson_95": wilson(coverage, repetitions),
            "mean_width": float(np.mean(widths)),
        },
        "confirmation": {
            "null": "iid_gaussian_with_duplicate_factor",
            "fwer": family_false_positives / repetitions,
            "fwer_wilson_95": wilson(family_false_positives, repetitions),
            "bootstrap_reps": 99,
        },
        "unverified": [
            "serial_dependence",
            "seasonality",
            "heavy_tails",
            "clustered_assignment",
            "adaptive_subgroup_selection",
            "full_causal_pipeline",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(run(args.repetitions), indent=2))
