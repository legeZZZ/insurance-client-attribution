"""attribution: Insurance growth attribution and causal-readiness vertical slice."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .analysis import (
    aggregate_funnel,
    build_claim,
    causal_readiness,
    estimate_itt,
    extract_features,
    sanitize_rows,
)
from .foundation import (
    AgentIdentity,
    AgentTeamsControlPlane,
    LocalEvidenceProvider,
    SQLiteCheckpointProvider,
    TeamTopology,
)

CASE_AGENTS = [
    (
        "intent",
        "Intent parsing",
        ["RECEIVED", "INTENT_PARSED"],
        ["parse business question"],
        ["AnalysisIntent"],
        ["MetricContractResolver"],
    ),
    (
        "metric_contract",
        "Metric contract governance",
        ["METRIC_CONFIRMED", "NEEDS_CLARIFICATION"],
        ["resolve metric definition"],
        ["MetricContract"],
        ["MetricContractResolver"],
    ),
    (
        "data_acquisition",
        "Read-only data acquisition",
        ["DATA_VALIDATED", "DATA_INSUFFICIENT"],
        ["profile schema", "validate data quality"],
        ["QueryPlan", "DataQualityReport"],
        ["SchemaProfiler", "ReadOnlyQueryPlanner", "DataQualityGate"],
    ),
    (
        "diagnostic",
        "Funnel and structure diagnosis",
        ["DIAGNOSING"],
        ["decompose funnel", "profile segments"],
        ["AttributionCandidateSet"],
        ["FunnelDecomposer", "ProductMixDecomposer", "SegmentProfiler", "EventAligner"],
    ),
    (
        "causal_evidence",
        "Causal readiness and claim governance",
        ["EVIDENCE_GRADED", "DESCRIPTIVE_ONLY", "COMPLIANCE_REVIEWED", "CLOSED"],
        ["grade evidence", "constrain claims"],
        ["EvidenceReport", "ClaimLedger"],
        ["ExperimentIntegrityGate", "CausalReadinessCheck", "ClaimPolicyGuard"],
    ),
    (
        "experiment_planner",
        "Experiment and action planning",
        ["ACTION_DRAFTED", "AWAITING_APPROVAL"],
        ["draft experiment", "define guardrails"],
        ["ExperimentSpec"],
        ["ExperimentPlanner"],
    ),
    (
        "monitor_review",
        "Experiment monitoring and review",
        ["MONITORING", "REVIEWED", "CLOSED"],
        ["monitor result", "propose playbook patch"],
        ["MonitoringReport", "PlaybookPatch"],
        ["ExperimentMonitor", "WeeklyBriefComposer"],
    ),
]


CASE_SKILLS = [
    ("MetricContractResolver", "deterministic"),
    ("SchemaProfiler", "tool"),
    ("DataQualityGate", "deterministic"),
    ("ReadOnlyQueryPlanner", "tool"),
    ("FunnelDecomposer", "statistics"),
    ("ProductMixDecomposer", "statistics"),
    ("SegmentProfiler", "statistics"),
    ("EventAligner", "statistics"),
    ("ExperimentIntegrityGate", "deterministic+statistics"),
    ("CausalReadinessCheck", "deterministic"),
    ("ExperimentPlanner", "model+template"),
    ("ExperimentMonitor", "tool+statistics"),
    ("ClaimPolicyGuard", "deterministic"),
    ("WeeklyBriefComposer", "model+template"),
]


def build_control_plane() -> AgentTeamsControlPlane:
    control_plane = AgentTeamsControlPlane()
    for agent_id, role, states, capabilities, can_write, can_call in CASE_AGENTS:
        control_plane.register_agent(
            AgentIdentity(agent_id, role, states, capabilities, can_write, can_call)
        )
    for skill_id, executor in CASE_SKILLS:
        control_plane.register_skill(
            skill_id,
            {
                "skill_id": skill_id,
                "version": "0.1.0",
                "executor": executor,
                "schema_version": "1.0",
                "policy": {
                    "requires_metric_contract": True,
                    "requires_claim_ledger": True,
                },
            },
        )
    control_plane.register_topology(
        TeamTopology(
            "insurance-growth-team",
            "AgentTeamsControlPlane",
            list(control_plane.agents.keys()),
            [
                {"from": "intent", "to": "metric_contract", "mode": "sequential"},
                {
                    "from": "metric_contract",
                    "to": "data_acquisition",
                    "mode": "contract-gated",
                },
                {"from": "data_acquisition", "to": "diagnostic", "mode": "read-only"},
                {
                    "from": "diagnostic",
                    "to": "causal_evidence",
                    "mode": "fan-in",
                    "input": "funnel+mix+segment artifacts",
                },
                {
                    "from": "causal_evidence",
                    "to": "experiment_planner",
                    "mode": "evidence-gated",
                },
                {
                    "from": "experiment_planner",
                    "to": "monitor_review",
                    "mode": "approval-gated",
                },
            ],
            {
                "fan_out": [
                    "diagnostic -> funnel, product_mix, segment, event_alignment skills"
                ],
                "fan_in": "causal_evidence consumes typed diagnostic artifacts",
                "conflict_policy": "ClaimPolicyGuard is deterministic and can block model output",
            },
        )
    )
    return control_plane


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _rate(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def generate_dataset(
    case: str, seed: int = 42, n: int = 1200, baseline: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate user-level observations and hidden structural truth.

    Rates use bounded logistic links. Case C exposes a randomized assignment;
    cases A and B intentionally use confounded observational assignment.
    """
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    truth: dict[str, Any] = {
        "case": case,
        "seed": seed,
        "assignment": "fixed-control" if baseline else "unknown",
    }
    randomization_block: list[int] = []
    for index in range(n):
        season = rng.choice([0.0, 0.05, -0.04, 0.08])
        user_quality = max(-2.0, min(2.0, rng.gauss(0.0, 0.9)))
        channel_quality = max(-2.0, min(2.0, rng.gauss(0.0, 0.65)))
        channel = "new" if channel_quality > 0.35 and not baseline else "owned"
        if case == "C" and not baseline:
            if not randomization_block:
                randomization_block = [0, 1]
                rng.shuffle(randomization_block)
            treatment = randomization_block.pop()
            assignment = "randomized"
        elif baseline:
            treatment = 0
            assignment = "fixed-control"
        else:
            treatment = 1 if channel == "new" else 0
            assignment = "observational-confounded"
        product_mix = 0.25 + 0.12 * (channel_quality > 0.4) + rng.random() * 0.25
        p_quote = _sigmoid(
            -0.25
            + 0.72 * user_quality
            + 0.28 * channel_quality
            + season
            - 0.35 * product_mix
        )
        quoted = 1 if rng.random() < p_quote else 0
        apply_uniform = rng.random()
        p_apply_control = _sigmoid(-0.55 + 0.65 * user_quality + 0.18 * channel_quality)
        p_apply_treatment = _sigmoid(
            -0.55 + 0.65 * user_quality + 0.18 * channel_quality + 0.12
        )
        applied_control = 1 if quoted and apply_uniform < p_apply_control else 0
        applied_treatment = 1 if quoted and apply_uniform < p_apply_treatment else 0
        paid_uniform = rng.random()
        p_paid_control = _sigmoid(-0.35 + 0.8 * user_quality - 0.12 * product_mix)
        p_paid_treatment = _sigmoid(
            -0.35 + 0.8 * user_quality + 0.2 - 0.12 * product_mix
        )
        paid_control = 1 if applied_control and paid_uniform < p_paid_control else 0
        paid_treatment = (
            1 if applied_treatment and paid_uniform < p_paid_treatment else 0
        )
        base_issue_logit = (
            -0.2 + 0.62 * user_quality + 0.2 * channel_quality + 0.1 * season
        )
        p_issue_control = _sigmoid(base_issue_logit)
        p_issue_treatment = _sigmoid(base_issue_logit + 0.28)
        issue_uniform = rng.random()
        issued_control = 1 if paid_control and issue_uniform < p_issue_control else 0
        issued_treatment = (
            1 if paid_treatment and issue_uniform < p_issue_treatment else 0
        )
        applied = applied_treatment if treatment else applied_control
        paid = paid_treatment if treatment else paid_control
        issued = issued_treatment if treatment else issued_control
        premium_if_issued = round(
            max(300.0, 850.0 + 220.0 * product_mix + rng.gauss(0.0, 55.0)), 2
        )
        refund_rate = 0.04 if rng.random() < 0.06 else 0.0
        cancel_rate = 0.05 if rng.random() < 0.03 else 0.0
        potential_net_control = round(
            premium_if_issued * issued_control * (1.0 - refund_rate - cancel_rate), 2
        )
        potential_net_treatment = round(
            premium_if_issued * issued_treatment * (1.0 - refund_rate - cancel_rate), 2
        )
        gross_premium = premium_if_issued if issued else 0.0
        refund = round(gross_premium * refund_rate, 2)
        cancel = round(gross_premium * cancel_rate, 2)
        rows.append(
            {
                "user_id": f"u{index:04d}",
                "active": 1,
                "season": season,
                "channel": channel,
                "channel_quality": round(channel_quality, 4),
                "user_quality": round(user_quality, 4),
                "product_mix": round(product_mix, 4),
                "treatment": treatment,
                "assigned_treatment": treatment,
                "exposed_treatment": treatment,
                "exposed": 1,
                "triggered": 1,
                "outcome_observed": 1,
                "assigned_at": index * 3,
                "exposed_at": index * 3 + 1,
                "outcome_observed_at": index * 3 + 2,
                "assignment_period": index // 200,
                "concurrent_experiment_ids": [],
                "assignment": assignment,
                "quoted": quoted,
                "applied": applied,
                "paid": paid,
                "issued": issued,
                "gross_premium": gross_premium,
                "refund": refund,
                "cancel": cancel,
                "net_premium": round(gross_premium - refund - cancel, 2),
                "_potential_issued_control": issued_control,
                "_potential_issued_treatment": issued_treatment,
                "_potential_net_premium_control": potential_net_control,
                "_potential_net_premium_treatment": potential_net_treatment,
            }
        )
    truth.update(
        {
            "estimand": "ATE/ITT on issued and net_premium under randomized assignment",
            "treatment_effect_logit": 0.28,
            "assignment": "randomized"
            if case == "C" and not baseline
            else ("fixed-control" if baseline else "observational-confounded"),
            "oracle_ate": {
                "issued": round(
                    sum(
                        row["_potential_issued_treatment"]
                        - row["_potential_issued_control"]
                        for row in rows
                    )
                    / len(rows),
                    6,
                )
                if rows
                else 0.0,
                "net_premium": round(
                    sum(
                        row["_potential_net_premium_treatment"]
                        - row["_potential_net_premium_control"]
                        for row in rows
                    )
                    / len(rows),
                    6,
                )
                if rows
                else 0.0,
            },
        }
    )
    return rows, truth


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return aggregate_funnel(rows)


