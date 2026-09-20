"""Paired no-memory/retrieval/governed memory and orchestration/loop evaluation."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_stage_e_statistics import association_request, effect_request, metric
from track2_v5.agent_orchestrator import run_pipeline
from track2_v5.contracts import digest
from track2_v5.evaluation import binomial_interval, mean_interval
from track2_v5.hypothesis_registry import HypothesisRegistry
from track2_v5.loop_controller import LoopController
from track2_v5.persistence import atomic_json
from track2_v5.skill_governance import SkillGovernance
from track2_v5.skill_replay import isolated_replay


def evaluate(output, repetitions=20):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    protocol = {
        "schema": "agent-comparison/1",
        "seeds": list(range(72000, 72000 + repetitions)),
        "model": "deterministic_rules",
        "model_calls": 0,
        "method_budget": 1,
        "worker_timeout": 30,
        "memory_arms": ["no_memory", "retrieval_only", "governed"],
        "same_tools": True,
        "cache_policy": "new task and data per seed, no cached execution",
        "scope": "metric-check method tasks; no claim of language-model or general reasoning benefit",
    }
    atomic_json(out / "protocol.json", protocol)
    service = SkillGovernance(out / "skills.db")
    context = {"metric_kind": "sum"}
    try:

        def request(i):
            m = metric()
            m["window"] = [i, i + 9]
            return {"metric_contract": m}

        def asset(i):
            r = request(i)
            return r, service.registry.add_asset("data", r)

        def suite(offset):
            cases = []
            for i in (offset, offset + 1):
                r, ref = asset(i)
                cases.append(
                    {
                        "task_id": f"validation-{i}",
                        "data_ref": ref,
                        "request": r,
                        "context": context,
                        "expected_operation": "check_metric",
                        "critical": True,
                    }
                )
            return service.freeze_suite(cases=cases)["suite_ref"]

        start = time.monotonic()
        r, ref = asset(0)
        trace = service.capture(
            task_id="source",
            data_ref=ref,
            context=context,
            operation="check_metric",
            author="author",
        )
        service.propose(
            name="metric", trace_ids=[trace["trace_id"]], applicability=context
        )
        service.review(name="metric", version=1, reviewer="independent-reviewer")
        frozen = suite(100)
        service.validate(name="metric", version=1, suite_ref=frozen)
        receipt = service.approve(
            name="metric",
            version=1,
            approver="human",
            credential_ref="fixture:declared-approval",
            suite_ref=frozen,
        )["approval_ref"]
        service.publish(name="metric", version=1, approval_ref=receipt)
        monitor = suite(200)
        service.monitor(name="metric", version=1, suite_ref=monitor)
        receipt = service.approve(
            name="metric",
            version=1,
            approver="human",
            credential_ref="fixture:expansion",
            suite_ref=monitor,
        )["approval_ref"]
        service.publish(name="metric", version=1, approval_ref=receipt, fraction=1.0)
        governance_seconds = time.monotonic() - start
        governance_snapshot = service.get("metric", 1)
        runs = []
        for seed in protocol["seeds"]:
            r, ref = asset(seed)
            expected = True
            if seed % 4 == 0:
                r["metric_contract"].pop("unit")
                ref = service.registry.add_asset("data", r)
                expected = False
            for arm in protocol["memory_arms"]:
                before = time.monotonic()
                task = f"{arm}-{seed}"
                hit = None
                if arm == "governed":
                    report = service.replay(
                        name="metric",
                        context=context,
                        task_id=task,
                        data_ref=ref,
                        window=seed,
                    )["report"]
                    hit = True
                else:
                    if arm == "retrieval_only":
                        hit = service.retrieve(
                            name="metric",
                            context=context,
                            task_id=task,
                            data_ref=ref,
                            window=seed,
                        )
                    report = isolated_replay(
                        "check_metric",
                        r,
                        {"task_id": task, "data_ref": ref, "skill_ref": arm},
                        timeout=30,
                    )
                runs.append(
                    {
                        "seed": seed,
                        "arm": arm,
                        "correct": report["result"]["passed"] == expected,
                        "retrieval_hit": bool(hit),
                        "seconds": time.monotonic() - before,
                        "cost": report["cost"],
                        "manual_interventions": 0,
                        "false_causal_assertion": bool(
                            report["result"].get("causal_eligible", False)
                        ),
                        "report_digest": report["digest"],
                    }
                )
        atomic_json(
            out / "memory.json",
            {
                "protocol_digest": digest(protocol),
                "governance_once_seconds": governance_seconds,
                "governance_human_approval_events": 2,
                "governance_snapshot": governance_snapshot,
                "source_trace": trace,
                "runs": runs,
                "summary": {
                    arm: {
                        "correctness": mean_interval(
                            [float(r["correct"]) for r in runs if r["arm"] == arm],
                            bounded=True,
                        ),
                        "seconds": mean_interval(
                            [r["seconds"] for r in runs if r["arm"] == arm]
                        ),
                        "total_seconds_including_governance": sum(
                            r["seconds"] for r in runs if r["arm"] == arm
                        )
                        + (governance_seconds if arm == "governed" else 0),
                        "false_causal_interval_95": binomial_interval(
                            sum(
                                r["false_causal_assertion"]
                                for r in runs
                                if r["arm"] == arm
                            ),
                            repetitions,
                        ),
                        "model_tokens": 0,
                    }
                    for arm in protocol["memory_arms"]
                },
                "paired_correctness_gain": mean_interval(
                    [
                        float(
                            next(
                                r
                                for r in runs
                                if r["seed"] == s and r["arm"] == "governed"
                            )["correct"]
                        )
                        - float(
                            next(
                                r
                                for r in runs
                                if r["seed"] == s and r["arm"] == "no_memory"
                            )["correct"]
                        )
                        for s in protocol["seeds"]
                    ]
                ),
                "interpretation": "No gain is a valid outcome. Governance cost is included; deterministic task results do not establish model-learning gains.",
            },
        )
    finally:
        service.close()
    orchestration = []
    loops = []
    for seed in protocol["seeds"]:
        request, _, _ = effect_request("A_signal", seed)
        pubs = []
        for mode in ("single_worker", "isolated"):
            before = time.monotonic()
            r = run_pipeline(request, execution_mode=mode)
            pubs.append(r.get("publication"))
            orchestration.append(
                {
                    "seed": seed,
                    "mode": mode,
                    "status": r["execution_status"],
                    "seconds": time.monotonic() - before,
                    "total_io_bytes": r["total_io_bytes"],
                    "model_tokens": r["model_tokens"],
                    "fallback": r["fallback"],
                    "cost_ledger": r["cost_ledger"],
                    "publication_digest": digest(r.get("publication")),
                }
            )
        if pubs[0] != pubs[1]:
            raise AssertionError("orchestration modes changed evidence")
        req, positive = association_request(
            "positive_lag" if seed % 2 else "null", seed
        )
        data = {k: req[k] for k in ("days", "residual", "factor_series")}
        for mode in ("single_pass", "loop"):
            registry = HypothesisRegistry(out / f"loop-{seed}-{mode}.db")
            try:
                name = f"data-{seed}"
                ref = registry.revise_resource(name, data)["ref"]
                controller = LoopController.create(
                    registry,
                    data_ref=ref,
                    resource_name=name,
                    config={
                        "max_rounds": 3,
                        "max_tests": 100,
                        "max_lag": 2,
                        "smoothing_window": 1,
                        "derived_layers": ["level"],
                        "bootstrap_reps": 199,
                        "block_length": 5,
                        "seed": seed,
                    },
                )
                before = time.monotonic()
                controller.step(
                    {
                        "action": "ADD_HYPOTHESES",
                        "parameters": {
                            "factor_ids": ["x"] if mode == "loop" else ["x", "noise"]
                        },
                        "rationale": "frozen paired discovery",
                    }
                )
                if mode == "loop" and controller.state()["phase"] == "DISCOVERY":
                    controller.step(
                        {
                            "action": "ADD_HYPOTHESES",
                            "parameters": {"factor_ids": ["noise"]},
                            "rationale": "second registered round",
                        }
                    )
                state = controller.finish()
                selected = {
                    h["spec"]["factor_id"]
                    for h in (
                        registry.hypothesis(ref) for ref in state["hypotheses"].values()
                    )
                    if h["state"] == "supported"
                }
                loops.append(
                    {
                        "seed": seed,
                        "mode": mode,
                        "seconds": time.monotonic() - before,
                        "selected": sorted(selected),
                        "fdp": len(selected - positive) / max(1, len(selected)),
                        "power": len(selected & positive) / len(positive)
                        if positive
                        else None,
                        "tests_spent": state["tests_spent"],
                        "rounds": state["round"],
                        "reason_codes": state["reason_codes"],
                        "phase": state["phase"],
                        "state": state,
                    }
                )
            finally:
                registry.close()
        atomic_json(out / "orchestration.json", orchestration)
        atomic_json(out / "loops.json", loops)
        print("paired_seed", seed, flush=True)
    return {
        "status": "COMPLETE",
        "memory_runs": repetitions * 3,
        "orchestration_runs": len(orchestration),
        "loop_runs": len(loops),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="outputs/stage_e/agents")
    p.add_argument("--repetitions", type=int, default=20)
    a = p.parse_args()
    print(json.dumps(evaluate(a.output, a.repetitions)))
