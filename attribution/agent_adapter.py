"""N2 intent adapter and N3 governed action facade."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from .experiment_platform import DryRunExperimentPlatform

INTENT_VALUES = {
    "line_b_monthly_review",
    "line_a_experiment",
    "factor_search",
    "clarify",
}
METRIC_VALUES = {"issued_policies", "qualified_ctr", "conversion_rate", "unknown"}
ACTION_VALUES = {
    "explain_and_design_experiment",
    "discover_factors",
    "design_experiment",
    "clarify",
}
SENSITIVE_MARKERS = {"subject_id", "phone", "mobile", "id_card", "身份证", "手机号"}


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


def validate_analysis_intent(
    value: Mapping[str, Any], min_confidence: float = 0.6
) -> dict[str, Any]:
    required = ("intent", "metric", "requested_action", "confidence")
    missing = [key for key in required if key not in value]
    extra = sorted(set(value) - set(required))
    errors = []
    if missing:
        errors.append(f"missing:{','.join(missing)}")
    if extra:
        errors.append(f"extra:{','.join(extra)}")
    if value.get("intent") not in INTENT_VALUES:
        errors.append("invalid:intent")
    if value.get("metric") not in METRIC_VALUES:
        errors.append("invalid:metric")
    if value.get("requested_action") not in ACTION_VALUES:
        errors.append("invalid:requested_action")
    try:
        confidence = float(value.get("confidence"))
        if not 0.0 <= confidence <= 1.0:
            errors.append("invalid:confidence_range")
        if confidence < min_confidence:
            errors.append("low:confidence")
    except (TypeError, ValueError):
        errors.append("invalid:confidence")
    return {
        "valid": not errors,
        "errors": errors,
        "schema": "AnalysisIntent/v1",
        "extra_fields_rejected": True,
    }


def rule_intent(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if any(key in lowered for key in ("因子", "外部", "竞品", "未知")):
        intent, metric, action = "factor_search", "unknown", "discover_factors"
    elif any(key in lowered for key in ("ab", "实验", "灰度")):
        intent, metric, action = (
            "line_a_experiment",
            "qualified_ctr",
            "design_experiment",
        )
    elif any(key in lowered for key in ("上个月", "注册量", "月度", "基线", "下降")):
        intent, metric, action = (
            "line_b_monthly_review",
            "issued_policies",
            "explain_and_design_experiment",
        )
    else:
        intent, metric, action = "clarify", "unknown", "clarify"
    return {
        "intent": intent,
        "metric": metric,
        "requested_action": action,
        "confidence": 1.0,
    }


class LocalLLMIntentAdapter:
    """Accept only a strict JSON intent and retain a complete execution trace."""

    def __init__(
        self,
        provider: Callable[[str], Mapping[str, Any]],
        *,
        model: str = "local-open-source",
        timeout_seconds: float = 3.0,
        min_confidence: float = 0.6,
    ) -> None:
        self.provider = provider
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.min_confidence = min_confidence

    def analyze(self, text: str) -> dict[str, Any]:
        started = time.perf_counter()
        trace = [
            {"stage": "n2", "event": "intent_request", "input_digest": _digest(text)}
        ]
        try:
            if any(marker in text for marker in SENSITIVE_MARKERS):
                raise ValueError("sensitive field marker rejected")
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(self.provider, text)
            try:
                result = dict(future.result(timeout=self.timeout_seconds))
            except FutureTimeoutError as exc:
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError(
                    f"local model timeout after {self.timeout_seconds}s"
                ) from exc
            finally:
                if not future.done():
                    executor.shutdown(wait=False, cancel_futures=True)
                else:
                    executor.shutdown(wait=True)
            validation = validate_analysis_intent(result, self.min_confidence)
            if not validation["valid"]:
                raise ValueError(
                    "schema_validation_failed:" + ";".join(validation["errors"])
                )
            elapsed = round(time.perf_counter() - started, 6)
            trace.append(
                {
                    "stage": "n2",
                    "event": "local_llm_success",
                    "model": self.model,
                    "latency_seconds": elapsed,
                    "output_digest": _digest(result),
                }
            )
            return {
                "intent": result,
                "fallback": False,
                "trace": trace,
                "model": self.model,
                "latency_seconds": elapsed,
            }
        except Exception as exc:  # noqa: BLE001 - adapter failures must use fallback
            fallback = rule_intent(text)
            elapsed = round(time.perf_counter() - started, 6)
            trace.append(
                {
                    "stage": "n2",
                    "event": "rule_fallback",
                    "status": "degraded",
                    "reason": str(exc),
                    "latency_seconds": elapsed,
                    "output_digest": _digest(fallback),
                }
            )
            return {
                "intent": fallback,
                "fallback": True,
                "fallback_reason": str(exc),
                "trace": trace,
                "model": self.model,
                "latency_seconds": elapsed,
            }


class ExperimentAgentAdapter:
    """Policy facade: the agent can propose actions, never silently execute them."""

    def __init__(self, platform: DryRunExperimentPlatform | None = None) -> None:
        self.platform = platform or DryRunExperimentPlatform()

    def create_and_canary(
        self, design: Mapping[str, Any], approval_ref: str, traffic_percent: int = 5
    ) -> dict[str, Any]:
        created = self.platform.create_experiment(design, approval_ref)
        canary = self.platform.start_canary(created["experiment_id"], traffic_percent)
        metrics = self.platform.read_metrics(created["experiment_id"])
        breached = [
            name
            for name, value in metrics.get("guardrails", {}).items()
            if float(value.get("value", 0)) > float(value.get("limit", float("inf")))
        ]
        recommendation = (
            self.platform.pause_experiment(created["experiment_id"], ",".join(breached))
            if breached
            else None
        )
        return {
            "experiment": created,
            "canary": canary,
            "metrics": metrics,
            "guardrail_breaches": breached,
            "recommendation": recommendation,
            "automatic_rollback": False,
            "human_approval_required": True,
        }


__all__ = [
    "ExperimentAgentAdapter",
    "LocalLLMIntentAdapter",
    "rule_intent",
    "validate_analysis_intent",
]
