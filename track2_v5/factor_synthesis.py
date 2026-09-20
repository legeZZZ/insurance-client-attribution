"""Opt-in bounded expression research; freeze whole family, confirm on new data."""

from __future__ import annotations

import json

import numpy as np

from .contracts import digest, finite, integer
from .hypothesis_registry import HypothesisRegistry
from .input_validation import validate_ordered_series


def evaluate_expression(expression, data, *, max_nodes=15, max_depth=4):
    days = data["days"]
    validate_ordered_series(days, data["response"], component="synthesis")
    counter = 0
    parents = set()

    def visit(node, depth):
        nonlocal counter
        counter += 1
        if counter > max_nodes or depth > max_depth:
            raise ValueError("expression complexity budget exceeded")
        if not isinstance(node, dict):
            raise TypeError("expression must be a typed object")
        if set(node) == {"factor"}:
            key = node["factor"]
            source = data["factors"][key]
            parents.add(key)
            if source.get("kind", "continuous") != "continuous" or not source.get(
                "unit"
            ):
                raise ValueError(
                    "numeric continuous factor with declared unit required"
                )
            validate_ordered_series(
                days, source["values"], component="synthesis_parent"
            )
            return dict(zip(days, map(float, source["values"]))), source["unit"]
        if set(node) - {"op", "args", "steps", "window"} or node.get("op") not in {
            "add",
            "subtract",
            "multiply",
            "divide",
            "lag",
            "rolling_mean",
        }:
            raise ValueError("unrecognized expression operation")
        op = node["op"]
        permitted = {"op", "args"} | (
            {"steps"} if op == "lag" else {"window"} if op == "rolling_mean" else set()
        )
        if set(node) - permitted:
            raise ValueError("operator-specific parameters required")
        args = node.get("args", [])
        arity = 1 if op in {"lag", "rolling_mean"} else 2
        if len(args) != arity:
            raise ValueError("operator arity mismatch")
        children = [visit(arg, depth + 1) for arg in args]
        values, unit = children[0]
        if op == "lag":
            steps = integer(node.get("steps", 1), "lag steps")
            if not 0 <= steps <= 30:
                raise ValueError("future or excessive lag forbidden")
            return {d: values[d - steps] for d in days if d - steps in values}, unit
        if op == "rolling_mean":
            window = integer(node.get("window", 3), "rolling window")
            if not 1 <= window <= 30:
                raise ValueError("bounded trailing window required")
            return {
                d: float(np.mean([values[t] for t in range(d - window + 1, d + 1)]))
                for d in days
                if all(t in values for t in range(d - window + 1, d + 1))
            }, unit
        right, right_unit = children[1]
        common = sorted(set(values) & set(right))
        if op in {"add", "subtract"} and unit != right_unit:
            raise ValueError("addition/subtraction require identical units")
        if op == "multiply":
            unit = (
                right_unit
                if unit == "index"
                else unit
                if right_unit == "index"
                else "*".join(sorted([unit, right_unit]))
            )
        if op == "divide":
            unit = (
                "index"
                if unit == right_unit
                else unit
                if right_unit == "index"
                else unit + "/" + right_unit
            )
            if any(right[d] == 0 for d in common):
                raise ValueError("zero denominator; no epsilon or fabricated values")
        actions = {
            "add": lambda a, b: a + b,
            "subtract": lambda a, b: a - b,
            "multiply": lambda a, b: a * b,
            "divide": lambda a, b: a / b,
        }
        return {
            d: finite(actions[op](values[d], right[d]), "expression result")
            for d in common
        }, unit

    values, unit = visit(expression, 1)
    if len(values) < 10:
        raise ValueError("insufficient aligned expression observations")
    return {
        "days": sorted(values),
        "values": [values[d] for d in sorted(values)],
        "unit": unit,
        "parents": sorted(parents),
        "nodes": counter,
        "expression_digest": digest(expression),
        "omitted_days": sorted(set(days) - set(values)),
    }


