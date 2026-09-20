"""Chapter 16 backend: bound human labels, durable handoffs and governed skill proposals."""

from __future__ import annotations

import json
import os

from .contracts import digest
from .feedback_service import FeedbackService
from .scan_service import ScanService
from .skill_governance import SkillGovernance


class CognitiveLoop:
    def __init__(self, path):
        self.feedback = FeedbackService(path)
        self.scans = ScanService(path)
        self.registry = self.feedback.registry
        self.db = self.registry.db
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS cognitive_handoffs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, body TEXT NOT NULL)"
        )
        self.db.commit()

    def close(self):
        self.scans.close()
        self.feedback.close()

    def read(self, request_id):
        row = self.db.execute(
            "SELECT body FROM cognitive_handoffs WHERE id=?", (request_id,)
        ).fetchone()
        if not row:
            raise KeyError(request_id)
        return json.loads(row[0])

    def _save(self, request_id, body):
        with self.registry.transaction():
            self.db.execute(
                "UPDATE cognitive_handoffs SET body=? WHERE id=?",
                (json.dumps(body), request_id),
            )
            self.registry._audit(
                "COGNITIVE_HANDOFF", {"request_id": request_id, **body}
            )

    def respond(
        self,
        *,
        request_id,
        kind,
        payload,
        alert_id=None,
        factor_db_path=None,
        skill_name=None,
        context=None,
        supplement=None,
    ):
        if not request_id:
            raise ValueError("request id required")
        fingerprint = digest(
            {
                "kind": kind,
                "payload": payload,
                "alert_id": alert_id,
                "factor_db_path": factor_db_path,
                "skill_name": skill_name,
                "context": context,
                "supplement": supplement,
            }
        )
        payload = dict(payload)
        if kind in {"alert_feedback", "candidate_review"}:
            ref = alert_id or payload.get("alert_id")
            row = self.db.execute(
                "SELECT * FROM scan_alerts WHERE id=?", (ref,)
            ).fetchone()
            if not row or row["status"] == "WITHDRAWN":
                raise ValueError("feedback requires a real current scan alert")
            alert = json.loads(row["body"])
            evidence = self.registry.asset(alert["evidence_ref"])
            if evidence["status"] != "VALID":
                raise ValueError("alert evidence invalidated")
            if kind == "candidate_review":
                if payload.get("factor_id") != alert["factor_id"]:
                    raise ValueError("candidate and alert factor mismatch")
            else:
                if payload.get("alert_id") != ref:
                    raise ValueError("alert binding mismatch")
                source = self.registry.asset(evidence["dependencies"][0])["body"]
                factor = next(
                    f
                    for f in source["factors"]
                    if f["factor_id"] == alert["factor_id"]
                    and str(f.get("scope_id", "global")) == alert["scope_id"]
                    and str(f.get("metric_id", "metric")) == alert["metric_id"]
                )
                source_kind = factor.get("kind", "unknown")
                if "source_kind" in payload and payload["source_kind"] != source_kind:
                    raise ValueError("source_kind must match the scanned factor")
                payload["source_kind"] = source_kind
        elif kind == "factor_supplement":
            if not factor_db_path:
                raise ValueError("factor registry path required")
        else:
            raise ValueError("unknown cognitive feedback kind")
        supplemented = (
            kind == "candidate_review" and payload.get("decision") == "supplemented"
        )
        if supplemented and (not supplement or not factor_db_path):
            raise ValueError(
                "supplemented review requires factor payload and registry path"
            )
        if supplement is not None and not supplemented:
            raise ValueError(
                "factor supplement attachment only allowed on supplemented review"
            )
        if skill_name and (kind != "alert_feedback" or not context):
            raise ValueError(
                "skill learning requires alert feedback and explicit scope"
            )
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT * FROM cognitive_handoffs WHERE id=?", (request_id,)
            ).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise ValueError("request id reused with different handoff")
                state = json.loads(old["body"])
                if state["status"] == "COMPLETED":
                    return state
                if state["status"] == "RUNNING":
                    try:
                        os.kill(state["owner_pid"], 0)
                    except ProcessLookupError:
                        pass
                    else:
                        return {"status": "BUSY", "request_id": request_id}
            state = {
                "status": "RUNNING",
                "owner_pid": os.getpid(),
                "alert_ref": (alert_id or payload.get("alert_id"))
                if kind != "factor_supplement"
                else None,
                "claim_promotion_allowed": False,
            }
            self.db.execute(
                "INSERT OR REPLACE INTO cognitive_handoffs VALUES (?,?,?)",
                (request_id, fingerprint, json.dumps(state)),
            )
        try:
            event = self.feedback.submit(
                request_id="cognitive:" + request_id, kind=kind, payload=payload
            )
            current = next(
                e
                for e in self.feedback.ledger()["entries"]
                if e["event_id"] == event["event_id"]
            )
            if not current["is_current"]:
                raise ValueError("superseded feedback cannot resume a handoff")
            state["feedback"] = event
            self._save(request_id, state)
            if kind == "factor_supplement":
                state["registration"] = self.feedback.register_supplement(
                    event_id=event["event_id"], factor_db_path=factor_db_path
                )
            if supplemented:
                extra = self.feedback.submit(
                    request_id="cognitive-supplement:" + request_id,
                    kind="factor_supplement",
                    payload=supplement,
                )
                state["supplement_feedback"] = extra
                state["registration"] = self.feedback.register_supplement(
                    event_id=extra["event_id"],
                    factor_db_path=factor_db_path,
                )
            if skill_name:
                skills = SkillGovernance(self.registry.path)
                try:
                    state["skill_proposal"] = skills.learn_from_feedback(
                        event_id=event["event_id"], name=skill_name, context=context
                    )
                finally:
                    skills.close()
            state.update(
                status="COMPLETED",
                next_step="independent_validation_and_human_release"
                if skill_name
                else "next_window_validation",
            )
            self._save(request_id, state)
            return state
        except Exception as exc:
            state.update(status="FAILED", error=str(exc)[:500])
            self._save(request_id, state)
            raise


def execute_cognitive(*, db_path, action, parameters=None):
    service = CognitiveLoop(db_path)
    try:
        if action not in {"respond", "read"}:
            raise ValueError("unknown cognitive operation")
        return getattr(service, action)(**(parameters or {}))
    finally:
        service.close()
