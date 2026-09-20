"""Transactional human feedback API with idempotency, revisions and validation queue."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import digest, finite, integer
from .human_feedback import HumanFeedbackStore
from .hypothesis_registry import HypothesisRegistry


class FeedbackService:
    def __init__(self, path):
        self.registry = HypothesisRegistry(path)
        self.db = self.registry.db
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS feedback_events(id TEXT PRIMARY KEY, kind TEXT NOT NULL, logical_key TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(kind,logical_key,revision));
          CREATE TABLE IF NOT EXISTS feedback_requests(id TEXT PRIMARY KEY, payload_digest TEXT NOT NULL, event_id TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS validation_queue(id TEXT PRIMARY KEY, factor_id TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
        """)

    def close(self):
        self.registry.close()

    def submit(self, *, request_id, kind, payload):
        if not request_id or kind not in {
            "candidate_review",
            "alert_feedback",
            "factor_supplement",
        }:
            raise ValueError(
                "named idempotency request and supported feedback kind required"
            )
        fingerprint = digest({"kind": kind, "payload": payload})
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT * FROM feedback_requests WHERE id=?", (request_id,)
            ).fetchone()
            if old:
                if old["payload_digest"] != fingerprint:
                    raise ValueError("idempotency key reused with different feedback")
                return self.read(old["event_id"])
            state = {"version": 1, "seq": 0, "entries": []}
            events = [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT body FROM feedback_events ORDER BY rowid"
                )
            ]
            state["entries"] = [e["entry"] for e in events]
            state["seq"] = len(state["entries"])
            store = HumanFeedbackStore(
                Path(self.registry.path).with_suffix(".unused_feedback.json"),
                autosave=False,
            )
            store.data = state
            if kind == "candidate_review":
                output = store.review_candidate(
                    **{k: v for k, v in payload.items() if k != "current_window"}
                )
                entry = output["entry"]
                logical = payload["factor_id"]
            elif kind == "alert_feedback":
                entry = store.record_alert_feedback(**payload)
                output = {"entry": entry, "routing": "next_window_budget_calibration"}
                logical = payload["alert_id"]
            else:
                if (
                    not payload.get("operator")
                    or not payload.get("note")
                    or not payload.get("factor_id")
                    or type(payload.get("current_window")) is not int
                    or type(payload.get("available_day")) is not int
                ):
                    raise ValueError(
                        "factor supplement requires operator, note, factor and explicit window/availability"
                    )
                snapshots = payload.get("snapshots", [])
                if not isinstance(snapshots, list) or len(snapshots) > 10000:
                    raise ValueError("at most 10000 factor snapshots allowed")
                keys = set()
                for snapshot in snapshots:
                    day = integer(snapshot["day"], "snapshot day")
                    finite(snapshot["value"], "snapshot value")
                    key = (snapshot.get("scope_id", "global"), day)
                    if key in keys or day > payload["available_day"]:
                        raise ValueError("duplicate or future factor snapshot")
                    keys.add(key)
                entry = store._append(kind, payload)
                output = {"entry": entry, "routing": "factor_registration_pending"}
                logical = payload["factor_id"]
            previous = self.db.execute(
                "SELECT * FROM feedback_events WHERE kind=? AND logical_key=? ORDER BY revision DESC LIMIT 1",
                (kind, logical),
            ).fetchone()
            if previous and json.loads(previous["body"])["payload"] == payload:
                event_id = previous["id"]
                output = json.loads(previous["body"])
            else:
                revision = previous["revision"] + 1 if previous else 1
                event_id = digest(
                    {
                        "kind": kind,
                        "key": logical,
                        "revision": revision,
                        "payload": payload,
                    }
                )
                output = {
                    **output,
                    "event_id": event_id,
                    "revision": revision,
                    "supersedes": previous["id"] if previous else None,
                    "payload": payload,
                    "kind": kind,
                    "claim_promotion_allowed": False,
                }
                self.db.execute(
                    "INSERT INTO feedback_events VALUES (?,?,?,?,?)",
                    (event_id, kind, logical, revision, json.dumps(output)),
                )
                if kind in {"candidate_review", "factor_supplement"}:
                    status = (
                        "REJECTED"
                        if payload.get("decision") == "rejected"
                        else "AWAITING_STATISTICAL_VALIDATION"
                    )
                    self.db.execute(
                        "UPDATE validation_queue SET status='SUPERSEDED' WHERE factor_id=? AND status IN ('AWAITING_STATISTICAL_VALIDATION','REJECTED')",
                        (logical,),
                    )
                    self.db.execute(
                        "INSERT INTO validation_queue VALUES (?,?,?,?)",
                        (
                            event_id,
                            logical,
                            status,
                            json.dumps(
                                {
                                    "event_id": event_id,
                                    "eligible_from_window": payload.get(
                                        "current_window", 0
                                    )
                                    + 1,
                                }
                            ),
                        ),
                    )
                self.registry._audit("HUMAN_FEEDBACK_REVISED", output)
            self.db.execute(
                "INSERT INTO feedback_requests VALUES (?,?,?)",
                (request_id, fingerprint, event_id),
            )
        return output

    def read(self, event_id):
        row = self.db.execute(
            "SELECT body FROM feedback_events WHERE id=?", (event_id,)
        ).fetchone()
        if not row:
            raise KeyError(event_id)
        return json.loads(row[0])

    def queue(self):
        return [
            {**dict(r), "body": json.loads(r["body"])}
            for r in self.db.execute("SELECT * FROM validation_queue ORDER BY rowid")
        ]

    def register_supplement(self, *, event_id, factor_db_path):
        from .factor_registry import FactorRegistry

        event = self.read(event_id)
        if event["kind"] != "factor_supplement":
            raise ValueError("not a factor supplement")
        row = self.db.execute(
            "SELECT * FROM validation_queue WHERE id=?", (event_id,)
        ).fetchone()
        if row["status"] == "REGISTERED":
            return json.loads(row["body"])
        if row["status"] != "AWAITING_STATISTICAL_VALIDATION":
            raise ValueError("superseded/rejected supplement cannot register")
        p = event["payload"]
        factors = FactorRegistry(factor_db_path)
        try:
            existing = factors.get_factor(p["factor_id"])
            factor = existing or {
                "factor_id": p["factor_id"],
                "name": p.get("name", p["factor_id"]),
                "source_type": "human_reported",
                "license_ref": "operator-entry",
                "metadata": {"kind": p.get("factor_kind", "event")},
            }
            result = factors.intake_next_window(
                factor,
                evidence=[
                    {
                        "evidence_id": event_id,
                        "factor_id": p["factor_id"],
                        "source_uri": "manual:" + p["operator"],
                        "license_ref": "operator-entry",
                        "excerpt": p["note"],
                    }
                ],
                snapshots=[
                    {
                        "factor_id": p["factor_id"],
                        "day": row["day"],
                        "value": row["value"],
                        "scope_id": row.get("scope_id", "global"),
                        "source_uri": "manual:" + p["operator"],
                        "license_ref": "operator-entry",
                    }
                    for row in p.get("snapshots", [])
                ],
                current_window=p["current_window"],
                available_day=p["available_day"],
            )
        finally:
            factors.close()
        with self.registry.transaction():
            self.db.execute(
                "UPDATE validation_queue SET status='REGISTERED',body=? WHERE id=?",
                (json.dumps(result), event_id),
            )
            self.registry._audit(
                "FEEDBACK_FACTOR_REGISTERED", {"event_id": event_id, **result}
            )
        return result

    def ledger(self):
        """Human-label ledger view; labels never become statistical claims."""
        events = [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT body FROM feedback_events ORDER BY rowid"
            )
        ]
        latest = {
            (e["kind"], e["payload"].get("alert_id", e["payload"].get("factor_id"))): e[
                "event_id"
            ]
            for e in events
        }
        return {
            "entries": [
                {
                    **e,
                    "entry_type": "HUMAN_LABEL",
                    "is_current": latest[
                        (
                            e["kind"],
                            e["payload"].get("alert_id", e["payload"].get("factor_id")),
                        )
                    ]
                    == e["event_id"],
                    "claim_promotion_allowed": False,
                }
                for e in events
            ]
        }

    def calibration(self):
        store = HumanFeedbackStore(
            Path(self.registry.path).with_suffix(".unused_feedback.json"),
            autosave=False,
        )
        store.data = {
            "entries": [
                json.loads(r[0])["entry"]
                for r in self.db.execute(
                    "SELECT body FROM feedback_events WHERE kind='alert_feedback' ORDER BY rowid"
                )
            ]
        }
        return store.budget_calibration()
