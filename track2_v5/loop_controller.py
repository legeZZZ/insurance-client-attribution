"""Recoverable bounded investigation; adaptive discovery, one final holdout.

Discovery q-values are descriptive under adaptation. Formal confirmation is
run once on a frozen union of attempted factors, never on a reused holdout.
"""

from __future__ import annotations

import json
import math
from itertools import pairwise

from .contracts import REASONS, digest, finite, integer
from .hypothesis_registry import HypothesisRegistry

ACTIONS = {
    "ADD_HYPOTHESES",
    "SYNTHESIZE_FACTOR",
    "ADJUST_THRESHOLD",
    "CHANGE_CONDITION_SET",
    "QUANTIFY",
    "STOP",
}


def validate_proposal(value):
    if (
        not isinstance(value, dict)
        or set(value) - {"action", "parameters", "rationale"}
        or value.get("action") not in ACTIONS
    ):
        raise ValueError("invalid policy action schema")
    parameters = value.get("parameters", {})
    if not isinstance(parameters, dict) or not isinstance(
        value.get("rationale", ""), str
    ):
        raise ValueError("invalid policy parameters")  # noqa: TRY004 -- uniform rejected-proposal API
    allowed = {
        "ADD_HYPOTHESES": {"factor_ids"},
        "SYNTHESIZE_FACTOR": set(),
        "ADJUST_THRESHOLD": {"min_abs_correlation"},
        "CHANGE_CONDITION_SET": {"factor_ids"},
        "QUANTIFY": {"request_id"},
        "STOP": {"reason_code"},
    }
    if set(parameters) - allowed[value["action"]]:
        raise ValueError("policy cannot write statuses, windows, alpha or evidence")
    if "reason_code" in parameters and parameters["reason_code"] not in REASONS:
        raise ValueError("unknown stop reason")
    if (
        "min_abs_correlation" in parameters
        and not 0 <= finite(parameters["min_abs_correlation"], "threshold") <= 1
    ):
        raise ValueError("invalid correlation threshold")
    if "factor_ids" in parameters and (
        not isinstance(parameters["factor_ids"], list)
        or not parameters["factor_ids"]
        or any(not isinstance(v, str) or not v for v in parameters["factor_ids"])
        or len(set(parameters["factor_ids"])) != len(parameters["factor_ids"])
    ):
        raise ValueError("unique named factors required")
    return {
        "action": value["action"],
        "parameters": parameters,
        "rationale": value.get("rationale", ""),
    }


