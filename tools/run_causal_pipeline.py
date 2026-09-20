"""Execute a graph, identification or randomized-effect request from JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.action_interface import (
    decide_action,
    evaluate_checkpoint,
    propose_experiment,
    register_sequential_policy,
)
from track2_v5.association_discovery import discover_association_factors
from track2_v5.blind_validation import execute_blind
from track2_v5.causal_discovery import discover_causal_graph
from track2_v5.cognitive_loop import execute_cognitive
from track2_v5.enterprise import external_adapter, run_enterprise
from track2_v5.evolution_api import (
    execute_feedback,
    execute_prior,
    execute_scan,
    execute_skills,
)
from track2_v5.factor_synthesis import execute_synthesis
from track2_v5.gcm_track import estimate_gcm_effect
from track2_v5.identification import identify_effect
from track2_v5.investigation_api import execute_factor_registry, execute_investigation
from track2_v5.knockoff_research import run_knockoff_research
from track2_v5.observational_extensions import (
    apply_negative_controls,
    estimate_bsts_mixture,
    estimate_ratio_series,
    estimate_staggered_did,
    run_negative_control_suite,
)
from track2_v5.persistence import atomic_json
from track2_v5.quant_track import (
    estimate_controlled_series_effect,
    estimate_did_effect,
    estimate_effect,
    estimate_randomized_effect,
)
from track2_v5.randomized_extensions import (
    estimate_causal_forest,
    estimate_ratio_effect,
)
from track2_v5.scenario_reports import run_causal_investigation


def execute(request):
    operations = {
        "cognitive": execute_cognitive,
        "knockoff_research": run_knockoff_research,
        "synthesis": execute_synthesis,
        "enterprise": run_enterprise,
        "external_adapter": external_adapter,
        "blind": execute_blind,
        "skills": execute_skills,
        "feedback": execute_feedback,
        "scan": execute_scan,
        "prior": execute_prior,
        "pipeline": run_causal_investigation,
        "investigation": execute_investigation,
        "factor_registry": execute_factor_registry,
        "graph": discover_causal_graph,
        "effect": estimate_effect,
        "association": discover_association_factors,
        "gcm_effect": estimate_gcm_effect,
        "ratio_effect": estimate_ratio_effect,
        "causal_forest": estimate_causal_forest,
        "staggered_did": estimate_staggered_did,
        "bsts_mixture": estimate_bsts_mixture,
        "ratio_series": estimate_ratio_series,
        "negative_controls": apply_negative_controls,
        "negative_control_suite": run_negative_control_suite,
        "action": decide_action,
        "experiment_proposal": propose_experiment,
        "sequential_policy": register_sequential_policy,
        "checkpoint": evaluate_checkpoint,
        "identify": identify_effect,
        "randomized_effect": estimate_randomized_effect,
        "did_effect": estimate_did_effect,
        "controlled_series_effect": estimate_controlled_series_effect,
    }
    if not isinstance(request, dict) or request.get("operation") not in operations:
        raise ValueError("unknown operation; supported: " + ", ".join(operations))
    parameters = request.get("parameters")
    if not isinstance(parameters, dict):
        raise TypeError("parameters must be an object")
    return operations[request["operation"]](**parameters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(json.loads(args.request.read_text(encoding="utf-8")))
        atomic_json(args.output, result)
    except (ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"DATA_INVALID: {exc}\n")
    print(
        json.dumps(
            {"status": result.get("status"), "output": str(args.output.resolve())},
            ensure_ascii=False,
        )
    )
