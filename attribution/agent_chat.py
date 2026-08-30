"""Deterministic Plan-and-Execute agent chat layer.

Fills the multi-turn interaction slot with a fully auditable, dependency-free
state machine instead of an LLM: every transition is rule-based and logged, so
the whole conversation is reproducible — a deliberate compliance choice for
regulated finance scenarios. An LLM intent parser can be plugged in at
`_classify_intent` without changing the state machine.

Flow (Plan-and-Execute, cf. Wang et al. 2023):
  intent   — classify user utterance into one of the 5 demo scenarios
  clarify  — when intent is ambiguous, ask a targeted disambiguation question
  confirm  — show the execution plan (scenario, pipeline steps, est. time)
  execute  — run the real pipeline via scenario_reports.run_scenario
  deliver  — summarize key metrics and point to the downloadable report

Wired into run_server.py as POST /api/attribution/chat {session_id, message}.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .scenario_reports import SCENARIOS, run_scenario

WORKSPACE = Path(__file__).resolve().parent.parent

# Keyword rules: (scenario_id, keywords). Order matters; first hit wins.
_INTENT_RULES = [
    ("bayes_case_a", ["拒答", "refus", "欠定", "证据不足", "案例a", "案例 a"]),
    ("experience", ["经验库", "跨期", "pid", "错配", "消融", "学习", "冷启动"]),
    ("external", ["外部事件", "时间线", "公开事件", "政策", "映射", "加息", "监管"]),
    ("line_b", ["月度", "基线", "注册变动", "未知桶", "环比", "上月", "上个月",
                "为什么掉", "为什么跌", "为什么降", "掉了", "下降", "下跌",
                "注册量", "业务量", "波动"]),
    ("line_a", ["组件", "因子", "实验", "归因", "异常", "决策", "线a", "线 a",
                "ab", "a/b", "策略效果", "新策略"]),
]

_SCENARIO_ALIASES = {s["id"]: s["id"] for s in SCENARIOS}
_SCENARIO_ALIASES.update({str(i + 1): s["id"] for i, s in enumerate(SCENARIOS)})

# In-memory session store: session_id -> state dict. Process-local by design;
# conversations hold no user data, so nothing persists across restarts (8.4-3).
_SESSIONS: dict[str, dict[str, Any]] = {}


def _catalog_text() -> str:
    lines = ["我可以演示以下 5 条可验证链路（回复编号或关键词选择）："]
    for i, s in enumerate(SCENARIOS):
        lines.append(f"  {i + 1}. {s['title']}（{s['est_seconds']}）")
    return "\n".join(lines)


def _classify_intent(text: str) -> str | None:
    """Rule-based intent classification. Swap for an LLM parser if desired;
    keep the rest of the state machine unchanged."""
    lowered = text.strip().lower()
    for alias, sid in _SCENARIO_ALIASES.items():
        if lowered == alias:
            return sid
    for sid, keywords in _INTENT_RULES:
        if any(k in lowered for k in keywords):
            return sid
    return None


def _plan_text(scenario_id: str) -> str:
    title = next(s["title"] for s in SCENARIOS if s["id"] == scenario_id)
    est = next(s["est_seconds"] for s in SCENARIOS if s["id"] == scenario_id)
    steps = {
        "line_a": "异常检测 → 因子挖掘 → 贝叶斯实验设计 → 决策门禁 → Claim Ledger 记账",
        "line_b": "面板模拟 → 变更注册表匹配 → 外部事件对齐 → 残差未知桶 → 滞后窗检验",
        "external": "公开事件时间线加载 → 行业/区域映射 → 覆盖率统计 → 错挂检查",
        "bayes_case_a": "欠定场景构造 → 证据充分性检验 → REFUSED 拒答 → 补数据建议",
        "experience": "多期实验回放 → 经验库先验更新（PID 调节）→ 错配报警 → 冷启动消融",
    }[scenario_id]
    return (f"执行计划：{title}\n"
            f"流程：{steps}\n"
            f"预计耗时：{est}，全程本地运行、不出网。\n"
            f"确认执行请回复「确认」或「执行」；换一条链路请直接说明。")


def handle_message(session_id: str, message: str,
                   runtime_dir: Path | None = None) -> dict[str, Any]:
    """One chat turn. Returns {reply, stage, scenario?, report?, trace}."""
    state = _SESSIONS.setdefault(session_id, {"stage": "intent", "scenario": None})
    trace: list[str] = [f"stage_in={state['stage']}"]
    text = (message or "").strip()

    if state["stage"] == "confirm":
        if any(k in text.lower() for k in ["确认", "执行", "好", "run", "yes", "ok"]):
            sid = state["scenario"]
            state["stage"] = "intent"
            state["scenario"] = None
            started = time.time()
            report = run_scenario(sid, runtime_dir)
            elapsed = round(time.time() - started, 2)
            trace.append(f"executed={sid} in {elapsed}s")
            metrics = ", ".join(f"{k}={v}" for k, v in
                                list(report["metrics"].items())[:6])
            reply = (f"✅ 已真实执行完毕（{elapsed}s，非预置输出）。\n"
                     f"关键指标：{metrics}\n"
                     f"完整审计报告：GET /api/attribution/scenario-report?scenario={sid}\n"
                     f"证据指针：{report.get('evidence_pointer', 'outputs/')}\n\n"
                     + _catalog_text())
            return {"reply": reply, "stage": "done", "scenario": sid,
                    "report": report, "trace": trace}
        # Not a confirmation: re-classify as a new intent.
        state["stage"] = "intent"
        state["scenario"] = None

    sid = _classify_intent(text)
    if sid is None:
        trace.append("intent=ambiguous -> clarify")
        return {"reply": ("我没有完全理解您的目标场景。\n" + _catalog_text()),
                "stage": "clarify", "trace": trace}

    state["scenario"] = sid
    state["stage"] = "confirm"
    trace.append(f"intent={sid} -> confirm")
    return {"reply": _plan_text(sid), "stage": "confirm",
            "scenario": sid, "trace": trace}


def reset_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)
