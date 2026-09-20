"""Synthetic A/B experiments using UCI Bank Marketing data for validation."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .track2_bayesian import compare_groups, prior_sensitivity
from .track2_factor_mining import build_factor_report


def synthesize_ab_from_uci(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcome_column: str = "y",
    treatment_effect: float = 0.03,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create a synthetic randomized experiment from UCI Bank Marketing data.

    The original data has no randomized treatment, so we:
    1. Randomly assign treatment/control
    2. Apply a known treatment effect to the outcome
    3. Return rows with treatment assignment and modified outcome

    This lets us validate our Bayesian estimators against a known ground truth.
    """
    rng = random.Random(seed)
    modified_rows: list[dict[str, Any]] = []
    truth = {
        "true_effect": treatment_effect,
        "assignment": "randomized",
        "source": "uci_synthetic",
    }

    for row in rows:
        new_row = dict(row)
        # Random assignment
        treatment = 1 if rng.random() < 0.5 else 0
        new_row[treatment_column] = treatment
        new_row["assignment"] = "randomized"

        # Original outcome (yes/no -> 1/0)
        original_outcome = (
            1 if str(new_row.get(outcome_column, "")).strip().lower() == "yes" else 0
        )

        # Apply treatment effect
        if treatment == 1:
            # Lift probability by treatment_effect (capped at 1)
            p_outcome = min(1.0, original_outcome + treatment_effect)
            new_outcome = 1 if rng.random() < p_outcome else 0
        else:
            new_outcome = original_outcome

        new_row["_original_" + outcome_column] = original_outcome
        new_row[outcome_column] = "yes" if new_outcome else "no"
        new_row["_synthetic_outcome"] = new_outcome

        modified_rows.append(new_row)

    return modified_rows, truth


def evaluate_synthetic_experiment(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcome_column: str = "_synthetic_outcome",
    true_effect: float | None = None,
) -> dict[str, Any]:
    """Evaluate a synthetic experiment using both frequentist and Bayesian methods."""
    # Convert to binary outcome if needed
    clean_rows = []
    for row in rows:
        new_row = dict(row)
        if isinstance(new_row.get(outcome_column), str):
            new_row[outcome_column] = (
                1 if new_row[outcome_column].strip().lower() == "yes" else 0
            )
        clean_rows.append(new_row)

    # Aggregate
    control = [r for r in clean_rows if r.get(treatment_column) == 0]
    treatment = [r for r in clean_rows if r.get(treatment_column) == 1]

    ctrl_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in control)
    ctrl_impressions = len(control)
    treat_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in treatment)
    treat_impressions = len(treatment)

    # Frequentist estimate
    ctrl_rate = ctrl_clicks / max(1, ctrl_impressions)
    treat_rate = treat_clicks / max(1, treat_impressions)
    freq_effect = treat_rate - ctrl_rate
    freq_se = math.sqrt(
        ctrl_rate * (1 - ctrl_rate) / max(1, ctrl_impressions)
        + treat_rate * (1 - treat_rate) / max(1, treat_impressions)
    )
    freq_ci = [freq_effect - 1.96 * freq_se, freq_effect + 1.96 * freq_se]

    # Bayesian estimate
    bayes_result = compare_groups(
        {"clicks": ctrl_clicks, "impressions": ctrl_impressions},
        {"clicks": treat_clicks, "impressions": treat_impressions},
        prior=(1.0, 1.0),
        threshold=0.01,
        draws=200_000,
        seed=42,
    )

    # Prior sensitivity
    sensitivity = prior_sensitivity(
        {"clicks": ctrl_clicks, "impressions": ctrl_impressions},
        {"clicks": treat_clicks, "impressions": treat_impressions},
        threshold=0.01,
        seed=42,
    )

    # Factor mining on the synthetic data
    factor_report = build_factor_report(
        clean_rows,
        treatment_column=treatment_column,
        outcome_column=outcome_column,
        segment_columns=["job", "marital", "education", "contact", "month", "poutcome"],
        min_subgroup_size=50,
        top_k=10,
    )

    # Calibration check
    calibration = {}
    if true_effect is not None:
        bayes_effect = bayes_result["effect_absolute"]
        bayes_ci = bayes_result["credible_interval_95"]
        calibration = {
            "true_effect": true_effect,
            "bayes_estimate": bayes_effect,
            "freq_estimate": round(freq_effect, 6),
            "bayes_bias": round(bayes_effect - true_effect, 6),
            "freq_bias": round(freq_effect - true_effect, 6),
            "bayes_rmse": round((bayes_effect - true_effect) ** 2, 6),
            "freq_rmse": round((freq_effect - true_effect) ** 2, 6),
            "ci_covers_truth": bayes_ci[0] <= true_effect <= bayes_ci[1],
            "freq_ci_covers_truth": freq_ci[0] <= true_effect <= freq_ci[1],
        }

    return {
        "experiment_type": "synthetic_uci_ab",
        "sample_size": len(clean_rows),
        "control_size": len(control),
        "treatment_size": len(treatment),
        "control_rate": round(ctrl_rate, 6),
        "treatment_rate": round(treat_rate, 6),
        "frequentist": {
            "effect": round(freq_effect, 6),
            "se": round(freq_se, 6),
            "ci95": [round(freq_ci[0], 6), round(freq_ci[1], 6)],
        },
        "bayesian": bayes_result,
        "prior_sensitivity": sensitivity,
        "calibration": calibration,
        "factor_report": factor_report,
    }


