"""Deterministic Plan-and-Execute agent chat layer for attribution (8.1-2).

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
import unicodedata
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from typing import Any

from .scenario_reports import SCENARIOS, run_scenario

WORKSPACE = Path(__file__).resolve().parent.parent

# Keyword rules: (scenario_id, keywords). Order matters; first hit wins.
_INTENT_RULES = [
    ("full_review", ["全链路", "综合复核", "全面复核", "a+b", "a＋b"]),
    ("bayes_case_a", ["拒答", "refus", "欠定", "证据不足", "案例a", "案例 a"]),
    ("experience", ["经验库", "跨期", "pid", "错配", "消融", "学习", "冷启动"]),
    ("external", ["外部事件", "时间线", "公开事件", "政策", "映射", "加息", "监管"]),
    (
        "line_b",
        [
            "月度",
            "基线",
            "注册变动",
            "未知桶",
            "环比",
            "上月",
            "上个月",
            "为什么掉",
            "为什么跌",
            "为什么降",
            "掉了",
            "下降",
            "下跌",
            "注册量",
            "业务量",
            "波动",
        ],
    ),
    (
        "line_a",
        [
            "组件",
            "因子",
            "实验",
            "归因",
            "异常",
            "决策",
            "线a",
            "线 a",
            "ab",
            "a/b",
            "策略效果",
            "新策略",
        ],
    ),
]

_SCENARIO_ALIASES = {s["id"]: s["id"] for s in SCENARIOS}
_SCENARIO_ALIASES.update({str(i + 1): s["id"] for i, s in enumerate(SCENARIOS)})

# In-memory session store: session_id -> state dict. Process-local by design;
# conversations hold no user data, so nothing persists across restarts (8.4-3).
# The cap prevents arbitrary client-provided session IDs from growing memory forever.
_MAX_SESSIONS = 1_000
_SESSION_LOCK = RLock()
_SESSIONS: OrderedDict[str, dict[str, Any]] = OrderedDict()

_CONFIRM_COMMANDS = {"确认", "执行", "好", "好的", "可以", "run", "yes", "ok"}


def _normalized_command(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().casefold()
    return normalized.strip("。.!！?？")


def _session_state(session_id: str) -> dict[str, Any]:
    state = _SESSIONS.get(session_id)
    if state is None:
        if len(_SESSIONS) >= _MAX_SESSIONS:
            _SESSIONS.popitem(last=False)
        state = {"stage": "intent", "scenario": None}
        _SESSIONS[session_id] = state
    else:
        _SESSIONS.move_to_end(session_id)
    return state


def _catalog_text() -> str:
    lines = [f"我可以演示以下 {len(SCENARIOS)} 条可验证链路（回复编号或关键词选择）："]
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
        "full_review": "意图规划 → B 线分层异常/RAG/关联 → A 线随机实验 → 外部事件映射 → N1/N2/N3 护栏 → Evidence Pack",
        "line_a": "异常检测 → 因子挖掘 → 贝叶斯实验设计 → 决策门禁 → Claim Ledger 记账",
        "line_b": "面板模拟 → 变更注册表匹配 → 外部事件对齐 → 残差未知桶 → 滞后窗检验",
        "external": "公开事件时间线加载 → 行业/区域映射 → 覆盖率统计 → 错挂检查",
        "bayes_case_a": "欠定场景构造 → 证据充分性检验 → REFUSED 拒答 → 补数据建议",
        "experience": "多期实验回放 → 经验库先验更新（PID 调节）→ 错配报警 → 冷启动消融",
    }[scenario_id]
    return (
        f"执行计划：{title}\n"
        f"流程：{steps}\n"
        f"预计耗时：{est}，全程本地运行、不出网。\n"
        f"确认执行请回复「确认」或「执行」；换一条链路请直接说明。"
    )


def handle_message(
    session_id: str, message: str, runtime_dir: Path | None = None
) -> dict[str, Any]:
    """One chat turn. Returns {reply, stage, scenario?, report?, trace}."""
    text = (message or "").strip()
    execute_sid: str | None = None
    with _SESSION_LOCK:
        state = _session_state(session_id)
        trace: list[str] = [f"stage_in={state['stage']}"]

        if state["stage"] == "confirm":
            if _normalized_command(text) in _CONFIRM_COMMANDS:
                execute_sid = str(state["scenario"])
                state["stage"] = "intent"
                state["scenario"] = None
            else:
                # Not a confirmation: re-classify as a new intent.
                state["stage"] = "intent"
                state["scenario"] = None

        if execute_sid is None:
            sid = _classify_intent(text)
            if sid is None:
                trace.append("intent=ambiguous -> clarify")
                return {
                    "reply": ("我没有完全理解您的目标场景。\n" + _catalog_text()),
                    "stage": "clarify",
                    "trace": trace,
                }

            state["scenario"] = sid
            state["stage"] = "confirm"
            trace.append(f"intent={sid} -> confirm")
            return {
                "reply": _plan_text(sid),
                "stage": "confirm",
                "scenario": sid,
                "trace": trace,
            }

    started = time.time()
    report = run_scenario(execute_sid, runtime_dir)
    elapsed = round(time.time() - started, 2)
    trace.append(f"executed={execute_sid} in {elapsed}s")
    metrics = ", ".join(
        f"{key}={value}" for key, value in list(report["metrics"].items())[:6]
    )
    reply = (
        f"✅ 已真实执行完毕（{elapsed}s，非预置输出）。\n"
        f"关键指标：{metrics}\n"
        f"完整审计报告：GET /api/attribution/scenario-report?scenario={execute_sid}\n"
        f"证据指针：{report.get('evidence_pointer', 'outputs/')}\n\n" + _catalog_text()
    )
    return {
        "reply": reply,
        "stage": "done",
        "scenario": execute_sid,
        "report": report,
        "trace": trace,
    }


def reset_session(session_id: str) -> None:
    with _SESSION_LOCK:
        _SESSIONS.pop(session_id, None)
