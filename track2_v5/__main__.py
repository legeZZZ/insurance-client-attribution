"""End-to-end demo: carousel CTR anomaly -> factors -> bundle A/B -> HTE
-> factorial design -> component effects -> Claim Ledger decision."""

from __future__ import annotations

import json
import random
from pathlib import Path

from .bayes import bundle_compare, estimate_high_dimensional_hte, estimate_hte
from .claim_ledger import ClaimLedger
from .experiment_designer import design_experiment, estimate_component_effects
from .factor_miner import mine_factors
from .insursim_carousel import generate_bundle_stage, generate_factorial_stage, sanitize
from .spec import load_spec, spec_diff
from .track2_benchmark import run_benchmark

SPECS_DIR = Path(__file__).resolve().parent.parent / "specs"


def _build_a_line_funnel(rows: list[dict], seed: int) -> dict:
    """Build a deterministic exposure-to-policy funnel from experiment rows."""
    rng = random.Random(seed + 4242)
    arms = {
        0: {
            "id": "control",
            "label": "Control · 旧版轮播",
            "component_version": "carousel.v1",
            "exposures": 0,
            "reach": 0,
            "click": 0,
            "quote": 0,
            "issue": 0,
        },
        1: {
            "id": "treatment",
            "label": "Treatment · 新版轮播",
            "component_version": "carousel.v2",
            "exposures": 0,
            "reach": 0,
            "click": 0,
            "quote": 0,
            "issue": 0,
        },
    }
    for row in rows:
        arm = arms[int(row["treatment"])]
        arm["exposures"] += 1
        reached = rng.random() < (0.965 - 0.018 * int(row["treatment"]))
        if not reached:
            continue
        arm["reach"] += 1
        if not row["clicked"]:
            continue
        arm["click"] += 1
        quote_probability = max(
            0.42,
            0.72
            - 0.08 * float(row["quote_complexity_score"])
            - 0.06 * int(row["treatment"])
            - 0.04 * int(row["image_load_failure"]),
        )
        if rng.random() >= quote_probability:
            continue
        arm["quote"] += 1
        issue_probability = max(
            0.24,
            0.46
            - 0.05 * float(row["price_sensitivity_score"])
            - 0.04 * int(row["treatment"])
            - 0.03 * (float(row["render_latency_ms"]) > 180),
        )
        if rng.random() < issue_probability:
            arm["issue"] += 1

    def rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 6) if denominator else 0.0

    stage_specs = (
        ("exposure", "曝光", "exposures", None),
        ("reach", "到达", "reach", "exposures"),
        ("click", "点击", "click", "exposures"),
        ("quote", "报价", "quote", "click"),
        ("issue", "投保", "issue", "quote"),
    )
    stages = []
    for stage_id, label, field, denominator in stage_specs:
        control = arms[0][field]
        treatment = arms[1][field]
        control_rate = rate(control, arms[0][denominator]) if denominator else 1.0
        treatment_rate = rate(treatment, arms[1][denominator]) if denominator else 1.0
        stages.append(
            {
                "id": stage_id,
                "label": label,
                "control": control,
                "treatment": treatment,
                "control_rate": control_rate,
                "treatment_rate": treatment_rate,
                "delta": round(treatment_rate - control_rate, 6),
            }
        )
    for arm in arms.values():
        arm["ctr"] = rate(arm["click"], arm["exposures"])
        arm["reach_rate"] = rate(arm["reach"], arm["exposures"])
        arm["quote_rate_from_click"] = rate(arm["quote"], arm["click"])
        arm["issue_rate_from_quote"] = rate(arm["issue"], arm["quote"])

    return {
        "window": {"start_day": 60, "end_day": 73},
        "metric": "carousel_ctr",
        "estimand": "treatment-control rate difference",
        "stages": stages,
        "arms": list(arms.values()),
        "evidence_level": "CAUSAL_READY",
        "fixture_note": "后续报价与投保阶段由同一随机化曝光 fixture 按固定规则生成，用于演示漏斗分析。",
    }


