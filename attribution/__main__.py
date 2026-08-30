"""End-to-end demo: carousel CTR anomaly -> factors -> bundle A/B -> HTE
-> factorial design -> component effects -> Claim Ledger decision."""

from __future__ import annotations

import json
from pathlib import Path

from .bayes import bundle_compare, estimate_hte
from .benchmark import run_benchmark
from .claim_ledger import ClaimLedger
from .experiment_designer import design_experiment, estimate_component_effects
from .factor_miner import mine_factors
from .insursim_carousel import generate_bundle_stage, generate_factorial_stage, sanitize
from .spec import load_spec, spec_diff

SPECS_DIR = Path(__file__).resolve().parent.parent / "specs"


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
    ledger.add_claim(
        "BUNDLE_EFFECT",
        f"新轮播整套样式在本实验中使 CTR 变化 {bundle['effect_absolute']:.4f}"
        f"（P(实际损害)={bundle['probability_practical_harm']:.3f}）。",
        estimand="ITT on qualified CTR",
        posterior_probability=bundle["probability_practical_harm"],
        credible_interval=bundle["credible_interval_95"],
        practical_threshold=0.005,
    )
    ledger.transition("BUNDLE_EFFECT_ESTIMATED")

    # 4. HTE with partial pooling.
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
    worst = min(hte["segments"], key=lambda s: s["effect_shrunk"])
    ledger.add_claim(
        "HETEROGENEOUS_TREATMENT_EFFECT",
        f"低端设备分群负向效应最大（收缩后 {worst['effect_shrunk']:.4f}）。",
        estimand="HTE by device_low_end",
    )
    ledger.transition("HETEROGENEITY_RANKED")

    # 5. Factorial experiment design + simulated execution.
    factor_ids = [f["factor_id"] for f in diff_factors][:5]
    design = design_experiment(factor_ids, traffic_budget=80_000)
    ledger.transition("COMPONENT_EXPERIMENT_DESIGNED")
    arm_rows = generate_factorial_stage(seed=seed, arms=design["arms"])
    effects = estimate_component_effects(arm_rows, design["arms"], factor_ids)
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
            )
        else:
            ledger.add_claim(
                "EXPERIMENT_INCONCLUSIVE",
                f"{item['factor_id']} 未达到组件级证据标准。",
            )
    ledger.transition("COMPONENT_EFFECT_ESTIMATED")
    ledger.transition("POSTERIOR_UPDATED")
    ledger.transition("DECISION_READY")

    return {
        "bundle": bundle,
        "oracle_bundle_ate": truth["oracle_bundle_ate"],
        "mined_top5": mined["candidates"][:5],
        "hte": hte,
        "design": {
            "design_type": design["design_type"],
            "arm_count": design["arm_count"],
            "design_diagnostics": design["design_diagnostics"],
        },
        "component_effects": effects,
        "ledger": ledger.render(),
    }


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
