"""One-shot JSON worker. Only four fixed stage capabilities are exposed."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

# -I ignores caller PYTHONPATH and user site packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.contracts import digest, validate_contract

STAGES = ("L0", "L1", "identification", "L3")


def execute_stage(stage, payload):
    if stage == "L0":
        if set(payload) != {"metric_contract", "input_digest", "baseline"}:
            raise ValueError("L0 accepts only metric and input reference")
        metric = validate_contract("MetricContract", payload["metric_contract"])
        baseline = None
        if payload["baseline"] is not None:
            from track2_v5.baseline_attribution import attribute_baseline

            parameters = dict(payload["baseline"])
            if (
                parameters.get("metric_contract") is not None
                and validate_contract("MetricContract", parameters["metric_contract"])
                != metric
            ):
                raise ValueError("L0 metric differs from registered analysis metric")
            parameters["metric_contract"] = metric
            baseline = attribute_baseline(**parameters)
        return {
            "baseline": baseline,
            "claim_type": "DESCRIPTIVE_FACT",
            "metric_contract": metric,
            "input_digest": payload["input_digest"],
        }
    if stage == "L1":
        if set(payload) != {"association"}:
            raise ValueError("L1 accepts only the association data slice")
        if payload["association"] is None:
            return {
                "status": "SKIPPED",
                "reason": "preregistered_design_direct_path",
                "causal_eligible": False,
            }
        from track2_v5.association_discovery import discover_association_factors
        from track2_v5.publication import publish_association

        result = discover_association_factors(**payload["association"])
        return {
            "status": "COMPLETED",
            "result": result,
            "claims": publish_association(result),
            "causal_eligible": False,
        }
    if stage not in {"identification", "L3"} or set(payload) != (
        {"route", "parameters"}
        if stage == "identification"
        else {"route", "parameters", "identification", "publication_options"}
    ):
        raise ValueError("worker capability or payload is outside stage allowlist")
    from track2_v5.quant_track import estimate_effect

    result = estimate_effect(route=payload["route"], parameters=payload["parameters"])
    identification = result["contracts"]["IdentificationReport"]
    if stage == "identification":
        # Reuse route-specific observed diagnostics; discard numerical estimates.
        # L3 independently recomputes and binds to this exact report.
        return {"identification": identification}
    if identification != validate_contract(
        "IdentificationReport", payload["identification"]
    ):
        raise ValueError("identification handoff does not match L3 observations")
    from track2_v5.publication import publish_conclusion

    return {
        "result": result,
        "publication": publish_conclusion(
            result["contracts"], **payload["publication_options"]
        ),
    }


def handle(request):
    if (
        set(request) != {"schema_version", "jobs", "previous_ref"}
        or request["schema_version"] != "worker/1"
    ):
        raise ValueError("invalid worker envelope")
    jobs = request["jobs"]
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 4:
        raise ValueError("bounded stage jobs required")
    previous, records = request["previous_ref"], []
    for job in jobs:
        if set(job) != {"stage", "payload"} or job["stage"] not in STAGES:
            raise ValueError("invalid job capability")
        payload = job["payload"]
        if job["stage"] == "L3" and payload.get("identification") == "$previous":
            payload = {
                **payload,
                "identification": records[-1]["output"]["identification"],
            }
        output = execute_stage(job["stage"], payload)
        record = {
            "stage": job["stage"],
            "previous_ref": previous,
            "input_digest": digest(payload),
            "output": output,
            "pid": os.getpid(),
        }
        record["digest"] = digest(record)
        previous = record["digest"]
        records.append(record)
    return {"execution_status": "COMPLETED", "records": records}


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("worker input too large")
        with contextlib.redirect_stdout(io.StringIO()):
            result = handle(json.loads(raw))
    except Exception as exc:  # noqa: BLE001 -- process boundary returns a structured failure
        result = {
            "execution_status": "FAILED",
            "reason_codes": ["DATA_INVALID"],
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
