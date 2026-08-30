"""FactorMiner: open candidate discovery layer.

Generates four candidate classes (change / distribution / interaction /
runtime), scores them, and emits FACTOR_CANDIDATE claims only. It never
asserts causation.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .bayes import moderation_scan
from .spec import render_diff, runtime_diff, spec_diff


def _psi(baseline: Counter, current: Counter) -> float:
    keys = set(baseline) | set(current)
    total_b = sum(baseline.values()) or 1
    total_c = sum(current.values()) or 1
    value = 0.0
    for key in keys:
        pb = max(baseline.get(key, 0) / total_b, 1e-4)
        pc = max(current.get(key, 0) / total_c, 1e-4)
        value += (pc - pb) * math.log(pc / pb)
    return value


def mine_factors(
    rows_baseline: Sequence[Mapping[str, Any]],
    rows_current: Sequence[Mapping[str, Any]],
    treatment_column: str,
    outcome_column: str,
    context_fields: Sequence[str],
    spec_old: Mapping[str, Any] | None = None,
    spec_new: Mapping[str, Any] | None = None,
    render_old: Mapping[str, Any] | None = None,
    render_new: Mapping[str, Any] | None = None,
    runtime_control: Mapping[str, Any] | None = None,
    runtime_treatment: Mapping[str, Any] | None = None,
    discovery: bool = True,
    practical_threshold: float = 0.005,
    seed: int = 20260809,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    # 1) Change candidates from the three diffs.
    if spec_old is not None and spec_new is not None:
        candidates.extend(spec_diff(spec_old, spec_new))
    if render_old is not None and render_new is not None:
        candidates.extend(render_diff(render_old, render_new))
    if runtime_control is not None and runtime_treatment is not None:
        candidates.extend(runtime_diff(runtime_control, runtime_treatment))

    # 2) Distribution candidates: PSI drift on context fields.
    for field in context_fields:
        drift = _psi(
            Counter(str(r.get(field, "<missing>")) for r in rows_baseline),
            Counter(str(r.get(field, "<missing>")) for r in rows_current),
        )
        if drift >= 0.1:
            candidates.append({
                "factor_id": f"context.{field}",
                "source_type": "DISTRIBUTION_DRIFT",
                "source_path": field,
                "psi": drift,
                "component": "context",
                "causal_role": "confounder_candidate",
                "experimentability": 0.0,
                "claim_type": "FACTOR_CANDIDATE",
            })

    # 3) Interaction candidates: moderation scan on current rows.
    interactions = moderation_scan(
        rows_current, treatment_column, outcome_column, context_fields,
        practical_threshold=practical_threshold, seed=seed, discovery=discovery,
    )
    for item in interactions:
        if abs(item["moderation"]) < practical_threshold:
            continue
        candidates.append({
            "factor_id": f"interaction.{item['factor_id']}={item['factor_value']}",
            "source_type": "INTERACTION_SCAN",
            "source_path": item["factor_id"],
            "moderation": item["moderation"],
            "probability_practical_harm": item["probability_practical_harm"],
            "probability_practical_benefit": item.get("probability_practical_benefit", 0.0),
            "impressions": item["impressions"],
            "component": "context",
            "causal_role": "moderator_candidate",
            "experimentability": 0.0,
            "association_score": abs(item["moderation_score"]),
            "claim_type": "FACTOR_CANDIDATE",
        })

    # 4) Priority scoring: impact x evidence x experimentability / cost proxy.
    def priority(factor: Mapping[str, Any]) -> float:
        if factor["source_type"] == "INTERACTION_SCAN":
            evidence_prob = max(
                float(factor.get("probability_practical_harm", 0.0)),
                float(factor.get("probability_practical_benefit", 0.0)),
            )
            impact = abs(factor.get("moderation", 0.0)) * evidence_prob
            evidence = min(factor.get("impressions", 0) / 2000.0, 1.0)
        elif factor["source_type"] == "DISTRIBUTION_DRIFT":
            impact = min(factor.get("psi", 0.0), 1.0)
            evidence = 0.6
        else:
            before, after = factor.get("before"), factor.get("after")
            try:
                impact = min(abs(float(after) - float(before)), 1.0)
            except (TypeError, ValueError):
                impact = 0.8  # categorical change
            evidence = 0.9
        experimentability = float(factor.get("experimentability", 0.0))
        business_value = 1.0
        cost = 1.0
        return impact * evidence * (0.5 + experimentability) * business_value / cost

    for factor in candidates:
        factor["priority"] = round(priority(factor), 6)

    ranked = sorted(candidates, key=lambda item: item["priority"], reverse=True)
    return {
        "claim_type": "FACTOR_CANDIDATE",
        "candidate_count": len(ranked),
        "candidates": ranked,
        "discovery_mode": discovery,
        "note": "FactorMiner emits candidates only; causal claims require randomized promotion gates.",
    }
