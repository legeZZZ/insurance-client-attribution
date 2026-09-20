#!/usr/bin/env python3
"""v2 console backend: factor library, C-line watchlist, HITL stations.

Reads demo artifacts produced by tools/seed_console_v2.py (all real pipeline
outputs) and exposes mutations through the same governed services the CLI
uses (FeedbackService, SkillGovernance). No shortcut around the gates:
human input is recorded and routed, never promoted automatically.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from track2_v5.factor_registry import FactorRegistry
from track2_v5.feedback_service import FeedbackService
from track2_v5.skill_governance import SkillGovernance

SUGGESTIONS = {
    "competitor.delisting": "竞品流量外溢窗口期：建议提升自身产品曝光（信息流与搜索位）。仅为动作提案，需独立实验验证后才可放量。",
    "campaign.sms_push": "短信触达与残余异动同向：建议保留当前节奏，并按验证计划做下一窗口独立确认。",
    "channel.feed_ad": "信息流投放与残余异动同向：建议核对同期素材与出价变更，再决定是否扩量。",
    "market.noise_index": "大盘噪声：不建议跟随动作。",
}

FEEDBACK_KINDS = {"candidate_review", "alert_feedback", "factor_supplement"}
SKILL_ACTIONS = {"review", "validate", "approve", "publish", "monitor",
                 "suspend_scope", "rollback"}


def _load(workdir: Path, name: str):
    path = workdir / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _feedback(workdir: Path) -> FeedbackService:
    return FeedbackService(str(workdir / "feedback.db"))


def overview(workdir: Path) -> dict:
    data = _load(workdir, "watchlist.json")
    if data is None:
        return {"error": "console_v2 workspace not seeded",
                "seed_command": "python tools/seed_console_v2.py"}
    scan = data["scan"]
    kinds = data.get("factor_kinds", {})
    nodes = []
    for item in scan["watchlist"]:
        conf = item.get("confirmation", {})
        nodes.append({
            "id": item["alert_id"],
            "factor_id": item["factor_id"],
            "level": conf.get("claim_type", "WATCHLIST"),
            "confidence": round(abs(item.get("correlation", 0.0)), 4),
            "lag": item["lag"],
            "kind": kinds.get(item["factor_id"], "unknown"),
        })
    queue = _feedback(workdir)
    try:
        pending = len(queue.queue())
        calibration = queue.calibration()
    finally:
        queue.close()
    skills = list_skills(workdir)
    return {
        "nodes": nodes,
        "metrics": _load(workdir, "anomaly_metrics.json") or [],
        "counts": {
            "watchlist": len(scan["watchlist"]),
            "deferred": len(scan["deferred"]),
            "killed": scan["killed_count"],
            "validated": sum(1 for n in nodes if n["level"] == "FACTOR_CANDIDATE"),
            "pending_feedback": pending,
            "skills": len(skills["skills"]),
        },
        "calibration": calibration,
        "confirmation_window": data["confirmation_window"],
        "policy": scan["policy"],
    }


def factors(workdir: Path) -> dict:
    db = workdir / "registry.db"
    if not db.is_file():
        return {"error": "registry not seeded"}
    data = _load(workdir, "watchlist.json") or {}
    strength = {}
    for bucket in ("watchlist", "deferred", "killed"):
        for item in (data.get("scan") or {}).get(bucket, []):
            prev = strength.get(item["factor_id"])
            if prev is None or abs(item.get("correlation", 0)) > abs(prev.get("correlation", 0)):
                strength[item["factor_id"]] = item
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        out = []
        for f in conn.execute(
            "SELECT factor_id, name, source_type, license_ref, metadata, status FROM factors ORDER BY factor_id"
        ):
            fid = f["factor_id"]
            meta = json.loads(f["metadata"] or "{}")
            ev_count = conn.execute(
                "SELECT count(*) FROM evidence WHERE factor_id=?", (fid,)
            ).fetchone()[0]
            hit = strength.get(fid)
            conf = (hit or {}).get("confirmation") or {}
            out.append({
                "factor_id": fid,
                "name": f["name"],
                "kind": meta.get("kind") or f["source_type"],
                "source_type": f["source_type"],
                "license_ref": f["license_ref"],
                "status": f["status"],
                "family": meta.get("family"),
                "priority": meta.get("priority"),
                "formula": meta.get("formula"),
                "data_source": meta.get("data_source"),
                "strength": round(abs(hit["correlation"]), 4) if hit else None,
                "lag": hit.get("lag") if hit else None,
                "claim_type": conf.get("claim_type")
                              or (hit or {}).get("claim_type"),
                "falsification_status": (hit or {}).get("falsification_status"),
                "evidence_count": ev_count,
            })
        return {"factors": out}
    finally:
        conn.close()


def watchlist(workdir: Path) -> dict:
    data = _load(workdir, "watchlist.json")
    trends = _load(workdir, "trends.json") or {}
    if data is None:
        return {"error": "console_v2 workspace not seeded"}
    fb = _feedback(workdir)
    try:
        events = [
            json.loads(r[0]) for r in fb.db.execute(
                "SELECT body FROM feedback_events WHERE kind='alert_feedback' ORDER BY rowid"
            )
        ]
    finally:
        fb.close()
    labels = {e["payload"]["alert_id"]: e["payload"]["label"] for e in events}
    items = []
    for w in data["scan"]["watchlist"]:
        conf = w.get("confirmation", {})
        fid = w["factor_id"]
        items.append({
            "alert_id": w["alert_id"],
            "factor_id": fid,
            "lag": w["lag"],
            "correlation": round(w.get("correlation", 0.0), 4),
            "score": round(w.get("score", 0.0), 4),
            "claim_type": conf.get("claim_type", "WATCHLIST"),
            "adjusted_pvalue": conf.get("adjusted_pvalue"),
            "falsification": w["falsification"],
            "falsification_status": w["falsification_status"],
            "discovery_window": w["discovery_window"],
            "suggestion": SUGGESTIONS.get(fid, "建议保持观察。"),
            "trend": {
                "days": trends.get("days", []),
                "residual": trends.get("residual", []),
                "factor": (trends.get("factors") or {}).get(fid, []),
            },
            "feedback_label": labels.get(w["alert_id"]),
            "next_step": w["next_step"],
        })
    return {
        "items": items,
        "deferred": [d["factor_id"] for d in data["scan"]["deferred"]],
        "killed": [k["factor_id"] for k in data["scan"]["killed"]],
        "confirmation_window": data["confirmation_window"],
        "policy": data["scan"]["policy"],
    }


def submit_feedback(workdir: Path, body: dict) -> dict:
    kind = body.get("kind")
    payload = body.get("payload")
    request_id = body.get("request_id")
    if kind not in FEEDBACK_KINDS or not isinstance(payload, dict):
        raise ValueError("supported kind and object payload required")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id required for idempotent submit")
    fb = _feedback(workdir)
    try:
        return fb.submit(request_id=request_id.strip(), kind=kind, payload=payload)
    finally:
        fb.close()


def feedback_queue(workdir: Path) -> dict:
    fb = _feedback(workdir)
    try:
        events = [
            json.loads(r[0]) for r in fb.db.execute(
                "SELECT body FROM feedback_events ORDER BY rowid DESC LIMIT 50"
            )
        ]
        return {"queue": fb.queue(), "calibration": fb.calibration(),
                "recent": events}
    finally:
        fb.close()


def list_skills(workdir: Path) -> dict:
    db = workdir / "governance.db"
    if not db.is_file():
        return {"error": "governance not seeded"}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        skills = []
        for row in conn.execute(
            "SELECT name, version, spec, lifecycle FROM governed_skills ORDER BY name, version"
        ):
            spec = json.loads(row["spec"])
            life = json.loads(row["lifecycle"])
            skills.append({
                "name": row["name"],
                "version": row["version"],
                "trust_state": life.get("trust_state", "provisional"),
                "claim_ceiling": spec.get("claim_ceiling"),
                "rules": len(spec.get("rules", [])),
                "review_passed": bool((life.get("review") or {}).get("passed")),
                "validated": bool((life.get("validation") or {}).get("passed")),
                "lifecycle": life,
            })
        releases = [
            json.loads(r["body"])
            for r in conn.execute(
                "SELECT body FROM skill_releases ORDER BY seq"
            )
        ]
        suites = [r["id"] for r in conn.execute("SELECT id FROM skill_suites")]
        return {"skills": skills, "releases": releases,
                "demo_suite_ref": suites[-1] if suites else None}
    finally:
        conn.close()


def skill_action(workdir: Path, body: dict) -> dict:
    action = body.get("action")
    if action not in SKILL_ACTIONS:
        raise ValueError(f"action must be one of {sorted(SKILL_ACTIONS)}")
    name = body.get("name")
    version = body.get("version")
    if not name or type(version) is not int:
        raise ValueError("skill name and integer version required")
    gov = SkillGovernance(str(workdir / "governance.db"))
    try:
        if action == "review":
            reviewer = str(body.get("operator") or "").strip()
            if not reviewer:
                raise ValueError("reviewer identity required")
            return gov.review(name=name, version=version, reviewer=reviewer)
        if action == "validate":
            suite_ref = str(body.get("suite_ref") or "")
            return gov.validate(name=name, version=version, suite_ref=suite_ref)
        if action == "approve":
            approver = str(body.get("operator") or "").strip()
            suite_ref = str(body.get("suite_ref") or "")
            if not approver:
                raise ValueError("approver identity required")
            return gov.approve(
                name=name, version=version, approver=approver,
                credential_ref=f"console-demo:{approver}", suite_ref=suite_ref)
        if action == "publish":
            approval_ref = str(body.get("approval_ref") or "")
            fraction = float(body.get("fraction") or 0.1)
            if not 0 < fraction <= 1:
                raise ValueError("fraction must be within (0,1]")
            return gov.publish(name=name, version=version,
                               approval_ref=approval_ref, fraction=fraction)
        if action == "monitor":
            suite_ref = str(body.get("suite_ref") or "")
            return gov.monitor(name=name, version=version, suite_ref=suite_ref)
        if action == "suspend_scope":
            return gov.suspend_scope(
                name=name, version=version,
                context=dict(body.get("context") or {}),
                task_id=str(body.get("task_id") or "console"),
                data_ref=str(body.get("data_ref") or "console"))
        approval_ref = str(body.get("approval_ref") or "")
        target = body.get("target_version")
        if type(target) is not int:
            raise ValueError("integer target_version required for rollback")
        return gov.rollback(name=name, target_version=target,
                            approval_ref=approval_ref,
                            effective_window=int(body.get("effective_window") or 0))
    finally:
        gov.close()


def conflicts(workdir: Path) -> dict:
    items = _load(workdir, "conflicts.json") or []
    fb = _feedback(workdir)
    try:
        events = [
            json.loads(r[0]) for r in fb.db.execute(
                "SELECT body FROM feedback_events WHERE kind='factor_supplement' ORDER BY rowid"
            )
        ]
    finally:
        fb.close()
    inputs = {}
    for e in events:
        p = e["payload"]
        if str(p.get("note", "")).startswith("[冲突核验]"):
            inputs.setdefault(p["factor_id"], []).append(p)
    for item in items:
        item["human_inputs"] = inputs.get(item["id"], [])
        if item["human_inputs"] and item["status"] == "open":
            item["status"] = "human_input_received"
    return {"conflicts": items}


def conflict_input(workdir: Path, body: dict) -> dict:
    conflict_id = str(body.get("conflict_id") or "").strip()
    operator = str(body.get("operator") or "").strip()
    event_time = str(body.get("event_time") or "").strip()
    scope = str(body.get("scope") or "").strip()
    mechanism = str(body.get("mechanism") or "").strip()
    if not all([conflict_id, operator, event_time, scope, mechanism]):
        raise ValueError(
            "conflict_id, operator, event_time, scope and mechanism required")
    payload = {
        "factor_id": conflict_id,
        "operator": operator,
        "note": f"[冲突核验] 事件时间 {event_time}；影响范围 {scope}；业务机制 {mechanism}",
        "current_window": int(body.get("current_window") or 0),
        "available_day": int(body.get("available_day") or 0),
        "factor_kind": "conflict_business_fact",
    }
    return submit_feedback(workdir, {
        "request_id": str(body.get("request_id") or ""),
        "kind": "factor_supplement",
        "payload": payload,
    })


def evidence(workdir: Path) -> dict:
    return _load(workdir, "evidence_summary.json") or {"error": "not seeded"}


# ---------------------------------------------------------------- alerts

ALERT_ACTIONS = {"confirm", "dismiss", "adopt", "close"}
ALERT_STATUS = {"confirm": "confirmed", "dismiss": "dismissed",
                "adopt": "adopted", "close": "closed"}

TREND_HIGH = 0.55   # |corr| at/above → 高风险趋势预警
TREND_WATCH = 0.30  # |corr| at/above → 关注


def _alert_states(workdir: Path) -> dict:
    """Latest lifecycle state per alert, from the append-only state log.

    Lifecycle (open→confirmed/adopted/closed, or dismissed) is console
    state; the governed label (useful/false_positive) is separately
    recorded through FeedbackService so calibration stays honest."""
    path = workdir / "alert_state.log"
    states = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("action") in ALERT_ACTIONS:
                states[e["alert_id"]] = {
                    "status": ALERT_STATUS[e["action"]],
                    "action": e["action"],
                    "reason": e.get("reason", ""),
                    "operator": e.get("operator", ""),
                    "at": e.get("at"),
                }
    return states


def alerts(workdir: Path) -> dict:
    """C-line alert board: trend warnings from the watchlist scan, plus
    conflict warnings where a live config contradicts a verified
    factor→metric conclusion. Status is overlaid from governed feedback;
    nothing here is hand-written per alert."""
    wl = _load(workdir, "watchlist.json")
    if wl is None:
        return {"error": "console_v2 workspace not seeded",
                "seed_command": "python tools/seed_console_v2.py"}
    trends = _load(workdir, "trends.json") or {}
    conclusions = _load(workdir, "verified_conclusions.json") or []
    configs = _load(workdir, "current_configs.json") or []
    states = _alert_states(workdir)

    out = []
    for w in wl["scan"]["watchlist"]:
        conf = w.get("confirmation", {})
        if conf.get("claim_type") == "FACTOR_CANDIDATE":
            continue  # already validated → lives in the factor library
        corr = abs(w.get("correlation", 0.0))
        if corr >= TREND_HIGH:
            level = "high"
        elif corr >= TREND_WATCH:
            level = "watch"
        else:
            continue
        fid = w["factor_id"]
        alert_id = f"trend-{fid}-lag{w['lag']}"
        out.append({
            "alert_id": alert_id,
            "type": "trend",
            "level": level,
            "title": f"{fid} 关联强度持续上升（lag {w['lag']}）",
            "factor_id": fid,
            "lag": w["lag"],
            "correlation": round(w.get("correlation", 0.0), 4),
            "basis": f"C 线盯防窗口 {w['discovery_window']}；校正后 p 值 "
                     f"{conf.get('adjusted_pvalue')}；三杀证伪 "
                     f"{w['falsification_status']}",
            "impact": "残余异动与该因子同向，若继续走强将放大指标波动",
            "suggestion": SUGGESTIONS.get(fid, "建议保持观察。"),
            "falsification": w["falsification"],
            "trend": {
                "days": trends.get("days", []),
                "residual": trends.get("residual", []),
                "factor": (trends.get("factors") or {}).get(fid, []),
            },
            "state": states.get(alert_id, {"status": "open"}),
        })

    concl_by_factor = {c["factor_id"]: c for c in conclusions}
    for cfg in configs:
        concl = concl_by_factor.get(cfg.get("factor_id"))
        if concl is None:
            continue
        if cfg.get("current_direction") == concl.get("direction"):
            continue  # consistent → no warning
        alert_id = f"conflict-{cfg['config_id']}"
        zh = {"positive": "正向", "negative": "负向"}
        out.append({
            "alert_id": alert_id,
            "type": "conflict",
            "level": "high",
            "title": cfg["title"],
            "factor_id": cfg["factor_id"],
            "conclusion": concl,
            "basis": f"已验证结论「{concl['name']} → {concl['metric']}」方向为"
                     f"{zh.get(concl['direction'], concl['direction'])}"
                     f"（{concl['basis']}）；当前配置方向为"
                     f"{zh.get(cfg.get('current_direction'), cfg.get('current_direction'))}。"
                     f"{cfg.get('detail', '')}",
            "impact": f"预计对 {concl['metric']} 产生与已验证结论相反的"
                      "负面影响",
            "suggestion": cfg.get("suggestion",
                                  "建议按已验证结论方向调整配置，并以小流量验证。"),
            "state": states.get(alert_id, {"status": "open"}),
        })
    order = {"high": 0, "watch": 1}
    out.sort(key=lambda a: (order.get(a["level"], 2), a["alert_id"]))
    counts = {
        "high": sum(1 for a in out
                    if a["level"] == "high" and a["state"]["status"] == "open"),
        "watch": sum(1 for a in out
                     if a["level"] == "watch" and a["state"]["status"] == "open"),
    }
    return {"alerts": out, "open_counts": counts,
            "thresholds": {"trend_high": TREND_HIGH, "trend_watch": TREND_WATCH,
                           "cooldown_hours": 24}}


def alert_action(workdir: Path, body: dict) -> dict:
    action = body.get("action")
    if action not in ALERT_ACTIONS:
        raise ValueError(f"action must be one of {sorted(ALERT_ACTIONS)}")
    alert_id = str(body.get("alert_id") or "").strip()
    operator = str(body.get("operator") or "").strip()
    reason = str(body.get("reason") or "").strip()
    request_id = str(body.get("request_id") or "").strip()
    if not alert_id or not operator or not request_id:
        raise ValueError("alert_id, operator and request_id required")
    if action == "dismiss" and not reason:
        raise ValueError("dismiss requires a reason (误报必须说明原因)")

    path = workdir / "alert_state.log"
    existing = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.add(json.loads(line).get("request_id"))
    if request_id in existing:
        return {"ok": True, "idempotent": True, "alert_id": alert_id,
                "status": ALERT_STATUS[action]}

    from datetime import UTC, datetime
    entry = {"request_id": request_id, "alert_id": alert_id,
             "action": action, "reason": reason, "operator": operator,
             "at": datetime.now(UTC).isoformat(timespec="seconds")}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    governed = None
    if action in ("confirm", "dismiss"):
        label = "useful" if action == "confirm" else "false_positive"
        try:
            governed = submit_feedback(workdir, {
                "request_id": f"{request_id}-label",
                "kind": "alert_feedback",
                "payload": {"alert_id": alert_id, "label": label,
                            "operator": operator,
                            "source_kind": "console_alert"},
            })
        except ValueError as exc:
            governed = {"ok": False, "note": str(exc)}
    return {"ok": True, "alert_id": alert_id, "status": ALERT_STATUS[action],
            "governed_label": governed,
            "note": "反馈已记录；不自动晋升或修改任何统计结论"}


# ------------------------------------------------------- factor management

FACTOR_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
FACTOR_ACTIONS = {"create", "disable", "enable"}


def factor_manage(workdir: Path, body: dict) -> dict:
    """Operator-managed factor lifecycle. Creates land as source_type
    operator-entry and never overwrite an already-registered factor;
    disable/enable flips status so the next C-line window skips it.
    Every call is audited at the HTTP layer (v2_action)."""
    action = body.get("action")
    if action not in FACTOR_ACTIONS:
        raise ValueError(f"action must be one of {sorted(FACTOR_ACTIONS)}")
    operator = str(body.get("operator") or "").strip()
    if not operator:
        raise ValueError("operator required for governance traceability")
    spec = body.get("factor")
    if not isinstance(spec, dict):
        raise ValueError("factor object required")
    factor_id = str(spec.get("factor_id") or "").strip().lower()
    if (not factor_id or len(factor_id) > 64
            or any(ch not in FACTOR_ID_CHARS for ch in factor_id)):
        raise ValueError("factor_id must be 1-64 chars of [a-z0-9._-]")

    registry = FactorRegistry(str(workdir / "registry.db"))
    try:
        existing = registry.get_factor(factor_id)
        if action == "create":
            if existing is not None:
                raise ValueError(
                    f"factor already registered: {factor_id} "
                    "(人工补录不覆盖已登记因子元数据)")
            name = str(spec.get("name") or "").strip()
            category = str(spec.get("category") or "").strip()
            mechanism = str(spec.get("mechanism") or "").strip()
            if not name or not category or not mechanism:
                raise ValueError("name, category and mechanism required")
            record = {
                "factor_id": factor_id,
                "name": name,
                "description": mechanism,
                "kind": "operator_entry",
                "source_type": "operator-entry",
                "scope": {"scope_id": "global"},
                "license_ref": "内部登记",
                "metadata": {
                    "kind": "operator_entry",
                    "category": category,
                    "mechanism": mechanism,
                    "operator": operator,
                    "available_day": int(spec.get("available_day") or 0),
                    "source_uri": "运营人工录入",
                },
                "available_day": int(spec.get("available_day") or 0),
            }
            saved = registry.register_factor(record)
            return {"ok": True, "action": action, "factor": saved,
                    "note": "已登记为 operator-entry，下一窗口起参与扫描；"
                            "不自动晋升任何统计结论"}
        if existing is None:
            raise ValueError(f"factor is not registered: {factor_id}")
        existing["status"] = "disabled" if action == "disable" else "active"
        existing.setdefault("metadata", {})
        existing["metadata"]["status_operator"] = operator
        registry.register_factor(existing)
        return {"ok": True, "action": action, "factor_id": factor_id,
                "status": existing["status"],
                "note": "停用后下一窗口起不参与 C 线扫描与 B 线候选打分"
                        if action == "disable" else "已恢复参与扫描"}
    finally:
        registry.close()


def factor_ledger(workdir: Path) -> dict:
    """Change ledger from the immutable factor_versions table."""
    db = workdir / "registry.db"
    if not db.is_file():
        return {"error": "registry not seeded"}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [
            {"factor_id": r["logical_key"], "version": r["version"],
             "body": json.loads(r["body"])}
            for r in conn.execute(
                "SELECT logical_key, version, body FROM factor_versions "
                "WHERE kind='factor' ORDER BY logical_key, version"
            )
        ]
        return {"ledger": rows}
    finally:
        conn.close()
