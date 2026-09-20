"""Actual CLI proof for research boundaries and opt-in future-window synthesis."""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_stage_f_research import synthetic
from track2_v5.persistence import atomic_json


def run(output):
    root = Path(__file__).resolve().parents[1]
    out = Path(output).resolve()
    folder = out / ("run-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    db = str(folder / "state.db")
    records = []

    def call(name, operation, parameters, expected=0):
        request = {"operation": operation, "parameters": parameters}
        p = folder / (name + ".request.json")
        r = folder / (name + ".result.json")
        atomic_json(p, request)
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools/run_causal_pipeline.py"),
                str(p),
                "--output",
                str(r),
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        records.append(
            {
                "case": name,
                "expected": expected,
                "returncode": result.returncode,
                "stderr": result.stderr,
            }
        )
        atomic_json(folder / "progress.json", records)
        if result.returncode != expected:
            raise AssertionError(name + ": " + result.stderr)
        return json.loads(r.read_text()) if r.exists() else None

    def synth(name, action, parameters, expected=0):
        return call(
            name,
            "synthesis",
            {"db_path": db, "action": action, "parameters": parameters},
            expected,
        )

    rng = np.random.default_rng(7)
    x = rng.normal(size=(160, 12))
    y = rng.normal(size=160)
    r = call(
        "knockoff-dependent",
        "knockoff_research",
        {
            "x": x.tolist(),
            "y": y.tolist(),
            "feature_ids": [str(i) for i in range(12)],
            "covariance": np.eye(12).tolist(),
            "distribution_known": True,
            "distribution_ref": "fixture:declared",
            "temporal_rho": 0.8,
            "subsample_gap": 3,
        },
    )
    assert not r["formal_selection_allowed"] and r["full_temporal_swap_error"] > 0
    ref = call(
        "discovery-data",
        "investigation",
        {
            "db_path": db,
            "action": "revise_resource",
            "parameters": {"name": "f-source", "body": synthetic(1)},
        },
    )["ref"]
    synth("disabled-config", "configure", {"policy_id": "p", "enabled": False})
    proposal = {
        "policy_id": "p",
        "task_id": "t",
        "data_ref": ref,
        "current_window": 99,
        "expression": {"op": "multiply", "args": [{"factor": "x"}, {"factor": "z"}]},
    }
    synth("disabled-reject", "propose", proposal, 2)
    synth("enable", "set_enabled", {"policy_id": "p", "enabled": True})
    product = synth("product", "propose", proposal)["factor_id"]
    for name, op in [("sum", "add"), ("difference", "subtract")]:
        synth(
            name,
            "propose",
            {
                **proposal,
                "expression": {"op": op, "args": [{"factor": "u"}, {"factor": "v"}]},
            },
        )
    r = synth("freeze", "freeze", {"task_id": "t"})
    assert len(r["items"]) == 3
    synth(
        "mutate-frozen-reject",
        "propose",
        {**proposal, "expression": {"factor": "x"}},
        2,
    )
    synth("reuse-discovery-reject", "confirm", {"task_id": "t", "data_ref": ref}, 2)
    fresh = call(
        "confirmation-data",
        "investigation",
        {
            "db_path": db,
            "action": "revise_resource",
            "parameters": {"name": "f-validation", "body": synthetic(5001, 110)},
        },
    )["ref"]
    r = synth("confirm", "confirm", {"task_id": "t", "data_ref": fresh})
    assert len(r["confirmation"]["results"]) == 3 and any(
        item["alert_id"] == product and item["confirmed"]
        for item in r["confirmation"]["results"]
    )
    replay = synth("idempotent", "confirm", {"task_id": "t", "data_ref": fresh})
    assert replay["result_ref"] == r["result_ref"]
    call(
        "invalidate",
        "investigation",
        {
            "db_path": db,
            "action": "invalidate",
            "parameters": {"ref": fresh, "reason": "fixture:corrected data"},
        },
    )
    r = synth("withdrawn", "read", {"task_id": "t"})
    assert r["state"] == "WITHDRAWN"
    result = {
        "status": "PASS",
        "cli_cases": len(records),
        "cases": records,
        "run_directory": str(folder),
    }
    atomic_json(out / "acceptance.json", result)
    print(json.dumps({"status": "PASS", "cli_cases": len(records)}))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "outputs/stage_f/completion")
