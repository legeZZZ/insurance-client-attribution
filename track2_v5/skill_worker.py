"""Isolated method replay; fixed operations, fresh data checks, no arbitrary code."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.contracts import digest, validate_contract

OPERATIONS = {"check_metric", "check_overlap", "estimate_effect", "scan_window"}


def execute(operation, request):
    if operation not in OPERATIONS:
        raise ValueError("skill operation outside capability allowlist")
    if operation == "check_metric":
        metric = validate_contract("MetricContract", request["metric_contract"])
        return {
            "passed": True,
            "claim_type": "DESCRIPTIVE_FACT",
            "metric_digest": metric["digest"],
        }
    if operation == "check_overlap":
        rows = request["rows"]
        group = request["group_column"]
        cells = {}
        for row in rows:
            if row["treatment"] not in (0, 1) or row.get(group) is None:
                raise ValueError("binary treatment and observed grouping required")
            cells.setdefault(str(row[group]), set()).add(row["treatment"])
        passed = bool(cells) and all(values == {0, 1} for values in cells.values())
        return {
            "passed": passed,
            "claim_type": "DESCRIPTIVE_FACT",
            "missing_overlap_groups": sorted(
                k for k, v in cells.items() if v != {0, 1}
            ),
            "next_action": "continue_identification"
            if passed
            else "randomize_within_group",
            "reason_codes": [] if passed else ["NOT_IDENTIFIABLE"],
        }
    if operation == "estimate_effect":
        from track2_v5.publication import publish_conclusion
        from track2_v5.quant_track import estimate_effect

        result = estimate_effect(**request)
        publication = publish_conclusion(result["contracts"])
        return {
            "passed": publication["identification"]["status"] == "IDENTIFIED",
            "publication": publication,
            "claim_type": publication["claim_type"],
            "reason_codes": publication["reason_codes"],
        }
    from track2_v5.watchlist_scan import run_c_line

    result = run_c_line(**request)
    return {"passed": True, "claim_type": "WATCHLIST", "scan": result}


def replay(job):
    if set(job) != {"operation", "request", "binding"}:
        raise ValueError("invalid skill worker envelope")
    binding = job["binding"]
    if not all(binding.get(k) for k in ("task_id", "data_ref", "skill_ref")):
        raise ValueError("task/data/skill binding required")
    try:
        result = execute(job["operation"], job["request"])
        status = "COMPLETED"
    except (ValueError, TypeError, KeyError) as exc:
        result = {
            "passed": False,
            "reason_codes": ["DATA_INVALID"],
            "error": str(exc)[:500],
            "claim_type": "DESCRIPTIVE_FACT",
        }
        status = "REJECTED"
    report = {
        "execution_status": status,
        "binding": binding,
        "operation": job["operation"],
        "input_digest": digest(job["request"]),
        "result": result,
        "pid": os.getpid(),
        "guardrails": {
            "no_code_execution": True,
            "no_traffic_mutation": True,
            "fresh_evidence_only": True,
            "no_causal_without_identification": result.get("claim_type")
            not in {"RANDOMIZED_EFFECT", "OBSERVATIONAL_EFFECT_UNDER_ASSUMPTIONS"}
            or result.get("publication", {}).get("identification", {}).get("status")
            == "IDENTIFIED",
        },
    }
    report["digest"] = digest(report)
    return report


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("skill input limit exceeded")
        with contextlib.redirect_stdout(io.StringIO()):
            report = replay(json.loads(raw))
        sys.stdout.write(json.dumps(report, ensure_ascii=False, allow_nan=False))
    except Exception as exc:  # noqa: BLE001 -- isolated process boundary
        sys.stdout.write(
            json.dumps({"execution_status": "FAILED", "error": type(exc).__name__})
        )
        sys.exit(2)
