"""Baseline attribution layer (Line B): A/B baseline + change registry +
external-factor association.

Answers: "premium moved 8% this month — how much is attributable to what WE
did?" Design principles (from the 2026-08 review):

- Baseline = a persistent control group that never receives operational
  changes. No model assumptions needed.
- Attribution = aggregation, not decomposition. Registered changes with
  experiments contribute their ATT (with posterior intervals, partial pooling
  across experiments). Changes without experiments are TEMPORAL_ASSOCIATION.
  Unexplainable residual is labeled "unknown" — never reallocated.
- External factors (regulation, competition, macro, seasonality) are
  registered as exogenous events and identified through the control group's
  own deviations. They never get causal claims.

Run:  python3 -m attribution.baseline_attribution
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

def change_registry_entry(change_id, start_day, scope, experiment_id=None, owner="growth"):
    return {
        "change_id": change_id,
        "start_day": start_day,
        "scope": scope,
        "experiment_id": experiment_id,
        "owner": owner,
        "registered": True,
    }


def external_event_entry(event_id, start_day, end_day, kind, description):
    return {
        "event_id": event_id,
        "start_day": start_day,
        "end_day": end_day,
        "kind": kind,  # regulation | competitor | macro | seasonality
        "description": description,
    }


# ---------------------------------------------------------------------------
# Simulator (ground truth buried; engine only sees aggregates + registries)
# ---------------------------------------------------------------------------

def simulate_panel(seed: int = 20260809, n_days: int = 60) -> dict[str, Any]:
    """Daily premium for a persistent control group and the treated population.

    True effects (per-day, additive on premium):
      chg_ranking  +60 from day 15 (registered, with experiment)
      chg_subsidy  +40 from day 30 (registered, with experiment)
      chg_quiet    -55 from day 40 (UNREGISTERED -> must be detected)
      ext_regulation -70 on days 45-49 for BOTH groups (external event)
      unknown_drift  treated-only linear drift from day 50, -4/day (unobserved)
    """
    rng = np.random.default_rng(seed)
    base = 1000.0
    weekly = np.sin(np.arange(n_days) * 2 * math.pi / 7.0) * 15.0
    noise_c = rng.normal(0, 12, n_days)
    noise_t = rng.normal(0, 12, n_days)

    control = base + weekly + noise_c
    treated = base + weekly + noise_t
    treated[15:] += 60.0
    treated[30:] += 40.0
    treated[40:] -= 55.0
    ext_mask = (np.arange(n_days) >= 45) & (np.arange(n_days) < 50)
    control[ext_mask] -= 70.0
    treated[ext_mask] -= 70.0
    drift_days = np.maximum(np.arange(n_days) - 50, 0)
    treated -= 4.0 * drift_days

    # Experiment readouts for the two registered changes (noisy estimates).
    def experiment_readout(true_att, se):
        est = true_att + float(rng.normal(0, se))
        return {"att_estimate": est, "att_se": se}

    experiments = {
        "exp_ranking": experiment_readout(60.0, 9.0),
        "exp_subsidy": experiment_readout(40.0, 11.0),
    }
    truth = {
        "chg_ranking": 60.0, "chg_subsidy": 40.0, "chg_quiet": -55.0,
        "ext_regulation": -70.0, "unknown_drift_per_day": -4.0,
        "unregistered_onset_day": 40, "external_window": [45, 49],
    }
    return {
        "days": list(range(n_days)),
        "control": control.tolist(),
        "treated": treated.tolist(),
        "experiments": experiments,
        "truth": truth,
    }


# ---------------------------------------------------------------------------
# Attribution engine
# ---------------------------------------------------------------------------

def _shrink_total(experiments: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """Hierarchical (precision-weighted) aggregation of experiment ATTs."""
    if not experiments:
        return {"naive_total": 0.0, "shrunk_total": 0.0, "grand_mean": 0.0,
                "tau2": 0.0, "per_experiment_shrunk": []}
    ests = np.array([e["att_estimate"] for e in experiments.values()])
    ses = np.array([e["att_se"] for e in experiments.values()])
    weights = 1.0 / np.maximum(ses, 1e-9) ** 2
    grand = float(np.sum(ests * weights) / np.sum(weights))
    # Between-experiment variance (DerSimonian-Laird style, floored at 0).
    q = float(np.sum(weights * (ests - grand) ** 2))
    df = max(len(ests) - 1, 1)
    tau2 = max((q - df) / max(np.sum(weights) - np.sum(weights ** 2) / np.sum(weights), 1e-9), 0.0)
    shrunk = (ests / ses ** 2 + grand / max(tau2, 1.0)) / (1.0 / ses ** 2 + 1.0 / max(tau2, 1.0))
    return {
        "naive_total": float(np.sum(ests)),
        "shrunk_total": float(np.sum(shrunk)),
        "grand_mean": grand,
        "tau2": tau2,
        "per_experiment_shrunk": shrunk.tolist(),
    }


def attribute_baseline(
    days: Sequence[int],
    control: Sequence[float],
    treated: Sequence[float],
    change_registry: Sequence[Mapping[str, Any]],
    external_registry: Sequence[Mapping[str, Any]],
    experiments: Mapping[str, Mapping[str, float]],
    detection_threshold: float = 18.0,
    min_run: int = 3,
) -> dict[str, Any]:
    c = np.asarray(control)
    t = np.asarray(treated)
    gap = t - c  # treated vs persistent baseline: no model assumptions

    # 1) Explained by registered changes with experiments.
    agg = _shrink_total(experiments)
    explained = np.zeros(len(days))
    per_change_explained: dict[str, np.ndarray] = {}
    shrunk_map = dict(zip(experiments.keys(), agg["per_experiment_shrunk"]))
    {ch["change_id"]: ch.get("experiment_id") for ch in change_registry}
    for ch in change_registry:
        exp_id = ch.get("experiment_id")
        effect = np.zeros(len(days))
        if exp_id and exp_id in shrunk_map:
            effect[np.asarray(days) >= ch["start_day"]] = shrunk_map[exp_id]
        per_change_explained[ch["change_id"]] = effect
        explained += effect

    residual = gap - explained

    # 2) External factors: identified from the CONTROL group's own deviation.
    #    Fit control trend on non-event days, then measure event-window gaps.
    ext_assoc: list[dict[str, Any]] = []
    external_explained = np.zeros(len(days))
    event_days = set()
    for ev in external_registry:
        event_days.update(range(ev["start_day"], ev["end_day"] + 1))
    fit_mask = np.array([d not in event_days for d in days])
    trend = np.polyfit(np.asarray(days)[fit_mask], c[fit_mask], deg=1)
    control_fit = np.polyval(trend, days)
    for ev in external_registry:
        window = (np.asarray(days) >= ev["start_day"]) & (np.asarray(days) <= ev["end_day"])
        deviation = float(np.mean(c[window] - control_fit[window]))
        assoc = {
            "event_id": ev["event_id"],
            "kind": ev["kind"],
            "window_deviation": round(deviation, 2),
            "claim_type": "TEMPORAL_ASSOCIATION",
            "note": "外生事件不可随机化；仅报告与指标的共同变化，不作因果断言。",
        }
        if abs(deviation) >= detection_threshold:
            assoc["alignment"] = "ALIGNED"
            external_explained[window] += deviation
        else:
            assoc["alignment"] = "NOT_DETECTED"
        ext_assoc.append(assoc)
    residual_after_ext = residual - external_explained

    # 3) Unregistered / miscalibrated change detection: STEP detection on the
    #    smoothed residual. A sustained downward step means either a change
    #    nobody registered, or a registered change whose in-platform effect
    #    deviates from its experiment ATT (explanation deficit). Both are
    #    governance-relevant and share one alert type.
    kernel = np.ones(3) / 3.0
    smoothed = np.convolve(residual_after_ext, kernel, mode="same")
    smoothed[0] = residual_after_ext[0]
    smoothed[-1] = residual_after_ext[-1]
    n = len(days)
    step_threshold = max(detection_threshold * 1.2, 1.0)
    candidates: list[tuple[int, float]] = []
    half = 5
    for i in range(half, n - half):
        if days[i] in event_days:
            continue
        before = float(np.mean(smoothed[i - half:i]))
        after = float(np.mean(smoothed[i:i + half]))
        score = after - before
        if score <= -step_threshold:
            candidates.append((i, score))
    # Merge adjacent candidates, keep the strongest step day.
    alerts: list[dict[str, Any]] = []
    for i, score in candidates:
        if alerts and days[i] - alerts[-1]["onset_day"] <= half:
            if score < alerts[-1]["step_score"]:
                alerts[-1]["onset_day"] = int(days[i])
                alerts[-1]["step_score"] = score
            continue
        alerts.append({
            "alert": "UNEXPLAINED_STEP_SUSPECTED",
            "onset_day": int(days[i]),
            "step_score": round(score, 2),
            "note": "未注册变更，或已注册变动的线上效果与实验 ATT 不一致（解释赤字）。",
        })

    # 4) Unknown bucket: the CURRENT unexplained residual level, measured
    #    over the trailing 10 days. Not modeled, not reallocated.
    tail = max(len(days) - 10, 0)
    unknown_start = int(days[tail])
    late = np.asarray(days) >= unknown_start
    unknown_mean = float(np.mean(residual_after_ext[late]))

    return {
        "baseline_definition": "persistent control group, no model assumptions",
        "att_aggregation": {
            "naive_total": round(agg["naive_total"], 2),
            "hierarchical_total": round(agg["shrunk_total"], 2),
            "tau2": round(agg["tau2"], 4),
        },
        "external_associations": ext_assoc,
        "unregistered_alerts": alerts,
        "unknown_bucket": {
            "window_start_day": int(unknown_start),
            "mean_residual_late_window": round(unknown_mean, 2),
            "claim_type": "UNEXPLAINED",
            "policy": "残差不建模、不摊派、不假装分解。",
        },
        "series": {
            "gap": [round(float(v), 2) for v in gap],
            "explained_registered": [round(float(v), 2) for v in explained],
            "external_explained": [round(float(v), 2) for v in external_explained],
            "residual": [round(float(v), 2) for v in residual_after_ext],
        },
    }


# ---------------------------------------------------------------------------
# Validation harness
# ---------------------------------------------------------------------------

def run_validation(seeds: Sequence[int] = (11, 23, 37, 51, 67)) -> dict[str, Any]:
    per_seed = []
    for seed in seeds:
        panel = simulate_panel(seed=seed)
        truth = panel["truth"]
        registry = [
            change_registry_entry("chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"),
            change_registry_entry("chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"),
        ]
        external = [external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")]
        out = attribute_baseline(
            panel["days"], panel["control"], panel["treated"],
            registry, external, panel["experiments"],
        )

        # (a) unregistered change recall (onset within 5 days of truth)
        onset_true = truth["unregistered_onset_day"]
        detected = any(
            abs(a["onset_day"] - onset_true) <= 5 for a in out["unregistered_alerts"])
        # (b) external association alignment
        ext_ok = out["external_associations"][0]["alignment"] == "ALIGNED" and abs(
            out["external_associations"][0]["window_deviation"] - truth["ext_regulation"]) < 25
        # (c) unknown-label honesty: the system must (i) report a material
        # unexplained remainder instead of claiming full explanation, and
        # (ii) its magnitude must sit within the noise-propagation band of
        # the planted unknowns. Band = 2.4 * combined experiment SE
        # (sqrt(9^2+11^2) ~= 14.2 -> ~34), plus slack for daily noise.
        unknown_truth = float(np.mean([
            (-55.0 if d >= onset_true else 0.0) + truth["unknown_drift_per_day"] * max(d - 50, 0)
            for d in range(50, 60)
        ]))
        unknown_mean = out["unknown_bucket"]["mean_residual_late_window"]
        band = 2.4 * math.sqrt(9.0 ** 2 + 11.0 ** 2) + 5.0
        honesty = abs(unknown_mean) >= 20.0 and abs(unknown_mean - unknown_truth) <= band

        per_seed.append({
            "seed": seed,
            "unregistered_detected": detected,
            "external_aligned": ext_ok,
            "unknown_mean": round(unknown_mean, 2),
            "unknown_truth": round(unknown_truth, 2),
            "unknown_honest": honesty,
        })

    # (d) ATT aggregation ablation: K noisy experiments with comparable true
    # effects (the regime where partial pooling is designed to help).
    true_atts = np.array([35.0, 30.0, 25.0, 40.0, 28.0, 32.0])
    ses = np.array([9.0, 11.0, 14.0, 10.0, 8.0, 12.0])
    naive_errs, shrunk_errs = [], []
    for seed in seeds:
        rng = np.random.default_rng(seed + 9000)
        experiments = {
            f"exp_{i}": {"att_estimate": float(t + rng.normal(0, s)), "att_se": float(s)}
            for i, (t, s) in enumerate(zip(true_atts, ses))
        }
        agg = _shrink_total(experiments)
        naive_est = np.array([e["att_estimate"] for e in experiments.values()])
        naive_errs.extend((naive_est - true_atts) ** 2)
        shrunk_errs.extend((np.array(agg["per_experiment_shrunk"]) - true_atts) ** 2)
    naive_rmse = math.sqrt(sum(naive_errs) / len(naive_errs))
    shrunk_rmse = math.sqrt(sum(shrunk_errs) / len(shrunk_errs))

    def mean(key):
        return round(sum(r[key] for r in per_seed) / len(per_seed), 4)

    return {
        "benchmark_version": "lineB-baseline-1",
        "seeds": len(per_seed),
        "metrics": {
            "unregistered_change_recall": mean("unregistered_detected"),
            "external_alignment_accuracy": mean("external_aligned"),
            "unknown_label_honesty": mean("unknown_honest"),
            "att_per_experiment_rmse_naive": round(naive_rmse, 3),
            "att_per_experiment_rmse_hierarchical": round(shrunk_rmse, 3),
        },
        "per_seed": per_seed,
    }


def main() -> None:
    panel = simulate_panel()
    registry = [
        change_registry_entry("chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"),
        change_registry_entry("chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"),
    ]
    external = [external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")]
    demo = attribute_baseline(
        panel["days"], panel["control"], panel["treated"],
        registry, external, panel["experiments"],
    )
    validation = run_validation()
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "lineB_baseline_attribution.json").write_text(
        json.dumps({"demo": demo, "validation": validation}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({
        "att_aggregation": demo["att_aggregation"],
        "external_associations": demo["external_associations"],
        "unregistered_alerts": demo["unregistered_alerts"],
        "unknown_bucket": demo["unknown_bucket"],
        "validation_metrics": validation["metrics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
