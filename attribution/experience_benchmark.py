"""Experience-store ablation: cross-period learning vs static baseline.

Runs the 7 benchmark seeds as 7 consecutive attribution periods. The
adaptive arm loads priors and shrinkage strength from a persistent
FactorExperienceStore (posterior write-back + PID-adapted nu); the static
arm re-runs every period cold (uniform prior, nu=500) exactly like the
current benchmark.

Reproduce: python3 -m attribution.experience_benchmark
Output:     outputs/experience_ablation.json
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any

from .bayes import bundle_compare, estimate_hte
from .experience_store import FactorExperienceStore
from .insursim_carousel import generate_bundle_stage, sanitize

SEEDS = [
    (101, False),
    (211, False),
    (307, False),
    (401, False),
    (503, False),
    (601, True),
    (701, True),
]
# Realistic ramp-up: early periods are traffic-sparse (cold start), later
# periods are data-rich. This is where an experience store should pay off.
TRAFFIC = [0.05, 0.10, 0.20, 0.50, 1.00, 1.00, 1.00]
PRIOR_PSEUDO_N = 1000.0  # fixed prior strength: dominates sparse periods,
# negligible (~2%) once fresh data is rich


def _segments_of(rows) -> list[dict[str, Any]]:
    segments = []
    for value in (0, 1):
        subset = [r for r in rows if r["device_low_end"] == value]
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
    for bucket in (3, 11):
        subset = [r for r in rows if r["impression_id"] % 23 == bucket]
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
    return segments


def _run_period(
    seed: int,
    mismatched: bool,
    traffic: float,
    store: FactorExperienceStore | None,
    out: dict[str, Any],
) -> dict[str, Any]:
    rows_all, truth = generate_bundle_stage(seed=seed, mismatched=mismatched)
    rows = sanitize(rows_all)
    estimation_rows = rows[len(rows) // 2 :]
    keep = max(int(len(estimation_rows) * traffic), 200)
    estimation_rows = estimation_rows[:keep]

    control = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 0),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 0),
    }
    treatment = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 1),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 1),
    }

    prior: Any = (1.0, 1.0)
    nu = 500.0
    mismatch_alarm = False
    prior_deviation = None
    if store is not None:
        pc = store.prior("bundle.control", max_total=PRIOR_PSEUDO_N)
        pt = store.prior("bundle.treatment", max_total=PRIOR_PSEUDO_N)
        devs = [
            d
            for d in (
                store.arm_deviation(
                    "bundle.control",
                    control["clicks"] / max(control["impressions"], 1),
                    max_total=PRIOR_PSEUDO_N,
                ),
                store.arm_deviation(
                    "bundle.treatment",
                    treatment["clicks"] / max(treatment["impressions"], 1),
                    max_total=PRIOR_PSEUDO_N,
                ),
            )
            if d is not None
        ]
        if devs:
            prior_deviation = sum(devs) / len(devs)
            mismatch_alarm = FactorExperienceStore.mismatch_alarm(prior_deviation)
        if pc and pt:
            prior = (pc, pt)
        nu = store.data["shrinkage_strength"]

    bundle = bundle_compare(
        control, treatment, prior=prior, practical_threshold=0.005, seed=seed
    )
    ate_error = bundle["effect_absolute"] - truth["oracle_bundle_ate"]

    segments = _segments_of(estimation_rows)
    hte = estimate_hte(
        segments,
        practical_threshold=0.01,
        moderation_threshold=0.005,
        seed=seed,
        discovery=False,
        shrinkage_strength=nu,
    )

    spurious = [s for s in hte["segments"] if s["segment_id"].startswith("hash_bucket")]
    mod_rmse = math.sqrt(
        sum(s["moderation_shrunk"] ** 2 for s in spurious) / len(spurious)
    )

    record = {
        "period_seed": seed,
        "mismatched": mismatched,
        "traffic": traffic,
        "ate_error": ate_error,
        "moderation_rmse_spurious": mod_rmse,
        "decision": bundle["decision"],
        "shrinkage_strength": nu,
        "prior_deviation": prior_deviation,
        "mismatch_alarm": mismatch_alarm,
        "prior_pseudo_impressions": (
            sum(prior[0]) + sum(prior[1])
            if isinstance(prior[0], (tuple, list))
            else 2.0
        ),
    }

    if store is not None:
        shapes = bundle["arm_shapes"]
        store.write_back("bundle.control", tuple(shapes["control"]))
        store.write_back("bundle.treatment", tuple(shapes["treatment"]))
        errors = {}
        for s in hte["segments"]:
            predicted = store.predict_segment(s["segment_id"])
            if predicted is not None:
                errors[s["segment_id"]] = s["effect_raw"] - predicted
        pid = store.adapt_shrinkage(errors)
        record["pid"] = {
            "shrinkage_strength": pid["nu"],
            **{key: value for key, value in pid.items() if key != "nu"},
        }
        store.update_predictions(
            {s["segment_id"]: s["effect_shrunk"] for s in hte["segments"]}
        )
        store.end_period()
    return record


def run_experience_ablation(store_path=None) -> dict[str, Any]:
    if store_path is None:
        store_path = (
            Path(tempfile.gettempdir()) / "attribution_experience_store_ablation.json"
        )
        Path(store_path).unlink(missing_ok=True)
    store = FactorExperienceStore(store_path)

    adaptive, static = [], []
    for (seed, mismatched), traffic in zip(SEEDS, TRAFFIC):
        adaptive.append(_run_period(seed, mismatched, traffic, store, {}))
    for (seed, mismatched), traffic in zip(SEEDS, TRAFFIC):
        static.append(_run_period(seed, mismatched, traffic, None, {}))
    store.save()

    def rmse(records, key):
        vals = [r[key] ** 2 for r in records]
        return round(math.sqrt(sum(vals) / len(vals)), 6) if vals else None

    sparse = lambda rs: [r for r in rs if r["traffic"] < 1.0]  # cold-start periods
    rich = lambda rs: [r for r in rs if r["traffic"] >= 1.0]  # data-rich periods

    return {
        "ablation": "experience_store_cross_period",
        "periods": len(SEEDS),
        "traffic_ramp": TRAFFIC,
        "note": "sparse periods (traffic<1) test cold-start; rich periods test no-harm",
        "parameter_definition": (
            "shrinkage_strength is the historical pseudo-impression control; "
            "the experience-store field formerly labeled nu is not Student-t nu"
        ),
        "static_baseline": {
            "ate_rmse_sparse": rmse(sparse(static), "ate_error"),
            "ate_rmse_rich": rmse(rich(static), "ate_error"),
            "moderation_rmse_spurious": rmse(static, "moderation_rmse_spurious"),
            "decisions": [r["decision"] for r in static],
        },
        "adaptive_experience_store": {
            "ate_rmse_sparse": rmse(sparse(adaptive), "ate_error"),
            "ate_rmse_rich": rmse(rich(adaptive), "ate_error"),
            "moderation_rmse_spurious": rmse(adaptive, "moderation_rmse_spurious"),
            "decisions": [r["decision"] for r in adaptive],
            "mismatch_alarm": {
                "fired_periods": [
                    r["period_seed"] for r in adaptive if r["mismatch_alarm"]
                ],
                "true_mismatch_seeds": [s for s, m in SEEDS if m],
                "deviation_by_period": [
                    {
                        "seed": r["period_seed"],
                        "mismatched": r["mismatched"],
                        "deviation": (
                            round(r["prior_deviation"], 5)
                            if r["prior_deviation"] is not None
                            else None
                        ),
                    }
                    for r in adaptive
                ],
                "note": "alarm semantics: fires at mismatch onset; the decayed "
                "store then adapts, so later mismatched periods may not fire",
            },
            "shrinkage_strength_trajectory": [
                round(r["shrinkage_strength"], 1) for r in adaptive
            ],
            "prior_pseudo_impressions": [
                round(r["prior_pseudo_impressions"], 1) for r in adaptive
            ],
        },
        "per_period_adaptive": adaptive,
        "store_final": store.summary(),
    }


def main() -> None:
    result = run_experience_ablation()
    out = (
        Path(__file__).resolve().parent.parent / "outputs" / "experience_ablation.json"
    )
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