def log_chain_decomposition(
    baseline_metrics: dict[str, Any], current_metrics: dict[str, Any]
) -> dict[str, Any]:
    factors = [
        ("active", "活跃流量"),
        ("quote_rate", "报价率"),
        ("apply_rate", "投保率"),
        ("paid_rate", "支付率"),
        ("issue_rate", "出单率"),
        ("avg_premium", "件均保费"),
    ]
    contributions = []
    total_log_change = 0.0
    for key, label in factors:
        before = max(float(baseline_metrics.get(key, 0.0)), 1e-9)
        after = max(float(current_metrics.get(key, 0.0)), 1e-9)
        change = math.log(after / before)
        total_log_change += change
        contributions.append(
            {
                "key": key,
                "label": label,
                "before": baseline_metrics.get(key, 0.0),
                "after": current_metrics.get(key, 0.0),
                "log_change": round(change, 6),
            }
        )
    for item in contributions:
        item["share"] = (
            round(item["log_change"] / total_log_change, 6) if total_log_change else 0.0
        )
    return {
        "method": "fixed-order log-chain decomposition",
        "baseline_premium": baseline_metrics["net_premium"],
        "current_premium": current_metrics["net_premium"],
        "total_log_change": round(total_log_change, 6),
        "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
        "unexplained_residual": 0.0,
        "factors": contributions,
    }


