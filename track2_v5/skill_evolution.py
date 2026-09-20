"""Skill self-evolution (D6): Trace2Skill-style loop, gated by evidence.

RSI is deliberately narrowed to the *skill layer*: what evolves are explicit
rule artifacts (how to drill down, which checks to run, which template to
use).  Model weights are frozen and the statistical core is off-limits.

Loop (mirrors Trace2Skill, arXiv:2603.25158, with our own gate):

1. analyze_traces   — success/failure execution traces are turned into
   rule patches in parallel (deterministic analysts, no LLM required for
   the reference path).
2. consolidate      — patches are merged key-wise; conflicting patches for
   the same trigger are excluded and reported (conflict-free consolidation).
3. shadow_evaluate  — the candidate skill is replayed in shadow mode on a
   holdout case set; it never touches live decisions.
4. evidence gate    — the candidate replaces the active skill only if its
   holdout score improves by at least min_delta.  The same philosophy as
   the claim gates: no evidence, no promotion.
5. versioned store  — every version is kept with a changelog; rollback is
   one call.

Hard boundary: SELF_MODIFICATION_FORBIDDEN lists components this loop may
never edit (statistical core and the evidence gates themselves).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .persistence import atomic_json

SELF_MODIFICATION_FORBIDDEN = (
    "statistical_core",  # joint-null max-T, AIPW SE, decomposition closure
    "evidence_gates",  # claim_ledger gates, this module's own promotion gate
    "release_actions",  # anything touching real traffic
)


def assert_evolvable(target: str) -> None:
    """Guard rail: refuse to evolve protected components."""
    if not target or any(
        part in SELF_MODIFICATION_FORBIDDEN
        for part in target.replace("/", ".").split(".")
    ):
        raise ValueError(f"component is not self-evolvable: {target}")


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


# ---- step 1: trace analysis ----------------------------------------------
def analyze_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn execution traces into rule patches (deterministic analysts).

    A trace is {trace_id, outcome, context, failure_kind?, lesson}.  Failure
    traces propose guard rules ("when <context>, do <lesson>"); success
    traces propose reinforcement rules.  Each patch carries its evidence.
    """
    patches = []
    for trace in traces:
        lesson = str(trace.get("lesson", "")).strip()
        if not lesson:
            continue
        context = dict(trace.get("context") or {})
        if not trace.get("trace_id"):
            raise ValueError("trace_id is required")
        outcome = trace.get("outcome")
        if outcome not in ("success", "failure"):
            raise ValueError(f"unknown trace outcome: {outcome}")
        patches.append(
            {
                "when": context,
                "action": lesson,
                "polarity": "guard" if outcome == "failure" else "reinforce",
                "evidence": [trace.get("trace_id")],
                **({"replaces": trace["replaces"]} if trace.get("replaces") else {}),
            }
        )
    return patches


