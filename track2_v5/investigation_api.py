"""JSON/CLI boundary for durable phase-C operations; no model-supplied evidence writes."""

from __future__ import annotations

from .hypothesis_registry import HypothesisRegistry
from .loop_controller import LoopController
from .policy_adapter import LocalPolicyAdapter, run_loop


def execute_investigation(*, db_path, action, parameters=None):
    parameters = dict(parameters or {})
    registry = HypothesisRegistry(db_path)
    try:
        if action == "invalidate":
            return {"affected": registry.invalidate(**parameters)}
        if action == "revise_resource":
            return registry.revise_resource(**parameters)
        if action == "register_hypothesis":
            return {"hypothesis_id": registry.register(**parameters)}
        if action == "snapshot":
            return registry.snapshot()
        if action == "audit":
            return {"events": registry.audit()}
        if action == "read_asset":
            return registry.asset(**parameters)
        if action == "create_loop_from_factors":
            return create_loop_from_factors(registry, **parameters)
        if action == "create_loop":
            loop = LoopController.create(registry, **parameters)
            return {"loop_id": loop.loop_id, **loop.state()}
        if action in {
            "step_loop",
            "finish_loop",
            "run_loop",
            "recover_loop",
            "read_loop",
        }:
            loop = LoopController(registry, parameters.pop("loop_id"))
            if action == "step_loop":
                return loop.step(**parameters)
            if action == "finish_loop":
                return loop.finish(**parameters)
            if action == "run_loop":
                return run_loop(loop, LocalPolicyAdapter(**parameters))
            if parameters:
                raise ValueError("unexpected loop parameters")
            return loop.recover() if action == "recover_loop" else loop.state()
        raise ValueError("unknown investigation operation")
    finally:
        registry.close()


def execute_factor_registry(*, db_path, action, parameters):
    from .factor_registry import FactorRegistry

    registry = FactorRegistry(db_path)
    try:
        from .adapters import intake_factor_series

        allowed = {
            "intake_adapter": lambda **kwargs: intake_factor_series(registry, **kwargs),
            "intake_next_window": registry.intake_next_window,
            "retrieve": registry.retrieve_factor_candidates,
            "history": registry.history,
        }
        if action not in allowed:
            raise ValueError("unknown factor operation")
        return {"result": allowed[action](**parameters)}
    finally:
        registry.close()


def create_loop_from_factors(
    registry,
    *,
    data_ref,
    resource_name,
    factor_db_path,
    as_of,
    search_window,
    config=None,
):
    from .factor_registry import FactorRegistry

    factors = FactorRegistry(factor_db_path)
    try:
        candidates = factors.retrieve_factor_candidates(
            as_of=as_of, search_window=search_window, limit=100000
        )
        snapshot = factors.export_window(
            registry,
            name=resource_name + ":factor_selection",
            as_of=as_of,
            search_window=search_window,
        )
    finally:
        factors.close()
    data = registry.asset(data_ref)
    if data["status"] != "VALID":
        raise ValueError("data snapshot invalid")
    body = data["body"]
    series = []
    for candidate in candidates:
        contract = candidate.get("factor_contract")
        if not contract or not candidate["production_eligible"]:
            continue
        scopes = sorted({s.get("scope_id", "global") for s in candidate["snapshots"]})
        for scope in scopes:
            points = sorted(
                [
                    s
                    for s in candidate["snapshots"]
                    if s.get("scope_id", "global") == scope
                ],
                key=lambda s: s["day"],
            )
            if [p["day"] for p in points] != body["days"]:
                continue
            series.append(
                {
                    "factor_id": candidate["factor_id"] + ":" + scope,
                    "registry_factor_id": candidate["factor_id"],
                    "scope_id": scope,
                    "days": body["days"],
                    "values": [p["value"] for p in points],
                    "unit": contract["unit"],
                    "source_type": candidate["source_type"],
                    "kind": "continuous",
                    "factor_contract": contract,
                }
            )
    if not series:
        raise ValueError(
            "no contract-valid aligned factor snapshots available for this window"
        )
    prepared = registry.revise_resource(
        resource_name,
        {"days": body["days"], "residual": body["residual"], "factor_series": series},
        dependencies=[data_ref, snapshot["ref"]],
    )
    loop = LoopController.create(
        registry, data_ref=prepared["ref"], resource_name=resource_name, config=config
    )
    return {"loop_id": loop.loop_id, **loop.state()}
