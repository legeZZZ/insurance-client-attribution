"""Four fresh processes with digest-bound JSON handoffs and measured cost fallback."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .contracts import digest, finite
from .persistence import atomic_json

STAGES = ("L0", "L1", "identification", "L3")


def invoke_worker(jobs, previous_ref, *, timeout=60):
    envelope = {
        "schema_version": "worker/1",
        "jobs": jobs,
        "previous_ref": previous_ref,
    }
    raw = json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("worker input exceeds 16 MiB")
    start = time.monotonic()
    env = {
        k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TMPDIR") if k in os.environ
    }
    env.update(
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMBA_NUM_THREADS="1",
    )
    try:
        process = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("stage_worker.py"))],
            input=raw,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            "isolated stage timed out; no downstream stage executed"
        ) from exc
    if process.returncode:
        raise RuntimeError(
            "isolated worker exited with code " + str(process.returncode)
        )
    if len(process.stdout) > 32 * 1024 * 1024:
        raise ValueError("worker output exceeds 32 MiB")
    response = json.loads(process.stdout)
    if response.get("execution_status") != "COMPLETED":
        raise ValueError("worker failed: " + response.get("error", "unknown"))
    records = response["records"]
    if len(records) != len(jobs):
        raise ValueError("incomplete stage handoff")
    previous = previous_ref
    for record, job in zip(records, jobs):
        expected = {k: v for k, v in record.items() if k != "digest"}
        payload = job["payload"]
        if job["stage"] == "L3" and payload.get("identification") == "$previous":
            payload = {
                **payload,
                "identification": records[records.index(record) - 1]["output"][
                    "identification"
                ],
            }
        if (
            record["stage"] != job["stage"]
            or record["previous_ref"] != previous
            or record["digest"] != digest(expected)
            or record["input_digest"] != digest(payload)
        ):
            raise ValueError("invalid stage order, input binding or handoff digest")
        previous = record["digest"]
    return records, {
        "input_bytes": len(raw),
        "output_bytes": len(process.stdout),
        "elapsed_seconds": time.monotonic() - start,
        "pid": records[0]["pid"],
    }


def run_pipeline(
    request,
    *,
    output_path=None,
    timeout=60,
    baseline_bytes=None,
    execution_mode="isolated",
):
    if not isinstance(request, dict) or set(request) - {
        "route",
        "parameters",
        "association",
        "publication_options",
        "baseline",
    }:
        raise ValueError("invalid pipeline request")
    if execution_mode not in {"isolated", "single_worker"}:
        raise ValueError("execution mode must be isolated or single_worker")
    params = request["parameters"]
    metric = params["metric_contract"]
    if not 0 < finite(timeout, "timeout") <= 60:
        raise ValueError("worker timeout must be in (0,60]")
    binding = digest(request)
    baseline = (
        baseline_bytes
        if baseline_bytes is not None
        else len(json.dumps(request, ensure_ascii=False).encode())
    )
    if finite(baseline, "baseline_bytes") <= 0:
        raise ValueError("positive preregistered single-layer byte baseline required")
    base = {"route": request["route"], "parameters": params}
    jobs = [
        {
            "stage": "L0",
            "payload": {
                "metric_contract": metric,
                "input_digest": binding,
                "baseline": request.get("baseline"),
            },
        },
        {"stage": "L1", "payload": {"association": request.get("association")}},
        {"stage": "identification", "payload": base},
        {
            "stage": "L3",
            "payload": {
                **base,
                "identification": "$previous",
                "publication_options": request.get("publication_options", {}),
            },
        },
    ]
    report = {
        "schema_version": "orchestration/1",
        "execution_mode": execution_mode,
        "input_digest": binding,
        "execution_status": "RUNNING",
        "records": [],
        "cost_ledger": [],
        "baseline_bytes": baseline,
        "cost_unit": "serialized_io_bytes_not_model_tokens",
        "model_tokens": 0,
        "worker_execution": "deterministic_processes_without_model_calls",
        "fallback": False,
    }
    previous, index, spent = binding, 0, 0
    try:
        while index < len(jobs):
            if report["fallback"] or execution_mode == "single_worker":
                selected = jobs[index:]
            else:
                selected = [jobs[index]]
            if selected[0]["stage"] == "L3":
                selected = [
                    {
                        **selected[0],
                        "payload": {
                            **selected[0]["payload"],
                            "identification": report["records"][-1]["output"][
                                "identification"
                            ],
                        },
                    }
                ]
            records, cost = invoke_worker(selected, previous, timeout=timeout)
            report["records"].extend(records)
            report["cost_ledger"].append(
                {"stages": [j["stage"] for j in selected], **cost}
            )
            spent += cost["input_bytes"] + cost["output_bytes"]
            previous = records[-1]["digest"]
            index += len(selected)
            if spent > 4 * baseline and index < len(jobs):
                report["fallback"] = True
                report["fallback_reason"] = (
                    "measured_io_exceeds_4x_single_layer_baseline"
                )
            if output_path:
                atomic_json(output_path, report)
        report["execution_status"] = "COMPLETED"
        report["publication"] = report["records"][-1]["output"]["publication"]
        report["reason_codes"] = report["publication"]["reason_codes"]
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        RuntimeError,
        TimeoutError,
    ) as exc:
        report.update(
            execution_status="FAILED",
            reason_codes=["DATA_INVALID"],
            error_type=type(exc).__name__,
            error=str(exc),
        )
    report["total_io_bytes"] = spent
    report["digest"] = digest(report)
    if output_path:
        atomic_json(output_path, report)
    return report
