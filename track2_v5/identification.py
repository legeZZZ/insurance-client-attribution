"""Design-driven, fail-closed identification decisions bound to evidence.

Diagnostics and maintained assumptions are reported separately. Declared
assumptions are not treated as facts established by a statistical test.
"""

from __future__ import annotations

from .contracts import digest, validate_contract

REQUIREMENTS = {
    "RCT": {
        "assignment_traceable": "DATA_INVALID",
        "srm_pass": "DATA_INVALID",
        "assignment_consistent": "DATA_INVALID",
        "interference_absent": "CONTROL_CONTAMINATED",
    },
    "DiD": {
        "parallel_trends": "MODEL_MISMATCH",
        "parallel_trends_extrapolation": "NOT_IDENTIFIABLE",
        "independent_units": "MODEL_MISMATCH",
        "no_anticipation": "MODEL_MISMATCH",
        "unaffected_controls": "CONTROL_CONTAMINATED",
        "no_differential_shock": "NOT_IDENTIFIABLE",
        "rollout_design_compatible": "MODEL_MISMATCH",
    },
    "BSTS": {
        "control_predictive_gain": "MODEL_MISMATCH",
        "preperiod_backtest": "MODEL_MISMATCH",
        "unaffected_controls": "CONTROL_CONTAMINATED",
        "stable_relationship": "MODEL_MISMATCH",
    },
    "SCM": {
        "control_predictive_gain": "MODEL_MISMATCH",
        "preperiod_backtest": "MODEL_MISMATCH",
        "stable_relationship": "MODEL_MISMATCH",
        "donor_eligibility": "CONTROL_CONTAMINATED",
        "preperiod_fit": "MODEL_MISMATCH",
        "no_spillover": "CONTROL_CONTAMINATED",
        "leave_one_out_stable": "MODEL_MISMATCH",
        "weight_concentration_acceptable": "MODEL_MISMATCH",
    },
    "GCM": {
        "independent_units": "MODEL_MISMATCH",
        "accepted_graph": "GRAPH_AMBIGUOUS",
        "mechanisms_fitted": "MODEL_MISMATCH",
        "no_extrapolation": "NOT_IDENTIFIABLE",
        "causal_sufficiency": "NOT_IDENTIFIABLE",
    },
    "ITS": {},
}
MAINTAINED = {
    "parallel_trends_extrapolation",
    "independent_units",
    "interference_absent",
    "no_differential_shock",
    "stable_relationship",
    "no_spillover",
    "causal_sufficiency",
}
ROUTES = {
    "RCT": "A",
    "DiD": "B",
    "BSTS": "B",
    "SCM": "B",
    "GCM": "C",
    "ITS": "exploratory_prediction",
}
FORBIDDEN_ROLES = {
    "mediator",
    "collider",
    "selection",
    "post_treatment",
    "treatment_proxy",
    "unknown",
}


def _is_dag(dag, treatment, outcome):
    if (
        not isinstance(dag, dict)
        or not isinstance(dag.get("nodes"), list)
        or not isinstance(dag.get("edges"), list)
    ):
        return False
    nodes = dag["nodes"]
    if len(set(nodes)) != len(nodes) or treatment not in nodes or outcome not in nodes:
        return False
    adjacency = {n: [] for n in nodes}
    for edge in dag["edges"]:
        if (
            not isinstance(edge, (tuple, list))
            or len(edge) != 2
            or any(n not in adjacency for n in edge)
        ):
            return False
        adjacency[edge[0]].append(edge[1])
    active, done = set(), set()

    def visit(n):
        if n in active:
            return False
        if n in done:
            return True
        active.add(n)
        if not all(visit(child) for child in adjacency[n]):
            return False
        active.remove(n)
        done.add(n)
        return True

    return all(visit(n) for n in nodes)


