"""Scenario runner + report renderer for the productized console demo (M3).

Each scenario runs a real pipeline (no canned output) and returns a
structured report dict; `render_markdown` turns it into a downloadable
audit report. Wired into run_server.py:

  GET /api/track2/scenarios                         -> catalog
  GET /api/track2/scenario-run?scenario=line_a      -> JSON report
  GET /api/track2/scenario-report?scenario=line_a   -> Markdown download
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from collections.abc import Callable

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime

    UTC = UTC
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
_SCENARIO_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_COMPANY_CONFIG: Any = None  # set via set_company_config()


def set_company_config(config: Any) -> None:
    """Register an external DataSourceConfig so `company_line_b` can run."""
    global _COMPANY_CONFIG
    _COMPANY_CONFIG = config
    _SCENARIO_CACHE.clear()


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
    {
        "id": "company_line_b",
        "title": "真实数据 · 线 B 全链路（企业内网数据适配器）",
        "est_seconds": "≈5s",
    },
]


def _scenario_company_line_b(runtime_dir: Path) -> dict[str, Any]:
    """Run the line-B pipeline on externally supplied (company) data.

    Same algorithmic core as the fixture demo: persistent-control baseline
    attribution, rate-aware scoped RCA, association discovery over internal /
    external factor candidates, and next-window validation plans.  Every
    factor/event carries the source_uri / license_ref from the adapter config
    so the Claim Ledger grading stays intact outside the demo setting.
    """
    from .adapters import load_line_b_inputs
    from .association_discovery import discover_association_factors
    from .baseline_attribution import attribute_baseline
    from .data_contract import ContractError
    from .factor_retriever import retrieve_factor_candidates
    from .factor_store import FactorStore
    from .rate_aware_rca import discover_rate_candidates
    from .validation_planner import plan_validation

    if _COMPANY_CONFIG is None:
        raise RuntimeError(
            "company_line_b 需要 --data-config 指向数据配置文件（见 config.example.json）"
        )
    inputs = load_line_b_inputs(_COMPANY_CONFIG)
    days = inputs["days"]
    if len(days) < 20:
        raise ContractError(
            f"metric_panel 需要至少 20 天的数据用于发现/留出切分，当前 {len(days)} 天"
        )
    split = int(len(days) * 5 / 6)  # 后 1/6 作为留出窗
    discovery_days = days[:split]
    holdout_days = days[split:]

    demo = attribute_baseline(
        days,
        inputs["control"],
        inputs["treated"],
        inputs["registry"],
        inputs["external"],
        inputs["experiments"],
        detection_threshold=_COMPANY_CONFIG.detection_threshold,
        metric_contract=inputs["metric_contract"],
    )
    anomaly_windows = [
        {
            "start_day": max(days[0], alert["onset_day"] - 2),
            "end_day": min(days[-1], alert["onset_day"] + 2),
        }
        for alert in demo["unregistered_alerts"]
    ]
    association = discover_association_factors(
        days,
        demo["series"]["residual"],
        anomaly_windows,
        events=inputs["events"],
        max_lag=14,
        discovery_days=discovery_days,
        holdout_days=holdout_days,
        factor_series=inputs["factor_series"],
        bootstrap_reps=49,
        statistic_method=_COMPANY_CONFIG.association_statistic,
        shadow_diagnostics=_COMPANY_CONFIG.shadow_diagnostics,
    )
    rate_aware = (
        discover_rate_candidates(
            inputs["scoped_panel"],
            ("region", "channel", "version"),
            baseline_window=(discovery_days[0], discovery_days[-1]),
            current_window=(holdout_days[0], holdout_days[-1]),
            min_impressions=100,
            top_k=8,
            beam_width=20,
        )
        if _COMPANY_CONFIG.metric_unit == "rate"
        else {
            "status": "NOT_APPLICABLE",
            "reason": "rate decomposition requires a probability metric",
            "candidates": [],
        }
    )
    if _COMPANY_CONFIG.metric_unit == "rate":
        from .risk_loc import discover_risk_candidates

        rate_aware["riskloc_challenger"] = discover_risk_candidates(
            inputs["scoped_panel"],
            ("region", "channel", "version"),
            (discovery_days[0], discovery_days[-1]),
            (holdout_days[0], holdout_days[-1]),
            max_candidates=10000,
            top_k=8,
        )
    store = FactorStore()
    registered: set[str] = set()
    try:
        for candidate in association["candidates"]:
            factor_id = candidate.get("parent_factor_id", candidate["factor_id"])
            if factor_id in registered:
                continue
            registered.add(factor_id)
            store.register_factor(
                {
                    "factor_id": factor_id,
                    "name": factor_id,
                    "description": "企业数据源候选因子",
                    "aliases": [factor_id],
                    "source_type": candidate["source_type"],
                    "license_ref": candidate.get("license_ref"),
                    "metadata": {
                        "kind": candidate.get("kind"),
                        "fixture": False,
                        "derived_layers": ["level", "velocity", "acceleration"],
                    },
                }
            )
            store.ingest_evidence(
                {
                    "factor_id": factor_id,
                    "evidence_type": "company_adapter",
                    "source_uri": candidate.get("source_uri"),
                    "observed_at": datetime.now(UTC).date().isoformat(),
                    "excerpt": "来自企业内网数据适配器的候选；验证以留出窗/下一窗口为准。",
                    "license_ref": candidate.get("license_ref"),
                }
            )
        factor_library = retrieve_factor_candidates(store, "", limit=40)
    finally:
        store.close()

    metric_contract = {
        **inputs["metric_contract"],
        "estimand": "rate difference"
        if _COMPANY_CONFIG.metric_unit == "rate"
        else f"{_COMPANY_CONFIG.metric_unit} difference",
    }
    validation_plans = [
        plan_validation(
            candidate,
            metric_contract,
            discovery_window=[discovery_days[0], discovery_days[-1]],
            holdout_window=[holdout_days[0], holdout_days[-1]],
        )
        for candidate in association["candidates"]
    ]

    evidence_path = runtime_dir / "evidence" / "T2-company-lineB.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json

    evidence_path.write_text(
        _json.dumps(
            {
                "provenance": inputs["provenance"],
                "att_aggregation": demo["att_aggregation"],
                "metric_contract": inputs["metric_contract"],
                "transfer_checks": demo["transfer_checks"],
                "explained_uncertainty": demo["explained_uncertainty"],
                "unregistered_alerts": demo["unregistered_alerts"],
                "unknown_bucket": demo["unknown_bucket"],
                "association_candidates": association["candidates"],
                "rate_aware_candidates": rate_aware.get("candidates"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    evidence_path = evidence_path.resolve()
    try:
        pointer = str(evidence_path.relative_to(WORKSPACE))
    except ValueError:
        pointer = str(evidence_path)
    return {
        "execution_mode": "company_adapter",
        "metrics": {
            "naive_total": demo["att_aggregation"]["naive_total"],
            "hierarchical_total": demo["att_aggregation"]["hierarchical_total"],
            "rate_candidate_count": len(rate_aware.get("candidates", [])),
            "panel_days": len(days),
            "panel_rows": inputs.get("panel_row_count", len(inputs["scoped_panel"])),
            "factor_parents": len(inputs["factor_series"]) + len(inputs["events"]),
        },
        "key_outputs": {
            "external_associations": demo["external_associations"],
            "metric_contract": inputs["metric_contract"],
            "transfer_checks": demo["transfer_checks"],
            "explained_uncertainty": demo["explained_uncertainty"],
            "unregistered_alerts": demo["unregistered_alerts"],
            "unknown_bucket": demo["unknown_bucket"],
            "association_discovery": association,
            "rate_aware_rca": rate_aware,
            "factor_library": factor_library,
            "validation_plans": validation_plans,
        },
        "data_details": {
            "mode": "company_adapter",
            "provenance": inputs["provenance"],
            "window": [discovery_days[0], holdout_days[-1]],
        },
        "evidence_pointer": pointer,
    }


def _scenario_line_a(runtime_dir: Path) -> dict[str, Any]:
    from .__main__ import run_demo

    demo = run_demo()
    hdim = demo["high_dimensional_hte"]
    worst_overlap = min(hdim["subgroups"], key=lambda item: item["effect_shrunk"])
    top_moderator = hdim["top_moderators"][0] if hdim["top_moderators"] else {}
    return {
        "metrics": {
            "bundle_decision": demo["bundle"]["decision"],
            "bundle_effect": round(demo["bundle"]["effect_absolute"], 4),
            "oracle_bundle_ate": round(demo["oracle_bundle_ate"], 4),
            "p_practical_harm": round(demo["bundle"]["probability_practical_harm"], 3),
            "hte_model": hdim["model"],
            "hte_feature_count": hdim["diagnostics"]["raw_feature_count"],
            "hte_continuous_features": hdim["diagnostics"]["continuous_feature_count"],
            "hte_design_columns": hdim["diagnostics"]["design_matrix_columns"],
            "overlap_subgroups": hdim["diagnostics"]["overlapping_subgroup_count"],
            "rows_with_multiple_subgroups": hdim["diagnostics"][
                "rows_with_multiple_subgroups"
            ],
            "worst_overlap_subgroup": worst_overlap["label"],
            "worst_overlap_cate": round(worst_overlap["effect_shrunk"], 4),
            "top_hte_moderator": top_moderator.get("term", "n/a"),
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
            "legacy_binary_hte": demo["hte"],
            "high_dimensional_hte": demo["high_dimensional_hte"],
            "a_line_funnel": demo["a_line_funnel"],
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
    days = panel["days"]
    target_scope = {"region": "east", "channel": "paid", "version": "8.4"}

    def pulse(day: int, start: int, end: int, height: float) -> float:
        return height if start <= day <= end else 0.0

    def factor(
        factor_id: str,
        *,
        kind: str,
        scope_id: str,
        values: list[float],
        scope_match: float,
        source_reliability: float,
        source_uri: str,
        experimentability: str,
        unit: str,
        target: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "factor_id": factor_id,
            "source_type": "factor_series",
            "kind": kind,
            "scope_id": scope_id,
            "days": days,
            "values": values,
            "scope_match": scope_match,
            "source_reliability": source_reliability,
            "source_uri": source_uri,
            "license_ref": "fixture-only",
            "experimentability": experimentability,
            "unit": unit,
        }
        if target:
            item["target_scope"] = target
        return item

    factor_series = [
        factor(
            "internal.checkout_error_rate",
            kind="runtime_quality",
            scope_id="east-paid-8.4",
            values=[
                0.008
                + (0.018 if day >= 40 else 0.0)
                + (0.010 if day >= 52 else 0.0)
                + 0.0002 * (day % 5)
                for day in days
            ],
            scope_match=0.88,
            source_reliability=0.88,
            source_uri="fixture://internal-observability/checkout-errors",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.page_latency_p95",
            kind="runtime_quality",
            scope_id="east-paid-8.4",
            values=[180.0 + 3.0 * (day % 7) + 2.5 * max(day - 38, 0) for day in days],
            scope_match=0.92,
            source_reliability=0.90,
            source_uri="fixture://internal-observability/page-latency",
            experimentability="controllable",
            unit="ms",
            target=target_scope,
        ),
        factor(
            "internal.quote_api_timeout_rate",
            kind="api_quality",
            scope_id="quote-east-paid",
            values=[
                0.004
                + pulse(day, 37, 43, 0.017)
                + pulse(day, 52, 56, 0.012)
                + 0.0003 * (day % 4)
                for day in days
            ],
            scope_match=0.86,
            source_reliability=0.91,
            source_uri="fixture://internal-observability/quote-api-timeout",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.payment_retry_rate",
            kind="payment_quality",
            scope_id="payment-east-paid",
            values=[
                0.006 + 0.0004 * (day % 6) + pulse(day, 52, 56, 0.028) for day in days
            ],
            scope_match=0.80,
            source_reliability=0.87,
            source_uri="fixture://internal-observability/payment-retry",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.form_validation_error_rate",
            kind="frontend_quality",
            scope_id="form-east-paid-8.4",
            values=[
                0.012 + (0.011 if day >= 37 else 0.0) + 0.00035 * max(day - 37, 0)
                for day in days
            ],
            scope_match=0.84,
            source_reliability=0.86,
            source_uri="fixture://internal-observability/form-validation",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.agent_followup_sla_hours",
            kind="ops_process",
            scope_id="ops-east-paid",
            values=[
                3.7 + 0.025 * day + pulse(day, 39, 43, 0.9) + pulse(day, 52, 57, 1.6)
                for day in days
            ],
            scope_match=0.72,
            source_reliability=0.82,
            source_uri="fixture://internal-crm/followup-sla",
            experimentability="controllable",
            unit="hours",
            target=target_scope,
        ),
        factor(
            "internal.sms_delivery_failure_rate",
            kind="messaging_quality",
            scope_id="sms-east-paid",
            values=[
                0.005 + pulse(day, 52, 56, 0.026) + pulse(day, 37, 40, 0.006)
                for day in days
            ],
            scope_match=0.75,
            source_reliability=0.84,
            source_uri="fixture://internal-vendor/sms-delivery",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.premium_quote_cache_miss_rate",
            kind="cache_quality",
            scope_id="quote-cache-east-paid",
            values=[
                0.10 + (0.14 if day >= 39 else 0.0) + 0.003 * (day % 7) for day in days
            ],
            scope_match=0.78,
            source_reliability=0.85,
            source_uri="fixture://internal-observability/quote-cache",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "internal.channel_bid_cpc",
            kind="paid_channel",
            scope_id="paid-east",
            values=[
                3.1 + 0.018 * day + pulse(day, 36, 43, 0.55) + pulse(day, 51, 56, 0.35)
                for day in days
            ],
            scope_match=0.70,
            source_reliability=0.80,
            source_uri="fixture://internal-marketing/channel-bid-cpc",
            experimentability="controllable",
            unit="cny_per_click",
            target=target_scope,
        ),
        factor(
            "internal.app_crash_rate",
            kind="client_quality",
            scope_id="app-east-paid-8.4",
            values=[
                0.002
                + (0.006 if day >= 40 else 0.0)
                + (0.004 if day % 3 == 0 and day >= 52 else 0.0)
                for day in days
            ],
            scope_match=0.66,
            source_reliability=0.81,
            source_uri="fixture://internal-observability/app-crash",
            experimentability="controllable",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "external.fx_rate_usd_cny",
            kind="macro",
            scope_id="global",
            values=[7.10 + 0.001 * day + 0.015 * max(day - 26, 0) for day in days],
            scope_match=0.55,
            source_reliability=0.70,
            source_uri="fixture://authorized-macro-feed/usd-cny",
            experimentability="external_or_observational",
            unit="cny_per_usd",
        ),
        factor(
            "external.competitor_pressure_index",
            kind="competitor_marketing",
            scope_id="paid",
            values=[20.0 + 0.05 * day + 0.8 * max(day - 47, 0) ** 1.35 for day in days],
            scope_match=0.62,
            source_reliability=0.65,
            source_uri="fixture://authorized-event-feed/competitor-pressure",
            experimentability="external_or_observational",
            unit="pressure_index",
        ),
        factor(
            "external.competitor_campaign_intensity",
            kind="competitor_marketing",
            scope_id="paid-east",
            values=[
                0.2 + pulse(day, 36, 41, 1.15) + pulse(day, 51, 56, 1.65)
                for day in days
            ],
            scope_match=0.64,
            source_reliability=0.68,
            source_uri="fixture://authorized-event-feed/competitor-campaign-intensity",
            experimentability="external_or_observational",
            unit="index",
        ),
        factor(
            "external.regulatory_notice_density",
            kind="regulation",
            scope_id="east",
            values=[
                0.1 + pulse(day, 45, 49, 1.0) + pulse(day, 50, 56, 0.45) for day in days
            ],
            scope_match=0.58,
            source_reliability=0.74,
            source_uri="fixture://authorized-policy-feed/insurance-notices",
            experimentability="external_or_observational",
            unit="notice_index",
        ),
        factor(
            "external.search_trend_insurance",
            kind="demand_signal",
            scope_id="east-paid-search",
            values=[
                100.0 + 0.7 * day + pulse(day, 36, 42, 22.0) + pulse(day, 51, 56, 18.0)
                for day in days
            ],
            scope_match=0.61,
            source_reliability=0.66,
            source_uri="fixture://authorized-search-trend/insurance-intent",
            experimentability="external_or_observational",
            unit="trend_index",
        ),
        factor(
            "external.market_rate_index",
            kind="macro_rate",
            scope_id="macro",
            values=[3.60 + 0.006 * day + (0.34 if day >= 50 else 0.0) for day in days],
            scope_match=0.50,
            source_reliability=0.69,
            source_uri="fixture://authorized-macro-feed/market-rate",
            experimentability="external_or_observational",
            unit="index",
        ),
        factor(
            "external.macro_consumer_confidence",
            kind="macro_demand",
            scope_id="macro",
            values=[99.0 - 0.04 * day - (1.2 if day >= 48 else 0.0) for day in days],
            scope_match=0.47,
            source_reliability=0.71,
            source_uri="fixture://authorized-macro-feed/consumer-confidence",
            experimentability="external_or_observational",
            unit="index",
        ),
        factor(
            "external.weather_rainfall_index",
            kind="weather",
            scope_id="weather-east",
            values=[
                0.4 + pulse(day, 52, 56, 1.9) + pulse(day, 38, 40, 0.5) for day in days
            ],
            scope_match=0.43,
            source_reliability=0.76,
            source_uri="fixture://authorized-weather-feed/east-rainfall",
            experimentability="external_or_observational",
            unit="rainfall_index",
        ),
        factor(
            "quality.event_late_arrival_rate",
            kind="data_quality",
            scope_id="tracking-east-paid",
            values=[
                0.004 + pulse(day, 37, 41, 0.018) + pulse(day, 52, 56, 0.021)
                for day in days
            ],
            scope_match=0.63,
            source_reliability=0.79,
            source_uri="fixture://internal-data-quality/event-late-arrival",
            experimentability="diagnostic_or_unknown",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "quality.tracking_gap_rate",
            kind="data_quality",
            scope_id="tracking-east-paid",
            values=[
                0.006 + (0.019 if day >= 37 else 0.0) + (0.012 if day >= 52 else 0.0)
                for day in days
            ],
            scope_match=0.60,
            source_reliability=0.77,
            source_uri="fixture://internal-data-quality/tracking-gap",
            experimentability="diagnostic_or_unknown",
            unit="rate",
            target=target_scope,
        ),
        factor(
            "quality.identity_stitch_drop_rate",
            kind="data_quality",
            scope_id="identity-east-paid",
            values=[
                0.002 + pulse(day, 38, 42, 0.009) + pulse(day, 52, 57, 0.017)
                for day in days
            ],
            scope_match=0.57,
            source_reliability=0.75,
            source_uri="fixture://internal-data-quality/identity-stitch",
            experimentability="diagnostic_or_unknown",
            unit="rate",
            target=target_scope,
        ),
    ]
    factor_series.extend(
        [
            factor(
                "internal.quote_form_step_count",
                kind="funnel_friction",
                scope_id="form-east-paid-8.4",
                values=[
                    7.0 + (1.0 if day >= 37 else 0.0) + pulse(day, 52, 56, 1.0)
                    for day in days
                ],
                scope_match=0.82,
                source_reliability=0.86,
                source_uri="fixture://internal-product-analytics/quote-form-step-count",
                experimentability="controllable",
                unit="steps",
                target=target_scope,
            ),
            factor(
                "internal.document_upload_failure_rate",
                kind="document_capture",
                scope_id="docs-east-paid",
                values=[
                    0.010 + pulse(day, 37, 42, 0.018) + pulse(day, 52, 57, 0.022)
                    for day in days
                ],
                scope_match=0.78,
                source_reliability=0.84,
                source_uri="fixture://internal-product-analytics/document-upload",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.esign_redirect_exit_rate",
                kind="signature_friction",
                scope_id="esign-east-paid",
                values=[
                    0.024 + (0.017 if day >= 40 else 0.0) + pulse(day, 52, 56, 0.011)
                    for day in days
                ],
                scope_match=0.73,
                source_reliability=0.82,
                source_uri="fixture://internal-product-analytics/esign-redirect-exit",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.coverage_comparison_confusion_rate",
                kind="product_comprehension",
                scope_id="coverage-east-paid-8.4",
                values=[
                    0.18
                    + 0.002 * day
                    + pulse(day, 36, 42, 0.055)
                    + pulse(day, 52, 56, 0.040)
                    for day in days
                ],
                scope_match=0.79,
                source_reliability=0.80,
                source_uri="fixture://internal-product-analytics/coverage-comparison",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.price_explanation_view_gap_rate",
                kind="price_transparency",
                scope_id="pricing-east-paid",
                values=[
                    0.11 + (0.052 if day >= 38 else 0.0) + 0.001 * (day % 9)
                    for day in days
                ],
                scope_match=0.76,
                source_reliability=0.78,
                source_uri="fixture://internal-product-analytics/price-explanation",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.prefill_success_rate",
                kind="prefill_quality",
                scope_id="prefill-east-paid",
                values=[
                    0.84
                    - pulse(day, 37, 42, 0.09)
                    - pulse(day, 52, 56, 0.12)
                    - 0.0005 * day
                    for day in days
                ],
                scope_match=0.74,
                source_reliability=0.83,
                source_uri="fixture://internal-product-analytics/prefill-success",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.agent_contact_answer_rate",
                kind="sales_ops",
                scope_id="crm-east-paid",
                values=[
                    0.62
                    - pulse(day, 39, 43, 0.08)
                    - pulse(day, 52, 57, 0.11)
                    + 0.002 * (day % 6)
                    for day in days
                ],
                scope_match=0.69,
                source_reliability=0.81,
                source_uri="fixture://internal-crm/contact-answer-rate",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "internal.underwriting_referral_rate",
                kind="underwriting_workflow",
                scope_id="uw-east-paid",
                values=[
                    0.075 + pulse(day, 37, 41, 0.025) + pulse(day, 51, 56, 0.038)
                    for day in days
                ],
                scope_match=0.67,
                source_reliability=0.80,
                source_uri="fixture://internal-underwriting/referral-rate",
                experimentability="controllable",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "external.aggregator_rank_drop_index",
                kind="aggregator_marketplace",
                scope_id="aggregator-east-paid",
                values=[
                    0.10 + pulse(day, 36, 42, 1.05) + pulse(day, 51, 56, 0.72)
                    for day in days
                ],
                scope_match=0.59,
                source_reliability=0.66,
                source_uri="fixture://authorized-aggregator-feed/rank-drop",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "external.competitor_quote_speed_index",
                kind="competitor_experience",
                scope_id="competitor-digital-east",
                values=[
                    55.0
                    + 0.10 * day
                    + pulse(day, 36, 42, 18.0)
                    + pulse(day, 51, 56, 24.0)
                    for day in days
                ],
                scope_match=0.57,
                source_reliability=0.64,
                source_uri="fixture://authorized-competitor-benchmark/quote-speed",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "external.ad_auction_pressure_paid_search",
                kind="paid_media_market",
                scope_id="paid-search-east",
                values=[
                    1.2
                    + 0.01 * day
                    + pulse(day, 37, 41, 0.42)
                    + pulse(day, 52, 56, 0.38)
                    for day in days
                ],
                scope_match=0.63,
                source_reliability=0.67,
                source_uri="fixture://authorized-ad-intelligence/paid-search-pressure",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "external.review_sentiment_negative_index",
                kind="brand_trust",
                scope_id="brand-east",
                values=[
                    12.0
                    + 0.04 * day
                    + pulse(day, 39, 45, 4.4)
                    + pulse(day, 52, 56, 2.8)
                    for day in days
                ],
                scope_match=0.49,
                source_reliability=0.61,
                source_uri="fixture://authorized-review-feed/negative-sentiment",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "external.travel_seasonality_index",
                kind="seasonality",
                scope_id="travel-east",
                values=[
                    18.0
                    + 0.2 * (day % 7)
                    + pulse(day, 36, 41, 8.0)
                    + pulse(day, 51, 56, 6.0)
                    for day in days
                ],
                scope_match=0.44,
                source_reliability=0.72,
                source_uri="fixture://authorized-calendar-feed/travel-seasonality",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "external.mobile_network_outage_index",
                kind="infrastructure_external",
                scope_id="mobile-network-east",
                values=[
                    0.0 + pulse(day, 37, 40, 0.9) + pulse(day, 53, 55, 1.2)
                    for day in days
                ],
                scope_match=0.48,
                source_reliability=0.74,
                source_uri="fixture://authorized-network-status/east-outage",
                experimentability="external_or_observational",
                unit="index",
            ),
            factor(
                "quality.consent_event_loss_rate",
                kind="data_quality",
                scope_id="consent-east-paid",
                values=[
                    0.003 + pulse(day, 37, 42, 0.016) + pulse(day, 52, 56, 0.014)
                    for day in days
                ],
                scope_match=0.55,
                source_reliability=0.76,
                source_uri="fixture://internal-data-quality/consent-event-loss",
                experimentability="diagnostic_or_unknown",
                unit="rate",
                target=target_scope,
            ),
            factor(
                "quality.utm_attribution_null_rate",
                kind="data_quality",
                scope_id="utm-east-paid",
                values=[
                    0.018 + pulse(day, 36, 42, 0.034) + pulse(day, 51, 56, 0.026)
                    for day in days
                ],
                scope_match=0.52,
                source_reliability=0.74,
                source_uri="fixture://internal-data-quality/utm-null-rate",
                experimentability="diagnostic_or_unknown",
                unit="rate",
                target=target_scope,
            ),
        ]
    )
    events = [
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
            "factor_id": "internal.vendor.sms_provider_switch",
            "source_type": "internal_event",
            "kind": "vendor_change",
            "start_day": 52,
            "end_day": 52,
            "scope_match": 0.72,
            "source_reliability": 0.82,
            "source_uri": "fixture://internal-vendor/sms-provider-switch",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "internal.payment_gateway_maintenance",
            "source_type": "internal_event",
            "kind": "payment_maintenance",
            "start_day": 54,
            "end_day": 55,
            "scope_match": 0.76,
            "source_reliability": 0.84,
            "source_uri": "fixture://internal-change-log/payment-maintenance",
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
        {
            "factor_id": "external.competitor_price_drop",
            "source_type": "external_event",
            "kind": "competitor_pricing",
            "start_day": 48,
            "end_day": 56,
            "scope_match": 0.58,
            "source_reliability": 0.67,
            "source_uri": "fixture://authorized-pricing-feed/competitor-price-drop",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "external.broker_affiliate_push",
            "source_type": "external_event",
            "kind": "partner_channel",
            "start_day": 36,
            "end_day": 41,
            "scope_match": 0.54,
            "source_reliability": 0.62,
            "source_uri": "fixture://authorized-market-feed/broker-affiliate-push",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "external.market_rate_announcement",
            "source_type": "external_event",
            "kind": "macro_rate",
            "start_day": 50,
            "end_day": 50,
            "scope_match": 0.50,
            "source_reliability": 0.70,
            "source_uri": "fixture://authorized-macro-feed/market-rate-announcement",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "quality.tracking_schema_gap",
            "source_type": "internal_event",
            "kind": "data_quality",
            "start_day": 38,
            "end_day": 41,
            "scope_match": 0.58,
            "source_reliability": 0.78,
            "source_uri": "fixture://internal-data-quality/schema-gap",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "internal.pricing_rule_hotfix",
            "source_type": "internal_event",
            "kind": "pricing_config",
            "start_day": 37,
            "end_day": 37,
            "scope_match": 0.68,
            "source_reliability": 0.81,
            "source_uri": "fixture://internal-pricing/config-hotfix",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "internal.underwriting_rule_queue_change",
            "source_type": "internal_event",
            "kind": "underwriting_workflow",
            "start_day": 53,
            "end_day": 54,
            "scope_match": 0.65,
            "source_reliability": 0.80,
            "source_uri": "fixture://internal-underwriting/rule-queue-change",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "external.aggregator_homepage_slot_loss",
            "source_type": "external_event",
            "kind": "aggregator_marketplace",
            "start_day": 36,
            "end_day": 41,
            "scope_match": 0.55,
            "source_reliability": 0.63,
            "source_uri": "fixture://authorized-aggregator-feed/homepage-slot-loss",
            "license_ref": "fixture-only",
        },
        {
            "factor_id": "external.negative_review_wave",
            "source_type": "external_event",
            "kind": "brand_trust",
            "start_day": 39,
            "end_day": 45,
            "scope_match": 0.45,
            "source_reliability": 0.60,
            "source_uri": "fixture://authorized-review-feed/negative-wave",
            "license_ref": "fixture-only",
        },
    ]
    association = discover_association_factors(
        panel["days"],
        demo["series"]["residual"],
        anomaly_windows,
        events=events,
        max_lag=14,
        discovery_days=list(range(50)),
        holdout_days=list(range(50, 60)),
        factor_series=factor_series,
        bootstrap_reps=49,
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
        "internal.quote_api_timeout_rate": (
            "报价 API 超时率",
            "内部可观测性中的报价接口超时比例",
        ),
        "internal.payment_retry_rate": ("支付重试率", "支付链路中需要重试的交易比例"),
        "internal.form_validation_error_rate": (
            "表单校验错误率",
            "前端表单校验失败或阻断比例",
        ),
        "internal.agent_followup_sla_hours": ("顾问跟进 SLA", "CRM 中销售跟进平均耗时"),
        "internal.sms_delivery_failure_rate": (
            "短信送达失败率",
            "短信供应商链路的送达失败比例",
        ),
        "internal.premium_quote_cache_miss_rate": (
            "保费报价缓存未命中",
            "报价缓存未命中比例",
        ),
        "internal.channel_bid_cpc": ("付费渠道 CPC", "内部投放系统记录的点击成本"),
        "internal.app_crash_rate": ("客户端崩溃率", "App 端会话崩溃比例"),
        "internal.quote_form_step_count": (
            "报价表单步骤数",
            "报价到投保路径中的表单步骤数量",
        ),
        "internal.document_upload_failure_rate": (
            "资料上传失败率",
            "投保资料上传失败或重传比例",
        ),
        "internal.esign_redirect_exit_rate": (
            "电子签跳出率",
            "电子签名重定向后退出比例",
        ),
        "internal.coverage_comparison_confusion_rate": (
            "保障责任对比困惑率",
            "保障责任对比页中的困惑或反复查看比例",
        ),
        "internal.price_explanation_view_gap_rate": (
            "价格解释缺口率",
            "报价解释模块未被有效查看或理解的比例",
        ),
        "internal.prefill_success_rate": ("资料预填成功率", "投保表单资料预填成功比例"),
        "internal.agent_contact_answer_rate": (
            "顾问接通率",
            "CRM 外呼或在线顾问联系成功比例",
        ),
        "internal.underwriting_referral_rate": (
            "核保转人工率",
            "自动核保转人工或排队的比例",
        ),
        "internal.vendor.sms_provider_switch": (
            "短信供应商切换",
            "供应商路由或服务商切换事件",
        ),
        "internal.payment_gateway_maintenance": (
            "支付通道维护",
            "支付网关维护或限流窗口",
        ),
        "internal.pricing_rule_hotfix": ("定价规则热修", "定价或费率配置热修事件"),
        "internal.underwriting_rule_queue_change": (
            "核保队列规则变更",
            "核保规则或队列策略调整事件",
        ),
        "external.competitor_campaign_intensity": (
            "竞品活动强度",
            "授权外部源构造的竞品活动强度序列",
        ),
        "external.regulatory_notice_density": (
            "监管通知密度",
            "公开或授权政策源中的保险相关通知密度",
        ),
        "external.search_trend_insurance": (
            "保险搜索热度",
            "授权搜索趋势中的保险意图指数",
        ),
        "external.market_rate_index": (
            "市场利率指数",
            "授权宏观源中的市场利率压力指标",
        ),
        "external.macro_consumer_confidence": (
            "消费者信心指数",
            "授权宏观源中的需求信心指标",
        ),
        "external.weather_rainfall_index": (
            "东区降雨指数",
            "授权天气源中的区域降雨强度",
        ),
        "external.aggregator_rank_drop_index": (
            "聚合平台排名下滑",
            "授权聚合平台源中的排名或展示位下滑指数",
        ),
        "external.competitor_quote_speed_index": (
            "竞品报价速度指数",
            "授权竞品体验基准中的报价速度优势指数",
        ),
        "external.ad_auction_pressure_paid_search": (
            "付费搜索竞价压力",
            "授权广告情报源中的付费搜索竞价压力",
        ),
        "external.review_sentiment_negative_index": (
            "负面评价情绪指数",
            "授权评价源中的负面情绪波动",
        ),
        "external.travel_seasonality_index": (
            "出行季节性指数",
            "日历和需求源中的出行季节性强度",
        ),
        "external.mobile_network_outage_index": (
            "移动网络故障指数",
            "区域移动网络或基础设施异常强度",
        ),
        "external.competitor_price_drop": (
            "竞品价格下调",
            "授权价格源观察到的竞品报价下调窗口",
        ),
        "external.broker_affiliate_push": (
            "经纪渠道集中投放",
            "公开或授权市场源观察到的经纪渠道投放",
        ),
        "external.market_rate_announcement": (
            "市场利率公告",
            "授权宏观源中的利率公告事件",
        ),
        "external.aggregator_homepage_slot_loss": (
            "聚合首页展位丢失",
            "授权聚合平台源观察到的展位变化事件",
        ),
        "external.negative_review_wave": (
            "负面评价集中波动",
            "授权评价源观察到的负面评价集中窗口",
        ),
        "quality.event_late_arrival_rate": (
            "事件迟到率",
            "内部数据质量监控中的事件延迟到达比例",
        ),
        "quality.tracking_gap_rate": ("埋点缺口率", "内部数据质量监控中的埋点缺口比例"),
        "quality.identity_stitch_drop_rate": (
            "身份拼接掉线率",
            "内部身份拼接链路的匹配掉线比例",
        ),
        "quality.tracking_schema_gap": (
            "埋点 Schema 缺口",
            "埋点字段或版本不一致的质量事件",
        ),
        "quality.consent_event_loss_rate": (
            "同意授权事件丢失率",
            "授权同意事件在采集链路中的丢失比例",
        ),
        "quality.utm_attribution_null_rate": (
            "UTM 归因空值率",
            "付费流量归因参数缺失或无法归属比例",
        ),
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
        factor_library = retrieve_factor_candidates(store, "", limit=40)
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
                "factor_parents": len(factor_series) + len(events),
                "derived_layers": len(
                    association["search_manifest"].get("derived_layers", [])
                ),
                "factor_snapshots": len(factor_series) * len(panel["days"]),
                "internal_events": len(registry)
                + sum(
                    1 for event in events if event["source_type"] == "internal_event"
                ),
                "external_events": len(external)
                + sum(
                    1 for event in events if event["source_type"] == "external_event"
                ),
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
    from goai_control_tower.track2 import (
        case_experiment_metadata,
        default_metric_contract,
        generate_dataset,
    )
    from goai_control_tower.track2_analysis import sanitize_rows
    from goai_control_tower.track2_v5_bridge import evaluate_with_bayes

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
        "evidence_pointer": "GET /api/track2/bayes-case?case=A",
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
            "shrinkage_strength_trajectory": result["adaptive_experience_store"][
                "shrinkage_strength_trajectory"
            ],
        },
        "key_outputs": {"store_final": result["store_final"], "note": result["note"]},
        "evidence_pointer": "outputs/experience_ablation.json",
    }


_RUNNERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "full_review": _scenario_full_review,
    "line_a": _scenario_line_a,
    "line_b": _scenario_line_b,
    "company_line_b": _scenario_company_line_b,
    "external": _scenario_external,
    "bayes_case_a": _scenario_bayes_case_a,
    "experience": _scenario_experience,
}

_SCENARIO_CLAIMS = {
    "full_review": "MULTI_ROUTE_REVIEW",
    "line_a": "CAUSAL_READY",
    "line_b": "FACTOR_CANDIDATE / TEMPORAL_ASSOCIATION",
    "company_line_b": "FACTOR_CANDIDATE / TEMPORAL_ASSOCIATION",
    "external": "TEMPORAL_ASSOCIATION + UNEXPLAINED",
    "bayes_case_a": "REFUSED",
    "experience": "EXPERIENCE_ABLATION",
}


def read_run(runtime_dir: Path, run_id: str) -> dict[str, Any]:
    """Load immutable evidence by run id; independent of any console route."""
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("invalid run_id")
    from .publication import govern_output

    return govern_output(
        json.loads(
            (Path(runtime_dir) / "runs" / f"{run_id}.json").read_text(encoding="utf-8")
        )
    )


def run_scenario(scenario_id: str, runtime_dir: Path | None = None) -> dict[str, Any]:
    from .publication import govern_output

    if scenario_id not in _RUNNERS:
        raise KeyError(f"unknown scenario: {scenario_id}")
    runtime_dir = Path(runtime_dir or (WORKSPACE / "runtime_data"))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cache_key = (scenario_id, str(runtime_dir.resolve()))
    cacheable = scenario_id not in {"experience", "company_line_b"}
    cached = _SCENARIO_CACHE.get(cache_key) if cacheable else None
    if cached is not None:
        result = copy.deepcopy(cached)
        result.update(
            served_at=datetime.now(UTC).isoformat(),
            cache_hit=True,
            real_run=False,
            runtime_seconds=round(time.time() - t0, 3),
        )
        return govern_output(result)
    from .contracts import digest
    from .persistence import atomic_json

    body = govern_output(_RUNNERS[scenario_id](runtime_dir))
    title = next(s["title"] for s in SCENARIOS if s["id"] == scenario_id)
    now = datetime.now(UTC).isoformat()
    run_id = uuid.uuid4().hex
    result = {
        **body,
        "scenario": scenario_id,
        "title": title,
        "generated_at": now,
        "computed_at": now,
        "served_at": now,
        "runtime_seconds": round(time.time() - t0, 3),
        "real_run": True,
        "cache_hit": False,
        "run_id": run_id,
        "execution_mode": body.get("execution_mode", "deterministic_fixture"),
        "claim": body.get("claim") or _SCENARIO_CLAIMS[scenario_id],
        "evidence": body.get("evidence") or body.get("evidence_pointer"),
        "run_evidence_path": str((runtime_dir / "runs" / f"{run_id}.json").resolve()),
        "result_digest": digest(body),
    }
    result = govern_output(result)
    result["result_digest"] = digest(
        {k: v for k, v in result.items() if k != "result_digest"}
    )
    atomic_json(runtime_dir / "runs" / f"{run_id}.json", result)
    if cacheable:
        _SCENARIO_CACHE[cache_key] = copy.deepcopy(result)
    return result


def render_markdown(report: dict[str, Any]) -> str:
    from .publication import govern_output

    report = govern_output(report)
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


def run_causal_investigation(
    request, runtime_dir=None, *, timeout=60, baseline_bytes=None
):
    """Authoritative backend entry: isolated stages and a persistent evidence ledger."""
    from .agent_orchestrator import run_pipeline
    from .hypothesis_registry import HypothesisRegistry
    from .persistence import atomic_json
    from .publication import persist_publication

    runtime_dir = Path(runtime_dir or (WORKSPACE / "runtime_data"))
    run_id = uuid.uuid4().hex
    path = runtime_dir / "runs" / f"{run_id}.json"
    report = run_pipeline(request, timeout=timeout, baseline_bytes=baseline_bytes)
    registry = HypothesisRegistry(runtime_dir / "hypotheses.sqlite3")
    try:
        source = registry.add_asset("data", request)
        report["data_ref"] = source
        if report["execution_status"] == "COMPLETED":
            final = report["records"][-1]["output"]["result"]
            evidence = registry.record_result(
                final, dependencies=[source], operation="effect"
            )
            report.update(
                persist_publication(
                    registry,
                    final["contracts"],
                    dependencies=[evidence],
                    **request.get("publication_options", {}),
                )
            )
        report["registry_path"] = str(Path(registry.path).resolve())
    finally:
        registry.close()
    report["run_id"] = run_id
    from .contracts import digest

    report["digest"] = digest({k: v for k, v in report.items() if k != "digest"})
    atomic_json(path, report)
    return report