class FactorSynthesis:
    def __init__(self, db_path):
        self.registry = HypothesisRegistry(db_path)
        self.db = self.registry.db
        self.db.executescript("""CREATE TABLE IF NOT EXISTS synthesis_policies(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS synthesis_families(id TEXT PRIMARY KEY,state TEXT NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS synthesis_confirmations(policy TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,task TEXT NOT NULL,PRIMARY KEY(policy,start,end));""")

    def close(self):
        self.registry.close()

    def configure(
        self,
        *,
        policy_id,
        enabled=False,
        max_candidates=8,
        max_nodes=15,
        max_depth=4,
        alpha=0.05,
    ):
        if (
            not policy_id
            or type(enabled) is not bool
            or not 1 <= integer(max_candidates, "max_candidates") <= 30
            or not 1 <= integer(max_nodes, "max_nodes") <= 30
            or not 1 <= integer(max_depth, "max_depth") <= 6
            or not 0 < finite(alpha, "alpha") < 1
        ):
            raise ValueError("bounded synthesis policy required")
        body = {
            "enabled": enabled,
            "max_candidates": max_candidates,
            "max_nodes": max_nodes,
            "max_depth": max_depth,
            "alpha": alpha,
        }
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT body FROM synthesis_policies WHERE id=?", (policy_id,)
            ).fetchone()
            if old and json.loads(old[0]) != body:
                raise ValueError(
                    "policy frozen; cannot reset existing expression/error budget"
                )
            self.db.execute(
                "INSERT OR IGNORE INTO synthesis_policies VALUES (?,?)",
                (policy_id, json.dumps(body)),
            )
        return {"policy_id": policy_id, **body}

    def set_enabled(self, *, policy_id, enabled):
        if type(enabled) is not bool:
            raise ValueError("explicit boolean switch required")
        with self.registry.transaction():
            row = self.db.execute(
                "SELECT body FROM synthesis_policies WHERE id=?", (policy_id,)
            ).fetchone()
            if not row:
                raise KeyError(policy_id)
            body = json.loads(row[0])
            body["enabled"] = enabled
            self.db.execute(
                "UPDATE synthesis_policies SET body=? WHERE id=?",
                (json.dumps(body), policy_id),
            )
            self.registry._audit(
                "SYNTHESIS_SWITCH", {"policy_id": policy_id, "enabled": enabled}
            )
        return {"policy_id": policy_id, **body}

    def _policy(self, key):
        row = self.db.execute(
            "SELECT body FROM synthesis_policies WHERE id=?", (key,)
        ).fetchone()
        if not row:
            raise ValueError("synthesis disabled without explicit policy")
        body = json.loads(row[0])
        if not body["enabled"]:
            raise ValueError("synthesis experimental switch is disabled")
        return body

    def read(self, *, task_id):
        row = self.db.execute(
            "SELECT state,body FROM synthesis_families WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            raise KeyError(task_id)
        result = {"state": row["state"], **json.loads(row["body"])}
        if (
            result["state"] == "CONFIRMED"
            and self.registry.asset(result["result_ref"])["status"] != "VALID"
        ):
            result["state"] = "WITHDRAWN"
            result["confirmation"] = {
                "results": [],
                "reason_codes": ["DATA_INVALID"],
                "causal_eligible": False,
            }
        return result

    def _data(self, ref):
        asset = self.registry.asset(ref)
        if asset["status"] != "VALID" or asset["kind"] != "data":
            raise ValueError("current valid synthesis data asset required")
        data = asset["body"]
        validate_ordered_series(
            data["days"], data["response"], component="synthesis_data"
        )
        if integer(data["available_day"], "available_day") < max(data["days"]):
            raise ValueError("availability cannot precede last observation")
        return data

    def propose(self, *, policy_id, task_id, data_ref, expression, current_window):
        policy = self._policy(policy_id)
        data = self._data(data_ref)
        current = integer(current_window, "current_window")
        if data["available_day"] > current:
            raise ValueError("data not available at proposal time")
        computed = evaluate_expression(
            expression,
            data,
            max_nodes=policy["max_nodes"],
            max_depth=policy["max_depth"],
        )
        key = "synth:" + computed["expression_digest"].split(":")[-1][:20]
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT state,body FROM synthesis_families WHERE id=?", (task_id,)
            ).fetchone()
            if old:
                body = json.loads(old["body"])
                if (
                    body["policy_id"] != policy_id
                    or body["data_ref"] != data_ref
                    or body["current_window"] != current
                ):
                    raise ValueError("task binding changed")
                if old["state"] != "PROPOSING":
                    raise ValueError(
                        "family already frozen; new expressions require a new future task"
                    )
            else:
                body = {
                    "task_id": task_id,
                    "policy_id": policy_id,
                    "data_ref": data_ref,
                    "current_window": current,
                    "candidates": [],
                }
            if any(c["factor_id"] == key for c in body["candidates"]):
                return {"decision": "NOOP", "factor_id": key}
            if len(body["candidates"]) >= policy["max_candidates"]:
                raise ValueError("candidate budget exhausted")
            spec = {
                "factor_id": key,
                "expression": expression,
                "unit": computed["unit"],
                "parents": computed["parents"],
                "parent_units": {
                    p: data["factors"][p]["unit"] for p in computed["parents"]
                },
                "source_data_ref": data_ref,
                "available_window": current + 1,
                "claim_ceiling": "FACTOR_CANDIDATE",
                "nodes": computed["nodes"],
            }
            spec["ref"] = self.registry._asset("manifest", spec, [data_ref])
            body["candidates"].append(spec)
            self.db.execute(
                "INSERT INTO synthesis_families VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (task_id, "PROPOSING", json.dumps(body)),
            )
            self.registry._audit(
                "SYNTHESIS_PROPOSED",
                {"task_id": task_id, "factor_id": key, "spec_ref": spec["ref"]},
            )
        return {"decision": "PROPOSED", "factor_id": key, "spec": spec}

    def freeze(self, *, task_id):
        with self.registry.transaction():
            body = self.read(task_id=task_id)
            if body["state"] != "PROPOSING":
                return body
            policy = self._policy(body["policy_id"])
            data = self._data(body["data_ref"])
            items = []
            if not body["candidates"]:
                raise ValueError("nonempty frozen family required")
            for spec in body["candidates"]:
                computed = evaluate_expression(
                    spec["expression"],
                    data,
                    max_nodes=policy["max_nodes"],
                    max_depth=policy["max_depth"],
                )
                by_day = dict(zip(data["days"], data["response"]))
                x = np.array(computed["values"])
                y = np.array([by_day[d] for d in computed["days"]])
                corr = (
                    float(np.corrcoef(x, y)[0, 1])
                    if np.std(x) > 0 and np.std(y) > 0
                    else 0.0
                )
                items.append(
                    {
                        "alert_id": spec["factor_id"],
                        "factor_id": spec["factor_id"],
                        "scope_id": "global",
                        "metric_id": "metric",
                        "lag": 0,
                        "correlation": corr,
                        "discovery_window": [min(data["days"]), max(data["days"])],
                    }
                )
            body.pop("state")
            body.update(
                items=items,
                family_digest=digest(body["candidates"]),
                tests_spent=len(items),
            )
            self.db.execute(
                "UPDATE synthesis_families SET state=?,body=? WHERE id=?",
                ("FROZEN", json.dumps(body), task_id),
            )
            self.registry._audit(
                "SYNTHESIS_FAMILY_FROZEN",
                {
                    "task_id": task_id,
                    "family_digest": body["family_digest"],
                    "family_size": len(items),
                },
            )
        return self.read(task_id=task_id)

    def confirm(self, *, task_id, data_ref, bootstrap_reps=199):
        from .watchlist_scan import confirm_watchlist

        with self.registry.transaction():
            body = self.read(task_id=task_id)
            policy = self._policy(body["policy_id"])
            if body["state"] == "CONFIRMED":
                if body["confirmation_data_ref"] != data_ref:
                    raise ValueError("completed confirmation cannot change data")
                return body
            if body["state"] != "FROZEN":
                raise ValueError(
                    "freeze family before confirmation; consumed failures cannot retry"
                )
            self._data(body["data_ref"])
            data = self._data(data_ref)
            start, end = min(data["days"]), max(data["days"])
            if data_ref == body["data_ref"] or start <= max(
                body["current_window"] + 1, body["items"][0]["discovery_window"][1] + 2
            ):
                raise ValueError("independent future confirmation window required")
            if digest(body["candidates"]) != body["family_digest"]:
                raise ValueError("frozen family changed")
            if self.db.execute(
                "SELECT 1 FROM synthesis_confirmations WHERE start<=? AND end>=?",
                (end, start),
            ).fetchone():
                raise ValueError(
                    "confirmation observations already consumed under this policy"
                )
            epoch = (
                self.db.execute(
                    "SELECT COUNT(*) FROM synthesis_confirmations"
                ).fetchone()[0]
                + 1
            )
            confirmation_alpha = policy["alpha"] / (epoch * (epoch + 1))
            factors = []
            for spec in body["candidates"]:
                if self.registry.asset(spec["ref"])["status"] != "VALID":
                    raise ValueError("expression source was invalidated")
                if any(
                    data["factors"][p]["unit"] != unit
                    for p, unit in spec["parent_units"].items()
                ):
                    raise ValueError("parent unit changed in new window")
                computed = evaluate_expression(
                    spec["expression"],
                    data,
                    max_nodes=policy["max_nodes"],
                    max_depth=policy["max_depth"],
                )
                factors.append(
                    {
                        "factor_id": spec["factor_id"],
                        "days": computed["days"],
                        "values": computed["values"],
                    }
                )
            self.db.execute(
                "INSERT INTO synthesis_confirmations VALUES (?,?,?,?)",
                (body["policy_id"], start, end, task_id),
            )
            body.pop("state")
            body.update(
                confirmation_data_ref=data_ref,
                tests_spent=body["tests_spent"] + len(factors),
            )
            self.db.execute(
                "UPDATE synthesis_families SET state=?,body=? WHERE id=?",
                ("CONFIRMING", json.dumps(body), task_id),
            )
        # Entire expression family is tested; low discovery scores are not excluded.
        try:
            result = confirm_watchlist(
                body["items"],
                data["days"],
                data["response"],
                factors,
                alpha=confirmation_alpha,
                bootstrap_reps=bootstrap_reps,
            )
        except (ValueError, KeyError, TypeError, RuntimeError, TimeoutError) as exc:
            body["failure"] = {
                "reason_code": "DATA_INVALID",
                "error": str(exc),
                "budget_retained": True,
            }
            with self.registry.transaction():
                self.db.execute(
                    "UPDATE synthesis_families SET state=?,body=? WHERE id=?",
                    ("FAILED", json.dumps(body), task_id),
                )
                self.registry._audit(
                    "SYNTHESIS_CONFIRMATION_FAILED",
                    {"task_id": task_id, **body["failure"]},
                )
            raise
        with self.registry.transaction():
            body["confirmation"] = result
            body["confirmation"]["error_policy"] = (
                "summable_alpha_spending_conditional_on_valid_block_null"
            )
            body["result_ref"] = self.registry._asset(
                "manifest",
                result,
                [body["data_ref"], data_ref, *[s["ref"] for s in body["candidates"]]],
            )
            self.db.execute(
                "UPDATE synthesis_families SET state=?,body=? WHERE id=?",
                ("CONFIRMED", json.dumps(body), task_id),
            )
            self.registry._audit(
                "SYNTHESIS_CONFIRMED",
                {"task_id": task_id, "result_ref": body["result_ref"]},
            )
        return self.read(task_id=task_id)


def execute_synthesis(*, db_path, action, parameters):
    service = FactorSynthesis(db_path)
    try:
        if action not in {
            "configure",
            "set_enabled",
            "propose",
            "freeze",
            "confirm",
            "read",
        }:
            raise ValueError("unknown synthesis action")
        return getattr(service, action)(**parameters)
    finally:
        service.close()
