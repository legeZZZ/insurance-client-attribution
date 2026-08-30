"""Governed experiment-platform adapter.

The default implementation is an in-memory dry run.  A production adapter
must implement the same methods and preserve approval, assignment and metric
provenance fields before any traffic-changing operation is enabled.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


class DryRunExperimentPlatform:
    def __init__(
        self, *, dry_run: bool = True, metric_fixture: Mapping[str, Any] | None = None
    ) -> None:
        self.dry_run = bool(dry_run)
        self.metric_fixture = dict(
            metric_fixture
            or {
                "control": {"clicks": 250, "impressions": 10000},
                "treatment": {"clicks": 215, "impressions": 10000},
                "guardrails": {
                    "error_rate": {"value": 0.021, "limit": 0.010},
                    "latency_p95_ms": {"value": 180, "limit": 250},
                },
            }
        )
        self.experiments: dict[str, dict[str, Any]] = {}

    def validate_spec(
        self, spec: Mapping[str, Any], metric_contract: Mapping[str, Any]
    ) -> dict[str, Any]:
        required = ("template_id", "metric", "factors")
        missing = [key for key in required if not spec.get(key)]
        contract_missing = [
            key for key in ("name", "unit") if not metric_contract.get(key)
        ]
        valid = (
            not missing
            and not contract_missing
            and bool(spec.get("stable_randomization_unit"))
        )
        return {
            "valid": valid,
            "missing_spec_fields": missing,
            "missing_metric_fields": contract_missing,
            "reason": None if valid else "experiment_contract_incomplete",
        }

    def create_experiment(
        self, design: Mapping[str, Any], approval_ref: str
    ) -> dict[str, Any]:
        validation = self.validate_spec(design, design.get("metric_contract", {}))
        if not validation["valid"]:
            raise ValueError(f"invalid experiment spec: {validation}")
        if not approval_ref:
            raise PermissionError("approval_ref is required")
        experiment_id = str(
            design.get("experiment_id", f"exp-{len(self.experiments) + 1:03d}")
        )
        record = {
            "experiment_id": experiment_id,
            "status": "CREATED",
            "platform_mode": "dry_run" if self.dry_run else "connected",
            "assignment_provenance": "dry_run_experiment_platform"
            if self.dry_run
            else "platform",
            "stable_randomization_unit": design["stable_randomization_unit"],
            "approval_ref": approval_ref,
            "design_digest": _digest(design),
            "traffic_percent": 0,
        }
        self.experiments[experiment_id] = record
        return dict(record)

    def start_canary(self, experiment_id: str, traffic_percent: int) -> dict[str, Any]:
        record = self._get(experiment_id)
        if traffic_percent not in (5, 10, 25):
            raise ValueError("canary traffic must be one of 5, 10, 25 percent")
        record.update(
            {
                "status": "RUNNING",
                "traffic_percent": int(traffic_percent),
                "side_effect": "none_dry_run" if self.dry_run else "traffic_changed",
            }
        )
        return dict(record)

    def read_metrics(
        self, experiment_id: str, window: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        self._get(experiment_id)
        return {
            "experiment_id": experiment_id,
            "window": dict(window or {}),
            **self.metric_fixture,
        }

    def pause_experiment(self, experiment_id: str, reason: str) -> dict[str, Any]:
        record = self._get(experiment_id)
        record.update(
            {
                "status": "PAUSE_RECOMMENDED",
                "pause_reason": reason,
                "requires_human_approval": True,
            }
        )
        return dict(record)

    def promote(self, experiment_id: str, approval_ref: str) -> dict[str, Any]:
        record = self._get(experiment_id)
        if not approval_ref:
            raise PermissionError("approval_ref is required")
        if record["status"] == "PAUSE_RECOMMENDED":
            raise PermissionError(
                "cannot promote after a guardrail pause recommendation"
            )
        record.update(
            {
                "status": "PROMOTE_RECOMMENDED",
                "promotion_approval_ref": approval_ref,
                "requires_human_approval": True,
            }
        )
        return dict(record)

    def _get(self, experiment_id: str) -> dict[str, Any]:
        if experiment_id not in self.experiments:
            raise KeyError(f"unknown experiment: {experiment_id}")
        return self.experiments[experiment_id]


__all__ = ["DryRunExperimentPlatform"]
