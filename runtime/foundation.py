"""Shared AgentTeams control-plane primitives and provider contracts.

This is deliberately dependency-free. It is a local conformance runtime, not
a claim that it is the official AgentTeams service. The adapter boundary makes
the same workflows runnable against a hosted control plane later.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class AgentIdentity:
    agent_id: str
    role: str
    allowed_states: list[str]
    capabilities: list[str]
    can_write: list[str]
    can_call: list[str]


@dataclass
class Event:
    event_id: str
    task_id: str
    trace_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    state_version: int
    created_at: str = field(default_factory=utc_now)


@dataclass
class Artifact:
    artifact_id: str
    task_id: str
    trace_id: str
    artifact_type: str
    schema_version: str
    producer: str
    payload: dict[str, Any]
    evidence_refs: list[str]
    created_at: str = field(default_factory=utc_now)


@dataclass
class Evidence:
    evidence_id: str
    task_id: str
    trace_id: str
    kind: str
    label: str
    source: str
    content: Any
    content_digest: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class TaskRecord:
    task_id: str
    trace_id: str
    domain: str
    input_payload: dict[str, Any]
    state: str
    state_version: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamTopology:
    team_id: str
    control_plane: str
    nodes: list[str]
    edges: list[dict[str, Any]]
    execution_semantics: dict[str, Any]


class StateTransitionError(RuntimeError):
    pass


class ConcurrentStateError(StateTransitionError):
    pass


class AuthorizationError(PermissionError):
    pass


class ApprovalError(RuntimeError):
    pass


class AgentTeamsControlPlane:
    """Authoritative task state, team identities, events, artifacts and approvals."""

    TRANSITIONS: dict[str, set[str]] = {
        "RECEIVED": {"FUSED", "INTENT_PARSED", "RECOVERING"},
        "FUSED": {"TRIAGED", "RECOVERING"},
        "TRIAGED": {"BOOTSTRAPPED", "AWAITING_APPROVAL", "NEEDS_HUMAN", "RECOVERING"},
        "BOOTSTRAPPED": {"LOCATED", "RETRYABLE_FAILURE", "NEEDS_HUMAN", "RECOVERING"},
        "LOCATED": {"PLANNED", "NEEDS_HUMAN", "RECOVERING"},
        "PLANNED": {
            "AWAITING_APPROVAL",
            "BLOCKED_BY_POLICY",
            "NEEDS_HUMAN",
            "RECOVERING",
        },
        "AWAITING_APPROVAL": {
            "PATCHED",
            "ACTION_DRAFTED",
            "MONITORING",
            "NEEDS_HUMAN",
            "BLOCKED_BY_POLICY",
            "RECOVERING",
        },
        "PATCHED": {"VERIFYING", "NEEDS_HUMAN", "RECOVERING"},
        "VERIFYING": {"RELEASE_READY", "PATCHED", "NEEDS_HUMAN", "RECOVERING"},
        "RELEASE_READY": {"POSTMORTEM", "CLOSED", "RECOVERING"},
        "POSTMORTEM": {"SKILL_DISTILLING", "CLOSED", "RECOVERING"},
        "SKILL_DISTILLING": {"CLOSED", "NEEDS_HUMAN", "RECOVERING"},
        "CLOSED": set(),
        "INTENT_PARSED": {"METRIC_CONFIRMED", "NEEDS_CLARIFICATION", "RECOVERING"},
        "METRIC_CONFIRMED": {"DATA_VALIDATED", "NEEDS_CLARIFICATION", "RECOVERING"},
        "DATA_VALIDATED": {
            "DIAGNOSING",
            "DATA_INSUFFICIENT",
            "RETRYABLE_QUERY_FAILURE",
            "RECOVERING",
        },
        "DIAGNOSING": {"EVIDENCE_GRADED", "DATA_INSUFFICIENT", "RECOVERING"},
        "EVIDENCE_GRADED": {"ACTION_DRAFTED", "DESCRIPTIVE_ONLY", "RECOVERING"},
        "DESCRIPTIVE_ONLY": {"ACTION_DRAFTED", "CLOSED", "RECOVERING"},
        "ACTION_DRAFTED": {"COMPLIANCE_REVIEWED", "BLOCKED_BY_GUARDRAIL", "RECOVERING"},
        "COMPLIANCE_REVIEWED": {
            "AWAITING_APPROVAL",
            "BLOCKED_BY_GUARDRAIL",
            "RECOVERING",
        },
        "MONITORING": {"REVIEWED", "MONITORING_ALERT", "RECOVERING"},
        "REVIEWED": {"CLOSED", "RECOVERING"},
        "NEEDS_CLARIFICATION": {"METRIC_CONFIRMED", "CLOSED", "RECOVERING"},
        "DATA_INSUFFICIENT": {
            "DESCRIPTIVE_ONLY",
            "NEEDS_HUMAN",
            "CLOSED",
            "RECOVERING",
        },
        "RETRYABLE_QUERY_FAILURE": {
            "DATA_VALIDATED",
            "NEEDS_HUMAN",
            "CLOSED",
            "RECOVERING",
        },
        "BLOCKED_BY_GUARDRAIL": {"NEEDS_HUMAN", "CLOSED", "RECOVERING"},
        "BLOCKED_BY_POLICY": {"NEEDS_HUMAN", "CLOSED", "RECOVERING"},
        "NEEDS_HUMAN": {
            "TRIAGED",
            "LOCATED",
            "PLANNED",
            "DATA_VALIDATED",
            "ACTION_DRAFTED",
            "CLOSED",
            "RECOVERING",
        },
        "RECOVERING": {
            "TRIAGED",
            "BOOTSTRAPPED",
            "LOCATED",
            "PLANNED",
            "PATCHED",
            "VERIFYING",
            "DATA_VALIDATED",
            "DIAGNOSING",
            "CLOSED",
            "NEEDS_HUMAN",
        },
        "RETRYABLE_FAILURE": {"BOOTSTRAPPED", "PATCHED", "NEEDS_HUMAN", "RECOVERING"},
        "MONITORING_ALERT": {"MONITORING", "REVIEWED", "NEEDS_HUMAN", "RECOVERING"},
    }

    def __init__(self) -> None:
        self.agents: dict[str, AgentIdentity] = {}
        self.skills: dict[str, dict[str, Any]] = {}
        self.topologies: dict[str, TeamTopology] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self.events: list[Event] = []
        self.artifacts: dict[str, Artifact] = {}
        self.evidence: dict[str, Evidence] = {}
        self.approvals: dict[str, dict[str, Any]] = {}

    def register_agent(self, identity: AgentIdentity) -> None:
        if identity.agent_id in self.agents:
            raise ValueError(f"duplicate agent identity: {identity.agent_id}")
        self.agents[identity.agent_id] = identity

    def register_skill(self, skill_id: str, manifest: dict[str, Any]) -> None:
        if skill_id in self.skills:
            raise ValueError(f"duplicate skill: {skill_id}")
        self.skills[skill_id] = manifest

    def register_topology(self, topology: TeamTopology) -> None:
        unknown = [node for node in topology.nodes if node not in self.agents]
        if unknown:
            raise ValueError(
                "topology references unknown agents: {}".format(", ".join(unknown))
            )
        self.topologies[topology.team_id] = topology

    def create_task(
        self,
        task_id: str,
        domain: str,
        input_payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> TaskRecord:
        if task_id in self.tasks:
            raise ValueError(f"duplicate task: {task_id}")
        task = TaskRecord(
            task_id, trace_id or new_id("trace"), domain, input_payload, "RECEIVED"
        )
        self.tasks[task_id] = task
        self._event(
            task,
            "TASK_CREATED",
            "control-plane",
            {"domain": domain, "input_digest": digest(input_payload)},
        )
        return task

    def _event(
        self, task: TaskRecord, event_type: str, actor: str, payload: dict[str, Any]
    ) -> Event:
        event = Event(
            new_id("evt"),
            task.task_id,
            task.trace_id,
            event_type,
            actor,
            payload,
            task.state_version,
        )
        self.events.append(event)
        return event

    def transition(
        self,
        task_id: str,
        target: str,
        actor: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
        expected_state_version: int | None = None,
    ) -> TaskRecord:
        task = self.tasks[task_id]
        if (
            expected_state_version is not None
            and task.state_version != expected_state_version
        ):
            raise ConcurrentStateError(
                "expected state version %d, found %d"
                % (expected_state_version, task.state_version)
            )
        allowed = self.TRANSITIONS.get(task.state, set())
        if target not in allowed:
            raise StateTransitionError(f"{task.state} -> {target} is not allowed")
        if actor not in {"control-plane", "AgentTeamsControlPlane"}:
            identity = self.agents.get(actor)
            if identity is None:
                raise AuthorizationError(f"unknown transition actor: {actor}")
            if target not in identity.allowed_states:
                raise AuthorizationError(
                    f"{actor} cannot own target state {target}"
                )
        previous = task.state
        task.state = target
        task.state_version += 1
        task.updated_at = utc_now()
        if metadata:
            task.metadata.update(metadata)
        self._event(
            task,
            "STATE_TRANSITION",
            actor,
            {
                "from": previous,
                "to": target,
                "reason": reason,
                "metadata": metadata or {},
            },
        )
        return task

    def publish_artifact(
        self,
        task_id: str,
        artifact_type: str,
        producer: str,
        payload: dict[str, Any],
        evidence_refs: list[str] | None = None,
        schema_version: str = "1.0",
    ) -> Artifact:
        task = self.tasks[task_id]
        artifact = Artifact(
            new_id("art"),
            task_id,
            task.trace_id,
            artifact_type,
            schema_version,
            producer,
            payload,
            evidence_refs or [],
        )
        self.artifacts[artifact.artifact_id] = artifact
        self._event(
            task,
            "ARTIFACT_PUBLISHED",
            producer,
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact_type,
                "evidence_refs": artifact.evidence_refs,
            },
        )
        return artifact

    def record_evidence(
        self, task_id: str, kind: str, label: str, source: str, content: Any
    ) -> Evidence:
        task = self.tasks[task_id]
        item = Evidence(
            new_id("ev"),
            task_id,
            task.trace_id,
            kind,
            label,
            source,
            content,
            digest(content),
        )
        self.evidence[item.evidence_id] = item
        self._event(
            task,
            "EVIDENCE_RECORDED",
            source,
            {
                "evidence_id": item.evidence_id,
                "kind": kind,
                "label": label,
                "content_digest": item.content_digest,
            },
        )
        return item

    def request_approval(
        self,
        task_id: str,
        actor: str,
        scope: dict[str, Any],
        expected_state: str | None = None,
    ) -> str:
        task = self.tasks[task_id]
        approval_id = new_id("approval")
        scope_digest = digest(scope)
        self.approvals[approval_id] = {
            "approval_id": approval_id,
            "task_id": task_id,
            "trace_id": task.trace_id,
            "requested_by": actor,
            "scope": scope,
            "scope_digest": scope_digest,
            "requested_state": task.state,
            "requested_state_version": task.state_version,
            "expected_state": expected_state,
            "status": "PENDING",
            "created_at": utc_now(),
        }
        self._event(
            task,
            "APPROVAL_REQUESTED",
            actor,
            {
                "approval_id": approval_id,
                "scope": scope,
                "scope_digest": scope_digest,
                "expected_state": expected_state,
            },
        )
        return approval_id

    def approve(
        self,
        approval_id: str,
        reviewer: str,
        decision: str = "APPROVED",
        note: str = "",
        decision_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approval = self.approvals[approval_id]
        if approval["status"] != "PENDING":
            raise ApprovalError("approval is not pending")
        if decision not in {"APPROVED", "REJECTED"}:
            raise ApprovalError("decision must be APPROVED or REJECTED")
        task = self.tasks[approval["task_id"]]
        if approval.get("expected_state") and task.state != approval["expected_state"]:
            raise ApprovalError(
                "approval expected task state {}, found {}".format(approval["expected_state"], task.state)
            )
        evidence = dict(decision_evidence or {})
        evidence.setdefault("provider", "local-conformance")
        evidence.setdefault("reviewer_identity", reviewer)
        evidence.setdefault("scope_digest", approval["scope_digest"])
        evidence.setdefault("event_id", new_id("approval_evt"))
        if evidence["reviewer_identity"] != reviewer:
            raise ApprovalError("reviewer identity does not match the approval actor")
        if evidence["scope_digest"] != approval["scope_digest"]:
            raise ApprovalError(
                "approval scope digest does not match the requested scope"
            )
        approval.update(
            {
                "status": decision,
                "reviewer": reviewer,
                "note": note,
                "decision_evidence": evidence,
                "decided_at": utc_now(),
            }
        )
        self._event(
            task,
            "APPROVAL_DECIDED",
            reviewer,
            {
                "approval_id": approval_id,
                "decision": decision,
                "note": note,
                "scope_digest": approval["scope_digest"],
                "decision_evidence": evidence,
            },
        )
        return approval

    def checkpoint_payload(self, task_id: str) -> dict[str, Any]:
        task = self.tasks[task_id]
        return {
            "task": asdict(task),
            "events": [asdict(e) for e in self.events if e.task_id == task_id],
            "artifacts": [
                asdict(a) for a in self.artifacts.values() if a.task_id == task_id
            ],
            "evidence": [
                asdict(e) for e in self.evidence.values() if e.task_id == task_id
            ],
            "approvals": [
                a for a in self.approvals.values() if a["task_id"] == task_id
            ],
        }

    def trace(self, task_id: str) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.events if e.task_id == task_id]

    def evidence_pack(self, task_id: str) -> dict[str, Any]:
        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "trace_id": task.trace_id,
            "domain": task.domain,
            "input_payload": task.input_payload,
            "state": task.state,
            "state_version": task.state_version,
            "artifacts": [
                asdict(a) for a in self.artifacts.values() if a.task_id == task_id
            ],
            "evidence": [
                asdict(e) for e in self.evidence.values() if e.task_id == task_id
            ],
            "approvals": [
                a for a in self.approvals.values() if a["task_id"] == task_id
            ],
            "trace": self.trace(task_id),
            "topologies": [asdict(topology) for topology in self.topologies.values()],
        }


class SQLiteCheckpointProvider:
    """Checkpoint storage only; it never owns task state transitions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints (task_id TEXT PRIMARY KEY, state_version INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    def save(self, task_id: str, state_version: int, payload: dict[str, Any]) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(task_id, state_version, payload, updated_at) VALUES (?, ?, ?, ?)",
                (task_id, state_version, canonical_json(payload), utc_now()),
            )

    def load(self, task_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(str(self.path)) as conn:
            row = conn.execute(
                "SELECT state_version, payload, updated_at FROM checkpoints WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "state_version": row[0],
            "payload": json.loads(row[1]),
            "updated_at": row[2],
        }


class LocalEvidenceProvider:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: str) -> Path:
        return self.root / (task_id + ".json")

    def write_pack(self, task_id: str, pack: dict[str, Any]) -> Path:
        path = self.path_for(task_id)
        pack["evidence_pack_path"] = str(path)
        pack["evidence_pack_relative_path"] = "evidence/" + path.name
        path.write_text(
            json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path
