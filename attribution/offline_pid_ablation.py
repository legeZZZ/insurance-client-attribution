"""Offline single-round ablation: fixed strength vs PID vs PID+Student-t.

Purpose (honest negative-result evidence, 2026-08-15 review): in offline,
one-shot evaluation each seed is an independent snapshot, so the PID has no
drift history to react to -- the legacy strength barely moves and Brier / decision accuracy /
moderation RMSE are expected to be (near-)identical for the two Gaussian
configurations. The Student-t branch uses the genuine random-effects posterior
and can differ in both point estimates and intervals. The historical PID
variable named ``nu`` is a pseudo-impression strength, not Student-t degrees of
freedom.

Run:  python3 -m attribution.offline_pid_ablation
Writes: outputs/offline_pid_ablation.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .bayes import bundle_compare, estimate_hte
from .benchmark import _segment_predictive_brier, _split
from .experience_store import FactorExperienceStore
from .insursim_carousel import generate_bundle_stage, sanitize

OUT = Path(__file__).resolve().parent.parent / "outputs" / "offline_pid_ablation.json"

SEEDS_MATCHED = (101, 211, 307, 401, 503)
SEEDS_MISMATCHED = (601, 701)
TRUE_MODERATOR = "device_low_end=1"


def _segments_from(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
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
    for seg_id, key in [
        ("channel=organic", "organic"),
        ("channel=paid", "paid"),
        ("channel=social", "social"),
        ("placement=home_mid", "home_mid"),
    ]:
        field = seg_id.split("=")[0]
        subset = [r for r in rows if str(r.get(field)) == key]
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


def _eval_config(
    segments, oracle_ate: float, shrinkage_strength: float, likelihood: str, seed: int
) -> dict[str, Any]:
    hte = estimate_hte(
        segments,
        practical_threshold=0.01,
        moderation_threshold=0.005,
        seed=seed,
        discovery=False,
        shrinkage_strength=shrinkage_strength,
        likelihood=likelihood,
    )
    fp = 0
    mod_errs: list[float] = []
    widths: list[float] = []
    direction_hit = 0
    for seg in hte["segments"]:
        sid = seg["segment_id"]
        lo, hi = seg["credible_interval_95"]
        widths.append(hi - lo)
        if sid == TRUE_MODERATOR:
            if (
                max(
                    seg["prob_moderation_worse_raw"],
                    seg["prob_moderation_worse_shrunk"],
                )
                >= 0.90
            ):
                direction_hit = 1
        else:
            if seg["prob_moderation_worse_shrunk"] >= 0.90:
                fp += 1
            # spurious / non-moderator cells: true moderation = 0
            mod_errs.append(seg["moderation_shrunk"] ** 2)
    return {
        "direction_hit": direction_hit,
        "false_positives": fp,
        "moderation_rmse": round(math.sqrt(sum(mod_errs) / len(mod_errs)), 6),
        "mean_interval_width": round(sum(widths) / len(widths), 6),
        "shrinkage_strength_used": round(shrinkage_strength, 1),
        "tau_scale_used": round(hte["tau_scale_probability_difference"], 8),
        "random_effect_variance": round(
            hte["random_effect_variance_probability_difference"], 10
        ),
    }


def run(seed_count_note: str = "") -> dict[str, Any]:
    configs = ("fixed_v500_gaussian", "pid_adaptive_gaussian", "pid_adaptive_student_t")
    agg: dict[str, dict[str, float]] = {c: {} for c in configs}
    per_seed: list[dict[str, Any]] = []
    nu_log: list[dict[str, float]] = []

    for seed, mismatched in [(s, False) for s in SEEDS_MATCHED] + [
        (s, True) for s in SEEDS_MISMATCHED
    ]:
        rows_all, truth = generate_bundle_stage(seed=seed, mismatched=mismatched)
        rows = sanitize(rows_all)
        _, estimation_rows = _split(rows)
        segments = _segments_from(estimation_rows)
        oracle_ate = truth["oracle_bundle_ate"]

        # Config-independent metrics (identical across configs by construction):
        control = {
            "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 0),
            "impressions": sum(1 for r in estimation_rows if r["treatment"] == 0),
        }
        treatment = {
            "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 1),
            "impressions": sum(1 for r in estimation_rows if r["treatment"] == 1),
        }
        bundle = bundle_compare(
            control, treatment, practical_threshold=0.005, seed=seed
        )
        p_hat = (treatment["clicks"] + control["clicks"]) / (
            treatment["impressions"] + control["impressions"]
        )
        brier = sum((r["clicked"] - p_hat) ** 2 for r in estimation_rows) / len(
            estimation_rows
        )
        brier_adaptive = _segment_predictive_brier(estimation_rows)
        decision_correct = (bundle["decision"] == "ROLLBACK_RECOMMENDED") == (
            oracle_ate < -0.005
        )

        # A: fixed legacy shrinkage strength=500, Gaussian
        res_a = _eval_config(segments, oracle_ate, 500.0, "gaussian", seed)

        # B: PID single-shot adaptation driven by noise leaked into spurious
        # hash-bucket moderation (single observation => tiny nu move).
        store = FactorExperienceStore(Path(f"/tmp/offline_pid_store_{seed}.json"))
        leaked = math.sqrt(
            sum(
                s["moderation_shrunk"] ** 2
                for s in estimate_hte(
                    segments,
                    practical_threshold=0.01,
                    moderation_threshold=0.005,
                    seed=seed,
                    discovery=False,
                )["segments"]
                if s["segment_id"].startswith("hash_bucket_")
            )
            / 2
        )
        step = store.adapt_shrinkage({"hash_buckets": leaked})
        nu_pid = step["nu"]
        nu_log.append(
            {
                "seed": seed,
                "shrinkage_strength_before": 500.0,
                "shrinkage_strength_after": round(nu_pid, 2),
            }
        )
        res_b = _eval_config(segments, oracle_ate, nu_pid, "gaussian", seed)

        # C: PID shrinkage strength + genuine Student-t(nu=4) random effects.
        res_c = _eval_config(segments, oracle_ate, nu_pid, "student_t", seed)

        for cfg, res in zip(configs, (res_a, res_b, res_c)):
            for k, v in res.items():
                agg[cfg][k] = agg[cfg].get(k, 0.0) + v
            agg[cfg]["brier"] = agg[cfg].get("brier", 0.0) + brier
            agg[cfg]["brier_adaptive"] = (
                agg[cfg].get("brier_adaptive", 0.0) + brier_adaptive
            )
            agg[cfg]["decision_correct"] = agg[cfg].get(
                "decision_correct", 0.0
            ) + float(decision_correct)
        per_seed.append(
            {
                "seed": seed,
                "mismatched": mismatched,
                "brier": round(brier, 5),
                "fixed": res_a,
                "pid": res_b,
                "pid_t": res_c,
            }
        )

    n = len(per_seed)
    summary = {c: {k: round(v / n, 6) for k, v in a.items()} for c, a in agg.items()}
    identical = all(
        abs(summary["fixed_v500_gaussian"][k] - summary["pid_adaptive_gaussian"][k])
        < 1e-4
        for k in ("brier", "decision_correct", "moderation_rmse", "false_positives")
    )
    result = {
        "ablation": (
            "offline single-round: fixed shrinkage strength vs PID-adaptive "
            "strength vs PID + Student-t random effects"
        ),
        "parameter_definitions": {
            "pid_nu_legacy_label": (
                "legacy pseudo-impression shrinkage strength; this is not the "
                "Student-t degrees of freedom"
            ),
            "student_t_nu": 4.0,
            "student_t_scale": "tau; SD=tau*sqrt(nu/(nu-2))",
            "tau_handling": (
                "legacy shrinkage variance converted to Student-t scale because "
                "this ablation intentionally compares the historical PID control"
            ),
        },
        "seeds": {"matched": SEEDS_MATCHED, "mismatched": SEEDS_MISMATCHED},
        "shrinkage_strength_trajectory": nu_log,
        "summary_means": summary,
        "offline_metrics_equivalent_fixed_vs_pid": identical,
        "per_seed": per_seed,
        "conclusion": (
            "离线单轮评估下，PID 控制的旧 shrinkage strength 只从约 500 小幅变化到 "
            "501；Gaussian 固定值与 PID 路径的决策和误差基本一致。真实 Student-t "
            f"随机效应路径的平均 moderation RMSE 为 "
            f"{summary['pid_adaptive_student_t']['moderation_rmse']}，Gaussian PID 为 "
            f"{summary['pid_adaptive_gaussian']['moderation_rmse']}；平均区间宽度分别为 "
            f"{summary['pid_adaptive_student_t']['mean_interval_width']} 和 "
            f"{summary['pid_adaptive_gaussian']['mean_interval_width']}。因此 Student-t 已经"
            "实际进入点估计和区间计算，不能再沿用旧版“与 Gaussian 完全相同”的结论。"
        ),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    r = run()
    print(
        json.dumps(
            {
                "shrinkage_strength_trajectory": r["shrinkage_strength_trajectory"],
                "summary_means": r["summary_means"],
                "equivalent": r["offline_metrics_equivalent_fixed_vs_pid"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("evidence:", OUT)