def estimate_case_c(
    rows: list[dict[str, Any]], integrity_report: Mapping[str, Any]
) -> dict[str, Any]:
    return estimate_itt(rows, integrity_report=integrity_report)


def _claim(
    case: str, readiness: dict[str, Any], decomposition: dict[str, Any]
) -> dict[str, Any]:
    return build_claim(readiness)


def default_metric_contract() -> dict[str, Any]:
    return {
        "metric_id": "insurance-premium-v2",
        "version": "2026-07-31",
        "identity": "user_id",
        "funnel": ["active", "quoted", "applied", "paid", "issued"],
        "outcomes": ["issued", "net_premium"],
        "treatment": "treatment",
        "premium": "net premium after refund and cancellation",
        "window": "7d",
        "owner": "growth-analytics",
    }


def case_experiment_metadata(case: str) -> dict[str, Any]:
    common: dict[str, Any] = {
        "treatment_column": "treatment",
        "window_closed": True,
        "outcome_complete": True,
        "minimum_detectable_effect": 0.05,
        "minimum_detectable_effect_type": "absolute",
        "alpha": 0.05,
        "target_power": 0.80,
        "power_design": "superiority",
        "test_sidedness": "two_sided",
        "expected_attrition_rate": 0.0,
        "approval_required": True,
        "guardrails": ["refund_rate", "cancel_rate", "privacy_policy"],
        "stop_rule": "guardrail breach or final observation window",
        "production_auto_action": False,
        "primary_estimand": "user_level",
        "analysis_unit": "user_id",
        "outcome_aggregations": {"issued": "max", "net_premium": "sum"},
        "assigned_arm_column": "assigned_treatment",
        "exposed_arm_column": "exposed_treatment",
        "exposure_column": "exposed",
        "triggered_column": "triggered",
        "outcome_observed_column": "outcome_observed",
        "assigned_at_column": "assigned_at",
        "exposed_at_column": "exposed_at",
        "outcome_at_column": "outcome_observed_at",
        "assignment_period_column": "assignment_period",
        "concurrent_experiments_column": "concurrent_experiment_ids",
        "expected_allocation": {"0": 0.5, "1": 0.5},
        "baseline_covariates": [
            "season",
            "user_quality",
            "channel_quality",
            "product_mix",
        ],
        "srm_alpha": 0.001,
        "balance_smd_threshold": 0.10,
        "balance_proportion_difference_threshold": 0.10,
        "allocation_stability_tolerance": 0.10,
        "allocation_stability_min_period_size": 30,
        "max_contamination_rate": 0.001,
        "max_funnel_rate_difference": 0.05,
        "compatible_concurrent_experiments": [],
    }
    if case == "A":
        common.update(
            {
                "experiment_id": "observational-ranking-change-A",
                "activity_config": "ranking-v2-observed",
                "assignment_method": "observational",
                "assignment_provenance": "event_log",
                "assignment_verified": False,
                "randomization_unit": "user_id",
                "control_group": 0,
                "treatment_group": 1,
            }
        )
    elif case == "B":
        common.update(
            {
                "experiment_id": None,
                "activity_config": None,
                "assignment_method": None,
                "assignment_provenance": None,
                "assignment_verified": None,
                "randomization_unit": None,
                "control_group": None,
                "treatment_group": None,
                "window_closed": False,
                "outcome_complete": False,
            }
        )
    elif case == "C":
        common.update(
            {
                "experiment_id": "randomized-ranking-C",
                "activity_config": "ranking-v2-randomized",
                "assignment_method": "randomized",
                "assignment_provenance": "experiment_platform",
                "assignment_verified": True,
                "randomization_unit": "user_id",
                "control_group": 0,
                "treatment_group": 1,
            }
        )
    else:
        raise ValueError("case must be A, B or C")
    return common