def run_uci_synthetic_benchmark(
    csv_path: Path,
    seeds: Sequence[int] = (101, 211, 307),
    treatment_effects: Sequence[float] = (0.0, 0.02, 0.05),
    max_rows: int | None = 5000,
) -> dict[str, Any]:
    """Run a benchmark suite on synthetic UCI A/B experiments."""

    if not csv_path.is_file():
        raise FileNotFoundError(f"UCI CSV not found: {csv_path}")

    # Read CSV
    import csv

    all_rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for i, row in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            all_rows.append(dict(row))

    results = []
    for seed in seeds:
        for effect in treatment_effects:
            synth_rows, _truth = synthesize_ab_from_uci(
                all_rows, treatment_effect=effect, seed=seed
            )
            eval_result = evaluate_synthetic_experiment(
                synth_rows,
                true_effect=effect,
            )
            eval_result["seed"] = seed
            eval_result["true_effect"] = effect
            results.append(eval_result)

    # Aggregate calibration metrics
    calibrations = [r["calibration"] for r in results if r.get("calibration")]
    if calibrations:
        avg_bias_bayes = sum(c["bayes_bias"] for c in calibrations) / len(calibrations)
        avg_bias_freq = sum(c["freq_bias"] for c in calibrations) / len(calibrations)
        avg_rmse_bayes = math.sqrt(
            sum(c["bayes_rmse"] for c in calibrations) / len(calibrations)
        )
        avg_rmse_freq = math.sqrt(
            sum(c["freq_rmse"] for c in calibrations) / len(calibrations)
        )
        ci_coverage = sum(1 for c in calibrations if c["ci_covers_truth"]) / len(
            calibrations
        )
    else:
        avg_bias_bayes = avg_bias_freq = avg_rmse_bayes = avg_rmse_freq = (
            ci_coverage
        ) = None

    return {
        "benchmark_type": "uci_synthetic_ab",
        "n_seeds": len(seeds),
        "n_effects": len(treatment_effects),
        "total_experiments": len(results),
        "avg_bias_bayes": round(avg_bias_bayes, 6)
        if avg_bias_bayes is not None
        else None,
        "avg_bias_freq": round(avg_bias_freq, 6) if avg_bias_freq is not None else None,
        "avg_rmse_bayes": round(avg_rmse_bayes, 6)
        if avg_rmse_bayes is not None
        else None,
        "avg_rmse_freq": round(avg_rmse_freq, 6) if avg_rmse_freq is not None else None,
        "bayes_ci_coverage": round(ci_coverage, 6) if ci_coverage is not None else None,
        "results": results,
    }
