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
    {"id": "line_a", "title": "线 A · 组件归因全链路（异常→因子→实验→决策）",
     "est_seconds": "≈5s"},
    {"id": "line_b", "title": "线 B · 月度基线归因（注册变动+外部事件+未知桶）",
     "est_seconds": "≈4s"},
    {"id": "external", "title": "线 B+ · 公开外部事件时间线映射（M2）",
     "est_seconds": "≈3s"},
    {"id": "bayes_case_a", "title": "拒答演示 · 欠定场景 REFUSED（案例 A）",
     "est_seconds": "≈3s"},
    {"id": "experience", "title": "v6.1 · 经验库跨期学习消融（PID+错配报警）",
     "est_seconds": "≈30s"},
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
                1 for e in demo["component_effects"] if e["significant"]),
        },
        "key_outputs": {
            "claims": [{"claim_type": c["claim_type"], "statement": c["statement"]}
                       for c in demo["ledger"]["claims"]],
            "design": demo["design"],
        },
        "evidence_pointer": "outputs/demo_evidence.json",
    }


def _scenario_line_b(runtime_dir: Path) -> dict[str, Any]:
    from .baseline_attribution import (
        attribute_baseline,
        change_registry_entry,
        external_event_entry,
        run_validation,
        simulate_panel,
    )
    panel = simulate_panel()
    registry = [
        change_registry_entry("chg_ranking", 15, "search_ranking", experiment_id="exp_ranking"),
        change_registry_entry("chg_subsidy", 30, "subsidy_push", experiment_id="exp_subsidy"),
    ]
    external = [external_event_entry("ext_regulation", 45, 49, "regulation", "监管新规发布")]
    demo = attribute_baseline(panel["days"], panel["control"], panel["treated"],
                              registry, external, panel["experiments"])
    validation = run_validation()
    return {
        "metrics": {**validation["metrics"],
                    "naive_total": demo["att_aggregation"]["naive_total"],
                    "hierarchical_total": demo["att_aggregation"]["hierarchical_total"]},
        "key_outputs": {
            "external_associations": demo["external_associations"],
            "unregistered_alerts": demo["unregistered_alerts"],
            "unknown_bucket": demo["unknown_bucket"],
        },
        "evidence_pointer": "outputs/lineB_baseline_attribution.json",
    }


def _scenario_external(runtime_dir: Path) -> dict[str, Any]:
    from .baseline_attribution import attribute_baseline
    from .external_events import (
        PUBLIC_EVENT_TIMELINE,
        _simulate_panel,
        map_anomalies_to_events,
    )
    panel = _simulate_panel()
    result = attribute_baseline(panel["days"], panel["control"], panel["treated"],
                                [], [], {}, detection_threshold=12.0)
    mapping = map_anomalies_to_events(result["unregistered_alerts"], PUBLIC_EVENT_TIMELINE)
    return {
        "metrics": mapping["coverage"],
        "key_outputs": {"mapped": mapping["mapped"], "unmapped": mapping["unmapped"],
                        "unused_events": mapping["unused_events"],
                        "detected_alerts": result["unregistered_alerts"]},
        "evidence_pointer": "outputs/external_event_mapping.json",
    }


def _scenario_bayes_case_a(runtime_dir: Path) -> dict[str, Any]:
    import sys
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    from runtime.analysis import sanitize_rows
    from runtime.bayes_bridge import evaluate_with_bayes
    from runtime.cases import (
        case_experiment_metadata,
        default_metric_contract,
        generate_dataset,
    )
    rows, _truth = generate_dataset("A", seed=42, n=1200)
    bundle = {"rows": sanitize_rows(rows), "metric_contract": default_metric_contract(),
              "experiment_metadata": case_experiment_metadata("A")}
    out = evaluate_with_bayes(bundle, practical_threshold=0.01, hte_segment_field="channel")
    verdict = out.get("causal_readiness", {}).get("outcome")
    bayes_layer = out.get("bayes_layer", {})
    return {
        "metrics": {"causal_readiness": verdict,
                    "refused": verdict != "CAUSAL_READY",
                    "bayes_layer_decision": bayes_layer.get("decision"),
                    "refusal_note": "案例 A 为观测性共变场景，门禁判定 DESCRIPTIVE_ONLY，"
                                    "贝叶斯层不输出因果决策——即拒答。"},
        "key_outputs": {"causal_readiness": out.get("causal_readiness"),
                        "claim": out.get("claim")},
        "evidence_pointer": "GET /api/attribution/bayes-case?case=A",
    }


def _scenario_experience(runtime_dir: Path) -> dict[str, Any]:
    from .experience_benchmark import run_experience_ablation
    store_path = runtime_dir / "experience_store.json"
    store_path.unlink(missing_ok=True)  # console demo always starts cold
    result = run_experience_ablation(store_path=store_path)
    return {
        "metrics": {
            "ate_rmse_sparse_static": result["static_baseline"]["ate_rmse_sparse"],
            "ate_rmse_sparse_adaptive": result["adaptive_experience_store"]["ate_rmse_sparse"],
            "ate_rmse_rich_static": result["static_baseline"]["ate_rmse_rich"],
            "ate_rmse_rich_adaptive": result["adaptive_experience_store"]["ate_rmse_rich"],
            "mismatch_alarm_fired": result["adaptive_experience_store"]["mismatch_alarm"]["fired_periods"],
            "nu_trajectory": result["adaptive_experience_store"]["nu_trajectory"],
        },
        "key_outputs": {"store_final": result["store_final"],
                        "note": result["note"]},
        "evidence_pointer": "outputs/experience_ablation.json",
    }


_RUNNERS: dict[str, Callable[[Path], dict[str, Any]]] = {
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
        "runtime_seconds": round(time.time() - t0, 1),
        "real_run": True,
        **body,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# 归因报告 · {report['title']}",
        "",
        f"- 场景：`{report['scenario']}`",
        f"- 生成时间：{report['generated_at']}",
        f"- 实机运行耗时：{report['runtime_seconds']}s（本报告由真实运行产生，非静态样例）",
        "",
        "## 关键指标",
        "",
        "| 指标 | 值 |", "|---|---|",
    ]
    for k, v in report.get("metrics", {}).items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 关键输出", "", "```json",
              __import__("json").dumps(report.get("key_outputs", {}), ensure_ascii=False, indent=2),
              "```", "", f"证据文件：`{report.get('evidence_pointer', '')}`", "",
              ("合规说明：本系统输出为经营决策支持，不构成投资建议；"
              "证据不足时应拒答而非强行归因。")]
    return "\n".join(lines)
