"""Actual phase-D CLI lifecycle and reproducible effect-form pressure evidence."""

from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_stage_d import metric_request, scan_request
from track2_v5.contracts import digest
from track2_v5.persistence import atomic_json
from track2_v5.watchlist_scan import run_c_line


def main():
    base = ROOT / "outputs/stage_d/completion"
    run = base / ("run-" + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    db = str(run / "governance.db")
    cases = []
    number = 0

    def execute(label, operation, parameters, expected=0):
        nonlocal number
        number += 1
        name = f"{number:02d}_{label}"
        source = run / (name + ".request.json")
        target = run / (name + ".result.json")
        atomic_json(source, {"operation": operation, "parameters": parameters})
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/run_causal_pipeline.py"),
                str(source),
                "--output",
                str(target),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        cases.append(
            {
                "case": name,
                "operation": operation,
                "expected": expected,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != expected:
            raise AssertionError(cases[-1])
        return json.loads(target.read_text()) if target.exists() else None

    def api(label, operation, action, parameters, expected=0):
        return execute(
            label,
            operation,
            {"db_path": db, "action": action, "parameters": parameters},
            expected,
        )

    def data(label, body):
        return api(
            label, "investigation", "revise_resource", {"name": label, "body": body}
        )["ref"]

    request = metric_request(0)
    source = data("source_metric", request)
    context = {"metric_kind": "ratio_of_sums"}
    trace = api(
        "capture_success",
        "skills",
        "capture",
        {
            "task_id": "source",
            "data_ref": source,
            "context": context,
            "operation": "check_metric",
            "author": "fixture-author",
        },
    )
    candidate = api(
        "propose_delta",
        "skills",
        "propose",
        {
            "name": "metric_skill",
            "trace_ids": [trace["trace_id"]],
            "applicability": context,
        },
    )
    api(
        "reject_self_review",
        "skills",
        "review",
        {"name": "metric_skill", "version": 1, "reviewer": "fixture-author"},
        2,
    )
    review = api(
        "independent_review",
        "skills",
        "review",
        {"name": "metric_skill", "version": 1, "reviewer": "fixture-reviewer"},
    )
    assert review["passed"] and review["checks"][0]["pid"] != os.getpid()

    def suite(offset, name, workflow_context, operation):
        records = []
        for i in (offset, offset + 1):
            body = (
                metric_request(i)
                if operation == "check_metric"
                else scan_request(seed=i, start=i * 100)
            )
            ref = data(f"{name}_data_{i}", body)
            records.append(
                {
                    "task_id": f"{name}-{i}",
                    "data_ref": ref,
                    "context": workflow_context,
                    "request": body,
                    "expected_operation": operation,
                    "critical": True,
                }
            )
        return api(name + "_freeze", "skills", "freeze_suite", {"cases": records})[
            "suite_ref"
        ]

    frozen = suite(10, "metric_suite", context, "check_metric")
    valid = api(
        "paired_validation",
        "skills",
        "validate",
        {"name": "metric_skill", "version": 1, "suite_ref": frozen},
    )
    assert valid["passed"]
    api(
        "reject_missing_receipt",
        "skills",
        "publish",
        {"name": "metric_skill", "version": 1, "approval_ref": "forged"},
        2,
    )
    receipt = api(
        "fixture_human_approval",
        "skills",
        "approve",
        {
            "name": "metric_skill",
            "version": 1,
            "approver": "fixture-human",
            "credential_ref": "fixture:explicit-approval",
            "suite_ref": frozen,
        },
    )["approval_ref"]
    api(
        "reject_direct_full_release",
        "skills",
        "publish",
        {"name": "metric_skill", "version": 1, "approval_ref": receipt, "fraction": 1},
        2,
    )
    api(
        "canary_release",
        "skills",
        "publish",
        {
            "name": "metric_skill",
            "version": 1,
            "approval_ref": receipt,
            "effective_window": 2,
        },
    )
    monitor_suite = suite(20, "metric_canary", context, "check_metric")
    monitored = api(
        "independent_canary",
        "skills",
        "monitor",
        {"name": "metric_skill", "version": 1, "suite_ref": monitor_suite},
    )
    assert monitored["passed"]
    receipt = api(
        "fixture_expand_approval",
        "skills",
        "approve",
        {
            "name": "metric_skill",
            "version": 1,
            "approver": "fixture-human",
            "credential_ref": "fixture:expand-approval",
            "suite_ref": monitor_suite,
        },
    )["approval_ref"]
    api(
        "staged_expansion",
        "skills",
        "publish",
        {
            "name": "metric_skill",
            "version": 1,
            "approval_ref": receipt,
            "fraction": 1,
            "effective_window": 3,
        },
    )
    current = data("current_metric", metric_request(30))
    replay = api(
        "fresh_bound_replay",
        "skills",
        "replay",
        {
            "name": "metric_skill",
            "context": context,
            "task_id": "current",
            "data_ref": current,
            "window": 3,
        },
    )
    assert replay["report"]["binding"]["data_ref"] == current
    mismatch = api(
        "mismatch_audit_only",
        "skills",
        "replay",
        {
            "name": "metric_skill",
            "context": {"metric_kind": "sum"},
            "task_id": "mismatch",
            "data_ref": current,
            "window": 3,
        },
    )
    assert mismatch["decision"] == "AUDIT_ONLY"
    api(
        "invalidate_skill_source",
        "investigation",
        "invalidate",
        {"ref": source, "reason": "fixture:source correction"},
    )
    suspended = api(
        "suspended_after_reopen",
        "skills",
        "get",
        {"name": "metric_skill", "version": 1},
    )
    assert suspended["lifecycle"]["trust_state"] == "suspended"
    # Actual feedback → method governance → next-window resident scan loop.
    input_path = run / "scan_input.json"
    atomic_json(
        input_path,
        {
            "window_id": 1,
            "expected_through": 79,
            "observed_through": 79,
            "request": scan_request(),
        },
    )
    scan_context = {"workflow": "c_line"}
    api(
        "configure_scan",
        "scan",
        "configure",
        {
            "name": "resident",
            "input_path": str(input_path),
            "interval_seconds": 0.2,
            "test_budget": 30,
            "timeout": 5,
            "skill_name": "watch_skill",
            "skill_context": scan_context,
            "error_policy": "alpha_spending_empirical",
        },
    )
    api("start_scan", "scan", "start", {"name": "resident"})
    scan = api("first_scan", "scan", "tick", {"name": "resident", "force": True})
    assert scan["status"] == "COMPLETED"
    alerts = api("read_alerts", "scan", "alerts", {"name": "resident"})["result"]
    assert alerts
    feedback = api(
        "useful_feedback",
        "feedback",
        "submit",
        {
            "request_id": "feedback-1",
            "kind": "alert_feedback",
            "payload": {
                "alert_id": alerts[0]["alert_id"],
                "label": "useful",
                "operator": "fixture-analyst",
                "source_kind": "internal_event",
            },
        },
    )
    duplicate = api(
        "idempotent_feedback",
        "feedback",
        "submit",
        {
            "request_id": "feedback-1",
            "kind": "alert_feedback",
            "payload": {
                "alert_id": alerts[0]["alert_id"],
                "label": "useful",
                "operator": "fixture-analyst",
                "source_kind": "internal_event",
            },
        },
    )
    assert duplicate == feedback
    learnt = api(
        "feedback_to_skill",
        "skills",
        "learn_from_feedback",
        {
            "event_id": feedback["event_id"],
            "name": "watch_skill",
            "context": scan_context,
        },
    )
    assert learnt["spec"]["claim_ceiling"] == "WATCHLIST"
    api(
        "watch_independent_review",
        "skills",
        "review",
        {"name": "watch_skill", "version": 1, "reviewer": "fixture-reviewer"},
    )
    watch_suite = suite(40, "watch_suite", scan_context, "scan_window")
    valid = api(
        "watch_paired_validation",
        "skills",
        "validate",
        {"name": "watch_skill", "version": 1, "suite_ref": watch_suite},
    )
    assert valid["passed"]
    receipt = api(
        "watch_human_approval",
        "skills",
        "approve",
        {
            "name": "watch_skill",
            "version": 1,
            "approver": "fixture-human",
            "credential_ref": "fixture:watch-canary",
            "suite_ref": watch_suite,
        },
    )["approval_ref"]
    api(
        "watch_canary_publish",
        "skills",
        "publish",
        {
            "name": "watch_skill",
            "version": 1,
            "approval_ref": receipt,
            "effective_window": 2,
        },
    )
    canary = suite(50, "watch_canary", scan_context, "scan_window")
    valid = api(
        "watch_canary_monitor",
        "skills",
        "monitor",
        {"name": "watch_skill", "version": 1, "suite_ref": canary},
    )
    assert valid["passed"]
    receipt = api(
        "watch_expand_approval",
        "skills",
        "approve",
        {
            "name": "watch_skill",
            "version": 1,
            "approver": "fixture-human",
            "credential_ref": "fixture:watch-expanded",
            "suite_ref": canary,
        },
    )["approval_ref"]
    api(
        "watch_expanded",
        "skills",
        "publish",
        {
            "name": "watch_skill",
            "version": 1,
            "approval_ref": receipt,
            "fraction": 1,
            "effective_window": 2,
        },
    )
    next_request = scan_request(seed=7, start=90)
    atomic_json(
        input_path,
        {
            "window_id": 2,
            "expected_through": 169,
            "observed_through": 169,
            "request": next_request,
        },
    )
    next_scan = api(
        "next_window_uses_skill", "scan", "tick", {"name": "resident", "force": True}
    )
    assert (
        next_scan["status"] == "COMPLETED"
        and next_scan["skill_usage"]["report"]["operation"] == "scan_window"
    )
    same = api("same_window_dedup", "scan", "tick", {"name": "resident", "force": True})
    assert same["status"] == "ALREADY_PROCESSED"
    confirmation = api(
        "independent_confirmation",
        "scan",
        "confirm",
        {
            "name": "resident",
            "alert_ids": [alerts[0]["alert_id"]],
            "days": next_request["days"],
            "residual": next_request["residual"],
            "factors": next_request["factors"],
        },
    )
    assert confirmation["results"][0]["confirmed"] and confirmation["alpha"] == 0.025
    api(
        "reject_confirmation_reuse",
        "scan",
        "confirm",
        {
            "name": "resident",
            "alert_ids": [alerts[0]["alert_id"]],
            "days": next_request["days"],
            "residual": next_request["residual"],
            "factors": next_request["factors"],
        },
        2,
    )
    launched = api(
        "launch_real_resident_worker", "scan", "launch", {"name": "resident"}
    )
    try:
        assert launched["status"] == "RUNNING"
        time.sleep(0.3)
    finally:
        api("stop_resident_worker", "scan", "stop", {"name": "resident"})
    deadline = time.time() + 8
    while time.time() < deadline:
        status = subprocess.run(
            ["ps", "-p", str(launched["pid"]), "-o", "stat="],
            capture_output=True,
            text=True,
            check=False,
        )
        if (
            status.returncode
            or not status.stdout.strip()
            or status.stdout.strip().startswith("Z")
        ):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("resident worker did not stop")
    # Fresh counts, compatible parameters, actual posterior computation.
    statistical_context = {
        "metric": "conversion",
        "population": "eligible",
        "assignment_version": "v1",
    }
    old = {"arm_key": "control", "successes": 20, "trials": 100}
    old_ref = data("prior_observations", old)
    api(
        "observe_statistical_memory",
        "prior",
        "observe",
        {
            "task_id": "historical",
            "period": 1,
            "context": statistical_context,
            **old,
            "data_ref": old_ref,
        },
    )
    fresh_ref = data(
        "fresh_binomial", {"arm_key": "control", "successes": 21, "trials": 100}
    )
    posterior = api(
        "bound_posterior",
        "prior",
        "estimate_rate",
        {
            "task_id": "fresh",
            "context": statistical_context,
            "arm_key": "control",
            "current_period": 2,
            "data_ref": fresh_ref,
        },
    )
    assert (
        posterior["prior_check"]["prior"]
        and not posterior["causal_eligible"]
        and not posterior["method_memory_used"]
    )
    api("audit_trail", "investigation", "audit", {})
    pressure = []
    for shape in ("persistent", "onset", "pulse", "null"):
        results = []
        for seed in range(30):
            request = scan_request(
                seed=seed, shape=shape if shape != "null" else "persistent"
            )
            if shape == "null":
                request["residual"] = (
                    np.random.default_rng(seed + 500).normal(size=80).tolist()
                )
            result = run_c_line(**request)
            assert result["manifest"]["total_tests_spent"] <= request["test_budget"]
            results.append(
                {
                    "seed": seed,
                    "watchlist_count": len(result["watchlist"]),
                    "deferred_count": len(result["deferred"]),
                    "killed_count": result["killed_count"],
                    "tests_spent": result["manifest"]["total_tests_spent"],
                }
            )
        k = sum(r["watchlist_count"] > 0 for r in results)
        n = len(results)
        interval = [
            0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1)),
            1 if k == n else float(beta.ppf(0.975, k + 1, n - k)),
        ]
        pressure.append(
            {
                "shape": shape,
                "watchlist_rate": k / n,
                "monte_carlo_interval": interval,
                "seeds": results,
            }
        )
        if shape != "null":
            assert k / n >= 0.8, (shape, k)
    atomic_json(
        run / "effect_form_pressure.json",
        {
            "status": "PASS",
            "matrix": pressure,
            "scope": "exploratory WATCHLIST retention; not a causal/FDR guarantee",
            "seed_cases": 120,
        },
    )
    files = [
        {"path": str(p.relative_to(base)), "digest": digest(json.loads(p.read_text()))}
        for p in sorted(run.rglob("*.json"))
    ]
    report = {
        "status": "PASS",
        "cli_cases": len(cases),
        "cases": cases,
        "pressure_seed_cases": 120,
        "run_directory": str(run),
        "artifacts": files,
        "approval_scope": "fixture approval receipts only; not a production authorization",
    }
    atomic_json(base / "acceptance.json", report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "cli_cases": len(cases),
                "pressure_seed_cases": 120,
                "artifacts": len(files),
                "path": str(base / "acceptance.json"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
