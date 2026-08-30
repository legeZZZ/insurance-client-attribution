"""M1 ablation: nested multi-factor pooling + calibration layer, 50 seeds.

Arms:
  flat       — current estimate_hte (shrink every cell toward pooled)
  nested     — estimate_hte_nested (cell -> factor-group marginal -> pooled)
  calibrated — bundle P(practical harm) adjusted by an expanding
               BinnedCalibrator fed with (predicted, oracle) pairs from
               previous seeds; ECE/Brier measured out-of-sample per seed
               before pairs are added (no look-ahead).

Reproduce: python3 -m attribution.nested_benchmark
Output:    outputs/nested_ablation_50seeds.json
Runtime:   ~2-3 minutes (50 seeds x 100k rows).
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from .bayes import bundle_compare, estimate_hte, estimate_hte_nested
from .calibration import BinnedCalibrator
from .insursim_carousel import generate_bundle_stage, sanitize

# Vary bundle strength so P(harm) spans [0,1] instead of saturating at 1 —
# otherwise the calibration layer has nothing to calibrate.
EFFECTS = (-0.45, -0.30, -0.18, -0.08, -0.02)
SAMPLE = 3_000  # small-sample regime: posterior spread makes calibration measurable
SEEDS = [(1000 + 37 * i, False, EFFECTS[i % len(EFFECTS)]) for i in range(35)] + [
    (5000 + 53 * i, True, EFFECTS[i % len(EFFECTS)]) for i in range(15)
]


def _segments(rows) -> list[dict[str, Any]]:
    """device x channel cells (true moderation lives at device level) +
    two spurious hash buckets."""
    segs: list[dict[str, Any]] = []
    for device in (0, 1):
        for channel in ("organic", "paid", "social"):
            subset = [
                r
                for r in rows
                if r["device_low_end"] == device and r["channel"] == channel
            ]
            segs.append(
                {
                    "segment_id": f"device={device}|channel={channel}",
                    "device": device,
                    "control": {
                        "clicks": sum(
                            r["clicked"] for r in subset if r["treatment"] == 0
                        ),
                        "impressions": sum(1 for r in subset if r["treatment"] == 0),
                    },
                    "treatment": {
                        "clicks": sum(
                            r["clicked"] for r in subset if r["treatment"] == 1
                        ),
                        "impressions": sum(1 for r in subset if r["treatment"] == 1),
                    },
                }
            )
    for bucket in (3, 11):
        subset = [r for r in rows if r["impression_id"] % 23 == bucket]
        segs.append(
            {
                "segment_id": f"hash_bucket_{bucket}",
                "device": None,
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
    return segs


def _score(htelike, flag_key, mod_key, effect_key) -> dict[str, Any]:
    hits = fp = 0
    mod_err = []
    for seg in htelike["segments"]:
        sid = seg["segment_id"]
        p = seg[flag_key]
        if sid.startswith("device=1"):
            if p >= 0.90:
                hits += 1
        else:
            mod_err.append(seg[mod_key] ** 2)
            if p >= 0.95:
                fp += 1
    true_cells = sum(
        1 for s in htelike["segments"] if s["segment_id"].startswith("device=1")
    )
    return {
        "direction_recall": hits / max(true_cells, 1),
        "false_positives": fp,
        "moderation_rmse": math.sqrt(sum(mod_err) / len(mod_err)) if mod_err else 0.0,
    }


def run_nested_ablation() -> dict[str, Any]:
    cal = BinnedCalibrator()
    per_seed: list[dict[str, Any]] = []
    for seed, mismatched, effect in SEEDS:
        rows_all, truth = generate_bundle_stage(
            seed=seed, mismatched=mismatched, bundle_logit_effect=effect
        )
        rows = sanitize(rows_all)
        est = rows[len(rows) // 2 :][:SAMPLE]
        control = {
            "clicks": sum(r["clicked"] for r in est if r["treatment"] == 0),
            "impressions": sum(1 for r in est if r["treatment"] == 0),
        }
        treatment = {
            "clicks": sum(r["clicked"] for r in est if r["treatment"] == 1),
            "impressions": sum(1 for r in est if r["treatment"] == 1),
        }
        bundle = bundle_compare(
            control, treatment, practical_threshold=0.005, seed=seed
        )
        true_harmful = float(truth["oracle_bundle_ate"] < -0.005)
        p_raw = bundle["probability_practical_harm"]

        segments = _segments(est)
        flat = estimate_hte(
            segments,
            practical_threshold=0.01,
            moderation_threshold=0.005,
            seed=seed,
            draws=20_000,
        )
        flat_student_t = estimate_hte(
            segments,
            practical_threshold=0.01,
            moderation_threshold=0.005,
            seed=seed,
            draws=20_000,
            likelihood="student_t",
            nu=5.0,
        )
        nested = estimate_hte_nested(
            segments, group_of=lambda s: s["device"], seed=seed
        )

        # 95% interval coverage from the actual Gaussian and Student-t
        # random-effects posteriors. Truth proxy: full-data (100k) empirical
        # cell effect, whose sampling error is small relative to these intervals.
        full_truth: dict[str, float] = {}
        for s in segments:
            sid = s["segment_id"]
            if sid.startswith("device="):
                d_, ch = int(sid.split("|")[0].split("=")[1]), sid.split("=")[2]
                sub = [
                    r for r in rows if r["device_low_end"] == d_ and r["channel"] == ch
                ]
            else:
                bkt = int(sid.split("_")[-1])
                sub = [r for r in rows if r["impression_id"] % 23 == bkt]
            rc = [r["clicked"] for r in sub if r["treatment"] == 0]
            rt = [r["clicked"] for r in sub if r["treatment"] == 1]
            full_truth[sid] = sum(rt) / len(rt) - sum(rc) / len(rc)
        cov_g = cov_t = 0
        student_by_id = {
            segment["segment_id"]: segment for segment in flat_student_t["segments"]
        }
        for seg in flat["segments"]:
            lo_g, hi_g = seg["credible_interval_95"]
            lo_t, hi_t = student_by_id[seg["segment_id"]]["credible_interval_95"]
            tv = full_truth[seg["segment_id"]]
            cov_g += lo_g <= tv <= hi_g
            cov_t += lo_t <= tv <= hi_t
        n_seg = len(flat["segments"])

        # Calibration target: per-segment moderation tail probabilities.
        # Out-of-sample: score with the map learned from previous seeds,
        # then add this seed's pairs.
        seg_pairs_raw, seg_pairs_cal = [], []
        for seg in nested["segments"]:
            y = 1.0 if seg["segment_id"].startswith("device=1") else 0.0
            p = seg["prob_moderation_worse_nested"]
            seg_pairs_raw.append((p, y))
            seg_pairs_cal.append((cal.calibrate(p), y))
        for p, y in seg_pairs_raw:
            cal.add(p, y)

        rec = {
            "seed": seed,
            "mismatched": mismatched,
            "p_harm_raw": p_raw,
            "true_harmful": true_harmful,
            "decision_correct": (bundle["decision"] == "ROLLBACK_RECOMMENDED")
            == bool(true_harmful),
            "flat": _score(
                flat,
                "prob_moderation_worse_shrunk",
                "moderation_shrunk",
                "effect_shrunk",
            ),
            "nested": _score(
                nested,
                "prob_moderation_worse_nested",
                "moderation_nested",
                "effect_nested",
            ),
            "student_t": _score(
                flat_student_t,
                "prob_moderation_worse_shrunk",
                "moderation_shrunk",
                "effect_shrunk",
            ),
            "student_t_tau": flat_student_t["tau_scale_probability_difference"],
            "coverage_gaussian_95": cov_g / n_seg,
            "coverage_student_t_95": cov_t / n_seg,
            "seg_pairs_raw": seg_pairs_raw,
            "seg_pairs_calibrated": seg_pairs_cal,
        }
        per_seed.append(rec)

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 6) if xs else None

    def agg(key, arm):
        return {
            "direction_recall": mean([r[arm]["direction_recall"] for r in per_seed]),
            "false_positives_total": sum(r[arm]["false_positives"] for r in per_seed),
            "moderation_rmse": mean([r[arm]["moderation_rmse"] for r in per_seed]),
        }

    raw_pairs = [xy for r in per_seed for xy in r["seg_pairs_raw"]]
    cal_pairs = [xy for r in per_seed for xy in r["seg_pairs_calibrated"]]
    out = {
        "ablation": "nested_pooling_and_calibration_50seeds",
        "seeds": len(SEEDS),
        "regimes": {"matched": 35, "mismatched": 15},
        "sample_per_seed": SAMPLE,
        "decision_accuracy_small_sample": mean(
            [r["decision_correct"] for r in per_seed]
        ),
        "flat_pooling": agg(None, "flat"),
        "nested_pooling": agg(None, "nested"),
        "student_t_pooling": {
            **agg(None, "student_t"),
            "nu": 5.0,
            "mean_tau_scale": mean([r["student_t_tau"] for r in per_seed]),
        },
        "hte_interval_coverage": {
            "gaussian_95": mean([r["coverage_gaussian_95"] for r in per_seed]),
            "student_t_95": mean([r["coverage_student_t_95"] for r in per_seed]),
            "note": (
                "coverage vs full-data (100k) empirical cell effects; both "
                "intervals come from their actual random-effects posteriors, "
                "with Student-t nu=5"
            ),
        },
        "calibration": {
            "target": "per-segment prob_moderation_worse (true moderation on device=1 cells)",
            "ece_raw": round(BinnedCalibrator.ece(raw_pairs), 5),
            "ece_calibrated": round(BinnedCalibrator.ece(cal_pairs), 5),
            "brier_raw": round(mean([(p - y) ** 2 for p, y in raw_pairs]), 6),
            "brier_calibrated": round(mean([(p - y) ** 2 for p, y in cal_pairs]), 6),
            "calibrator": cal.summary(),
            "note": "calibrated probabilities are out-of-sample (map learned "
            "only from previous seeds' segments)",
        },
        "per_seed": [
            {k: v for k, v in r.items() if not k.startswith("seg_pairs")}
            for r in per_seed
        ],
    }
    return out


def main() -> None:
    t0 = time.time()
    result = run_nested_ablation()
    result["runtime_seconds"] = round(time.time() - t0, 1)
    out = (
        Path(__file__).resolve().parent.parent
        / "outputs"
        / "nested_ablation_50seeds.json"
    )
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "per_seed"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
