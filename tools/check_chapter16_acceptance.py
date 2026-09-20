"""Actual CLI replay of chapter 16 feedback, registry, scanning and skill handoffs."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from track2_v5.hypothesis_registry import HypothesisRegistry


def main():
    base = ROOT / "outputs/chapter16"
    run = base / ("run-" + uuid.uuid4().hex[:10])
    run.mkdir(parents=True)
    db, factors = str(run / "state.db"), str(run / "factors.db")
    cases = []

    def call(label, operation, parameters, expected=0):
        path = run / f"{len(cases) + 1:02d}-{label}.request.json"
        out = path.with_name(path.name.replace(".request.", ".result."))
        path.write_text(
            json.dumps(
                {"operation": operation, "parameters": parameters}, ensure_ascii=False
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/run_causal_pipeline.py"),
                str(path),
                "--output",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        cases.append(
            {
                "case": label,
                "expected": expected,
                "returncode": result.returncode,
                "stderr": result.stderr,
            }
        )
        assert result.returncode == expected, cases[-1]
        return json.loads(out.read_text()) if result.returncode == 0 else None

    def service(label, operation, action, parameters, expected=0):
        return call(
            label,
            operation,
            {"db_path": db, "action": action, "parameters": parameters},
            expected,
        )

    rng = np.random.default_rng(1601)
    x = rng.normal(size=80)
    y = 0.9 * np.roll(x, 2) + rng.normal(size=80) * 0.1
    days = list(range(80))
    request = {
        "days": days,
        "residual": y.tolist(),
        "factors": [
            {
                "factor_id": "driver",
                "kind": "internal_event",
                "days": days,
                "values": x.tolist(),
            }
        ],
        "lags": [2],
        "budget": 2,
        "test_budget": 30,
    }
    source = run / "scan-input.json"
    payload = {
        "window_id": 0,
        "expected_through": 79,
        "observed_through": 79,
        "request": request,
    }
    source.write_text(json.dumps(payload))
    service(
        "configure",
        "scan",
        "configure",
        {
            "name": "c",
            "input_path": str(source),
            "factor_db_path": factors,
            "test_budget": 30,
        },
    )
    service("start", "scan", "start", {"name": "c"})
    first = service("scan-first", "scan", "tick", {"name": "c", "force": True})
    assert first["status"] == "COMPLETED"
    alerts = service("alerts", "scan", "alerts", {"name": "c"})["result"]
    alert = alerts[0]
    service(
        "candidate-confirm",
        "cognitive",
        "respond",
        {
            "request_id": "confirm",
            "kind": "candidate_review",
            "alert_id": alert["alert_id"],
            "payload": {
                "factor_id": alert["factor_id"],
                "decision": "confirmed",
                "operator": "ops",
                "current_window": 0,
            },
        },
    )
    supplement = {
        "factor_id": "sms",
        "factor_kind": "internal_event",
        "operator": "ops",
        "note": "declared SMS event",
        "available_day": 79,
        "current_window": 0,
        "snapshots": [{"day": d, "value": v} for d, v in zip(days, x.tolist())],
    }
    registered = service(
        "human-factor",
        "cognitive",
        "respond",
        {
            "request_id": "factor",
            "kind": "factor_supplement",
            "factor_db_path": factors,
            "payload": supplement,
        },
    )
    assert registered["registration"]["eligible_from_window"] == 1
    frozen = service("same-window-frozen", "scan", "tick", {"name": "c", "force": True})
    assert frozen["status"] == "ALREADY_PROCESSED"
    payload["window_id"] = 1
    source.write_text(json.dumps(payload))
    second = service("next-window-grid", "scan", "tick", {"name": "c", "force": True})
    assert second["status"] == "COMPLETED" and second["registry_intake"]["added"] == [
        "sms"
    ]
    useful = {
        "request_id": "useful",
        "kind": "alert_feedback",
        "payload": {
            "alert_id": alert["alert_id"],
            "operator": "ops",
            "label": "useful",
        },
        "skill_name": "watch_skill",
        "context": {"workflow": "c_line"},
    }
    learned = service("feedback-to-skill", "cognitive", "respond", useful)
    assert learned["skill_proposal"]["spec"]["claim_ceiling"] == "WATCHLIST"
    assert service("idempotent", "cognitive", "respond", useful) == learned
    exported = service(
        "export-skill", "skills", "export_markdown", {"name": "watch_skill"}
    )
    assert not exported["execution_eligible"]
    (run / "SKILL.md").write_text(exported["markdown"])
    trace = service(
        "second-trace",
        "skills",
        "capture",
        {
            "task_id": "second",
            "data_ref": second["data_ref"],
            "context": {"workflow": "c_line"},
            "operation": "scan_window",
            "author": "ops",
        },
    )
    service(
        "parallel-proposal",
        "skills",
        "propose",
        {
            "name": "parallel_watch",
            "trace_ids": [
                *learned["skill_proposal"]["spec"]["source_trace_ids"],
                trace["trace_id"],
            ],
            "applicability": {"workflow": "c_line"},
            "claim_ceiling": "WATCHLIST",
        },
    )
    registry = HypothesisRegistry(db)
    try:
        analyses = [
            r["body"]["analyses"]
            for r in registry.audit()
            if r["event"] == "PARALLEL_SKILL_ANALYSIS"
        ][-1]
        assert len({a["analyst_pid"] for a in analyses}) == 2
        (run / "analyst-evidence.json").write_text(json.dumps(analyses, indent=2))
    finally:
        registry.close()
    revised = {
        **useful,
        "request_id": "false-positive",
        "payload": {**useful["payload"], "label": "false_positive"},
    }
    negative = service("negative-label", "cognitive", "respond", revised)
    assert negative["skill_proposal"]["negative_example_retained"]
    service(
        "stale-training-rejected",
        "skills",
        "learn_from_feedback",
        {
            "event_id": learned["feedback"]["event_id"],
            "name": "watch_skill",
            "context": {"workflow": "c_line"},
        },
        2,
    )
    service(
        "unknown-alert-rejected",
        "cognitive",
        "respond",
        {
            "request_id": "unknown",
            "kind": "alert_feedback",
            "payload": {"alert_id": "unknown", "operator": "ops", "label": "useful"},
        },
        2,
    )
    service(
        "spoof-source-rejected",
        "cognitive",
        "respond",
        {
            "request_id": "spoof",
            "kind": "alert_feedback",
            "payload": {**useful["payload"], "source_kind": "fake"},
        },
        2,
    )
    ledger = service("ledger", "feedback", "ledger", {})
    assert any(not e["is_current"] for e in ledger["entries"])
    assert all(not e["claim_promotion_allowed"] for e in ledger["entries"])
    service("stop", "scan", "stop", {"name": "c"})
    summary = {
        "status": "PASS",
        "cli_cases": len(cases),
        "run": str(run.relative_to(ROOT)),
        "cases": cases,
    }
    (base / "acceptance.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
