"""Frozen end-to-end statistical pressure matrix; retains every seed and refusal."""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_observational_tracks import request as observational_request
from track2_v5.association_discovery import discover_association_factors
from track2_v5.contracts import digest
from track2_v5.evaluation import binomial_interval, mean_interval
from track2_v5.persistence import atomic_json
from track2_v5.stage_worker import execute_stage

ASSOCIATION_CASES = (
    "null",
    "proxy_collinear",
    "trend_season",
    "nonlinear",
    "positive_lag",
    "negative_lag",
    "missing",
    "heavy_tail",
    "serial_null",
)
EFFECT_CASES = (
    "A_null",
    "A_signal",
    "A_heavy",
    "A_cluster",
    "A_CUPED",
    "A_CUPAC",
    "A_overlap_invalid",
    "DiD",
    "DiD_trend_violation",
    "SCM",
    "BSTS",
    "GCM",
    "GCM_ambiguous",
)


def metric(rate=False):
    return {
        "name": "outcome",
        "numerator": "outcome",
        "denominator": "users" if rate else None,
        "aggregation": "ratio_of_sums" if rate else "sum",
        "unit": "rate" if rate else "currency",
        "analysis_unit": "unit",
        "target_population": "eligible",
        "timezone": "UTC",
        "window": [0, 9],
        "maturity_days": 0,
        "deduplication": "unit_id",
    }


