"""Benchmark harness for attribution.

Runs the full pipeline on multiple hidden seeds in matched and mismatched
regimes and reports the Bayesian-specific metrics from plan §11.2:

  factor_recall_at_k, bundle_ate_error, ci95_coverage, brier calibration,
  shrinkage false-positive comparison, decision accuracy, factor recovery.
"""

from __future__ import annotations

import json
import math
from typing import Any

from .bayes import bundle_compare, estimate_hte
from .experiment_designer import design_experiment, estimate_component_effects
from .factor_miner import mine_factors
from .insursim_carousel import (
    TRUE_COMPONENT_EFFECTS,
    generate_bundle_stage,
    generate_factorial_stage,
    sanitize,
)


def _segment_predictive_brier(
    rows, fields=("device_low_end", "channel"), pseudo_n=50.0
):
    """Per-row Brier score using cell-level shrunk rates instead of one pooled rate.

    Predictive p for each row comes from its (fields, arm) cell, shrunk toward
    the arm's pooled rate with fixed pseudo-count strength. Under structural
    mismatch the pooled predictor misfires on drifting subpopulations; the
    cell-level predictor adapts, which is the calibration fix measured here.
    """
    pooled = {
        arm: (
            sum(r["clicked"] for r in rows if r["treatment"] == arm),
            sum(1 for r in rows if r["treatment"] == arm),
        )
        for arm in (0, 1)
    }
    pooled_rate = {a: (c[0] / max(c[1], 1)) for a, c in pooled.items()}
    cells: dict[Any, list] = {}
    for r in rows:
        key = tuple(r.get(f) for f in fields) + (r["treatment"],)
        cells.setdefault(key, [0, 0])
        cells[key][0] += r["clicked"]
        cells[key][1] += 1
    rate = {
        k: (v[0] + pseudo_n * pooled_rate[k[-1]]) / (v[1] + pseudo_n)
        for k, v in cells.items()
    }
    return sum(
        (r["clicked"] - rate[tuple(r.get(f) for f in fields) + (r["treatment"],)]) ** 2
        for r in rows
    ) / len(rows)


def _split(rows, fraction=0.5):
    midpoint = len(rows) // 2
    return rows[:midpoint], rows[midpoint:]


