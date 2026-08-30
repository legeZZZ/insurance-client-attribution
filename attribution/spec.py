"""Growth UI Spec loading and the three diff extractors (Spec/Render/Runtime).

Specs are JSON documents following the Growth UI Spec shape from the v5 plan
(anatomy / props / states / behaviors / constraints / telemetry / experiment /
causal_roles). Diffs produce candidate factors with a full provenance chain.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_spec(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    if "component" not in spec or "props" not in spec:
        raise ValueError("spec must contain component and props")
    return spec


def _factor_entry(
    factor_id: str,
    source_type: str,
    source_path: str,
    before: Any,
    after: Any,
    component: str,
    causal_role: str,
    experimentability: float,
) -> dict[str, Any]:
    return {
        "factor_id": factor_id,
        "source_type": source_type,
        "source_path": source_path,
        "before": before,
        "after": after,
        "component": component,
        "causal_role": causal_role,
        "experimentability": experimentability,
        "claim_type": "FACTOR_CANDIDATE",
    }


def spec_diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Diff two Growth UI Specs into SPEC_DIFF candidate factors."""
    component = str(new.get("component", {}).get("name", "component")).lower()
    causal_roles = new.get("causal_roles", {})
    role_of: dict[str, str] = {}
    for role, factor_ids in causal_roles.items():
        for factor_id in factor_ids:
            role_of[str(factor_id)] = role

    factors: list[dict[str, Any]] = []
    old_props = old.get("props", {})
    new_props = new.get("props", {})
    for name in sorted(set(old_props) | set(new_props)):
        before = old_props.get(name, {}).get("default")
        after = new_props.get(name, {}).get("default")
        if before == after and name in old_props and name in new_props:
            continue
        prop_meta = new_props.get(name, {})
        experiment_meta = prop_meta.get("experiment", {})
        factor_id = experiment_meta.get("factor_id", f"{component}.{name}")
        factors.append(_factor_entry(
            factor_id=factor_id,
            source_type="SPEC_DIFF",
            source_path=f"props.{name}.default",
            before=before,
            after=after,
            component=component,
            causal_role=role_of.get(factor_id, "treatment_candidate"),
            experimentability=1.0 if experiment_meta.get("randomizable") else 0.3,
        ))
    return factors


def render_diff(
    old_snapshot: Mapping[str, Any],
    new_snapshot: Mapping[str, Any],
    component: str = "carousel",
) -> list[dict[str, Any]]:
    """Diff two render snapshots (geometry/density metrics) into RENDER_DIFF factors.

    Snapshots map metric name -> float, e.g. text_area_ratio, contrast_ratio.
    A metric becomes a candidate when it changes by >= 10% relative or 0.02 absolute.
    """
    factors: list[dict[str, Any]] = []
    for name in sorted(set(old_snapshot) | set(new_snapshot)):
        before = old_snapshot.get(name)
        after = new_snapshot.get(name)
        if before is None or after is None:
            continue
        delta = abs(after - before)
        if delta < 0.02 and (before == 0 or delta / abs(before) < 0.10):
            continue
        factors.append(_factor_entry(
            factor_id=f"{component}.{name}",
            source_type="RENDER_DIFF",
            source_path=f"render.{name}",
            before=before,
            after=after,
            component=component,
            causal_role="treatment_candidate",
            experimentability=0.6,
        ))
    return factors


def runtime_diff(
    control_metrics: Mapping[str, Any],
    treatment_metrics: Mapping[str, Any],
    component: str = "carousel",
    relative_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """Diff runtime quality metrics between arms into RUNTIME_DIFF factors.

    Runtime factors are mediators/runtime_quality candidates and must never be
    mixed with visual style factors in one claim.
    """
    factors: list[dict[str, Any]] = []
    for name in sorted(set(control_metrics) | set(treatment_metrics)):
        before = control_metrics.get(name)
        after = treatment_metrics.get(name)
        if before is None or after is None:
            continue
        base = abs(before) if before else 1e-9
        if abs(after - before) / base < relative_threshold:
            continue
        factors.append(_factor_entry(
            factor_id=f"{component}.{name}",
            source_type="RUNTIME_DIFF",
            source_path=f"runtime.{name}",
            before=before,
            after=after,
            component=component,
            causal_role="runtime_quality",
            experimentability=0.4,
        ))
    return factors
