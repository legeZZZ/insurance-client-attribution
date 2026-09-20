"""Real CLI acceptance for enterprise adapters and blind state transitions."""

import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_stage_e_statistics import effect_request
from track2_v5.contracts import digest
from track2_v5.evaluation import TRUTH_KEYS
from track2_v5.persistence import atomic_json


def run(output):
    root = Path(__file__).resolve().parents[1]
    out = Path(output).resolve()
    run = out / ("run-" + uuid.uuid4().hex[:10])
    run.mkdir(parents=True)
    cases = []

    def call(label, operation, parameters, expected=0):
        request = {"operation": operation, "parameters": parameters}
        input_path = run / (label + ".request.json")
        result_path = run / (label + ".result.json")
        atomic_json(input_path, request)
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools/run_causal_pipeline.py"),
                str(input_path),
                "--output",
                str(result_path),
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
            cwd=root,
        )
        cases.append(
            {
                "case": label,
                "expected": expected,
                "returncode": result.returncode,
                "stderr": result.stderr,
                "stdout": result.stdout,
                "request_digest": digest(request),
            }
        )
        atomic_json(run / "progress.json", cases)
        if result.returncode != expected:
            raise AssertionError(label + ": " + result.stderr)
        return json.loads(result_path.read_text()) if result_path.exists() else None

    for domain in ("insurance", "ecommerce"):
        for line in ("A", "B", "C"):
            result = call(
                domain + "-" + line,
                "enterprise",
                {
                    "manifest_path": str(
                        root / "examples/domains" / domain / (line + ".json")
                    ),
                    "as_of": 101,
                    "runtime_dir": str(run / "runtime"),
                },
            )
            assert result["result"]["execution_status"] == "COMPLETED"
    call(
        "unavailable-source",
        "enterprise",
        {
            "manifest_path": str(root / "examples/domains/insurance/A.json"),
            "as_of": 100,
            "runtime_dir": str(run / "runtime"),
        },
        2,
    )
    call(
        "N1",
        "external_adapter",
        {
            "kind": "N1",
            "parameters": {
                "db_path": str(run / "factors.db"),
                "current_window": 100,
                "available_day": 101,
                "factor_series": [
                    {
                        "factor_id": "external-x",
                        "days": [0, 1],
                        "values": [1, 2],
                        "source_uri": "declared://authorized",
                        "license_ref": "declared",
                        "unit": "index",
                        "source_type": "authorized_external",
                        "response_window": [1, 2],
                    }
                ],
            },
        },
    )
    call(
        "N2",
        "external_adapter",
        {
            "kind": "N2",
            "parameters": {
                "snapshot": {"phase": "DISCOVERY", "round": 0},
                "factor_ids": ["x"],
            },
        },
    )
    design = {
        "template_id": "ab",
        "metric": "conversion",
        "factors": ["x"],
        "stable_randomization_unit": "user",
        "metric_contract": {"name": "conversion", "unit": "rate"},
    }
    r = call(
        "N3",
        "external_adapter",
        {
            "kind": "N3",
            "parameters": {"design": design, "approval_ref": "fixture:sandbox"},
        },
    )
    assert (
        r["side_effect"] == "none_sandbox"
        and r["final"]["status"] == "PAUSE_RECOMMENDED"
    )
    call(
        "N3-production-rejected",
        "external_adapter",
        {"kind": "N3", "parameters": {"mode": "production"}},
        2,
    )
    for family in ("A_signal", "A_null", "A_overlap_invalid"):
        req, effect, identified = effect_request(family, 90001)
        db = str(run / "blind.db")
        case_id = family

        def blind(label, action, parameters, expected=0, family=family, db=db):
            return call(
                family + "-" + label,
                "blind",
                {"db_path": db, "action": action, "parameters": parameters},
                expected,
            )

        protocol = {
            "frozen_by": "analyst",
            "analysis_as_of": 101,
            "truth_scope": "full",
        }
        blind(
            "freeze",
            "freeze",
            {
                "case_id": case_id,
                "request": {"operation": "effect", "parameters": req},
                "protocol": protocol,
            },
        )
        truth = {key: None for key in TRUTH_KEYS}
        truth["intervention_effects"] = [
            {"id": "effect", "effect": effect, "identifiable": identified}
        ]
        reveal = {
            "case_id": case_id,
            "truth": truth,
            "reviewer": "independent-business-review",
            "evidence_ref": "fixture:known-DGP",
        }
        blind("early-reveal-rejected", "reveal", reveal, 2)
        result = blind("run", "run", {"case_id": case_id})
        assert result["state"] == "RESULT_FROZEN"
        score = blind("truth", "reveal", reveal)
        assert score["state"] == "SCORED"
        blind("read", "read", {"case_id": case_id})
        blind(
            "report",
            "report",
            {"case_id": case_id, "output_path": str(run / (family + ".md"))},
        )
        replay = blind("idempotent", "run", {"case_id": case_id})
        assert replay["result_digest"] == result["result_digest"]
        if identified:
            assert score["scores"]["intervention_effects"]["evaluated"] == 1
        else:
            assert score["scores"]["intervention_effects"]["unavailable"] == 1
    files = [
        {"path": str(p.relative_to(out)), "digest": digest(p.read_text())}
        for p in sorted(run.glob("*.json"))
    ]
    result = {
        "status": "PASS",
        "cli_cases": len(cases),
        "cases": cases,
        "run_directory": str(run),
        "artifacts": files,
        "scope": "existing data and fixture business evidence; real business blind cases are replaceable later",
    }
    atomic_json(out / "acceptance.json", result)
    print(
        json.dumps(
            {"status": "PASS", "cli_cases": len(cases), "run_directory": str(run)}
        )
    )


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "outputs/stage_e/completion")
