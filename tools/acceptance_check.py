#!/usr/bin/env python3
"""验收脚本：核心算法准入验证（配合《验证交接手册.md》使用）。

用法：
  PYTHONPATH=. python3 tools/acceptance_check.py                # 全项
  PYTHONPATH=. python3 tools/acceptance_check.py --quick        # 跳过慢项（经验库消融）
  PYTHONPATH=. python3 tools/acceptance_check.py --data-config company_data/config.json
      # 额外验证公司数据源场景

输出：每项 PASS/FAIL + 实测值 vs 准入阈值，全部 PASS 退出码 0，否则 1。
所有判定调用真实管线，不读静态证据文件。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

RUNTIME = PROJECT / "runtime_data"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str) -> None:
    RESULTS.append((name, bool(passed), detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="跳过慢项")
    parser.add_argument("--data-config", type=Path, default=None, help="公司数据源配置")
    parser.add_argument(
        "--skip-regression",
        action="store_true",
        help="使用已归档的独立后端回归，不重复运行",
    )
    args = parser.parse_args()

    from track2_v5 import scenario_reports as sr

    # A0 单元回归
    if not args.skip_regression:
        completed = subprocess.run(
            [sys.executable, str(PROJECT / "tools/run_backend_tests.py")],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        ok = completed.returncode == 0
        tail = (completed.stderr or completed.stdout).strip().splitlines()
        summary = next(
            (ln for ln in reversed(tail) if ln.startswith("Ran ")), "no summary"
        )
        check("A0 单元回归", ok, summary)

    # A1 A 线贝叶斯决策：估计贴近真值 + 给出决策
    rep = sr.run_scenario("line_a", RUNTIME)
    est = rep["metrics"]["bundle_effect"]
    truth = rep["metrics"]["oracle_bundle_ate"]
    err = abs(est - truth)
    check(
        "A1 历史数值/决策回归（不授予新因果资格）",
        err <= 0.01 and rep["metrics"]["bundle_decision"] == "ROLLBACK_RECOMMENDED",
        f"bundle_effect={est:.4f} vs oracle={truth:.4f}（误差 {err:.4f}，准入 ≤0.01），决策={rep['metrics']['bundle_decision']}",
    )

    from tools.check_stage_e_statistics import effect_request
    from track2_v5.quant_track import estimate_effect
    from track2_v5.publication import publish_conclusion

    request, _, _ = effect_request("A_signal", 90001)
    for row in request["parameters"]["rows"]:
        row["outcome"] = -row["outcome"]
    governed = publish_conclusion(
        estimate_effect(**request)["contracts"],
        practical_threshold=0.05,
        action_policy={
            "business_value_per_unit": 1,
            "exposure": 1000,
            "implementation_cost": 0,
            "guardrails": {
                "quality": {
                    "max_harm": 0.02,
                    "interval": [-0.01, 0.01],
                    "simultaneous_evidence_ref": "fixture:joint-guardrail",
                }
            },
        },
    )
    check(
        "A1b 当前发布门与行动政策",
        governed["claim_type"] == "RANDOMIZED_EFFECT"
        and governed["statistical_uncertainty"]["interval"][1] < 0
        and governed["action_policy"]["action"] in {"KEEP_BASELINE"},
        str(governed["action_policy"]),
    )

    # A2 拒答：欠定场景必须 REFUSED
    rep = sr.run_scenario("bayes_case_a", RUNTIME)
    check(
        "A2 证据门禁拒答",
        rep["claim"] == "REFUSED" and rep["metrics"].get("refused") is True,
        f"claim={rep['claim']} refused={rep['metrics'].get('refused')}（准入：REFUSED 且 refused=true）",
    )

    # B1 线 B：未知桶诚实保留 + 候选可发现
    rep = sr.run_scenario("line_b", RUNTIME)
    candidates = rep["key_outputs"]["association_discovery"]["candidate_count"]
    unknown = rep["key_outputs"].get("unknown_bucket")
    check(
        "B1 开放因子发现",
        candidates > 0 and unknown is not None,
        f"candidates={candidates}（准入 >0），unknown_bucket={'保留' if unknown else '缺失'}",
    )

    # B2 外部事件映射：挂靠必须是时间关联，零因果断言
    rep = sr.run_scenario("external", RUNTIME)
    mapped = rep["key_outputs"].get("mapped", [])
    all_temporal = bool(mapped) and all(
        m.get("claim_type") == "TEMPORAL_ASSOCIATION" for m in mapped
    )
    check(
        "B2 外部事件边界",
        rep["claim"].startswith("TEMPORAL_ASSOCIATION") and all_temporal,
        f"mapped={len(mapped)}，全部 TEMPORAL_ASSOCIATION={all_temporal}",
    )

    # C1 经验库消融（慢项）：冷启动误差应下降
    if not args.quick:
        rep = sr.run_scenario("experience", RUNTIME)
        m = rep["metrics"]
        static = m.get("ate_rmse_sparse_static")
        adaptive = m.get("ate_rmse_sparse_adaptive")
        improved = static is not None and adaptive is not None and adaptive < static
        from track2_v5.experience_benchmark import SEEDS

        first_mismatch = next(seed for seed, mismatch in SEEDS if mismatch)
        onset_detected = first_mismatch in m.get("mismatch_alarm_fired", [])
        check(
            "C1 经验库消融",
            improved and onset_detected,
            f"冷启动稀疏场景 ATE RMSE：adaptive={adaptive} < static={static}（准入：adaptive 更低），"
            f"mismatch_alarm={m.get('mismatch_alarm_fired')}",
        )

    # D1 公司数据源（可选）
    if args.data_config:
        from track2_v5.adapters import load_config

        sr.set_company_config(load_config(args.data_config))
        rep = sr.run_scenario("company_line_b", RUNTIME)
        check(
            "D1 公司数据链路",
            rep["execution_mode"] == "company_adapter"
            and rep["metrics"]["panel_days"] >= 20
            and rep["key_outputs"]["association_discovery"]["candidate_count"] > 0,
            f"mode={rep['execution_mode']} days={rep['metrics']['panel_days']} candidates={rep['key_outputs']['association_discovery']['candidate_count']}",
        )

    failed = [n for n, ok, _ in RESULTS if not ok]
    print("\n==== 验收结论 ====")
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} 项 PASS")
    if failed:
        print("FAIL 项：", "、".join(failed))
        return 1
    print("全部通过，达到准入标准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