def identify_effect(
    *,
    treatment,
    outcome,
    design,
    checks,
    data_digest,
    target_population,
    adjustment_set=(),
    feature_roles=None,
    graph_report=None,
    accepted_dag=None,
    simultaneous_interventions=(),
    requested_effect="individual",
):
    if design not in REQUIREMENTS:
        raise ValueError("unsupported identification design")
    if not all(
        isinstance(v, str) and v.strip()
        for v in (treatment, outcome, data_digest, target_population)
    ):
        raise ValueError(
            "identification requires treatment, outcome, data digest and population"
        )
    if treatment == outcome or not isinstance(checks, dict):
        raise ValueError("invalid treatment/outcome or evidence checks")
    proposed = list(adjustment_set)
    if len(set(proposed)) != len(proposed):
        raise ValueError("duplicate adjustment variable")
    roles = dict(feature_roles or {})
    forbidden = sorted(
        {n for n in proposed if roles.get(n, "unknown") != "pre_treatment"}
        | {treatment, outcome}
    )
    invalid_adjustments = sorted(set(proposed) & set(forbidden))
    requirements = {
        "data_valid": "DATA_INVALID",
        "outcome_mature": "DATA_INVALID",
        "support_overlap": "NOT_IDENTIFIABLE",
        **REQUIREMENTS[design],
    }
    reasons, assumptions, refs = set(), [], set()
    for name, failure_code in requirements.items():
        entry = checks.get(name, {})
        if not isinstance(entry, dict):
            raise ValueError(f"malformed check: {name}")
        evidence = entry.get("evidence_refs", [])
        if not isinstance(evidence, list) or any(
            not isinstance(x, str) or not x.strip() for x in evidence
        ):
            raise ValueError(f"malformed evidence references: {name}")
        state = entry.get("status", "missing")
        allowed = state == "supported" or (state == "assumed" and name in MAINTAINED)
        passed = bool(allowed and evidence)
        if not passed:
            reasons.add(failure_code)
        refs.update(evidence)
        assumptions.append(
            {
                "name": name,
                "status": state,
                "passed": passed,
                "evidence_refs": evidence,
                "data_verifiable": name not in MAINTAINED,
            }
        )
    if invalid_adjustments:
        reasons.add("NOT_IDENTIFIABLE")
    ambiguities = []
    if design == "ITS":
        reasons.add("NOT_IDENTIFIABLE")
    if len(simultaneous_interventions) > 1 and requested_effect != "bundle":
        reasons.add("NOT_IDENTIFIABLE")
        ambiguities.append("simultaneous_interventions_not_separable")
    # Valid randomization does not require observational graph orientation.
    if design == "GCM":
        if graph_report is not None:
            body = {k: v for k, v in graph_report.items() if k != "digest"}
            if graph_report.get("digest") != digest(body):
                reasons.add("DATA_INVALID")
            ambiguities.extend(graph_report.get("ambiguities", []))
            if graph_report.get("status") != "COMPLETED":
                ambiguities.append("graph_discovery_incomplete")
        if not _is_dag(accepted_dag, treatment, outcome):
            ambiguities.append("accepted_acyclic_graph_required")
        if ambiguities:
            reasons.add("GRAPH_AMBIGUOUS")
    result = {
        "treatment": treatment,
        "outcome": outcome,
        "design": design,
        "status": "IDENTIFIED" if not reasons else "NOT_IDENTIFIED",
        "assumptions": assumptions,
        "evidence_refs": sorted(refs),
        "adjustment_set": [n for n in proposed if n not in invalid_adjustments],
        "forbidden_adjustments": forbidden,
        "rejected_adjustments": invalid_adjustments,
        "support": {
            "target_population": target_population,
            "data_digest": data_digest,
            "overlap_check": checks.get("support_overlap", {}),
        },
        "ambiguities": sorted(set(ambiguities)),
        "reason_codes": sorted(reasons),
        "route": ROUTES[design],
        "effect_scope": requested_effect,
        "causal_effect_allowed": not reasons,
        "supplemental_evidence_needed": [
            a["name"] for a in assumptions if not a["passed"]
        ],
        "graph_ref": graph_report.get("digest") if graph_report else None,
        "dag_digest": digest(accepted_dag) if accepted_dag is not None else None,
    }
    return validate_contract("IdentificationReport", result)