def _run_single_seed(seed: int, mismatched: bool) -> dict[str, Any]:
    rows_all, truth = generate_bundle_stage(seed=seed, mismatched=mismatched)
    rows = sanitize(rows_all)
    discovery_rows, estimation_rows = _split(rows)

    # --- Stage 0/1: FactorMiner on discovery half.
    baseline_rows = [r for r in discovery_rows if r["treatment"] == 0]
    mined = mine_factors(
        rows_baseline=baseline_rows,
        rows_current=discovery_rows,
        treatment_column="treatment",
        outcome_column="clicked",
        context_fields=("device_low_end", "user_new_old", "channel", "placement"),
        runtime_control={"media_load_success_rate": 0.98},
        runtime_treatment={"media_load_success_rate": 0.86},
        practical_threshold=0.005,
        seed=seed,
    )
    found_ids = {c["factor_id"] for c in mined["candidates"][:5]}
    true_factors = {"interaction.device_low_end=1", "carousel.media_load_success_rate"}
    recall_at_5 = len(found_ids & true_factors) / len(true_factors)

    # --- Stage 1: Bundle A/B on estimation half.
    control = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 0),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 0),
    }
    treatment = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 1),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 1),
    }
    bundle = bundle_compare(control, treatment, practical_threshold=0.005, seed=seed)
    ate_error = bundle["effect_absolute"] - truth["oracle_bundle_ate"]
    lo, hi = bundle["credible_interval_95"]
    covered = lo <= truth["oracle_bundle_ate"] <= hi

    # Calibration: predicted click probability vs realized rate (Brier, pooled).
    p_hat = (treatment["clicks"] + control["clicks"]) / (
        treatment["impressions"] + control["impressions"]
    )
    brier = sum((r["clicked"] - p_hat) ** 2 for r in estimation_rows) / len(
        estimation_rows
    )
    # Adaptive calibration: cell-level shrunk predictor (mismatch fix, v6.1).
    brier_adaptive = _segment_predictive_brier(estimation_rows)
    # Theoretical floor: expected Brier of the god model that knows each row's
    # true probability (expert consultation 2026-08-15, 冈). Uses unsanitized
    # rows; sanitized rows preserve order so indices align.
    oracle_rows = rows_all[len(rows_all) // 2 :]
    brier_floor = sum(
        r["_oracle_true_p"] * (1 - r["_oracle_true_p"]) for r in oracle_rows
    ) / len(oracle_rows)

    # Decision accuracy: true effect < -0.005 should trigger rollback.
    true_harmful = truth["oracle_bundle_ate"] < -0.005
    decision_correct = (bundle["decision"] == "ROLLBACK_RECOMMENDED") == true_harmful

    # --- Stage 1.5: HTE with partial pooling vs unshrunk baseline.
    segments = []
    for value in (0, 1):
        subset = [r for r in estimation_rows if r["device_low_end"] == value]
        segments.append(
            {
                "segment_id": f"device_low_end={value}",
                "control": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 0),
                    "impressions": sum(1 for r in subset if r["treatment"] == 0),
                },
                "treatment": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 1),
                    "impressions": sum(1 for r in subset if r["treatment"] == 1),
                },
            }
        )
    # Add tiny spurious segments to test shrinkage discipline.
    rng_segs = [
        ("channel=organic", "organic"),
        ("channel=paid", "paid"),
        ("channel=social", "social"),
        ("placement=home_mid", "home_mid"),
    ]
    for seg_id, key in rng_segs:
        field = seg_id.split("=")[0]
        subset = [r for r in estimation_rows if str(r.get(field)) == key]
        if len(subset) < 60:
            continue
        segments.append(
            {
                "segment_id": seg_id,
                "control": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 0),
                    "impressions": sum(1 for r in subset if r["treatment"] == 0),
                },
                "treatment": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 1),
                    "impressions": sum(1 for r in subset if r["treatment"] == 1),
                },
            }
        )
    # Add small spurious segments (hash buckets) to test shrinkage discipline:
    # these slices carry no true moderation but are noisy enough to fool
    # unshrunk per-segment estimation.
    for bucket in (3, 11):
        subset = [r for r in estimation_rows if r["impression_id"] % 23 == bucket]
        segments.append(
            {
                "segment_id": f"hash_bucket_{bucket}",
                "control": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 0),
                    "impressions": sum(1 for r in subset if r["treatment"] == 0),
                },
                "treatment": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 1),
                    "impressions": sum(1 for r in subset if r["treatment"] == 1),
                },
            }
        )
    hte = estimate_hte(
        segments,
        practical_threshold=0.01,
        moderation_threshold=0.005,
        seed=seed,
        discovery=False,
    )
    true_harm_segments = {"device_low_end=1"}
    shrunk_fp, raw_fp = 0, 0
    hte_direction_hits = 0
    mod_err_raw, mod_err_shrunk = [], []
    for seg in hte["segments"]:
        seg_id = seg["segment_id"]
        raw_flag_p = seg["prob_moderation_worse_raw"]
        shrunk_flag_p = seg["prob_moderation_worse_shrunk"]
        if seg_id in true_harm_segments:
            # Two-tier evidence: 0.90 exploratory-confident, 0.95 confirmatory.
            if max(raw_flag_p, shrunk_flag_p) >= 0.90:
                hte_direction_hits += 1
        else:
            # Spurious segment: true moderation is zero.
            mod_err_raw.append(seg["moderation_raw"] ** 2)
            mod_err_shrunk.append(seg["moderation_shrunk"] ** 2)
            if raw_flag_p >= 0.95:
                raw_fp += 1
            if shrunk_flag_p >= 0.95:
                shrunk_fp += 1
    moderation_rmse_raw = (
        math.sqrt(sum(mod_err_raw) / len(mod_err_raw)) if mod_err_raw else 0.0
    )
    moderation_rmse_shrunk = (
        math.sqrt(sum(mod_err_shrunk) / len(mod_err_shrunk)) if mod_err_shrunk else 0.0
    )

    # --- Stage 2: factorial component experiment.
    factors = list(TRUE_COMPONENT_EFFECTS.keys())
    design = design_experiment(factors, traffic_budget=40_000)
    arm_rows = generate_factorial_stage(seed=seed, arms=design["arms"])
    effects = estimate_component_effects(arm_rows, design["arms"], factors)
    recovered = 0
    total_true = 0
    for item in effects:
        true_effect = TRUE_COMPONENT_EFFECTS[item["factor_id"]]
        is_true_factor = abs(true_effect) > 0.005
        if is_true_factor:
            total_true += 1
            if item["significant"] and (item["component_effect"] < 0) == (
                true_effect < 0
            ):
                recovered += 1
        elif item["significant"]:
            recovered -= 1  # false component claim penalty
    factor_recovery = max(recovered, 0) / max(total_true, 1)

    return {
        "seed": seed,
        "mismatched": mismatched,
        "factor_recall_at_5": recall_at_5,
        "bundle_ate_error": ate_error,
        "ci95_covered": covered,
        "brier": brier,
        "brier_adaptive": brier_adaptive,
        "brier_floor": brier_floor,
        "brier_optimal_share": brier_floor / brier if brier > 0 else None,
        "decision_correct": decision_correct,
        "hte_direction_hit": hte_direction_hits / max(len(true_harm_segments), 1),
        "raw_false_positive_segments": raw_fp,
        "shrunk_false_positive_segments": shrunk_fp,
        "moderation_rmse_raw": moderation_rmse_raw,
        "moderation_rmse_shrunk": moderation_rmse_shrunk,
        "factor_recovery": factor_recovery,
    }


