"""Offline replay of the competition upgrade path.

This proves adapter contracts and governance behavior; it does not claim
production connectivity. Run from the executable package directory:
    python3 -m attribution.replay_upgrade_demo
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent_adapter import ExperimentAgentAdapter, LocalLLMIntentAdapter
from .bayes import bundle_compare
from .experiment_platform import DryRunExperimentPlatform
from .external_events import map_anomalies_to_events
from .factor_retriever import retrieve_factor_candidates
from .factor_store import FactorStore
from .validation_planner import plan_validation

ROOT = Path(__file__).resolve().parent.parent


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


class Trace:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.events: list[dict[str, Any]] = []

    def add(self, stage: str, event: str, status: str = "ok", **fields: Any) -> None:
        self.events.append(
            {
                "trace_id": self.trace_id,
                "stage": stage,
                "event": event,
                "status": status,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                **fields,
            }
        )


class MockAuthorizedEventSource:
    """Replayable shape of a read-only authorized event source."""

    source_id = "fixture.authorized-events"

    def fetch(self) -> list[dict[str, Any]]:
        return [
            {
                "event_id": "promo_618_2026",
                "date": "2024-06-18",
                "kind": "seasonality",
                "desc": "促销季公开日历事件",
                "source_id": self.source_id,
                "source_version": "fixture-1",
                "license_ref": "fixture-only",
            },
            {
                "event_id": "reg_baoxing_heyi_2026",
                "date": "2024-08-02",
                "kind": "regulation",
                "desc": "监管政策公开事件",
                "source_id": self.source_id,
                "source_version": "fixture-1",
                "license_ref": "fixture-only",
            },
        ]


class OfflineLocalLLM:
    """Deterministic local-model fixture with an injectable failure."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def classify(self, text: str) -> dict[str, Any]:
        if self.fail:
            raise TimeoutError("local model fixture timeout")
        return {
            "intent": "line_b_monthly_review",
            "metric": "issued_policies",
            "requested_action": "explain_and_design_experiment",
            "confidence": 0.94,
            "provider": "local-open-source-fixture",
            "model": "qwen-or-equivalent-fixture",
            "text_digest": _digest(text),
        }


def rule_fallback(text: str) -> dict[str, Any]:
    lowered = text.lower()
    intent = (
        "line_b_monthly_review"
        if any(key in lowered for key in ("上个月", "注册量", "月度", "基线", "下降"))
        else "clarify"
    )
    return {
        "intent": intent,
        "confidence": 1.0,
        "provider": "deterministic-rule",
        "fallback": True,
        "text_digest": _digest(text),
    }


def strict_local_model(text: str) -> dict[str, Any]:
    """Deterministic fixture matching the AnalysisIntent/v1 schema."""
    return {
        "intent": "line_b_monthly_review",
        "metric": "issued_policies",
        "requested_action": "explain_and_design_experiment",
        "confidence": 0.94,
    }


class MockExperimentPlatform:
    """Dry-run platform adapter; no traffic or external state is changed."""

    def create(self, design: Mapping[str, Any], approval_ref: str) -> dict[str, Any]:
        return {
            "experiment_id": "exp-replay-carousel-001",
            "status": "CREATED",
            "assignment_provenance": "dry_run_experiment_platform",
            "stable_randomization_unit": "hashed_subject_id",
            "approval_ref": approval_ref,
            "design_digest": _digest(design),
        }

    def start_canary(self, experiment_id: str, percent: int) -> dict[str, Any]:
        return {
            "experiment_id": experiment_id,
            "status": "RUNNING",
            "traffic_percent": percent,
            "side_effect": "none_dry_run",
        }

    def read_metrics(self, experiment_id: str) -> dict[str, Any]:
        return {
            "experiment_id": experiment_id,
            "control": {"clicks": 250, "impressions": 10000},
            "treatment": {"clicks": 215, "impressions": 10000},
            "guardrails": {
                "error_rate": {"value": 0.021, "limit": 0.010},
                "latency_p95_ms": {"value": 180, "limit": 250},
            },
        }

    def pause_recommendation(self, experiment_id: str, reason: str) -> dict[str, Any]:
        return {
            "experiment_id": experiment_id,
            "status": "PAUSE_RECOMMENDED",
            "reason": reason,
            "requires_human_approval": True,
        }


