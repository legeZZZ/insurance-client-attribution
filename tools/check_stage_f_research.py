"""Prespecified model-X/TSKI and bounded synthesis research experiments."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.contracts import digest
from track2_v5.evaluation import binomial_interval, mean_interval
from track2_v5.factor_synthesis import FactorSynthesis
from track2_v5.knockoff_research import run_knockoff_research
from track2_v5.persistence import atomic_json


def synthetic(seed, start=0, null=False):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=100)
    z = rng.normal(size=100)
    noise = rng.normal(size=100) * 0.1
    return {
        "days": list(range(start, start + 100)),
        "response": (noise if null else x * z + noise).tolist(),
        "available_day": start + 99,
        "factors": {
            "x": {"values": x.tolist(), "unit": "index"},
            "z": {"values": z.tolist(), "unit": "index"},
            "u": {"values": rng.normal(size=100).tolist(), "unit": "index"},
            "v": {"values": rng.normal(size=100).tolist(), "unit": "index"},
        },
    }


def run(output, repetitions=50):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    protocol = {
        "seeds": list(range(93000, 93000 + repetitions)),
        "n": 600,
        "p": 40,
        "alpha": 0.1,
        "cases": [
            "iid_signal",
            "iid_null",
            "iid_sparse",
            "ar_unthinned",
            "ar_thinned",
            "wrong_covariance",
        ],
        "synthesis_cases": ["interaction", "null"],
        "source": "https://arxiv.org/html/2112.09851v3",
        "algorithm_seed_offset": 1000000,
        "synthesis_null": "independent u/v; planted x*z",
        "statistic": "symmetric ridge coefficient difference; no Lasso power theorem",
        "guarantee": "research only; no automatic production selection",
    }
    path = out / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError("research protocol frozen; choose new output directory")
    atomic_json(path, protocol)
    report = {"protocol_digest": digest(protocol), "knockoffs": {}, "synthesis": {}}
    for case in protocol["cases"]:
        runs = []
        for seed in protocol["seeds"]:
            rng = np.random.default_rng(seed)
            p = protocol["p"]
            n = protocol["n"]
            rho = 0.7 if case.startswith("ar_") else 0.0
            cov = 0.3 ** np.abs(np.arange(p)[:, None] - np.arange(p)[None, :])
            if case == "wrong_covariance":
                cov = 0.9 ** np.abs(np.arange(p)[:, None] - np.arange(p)[None, :])
            x = rng.multivariate_normal(np.zeros(p), cov, size=n)
            for i in range(1, n):
                x[i] = rho * x[i - 1] + np.sqrt(1 - rho * rho) * x[i]
            beta = np.zeros(p)
            active = 0 if case == "iid_null" else 3 if case == "iid_sparse" else 12
            beta[:active] = 0.8
            y = x @ beta + rng.normal(size=n) * 0.5
            result = run_knockoff_research(
                x=x.tolist(),
                y=y.tolist(),
                feature_ids=[f"x{i}" for i in range(p)],
                covariance=(np.eye(p) if case == "wrong_covariance" else cov).tolist(),
                distribution_known=case != "wrong_covariance",
                distribution_ref="fixture:registered-Gaussian-DGP",
                temporal_rho=rho,
                subsample_gap=3 if case == "ar_thinned" else 0,
                alpha=0.1,
                threshold_level=0.1,
                seed=seed + 1000000,
            )
            selected = set(result["research_selected"])
            truth = {f"x{i}" for i in range(active)}
            runs.append(
                {
                    "seed": seed,
                    "selected": sorted(selected),
                    "truth": sorted(truth),
                    "fdp": len(selected - truth) / max(1, len(selected)),
                    "power": len(selected & truth) / active if active else None,
                    "qualification": result["qualification"],
                    "eligible_under_declared_model": result[
                        "eligible_under_declared_iid_gaussian_model"
                    ],
                    "full_temporal_swap_error": result["full_temporal_swap_error"],
                    "flip_sign_max_error": result["flip_sign_max_error"],
                    "covariance_discrepancy": result["marginal_covariance_discrepancy"],
                    "report_digest": result["digest"],
                }
            )
            if seed == protocol["seeds"][0]:
                atomic_json(out / (case + "-example.json"), result)
        summary = {
            "mean_fdp": mean_interval([r["fdp"] for r in runs], bounded=True),
            "power": mean_interval(
                [r["power"] for r in runs if r["power"] is not None], bounded=True
            ),
            "discoveries": mean_interval([len(r["selected"]) for r in runs]),
            "any_error_interval": binomial_interval(
                sum(r["fdp"] > 0 for r in runs), len(runs)
            ),
            "max_flip_error": max(r["flip_sign_max_error"] for r in runs),
            "declared_model_eligible_count": sum(
                r["eligible_under_declared_model"] for r in runs
            ),
        }
        summary["assessment"] = (
            "LOW_POWER"
            if active and summary["power"]["mean"] < 0.5
            else "EMPIRICAL_RESULT_ONLY"
        )
        if case in {"ar_unthinned", "ar_thinned", "wrong_covariance"}:
            summary["assessment"] = "FORMAL_USE_REJECTED"
        report["knockoffs"][case] = {"summary": summary, "runs": runs}
        atomic_json(out / "research.json", report)
        print(case, summary["assessment"], flush=True)
    for case in protocol["synthesis_cases"]:
        runs = []
        for seed in protocol["seeds"]:
            service = FactorSynthesis(out / f"synthesis-{case}-{seed}.db")
            try:
                service.configure(policy_id="p", enabled=True, max_candidates=3)
                ref = service.registry.add_asset(
                    "data", synthetic(seed, null=case == "null")
                )
                ids = []
                for expr in (
                    {"op": "multiply", "args": [{"factor": "x"}, {"factor": "z"}]},
                    {"op": "add", "args": [{"factor": "u"}, {"factor": "v"}]},
                    {"op": "subtract", "args": [{"factor": "u"}, {"factor": "v"}]},
                ):
                    ids.append(
                        service.propose(
                            policy_id="p",
                            task_id="t",
                            data_ref=ref,
                            expression=expr,
                            current_window=99,
                        )["factor_id"]
                    )
                service.freeze(task_id="t")
                new = service.registry.add_asset(
                    "data", synthetic(seed + 5000, start=110, null=case == "null")
                )
                result = service.confirm(task_id="t", data_ref=new)
                selected = {
                    r["alert_id"]
                    for r in result["confirmation"]["results"]
                    if r["confirmed"]
                }
                truth = {ids[0]} if case == "interaction" else set()
                runs.append(
                    {
                        "seed": seed,
                        "family_size": len(result["confirmation"]["results"]),
                        "tests_spent": result["tests_spent"],
                        "selected": sorted(selected),
                        "fdp": len(selected - truth) / max(1, len(selected)),
                        "power": len(selected & truth) if truth else None,
                        "alpha": result["confirmation"]["alpha"],
                        "result_ref": result["result_ref"],
                    }
                )
            finally:
                service.close()
        report["synthesis"][case] = {
            "runs": runs,
            "summary": {
                "fdp": mean_interval([r["fdp"] for r in runs], bounded=True),
                "power": mean_interval(
                    [r["power"] for r in runs if r["power"] is not None], bounded=True
                ),
                "any_error_interval": binomial_interval(
                    sum(r["fdp"] > 0 for r in runs), len(runs)
                ),
            },
        }
        atomic_json(out / "research.json", report)
        print("synthesis", case, flush=True)
    report["status"] = "COMPLETE"
    atomic_json(out / "research.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="outputs/stage_f/research")
    p.add_argument("--repetitions", type=int, default=50)
    a = p.parse_args()
    run(a.output, a.repetitions)