def run_case(base_dir: Path, case: str = "A") -> dict[str, Any]:
    if case not in {"A", "B", "C"}:
        raise ValueError("case must be A, B or C")
    control_plane = build_control_plane()
    checkpoint = SQLiteCheckpointProvider(
        base_dir / "checkpoints" / "attribution.sqlite3"
    )
    evidence_provider = LocalEvidenceProvider(base_dir / "evidence")
    task_id = f"T2-case-{case}"
    task = control_plane.create_task(
        task_id,
        "insurance-growth-attribution",
        {
            "case": case,
            "question": "DAU rose while premium declined; explain what is known and what should be tested.",
        },
    )

    def move(
        target: str,
        actor: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        control_plane.transition(task_id, target, actor, reason, metadata)
        current = control_plane.tasks[task_id]
        checkpoint.save(
            task_id, current.state_version, control_plane.checkpoint_payload(task_id)
        )

    def evidence(kind: str, label: str, source: str, content: Any) -> str:
        return control_plane.record_evidence(
            task_id, kind, label, source, content
        ).evidence_id

    private_rows, truth = generate_dataset(case, seed=42 if case != "C" else 84, n=1200)
    private_baseline_rows, _ = generate_dataset(
        case, seed=41 if case != "C" else 83, n=1200, baseline=True
    )
    rows = sanitize_rows(private_rows)
    baseline_rows = sanitize_rows(private_baseline_rows)
    current_metrics = aggregate(rows)
    baseline_metrics = aggregate(baseline_rows)
    metric_contract = default_metric_contract()
    experiment_metadata = case_experiment_metadata(case)
    feature_set = extract_features(rows, metric_contract, experiment_metadata)
    readiness = causal_readiness(feature_set, metric_contract, experiment_metadata)
    input_ev = evidence(
        "metric-contract",
        "versioned insurance metric contract",
        "metric_contract",
        metric_contract,
    )
    move(
        "INTENT_PARSED",
        "intent",
        "business question normalized",
        {"evidence_ref": input_ev},
    )
    control_plane.publish_artifact(
        task_id,
        "AnalysisIntent",
        "intent",
        {
            "question": task.input_payload["question"],
            "target": "premium growth and conversion",
            "unit": "user_id",
        },
        [input_ev],
    )
    move("METRIC_CONFIRMED", "metric_contract", "metric version accepted")
    control_plane.publish_artifact(
        task_id, "MetricContract", "metric_contract", metric_contract, [input_ev]
    )
    quality_features = feature_set["data_quality"]
    data_quality = {
        "freshness": "simulated-current",
        "privacy": "aggregated-demo-only",
        **quality_features,
        "missing_fields": sorted(
            set(
                quality_features["missing_row_fields"]
                + quality_features["missing_experiment_fields"]
            )
        ),
    }
    data_ev = evidence(
        "data-quality",
        "schema and data quality report",
        "data_acquisition",
        data_quality,
    )
    move(
        "DATA_VALIDATED",
        "data_acquisition",
        "read-only dataset passed schema checks",
        {"evidence_ref": data_ev},
    )
    control_plane.publish_artifact(
        task_id, "DataQualityReport", "data_acquisition", data_quality, [data_ev]
    )
    feature_ev = evidence(
        "feature-set",
        "deterministic funnel, segment and treatment features",
        "diagnostic",
        feature_set,
    )
    control_plane.publish_artifact(
        task_id, "FeatureSet", "diagnostic", feature_set, [data_ev, feature_ev]
    )
    if readiness["outcome"] == "DATA_INSUFFICIENT":
        move(
            "DATA_INSUFFICIENT",
            "data_acquisition",
            "required experiment evidence is missing",
            {"missing_evidence": readiness["diagnostics"]["missing_evidence"]},
        )
    else:
        move(
            "DIAGNOSING",
            "diagnostic",
            "funnel and product structure decomposition is available",
        )
    decomposition = log_chain_decomposition(baseline_metrics, current_metrics)
    decomposition_ev = evidence(
        "analysis", "fixed-order log-chain decomposition", "diagnostic", decomposition
    )
    control_plane.publish_artifact(
        task_id,
        "AttributionCandidateSet",
        "diagnostic",
        {
            "metrics": current_metrics,
            "features": feature_set["segments"],
            "decomposition": decomposition,
            "interpretation": "structural contribution only",
        },
        [feature_ev, decomposition_ev],
    )
    if readiness["outcome"] != "DATA_INSUFFICIENT":
        move(
            "EVIDENCE_GRADED",
            "causal_evidence",
            "candidate causes are separated from causal claims",
        )
    readiness_ev = evidence(
        "causal-readiness",
        "row-level experiment integrity and causal-readiness check",
        "causal_evidence",
        readiness,
    )
    control_plane.publish_artifact(
        task_id,
        "EvidenceReport",
        "causal_evidence",
        readiness,
        [data_ev, feature_ev, readiness_ev],
    )
    if readiness["outcome"] == "DATA_INSUFFICIENT":
        move(
            "DESCRIPTIVE_ONLY",
            "causal_evidence",
            "required experiment metadata is absent",
            {"reason_codes": readiness["reason_codes"]},
        )
    elif readiness["outcome"] == "DESCRIPTIVE_ONLY":
        move(
            "DESCRIPTIVE_ONLY",
            "causal_evidence",
            "observable design evidence does not identify an effect",
            {"reason_codes": readiness["reason_codes"]},
        )
    claim = _claim(case, readiness, decomposition)
    claim_ev = evidence(
        "claim-ledger",
        "structured claim and prohibited actions",
        "causal_evidence",
        claim,
    )
    control_plane.publish_artifact(
        task_id, "ClaimLedger", "causal_evidence", claim, [claim_ev]
    )
    if readiness["outcome"] != "DATA_INSUFFICIENT":
        experiment = {
            "experiment_id": experiment_metadata["experiment_id"],
            "treatment": "new ranking",
            "unit": "user_id",
            "randomization": experiment_metadata["assignment_method"],
            "primary_metric": "issued",
            "guardrails": experiment_metadata["guardrails"],
            "stop_rule": experiment_metadata["stop_rule"],
            "approval": "required",
        }
        experiment_ev = evidence(
            "experiment", "bounded experiment draft", "experiment_planner", experiment
        )
        control_plane.publish_artifact(
            task_id, "ExperimentSpec", "experiment_planner", experiment, [experiment_ev]
        )
    if readiness["outcome"] == "CAUSAL_READY":
        move(
            "ACTION_DRAFTED",
            "experiment_planner",
            "causal-ready evidence permits an experiment draft",
        )
        move(
            "COMPLIANCE_REVIEWED",
            "causal_evidence",
            "claim and privacy guardrails pass",
        )
        approval_id = control_plane.request_approval(
            task_id,
            "experiment_planner",
            {
                "experiment_id": experiment_metadata["experiment_id"],
                "scope": "synthetic dataset only",
            },
        )
        move(
            "AWAITING_APPROVAL",
            "experiment_planner",
            "experiment requires explicit human approval",
            {"approval_id": approval_id},
        )
        control_plane.approve(
            approval_id, "human-reviewer", "APPROVED", "synthetic demo only"
        )
        move("MONITORING", "monitor_review", "approved experiment enters monitoring")
        estimate = estimate_case_c(rows, feature_set["experiment_integrity"])
        monitor_ev = evidence(
            "monitoring",
            "ITT estimate and confidence intervals",
            "monitor_review",
            estimate,
        )
        control_plane.publish_artifact(
            task_id, "MonitoringReport", "monitor_review", estimate, [monitor_ev]
        )
        move("REVIEWED", "monitor_review", "monitoring report completed")
    elif readiness["outcome"] == "DESCRIPTIVE_ONLY":
        move(
            "ACTION_DRAFTED",
            "experiment_planner",
            "only a pre-experiment draft is permitted",
        )
        move(
            "COMPLIANCE_REVIEWED",
            "causal_evidence",
            "descriptive-only claim policy passes",
        )
        approval_id = control_plane.request_approval(
            task_id,
            "experiment_planner",
            {
                "experiment_id": experiment_metadata["experiment_id"],
                "scope": "draft only; no production change",
            },
        )
        move(
            "AWAITING_APPROVAL",
            "experiment_planner",
            "draft still requires explicit human approval",
            {"approval_id": approval_id},
        )
        control_plane.approve(
            approval_id,
            "human-reviewer",
            "APPROVED",
            "draft approved for synthetic monitoring only",
        )
        move(
            "MONITORING",
            "monitor_review",
            "approved draft enters a non-production monitoring state",
        )
        pending_monitor_ev = evidence(
            "monitoring",
            "pre-experiment monitoring placeholder",
            "monitor_review",
            {
                "status": "waiting for a real randomized window",
                "claim_policy": "descriptive-only",
            },
        )
        control_plane.publish_artifact(
            task_id,
            "MonitoringReport",
            "monitor_review",
            {"status": "waiting_for_real_randomized_window", "causal_estimate": None},
            [pending_monitor_ev],
        )
        move(
            "REVIEWED",
            "monitor_review",
            "descriptive case reviewed without causal overclaim",
        )
    else:
        move("CLOSED", "causal_evidence", "closed with safe refusal and补数路径")
    if control_plane.tasks[task_id].state != "CLOSED":
        move("CLOSED", "monitor_review", "evidence pack finalized")
    pack = control_plane.evidence_pack(task_id)
    pack.update(
        {
            "pipeline": "causal-readiness",
            "case": case,
            "agents": list(control_plane.agents.keys()),
            "skills": list(control_plane.skills.keys()),
            "metric_contract": metric_contract,
            "experiment_metadata": experiment_metadata,
            "experiment_integrity": feature_set["experiment_integrity"],
            "feature_set": feature_set,
            "metrics": {"baseline": baseline_metrics, "current": current_metrics},
            "decomposition": decomposition,
            "causal_readiness": readiness,
            "claim": claim,
            "sample": rows[:3],
            "truth": truth,
            "checkpoint": checkpoint.load(task_id),
            "summary": {
                "final_state": control_plane.tasks[task_id].state,
                "claim_type": claim["claim_type"],
                "evidence_level": claim["evidence_level"],
                "causal_outcome": readiness["outcome"],
            },
        }
    )
    if readiness["outcome"] == "CAUSAL_READY":
        pack["estimate"] = estimate_case_c(rows, feature_set["experiment_integrity"])
    pack_path = evidence_provider.write_pack(task_id, pack)
    pack["evidence_pack_path"] = str(pack_path)
    return pack


def public_case(pack: dict[str, Any]) -> dict[str, Any]:
    """Remove hidden structural truth before exposing a case to the UI."""
    result = dict(pack)
    result.pop("truth", None)
    return result
