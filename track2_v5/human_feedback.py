"""Human-in-the-loop feedback intake (D5).

Operators enter the loop at three touchpoints:

1. Candidate review — confirm / reject / supplement a FACTOR_CANDIDATE or
   WATCHLIST item.  A human confirmation never promotes a claim by itself;
   it only attaches a structured label and routes the candidate into the
   validation queue.  The evidence gates in claim_ledger.py stay in charge.
2. Factor supplement — register an unregistered real-world event (e.g. an
   offline SMS push) into the FactorRegistry with source_type=human_reported
   so it joins the next search grid with honest provenance.
3. Alert feedback — every C-line alert gets a useful / false_positive label.
   Labels feed budget_calibration(): scanning budget is shifted away from
   directions with low precision and toward directions with high precision.

Determinism: entries are sequence-numbered; no wall-clock is read inside the
computation paths, so the same feedback sequence always yields the same
calibration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .factor_registry import FactorRegistry
from .persistence import atomic_json

CANDIDATE_DECISIONS = ("confirmed", "rejected", "supplemented")
ALERT_LABELS = ("useful", "false_positive")
ALERT_CLAIM_TYPES = ("WATCHLIST", "FACTOR_CANDIDATE")

# Budget multipliers are deliberately conservative: human feedback steers
# the scan budget, it never silences a direction entirely.
MULTIPLIER_MIN, MULTIPLIER_MAX = 0.5, 1.5
PRECISION_LOW, PRECISION_HIGH = 0.3, 0.7


class HumanFeedbackStore:
    """JSON-backed structured feedback store with digest-chained entries."""

    def __init__(self, path: str | Path, *, autosave: bool = True):
        self.path = Path(path)
        self.autosave = autosave
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"version": 1, "seq": 0, "entries": []}

    # ---- internal --------------------------------------------------------
    def _append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.data["seq"] += 1
        prev = self.data["entries"][-1]["digest"] if self.data["entries"] else "genesis"
        body = {
            "seq": self.data["seq"],
            "kind": kind,
            "prev_digest": prev,
            **payload,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        body["digest"] = digest
        self.data["entries"].append(body)
        if self.autosave:
            self.save()
        return body

    def save(self) -> None:
        atomic_json(self.path, self.data)

    # ---- touchpoint 1: candidate review ----------------------------------
    def review_candidate(
        self,
        factor_id: str,
        decision: str,
        operator: str,
        note: str = "",
        claim_type: str = "FACTOR_CANDIDATE",
    ) -> dict[str, Any]:
        """Attach a structured human label to a candidate.

        Returns the entry plus a routing hint.  `confirmed` only queues the
        candidate for validation — the statistical gates still decide the
        final claim level.  `supplemented` requires a note describing what
        the operator knows that the system does not.
        """
        if (
            claim_type not in ALERT_CLAIM_TYPES
            or not factor_id.strip()
            or not operator.strip()
        ):
            raise ValueError(
                "candidate review requires an eligible claim, factor and operator"
            )
        if decision not in CANDIDATE_DECISIONS:
            raise ValueError(f"unknown decision: {decision}")
        if decision == "supplemented" and not note.strip():
            raise ValueError("supplemented requires a note")
        entry = self._append(
            "candidate_review",
            {
                "factor_id": factor_id,
                "decision": decision,
                "operator": operator,
                "note": note,
                "claim_type": claim_type,
            },
        )
        routing = {
            "confirmed": "queued_for_validation",
            "rejected": "demoted_to_context",
            "supplemented": "queued_for_validation_with_human_note",
        }[decision]
        return {"entry": entry, "routing": routing}

    # ---- touchpoint 2: factor supplement ---------------------------------
    def register_factor_supplement(
        self,
        registry: FactorRegistry,
        factor_id: str,
        name: str,
        kind: str,
        operator: str,
        note: str,
        *,
        current_window: int = 0,
        available_day: int = 0,
    ) -> dict[str, Any]:
        """Register an operator-reported factor into the FactorRegistry.

        Provenance is explicit: source_type=human_reported and a license_ref
        marking it as an operator entry, so downstream rules that require a
        re-checkable license keep it out of production conclusions.
        """
        if not note.strip():
            raise ValueError("factor supplement requires a note")
        intake = registry.intake_next_window(
            registry.get_factor(factor_id)
            or {
                "factor_id": factor_id,
                "name": name,
                "description": note,
                "source_type": "human_reported",
                "license_ref": "operator-entry",
                "metadata": {"kind": kind, "reported_by": operator},
            },
            evidence=[
                {
                    "factor_id": factor_id,
                    "evidence_type": "human_supplement",
                    "excerpt": note,
                    "source_uri": "manual:" + operator,
                    "license_ref": "operator-entry",
                    "metadata": {"operator": operator, "kind": kind},
                }
            ],
            current_window=current_window,
            available_day=available_day,
        )
        factor = registry.get_factor(factor_id)
        entry = self._append(
            "factor_supplement",
            {
                "factor_id": factor_id,
                "factor_kind": kind,
                "operator": operator,
                "note": note,
            },
        )
        return {"factor": factor, "entry": entry, "intake": intake}

    # ---- touchpoint 3: alert feedback ------------------------------------
    def record_alert_feedback(
        self,
        alert_id: str,
        label: str,
        operator: str,
        source_kind: str = "unknown",
    ) -> dict[str, Any]:
        if label not in ALERT_LABELS:
            raise ValueError(f"unknown alert label: {label}")
        if not alert_id.strip() or not operator.strip():
            raise ValueError("alert_id and operator are required")
        previous = next(
            (
                e
                for e in reversed(self.data["entries"])
                if e["kind"] == "alert_feedback" and e["alert_id"] == alert_id
            ),
            None,
        )
        if previous and previous["source_kind"] != source_kind:
            raise ValueError("an alert cannot change source_kind")
        if previous and previous["label"] == label:
            return dict(previous)
        return self._append(
            "alert_feedback",
            {
                "alert_id": alert_id,
                "label": label,
                "operator": operator,
                "source_kind": source_kind,
                "supersedes_seq": previous["seq"] if previous else None,
            },
        )

    # ---- calibration ------------------------------------------------------
    def precision_by_source(self) -> dict[str, dict[str, Any]]:
        """Useful/(useful+false_positive) per source_kind of reviewed alerts."""
        stats: dict[str, dict[str, int]] = {}
        latest = {
            entry["alert_id"]: entry
            for entry in self.data["entries"]
            if entry["kind"] == "alert_feedback"
        }
        for entry in latest.values():
            bucket = stats.setdefault(
                entry["source_kind"], {"useful": 0, "false_positive": 0}
            )
            bucket[entry["label"]] += 1
        result = {}
        for source_kind, counts in stats.items():
            total = counts["useful"] + counts["false_positive"]
            result[source_kind] = {
                "precision": counts["useful"] / total,
                "n_labels": total,
            }
        return result

    def budget_calibration(self, min_labels: int = 4) -> dict[str, float]:
        """Scan-budget multiplier per source_kind.

        Below `min_labels` the direction stays at 1.0 (cold start: do not
        act on anecdotes).  Precision < PRECISION_LOW halves the budget,
        > PRECISION_HIGH raises it by half; clamped to [0.5, 1.5].
        """
        multipliers = {}
        for source_kind, stats in self.precision_by_source().items():
            if stats["n_labels"] < min_labels:
                multipliers[source_kind] = 1.0
                continue
            precision = stats["precision"]
            if precision < PRECISION_LOW:
                multipliers[source_kind] = MULTIPLIER_MIN
            elif precision > PRECISION_HIGH:
                multipliers[source_kind] = MULTIPLIER_MAX
            else:
                multipliers[source_kind] = 1.0
        return multipliers

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for entry in self.data["entries"]:
            counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
        return {
            "entries": self.data["seq"],
            "by_kind": counts,
            "budget_calibration": self.budget_calibration(),
        }


def run_demo(output_path=None) -> dict[str, Any]:
    """Deterministic smoke demo: one review, one supplement, alert labels."""
    import tempfile

    store = HumanFeedbackStore(Path(tempfile.mkdtemp()) / "feedback.json")
    store.review_candidate(
        "internal.vendor.sms_provider_switch",
        "confirmed",
        operator="op.demo",
        note="当天确实切换了短信供应商，未走发布登记。",
    )
    registry = FactorRegistry()
    store.register_factor_supplement(
        registry,
        "internal.offline.sms_push_day40",
        "day40 线下短信推送",
        kind="internal_event",
        operator="op.demo",
        note="运营补登：day 40 有一次未登记的短信推送。",
    )
    for index in range(5):
        store.record_alert_feedback(
            f"alert-{index:03d}",
            "useful" if index < 4 else "false_positive",
            operator="op.demo",
            source_kind="internal_event",
        )
    store.save()
    result = store.summary()
    if output_path:
        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