def run_benchmark(
    seeds=(101, 211, 307, 401, 503), mismatched_seeds=(601, 701)
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for seed in seeds:
        results.append(_run_single_seed(seed, mismatched=False))
    for seed in mismatched_seeds:
        results.append(_run_single_seed(seed, mismatched=True))

    def mean(key, subset):
        values = [r[key] for r in subset]
        return round(sum(values) / len(values), 6) if values else None

    matched = [r for r in results if not r["mismatched"]]
    mismatched = [r for r in results if r["mismatched"]]

    def summarize(subset):
        return {
            "seeds": len(subset),
            "factor_recall_at_5": mean("factor_recall_at_5", subset),
            "bundle_ate_rmse": round(
                math.sqrt(
                    mean(
                        "_ate_sq",
                        [{**r, "_ate_sq": r["bundle_ate_error"] ** 2} for r in subset],
                    )
                    or 0.0
                ),
                6,
            ),
            "ci95_coverage": mean("ci95_covered", subset),
            "brier": mean("brier", subset),
            "brier_adaptive": mean("brier_adaptive", subset),
            "brier_floor": mean("brier_floor", subset),
            "brier_optimal_share": mean("brier_optimal_share", subset),
            "decision_accuracy": mean("decision_correct", subset),
            "hte_direction_accuracy": mean("hte_direction_hit", subset),
            "raw_fp_segments_total": sum(
                r["raw_false_positive_segments"] for r in subset
            ),
            "shrunk_fp_segments_total": sum(
                r["shrunk_false_positive_segments"] for r in subset
            ),
            "moderation_rmse_raw": mean("moderation_rmse_raw", subset),
            "moderation_rmse_shrunk": mean("moderation_rmse_shrunk", subset),
            "factor_recovery": mean("factor_recovery", subset),
        }

    return {
        "benchmark_version": "carousel-attribution-v1",
        "matched_regime": summarize(matched),
        "mismatched_regime": summarize(mismatched),
        "per_seed": results,
    }


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), ensure_ascii=False, indent=2))
