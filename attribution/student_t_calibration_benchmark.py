"""Multi-truth-family calibration benchmark for Student-t HTE posteriors.

This benchmark is intentionally separate from the product simulator. It tests
the hierarchical interval implementation against Gaussian, heavy-tailed,
zero-heterogeneity and sparse-outlier random-effects truth families.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from .bayes import estimate_hte

OUT = (
    Path(__file__).resolve().parent.parent
    / "outputs"
    / "student_t_calibration_benchmark.json"
)
TRUTH_FAMILIES = ("gaussian", "student_t", "zero_heterogeneity", "mixture_outliers")


def _truth_effects(
    family: str, segment_count: int, rng: np.random.Generator
) -> np.ndarray:
    location = -0.008
    if family == "gaussian":
        effects = location + rng.normal(0.0, 0.008, segment_count)
    elif family == "student_t":
        effects = location + rng.standard_t(4.0, segment_count) * 0.0057
    elif family == "zero_heterogeneity":
        effects = np.full(segment_count, location)
    elif family == "mixture_outliers":
        effects = location + rng.normal(0.0, 0.004, segment_count)
        outlier_count = max(1, segment_count // 6)
        indexes = rng.choice(segment_count, outlier_count, replace=False)
        effects[indexes] += rng.choice((-0.028, 0.028), outlier_count)
    else:
        raise ValueError(f"unknown truth family: {family}")
    return np.clip(effects, -0.08, 0.08)


def _simulate_segments(
    family: str, seed: int, segment_count: int
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rng = np.random.default_rng(seed)
    effects = _truth_effects(family, segment_count, rng)
    segments: list[dict[str, Any]] = []
    truth: dict[str, float] = {}
    for index, effect in enumerate(effects):
        control_probability = float(np.clip(0.055 + rng.normal(0.0, 0.008), 0.02, 0.12))
        treatment_probability = float(
            np.clip(control_probability + effect, 0.002, 0.20)
        )
        actual_effect = treatment_probability - control_probability
        control_n = int(rng.integers(350, 1_601))
        treatment_n = int(rng.integers(350, 1_601))
        segment_id = f"segment-{index:02d}"
        segments.append(
            {
                "segment_id": segment_id,
                "control": {
                    "clicks": int(rng.binomial(control_n, control_probability)),
                    "impressions": control_n,
                },
                "treatment": {
                    "clicks": int(rng.binomial(treatment_n, treatment_probability)),
                    "impressions": treatment_n,
                },
            }
        )
        truth[segment_id] = actual_effect
    return segments, truth


def _score(
    result: dict[str, Any], truth: dict[str, float], practical_threshold: float
) -> dict[str, float]:
    covered = 0
    squared_errors: list[float] = []
    widths: list[float] = []
    false_harm = 0
    harm_predictions = 0
    decision_correct = 0
    for segment in result["segments"]:
        actual = truth[segment["segment_id"]]
        lower, upper = segment["credible_interval_95"]
        predicted_harm = segment["shrunk_probability_practical_harm"] >= 0.95
        true_harm = actual < -practical_threshold
        covered += lower <= actual <= upper
        squared_errors.append((segment["effect_shrunk"] - actual) ** 2)
        widths.append(upper - lower)
        harm_predictions += predicted_harm
        false_harm += predicted_harm and not true_harm
        decision_correct += predicted_harm == true_harm
    count = len(result["segments"])
    return {
        "coverage": covered / count,
        "rmse": math.sqrt(sum(squared_errors) / count),
        "mean_interval_width": sum(widths) / count,
        "false_harm_rate": false_harm / count,
        "false_discovery_share": false_harm / max(harm_predictions, 1),
        "decision_accuracy": decision_correct / count,
    }


def run_calibration_benchmark(
    seeds_per_family: int = 50,
    segment_count: int = 12,
    draws: int = 4_000,
    seed_base: int = 20260830,
) -> dict[str, Any]:
    if seeds_per_family < 1 or segment_count < 3 or draws < 1_000:
        raise ValueError(
            "seeds_per_family>=1, segment_count>=3 and draws>=1000 are required"
        )
    started = time.time()
    model_names = ("gaussian", "student_t_plugin", "student_t_joint")
    per_family: dict[str, dict[str, list[dict[str, float]]]] = {
        family: {model: [] for model in model_names} for family in TRUTH_FAMILIES
    }
    hyperparameter_audit: list[dict[str, Any]] = []
    practical_threshold = 0.005

    for family_index, family in enumerate(TRUTH_FAMILIES):
        for seed_index in range(seeds_per_family):
            seed = seed_base + family_index * 100_000 + seed_index * 101
            segments, truth = _simulate_segments(family, seed, segment_count)
            common = {
                "practical_threshold": practical_threshold,
                "moderation_threshold": practical_threshold,
                "draws": draws,
                "seed": seed,
            }
            gaussian = estimate_hte(segments, **common)
            plugin = estimate_hte(
                segments,
                **common,
                likelihood="student_t",
                nu=5.0,
                student_t_hyperparameter_method="plug_in",
            )
            joint = estimate_hte(
                segments,
                **common,
                likelihood="student_t",
                nu=5.0,
                student_t_hyperparameter_method="grid_mixture",
            )
            for model, result in zip(model_names, (gaussian, plugin, joint)):
                per_family[family][model].append(
                    _score(result, truth, practical_threshold)
                )
            hyper = joint["student_t_hyperparameter_posterior"]
            hyperparameter_audit.append(
                {
                    "family": family,
                    "seed": seed,
                    "probability_tau_zero": hyper["probability_tau_zero"],
                    "tau_posterior_mean": hyper["tau_posterior_mean"],
                    "nu_posterior_mean": hyper["nu_posterior_mean"],
                    "retained_component_count": hyper["retained_component_count"],
                }
            )

    metric_names = (
        "coverage",
        "rmse",
        "mean_interval_width",
        "false_harm_rate",
        "false_discovery_share",
        "decision_accuracy",
    )

    def aggregate(records: list[dict[str, float]]) -> dict[str, float]:
        return {
            metric: round(sum(record[metric] for record in records) / len(records), 6)
            for metric in metric_names
        }

    family_summary = {
        family: {model: aggregate(per_family[family][model]) for model in model_names}
        for family in TRUTH_FAMILIES
    }
    overall = {
        model: aggregate(
            [
                record
                for family in TRUTH_FAMILIES
                for record in per_family[family][model]
            ]
        )
        for model in model_names
    }
    joint = overall["student_t_joint"]
    gaussian = overall["gaussian"]
    coverage_by_family = [
        family_summary[family]["student_t_joint"]["coverage"]
        for family in TRUTH_FAMILIES
    ]
    gates = {
        "overall_coverage_0_93_to_0_97": 0.93 <= joint["coverage"] <= 0.97,
        "each_family_coverage_at_least_0_90": min(coverage_by_family) >= 0.90,
        "decision_accuracy_noninferior_2pp": joint["decision_accuracy"]
        >= gaussian["decision_accuracy"] - 0.02,
        "false_harm_rate_noninferior_2pp": joint["false_harm_rate"]
        <= gaussian["false_harm_rate"] + 0.02,
        "interval_width_ratio_at_most_1_75": joint["mean_interval_width"]
        <= gaussian["mean_interval_width"] * 1.75,
    }
    calibration_gate_passed = all(gates.values())
    return {
        "benchmark": "student_t_multi_truth_calibration_v1",
        "truth_families": list(TRUTH_FAMILIES),
        "seeds_per_family": seeds_per_family,
        "evaluated_datasets": seeds_per_family * len(TRUTH_FAMILIES),
        "segment_count": segment_count,
        "draws": draws,
        "models": {
            "gaussian": "production baseline",
            "student_t_plugin": "historical empirical-Bayes plug-in tau",
            "student_t_joint": "joint grid mixture over mu/tau/nu",
        },
        "family_summary": family_summary,
        "overall": overall,
        "release_gates": gates,
        "calibration_gate_passed": calibration_gate_passed,
        "production_eligible": False,
        "deployment_policy": (
            "calibration gates passed; production still requires the separate "
            "repository replay utility gates"
            if calibration_gate_passed
            else "experimental_only; Gaussian remains production default"
        ),
        "hyperparameter_audit": hyperparameter_audit,
        "runtime_seconds": round(time.time() - started, 3),
    }


def main() -> None:
    result = run_calibration_benchmark()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "overall": result["overall"],
                "release_gates": result["release_gates"],
                "calibration_gate_passed": result["calibration_gate_passed"],
                "production_eligible": result["production_eligible"],
                "runtime_seconds": result["runtime_seconds"],
                "output": str(OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
