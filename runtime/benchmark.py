"""Process-isolated hidden-seed benchmark for attribution causal governance."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .analysis import sanitize_rows
from .cases import case_experiment_metadata, default_metric_contract, generate_dataset

SCENARIOS: tuple[tuple[str, str, str], ...] = (
    ("observational_confounded", "A", "DESCRIPTIVE_ONLY"),
    ("missing_experiment_evidence", "B", "DATA_INSUFFICIENT"),
    ("randomized_experiment", "C", "CAUSAL_READY"),
)


def _opaque_id(family: str, seed: int) -> str:
    return (
        "hb-"
        + hashlib.sha256(
            (family + ":" + str(seed) + ":attribution-v1").encode("utf-8")
        ).hexdigest()[:16]
    )


def _build_hidden_cases(
    seeds: Iterable[int], n: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    public_datasets: list[dict[str, Any]] = []
    oracle: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        for family, source_case, expected_outcome in SCENARIOS:
            rows, truth = generate_dataset(source_case, seed=seed, n=n)
            benchmark_id = _opaque_id(family, seed)
            public_datasets.append(
                {
                    "benchmark_id": benchmark_id,
                    "rows": sanitize_rows(rows),
                    "metric_contract": default_metric_contract(),
                    "experiment_metadata": case_experiment_metadata(source_case),
                }
            )
            oracle[benchmark_id] = {
                "family": family,
                "expected_outcome": expected_outcome,
                "oracle_ate": truth["oracle_ate"],
            }
    return public_datasets, oracle


def _run_isolated_worker(
    public_datasets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    environment = dict(os.environ)
    completed = subprocess.run(
        [sys.executable, "-m", "runtime.worker"],
        input=json.dumps({"datasets": list(public_datasets)}, ensure_ascii=False),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "isolated attribution worker failed: " + completed.stderr.strip()
        )
    payload = json.loads(completed.stdout)
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(public_datasets):
        raise RuntimeError("isolated attribution worker returned an invalid result set")
    return results


def _effect_metrics(
    outputs: Sequence[Mapping[str, Any]],
    oracle: Mapping[str, Mapping[str, Any]],
    outcome: str,
) -> dict[str, Any]:
    errors: list[float] = []
    covered = 0
    for output in outputs:
        hidden = oracle[str(output["benchmark_id"])]
        if hidden["expected_outcome"] != "CAUSAL_READY":
            continue
        estimate = float(output["estimate"][outcome]["estimate"])
        truth = float(hidden["oracle_ate"][outcome])
        lower, upper = output["estimate"][outcome]["ci95"]
        errors.append(estimate - truth)
        if float(lower) <= truth <= float(upper):
            covered += 1
    count = len(errors)
    return {
        "evaluated": count,
        "bias": round(sum(errors) / count, 6) if count else None,
        "rmse": round(math.sqrt(sum(error**2 for error in errors) / count), 6)
        if count
        else None,
        "ci95_coverage": round(covered / count, 6) if count else None,
    }


def run_hidden_benchmark(
    seeds: Sequence[int] = (101, 211, 307, 401, 503, 601, 701, 809), n: int = 1200
) -> dict[str, Any]:
    """Generate after code freeze, evaluate in a subprocess, and score with parent-only truth."""
    public_datasets, oracle = _build_hidden_cases(seeds, n)
    outputs = _run_isolated_worker(public_datasets)
    predictions: list[tuple[str, str, str]] = []
    false_causal = 0
    noncausal_count = 0
    refusals_expected = 0
    refusals_correct = 0
    failures: list[dict[str, str]] = []
    for output in outputs:
        benchmark_id = str(output["benchmark_id"])
        hidden = oracle[benchmark_id]
        expected = str(hidden["expected_outcome"])
        predicted = str(output["causal_readiness"]["outcome"])
        claim_type = str(output["claim"]["claim_type"])
        predictions.append((expected, predicted, claim_type))
        if expected != "CAUSAL_READY":
            noncausal_count += 1
            if claim_type == "causal_effect":
                false_causal += 1
        if expected == "DATA_INSUFFICIENT":
            refusals_expected += 1
            if predicted == "DATA_INSUFFICIENT":
                refusals_correct += 1
        if expected != predicted:
            failures.append(
                {
                    "benchmark_id": benchmark_id,
                    "expected": expected,
                    "predicted": predicted,
                }
            )
    correct = sum(1 for expected, predicted, _ in predictions if expected == predicted)
    expected_counts = Counter(expected for expected, _, _ in predictions)
    return {
        "benchmark_version": "causal-governance-benchmark-v1",
        "worker_isolation": "subprocess; public rows and metadata only",
        "hidden_inputs": [
            "scenario_family",
            "seed",
            "potential_outcomes",
            "oracle_ate",
            "expected_outcome",
        ],
        "seeds": len(seeds),
        "scenario_families": len(SCENARIOS),
        "evaluated_cases": len(predictions),
        "expected_distribution": dict(sorted(expected_counts.items())),
        "metrics": {
            "causal_gate_accuracy": round(correct / len(predictions), 6)
            if predictions
            else 0.0,
            "false_causal_assertion_rate": round(false_causal / noncausal_count, 6)
            if noncausal_count
            else 0.0,
            "refusal_recall": round(refusals_correct / refusals_expected, 6)
            if refusals_expected
            else 0.0,
            "issued_effect": _effect_metrics(outputs, oracle, "issued"),
            "net_premium_effect": _effect_metrics(outputs, oracle, "net_premium"),
        },
        "failed_cases": failures,
    }
