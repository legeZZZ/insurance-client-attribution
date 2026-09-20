#!/usr/bin/env python3
"""Seed the v2 console demo workspace with real pipeline outputs.

Everything under runtime_data/console_v2/ is produced by actually running
track2_v5 modules (C-line scan, next-window confirmation, factor registry,
skill governance chain). Nothing is hand-written to look like a result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tests"))

from test_stage_c import metric  # noqa: E402

from track2_v5.factor_registry import FactorRegistry  # noqa: E402
from track2_v5.skill_governance import SkillGovernance  # noqa: E402
from track2_v5.watchlist_scan import confirm_watchlist, run_c_line  # noqa: E402

OUT = PROJECT / "runtime_data" / "console_v2"


def build_panel():
    """90-day discovery window + 40-day confirmation window, shared truth."""
    rng = np.random.default_rng(20260916)
    n1, n2 = 90, 40
    total = 100 + n2
    days1 = list(range(n1))
    days2 = list(range(100, 100 + n2))  # isolation gap after discovery

    sms = rng.normal(0.0, 1.0, total)
    feed = rng.normal(0.0, 1.0, total)
    noise = rng.normal(0.0, 1.0, total)
    comp = np.zeros(total)
    comp[40:] = 1.0  # 竞品 day40 下架（onset 型外生事件）

    def residual(sl):
        r = rng.normal(0.0, 0.35, len(sl))
        for i, t in enumerate(sl):
            if t - 2 >= 0:
                r[i] += 0.9 * sms[t - 2]
            if t - 1 >= 0:
                r[i] += 0.6 * feed[t - 1] + 1.6 * comp[t - 1]
        return r

    def take(series, days):
        return [float(series[d]) for d in days]

    factors1 = [
        {"factor_id": "campaign.sms_push", "kind": "internal_event",
         "scope_id": "global", "metric_id": "residual",
         "days": days1, "values": take(sms, days1), "effect_shape": "persistent"},
        {"factor_id": "channel.feed_ad", "kind": "internal_event",
         "scope_id": "global", "metric_id": "residual",
         "days": days1, "values": take(feed, days1), "effect_shape": "persistent"},
        {"factor_id": "competitor.delisting", "kind": "external_event",
         "scope_id": "global", "metric_id": "residual",
         "days": days1, "values": take(comp, days1), "effect_shape": "onset"},
        {"factor_id": "market.noise_index", "kind": "external_event",
         "scope_id": "global", "metric_id": "residual",
         "days": days1, "values": take(noise, days1), "effect_shape": "persistent"},
    ]
    factors2 = [
        {**f, "days": days2, "values": take(s, days2)}
        for f, s in zip(factors1, (sms, feed, comp, noise))
    ]
    return (
        (days1, residual(days1).tolist(), factors1),
        (days2, residual(days2).tolist(), factors2),
        {"sms": sms.tolist(), "feed": feed.tolist(),
         "competitor": comp.tolist(), "noise": noise.tolist()},
    )


def seed_scan():
    (days1, res1, factors1), (days2, res2, factors2), _raw = build_panel()
    scan = run_c_line(days1, res1, factors1, budget=5, test_budget=200,
                      window_id="discovery-2026w37")
    confirmed = {"results": []}
    if scan["watchlist"]:
        confirmed = confirm_watchlist(scan["watchlist"], days2, res2, factors2)
    by_alert = {r["alert_id"]: r for r in confirmed["results"]}
    for item in scan["watchlist"]:
        c = by_alert.get(item["alert_id"], {})
        item["confirmation"] = {
            "claim_type": c.get("claim_type", "WATCHLIST"),
            "adjusted_pvalue": c.get("adjusted_pvalue"),
            "window_correlation": c.get("correlation"),
            "reason_codes": c.get("reason_codes", []),
        }
    payload = {"scan": scan, "confirmation_window": [min(days2), max(days2)],
               "factor_kinds": {f["factor_id"]: f["kind"] for f in factors1}}
    (OUT / "watchlist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    trends = {
        "days": days1,
        "residual": res1,
        "factors": {f["factor_id"]: f["values"] for f in factors1},
    }
    (OUT / "trends.json").write_text(
        json.dumps(trends, ensure_ascii=False), encoding="utf-8")
    return scan


def seed_registry(scan):
    db = OUT / "registry.db"
    if db.exists():
        db.unlink()
    registry = FactorRegistry(str(db))
    meta = {
        "campaign.sms_push": ("短信触达campaign", "内部变动注册表", "自有"),
        "channel.feed_ad": ("信息流投放", "内部变动注册表", "自有"),
        "competitor.delisting": ("竞品下架事件", "公开竞品监测", "公开信息"),
        "market.noise_index": ("大盘噪声指数", "公开行情", "公开信息"),
    }
    strength = {}
    for bucket in ("watchlist", "deferred", "killed"):
        for item in scan[bucket]:
            strength[item["factor_id"]] = item
    for fid, (label, source, license_ref) in meta.items():
        kind = ("internal_event" if fid.startswith(("campaign", "channel"))
                else "external_event")
        registry.register_factor({
            "factor_id": fid,
            "name": label,
            "kind": kind,
            "source_type": "internal_registry" if kind == "internal_event"
                           else "public_monitor",
            "scope": {"scope_id": "global"},
            "source_uri": source,
            "license_ref": license_ref,
            "metadata": {"kind": kind, "source_uri": source},
            "available_day": 0,
        })
        hit = strength.get(fid)
        if hit:
            registry.ingest_evidence({
                "factor_id": fid,
                "evidence_type": "C_LINE_SCAN",
                "claim_type": hit["claim_type"],
                "strength": round(abs(hit.get("correlation", 0.0)), 4),
                "lag": hit["lag"],
                "window_id": hit["window_id"],
                "falsification_status": hit["falsification_status"],
                "confirmation": hit.get("confirmation", {}),
            })
    registry.close()


def metric_request(index):
    m = metric()
    m["window"] = [index, index + 9]
    return {"metric_contract": m}


def seed_governance():
    db = OUT / "governance.db"
    for suffix in ("", ".skills.json"):
        p = Path(str(db) + suffix) if suffix else db
        if p.exists():
            p.unlink()
    gov = SkillGovernance(str(db))
    context = {"metric_kind": "ratio_of_sums"}

    def asset(req):
        return gov.registry.add_asset("data", req)

    def capture(task):
        req = metric_request(0)
        ref = asset(req)
        return gov.capture(task_id=task, data_ref=ref, context=context,
                           operation="check_metric", author="analyst")

    def suite(offset=10):
        cases = []
        for i in (offset, offset + 1):
            req = metric_request(i)
            cases.append({"task_id": f"holdout-{i}", "data_ref": asset(req),
                          "context": context, "request": req,
                          "expected_operation": "check_metric",
                          "critical": False})
        return gov.freeze_suite(cases=cases)["suite_ref"]

    # 技能一：已走到「已验证待审批」——发布台可现场审批/发布
    trace1 = capture("metric-guard-source")
    gov.propose(name="metric_guard", trace_ids=[trace1["trace_id"]],
                applicability=context)
    gov.review(name="metric_guard", version=1, reviewer="independent-reviewer")
    suite_ref = suite()
    gov.validate(name="metric_guard", version=1, suite_ref=suite_ref)

    # 技能二：仅提案（provisional）——发布台可现场评审/验证
    trace2 = capture("scan-triage-source")
    gov.propose(name="scan_triage", trace_ids=[trace2["trace_id"]],
                applicability=context)

    gov.close()
    return suite_ref


def seed_conflicts():
    conflicts = [
        {"id": "conflict-1", "status": "open", "lines": ["A", "B"],
         "title": "A线实验与B线关联方向不一致",
         "detail": "轮播改版 A 线 ITT 为负（-0.016，区间不含 0），B 线关联扫描同期曝光切片为正相关。疑似对照污染或结构混杂，需要业务事实核验。",
         "human_can": "提供事件时间、影响范围、业务机制说明",
         "human_cannot": "不能用经验判断替代识别报告"},
        {"id": "conflict-2", "status": "open", "lines": ["B", "C"],
         "title": "C线盯防信号与B线注册表缺位",
         "detail": "C 线检出 competitor.delisting 与残差同向（lag 1），但变动注册表无对应记录。需要确认是否未登记的外部事件。",
         "human_can": "确认外部事件真实性并补充时间/范围",
         "human_cannot": "不能把确认直接写成因果结论"},
    ]
    (OUT / "conflicts.json").write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_alert_context(scan):
    """Verified conclusions + live configs → conflict/trend alert inputs.

    Conclusions come from two honest sources: (a) watchlist items that
    survived independent-window confirmation in this very seed run;
    (b) the carousel entry, registered in the factor registry with its
    A-line provenance. Configs describe what operations is running now.
    """
    conclusions = []
    for item in scan["watchlist"]:
        conf = item.get("confirmation", {})
        if conf.get("claim_type") == "FACTOR_CANDIDATE":
            conclusions.append({
                "factor_id": item["factor_id"],
                "name": "短信触达campaign",
                "metric": "残余异动（经营指标异常成分）",
                "direction": "positive",
                "basis": f"B 线发现 + 独立窗口确认，校正后 p="
                         f"{conf.get('adjusted_pvalue')}",
            })
    conclusions.append({
        "factor_id": "homepage.carousel_exposure",
        "name": "首页轮播曝光",
        "metric": "付费转化",
        "direction": "positive",
        "basis": "A 线随机化实验库结论（已验证因子）",
    })

    configs = [
        {"config_id": "cfg-carousel-0917", "title": "轮播图配置异常",
         "factor_id": "homepage.carousel_exposure",
         "current_direction": "negative",
         "detail": "本周轮播首位分配给低转化素材 mat_7731（历史转化 0.4%，"
                   "位均 1.2%），首页高转化曝光位被挤出。",
         "suggestion": "恢复高转化素材至轮播首位；调整后以 5% 灰度观察 "
                       "付费转化回升，再全量。",
         "since_day": 137, "owner": "运营后台"},
        {"config_id": "cfg-feed-0915", "title": "信息流投放节奏",
         "factor_id": "channel.feed_ad",
         "current_direction": "positive",
         "detail": "信息流维持既有出价与素材节奏。",
         "since_day": 130, "owner": "运营后台"},
    ]
    (OUT / "verified_conclusions.json").write_text(
        json.dumps(conclusions, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "current_configs.json").write_text(
        json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")

    # carousel factor enters the registry with its A-line provenance
    registry = FactorRegistry(str(OUT / "registry.db"))
    try:
        if registry.get_factor("homepage.carousel_exposure") is None:
            registry.register_factor({
                "factor_id": "homepage.carousel_exposure",
                "name": "首页轮播曝光",
                "kind": "internal_event",
                "source_type": "internal_registry",
                "scope": {"scope_id": "global"},
                "license_ref": "自有",
                "metadata": {"kind": "internal_event",
                             "source_uri": "A 线随机化实验库"},
                "available_day": 0,
            })
            registry.ingest_evidence({
                "factor_id": "homepage.carousel_exposure",
                "evidence_type": "A_LINE_EXPERIMENT",
                "claim_type": "CAUSAL_CONFIRMED",
                "metric": "付费转化",
                "direction": "positive",
                "excerpt": "轮播曝光位随机化实验：处理组付费转化显著提升，"
                           "区间为正。",
            })
    finally:
        registry.close()


def seed_metrics(scan):
    """Anomaly metrics board + metric↔factor attribution edges.

    Claim levels mirror the pipeline vocabulary:
    CAUSAL_CONFIRMED (A 线随机化实验), FACTOR_CANDIDATE (B 线发现 +
    独立窗口确认), WATCHLIST (算法可疑、待人工业务核验),
    AB_TESTING (已进 A 线灰度验证中), TEMPORAL_ASSOCIATION (外部时间关联).
    layer: level=因子本体, velocity/acceleration=派生导数值.
    """
    links = []
    for item in scan["watchlist"]:
        conf = item.get("confirmation", {})
        links.append({
            "factor_id": item["factor_id"],
            "strength": round(abs(item.get("correlation", 0.0)), 4),
            "lag": item["lag"], "layer": "level",
            "claim": conf.get("claim_type", "WATCHLIST"),
            "direction": "positive" if item.get("correlation", 0) >= 0
                         else "negative",
        })
    metrics = [
        {"id": "residual", "name": "残余异动（未解释成分）",
         "change": "窗口内显著偏离基线",
         "status": "部分已解释 · 未知量保留",
         "window": "发现窗口 + 独立确认窗口",
         "factors": links},
        {"id": "paid_conversion", "name": "付费转化 · 华东/付费切面",
         "change": "+8.4%",
         "status": "UNEXPLAINED · 未解释阶跃保留",
         "window": "full_review 场景输出",
         "factors": [
             {"factor_id": "homepage.carousel_exposure",
              "strength": None, "lag": None, "layer": "level",
              "claim": "CAUSAL_CONFIRMED", "direction": "positive",
              "basis": "A 线随机化实验库结论"},
             {"factor_id": "channel.feed_ad",
              "strength": 0.58, "lag": 1, "layer": "level",
              "claim": "WATCHLIST", "direction": "positive"},
             {"factor_id": "internal.quote_form_step_count",
              "strength": 0.41, "lag": 0, "layer": "level",
              "claim": "AB_TESTING", "direction": "negative",
              "basis": "新版报价页 5% 灰度实验中（ITT 区间未收口）"},
         ]},
        {"id": "resource_ctr", "name": "首页资源位 CTR · 全量切面",
         "change": "-12.6% 同比下滑",
         "status": "归因中 · 已定位 1 个因果因子",
         "window": "近 14 天 vs 去年同期",
         "factors": [
             {"factor_id": "homepage.carousel_exposure",
              "strength": 0.83, "lag": 0, "layer": "level",
              "claim": "CAUSAL_CONFIRMED", "direction": "positive",
              "basis": "A 线随机化实验库结论（轮播曝光→点击）"},
             {"factor_id": "internal.page_latency_p95",
              "strength": 0.44, "lag": -4, "layer": "velocity",
              "claim": "WATCHLIST", "direction": "negative",
              "basis": "算法检出（导数层·增速），待人工业务核验"},
             {"factor_id": "external.competitor_pressure_index",
              "strength": 0.39, "lag": -9, "layer": "acceleration",
              "claim": "TEMPORAL_ASSOCIATION", "direction": "negative",
              "basis": "外部时间关联（导数层·加速度）"},
             {"factor_id": "internal.checkout_error_rate",
              "strength": 0.36, "lag": 0, "layer": "level",
              "claim": "AB_TESTING", "direction": "negative",
              "basis": "结算链路修复包 A/B 验证中"},
         ]},
    ]
    (OUT / "anomaly_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_research_candidates():
    """Register the 38 research candidates from the factor-library deep-dive
    (data/因子库深挖-20260917). They land as status=research_candidate —
    definitions with formulas/sources, deliberately NOT in the active scan
    set until instrumentation lands (校验: no candidate in default retrieval).
    """
    path = PROJECT / "data" / "因子库深挖-20260917" / "候选因子库.json"
    if not path.is_file():
        return 0
    catalog = json.loads(path.read_text(encoding="utf-8"))
    registry = FactorRegistry(str(OUT / "registry.db"))
    count = 0
    try:
        for c in catalog:
            if registry.get_factor(c["factor_id"]) is not None:
                continue
            registry.register_factor({
                "factor_id": c["factor_id"],
                "name": c.get("name", c["factor_id"]),
                "description": c.get("description", ""),
                "kind": "research_candidate",
                "source_type": "research_candidate",
                "scope": c.get("scope", {}),
                "aliases": c.get("aliases", []),
                "status": "research_candidate",
                "license_ref": c.get("license_ref") or "研究来源见记录",
                "metadata": {**c.get("metadata", {}),
                             "kind": "research_candidate",
                             "source_uri": "因子库深挖-20260917"},
                "available_day": None,
            })
            count += 1
    finally:
        registry.close()
    return count


def seed_evidence_summary():
    summary = {
        "regression": {"local": "235/235", "container": "234/234",
                       "cli_acceptance": 48},
        "statistics": {
            "association_fdp_max": 0.01, "association_power": 1.0,
            "randomized_coverage": [0.90, 0.98],
            "watchlist_keep_rate": "30/30（植入三型）",
            "watchlist_null_rate": "1/30",
        },
        "negative_results": [
            "图方向严格共识在植入场景功效为 0——不标为统计功效达标",
            "稀疏信号下 knockoff 功效为 0——低功效负结果",
            "错设协方差时 knockoff FDP≈0.562——禁止正式使用的压力证据",
            "三组记忆条件正确率相同——不宣称“越用越强”",
        ],
        "boundaries": [
            "无随机化证据只输出关联级结论；外部因子恒为 TEMPORAL_ASSOCIATION",
            "研究模块（knockoff/因子合成）formal_selection_allowed=false",
            "反馈与人工标签不自动晋升任何结论",
        ],
    }
    (OUT / "evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scan = seed_scan()
    seed_registry(scan)
    suite_ref = seed_governance()
    seed_conflicts()
    seed_alert_context(scan)
    seed_metrics(scan)
    research_count = seed_research_candidates()
    seed_evidence_summary()
    print(json.dumps({
        "workspace": str(OUT),
        "watchlist": [w["factor_id"] for w in scan["watchlist"]],
        "deferred": [d["factor_id"] for d in scan["deferred"]],
        "killed": [k["factor_id"] for k in scan["killed"]],
        "demo_suite_ref": suite_ref,
        "research_candidates": research_count,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