# ---- step 2: conflict-free consolidation ---------------------------------
def consolidate(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge patches by (when, action); conflicts are excluded, not voted.

    Two patches conflict when they share the same trigger (`when`) but
    prescribe different actions.  Voting would let a noisy majority overwrite
    a rare but real failure mode, so conflicts go to the report instead.
    """
    by_trigger: dict[str, list[dict[str, Any]]] = {}
    for patch in patches:
        key = _digest(patch["when"])
        by_trigger.setdefault(key, []).append(patch)
    merged, conflicts = [], []
    for group in by_trigger.values():
        actions = {patch["action"] for patch in group}
        if len(actions) > 1:
            conflicts.append(
                {
                    "when": group[0]["when"],
                    "actions": sorted(actions),
                    "evidence": [t for p in group for t in p["evidence"]],
                }
            )
            continue
        merged.append(
            {
                "when": group[0]["when"],
                "action": group[0]["action"],
                "polarity": group[0]["polarity"],
                "evidence": sorted({t for p in group for t in p["evidence"]}),
                **(
                    {"replaces": group[0]["replaces"]}
                    if group[0].get("replaces")
                    else {}
                ),
            }
        )
    merged.sort(key=lambda rule: _digest(rule))
    return {"rules": merged, "conflicts": conflicts}


def validate_rules(rules: list[dict[str, Any]]) -> None:
    if not isinstance(rules, list):
        raise ValueError("rules must be a list")
    for rule in rules:
        if (
            not isinstance(rule.get("when"), dict)
            or not isinstance(rule.get("action"), str)
            or not rule["action"].strip()
        ):
            raise ValueError("rule requires object when and non-empty action")
        if not rule.get("evidence") or any(
            not isinstance(e, str) or not e for e in rule["evidence"]
        ):
            raise ValueError("rule requires non-empty evidence references")
        # Only equality predicates are executable here. No arbitrary expressions.
        if any(isinstance(v, (dict, list)) for v in rule["when"].values()):
            raise ValueError("rule predicates must use scalar equality values")
    json.dumps(rules, allow_nan=False)


def merge_with_active(
    active: list[dict[str, Any]], patches: list[dict[str, Any]]
) -> dict[str, Any]:
    """Reject overlapping contradictory actions unless exact replacement is bound by digest."""
    rules = copy.deepcopy(active)
    conflicts, replacements = [], []
    for patch in patches:
        validate_rules([patch])
        overlapping = [
            r
            for r in rules
            if all(
                k not in r["when"] or r["when"][k] == v
                for k, v in patch["when"].items()
            )
        ]
        conflicting = [r for r in overlapping if r["action"] != patch["action"]]
        if conflicting:
            if (
                len(conflicting) == 1
                and conflicting[0]["when"] == patch["when"]
                and patch.get("replaces") == _digest(conflicting[0])
            ):
                old = conflicting[0]
                rules.remove(old)
                replacements.append(
                    {"old_digest": _digest(old), "new_action": patch["action"]}
                )
            else:
                conflicts.append(
                    {
                        "when": patch["when"],
                        "actions": sorted(
                            {patch["action"], *(r["action"] for r in conflicting)}
                        ),
                        "reason": "overlapping_active_rule_requires_exact_replacement",
                    }
                )
                continue
        same = next(
            (
                r
                for r in rules
                if r["when"] == patch["when"] and r["action"] == patch["action"]
            ),
            None,
        )
        if same:
            same["evidence"] = sorted(set(same["evidence"] + patch["evidence"]))
        else:
            rules.append({k: v for k, v in patch.items() if k != "replaces"})
    return {"rules": rules, "conflicts": conflicts, "replacements": replacements}


# ---- step 3: shadow evaluation -------------------------------------------
def _matches(rule_when: dict[str, Any], context: dict[str, Any]) -> bool:
    return all(context.get(key) == value for key, value in rule_when.items())


def shadow_evaluate(
    rules: list[dict[str, Any]], holdout_cases: list[dict[str, Any]]
) -> float:
    """Replay rules on holdout cases; score = fraction of cases answered right.

    A case is {case_id, context, expected_action}.  A case scores 1 when the
    first matching rule prescribes the expected action; cases with no
    matching rule score 0 (a skill that says nothing earns nothing).
    """
    if not holdout_cases:
        return 0.0
    hits = 0
    for case in holdout_cases:
        for rule in rules:
            if _matches(rule["when"], case.get("context", {})):
                if rule["action"] == case.get("expected_action"):
                    hits += 1
                break
    return hits / len(holdout_cases)


# ---- versioned skill store ------------------------------------------------
class SkillStore:
    """JSON-backed versioned skill store with one-call rollback."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"version": 1, "skills": {}}

    def save(self) -> None:
        atomic_json(self.path, self.data)

    def _record(self, name: str) -> dict[str, Any]:
        return self.data["skills"].setdefault(
            name, {"versions": [], "active": None, "changelog": []}
        )

    def register(
        self, name: str, rules: list[dict[str, Any]], note: str
    ) -> dict[str, Any]:
        assert_evolvable(name)
        validate_rules(rules)
        record = self._record(name)
        version = len(record["versions"]) + 1
        entry = {
            "version": version,
            "rules": copy.deepcopy(rules),
            "digest": _digest({"name": name, "version": version, "rules": rules}),
            "note": note,
        }
        record["versions"].append(entry)
        record["changelog"].append(
            {"version": version, "event": "registered", "note": note}
        )
        return copy.deepcopy(entry)

    def active(self, name: str) -> dict[str, Any] | None:
        record = self.data["skills"].get(name)
        if not record or record["active"] is None:
            return None
        entry = next(v for v in record["versions"] if v["version"] == record["active"])
        if (
            record.get("governed") and not entry.get("governance_binding")
        ) or not self._evidence_valid(entry):
            record["changelog"].append(
                {"event": "evidence_suspended", "version": record["active"]}
            )
            record["active"] = None
            self.save()
            return None
        return copy.deepcopy(entry)

    def bind_evidence(self, name, version, registry, dependencies):
        if registry.path == ":memory:" or not dependencies:
            raise ValueError("skills require durable evidence dependencies")
        entry = next(
            v for v in self._record(name)["versions"] if v["version"] == version
        )
        ref = registry.add_asset(
            "skill",
            {"name": name, "version": version, "rules_digest": _digest(entry["rules"])},
            dependencies=dependencies,
        )
        entry["evidence_binding"] = {
            "registry_path": str(Path(registry.path).resolve()),
            "asset_ref": ref,
        }
        self.save()
        return ref

    @staticmethod
    def _evidence_valid(entry):
        governance = entry.get("governance_binding")
        if governance:
            from .skill_governance import SkillGovernance

            service = SkillGovernance(governance["registry_path"])
            try:
                item = service.get(governance["name"], governance["version"])
                if (
                    item["spec"]["digest"] != governance["spec_digest"]
                    or not item["lifecycle"]["execution_eligible"]
                    or item["lifecycle"]["trust_state"] != "trusted"
                ):
                    return False
            finally:
                service.close()
        binding = entry.get("evidence_binding")
        if not binding:
            return True  # Legacy non-evidence skills retain their validation rules.
        from .hypothesis_registry import HypothesisRegistry

        try:
            registry = HypothesisRegistry(binding["registry_path"])
            try:
                asset = registry.asset(binding["asset_ref"])
                return asset["status"] == "VALID" and asset["body"][
                    "rules_digest"
                ] == _digest(entry["rules"])
            finally:
                registry.close()
        except OSError, ValueError, KeyError:
            return False

    def validate_candidate(
        self,
        name: str,
        version: int,
        cases: list[dict[str, Any]],
        min_delta: float = 0.0,
    ) -> dict[str, Any]:
        assert_evolvable(name)
        if not math.isfinite(min_delta) or min_delta < 0:
            raise ValueError("min_delta must be finite and non-negative")
        record = self._record(name)
        entry = next((v for v in record["versions"] if v["version"] == version), None)
        if entry is None:
            raise ValueError("unknown candidate version")
        validate_rules(entry["rules"])
        if cases:
            ids = [c.get("case_id") for c in cases]
            if any(not i for i in ids) or len(set(ids)) != len(ids):
                raise ValueError("holdout requires unique non-empty case_id values")
            if any(
                not isinstance(c.get("context"), dict) or not c.get("expected_action")
                for c in cases
            ):
                raise ValueError("holdout requires context and expected_action")
        active = self.active(name)
        active_score = shadow_evaluate(active["rules"] if active else [], cases)
        candidate_score = shadow_evaluate(entry["rules"], cases)
        gate = {
            "passed": bool(cases)
            and candidate_score > active_score
            and candidate_score >= active_score + min_delta,
            "active_score": active_score,
            "candidate_score": candidate_score,
            "base_version": record["active"],
            "rules_digest": _digest(entry["rules"]),
            "holdout_digest": _digest(cases),
            "holdout_count": len(cases),
            "min_delta": min_delta,
        }
        entry["validation"] = gate
        record["changelog"].append({"event": "evaluated", "version": version, **gate})
        return copy.deepcopy(gate)

    def activate(self, name: str, version: int, note: str) -> None:
        assert_evolvable(name)
        record = self._record(name)
        entry = next((v for v in record["versions"] if v["version"] == version), None)
        if entry is None:
            raise ValueError(f"unknown version {version} for skill {name}")
        if record.get("governed") and not entry.get("governance_binding"):
            raise ValueError(
                "governed skill cannot bypass G0-G6 through legacy activation"
            )
        if not self._evidence_valid(entry):
            raise ValueError("dependent evidence is invalid; skill suspended")
        gate = entry.get("validation", {})
        if (
            not gate.get("passed")
            or gate.get("rules_digest") != _digest(entry["rules"])
            or gate.get("base_version") != record["active"]
        ):
            raise ValueError(
                "activation requires a passing validation bound to candidate and active version"
            )
        self._activate(record, version, note)

    @staticmethod
    def _activate(record: dict[str, Any], version: int, note: str) -> None:
        previous = record["active"]
        record["active"] = version
        record["changelog"].append(
            {
                "version": version,
                "event": "activated",
                "previous": previous,
                "note": note,
            }
        )

    def rollback(self, name: str, note: str = "rollback") -> dict[str, Any]:
        assert_evolvable(name)
        record = self._record(name)
        history = [c for c in record["changelog"] if c["event"] == "activated"]
        previous = history[-1]["previous"] if history else None
        if previous is None:
            raise ValueError("no previous version to roll back to")
        entry = next(v for v in record["versions"] if v["version"] == previous)
        if record.get("governed") and not entry.get("governance_binding"):
            raise ValueError(
                "governed rollback cannot target an unreviewed legacy skill"
            )
        if not self._evidence_valid(entry):
            raise ValueError("rollback target depends on invalidated evidence")
        if entry.get("validation", {}).get("rules_digest") != _digest(entry["rules"]):
            raise ValueError("rollback target changed since validation")
        self._activate(record, previous, note)
        self.save()
        return self.active(name)  # type: ignore


# ---- step 4+5: gated evolution -------------------------------------------
def evolve_skill(
    store: SkillStore,
    name: str,
    traces: list[dict[str, Any]],
    holdout_cases: list[dict[str, Any]],
    min_delta: float = 0.0,
) -> dict[str, Any]:
    """One full evolution round for one skill.

    The candidate (active rules + consolidated patches) is shadow-evaluated
    on the holdout set and promoted only if it beats the active skill by at
    least min_delta.  Every round is recorded, promoted or not.
    """
    assert_evolvable(name)
    patches = analyze_traces(traces)
    merged = consolidate(patches)
    active = store.active(name)
    active_rules = list(active["rules"]) if active else []
    combined = merge_with_active(active_rules, merged["rules"])
    merged["conflicts"].extend(combined["conflicts"])
    candidate_rules = combined["rules"]
    candidate_entry = store.register(name, candidate_rules, note="evolution candidate")
    gate = store.validate_candidate(
        name, candidate_entry["version"], holdout_cases, min_delta
    )
    active_score = gate["active_score"]
    candidate_score = gate["candidate_score"]
    promoted = gate["passed"] and not merged["conflicts"]
    if merged["conflicts"]:
        store.data["skills"][name]["versions"][-1]["validation"]["passed"] = False
    if promoted:
        store.activate(name, candidate_entry["version"], note="shadow gate passed")
    result = {
        "skill": name,
        "candidate_version": candidate_entry["version"],
        "active_score": active_score,
        "candidate_score": candidate_score,
        "promoted": promoted,
        "rules_added": len(candidate_rules) - len(active_rules),
        "replacements": combined["replacements"],
        "holdout_digest": gate["holdout_digest"],
        "conflicts_excluded": len(merged["conflicts"]),
        "conflicts": merged["conflicts"],
        "gate": f"holdout shadow score >= active + {min_delta}",
    }
    store.save()
    return result


def run_demo(output_path=None) -> dict[str, Any]:
    """Deterministic smoke demo on a tiny RCA-drilldown skill."""
    import tempfile

    store = SkillStore(Path(tempfile.mkdtemp()) / "skills.json")
    seed = store.register(
        "rca_drilldown",
        [
            {
                "when": {"metric": "rate"},
                "action": "decompose_first",
                "polarity": "reinforce",
                "evidence": ["seed"],
            }
        ],
        note="seed skill",
    )
    store.validate_candidate(
        "rca_drilldown",
        seed["version"],
        [
            {
                "case_id": "seed-validation",
                "context": {"metric": "rate"},
                "expected_action": "decompose_first",
            }
        ],
    )
    store.activate("rca_drilldown", seed["version"], note="validated seed")
    traces = [
        {
            "trace_id": "t1",
            "outcome": "failure",
            "context": {"metric": "rate"},
            "lesson": "check_mix_before_rate",
            "replaces": _digest(seed["rules"][0]),
        },
        {
            "trace_id": "t2",
            "outcome": "success",
            "context": {"metric": "count"},
            "lesson": "decompose_first",
        },
    ]
    holdout = [
        {
            "case_id": "c1",
            "context": {"metric": "rate"},
            "expected_action": "check_mix_before_rate",
        },
        {
            "case_id": "c2",
            "context": {"metric": "count"},
            "expected_action": "decompose_first",
        },
    ]
    result = evolve_skill(store, "rca_drilldown", traces, holdout)
    if output_path:
        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