def run_demo(seed: int = 20260809) -> dict:
    ledger = ClaimLedger()

    # 1. Anomaly observed; lock the metric contract (reference, not re-derived).
    ledger.add_claim(
        "ASSOCIATION_ONLY",
        "新轮播样式上线后 CTR 由 4.1% 降至 3.2%，与样式变更同时出现。",
    )

    # 2. Spec diff + factor mining.
    spec_v1 = load_spec(SPECS_DIR / "carousel_spec_v1.json")
    spec_v2 = load_spec(SPECS_DIR / "carousel_spec_v2.json")
    diff_factors = spec_diff(spec_v1, spec_v2)

    rows_all, truth = generate_bundle_stage(seed=seed)
    rows = sanitize(rows_all)
    mid = len(rows) // 2
    discovery_rows, estimation_rows = rows[:mid], rows[mid:]
    mined = mine_factors(
        rows_baseline=[r for r in discovery_rows if r["treatment"] == 0],
        rows_current=discovery_rows,
        treatment_column="treatment",
        outcome_column="clicked",
        context_fields=("device_low_end", "user_new_old", "channel", "placement"),
        spec_old=spec_v1,
        spec_new=spec_v2,
        runtime_control={"media_load_success_rate": 0.98, "render_latency_ms": 120.0},
        runtime_treatment={"media_load_success_rate": 0.86, "render_latency_ms": 185.0},
        practical_threshold=0.005,
        seed=seed,
    )
    ledger.add_claim(
        "FACTOR_CANDIDATE", f"FactorMiner 输出 {mined['candidate_count']} 个候选因子。"
    )
    ledger.transition("FACTORS_DISCOVERED")

    # 3. Bundle A/B on the held-out estimation half.
    control = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 0),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 0),
    }
    treatment = {
        "clicks": sum(r["clicked"] for r in estimation_rows if r["treatment"] == 1),
        "impressions": sum(1 for r in estimation_rows if r["treatment"] == 1),
    }
    bundle = bundle_compare(control, treatment, practical_threshold=0.005, seed=seed)
    from .publication import govern_output
    from .quant_track import estimate_randomized_effect

    metric = {
        "name": "carousel_ctr",
        "numerator": "clicks",
        "denominator": "exposures",
        "aggregation": "ratio_of_sums",
        "unit": "rate",
        "analysis_unit": "exposure",
        "target_population": "fixture_eligible_exposures",
        "timezone": "UTC",
        "window": [60, 73],
        "maturity_days": 0,
        "deduplication": "unit_id",
    }
    qualified = estimate_randomized_effect(
        [
            {"unit_id": i, "treatment": r["treatment"], "outcome": r["clicked"]}
            for i, r in enumerate(estimation_rows)
        ],
        metric,
        assignment_ref="insursim:generate_bundle_stage",
        randomized=True,
        observed_through=73,
        no_interference_ref="insursim:independent_exposure_generator",
        seed=seed,
    )
    bundle["contracts"] = qualified["contracts"]
    ledger.transition("BUNDLE_EXPERIMENT_READY")
    ledger.add_claim(
        "BUNDLE_EFFECT",
        f"新轮播整套样式在本实验中使 CTR 变化 {bundle['effect_absolute']:.4f}"
        f"（P(实际损害)={bundle['probability_practical_harm']:.3f}）。",
        estimand="ITT on qualified CTR",
        contracts=qualified["contracts"],
        posterior_probability=bundle["probability_practical_harm"],
        credible_interval=bundle["credible_interval_95"],
        practical_threshold=0.005,
    )
    ledger.transition("BUNDLE_EFFECT_ESTIMATED")

    # 4. HTE with partial pooling plus high-dimensional overlapping CATE.
    segments = []
    for value in (0, 1):
        subset = [r for r in estimation_rows if r["device_low_end"] == value]
        segments.append(
            {
                "segment_id": f"device_low_end={value}",
                "control": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 0),
                    "impressions": sum(1 for r in subset if r["treatment"] == 0),
                },
                "treatment": {
                    "clicks": sum(r["clicked"] for r in subset if r["treatment"] == 1),
                    "impressions": sum(1 for r in subset if r["treatment"] == 1),
                },
            }
        )
    hte = estimate_hte(segments, practical_threshold=0.01, seed=seed, discovery=False)
    hdim_hte = estimate_high_dimensional_hte(
        estimation_rows,
        treatment_column="treatment",
        outcome_column="clicked",
        feature_columns=(
            "device_low_end",
            "user_new_old",
            "channel",
            "placement",
            "session_depth",
            "prior_quote_count",
            "quote_complexity_score",
            "price_sensitivity_score",
            "coverage_need_score",
            "lead_quality_score",
            "network_quality_score",
            "market_pressure_index",
            "ad_auction_pressure_index",
            "competitor_quote_speed_index",
            "fx_rate_pressure_index",
            "regulatory_attention_index",
            "quote_form_step_count",
            "baseline_latency_risk",
            "premium_index",
        ),
        continuous_features=(
            "session_depth",
            "prior_quote_count",
            "quote_complexity_score",
            "price_sensitivity_score",
            "coverage_need_score",
            "lead_quality_score",
            "network_quality_score",
            "market_pressure_index",
            "ad_auction_pressure_index",
            "competitor_quote_speed_index",
            "fx_rate_pressure_index",
            "regulatory_attention_index",
            "quote_form_step_count",
            "baseline_latency_risk",
            "premium_index",
        ),
        subgroup_rules=(
            {
                "subgroup_id": "low_end_device",
                "label": "低端设备",
                "condition": {"device_low_end": 1},
            },
            {
                "subgroup_id": "paid_market_pressure",
                "label": "付费渠道 × 竞价/竞品压力高",
                "condition": {
                    "channel": "paid",
                    "market_pressure_index": {"min": 0.55},
                },
            },
            {
                "subgroup_id": "complex_quote_path",
                "label": "报价复杂 × 表单步骤多",
                "condition": {
                    "quote_complexity_score": {"min": 0.62},
                    "quote_form_step_count": {"min": 6},
                },
            },
            {
                "subgroup_id": "price_sensitive_new_users",
                "label": "新客 × 价格敏感",
                "condition": {
                    "user_new_old": "new",
                    "price_sensitivity_score": {"min": 0.58},
                },
            },
            {
                "subgroup_id": "weak_network_high_complexity",
                "label": "弱网络 × 高复杂报价",
                "condition": {
                    "network_quality_score": {"max": 0.58},
                    "quote_complexity_score": {"min": 0.60},
                },
            },
            {
                "subgroup_id": "external_pressure_combo",
                "label": "外部压力 × 内部摩擦组合",
                "condition": {
                    "competitor_quote_speed_index": {"min": 0.46},
                    "quote_form_step_count": {"min": 6},
                },
            },
            {
                "subgroup_id": "regulatory_price_attention",
                "label": "监管关注 × 价格敏感",
                "condition": {
                    "regulatory_attention_index": {"min": 0.22},
                    "price_sensitivity_score": {"min": 0.56},
                },
            },
        ),
        practical_threshold=0.01,
        seed=seed,
    )
    worst = min(hte["segments"], key=lambda s: s["effect_shrunk"])
    worst_overlap = min(hdim_hte["subgroups"], key=lambda s: s["effect_shrunk"])
    ledger.add_claim(
        "HETEROGENEOUS_TREATMENT_EFFECT",
        f"低端设备分群负向效应最大（收缩后 {worst['effect_shrunk']:.4f}）。",
        estimand="HTE by device_low_end",
        selected_after_seeing_outcome=True,
    )
    ledger.add_claim(
        "EXPLORATORY_HETEROGENEITY",
        "高维重叠 HTE 显示 "
        f"{worst_overlap['label']} 的 CATE 更差"
        f"（重叠校正后 {worst_overlap['effect_shrunk']:.4f}）。",
        estimand="cross-fit CATE over pre-treatment continuous/categorical features",
        selected_after_seeing_outcome=True,
    )
    ledger.transition("HETEROGENEITY_RANKED")

    # 5. Factorial experiment design + simulated execution.
    factor_ids = [f["factor_id"] for f in diff_factors][:5]
    design = design_experiment(factor_ids, traffic_budget=80_000)
    ledger.transition("COMPONENT_EXPERIMENT_DESIGNED")
    arm_rows = generate_factorial_stage(seed=seed, arms=design["arms"])
    effects = estimate_component_effects(arm_rows, design["arms"], factor_ids)
    a_line_funnel = _build_a_line_funnel(estimation_rows, seed)
    a_line_funnel["overlap_subgroups"] = hdim_hte["diagnostics"][
        "overlapping_subgroup_count"
    ]
    design_record = {
        "independent_randomization": True,
        "assignment_provenance": "experiment_platform",
        "design_code_traceable": True,
        "stable_randomization_unit": True,
    }
    for item in effects:
        if item["significant"] and ledger.can_promote_to_component_effect(
            design_record
        ):
            ledger.add_claim(
                "COMPONENT_EFFECT",
                f"独立随机化显示 {item['factor_id']} 的组件级效应为 {item['component_effect']:.4f}。",
                estimand="Component ATE",
                credible_interval=None,
                design_record=design_record,
            )
        else:
            ledger.add_claim(
                "EXPERIMENT_INCONCLUSIVE",
                f"{item['factor_id']} 未达到组件级证据标准。",
            )
    ledger.transition("COMPONENT_EFFECT_ESTIMATED")
    ledger.transition("POSTERIOR_UPDATED")
    ledger.transition("DECISION_READY")

    return govern_output(
        {
            "bundle": bundle,
            "oracle_bundle_ate": truth["oracle_bundle_ate"],
            "mined_top5": mined["candidates"][:5],
            "hte": hte,
            "high_dimensional_hte": hdim_hte,
            "design": {
                "design_type": design["design_type"],
                "arm_count": design["arm_count"],
                "design_diagnostics": design["design_diagnostics"],
            },
            "component_effects": effects,
            "a_line_funnel": a_line_funnel,
            "ledger": ledger.render(),
        }
    )


def main() -> None:
    demo = run_demo()
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "demo_evidence.json").write_text(
        json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bench = run_benchmark()
    (out_dir / "benchmark_metrics.json").write_text(
        json.dumps(bench, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "bundle_decision": demo["bundle"]["decision"],
                "bundle_effect": demo["bundle"]["effect_absolute"],
                "oracle_ate": demo["oracle_bundle_ate"],
                "ledger_state": demo["ledger"]["state"],
                "claim_types": [c["claim_type"] for c in demo["ledger"]["claims"]],
                "hte_model": demo["high_dimensional_hte"]["model"],
                "overlap_subgroups": demo["high_dimensional_hte"]["diagnostics"][
                    "overlapping_subgroup_count"
                ],
                "benchmark_matched": bench["matched_regime"],
                "benchmark_mismatched": bench["mismatched_regime"],
                "evidence_files": [
                    str(out_dir / "demo_evidence.json"),
                    str(out_dir / "benchmark_metrics.json"),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