def effect_request(case, seed):
    rng = np.random.default_rng(seed)
    if case.startswith("A_"):
        n = 800
        t = rng.binomial(1, 0.5, n)
        x = rng.normal(size=n)
        e = rng.normal(size=n)
        truth = 0.0 if case == "A_null" else 0.4
        if case == "A_heavy":
            e = rng.standard_t(3, size=n)
        if case == "A_cluster":
            t = np.repeat(rng.binomial(1, 0.5, n // 8), 8)
            e = np.repeat(rng.normal(size=n // 8), 8) + e * 0.3
        y = truth * t + 0.8 * x + e
        rows = [
            {
                "unit_id": i,
                "treatment": int(t[i]),
                "outcome": float(y[i]),
                "x": float(x[i]),
                "cluster": i // 8,
            }
            for i in range(n)
        ]
        p = {
            "rows": rows,
            "metric_contract": metric(),
            "assignment_ref": "frozen:randomized",
            "randomized": case != "A_overlap_invalid",
            "observed_through": 9,
            "no_interference_ref": "frozen:independent",
        }
        if case == "A_cluster":
            p["cluster_column"] = "cluster"
        if case in {"A_CUPED", "A_CUPAC"}:
            p.update(
                method=case[2:], features=["x"], feature_roles={"x": "pre_treatment"}
            )
        # sum-scale output reports total over the treated target population.
        return {"route": "A", "parameters": p}, truth, case != "A_overlap_invalid"
    if case.startswith("GCM"):
        frames = []
        for shift in (0.0, 0.5):
            x = rng.normal(size=100) + shift
            y = 2 * x + rng.normal(scale=0.1, size=100)
            frames.append([{"x": float(a), "outcome": float(b)} for a, b in zip(x, y)])
        p = {
            "old_rows": frames[0],
            "new_rows": frames[1],
            "metric_contract": metric(),
            "accepted_dag": {"nodes": ["x", "outcome"], "edges": [["x", "outcome"]]},
            "treatment": "x",
            "treatment_reference": 0.0,
            "treatment_alternative": 1.0,
            "causal_sufficiency_ref": "frozen:DAG" if case == "GCM" else None,
            "independent_rows_ref": "frozen:iid",
            "mechanism_rmse_limits": {"outcome": 0.3},
            "bootstrap_samples": 20,
            "simulation_samples": 200,
            "observed_through": 9,
            "seed": seed,
        }
        if case == "GCM_ambiguous":
            p["accepted_dag"]["edges"].append(["outcome", "x"])
        return {"route": "C", "parameters": p}, 2.0, case == "GCM"
    method = "DiD" if case.startswith("DiD") else case
    req, truth = observational_request(method, seed)
    if case == "DiD_trend_violation":
        for row in req["parameters"]["rows"]:
            if int(row["unit_id"]) < 20:
                row["outcome"] += 0.3 * row["day"]
        req["parameters"]["trend_tolerance"] = 0.01
    return (
        {
            "route": "B_DiD" if method == "DiD" else "B_series",
            "parameters": req["parameters"],
        },
        truth,
        case != "DiD_trend_violation",
    )


def full_pipeline(request):
    # The same four stage implementations as isolated production execution.
    p = request["parameters"]
    route = request["route"]
    cost = []

    def call(stage, payload):
        before = time.monotonic()
        result = execute_stage(stage, payload)
        cost.append(
            {
                "stage": stage,
                "seconds": time.monotonic() - before,
                "input_bytes": len(json.dumps(payload).encode()),
                "output_bytes": len(json.dumps(result).encode()),
                "model_tokens": 0,
            }
        )
        return result

    call(
        "L0",
        {
            "metric_contract": p["metric_contract"],
            "input_digest": digest(request),
            "baseline": request.get("baseline"),
        },
    )
    call("L1", {"association": request.get("association")})
    identification = call("identification", {"route": route, "parameters": p})[
        "identification"
    ]
    result = call(
        "L3",
        {
            "route": route,
            "parameters": p,
            "identification": identification,
            "publication_options": {},
        },
    )
    return result, cost


def association_request(case, seed):
    rng = np.random.default_rng(seed)
    n = 140
    days = np.arange(n)
    x = rng.normal(size=n)
    noise = rng.normal(size=n)
    y = noise.copy()
    positive = set()
    if case in {"positive_lag", "proxy_collinear", "missing", "heavy_tail"}:
        y = np.roll(x, 2) + noise * 0.3
        positive = {"x"}
    if case == "negative_lag":
        y = np.roll(x, -2) + noise * 0.3
        positive = {"x"}
    if case == "nonlinear":
        y = x * x + noise * 0.15
        positive = {"x"}
    if case == "trend_season":
        common = 0.03 * days + np.sin(2 * np.pi * days / 7)
        x = x + common
        y = noise + common
    if case == "heavy_tail":
        y = np.roll(x, 2) + rng.standard_t(3, n) * 0.25
    if case == "serial_null":
        for i in range(1, n):
            x[i] += 0.8 * x[i - 1]
            y[i] += 0.8 * y[i - 1]
    fd = days.tolist()
    fv = x.tolist()
    if case == "missing":
        fd = fd[::2]
        fv = fv[::2]
    factors = [
        {"factor_id": "x", "days": fd, "values": fv},
        {
            "factor_id": "noise",
            "days": days.tolist(),
            "values": rng.normal(size=n).tolist(),
        },
    ]
    if case == "proxy_collinear":
        factors.append(
            {"factor_id": "proxy", "days": days.tolist(), "values": x.tolist()}
        )
        positive.add("proxy")
    return {
        "days": days.tolist(),
        "residual": y.tolist(),
        "anomaly_windows": [],
        "factor_series": factors,
        "discovery_days": days[:85].tolist(),
        "holdout_days": days[95:].tolist(),
        "max_lag": 2,
        "smoothing_window": 1,
        "derived_layers": ["level"],
        "seasonal_period": 7 if case == "trend_season" else None,
        "bootstrap_reps": 199,
        "block_length": 5,
        "seed": seed,
        "statistic_method": "dcor" if case == "nonlinear" else "pearson",
    }, positive


def summarize_effect(runs):
    valid = [r for r in runs if r.get("estimate") is not None]
    errors = [r["estimate"] - r["truth"] for r in valid]
    covered = sum(r["covered"] for r in valid)
    return {
        "total": len(runs),
        "available": len(valid),
        "refused": len(runs) - len(valid),
        "bias": mean_interval(errors),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
        "width": mean_interval([r["interval"][1] - r["interval"][0] for r in valid]),
        "coverage": covered / len(valid) if valid else None,
        "coverage_mc_interval_95": binomial_interval(covered, len(valid)),
        "unconditional_coverage": covered / len(runs),
        "publication_available": sum(
            r.get("published_estimate") is not None for r in runs
        ),
        "published_coverage": sum(
            bool(r.get("published_interval"))
            and r["published_interval"][0] <= r["truth"] <= r["published_interval"][1]
            for r in runs
        )
        / len(runs),
        "false_causal_assertions": sum(r.get("false_causal", False) for r in runs),
        "power": mean_interval(
            [
                float(r["interval"][0] > 0 or r["interval"][1] < 0)
                if r.get("interval")
                else 0.0
                for r in runs
            ],
            bounded=True,
        ),
        "reason_counts": {
            reason: sum(reason in r.get("reasons", []) for r in runs)
            for reason in sorted({x for r in runs for x in r.get("reasons", [])})
        },
    }


def run(output, repetitions=50):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    protocol = {
        "schema": "statistical-evaluation/1",
        "repetitions": repetitions,
        "seeds": [60000 + i for i in range(repetitions)],
        "association_cases": ASSOCIATION_CASES,
        "effect_cases": EFFECT_CASES,
        "alpha": 0.05,
        "fdp_tolerance": 0.05,
        "coverage_tolerance": 0.05,
        "minimum_power": 0.5,
        "negative_results_retained": True,
        "truth_scope": "fully_generated_observations",
        "execution": "same L0/L1/identification/L3 implementations; single process for Monte Carlo; isolated equivalence separately tested",
    }
    protocol_path = output / "protocol.json"
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != json.loads(
        json.dumps(protocol)
    ):
        raise ValueError("protocol already frozen; use new output directory")
    atomic_json(protocol_path, protocol)
    report = {"protocol_digest": digest(protocol), "association": {}, "effects": {}}
    for case in ASSOCIATION_CASES:
        runs = []
        for seed in protocol["seeds"]:
            req, positive = association_request(case, seed)
            start = time.monotonic()
            try:
                result = discover_association_factors(**req)
                selected = {
                    c["factor_id"]
                    for c in result["candidates"]
                    if c.get("confirmation_status") == "CONFIRMED_ASSOCIATION"
                }
                runs.append(
                    {
                        "seed": seed,
                        "selected": sorted(selected),
                        "truth_positive": sorted(positive),
                        "fdp": len(selected - positive) / max(1, len(selected)),
                        "power": len(selected & positive) / len(positive)
                        if positive
                        else None,
                        "seconds": time.monotonic() - start,
                        "request_digest": digest(req),
                        "result_digest": digest(result),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - retain failed runs in frozen evaluation
                runs.append(
                    {
                        "seed": seed,
                        "fdp": 0.0,
                        "power": 0.0 if positive else None,
                        "selected": [],
                        "error": str(exc),
                        "seconds": time.monotonic() - start,
                    }
                )
        summary = {
            "fdp": mean_interval([r["fdp"] for r in runs], bounded=True),
            "fwer_mc_interval_95": binomial_interval(
                sum(r["fdp"] > 0 for r in runs), len(runs)
            ),
            "power": mean_interval(
                [r["power"] for r in runs if r["power"] is not None], bounded=True
            ),
            "discoveries": mean_interval([len(r["selected"]) for r in runs]),
            "errors": sum("error" in r for r in runs),
        }
        summary["calibration_status"] = (
            "PASS"
            if summary["fdp"]["mean"] <= 0.1
            and not summary["errors"]
            and (summary["power"]["mean"] is None or summary["power"]["mean"] >= 0.5)
            else "NOT_CALIBRATED"
        )
        report["association"][case] = {"summary": summary, "runs": runs}
        atomic_json(output / "statistics.json", report)
        print("association", case, summary["calibration_status"], flush=True)
    for case in EFFECT_CASES:
        runs = []
        for seed in protocol["seeds"]:
            request, truth, identifiable = effect_request(case, seed)
            start = time.monotonic()
            try:
                result, cost = full_pipeline(request)
                pub = result["publication"]
                stats = pub["statistical_uncertainty"]
                raw = result["result"]["contracts"]["EffectEstimate"]
                estimate = raw["estimate"]
                interval = raw["interval"]
                runs.append(
                    {
                        "seed": seed,
                        "truth": truth,
                        "estimate": estimate,
                        "interval": interval,
                        "published_estimate": stats["effect"],
                        "published_interval": stats["interval"],
                        "covered": interval[0] <= truth <= interval[1]
                        if interval
                        else None,
                        "false_causal": not identifiable
                        and pub["identification"]["status"] == "IDENTIFIED",
                        "reasons": pub["reason_codes"],
                        "cost": cost,
                        "request_digest": digest(request),
                        "result_digest": digest(result),
                        "seconds": time.monotonic() - start,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - retain failed runs in frozen evaluation
                runs.append(
                    {
                        "seed": seed,
                        "truth": truth,
                        "estimate": None,
                        "interval": None,
                        "error": str(exc),
                        "reasons": ["DATA_INVALID"],
                        "seconds": time.monotonic() - start,
                    }
                )
        summary = summarize_effect(runs)
        summary["calibration_status"] = (
            "PASS"
            if (
                summary["coverage"] is not None
                and summary["coverage"] >= 0.9
                and not summary["false_causal_assertions"]
            )
            or (
                not effect_request(case, protocol["seeds"][0])[2]
                and summary["refused"] == repetitions
            )
            else "NOT_CALIBRATED"
        )
        report["effects"][case] = {"summary": summary, "runs": runs}
        atomic_json(output / "statistics.json", report)
        print("effect", case, summary["calibration_status"], flush=True)
    report["execution_status"] = "COMPLETE"
    report["calibration_failures"] = [
        f"{group}:{case}"
        for group in ("association", "effects")
        for case, row in report[group].items()
        if row["summary"]["calibration_status"] != "PASS"
    ]
    report["claim"] = (
        "finite registered matrix; negative results retained; no universal calibration guarantee"
    )
    atomic_json(output / "statistics.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/stage_e/statistics")
    parser.add_argument("--repetitions", type=int, default=50)
    args = parser.parse_args()
    run(args.output, args.repetitions)
