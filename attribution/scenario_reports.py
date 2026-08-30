"""Scenario runner + report renderer for the productized console demo (M3).

Each scenario runs a real pipeline (no canned output) and returns a
structured report dict; `render_markdown` turns it into a downloadable
audit report. Wired into run_server.py:

  GET /api/attribution/scenarios                         -> catalog
  GET /api/attribution/scenario-run?scenario=line_a      -> JSON report
  GET /api/attribution/scenario-report?scenario=line_a   -> Markdown download
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent

SCENARIOS: list[dict[str, str]] = [
    {
        "id": "full_review",
        "title": "全链路 · 经营异常自动复核（A+B+外部+N1/N2/N3）",
        "est_seconds": "≈6s",
    },
    {
        "id": "line_a",
        "title": "线 A · 组件归因全链路（异常→因子→实验→决策）",
        "est_seconds": "≈5s",
    },
    {
        "id": "line_b",
        "title": "线 B · 开放因子发现（分层异常+三层因子+下一窗口验证）",
        "est_seconds": "≈4s",
    },
    {
        "id": "external",
        "title": "线 B+ · 公开外部事件时间线映射（M2）",
        "est_seconds": "≈3s",
    },
    {
        "id": "bayes_case_a",
        "title": "拒答演示 · 欠定场景 REFUSED（案例 A）",
        "est_seconds": "≈3s",
    },
    {
        "id": "experience",
        "title": "v6.1 · 经验库跨期学习消融（PID+错配报警）",
        "est_seconds": "≈30s",
    },
]


def _scenario_line_a(runtime_dir: Path) -> dict[str, Any]:
    from .__main__ import run_demo

    demo = run_demo()
    return {
        "metrics": {
            "bundle_decision": demo["bundle"]["decision"],
            "bundle_effect": round(demo["bundle"]["effect_absolute"], 4),
            "oracle_bundle_ate": round(demo["oracle_bundle_ate"], 4),
            "p_practical_harm": round(demo["bundle"]["probability_practical_harm"], 3),
            "ledger_state": demo["ledger"]["state"],
            "component_effects_significant": sum(
                1 for e in demo["component_effects"] if e["significant"]
            ),
        },
        "key_outputs": {
            "claims": [
                {"claim_type": c["claim_type"], "statement": c["statement"]}
                for c in demo["ledger"]["claims"]
            ],
            "design": demo["design"],
        },
        "evidence_pointer": "outputs/demo_evidence.json",
    }


def _scenario_line_b(runtime_dir: Path) -> dict[str, Any]:
    from .association_discovery import discover_association_factors
    from .baseline_attribution import (
        attribute_baseline,
        change_registry_entry,
        external_event_entry,
        run_validation,
        simulate_panel,
    )
    from .factor_retriever import retrieve_factor_candidates
    from .factor_store import FactorStore
    from .rate_aware_rca import make_demo_panel
    from .rate_aware_rca import run_demo as run_rate_aware_rca
    from .validation_planner import plan_validation

    panel = simulate_panel()
    registry = [
        change_registry_entry(
            "chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"
        ),
        change_registry_entry(
            "chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"
        ),
    ]
    external = [
        external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")
    ]
    demo = attribute_baseline(
        panel["days"],
        panel["control"],
        panel["treated"],
        registry,
        external,
        panel["experiments"],
    )
    anomaly_windows = [
        {
            "start_day": max(panel["days"][0], alert["onset_day"] - 2),
            "end_day": min(panel["days"][-1], alert["onset_day"] + 2),
        }
        for alert in demo["unregistered_alerts"]
    ]
    rate_fixture = make_demo_panel(seed=20260826, n_days=60)
    raw_panel = rate_fixture["panel"]
    factor_series = [
        {
            "factor_id": "external.fx_rate_usd_cny",
            "source_type": "factor_series",
            "kind": "macro",
            "scope_id": "global",
            "days": panel["days"],
            "values": [
                7.10 + 0.001 * day + 0.015 * max(day - 26, 0) for day in panel["days"]
            ],
            "scope_match": 0.55,
            "source_reliability": 0.70,
            "source_uri": "fixture://authorized-macro-feed/usd-cny",
            "license_ref": "fixture-only",
            "experimentability": "external_or_observational",
            "unit": "cny_per_usd",
        },
        {
            "factor_id": "internal.page_latency_p95",
            "source_type": "factor_series",
            "kind": "runtime_quality",
            "scope_id": "east-paid-8.4",
            "days": panel["days"],
            "values": [
                180.0 + 3.0 * (day % 7) + 2.5 * max(day - 38, 0)
                for day in panel["days"]
            ],
            "scope_match": 0.92,
            "source_reliability": 0.90,
            "source_uri": "fixture://internal-observability/page-latency",
            "license_ref": "fixture-only",
            "experimentability": "controllable",
            "unit": "ms",
            "target_scope": {"region": "east", "channel": "paid", "version": "8.4"},
        },
        {
            "factor_id": "external.competitor_pressure_index",
            "source_type": "factor_series",
            "kind": "competitor_marketing",
            "scope_id": "paid",
            "days": panel["days"],
            "values": [
                20.0 + 0.05 * day + 0.8 * max(day - 47, 0) ** 1.35
                for day in panel["days"]
            ],
            "scope_match": 0.62,
            "source_reliability": 0.65,
            "source_uri": "fixture://authorized-event-feed/competitor-pressure",
            "license_ref": "fixture-only",
            "experimentability": "external_or_observational",
            "unit": "pressure_index",
        },
        {
            "factor_id": "internal.checkout_error_rate",
            "source_type": "factor_series",
            "kind": "runtime_quality",
            "scope_id": "east-paid-8.4",
            "days": panel["days"],
            "values": [
                0.008 + (0.018 if day >= 40 else 0.0) + 0.0002 * (day % 5)
                for day in panel["days"]
            ],
            "scope_match": 0.88,
            "source_reliability": 0.88,
            "source_uri": "fixture://internal-observability/checkout-errors",
            "license_ref": "fixture-only",
            "experimentability": "controllable",
            "unit": "rate",
            "target_scope": {"region": "east", "channel": "paid", "version": "8.4"},
        },
    ]
    association = discover_association_factors(
        panel["days"],
        demo["series"]["residual"],
        anomaly_windows,
        events=[
            {
                "factor_id": "internal.audit.unregistered_release",
                "source_type": "internal_event",
                "kind": "release_audit",
                "start_day": 40,
                "end_day": 40,
                "scope_match": 0.85,
                "source_reliability": 0.90,
                "source_uri": "fixture://internal-release-audit/day-40",
                "license_ref": "fixture-only",
            },
            {
                "factor_id": "external.competitor_campaign",
                "source_type": "external_event",
                "kind": "competitor_marketing",
                "start_day": 51,
                "end_day": 54,
                "scope_match": 0.60,
                "source_reliability": 0.65,
                "source_uri": "fixture://authorized-event-feed/competitor-campaign",
                "license_ref": "fixture-only",
            },
        ],
        max_lag=14,
        discovery_days=list(range(50)),
        holdout_days=list(range(50, 60)),
        factor_series=factor_series,
    )
    validation = run_validation()
    rate_aware = run_rate_aware_rca(
        runtime_dir / "evidence" / "T2-lineB-rate-aware-rca.json"
    )
    factor_names = {
        "internal.audit.unregistered_release": (
            "未登记发布变更",
            "内部发布审计中发现的未登记版本/配置变更",
        ),
        "external.competitor_campaign": (
            "竞品营销活动",
            "授权或公开来源观察到的竞品投放/促销活动",
        ),
        "external.fx_rate_usd_cny": (
            "美元兑人民币汇率",
            "授权宏观数据源中的日度汇率快照",
        ),
        "internal.page_latency_p95": ("页面 P95 延迟", "内部可观测性中的页面响应延迟"),
        "external.competitor_pressure_index": (
            "竞品压力指数",
            "授权或公开来源构造的竞品压力序列",
        ),
        "internal.checkout_error_rate": ("结算错误率", "内部可观测性中的结算失败比例"),
    }
    store = FactorStore()
    registered = set()
    try:
        for candidate in association["candidates"]:
            factor_id = candidate.get("parent_factor_id", candidate["factor_id"])
            if factor_id in registered:
                continue
            registered.add(factor_id)
            name, description = factor_names.get(factor_id, (factor_id, "候选因子"))
            store.register_factor(
                {
                    "factor_id": factor_id,
                    "name": name,
                    "description": description,
                    "aliases": [factor_id, name],
                    "source_type": candidate["source_type"],
                    "license_ref": candidate.get("license_ref"),
                    "metadata": {
                        "kind": candidate.get("kind"),
                        "fixture": True,
                        "derived_layers": ["level", "velocity", "acceleration"],
                    },
                }
            )
            store.ingest_evidence(
                {
                    "factor_id": factor_id,
                    "evidence_type": "scenario_fixture",
                    "source_uri": candidate.get("source_uri"),
                    "observed_at": "2026-08-27",
                    "excerpt": "可复现演示候选，不能替代授权生产数据。",
                    "license_ref": candidate.get("license_ref"),
                }
            )
            if candidate.get("source_type") == "factor_series":
                source = next(
                    (item for item in factor_series if item["factor_id"] == factor_id),
                    None,
                )
                if source:
                    for day, value in zip(source["days"], source["values"]):
                        store.ingest_factor_snapshot(
                            {
                                "factor_id": factor_id,
                                "day": day,
                                "value": value,
                                "source_uri": candidate.get("source_uri"),
                                "license_ref": candidate.get("license_ref"),
                            }
                        )
        factor_library = retrieve_factor_candidates(store, "", limit=10)
    finally:
        store.close()
    metric_contract = {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference",
    }
    validation_plans = [
        plan_validation(
            candidate,
            metric_contract,
            discovery_window=[0, 49],
            holdout_window=[50, 59],
        )
        for candidate in association["candidates"]
    ]
    scope_cells = sorted({tuple(sorted(row["scope"].items())) for row in raw_panel})
    raw_panel_rows = []
    for row in raw_panel:
        control = row["control"]
        treatment = row["treatment"]
        raw_panel_rows.append(
            {
                "row_id": f"scope-{row['scope']['region']}-{row['scope']['channel']}-"
                f"v{row['scope']['version'].replace('.', '')}-day{row['day']:03d}",
                "day": row["day"],
                "scope": row["scope"],
                "control": {
                    **control,
                    "rate": round(
                        control["clicks"] / max(control["impressions"], 1), 6
                    ),
                },
                "treatment": {
                    **treatment,
                    "rate": round(
                        treatment["clicks"] / max(treatment["impressions"], 1), 6
                    ),
                },
                "gap": round(
                    treatment["clicks"] / max(treatment["impressions"], 1)
                    - control["clicks"] / max(control["impressions"], 1),
                    6,
                ),
                "quality": {
                    "missing_rate": 0.0,
                    "late_arrival_rate": round(0.004 + (row["day"] % 4) * 0.002, 4),
                },
            }
        )
    detail_days = list(range(36, 60))
    data_details = [
        {
            "day": day,
            "control": round(panel["control"][day], 2),
            "treated": round(panel["treated"][day], 2),
            "gap": demo["series"]["gap"][day],
            "residual": demo["series"]["residual"][day],
            "abs_residual": round(abs(demo["series"]["residual"][day]), 2),
            "direction": "up" if demo["series"]["residual"][day] > 0 else "down",
        }
        for day in detail_days
    ]
    return {
        "metrics": {
            **validation["metrics"],
            "naive_total": demo["att_aggregation"]["naive_total"],
            "hierarchical_total": demo["att_aggregation"]["hierarchical_total"],
            "rate_candidate_count": rate_aware["candidate_count"],
            "rate_candidates_scored": rate_aware["candidate_count_scored"],
        },
        "key_outputs": {
            "external_associations": demo["external_associations"],
            "unregistered_alerts": demo["unregistered_alerts"],
            "unknown_bucket": demo["unknown_bucket"],
            "association_discovery": association,
            "rate_aware_rca": rate_aware,
            "factor_library": factor_library,
            "validation_plans": validation_plans,
        },
        "data_details": {
            "mode": "deterministic_fixture",
            "panel_contract": [
                "day",
                "control",
                "treated",
                "gap",
                "residual",
                "abs_residual",
                "direction",
            ],
            "window": [36, 59],
            "rows": data_details,
            "raw_panel": raw_panel_rows,
            "factor_snapshots": [
                {
                    "factor_id": factor["factor_id"],
                    "day": int(day),
                    "value": round(float(value), 6),
                    "scope_id": factor.get("scope_id", "global"),
                    "unit": factor.get("unit"),
                }
                for factor in factor_series
                for day, value in zip(factor["days"], factor["values"])
            ],
            "inventory": {
                "panel_rows": len(raw_panel_rows),
                "panel_days": len(panel["days"]),
                "scope_cells": len(scope_cells),
                "factor_parents": len(factor_series) + len(registry),
                "derived_layers": len(
                    association["search_manifest"].get("derived_layers", [])
                ),
                "factor_snapshots": len(factor_series) * len(panel["days"]),
                "internal_events": len(registry) + 1,
                "external_events": len(external) + 1,
                "candidate_count": association["candidate_count"],
                "association_comparisons": association["search_manifest"]["N"],
            },
        },
        "evidence_pointer": "outputs/lineB_baseline_attribution.json",
    }


def _scenario_full_review(runtime_dir: Path) -> dict[str, Any]:
    """Run every compatible offline route and produce one review pack.

    This is intentionally an orchestration layer: it does not blend effect
    estimates across lines. Each child result retains its own evidence level.
    """
    from .replay_upgrade_demo import run_upgrade_demo

    line_b = _scenario_line_b(runtime_dir)
    line_a = _scenario_line_a(runtime_dir)
    external = _scenario_external(runtime_dir)
    upgrade = run_upgrade_demo()
    association = line_b["key_outputs"]["association_discovery"]
    return {
        "metrics": {
            "routes_executed": 4,
            "b_line_candidates": association["candidate_count"],
            "association_comparisons": association["search_manifest"]["N"],
            "a_line_decision": line_a["metrics"]["bundle_decision"],
            "external_mapping_coverage": external["metrics"]["mapping_coverage"],
            "n3_guardrail": upgrade["n3"]["guardrail_status"],
        },
        "key_outputs": {
            "line_b": line_b["key_outputs"],
            "line_a": line_a["key_outputs"],
            "external": external["key_outputs"],
            "n1_n2_n3": {"n1": upgrade["n1"], "n2": upgrade["n2"], "n3": upgrade["n3"]},
        },
        "data_details": line_b["data_details"],
        "evidence_pointer": "outputs/upgrade_demo_evidence.json + outputs/lineB_baseline_attribution.json",
    }


def _scenario_external(runtime_dir: Path) -> dict[str, Any]:
    from .baseline_attribution import attribute_baseline
    from .external_events import (
        PUBLIC_EVENT_TIMELINE,
        _simulate_panel,
        map_anomalies_to_events,
    )

    panel = _simulate_panel()
    result = attribute_baseline(
        panel["days"],
        panel["control"],
        panel["treated"],
        [],
        [],
        {},
        detection_threshold=12.0,
    )
    mapping = map_anomalies_to_events(
        result["unregistered_alerts"], PUBLIC_EVENT_TIMELINE
    )
    return {
        "metrics": mapping["coverage"],
        "key_outputs": {
            "mapped": mapping["mapped"],
            "unmapped": mapping["unmapped"],
            "unused_events": mapping["unused_events"],
            "detected_alerts": result["unregistered_alerts"],
        },
        "evidence_pointer": "outputs/external_event_mapping.json",
    }


def _scenario_bayes_case_a(runtime_dir: Path) -> dict[str, Any]:
    import sys

    src = WORKSPACE / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from runtime.analysis import sanitize_rows
    from runtime.bayes_bridge import evaluate_with_bayes
    from runtime.cases import (
        case_experiment_metadata,
        default_metric_contract,
        generate_dataset,
    )

    rows, _truth = generate_dataset("A", seed=42, n=1200)
    bundle = {
        "rows": sanitize_rows(rows),
        "metric_contract": default_metric_contract(),
        "experiment_metadata": case_experiment_metadata("A"),
    }
    out = evaluate_with_bayes(
        bundle, practical_threshold=0.01, hte_segment_field="channel"
    )
    verdict = out.get("causal_readiness", {}).get("outcome")
    bayes_layer = out.get("bayes_layer", {})
    return {
        "metrics": {
            "causal_readiness": verdict,
            "refused": verdict != "CAUSAL_READY",
            "bayes_layer_decision": bayes_layer.get("decision"),
            "refusal_note": "案例 A 为观测性共变场景，门禁判定 DESCRIPTIVE_ONLY，"
            "贝叶斯层不输出因果决策——即拒答。",
        },
        "key_outputs": {
            "causal_readiness": out.get("causal_readiness"),
            "claim": out.get("claim"),
        },
        "evidence_pointer": "GET /api/attribution/bayes-case?case=A",
    }


def _scenario_experience(runtime_dir: Path) -> dict[str, Any]:
    from .experience_benchmark import run_experience_ablation

    store_path = runtime_dir / "attribution_experience_store.json"
    store_path.unlink(missing_ok=True)  # console demo always starts cold
    result = run_experience_ablation(store_path=store_path)
    return {
        "metrics": {
            "ate_rmse_sparse_static": result["static_baseline"]["ate_rmse_sparse"],
            "ate_rmse_sparse_adaptive": result["adaptive_experience_store"][
                "ate_rmse_sparse"
            ],
            "ate_rmse_rich_static": result["static_baseline"]["ate_rmse_rich"],
            "ate_rmse_rich_adaptive": result["adaptive_experience_store"][
                "ate_rmse_rich"
            ],
            "mismatch_alarm_fired": result["adaptive_experience_store"][
                "mismatch_alarm"
            ]["fired_periods"],
            "nu_trajectory": result["adaptive_experience_store"]["nu_trajectory"],
        },
        "key_outputs": {"store_final": result["store_final"], "note": result["note"]},
        "evidence_pointer": "outputs/experience_ablation.json",
    }


_RUNNERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "full_review": _scenario_full_review,
    "line_a": _scenario_line_a,
    "line_b": _scenario_line_b,
    "external": _scenario_external,
    "bayes_case_a": _scenario_bayes_case_a,
    "experience": _scenario_experience,
}


def run_scenario(scenario_id: str, runtime_dir: Path | None = None) -> dict[str, Any]:
    if scenario_id not in _RUNNERS:
        raise KeyError(f"unknown scenario: {scenario_id}")
    runtime_dir = runtime_dir or (WORKSPACE / "runtime_data")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    body = _RUNNERS[scenario_id](runtime_dir)
    title = next(s["title"] for s in SCENARIOS if s["id"] == scenario_id)
    return {
        "scenario": scenario_id,
        "title": title,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.time() - t0, 3),
        "real_run": True,
        "execution_mode": "deterministic_fixture",
        **body,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# 归因报告 · {report['title']}",
        "",
        f"- 场景：`{report['scenario']}`",
        f"- 生成时间：{report['generated_at']}",
        f"- API 执行耗时：{report['runtime_seconds']}s（计算链路真实执行；数据为明确标记的 deterministic fixture）",
        "",
        "## 关键指标",
        "",
        "| 指标 | 值 |",
        "|---|---|",
    ]
    for k, v in report.get("metrics", {}).items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## 关键输出",
        "",
        "```json",
        __import__("json").dumps(
            report.get("key_outputs", {}), ensure_ascii=False, indent=2
        ),
        "```",
        "",
        f"证据文件：`{report.get('evidence_pointer', '')}`",
        "",
        (
            "合规说明：本系统输出为经营决策支持，不构成投资建议；"
            "证据不足时应拒答而非强行归因。"
        ),
    ]
    return "\n".join(lines)
