"""Transactional evidence versions, dependency invalidation and hypothesis states.

Only deterministic evidence evaluation can advance a hypothesis. Content hashes
bind inputs and versions; they do not authenticate business-source assertions.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .contracts import digest, finite, validate_bundle, validate_contract


class HypothesisRegistry:
    def __init__(self, path=":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS dependencies (
              child TEXT NOT NULL REFERENCES assets(id), parent TEXT NOT NULL REFERENCES assets(id), PRIMARY KEY(child,parent));
            CREATE TABLE IF NOT EXISTS resources (name TEXT PRIMARY KEY, current_id TEXT NOT NULL REFERENCES assets(id), version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS hypotheses (
              id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL, gate INTEGER NOT NULL,
              gate_passed INTEGER NOT NULL, version INTEGER NOT NULL, evidence_id TEXT REFERENCES assets(id));
            CREATE TABLE IF NOT EXISTS hypothesis_parents (child TEXT REFERENCES hypotheses(id), parent TEXT REFERENCES hypotheses(id), PRIMARY KEY(child,parent));
            CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loops (id TEXT PRIMARY KEY, version INTEGER NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS holdouts (data_ref TEXT NOT NULL, window_key TEXT NOT NULL,
              owner TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(data_ref, window_key));
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _audit(self, event, body):
        self.db.execute(
            "INSERT INTO audit(event,body) VALUES (?,?)",
            (event, json.dumps(body, ensure_ascii=False, allow_nan=False)),
        )

    def _asset(self, kind, body, dependencies):
        if kind == "claim":
            from .publication import verify_publication

            verify_publication(body)
        deps = sorted(set(dependencies))
        for ref in deps:
            row = self.db.execute(
                "SELECT status FROM assets WHERE id=?", (ref,)
            ).fetchone()
            if row is None or row[0] != "VALID":
                raise ValueError("missing or invalid dependency: " + ref)
        if kind == "claim":
            matches = [self.asset(d) for d in deps]
            if not any(
                a["kind"] == "statistic"
                and a["body"].get("result", {}).get("contracts") == body["contracts"]
                for a in matches
            ):
                raise ValueError(
                    "claim requires matching versioned statistical evidence"
                )
        ref = digest({"kind": kind, "body": body, "dependencies": deps})
        old = self.db.execute("SELECT status FROM assets WHERE id=?", (ref,)).fetchone()
        if old is not None and old[0] != "VALID":
            raise ValueError(
                "invalidated evidence cannot be resurrected by reusing its digest"
            )
        self.db.execute(
            "INSERT OR IGNORE INTO assets VALUES (?,?,?,?)",
            (ref, kind, json.dumps(body, ensure_ascii=False, allow_nan=False), "VALID"),
        )
        self.db.executemany(
            "INSERT OR IGNORE INTO dependencies VALUES (?,?)",
            [(ref, parent) for parent in deps],
        )
        return ref

    def add_asset(self, kind, body, *, dependencies=()):
        if kind not in {"data", "statistic", "claim", "skill", "snapshot", "manifest"}:
            raise ValueError("unsupported evidence kind")
        with self.transaction():
            ref = self._asset(kind, body, dependencies)
            self._audit("ASSET_RECORDED", {"ref": ref, "kind": kind})
        return ref

    def _invalidate(self, ref, reason):
        if not self.db.execute("SELECT 1 FROM assets WHERE id=?", (ref,)).fetchone():
            raise KeyError(ref)
        rows = self.db.execute(
            """WITH RECURSIVE affected(id) AS (
            SELECT ? UNION SELECT d.child FROM dependencies d JOIN affected a ON d.parent=a.id
        ) SELECT assets.id,assets.kind FROM assets JOIN affected USING(id)""",
            (ref,),
        ).fetchall()
        affected = []
        for row in rows:
            status = (
                "REVOKED"
                if row["kind"] == "claim"
                else "SUSPENDED"
                if row["kind"] == "skill"
                else "INVALID"
            )
            self.db.execute(
                "UPDATE assets SET status=? WHERE id=?", (status, row["id"])
            )
            self.db.execute(
                "UPDATE hypotheses SET state='dormant',gate=0,gate_passed=0,version=version+1 WHERE evidence_id=?",
                (row["id"],),
            )
            affected.append({"ref": row["id"], "kind": row["kind"], "status": status})
        self.db.execute("""WITH RECURSIVE stale(id) AS (
            SELECT id FROM hypotheses WHERE evidence_id IN (SELECT id FROM assets WHERE status!='VALID')
            UNION SELECT hp.child FROM hypothesis_parents hp JOIN stale ON hp.parent=stale.id)
            UPDATE hypotheses SET state='dormant',gate=0,gate_passed=0,version=version+1 WHERE id IN (SELECT id FROM stale)""")
        self._audit(
            "EVIDENCE_INVALIDATED",
            {
                "source": ref,
                "reason": reason,
                "affected": affected,
                "alert": "dependent claims revoked; skills suspended",
            },
        )
        return affected

    def invalidate(self, ref, *, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalidation reason required")
        with self.transaction():
            return self._invalidate(ref, reason)

    def revise_resource(self, name, body, *, kind="data", dependencies=()):
        if not name or kind not in {"data", "snapshot"}:
            raise ValueError("named data or snapshot resource required")
        with self.transaction():
            ref = self._asset(kind, body, dependencies)
            old = self.db.execute(
                "SELECT current_id,version FROM resources WHERE name=?", (name,)
            ).fetchone()
            if old and old["current_id"] == ref:
                return {"ref": ref, "version": old["version"], "invalidated": []}
            affected = (
                self._invalidate(old["current_id"], "resource revised: " + name)
                if old
                else []
            )
            if self.asset(ref)["status"] != "VALID":
                raise ValueError(
                    "new resource cannot depend on its invalidated predecessor"
                )
            version = old["version"] + 1 if old else 1
            self.db.execute(
                "INSERT INTO resources VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET current_id=excluded.current_id,version=excluded.version",
                (name, ref, version),
            )
            self._audit(
                "RESOURCE_REVISED", {"name": name, "ref": ref, "version": version}
            )
            return {"ref": ref, "version": version, "invalidated": affected}

    def asset(self, ref, *, audit=False):
        row = self.db.execute("SELECT * FROM assets WHERE id=?", (ref,)).fetchone()
        if row is None:
            raise KeyError(ref)
        value = dict(row)
        value["body"] = json.loads(value["body"])
        if value["status"] != "VALID" and not audit:
            value["body"] = {
                "execution_status": "COMPLETED",
                "reason_codes": ["DATA_INVALID"],
                "effect_estimate": None,
                "next_action": "recompute_from_revised_data",
            }
        value["dependencies"] = [
            r[0]
            for r in self.db.execute(
                "SELECT parent FROM dependencies WHERE child=? ORDER BY parent", (ref,)
            )
        ]
        return value

    def register(self, spec, *, parents=()):
        if (
            not isinstance(spec, dict)
            or not isinstance(spec.get("factor_id"), str)
            or not spec["factor_id"].strip()
        ):
            raise ValueError("hypothesis needs factor_id")
        if set(spec) - {
            "factor_id",
            "scope",
            "metric",
            "direction",
            "threshold",
            "window",
            "variant",
            "claim_ceiling",
        }:
            raise ValueError("hypothesis schema rejects model-controlled state fields")
        if spec.get("direction", "nonzero") not in {
            "positive",
            "negative",
            "nonzero",
            "equivalent",
        }:
            raise ValueError("invalid hypothesis direction")
        if finite(spec.get("threshold", 0), "threshold") < 0:
            raise ValueError("nonnegative hypothesis threshold required")
        ref = digest({"spec": spec, "parents": sorted(parents)})
        with self.transaction():
            for parent in parents:
                row = self.db.execute(
                    "SELECT state,gate_passed FROM hypotheses WHERE id=?", (parent,)
                ).fetchone()
                if not row or row["state"] != "supported" or not row["gate_passed"]:
                    raise ValueError(
                        "refine/merge requires every parent to pass its current gate"
                    )
            self.db.execute(
                "INSERT OR IGNORE INTO hypotheses VALUES (?,?, 'open',0,0,1,NULL)",
                (ref, json.dumps(spec, ensure_ascii=False)),
            )
            self.db.executemany(
                "INSERT OR IGNORE INTO hypothesis_parents VALUES (?,?)",
                [(ref, p) for p in parents],
            )
            self._audit("HYPOTHESIS_REGISTERED", {"id": ref, "parents": list(parents)})
        return ref

    def record_result(self, result, *, dependencies, operation):
        if not dependencies:
            raise ValueError("statistical results require versioned input dependencies")
        if operation == "effect":
            validate_bundle(result["contracts"])
        elif operation in {"discovery", "confirmation"}:
            if not isinstance(result.get("candidates"), list):
                raise ValueError("association result candidates required")
            if (
                operation == "confirmation"
                and result.get("test_family_contract") is not None
            ):
                validate_contract("TestFamilyContract", result["test_family_contract"])
        else:
            raise ValueError("only deterministic estimator results are accepted")
        return self.add_asset(
            "statistic",
            {"operation": operation, "result": result},
            dependencies=dependencies,
        )

    def apply_evidence(self, hypothesis_id, evidence_ref):
        from .publication import publish_conclusion

        with self.transaction():
            row = self.db.execute(
                "SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)
            ).fetchone()
            if not row:
                raise KeyError(hypothesis_id)
            if row["state"] != "open":
                raise ValueError(
                    "terminal hypotheses require a new evidence/versioned hypothesis"
                )
            evidence = self.asset(evidence_ref)
            if evidence["kind"] != "statistic" or evidence["status"] != "VALID":
                raise ValueError("valid statistical evidence required")
            for parent in self.db.execute(
                "SELECT parent FROM hypothesis_parents WHERE child=?", (hypothesis_id,)
            ):
                p = self.hypothesis(parent[0])
                if (
                    p["state"] != "supported"
                    or not p["gate_passed"]
                    or p["evidence_id"] not in evidence["dependencies"]
                ):
                    raise ValueError(
                        "refined evidence must depend on each valid parent evidence version"
                    )
            spec = json.loads(row["spec"])
            operation, result = (
                evidence["body"]["operation"],
                evidence["body"]["result"],
            )
            state, gate, passed = "open", row["gate"], False
            if operation == "effect":
                conclusion = publish_conclusion(
                    result["contracts"], practical_threshold=spec.get("threshold", 0)
                )
                effect = result["contracts"]["EffectEstimate"]
                interval = effect["interval"]
                if (
                    spec.get("metric")
                    and spec["metric"] != result["contracts"]["MetricContract"]["name"]
                ):
                    raise ValueError("hypothesis metric does not match effect evidence")
                if (
                    spec["factor_id"]
                    != result["contracts"]["IdentificationReport"]["treatment"]
                ):
                    raise ValueError(
                        "effect treatment must match the registered hypothesis"
                    )
                if (
                    conclusion["interpretation"]
                    in {"UNTRUSTWORTHY", "NEEDS_INDEPENDENT_CONFIRMATION"}
                    or interval is None
                ):
                    state = "dormant"
                else:
                    low, high = interval
                    threshold, direction = (
                        spec.get("threshold", 0),
                        spec.get("direction", "nonzero"),
                    )
                    passed = (
                        low > threshold
                        if direction == "positive"
                        else high < -threshold
                        if direction == "negative"
                        else low >= -threshold and high <= threshold
                        if direction == "equivalent"
                        else low > threshold or high < -threshold
                    )
                    contradicted = (
                        high < -threshold
                        if direction == "positive"
                        else low > threshold
                        if direction == "negative"
                        else low > threshold or high < -threshold
                        if direction == "equivalent"
                        else low >= -threshold and high <= threshold
                    )
                    state = (
                        "supported"
                        if passed
                        else "refuted"
                        if contradicted
                        else "dormant"
                    )
                    gate = 3
            else:
                candidates = [
                    c
                    for c in result["candidates"]
                    if c.get("factor_id") == spec["factor_id"]
                ]
                if candidates:
                    gate = max(gate, 1)
                if operation == "confirmation":
                    passed = any(
                        c.get("holdout", {}).get("survives") is True
                        and c["holdout"].get("adjusted_pvalue", 1)
                        <= (result.get("test_family_contract") or {}).get("alpha", 0.05)
                        for c in candidates
                    )
                    state = "supported" if passed else "dormant"
                    gate = 2
            self.db.execute(
                "UPDATE hypotheses SET state=?,gate=?,gate_passed=?,version=version+1,evidence_id=? WHERE id=?",
                (state, gate, int(passed), evidence_ref, hypothesis_id),
            )
            self._audit(
                "EVIDENCE_MOVED_STATE",
                {
                    "id": hypothesis_id,
                    "from": row["state"],
                    "to": state,
                    "evidence": evidence_ref,
                    "gate": gate,
                },
            )
        return self.hypothesis(hypothesis_id)

    def hypothesis(self, ref):
        row = self.db.execute("SELECT * FROM hypotheses WHERE id=?", (ref,)).fetchone()
        if not row:
            raise KeyError(ref)
        value = dict(row)
        value["spec"] = json.loads(value["spec"])
        value.update(
            claim_type="CANDIDATE_ASSOCIATION",
            identification_status="NOT_IDENTIFIED",
            statistical_uncertainty=None,
        )
        if value["evidence_id"]:
            asset = self.asset(value["evidence_id"])
            body = asset["body"]
            if asset["status"] != "VALID":
                value["reason_codes"] = ["DATA_INVALID"]
            elif body.get("operation") == "effect":
                from .publication import publish_conclusion

                publication = publish_conclusion(
                    body["result"]["contracts"],
                    practical_threshold=value["spec"].get("threshold", 0),
                )
                value.update(
                    claim_type=publication["claim_type"],
                    identification_status=publication["identification"]["status"],
                    statistical_uncertainty=publication["statistical_uncertainty"],
                    reason_codes=publication["reason_codes"],
                )
            elif body.get("operation") in {"discovery", "confirmation"}:
                candidates = [
                    c
                    for c in body["result"]["candidates"]
                    if c.get("factor_id") == value["spec"]["factor_id"]
                ]
                value["statistical_uncertainty"] = [
                    {
                        "factor_id": c["factor_id"],
                        "correlation": c.get("correlation"),
                        "holdout": c.get("holdout"),
                        "causal_effect": None,
                    }
                    for c in candidates
                ]
                if value["gate_passed"] and value["gate"] == 2:
                    value["claim_type"] = "CONDITIONAL_TEMPORAL"
            elif body.get("operation") == "graph":
                value["statistical_uncertainty"] = {
                    "ci_tests_spent": body["result"].get("ci_tests_spent"),
                    "ambiguities": body["result"].get("ambiguities"),
                    "causal_effect": None,
                }
        value["test_history"] = [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT body FROM audit WHERE event IN ('EVIDENCE_MOVED_STATE','GRAPH_DIAGNOSTIC_RECORDED') AND json_extract(body,'$.id')=? ORDER BY seq",
                (ref,),
            )
        ]
        return value

    def snapshot(self):
        return {
            "schema_version": "1.0",
            "hypotheses": [
                self.hypothesis(r[0])
                for r in self.db.execute("SELECT id FROM hypotheses ORDER BY id")
            ],
            "audit_cursor": self.db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM audit"
            ).fetchone()[0],
        }

    def audit(self):
        return [
            {"seq": r["seq"], "event": r["event"], "body": json.loads(r["body"])}
            for r in self.db.execute("SELECT * FROM audit ORDER BY seq")
        ]

    def close(self):
        self.db.close()