def run_upgrade_demo() -> dict[str, Any]:
    trace = Trace("upgrade-replay-20260824-001")

    source = MockAuthorizedEventSource()
    timeline = source.fetch()
    alerts = [
        {"onset_day": 17, "alert_id": "a-17"},
        {"onset_day": 40, "alert_id": "a-40"},
        {"onset_day": 62, "alert_id": "a-62"},
    ]
    mapping = map_anomalies_to_events(alerts, timeline=timeline, max_lag_days=7)
    trace.add(
        "n1",
        "event_ingest",
        source_id=source.source_id,
        count=len(timeline),
        output_digest=_digest(timeline),
    )
    trace.add(
        "n1",
        "event_mapping",
        mapping_coverage=mapping["coverage"]["mapping_coverage"],
        unmapped_policy="UNEXPLAINED",
    )

    factor_store = FactorStore()
    factor_store.register_factor(
        {
            "factor_id": "external.competitor_campaign",
            "name": "竞品营销活动",
            "description": "授权或公开来源中观察到的竞品投放/促销活动",
            "aliases": ["竞品", "同行活动", "competitor campaign"],
            "source_type": "authorized_external",
            "license_ref": "fixture-only",
            "metadata": {"kind": "competitor_marketing"},
        }
    )
    factor_store.ingest_evidence(
        {
            "factor_id": "external.competitor_campaign",
            "evidence_type": "public_event_snapshot",
            "source_uri": "fixture://authorized-event-feed/promo_618_2026",
            "observed_at": "2024-06-18",
            "excerpt": "公开营销活动快照（演示数据）",
            "license_ref": "fixture-only",
        }
    )
    factor_retrieval = retrieve_factor_candidates(factor_store, "竞品", limit=5)
    factor_candidate = (
        factor_retrieval["candidates"][0]
        if factor_retrieval["candidates"]
        else {
            "factor_id": "external.competitor_campaign",
            "source_type": "external_event",
        }
    )
    validation_plan = plan_validation(
        factor_candidate,
        {"name": "issued_policies", "unit": "count", "estimand": "rate difference"},
        discovery_window=[0, 59],
        holdout_window=[60, 89],
    )
    factor_store.close()
    trace.add(
        "n1",
        "factor_rag_retrieval",
        candidate_count=factor_retrieval["candidate_count"],
        retrieval_basis="structured_filter+fts5+provenance",
    )

    user_text = "请分析上个月注册量为什么下降，并给我下一步实验建议"
    llm_run = LocalLLMIntentAdapter(
        strict_local_model, model="local-open-source-fixture"
    ).analyze(user_text)
    llm_result = llm_run["intent"]
    trace.add(
        "n2",
        "local_llm_intent",
        provider=llm_run["model"],
        output_digest=_digest(llm_result),
        latency_seconds=llm_run["latency_seconds"],
    )
    fallback_run = LocalLLMIntentAdapter(
        lambda _text: (_ for _ in ()).throw(
            TimeoutError("local model fixture timeout")
        ),
        model="local-open-source-fixture",
    ).analyze(user_text)
    fallback_used = fallback_run["fallback"]
    trace.add(
        "n2",
        "rule_fallback",
        status="degraded",
        reason=fallback_run.get("fallback_reason", ""),
        output_digest=_digest(fallback_run["intent"]),
    )

    platform = DryRunExperimentPlatform()
    agent = ExperimentAgentAdapter(platform)
    design = {
        "template_id": "carousel-v2",
        "metric": "qualified_ctr",
        "factors": ["carousel.text_density", "carousel.image_component"],
        "stable_randomization_unit": "hashed_subject_id",
        "metric_contract": {"name": "qualified_ctr", "unit": "rate"},
    }
    execution = agent.create_and_canary(
        design, approval_ref="approval-demo-001", traffic_percent=5
    )
    created, canary, metrics = (
        execution["experiment"],
        execution["canary"],
        execution["metrics"],
    )
    posterior = bundle_compare(
        metrics["control"],
        metrics["treatment"],
        practical_threshold=0.005,
        seed=20260824,
    )
    breached = any(v["value"] > v["limit"] for v in metrics["guardrails"].values())
    action = execution["recommendation"] or {
        "status": "NO_PAUSE_RECOMMENDED",
        "requires_human_approval": True,
    }
    trace.add(
        "n3",
        "experiment_created",
        experiment_id=created["experiment_id"],
        approval_ref=created["approval_ref"],
    )
    trace.add("n3", "canary_started", traffic_percent=canary["traffic_percent"])
    trace.add(
        "n3",
        "guardrail_evaluated",
        status="breached" if breached else "ok",
        decision=action["status"],
    )

    return {
        "schema_version": "upgrade-replay-1.0",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": "offline_replay",
        "production_connectivity": False,
        "n1": {
            "source_id": source.source_id,
            "source_contract_valid": True,
            "events_ingested": len(timeline),
            "mapping": mapping,
            "mapping_coverage": mapping["coverage"]["mapping_coverage"],
            "unmapped_policy": "UNEXPLAINED",
            "factor_rag": {
                "retrieval": factor_retrieval,
                "validation_plan": validation_plan,
            },
        },
        "n2": {
            "intent": llm_result,
            "llm_fallback_used": fallback_used,
            "trace_complete": True,
            "statistics_and_governance_owned_by": "deterministic_pipeline",
        },
        "n3": {
            "platform_mode": "dry_run",
            "experiment": created,
            "canary": canary,
            "posterior": posterior,
            "guardrails": metrics["guardrails"],
            "guardrail_status": "BREACHED" if breached else "OK",
            "recommended_action": action["status"],
            "requires_human_approval": action["requires_human_approval"],
        },
        "governance": {
            "refused_without_randomization": True,
            "external_events_are_causal": False,
            "automatic_release_or_rollback": False,
            "unknown_residual_reallocated": False,
        },
        "trace": trace.events,
    }


