"""G0–G6 durable method memory. Trust never substitutes for current identification."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import digest, finite
from .hypothesis_registry import HypothesisRegistry
from .skill_evolution import (
    SkillStore,
    assert_evolvable,
    consolidate,
    merge_with_active,
)
from .skill_replay import OPS, isolated_replay

CEILINGS = {
    "DESCRIPTIVE_FACT": 0,
    "WATCHLIST": 0,
    "CANDIDATE_ASSOCIATION": 1,
    "CONDITIONAL_TEMPORAL": 2,
    "OBSERVATIONAL_EFFECT_UNDER_ASSUMPTIONS": 3,
    "RANDOMIZED_EFFECT": 4,
    "COMPONENT_RANDOMIZED_EFFECT": 5,
}


def matches(applicability, context):
    return all(
        context.get(k) in v if isinstance(v, list) else context.get(k) == v
        for k, v in applicability.items()
    )


class SkillGovernance:
    def __init__(self, path, *, skill_store_path=None):
        self.registry = HypothesisRegistry(path)
        self.db = self.registry.db
        self.skill_store_path = str(
            skill_store_path or Path(path).with_suffix(".skills.json")
        )
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS skill_traces(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, data_ref TEXT NOT NULL, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS governed_skills(name TEXT NOT NULL, version INTEGER NOT NULL, spec TEXT NOT NULL, lifecycle TEXT NOT NULL, PRIMARY KEY(name,version));
          CREATE TABLE IF NOT EXISTS skill_suites(id TEXT PRIMARY KEY, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS skill_receipts(id TEXT PRIMARY KEY, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS skill_releases(seq INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL);
        """)

    def close(self):
        self.registry.close()

    def _log(self, event, body):
        with self.registry.transaction():
            self.registry._audit(event, body)

    def _data(self, ref, request):
        asset = self.registry.asset(ref)
        if (
            asset["status"] != "VALID"
            or asset["kind"] != "data"
            or asset["body"] != request
        ):
            raise ValueError("request must exactly match a valid versioned data asset")

    def capture(
        self,
        *,
        task_id,
        data_ref,
        context,
        operation,
        author,
        correction=None,
        failure_kind=None,
    ):
        if not task_id or not author or not isinstance(context, dict) or not context:
            raise ValueError("task, author and applicability context required")
        request = self.registry.asset(data_ref)["body"]
        self._data(data_ref, request)
        binding = {
            "task_id": task_id,
            "data_ref": data_ref,
            "skill_ref": "capture:" + author,
        }
        try:
            replay = isolated_replay(operation, request, binding)
        except TimeoutError:
            self._log(
                "G6_ISSUE", {"task_id": task_id, "failure_kind": "environment_timeout"}
            )
            return {"decision": "ISSUE", "reason": "environment_timeout"}
        body = {
            "task_id": task_id,
            "data_ref": data_ref,
            "context": context,
            "operation": operation,
            "author": author,
            "replay": replay,
            "outcome": "success" if replay["result"]["passed"] else "failure",
            "failure_kind": failure_kind,
            "correction": None,
        }
        if correction:
            if set(correction) != {"operation", "data_ref"}:
                raise ValueError("correction must reference a registered request")
            corrected = self.registry.asset(correction["data_ref"])["body"]
            self._data(correction["data_ref"], corrected)
            check = isolated_replay(
                correction["operation"],
                corrected,
                {**binding, "data_ref": correction["data_ref"]},
            )
            body["correction"] = {**correction, "replay": check}
        # Retry identity excludes process ids/time. Same task+data cannot silently change.
        identity = digest(
            {
                "task_id": task_id,
                "data_ref": data_ref,
                "operation": operation,
                "context": context,
                "correction": correction,
                "author": author,
                "failure_kind": failure_kind,
            }
        )
        old = self.db.execute(
            "SELECT body FROM skill_traces WHERE id=?", (identity,)
        ).fetchone()
        if old:
            return json.loads(old[0])
        deps = [data_ref] + ([correction["data_ref"]] if correction else [])
        body["source_claim_ref"] = None
        publication = replay["result"].get("publication")
        if publication:
            statistic = self.registry.record_result(
                {"contracts": publication["contracts"]},
                dependencies=[data_ref],
                operation="effect",
            )
            body["source_claim_ref"] = self.registry.add_asset(
                "claim", publication, dependencies=[statistic]
            )
        body["trace_id"] = identity
        body["evidence_ref"] = self.registry.add_asset(
            "manifest", body, dependencies=deps
        )
        with self.registry.transaction():
            self.db.execute(
                "INSERT INTO skill_traces VALUES (?,?,?,?)",
                (identity, task_id, data_ref, json.dumps(body)),
            )
            self.registry._audit(
                "G0_CAPTURED",
                {
                    "trace_id": identity,
                    "outcome": body["outcome"],
                    "task_id": task_id,
                    "data_ref": data_ref,
                },
            )
        return body

    def trace(self, trace_id):
        row = self.db.execute(
            "SELECT body FROM skill_traces WHERE id=?", (trace_id,)
        ).fetchone()
        if not row:
            raise KeyError(trace_id)
        result = json.loads(row[0])
        if self.registry.asset(result["evidence_ref"])["status"] != "VALID":
            raise ValueError("source trace evidence invalidated")
        return result

    def propose(
        self,
        *,
        name,
        trace_ids,
        applicability,
        claim_ceiling="DESCRIPTIVE_FACT",
        base_version=None,
        replacements=None,
    ):
        assert_evolvable(name)
        if claim_ceiling not in CEILINGS or not trace_ids or not applicability:
            raise ValueError("sources, applicability and known claim ceiling required")
        base = self.get(name, base_version) if base_version else None
        trace_ids = sorted(
            set(trace_ids) | set(base["spec"]["source_trace_ids"] if base else [])
        )
        traces = [self.trace(t) for t in trace_ids]
        replacements = replacements or {}
        if any(
            not matches(applicability, t["context"])
            or set(t["context"]) - set(applicability)
            for t in traces
        ):
            raise ValueError("candidate cannot generalize beyond recorded source scope")
        from .skill_analyst import analyze_parallel

        pending = [
            t
            for t in traces
            if not (
                base
                and t["trace_id"] in base["spec"]["source_trace_ids"]
                and t["trace_id"] not in replacements
            )
        ]
        analyses = analyze_parallel(pending, replacements) if pending else []
        self._log("PARALLEL_SKILL_ANALYSIS", {"name": name, "analyses": analyses})
        if any(a["issue"] for a in analyses):
            return {"decision": "ISSUE", "trace_ids": trace_ids}
        patches = [a["patch"] for a in analyses if a["patch"]]
        failures = [a["trace_id"] for a in analyses if a["negative_example"]]
        if not patches and base:
            return {"decision": "NOOP", "name": name, "version": base_version}
        if not patches:
            self._log("G6_AUDIT_ONLY", {"trace_ids": trace_ids})
            return {
                "decision": "AUDIT_ONLY",
                "reason": "no_verified_executable_correction",
            }
        merged = consolidate(patches)
        base = self.get(name, base_version) if base_version else None
        combined = merge_with_active(
            base["spec"]["rules"] if base else [], merged["rules"]
        )
        conflicts = merged["conflicts"] + combined["conflicts"]
        if conflicts:
            self._log("G1_CONFLICT", {"name": name, "conflicts": conflicts})
            return {"decision": "AUDIT_ONLY", "conflicts": conflicts}
        supported = min(
            CEILINGS.get((t["correction"] or t)["replay"]["result"]["claim_type"], 0)
            for t in traces
            if (t["correction"] or t)["replay"]["result"]["passed"]
        )
        if CEILINGS[claim_ceiling] > supported:
            raise ValueError("claim ceiling exceeds source evidence")
        rules = combined["rules"]
        if (
            base
            and rules == base["spec"]["rules"]
            and applicability == base["spec"]["applicability"]
        ):
            return {"decision": "NOOP", "name": name, "version": base_version}
        version = self.db.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM governed_skills WHERE name=?",
            (name,),
        ).fetchone()[0]
        spec = {
            "schema_version": "skill/2",
            "name": name,
            "version": version,
            "rules": rules,
            "applicability": applicability,
            "claim_ceiling": claim_ceiling,
            "preconditions": ["valid_current_data", "scope_matches"],
            "postconditions": [
                "no_causal_without_identification",
                "no_traffic_mutation",
            ],
            "source_trace_ids": [t["trace_id"] for t in traces],
            "source_claim_refs": [
                t["source_claim_ref"] for t in traces if t.get("source_claim_ref")
            ],
            "source_evidence_refs": [t["evidence_ref"] for t in traces],
            "negative_examples": sorted(
                set(failures) | set(base["spec"]["negative_examples"] if base else [])
            ),
            "validation_task_refs": [],
            "compatibility_check_refs": [],
            "delta": {
                "base_version": base_version,
                "previous_digest": base["spec"]["digest"] if base else None,
                "added_rules": [
                    r for r in rules if not base or r not in base["spec"]["rules"]
                ],
            },
        }
        spec["digest"] = digest(spec)
        lifecycle = {
            "trust_state": "provisional",
            "review": None,
            "validation": None,
            "release": None,
            "suspended_scopes": [],
            "execution_eligible": False,
        }
        with self.registry.transaction():
            self.db.execute(
                "INSERT INTO governed_skills VALUES (?,?,?,?)",
                (name, version, json.dumps(spec), json.dumps(lifecycle)),
            )
            self.registry._audit(
                "G1_DELTA_CREATED",
                {
                    "name": name,
                    "version": version,
                    "spec_digest": spec["digest"],
                    "source_task_data": [[t["task_id"], t["data_ref"]] for t in traces],
                },
            )
        return {
            "decision": "AUDIT_ONLY",
            "name": name,
            "version": version,
            "spec": spec,
        }

    def export_markdown(self, *, name, version=None):
        skill = self.get(name, version)
        spec = skill["spec"]
        body = (
            "# "
            + name
            + "\n\n"
            + (
                "Governed method memory; this document does not authorize execution. "
                "Current evidence, independent validation and human release approval remain required.\n\n"
            )
        )
        body += "```json\n" + json.dumps(spec, ensure_ascii=False, indent=2) + "\n```\n"
        return {
            "name": name,
            "version": spec["version"],
            "filename": "SKILL.md",
            "markdown": body,
            "spec_digest": spec["digest"],
            "execution_eligible": skill["lifecycle"]["execution_eligible"],
        }

    def get(self, name, version=None):
        row = self.db.execute(
            "SELECT * FROM governed_skills WHERE name=? "
            + (
                "AND version=?"
                if version is not None
                else "ORDER BY version DESC LIMIT 1"
            ),
            (name, version) if version is not None else (name,),
        ).fetchone()
        if not row:
            raise KeyError((name, version))
        spec, lifecycle = json.loads(row["spec"]), json.loads(row["lifecycle"])
        if spec["digest"] != digest({k: v for k, v in spec.items() if k != "digest"}):
            raise ValueError("immutable skill specification was altered")
        valid = all(
            self.registry.asset(ref)["status"] == "VALID"
            for ref in spec["source_evidence_refs"]
        )
        if lifecycle.get("validation"):
            valid = valid and all(
                self.registry.asset(ref)["status"] == "VALID"
                for ref in lifecycle["validation"]["data_refs"]
            )
        if not valid:
            lifecycle.update(trust_state="suspended", execution_eligible=False)
        return {
            "spec": spec,
            "lifecycle": lifecycle,
            "evidence_links": {
                "source_claim_refs": spec["source_claim_refs"],
                "source_task_refs": spec["source_evidence_refs"],
                "validation_task_refs": (lifecycle.get("validation") or {}).get(
                    "independent_task_refs", []
                ),
                "compatibility_check_refs": lifecycle.get(
                    "compatibility_check_refs", []
                ),
            },
        }

    def _update(self, name, version, lifecycle, event):
        with self.registry.transaction():
            self.db.execute(
                "UPDATE governed_skills SET lifecycle=? WHERE name=? AND version=?",
                (json.dumps(lifecycle), name, version),
            )
            self.registry._audit(event, {"name": name, "version": version, **lifecycle})

    def review(self, *, name, version, reviewer):
        item = self.get(name, version)
        spec = item["spec"]
        traces = [self.trace(t) for t in spec["source_trace_ids"]]
        if not reviewer or reviewer in {t["author"] for t in traces}:
            raise ValueError("reviewer must be distinct from capture authors")
        checks = []
        for trace in traces:
            chosen = trace["correction"] or trace
            request = self.registry.asset(chosen["data_ref"])["body"]
            checks.append(
                isolated_replay(
                    chosen["operation"],
                    request,
                    {
                        "task_id": trace["task_id"],
                        "data_ref": chosen["data_ref"],
                        "skill_ref": spec["digest"],
                    },
                )
            )
        review = {
            "reviewer": reviewer,
            "spec_digest": spec["digest"],
            "passed": bool(checks)
            and all(
                c["result"]["passed"] and all(c["guardrails"].values()) for c in checks
            ),
            "checks": checks,
        }
        item["lifecycle"]["review"] = review
        self._update(name, version, item["lifecycle"], "G2_REVIEWED")
        return review

    def freeze_suite(
        self, *, cases, tolerance=0, min_gain=None, min_independent_tasks=2
    ):
        if (
            not cases
            or not 0 <= finite(tolerance, "tolerance") <= 1
            or (min_gain is not None and not 0 <= finite(min_gain, "min_gain") <= 1)
            or type(min_independent_tasks) is not int
            or min_independent_tasks < 2
        ):
            raise ValueError(
                "frozen cases, bounded tolerances and >=2 independent tasks required"
            )
        if len({c["task_id"] for c in cases}) != len(cases):
            raise ValueError("suite task ids must be unique")
        for case in cases:
            if (
                case["expected_operation"] not in OPS
                or type(case.get("critical", False)) is not bool
            ):
                raise ValueError("invalid frozen case oracle")
            self._data(case["data_ref"], case["request"])
        body = {
            "cases": cases,
            "tolerance": tolerance,
            "min_gain": min_gain,
            "min_independent_tasks": min_independent_tasks,
        }
        ref = digest(body)
        with self.registry.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO skill_suites VALUES (?,?)",
                (ref, json.dumps(body)),
            )
            self.registry._audit("G5_SUITE_FROZEN", {"suite_ref": ref})
        return {"suite_ref": ref}

    @staticmethod
    def _operation(spec, context):
        if not matches(spec["applicability"], context):
            return None
        matching = [r["action"] for r in spec["rules"] if matches(r["when"], context)]
        return matching[0] if matching and len(set(matching)) == 1 else None

    def validate(self, *, name, version, suite_ref):
        item = self.get(name, version)
        spec = item["spec"]
        lifecycle = item["lifecycle"]
        if not lifecycle.get("review", {}) or not lifecycle["review"]["passed"]:
            raise ValueError("independent executable review must pass first")
        existing = lifecycle.get("validation")
        if existing and existing["suite_ref"] == suite_ref:
            return {"decision": "NOOP", **existing}
        row = self.db.execute(
            "SELECT body FROM skill_suites WHERE id=?", (suite_ref,)
        ).fetchone()
        if not row:
            raise KeyError(suite_ref)
        suite = json.loads(row[0])
        requested_tasks = {case["task_id"] for case in suite["cases"]}
        requested_data = {case["data_ref"] for case in suite["cases"]}
        for prior_row in self.db.execute("SELECT lifecycle FROM governed_skills"):
            prior_lifecycle = json.loads(prior_row["lifecycle"])
            history = prior_lifecycle.get("validation_history", [])
            if prior_lifecycle.get("validation"):
                history = [*history, prior_lifecycle["validation"]]
            for prior in history:
                if requested_tasks.intersection(
                    prior["independent_task_refs"]
                ) or requested_data.intersection(prior["data_refs"]):
                    raise ValueError(
                        "frozen validation task or data already consumed; independent holdout required"
                    )
        traces = [self.trace(t) for t in spec["source_trace_ids"]]
        source_tasks = {t["task_id"] for t in traces}
        source_data = {t["data_ref"] for t in traces} | {
            t["correction"]["data_ref"] for t in traces if t["correction"]
        }
        base = (
            self.get(name, spec["delta"]["base_version"])
            if spec["delta"]["base_version"]
            else None
        )
        # Reserve independent observations before execution; failed workers cannot
        # make an already inspected holdout available to another candidate.
        for case in suite["cases"]:
            if case["task_id"] in source_tasks or case["data_ref"] in source_data:
                raise ValueError(
                    "holdout task and data must be independent of extraction"
                )
            self._data(case["data_ref"], case["request"])
        lifecycle.setdefault("validation_history", []).append(
            {
                "suite_ref": suite_ref,
                "data_refs": sorted(requested_data),
                "independent_task_refs": sorted(requested_tasks),
            }
        )
        self._update(name, version, lifecycle, "G5_HOLDOUT_CONSUMED")
        pairs = []
        for case in suite["cases"]:
            if case["task_id"] in source_tasks or case["data_ref"] in source_data:
                raise ValueError(
                    "holdout task and data must be independent of extraction"
                )
            self._data(case["data_ref"], case["request"])
            actions = [
                self._operation(base["spec"], case["context"]) if base else None,
                self._operation(spec, case["context"]),
            ]
            outcomes = []
            for action in actions:
                report = (
                    isolated_replay(
                        action,
                        case["request"],
                        {
                            "task_id": case["task_id"],
                            "data_ref": case["data_ref"],
                            "skill_ref": spec["digest"],
                        },
                    )
                    if action
                    else None
                )
                score = int(
                    bool(
                        report
                        and action == case["expected_operation"]
                        and report["execution_status"] == "COMPLETED"
                        and report["result"]["passed"]
                        == case.get("expected_passed", True)
                    )
                )
                outcomes.append({"operation": action, "score": score, "replay": report})
            pairs.append(
                {
                    "task_id": case["task_id"],
                    "data_ref": case["data_ref"],
                    "critical": case.get("critical", False),
                    "base": outcomes[0],
                    "candidate": outcomes[1],
                }
            )
        gain = sum(p["candidate"]["score"] - p["base"]["score"] for p in pairs) / len(
            pairs
        )
        guard_failures = [
            p["task_id"]
            for p in pairs
            if (p["critical"] and not p["candidate"]["score"])
            or (
                p["candidate"]["replay"]
                and not all(p["candidate"]["replay"]["guardrails"].values())
            )
        ]
        passed = (
            len({p["data_ref"] for p in pairs}) >= suite["min_independent_tasks"]
            and gain >= -suite["tolerance"]
            and (suite["min_gain"] is None or gain >= suite["min_gain"])
            and not guard_failures
            and any(p["candidate"]["score"] for p in pairs)
        )
        validation = {
            "suite_ref": suite_ref,
            "spec_digest": spec["digest"],
            "passed": passed,
            "paired_gain": gain,
            "critical_failures": guard_failures,
            "pairs": pairs,
            "data_refs": [p["data_ref"] for p in pairs],
            "independent_task_refs": [p["task_id"] for p in pairs],
        }
        lifecycle.update(
            validation=validation,
            trust_state="trusted" if passed else "provisional",
            execution_eligible=False,
        )
        self._update(name, version, lifecycle, "G5_VALIDATED")
        return {
            "decision": "CRYSTALLIZE"
            if passed and gain > 0
            else "NOOP"
            if passed
            else "AUDIT_ONLY",
            **validation,
        }

    def approve(self, *, name, version, approver, credential_ref, suite_ref):
        item = self.get(name, version)
        lifecycle = item["lifecycle"]
        validation = lifecycle.get("validation")
        if (
            not approver
            or not credential_ref
            or not validation
            or not validation["passed"]
            or validation["suite_ref"] != suite_ref
            or lifecycle["trust_state"] != "trusted"
        ):
            raise ValueError(
                "approval requires valid frozen validation and explicit human credential"
            )
        if approver in {
            self.trace(t)["author"] for t in item["spec"]["source_trace_ids"]
        }:
            raise ValueError("capture author cannot approve own skill release")
        receipt = {
            "name": name,
            "version": version,
            "spec_digest": item["spec"]["digest"],
            "suite_ref": suite_ref,
            "approver": approver,
            "credential_ref": credential_ref,
        }
        ref = digest(receipt)
        with self.registry.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO skill_receipts VALUES (?,?)",
                (ref, json.dumps(receipt)),
            )
            self.registry._audit("HUMAN_RELEASE_APPROVED", {"receipt": ref, **receipt})
        return {"approval_ref": ref}

    def publish(self, *, name, version, approval_ref, fraction=0.1, effective_window=0):
        item = self.get(name, version)
        spec = item["spec"]
        lifecycle = item["lifecycle"]
        row = self.db.execute(
            "SELECT body FROM skill_receipts WHERE id=?", (approval_ref,)
        ).fetchone()
        receipt = json.loads(row[0]) if row else {}
        if (
            receipt.get("spec_digest") != spec["digest"]
            or lifecycle["trust_state"] != "trusted"
            or not lifecycle.get("validation", {}).get("passed")
            or receipt.get("suite_ref") != lifecycle["validation"]["suite_ref"]
        ):
            raise ValueError("valid bound human receipt required")
        if (
            not 0 < finite(fraction, "fraction") <= 1
            or type(effective_window) is not int
            or effective_window < 0
        ):
            raise ValueError("bounded staged fraction and window required")
        prior = lifecycle.get("release")
        if fraction > 0.1 and (not prior or not prior.get("canary_passed")):
            raise ValueError("expand only after independent canary monitoring passes")
        release = {
            "approval_ref": approval_ref,
            "fraction": fraction,
            "effective_window": effective_window,
            "canary_passed": bool(prior and prior.get("canary_passed")),
        }
        lifecycle.update(release=release, execution_eligible=True)
        self._update(name, version, lifecycle, "SKILL_RELEASED")
        with self.registry.transaction():
            self.db.execute(
                "INSERT INTO skill_releases(name,version,body) VALUES (?,?,?)",
                (name, version, json.dumps(release)),
            )
        store = SkillStore(self.skill_store_path)
        entry = store.register(name, spec["rules"], "G0–G6 governed release")
        store._record(name)["governed"] = True
        entry_actual = store._record(name)["versions"][-1]
        entry_actual["governance_binding"] = {
            "registry_path": str(Path(self.registry.path).resolve()),
            "name": name,
            "version": version,
            "spec_digest": spec["digest"],
        }
        store.bind_evidence(
            name,
            entry["version"],
            self.registry,
            [*spec["source_evidence_refs"], *lifecycle["validation"]["data_refs"]],
        )
        store._activate(
            store._record(name), entry["version"], "bound human release " + approval_ref
        )
        store.save()
        return {"status": "RELEASED", "name": name, "version": version, **release}

    def retrieve(self, *, name, context, task_id, data_ref, window=0):
        rows = self.db.execute(
            "SELECT version FROM governed_skills WHERE name=? ORDER BY version DESC",
            (name,),
        ).fetchall()
        hits = []
        for row in rows:
            item = self.get(name, row[0])
            spec, life = item["spec"], item["lifecycle"]
            release = life.get("release") or {}
            in_scope = matches(spec["applicability"], context) and not any(
                matches(scope, context) for scope in life["suspended_scopes"]
            )
            cohort = (
                int(digest({"task": task_id, "skill": name}).split(":")[-1][:8], 16)
                / 2**32
            )
            valid_data = self.registry.asset(data_ref)["status"] == "VALID"
            eligible = bool(
                valid_data
                and life["execution_eligible"]
                and life["trust_state"] == "trusted"
                and in_scope
                and window >= release.get("effective_window", 0)
                and cohort < release.get("fraction", 0)
            )
            hit = {
                "name": name,
                "version": spec["version"],
                "spec_digest": spec["digest"],
                "mode": "EXECUTE" if eligible else "AUDIT_ONLY",
                "scope_matches": in_scope,
                "claim_ceiling": spec["claim_ceiling"],
                "task_id": task_id,
                "data_ref": data_ref,
            }
            hits.append(hit)
            self._log("G4_RETRIEVED", hit)
            if eligible:
                break
        return hits

    def replay(self, *, name, context, task_id, data_ref, window=0):
        hits = self.retrieve(
            name=name,
            context=context,
            task_id=task_id,
            data_ref=data_ref,
            window=window,
        )
        hit = next((h for h in hits if h["mode"] == "EXECUTE"), None)
        if not hit:
            return {"decision": "AUDIT_ONLY", "hits": hits}
        item = self.get(name, hit["version"])
        action = self._operation(item["spec"], context)
        if not action:
            return {"decision": "AUDIT_ONLY", "reason": "no_unambiguous_method"}
        request = self.registry.asset(data_ref)["body"]
        self._data(data_ref, request)
        report = isolated_replay(
            action,
            request,
            {"task_id": task_id, "data_ref": data_ref, "skill_ref": hit["spec_digest"]},
        )
        result = report["result"]
        level = CEILINGS.get(result.get("claim_type"), 0)
        if level > CEILINGS[item["spec"]["claim_ceiling"]]:
            # Current effect still has its own identification gate; method cannot raise its ceiling.
            report["result"] = {
                "passed": result["passed"],
                "claim_type": item["spec"]["claim_ceiling"],
                "reason": "fresh_analysis_exceeds_skill_ceiling; use main publication pipeline",
                "effect_estimate": None,
            }
        report["digest"] = digest({k: v for k, v in report.items() if k != "digest"})
        compatibility_ref = self.registry.add_asset(
            "manifest",
            report,
            dependencies=[data_ref, *item["spec"]["source_evidence_refs"]],
        )
        item["lifecycle"].setdefault("compatibility_check_refs", []).append(
            compatibility_ref
        )
        self._update(
            name, hit["version"], item["lifecycle"], "CURRENT_COMPATIBILITY_CHECKED"
        )
        self._log(
            "SKILL_REPLAYED",
            {
                "name": name,
                "version": hit["version"],
                "task_id": task_id,
                "data_ref": data_ref,
                "report": report,
            },
        )
        return {
            "decision": "NOOP",
            "attribution": "existing_skill_replay_not_new_discovery",
            "report": report,
        }

    def monitor(self, *, name, version, suite_ref):
        item = self.get(name, version)
        if not item["lifecycle"].get("release"):
            raise ValueError("canary release required")
        if suite_ref == item["lifecycle"]["validation"]["suite_ref"]:
            raise ValueError("canary monitoring requires another frozen task suite")
        validation = self.validate(name=name, version=version, suite_ref=suite_ref)
        item = self.get(name, version)
        item["lifecycle"]["release"]["canary_passed"] = validation["passed"]
        item["lifecycle"]["execution_eligible"] = validation["passed"]
        if not validation["passed"]:
            item["lifecycle"]["trust_state"] = "suspended"
        self._update(name, version, item["lifecycle"], "CANARY_MONITORED")
        return validation

    def suspend_scope(self, *, name, version, context, task_id, data_ref):
        item = self.get(name, version)
        action = self._operation(item["spec"], context)
        if not action:
            raise ValueError("failure must be attributable to applicable skill")
        request = self.registry.asset(data_ref)["body"]
        self._data(data_ref, request)
        report = isolated_replay(
            action,
            request,
            {
                "task_id": task_id,
                "data_ref": data_ref,
                "skill_ref": item["spec"]["digest"],
            },
        )
        if report["result"]["passed"]:
            raise ValueError("successful replay cannot support failure downgrade")
        item["lifecycle"]["suspended_scopes"].append(context)
        self._update(name, version, item["lifecycle"], "G3_SCOPE_DOWNGRADED")
        return {"decision": "AUDIT_ONLY", "scope": context, "evidence": report}

    def learn_from_feedback(self, *, event_id, name, context):
        from .feedback_service import FeedbackService

        feedback = FeedbackService(self.registry.path)
        try:
            event = feedback.read(event_id)
        finally:
            feedback.close()
        latest = self.db.execute(
            "SELECT id FROM feedback_events WHERE kind=? AND logical_key=? ORDER BY revision DESC LIMIT 1",
            (event["kind"], event["payload"].get("alert_id", "")),
        ).fetchone()
        if not latest or latest[0] != event_id:
            raise ValueError("superseded feedback cannot train a skill")
        if event["kind"] != "alert_feedback":
            raise ValueError("learning trigger must reference an alert feedback event")
        row = self.db.execute(
            "SELECT body FROM scan_alerts WHERE id=?", (event["payload"]["alert_id"],)
        ).fetchone()
        if not row:
            raise ValueError("feedback must reference a real scan alert")
        alert = json.loads(row[0])
        evidence = self.registry.asset(alert["evidence_ref"])
        if evidence["status"] != "VALID":
            raise ValueError("alert source invalidated")
        if event["payload"]["label"] == "false_positive":
            self._log(
                "G6_AUDIT_ONLY",
                {
                    "feedback_ref": event_id,
                    "negative_example": alert,
                    "reason": "human false-positive label requires independently validated method correction",
                },
            )
            return {
                "decision": "AUDIT_ONLY",
                "feedback_ref": event_id,
                "negative_example_retained": True,
            }
        for audit in reversed(self.registry.audit()):
            if audit["event"] == "FEEDBACK_TO_SKILL_CANDIDATE":
                previous = audit["body"]
                if previous.get("feedback_ref") == event_id:
                    proposal = previous["proposal"]
                    if (
                        proposal.get("name") != name
                        or previous.get("context") != context
                    ):
                        raise ValueError("feedback learning scope/name already bound")
                    return {**proposal, "feedback_ref": event_id}
        data_ref = evidence["dependencies"][0]
        trace = self.capture(
            task_id="feedback:" + event_id,
            data_ref=data_ref,
            context=context,
            operation="scan_window",
            author=event["payload"]["operator"],
        )
        proposal = self.propose(
            name=name,
            trace_ids=[trace["trace_id"]],
            applicability=context,
            claim_ceiling="WATCHLIST",
        )
        self._log(
            "FEEDBACK_TO_SKILL_CANDIDATE",
            {"feedback_ref": event_id, "proposal": proposal, "context": context},
        )
        return {**proposal, "feedback_ref": event_id}

    def rollback(self, *, name, target_version, approval_ref, effective_window):
        latest = self.get(name)
        target = self.get(name, target_version)
        if (
            target_version >= latest["spec"]["version"]
            or target["lifecycle"]["trust_state"] != "trusted"
        ):
            raise ValueError("rollback requires an older still-valid trusted version")
        row = self.db.execute(
            "SELECT body FROM skill_receipts WHERE id=?", (approval_ref,)
        ).fetchone()
        receipt = json.loads(row[0]) if row else {}
        if (
            receipt.get("spec_digest") != target["spec"]["digest"]
            or receipt.get("suite_ref")
            != target["lifecycle"]["validation"]["suite_ref"]
            or type(effective_window) is not int
            or effective_window < 0
        ):
            raise ValueError(
                "rollback receipt must match the still-valid target before changing activation"
            )
        latest["lifecycle"].update(execution_eligible=False, trust_state="suspended")
        self._update(
            name, latest["spec"]["version"], latest["lifecycle"], "ROLLED_BACK"
        )
        return self.publish(
            name=name,
            version=target_version,
            approval_ref=approval_ref,
            fraction=0.1,
            effective_window=effective_window,
        )