class LoopController:
    def __init__(self, registry: HypothesisRegistry, loop_id):
        self.registry, self.loop_id = registry, loop_id

    @classmethod
    def create(cls, registry, *, data_ref, resource_name, config=None):
        data = registry.asset(data_ref)
        if data["kind"] != "data" or data["status"] != "VALID":
            raise ValueError("valid data snapshot required")
        body = data["body"]
        days = [integer(d, "day") for d in body["days"]]
        if not days or any(b - a != 1 for a, b in pairwise(days)):
            raise ValueError("regular ordered daily grid required")
        if not isinstance(resource_name, str) or not resource_name:
            raise ValueError(
                "stable resource identity required for holdout reuse checks"
            )
        resource = registry.db.execute(
            "SELECT current_id FROM resources WHERE name=?", (resource_name,)
        ).fetchone()
        if not resource or resource[0] != data_ref:
            raise ValueError("data must be the current version of this named resource")
        config = dict(config or {})
        allowed = {
            "max_rounds",
            "max_tests",
            "alpha",
            "gap_days",
            "max_lag",
            "smoothing_window",
            "derived_layers",
            "bootstrap_reps",
            "block_length",
            "seasonal_period",
            "statistic_method",
            "min_abs_correlation",
            "seed",
            "quantification_requests",
        }
        if set(config) - allowed:
            raise ValueError("unrecognized or model-writable loop settings")
        settings = {
            "max_rounds": 3,
            "max_tests": 2000,
            "alpha": 0.05,
            "max_lag": 2,
            "smoothing_window": 3,
            "derived_layers": ["level", "velocity"],
            "bootstrap_reps": 199,
            "block_length": 5,
            "seasonal_period": None,
            "statistic_method": "pearson",
            "min_abs_correlation": 0.25,
            "seed": 20260915,
            **config,
        }
        rounds, tests = (
            integer(settings["max_rounds"], "max_rounds"),
            integer(settings["max_tests"], "max_tests"),
        )
        if not 1 <= rounds <= 3 or tests < 1 or not 0 < settings["alpha"] < 1:
            raise ValueError("bounded rounds, test budget and alpha required")
        for key in (
            "max_lag",
            "smoothing_window",
            "bootstrap_reps",
            "block_length",
            "seed",
        ):
            settings[key] = integer(settings[key], key)
        if (
            settings["max_lag"] < 0
            or settings["smoothing_window"] < 1
            or settings["block_length"] < 1
        ):
            raise ValueError("invalid temporal settings")
        minimum_gap = settings["max_lag"] + settings["smoothing_window"] + 2
        gap = integer(settings.get("gap_days", minimum_gap), "gap_days")
        if gap < minimum_gap:
            raise ValueError("gap shorter than the registered lag/derivation boundary")
        cutoff = len(days) - math.ceil(0.2 * len(days))
        discovery, holdout = days[: cutoff - gap], days[cutoff:]
        if len(discovery) < 20 or len(holdout) < max(6, 2 * settings["block_length"]):
            raise ValueError("insufficient discovery/holdout after isolation gap")
        settings["gap_days"] = gap
        state = {
            "schema_version": "loop/1",
            "data_ref": data_ref,
            "resource_name": resource_name,
            "config": settings,
            "discovery_days": discovery,
            "holdout_days": holdout,
            "round": 0,
            "phase": "DISCOVERY",
            "attempts": [],
            "selected_factors": [],
            "confirmation_min_abs_correlation": settings["min_abs_correlation"],
            "hypotheses": {},
            "tests_spent": 0,
            "pending": None,
            "reason_codes": [],
            "exit_report": None,
        }
        loop_id = digest(
            {"resource": resource_name, "data": data_ref, "config": settings}
        )
        with registry.transaction():
            registry.db.execute(
                "INSERT OR IGNORE INTO loops VALUES (?,1,?)",
                (loop_id, json.dumps(state, ensure_ascii=False)),
            )
            registry._audit(
                "LOOP_CREATED",
                {
                    "id": loop_id,
                    "data_ref": data_ref,
                    "holdout_window": [holdout[0], holdout[-1]],
                },
            )
        return cls(registry, loop_id)

    def state(self):
        row = self.registry.db.execute(
            "SELECT * FROM loops WHERE id=?", (self.loop_id,)
        ).fetchone()
        if not row:
            raise KeyError(self.loop_id)
        state = json.loads(row["body"])
        if state.get("schema_version") != "loop/1":
            raise ValueError("unsupported persisted loop schema")
        state.setdefault(
            "confirmation_min_abs_correlation", state["config"]["min_abs_correlation"]
        )
        if (
            digest(
                {
                    "resource": state["resource_name"],
                    "data": state["data_ref"],
                    "config": state["config"],
                }
            )
            != self.loop_id
        ):
            raise ValueError("persisted loop settings no longer match frozen identity")
        state["version"] = row["version"]
        return state

    def _save(self, state):
        version = state.pop("version")
        with self.registry.transaction():
            cursor = self.registry.db.execute(
                "UPDATE loops SET body=?,version=version+1 WHERE id=? AND version=?",
                (
                    json.dumps(state, ensure_ascii=False, allow_nan=False),
                    self.loop_id,
                    version,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("concurrent loop revision; reload before continuing")
        state["version"] = version + 1

    def snapshot_for_policy(self):
        state = self.state()
        return {
            k: state[k]
            for k in (
                "phase",
                "round",
                "selected_factors",
                "tests_spent",
                "reason_codes",
            )
        } | {
            "hypotheses": [
                self.registry.hypothesis(h) for h in state["hypotheses"].values()
            ],
            "remaining_tests": state["config"]["max_tests"] - state["tests_spent"],
            "max_rounds": state["config"]["max_rounds"],
            "allowed_actions": sorted(ACTIONS - {"SYNTHESIZE_FACTOR"}),
        }

    def _exit_report(self, state):
        if state["phase"] == "STOPPED":
            with self.registry.transaction():
                for h in state["hypotheses"].values():
                    self.registry.db.execute(
                        "UPDATE hypotheses SET state='dormant',gate_passed=0,version=version+1 WHERE id=? AND state='open'",
                        (h,),
                    )
                self.registry._audit(
                    "LOOP_STOPPED",
                    {"id": self.loop_id, "reason_codes": state["reason_codes"]},
                )
        return [
            {
                "hypothesis_id": h,
                "state": self.registry.hypothesis(h)["state"],
                "stopped_gate": self.registry.hypothesis(h)["gate"],
                "evidence_ref": self.registry.hypothesis(h)["evidence_id"],
                "statistical_uncertainty": self.registry.hypothesis(h)[
                    "statistical_uncertainty"
                ],
            }
            for h in state["hypotheses"].values()
        ]

    def recover(self):
        state = self.state()
        if state["pending"]:
            state["attempts"].append(
                {
                    **state["pending"],
                    "status": "INTERRUPTED",
                    "reason_codes": ["DATA_INVALID"],
                }
            )
            state["pending"] = None
            state["phase"] = "STOPPED"
            state["reason_codes"] = ["DATA_INVALID"]
            state["exit_report"] = self._exit_report(state)
            self._save(state)
        return state

    def _data(self, state, ids, *, final=False):
        stored = self.registry.asset(state["data_ref"])
        if stored["status"] != "VALID":
            raise ValueError("data snapshot was invalidated")
        body = stored["body"]
        eligible = (
            state["discovery_days"] + state["holdout_days"]
            if final
            else state["discovery_days"]
        )
        # Final runner receives the isolation days too; discovery stage never sees them.
        if final:
            eligible = body["days"]
        positions = [i for i, d in enumerate(body["days"]) if d in set(eligible)]
        series = []
        for factor in body["factor_series"]:
            if factor["factor_id"] not in ids:
                continue
            fd = factor.get("days", body["days"])
            keep = [i for i, d in enumerate(fd) if d in set(eligible)]
            series.append(
                {
                    **factor,
                    "days": [fd[i] for i in keep],
                    "values": [factor["values"][i] for i in keep],
                }
            )
        if {s["factor_id"] for s in series} != set(ids):
            raise ValueError("policy factor is outside frozen data snapshot")
        return {
            "days": [body["days"][i] for i in positions],
            "residual": [body["residual"][i] for i in positions],
            "factor_series": series,
        }

    def step(self, proposal):
        from .association_discovery import discover_association_factors

        proposal = validate_proposal(proposal)
        state = self.state()
        if state["pending"]:
            raise ValueError("unfinished attempt: recover instead of rerunning")
        if state["phase"] != "DISCOVERY":
            raise ValueError("loop has ended; cannot change selection")
        if proposal["action"] == "STOP":
            return self.finish(proposal["parameters"].get("reason_code"))
        if state["round"] >= state["config"]["max_rounds"]:
            return self.finish("INSUFFICIENT_POWER")
        ids = proposal["parameters"].get("factor_ids", state["selected_factors"])
        if proposal["action"] == "SYNTHESIZE_FACTOR":
            raise ValueError("factor synthesis is disabled by the P3 roadmap policy")
        if proposal["action"] == "QUANTIFY":
            return self._quantify(state, proposal)
        if not ids:
            raise ValueError("select factors before threshold or graph changes")
        data = self._data(state, ids)
        settings = state["config"]
        cost = (
            len(ids) * len(settings["derived_layers"]) * (2 * settings["max_lag"] + 1)
        )
        # Reserve one complete final family before any discovery attempt is admitted.
        union = sorted(set(ids) | set(state["selected_factors"]))
        final_cost = (
            len(union) * len(settings["derived_layers"]) * (2 * settings["max_lag"] + 1)
        )
        if proposal["action"] == "CHANGE_CONDITION_SET":
            cost = settings["max_tests"] - state["tests_spent"] - final_cost
            if cost < 1:
                return self.finish("INSUFFICIENT_POWER")
        if state["tests_spent"] + cost + final_cost > settings["max_tests"]:
            return self.finish("INSUFFICIENT_POWER")
        state["round"] += 1
        state["tests_spent"] += cost
        pending = {
            "round": state["round"],
            "proposal": proposal,
            "comparisons_charged": cost,
            "discovery_window": [data["days"][0], data["days"][-1]],
        }
        state["pending"] = pending
        state["selected_factors"] = union
        if proposal["action"] != "CHANGE_CONDITION_SET":
            state["confirmation_min_abs_correlation"] = min(
                state["confirmation_min_abs_correlation"],
                proposal["parameters"].get(
                    "min_abs_correlation", settings["min_abs_correlation"]
                ),
            )
        self._save(state)
        try:
            if proposal["action"] == "CHANGE_CONDITION_SET":
                from .causal_discovery import discover_causal_graph

                report = discover_causal_graph(
                    data["days"],
                    {
                        **{f["factor_id"]: f["values"] for f in data["factor_series"]},
                        "__outcome_residual__": data["residual"],
                    },
                    screened_candidates=ids,
                    protected_covariates=[*ids, "__outcome_residual__"],
                    max_ci_tests=cost,
                    tau_max=settings["max_lag"],
                    response_window_basis="registered investigation lag",
                    max_condition_dim=min(3, len(ids)),
                )
                actual = report.get("ci_tests_spent", 0)
                state["tests_spent"] -= cost - actual
                pending["comparisons_charged"] = actual
                evidence = self.registry.add_asset(
                    "statistic",
                    {"operation": "graph", "result": report},
                    dependencies=[state["data_ref"]],
                )
                progressed = False
                for factor, h in state["hypotheses"].items():
                    if (
                        factor in ids
                        and self.registry.hypothesis(h)["gate"] < 2
                        and report.get("status") == "COMPLETED"
                    ):
                        with self.registry.transaction():
                            self.registry.db.execute(
                                "UPDATE hypotheses SET gate=2,evidence_id=?,version=version+1 WHERE id=? AND state='open'",
                                (evidence, h),
                            )
                            self.registry._audit(
                                "GRAPH_DIAGNOSTIC_RECORDED",
                                {
                                    "id": h,
                                    "evidence": evidence,
                                    "causal_gate_passed": False,
                                },
                            )
                        progressed = True
            else:
                threshold = proposal["parameters"].get(
                    "min_abs_correlation", settings["min_abs_correlation"]
                )
                args = {
                    k: settings[k]
                    for k in (
                        "max_lag",
                        "smoothing_window",
                        "derived_layers",
                        "bootstrap_reps",
                        "block_length",
                        "seasonal_period",
                        "statistic_method",
                        "seed",
                    )
                }
                report = discover_association_factors(
                    **data,
                    anomaly_windows=[],
                    discovery_days=data["days"],
                    holdout_days=None,
                    min_abs_correlation=threshold,
                    **args,
                )
                evidence = self.registry.record_result(
                    report, dependencies=[state["data_ref"]], operation="discovery"
                )
                progressed = False
                for factor in ids:
                    if factor not in state["hypotheses"]:
                        state["hypotheses"][factor] = self.registry.register(
                            {
                                "factor_id": factor,
                                "scope": "registered_panel",
                                "variant": state["data_ref"],
                            }
                        )
                    h = state["hypotheses"][factor]
                    before = self.registry.hypothesis(h)["gate"]
                    if self.registry.hypothesis(h)["state"] == "open":
                        after = self.registry.apply_evidence(h, evidence)
                        progressed = progressed or after["gate"] > before
            state["attempts"].append(
                {
                    **pending,
                    "status": "COMPLETED",
                    "evidence_ref": evidence,
                    "progressed": progressed,
                    "test_manifest": report.get("attempted_tests", []),
                    "multiplicity_scope": "all adaptive discovery attempts counted; formal inference reserved for final holdout",
                }
            )
            state["pending"] = None
            self._save(state)
        except Exception as exc:
            state["attempts"].append(
                {
                    **pending,
                    "status": "FAILED",
                    "error": type(exc).__name__,
                    "test_manifest": getattr(exc, "attempted_tests", []),
                    "reason_codes": ["DATA_INVALID"],
                }
            )
            state["pending"] = None
            state["phase"] = "STOPPED"
            state["reason_codes"] = ["DATA_INVALID"]
            state["exit_report"] = self._exit_report(state)
            self._save(state)
            raise
        if not progressed or state["round"] >= settings["max_rounds"]:
            return self.finish("INSUFFICIENT_POWER" if not progressed else None)
        return self.state()

    def _quantify(self, state, proposal):
        from .quant_track import estimate_effect

        request_id = proposal["parameters"].get("request_id")
        allowed = state["config"].get("quantification_requests", {})
        if request_id not in allowed:
            raise ValueError(
                "only preregistered independent experimental requests may be quantified"
            )
        asset = self.registry.asset(allowed[request_id])
        body = asset["body"]
        if (
            asset["status"] != "VALID"
            or body.get("independent_of_search") is not True
            or not body.get("independence_ref")
        ):
            raise ValueError("independent experimental evidence reference required")
        reserve = (
            len(state["selected_factors"])
            * len(state["config"]["derived_layers"])
            * (2 * state["config"]["max_lag"] + 1)
        )
        if state["tests_spent"] + 1 + reserve > state["config"]["max_tests"]:
            return self.finish("INSUFFICIENT_POWER")
        state["round"] += 1
        state["tests_spent"] += 1
        state["pending"] = {
            "round": state["round"],
            "proposal": proposal,
            "comparisons_charged": 1,
        }
        self._save(state)
        try:
            result = estimate_effect(route=body["route"], parameters=body["parameters"])
            evidence = self.registry.record_result(
                result, dependencies=[allowed[request_id]], operation="effect"
            )
            factor = result["contracts"]["IdentificationReport"]["treatment"]
            h = self.registry.register(
                {
                    "factor_id": factor,
                    "metric": result["contracts"]["MetricContract"]["name"],
                    "variant": digest(
                        {"request": request_id, "asset": allowed[request_id]}
                    ),
                }
            )
            self.registry.apply_evidence(h, evidence)
            state["hypotheses"][factor] = h
            state["attempts"].append(
                {**state["pending"], "status": "COMPLETED", "evidence_ref": evidence}
            )
            state["pending"] = None
            self._save(state)
        except Exception:
            self.recover()
            raise
        return self.finish()

    def finish(self, reason=None):
        from .association_discovery import discover_association_factors

        state = self.state()
        if state["phase"] != "DISCOVERY":
            return state
        if state["pending"]:
            raise ValueError("cannot confirm while an attempt is pending")
        if reason and reason not in REASONS:
            raise ValueError("invalid exit reason")
        if not state["selected_factors"]:
            state["phase"] = "COMPLETED"
            supported = any(
                self.registry.hypothesis(h)["state"] == "supported"
                for h in state["hypotheses"].values()
            )
            state["reason_codes"] = (
                [reason] if reason else ([] if supported else ["INSUFFICIENT_POWER"])
            )
            state["exit_report"] = [
                self.registry.hypothesis(h) for h in state["hypotheses"].values()
            ]
            self._save(state)
            return self.state()
        window = [state["holdout_days"][0], state["holdout_days"][-1]]
        charge = (
            len(state["selected_factors"])
            * len(state["config"]["derived_layers"])
            * (2 * state["config"]["max_lag"] + 1)
        )
        if state["tests_spent"] + charge > state["config"]["max_tests"]:
            raise ValueError("final confirmation exceeds frozen test budget")
        # Consume before reading: failures/crashes retain the lease and cannot re-peek.
        with self.registry.transaction():
            for row in self.registry.db.execute(
                "SELECT window_key FROM holdouts WHERE data_ref=?",
                (state["resource_name"],),
            ):
                old = json.loads(row[0])
                if max(old[0], window[0]) <= min(old[1], window[1]):
                    raise ValueError(
                        "holdout overlaps previously consumed confirmation window"
                    )
            self.registry.db.execute(
                "INSERT INTO holdouts VALUES (?,?,?,'CONSUMED')",
                (state["resource_name"], json.dumps(window), self.loop_id),
            )
            state["phase"] = "CONFIRMING"
            state["pending"] = {
                "stage": "final_holdout",
                "window": window,
                "comparisons_charged": charge,
            }
            state["tests_spent"] += charge
            cursor = self.registry.db.execute(
                "UPDATE loops SET body=?,version=version+1 WHERE id=? AND version=?",
                (
                    json.dumps({k: v for k, v in state.items() if k != "version"}),
                    self.loop_id,
                    state["version"],
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("concurrent holdout confirmation")
            self.registry._audit(
                "HOLDOUT_CONSUMED",
                {
                    "loop": self.loop_id,
                    "resource": state["resource_name"],
                    "window": window,
                },
            )
        state = self.state()
        try:
            data = self._data(state, state["selected_factors"], final=True)
            settings = state["config"]
            args = {
                k: settings[k]
                for k in (
                    "max_lag",
                    "smoothing_window",
                    "derived_layers",
                    "bootstrap_reps",
                    "block_length",
                    "seasonal_period",
                    "statistic_method",
                    "seed",
                    "min_abs_correlation",
                )
            }
            args["min_abs_correlation"] = state["confirmation_min_abs_correlation"]
            result = discover_association_factors(
                **data,
                anomaly_windows=[],
                discovery_days=state["discovery_days"],
                holdout_days=state["holdout_days"],
                confirmation_alpha=settings["alpha"],
                **args,
            )
            ref = self.registry.record_result(
                result, dependencies=[state["data_ref"]], operation="confirmation"
            )
            for factor, h in state["hypotheses"].items():
                if (
                    factor in state["selected_factors"]
                    and self.registry.hypothesis(h)["state"] == "open"
                ):
                    self.registry.apply_evidence(h, ref)
            state["attempts"].append(
                {
                    "stage": "final_holdout",
                    "evidence_ref": ref,
                    "comparisons_charged": charge,
                    "status": "COMPLETED",
                    "test_family_ref": (result.get("test_family_contract") or {}).get(
                        "digest"
                    ),
                }
            )
            state["phase"] = "COMPLETED"
            state["confirmation_ref"] = ref
            state["reason_codes"] = (
                [] if result["holdout_survivors"] else [reason or "INSUFFICIENT_POWER"]
            )
        except Exception as exc:
            state["attempts"].append(
                {
                    **state["pending"],
                    "status": "FAILED",
                    "error": type(exc).__name__,
                    "reason_codes": ["DATA_INVALID"],
                }
            )
            state["phase"] = "STOPPED"
            state["reason_codes"] = ["DATA_INVALID"]
            raise
        finally:
            state["pending"] = None
            state["exit_report"] = self._exit_report(state)
            self._save(state)
        return self.state()