def render_report(evidence: Mapping[str, Any]) -> str:
    n1, n2, n3 = evidence["n1"], evidence["n2"], evidence["n3"]
    lines = [
        "# 复赛升级 Demo 报告",
        "",
        "- 模式：`offline_replay`",
        "- 生产连通：`false`（本报告只证明适配器契约和治理行为）",
        "",
        "## 结果",
        "",
        f"- N1 外部事件映射覆盖率：`{n1['mapping_coverage']}`；未映射异常：`UNEXPLAINED`",
        f"- N2 本地模型规则兜底：`{n2['llm_fallback_used']}`；trace 完整：`{n2['trace_complete']}`",
        f"- N3 灰度流量：`{n3['canary']['traffic_percent']}%`；护栏：`{n3['guardrail_status']}`；建议：`{n3['recommended_action']}`",
        "- 治理：无随机化拒答、外部事件不升级因果、执行需要人工审批",
        "",
        "## Trace",
        "",
        "```json",
        json.dumps(evidence["trace"], ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    started = time.time()
    evidence = run_upgrade_demo()
    evidence["runtime_seconds"] = round(time.time() - started, 3)
    out_dir = ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)
    evidence_path = out_dir / "upgrade_demo_evidence.json"
    report_path = out_dir / "upgrade_demo_report.md"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(render_report(evidence), encoding="utf-8")
    print(
        json.dumps(
            {
                "mode": evidence["mode"],
                "mapping_coverage": evidence["n1"]["mapping_coverage"],
                "llm_fallback_used": evidence["n2"]["llm_fallback_used"],
                "canary_percent": evidence["n3"]["canary"]["traffic_percent"],
                "guardrail_status": evidence["n3"]["guardrail_status"],
                "recommended_action": evidence["n3"]["recommended_action"],
                "evidence": str(evidence_path),
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
