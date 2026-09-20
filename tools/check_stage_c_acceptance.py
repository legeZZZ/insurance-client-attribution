"""Run actual phase-C CLI requests and retain replayable evidence, failures and digests."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_stage_c import panel, parameters

from track2_v5.contracts import digest
from track2_v5.persistence import atomic_json
from track2_v5.scenario_reports import read_run


def main():
    base = ROOT / "outputs/stage_c/completion"
    run = base / ("run-" + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    cases = []

    def execute(name, operation, parameters_, expected=0):
        request = {"operation": operation, "parameters": parameters_}
        source, target = run / (name + ".request.json"), run / (name + ".result.json")
        atomic_json(source, request)
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/run_causal_pipeline.py"),
                str(source),
                "--output",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=ROOT,
        )
        cases.append(
            {
                "case": name,
                "operation": operation,
                "returncode": process.returncode,
                "expected_returncode": expected,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
        )
        if process.returncode != expected:
            raise AssertionError(cases[-1])
        return json.loads(target.read_text()) if target.exists() else None

    direct = execute(
        "01_direct_rct",
        "pipeline",
        {
            "request": {"route": "A", "parameters": parameters()},
            "runtime_dir": str(run / "runtime"),
            "baseline_bytes": 10000000,
        },
    )
    assert direct["execution_status"] == "COMPLETED"
    assert len({r["pid"] for r in direct["records"]}) == 4
    assert direct["publication"]["claim_type"] == "RANDOMIZED_EFFECT"
    refused = execute(
        "02_identification_refused",
        "pipeline",
        {
            "request": {"route": "A", "parameters": parameters(False)},
            "runtime_dir": str(run / "runtime"),
            "baseline_bytes": 10000000,
        },
    )
    assert refused["publication"]["interpretation"] == "UNTRUSTWORTHY"
    assert refused["publication"]["statistical_uncertainty"]["effect"] is None
    fallback = execute(
        "03_cost_fallback",
        "pipeline",
        {
            "request": {"route": "A", "parameters": parameters()},
            "runtime_dir": str(run / "runtime"),
            "baseline_bytes": 1,
        },
    )
    assert fallback["fallback"] and len(fallback["cost_ledger"]) == 2
    timed = execute(
        "04_worker_timeout",
        "pipeline",
        {
            "request": {"route": "A", "parameters": parameters()},
            "runtime_dir": str(run / "runtime"),
            "timeout": 0.00001,
        },
    )
    assert timed["execution_status"] == "FAILED" and not timed["records"]
    data = panel()
    association = {
        **data,
        "anomaly_windows": [],
        "discovery_days": list(range(74)),
        "holdout_days": list(range(80, 100)),
        "max_lag": 1,
        "smoothing_window": 1,
        "derived_layers": ["level"],
        "bootstrap_reps": 19,
        "block_length": 3,
        "min_abs_correlation": 0.1,
    }
    baseline = {
        "days": data["days"],
        "control": [0.3] * 100,
        "treated": [0.3] * 100,
        "change_registry": [],
        "external_registry": [],
        "experiments": {},
    }
    layered = execute(
        "05_full_four_layer",
        "pipeline",
        {
            "request": {
                "route": "A",
                "parameters": parameters(),
                "association": association,
                "baseline": baseline,
            },
            "runtime_dir": str(run / "runtime"),
            "baseline_bytes": 10000000,
        },
    )
    assert layered["execution_status"] == "COMPLETED", layered.get("error")
    assert layered["records"][0]["output"]["baseline"] is not None
    assert layered["records"][1]["output"]["status"] == "COMPLETED"
    db = str(run / "investigation.db")

    def investigation(name, action, parameters_, expected=0):
        return execute(
            name,
            "investigation",
            {"db_path": db, "action": action, "parameters": parameters_},
            expected,
        )

    resource = investigation(
        "06_data_snapshot", "revise_resource", {"name": "panel", "body": data}
    )
    config = {
        "max_lag": 1,
        "derived_layers": ["level"],
        "smoothing_window": 1,
        "bootstrap_reps": 19,
        "block_length": 3,
        "min_abs_correlation": 0.1,
    }
    loop = investigation(
        "07_create_loop",
        "create_loop",
        {"data_ref": resource["ref"], "resource_name": "panel", "config": config},
    )
    completed = investigation("08_rules_loop", "run_loop", {"loop_id": loop["loop_id"]})
    assert completed["phase"] == "COMPLETED" and completed["tests_spent"] == 6
    replay = investigation("09_reopen_loop", "read_loop", {"loop_id": loop["loop_id"]})
    assert replay == completed
    investigation(
        "10_reject_post_terminal_change",
        "step_loop",
        {
            "loop_id": loop["loop_id"],
            "proposal": {
                "action": "ADJUST_THRESHOLD",
                "parameters": {"min_abs_correlation": 0.01},
            },
        },
        2,
    )
    investigation(
        "11_reject_window_escape",
        "step_loop",
        {
            "loop_id": loop["loop_id"],
            "proposal": {
                "action": "ADJUST_THRESHOLD",
                "parameters": {"window": [0, 99]},
            },
        },
        2,
    )
    investigation("12_audit", "audit", {})
    execute(
        "13_invalidate_published_data",
        "investigation",
        {
            "db_path": direct["registry_path"],
            "action": "invalidate",
            "parameters": {
                "ref": direct["data_ref"],
                "reason": "phase C corrected-input replay",
            },
        },
    )
    revoked = read_run(run / "runtime", direct["run_id"])
    assert revoked["publication_status"] == "REVOKED" and "publication" not in revoked
    atomic_json(run / "14_read_revoked_report.result.json", revoked)
    factor_db = str(run / "factors.db")
    series = {
        **data["factor_series"][0],
        "days": data["days"],
        "source_uri": "fixture:declared-source",
        "license_ref": "fixture-license",
        "response_window": [0, 1],
    }
    execute(
        "15_adapter_intake",
        "factor_registry",
        {
            "db_path": factor_db,
            "action": "intake_adapter",
            "parameters": {
                "factor_series": [series],
                "current_window": 0,
                "available_day": 0,
            },
        },
    )
    hidden = execute(
        "16_same_window_excluded",
        "factor_registry",
        {
            "db_path": factor_db,
            "action": "retrieve",
            "parameters": {"as_of": 99, "search_window": 0},
        },
    )
    assert not hidden["result"]
    available = execute(
        "17_next_window_retrieval",
        "factor_registry",
        {
            "db_path": factor_db,
            "action": "retrieve",
            "parameters": {"as_of": 99, "search_window": 1},
        },
    )
    assert available["result"][0]["factor_contract"]
    assert available["result"][0]["causal_eligible"] is False
    prepared = investigation(
        "18_registry_to_loop",
        "create_loop_from_factors",
        {
            "data_ref": resource["ref"],
            "resource_name": "registry_analysis",
            "factor_db_path": factor_db,
            "as_of": 99,
            "search_window": 1,
            "config": config,
        },
    )
    registered_loop = investigation(
        "19_registered_factor_loop", "run_loop", {"loop_id": prepared["loop_id"]}
    )
    assert registered_loop["phase"] == "COMPLETED"
    execute(
        "20_factor_history",
        "factor_registry",
        {"db_path": factor_db, "action": "history", "parameters": {"factor_id": "x"}},
    )
    files = [
        {"path": str(p.relative_to(base)), "digest": digest(json.loads(p.read_text()))}
        for p in sorted(run.rglob("*.json"))
    ]
    result = {
        "status": "PASS",
        "cli_cases": len(cases),
        "cases": cases,
        "artifacts": files,
        "run_directory": str(run),
        "verification": [
            "four_process_ids",
            "L0_baseline_and_L1_association_executed",
            "direct_preregistered_RCT",
            "refused_design_has_no_effect",
            "timeout_stops_downstream",
            "4x_cost_fallback",
            "durable_rule_loop",
            "one_final_holdout",
            "reject_window_reset",
            "revoked_report_redaction",
            "adapter_next_window_factor_contract_loop",
        ],
    }
    atomic_json(base / "acceptance.json", result)
    print(
        json.dumps(
            {
                "status": "PASS",
                "cli_cases": len(cases),
                "artifacts": len(files),
                "path": str(base / "acceptance.json"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
