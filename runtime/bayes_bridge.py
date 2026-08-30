"""Bridge between the v3 causal-governance runtime and the attribution Bayesian layer.

v3 decides *whether* a causal claim is allowed (five-layer gate); the v5
Bayesian layer then decides *what to do* with an estimable effect
(rollback / ship / equivalence / continue) and how effect heterogeneity
should be shrunk. This module wires them together without changing any
v3 behavior: the hidden benchmark and all v3 metrics stay untouched.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# attribution lives at the workspace root, one level above this bundle.
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from attribution.baseline_attribution import (
    attribute_baseline,
    change_registry_entry,
    external_event_entry,
    run_validation,
    simulate_panel,
)
from attribution.bayes import bundle_compare, estimate_hte

from .analysis import evaluate_public_dataset, sanitize_rows


def run_line_b_monthly_review(runtime_dir=None) -> dict[str, Any]:
    """Line B monthly review: baseline attribution + registries -> evidence pack.

    Produces a v3-style evidence pack JSON so the console / Evidence drawer
    can consume the baseline-attribution layer through the same channel as
    case A/B/C evidence.
    """
    panel = simulate_panel()
    registry = [
        change_registry_entry("chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"),
        change_registry_entry("chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"),
    ]
    external = [external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")]
    demo = attribute_baseline(
        panel["days"], panel["control"], panel["treated"],
        registry, external, panel["experiments"],
    )
    pack = {
        "task_id": "T2-lineB-monthly-review",
        "domain": "insurance-growth-attribution",
        "schema_version": "1.0",
        "view": "monthly_baseline_attribution",
        "baseline_definition": demo["baseline_definition"],
        "change_registry": registry,
        "external_factor_registry": external,
        "att_aggregation": demo["att_aggregation"],
        "external_associations": demo["external_associations"],
        "unregistered_alerts": demo["unregistered_alerts"],
        "unknown_bucket": demo["unknown_bucket"],
        "claim_types_used": ["BUNDLE_EFFECT", "TEMPORAL_ASSOCIATION", "UNEXPLAINED"],
        "governance_note": "外部因子恒为时序关联；残差标未知不摊派；未注册变更触发治理告警。",
        "validation": run_validation(),
    }
    if runtime_dir is not None:
        evidence_dir = runtime_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path = evidence_dir / "T2-lineB-monthly-review.json"
        import json as _json
        path.write_text(_json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
        pack["evidence_pack_path"] = str(path)
    return pack


def _binary_group(rows, treatment_column, outcome, arm):
    group = [row for row in rows if row.get(treatment_column) == arm]
    return {
        "clicks": sum(int(float(row.get(outcome, 0) or 0)) for row in group),
        "impressions": len(group),
    }


def evaluate_with_bayes(
    bundle: Mapping[str, Any],
    practical_threshold: float = 0.005,
    hte_segment_field: str | None = None,
    seed: int = 20260809,
) -> dict[str, Any]:
    """v3 evaluation + Bayesian decision layer for CAUSAL_READY datasets.

    - If the v3 gate is not CAUSAL_READY, the Bayesian layer refuses to
      issue any decision (evidence discipline is inherited, not bypassed).
    - If CAUSAL_READY, the binary primary outcome gets a Beta-Binomial
      posterior with the four-state decision guard, and optional segment
      HTE with partial pooling.
    """
    base = evaluate_public_dataset(bundle)
    result = dict(base)
    if base["causal_readiness"]["outcome"] != "CAUSAL_READY":
        result["bayes_layer"] = {
            "status": "REFUSED",
            "reason": "v3 causal gate did not pass; Bayesian decision layer inherits the refusal.",
        }
        return result

    rows = sanitize_rows(bundle.get("rows", []))
    experiment_metadata = dict(bundle.get("experiment_metadata", {}))
    treatment_column = str(experiment_metadata.get("treatment_column") or "treatment")
    control = _binary_group(rows, treatment_column, "issued", 0)
    treatment = _binary_group(rows, treatment_column, "issued", 1)
    bundle_result = bundle_compare(
        control, treatment, practical_threshold=practical_threshold, seed=seed)
    bayes_layer: dict[str, Any] = {
        "status": "ACTIVE",
        "bundle_decision": bundle_result,
        "decision_rule": {
            "rollback": "P(effect < -delta) >= 0.95",
            "ship": "P(effect > delta) >= 0.95",
            "equivalent": "P(|effect| <= delta) >= 0.90",
            "delta": practical_threshold,
        },
    }

    if hte_segment_field and any(hte_segment_field in row for row in rows):
        segments = []
        for value in sorted({str(row.get(hte_segment_field)) for row in rows}):
            subset = [row for row in rows if str(row.get(hte_segment_field)) == value]
            segments.append({
                "segment_id": f"{hte_segment_field}={value}",
                "control": _binary_group(subset, treatment_column, "issued", 0),
                "treatment": _binary_group(subset, treatment_column, "issued", 1),
            })
        bayes_layer["hte"] = estimate_hte(
            segments, practical_threshold=practical_threshold, seed=seed)

    result["bayes_layer"] = bayes_layer
    return result
