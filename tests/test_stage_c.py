"""Phase C: publication enforcement, durable investigation, isolation and as-of intake."""

import copy
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import numpy as np

from track2_v5.agent_orchestrator import invoke_worker, run_pipeline
from track2_v5.claim_ledger import ClaimLedger
from track2_v5.factor_registry import FactorRegistry
from track2_v5.hypothesis_registry import HypothesisRegistry
from track2_v5.loop_controller import LoopController, validate_proposal
from track2_v5.policy_adapter import LocalPolicyAdapter, run_loop
from track2_v5.publication import (
    govern_output,
    persist_publication,
    publish_conclusion,
    verify_publication,
)
from track2_v5.quant_track import estimate_randomized_effect
from track2_v5.skill_evolution import SkillStore
from track2_v5.stage_worker import handle


def metric():
    return {
        "name": "conversion",
        "numerator": "converted",
        "denominator": "users",
        "aggregation": "ratio_of_sums",
        "unit": "rate",
        "analysis_unit": "user",
        "target_population": "eligible_users",
        "timezone": "UTC",
        "window": [0, 9],
        "maturity_days": 2,
        "deduplication": "unit_id",
    }


def parameters(randomized=True):
    return {
        "rows": [
            {
                "unit_id": i,
                "treatment": i % 2,
                "outcome": int(i % 2 == 1 and i % 4 == 1),
            }
            for i in range(160)
        ],
        "metric_contract": metric(),
        "assignment_ref": "fixture:random_assignment",
        "randomized": randomized,
        "observed_through": 11,
        "no_interference_ref": "fixture:independent_users",
    }


def panel():
    rng = np.random.default_rng(123)
    x = rng.normal(size=100)
    return {
        "days": list(range(100)),
        "residual": (x + rng.normal(size=100) * 0.2).tolist(),
        "factor_series": [
            {
                "factor_id": "x",
                "values": x.tolist(),
                "kind": "continuous",
                "source_type": "internal",
                "unit": "index",
            }
        ],
    }


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "registry.db"
        self.registry = HypothesisRegistry(self.path)
        self.addCleanup(self.registry.close)
        self.source = self.registry.revise_resource("observations", {"rows": "v1"})[
            "ref"
        ]
        self.result = estimate_randomized_effect(**parameters())

    def test_three_objects_and_direct_rct(self):
        result = publish_conclusion(self.result["contracts"], practical_threshold=0.01)
        self.assertEqual(result["claim_type"], "RANDOMIZED_EFFECT")
        self.assertEqual(result["interpretation"], "PRACTICAL_EFFECT")
        self.assertIsNone(result["statistical_uncertainty"]["posterior_probability"])
        self.assertEqual(verify_publication(result), result)
        forged = copy.deepcopy(result)
        forged["statement"] = "证明是根因"
        with self.assertRaises(ValueError):
            verify_publication(forged)

    def test_equivalence_inconclusive_and_untrustworthy_are_distinct(self):
        equivalent = publish_conclusion(self.result["contracts"], practical_threshold=1)
        self.assertEqual(equivalent["interpretation"], "PRACTICALLY_EQUIVALENT")
        inconclusive = publish_conclusion(
            self.result["contracts"], practical_threshold=0.5
        )
        self.assertEqual(inconclusive["interpretation"], "INCONCLUSIVE")
        refused = publish_conclusion(
            estimate_randomized_effect(**parameters(False))["contracts"]
        )
        self.assertEqual(refused["interpretation"], "UNTRUSTWORTHY")
        self.assertIsNone(refused["statistical_uncertainty"]["effect"])
        exploratory = parameters()
        exploratory["selection_status"] = "exploratory"
        self.assertEqual(
            publish_conclusion(estimate_randomized_effect(**exploratory)["contracts"])[
                "interpretation"
            ],
            "NEEDS_INDEPENDENT_CONFIRMATION",
        )

    def test_legacy_cannot_publish_unidentified_claim(self):
        ledger = ClaimLedger()
        claim = ledger.add_claim(
            "BUNDLE_EFFECT", "证明根因", posterior_probability=0.999
        )
        self.assertEqual(claim["claim_type"], "ASSOCIATION_ONLY")
        self.assertIsNone(claim["posterior_probability"])
        report = govern_output(
            {
                "payload": {
                    "claim_type": "RANDOMIZED_EFFECT",
                    "statement": "fake",
                    "effect": 42,
                }
            }
        )
        self.assertIsNone(report["payload"]["effect"])
        valid = ledger.add_claim(
            "BUNDLE_EFFECT", "arbitrary override", contracts=self.result["contracts"]
        )
        self.assertNotEqual(valid["statement"], "arbitrary override")

    def test_durable_transitive_revocation_and_reopen(self):
        stat = self.registry.record_result(
            self.result, dependencies=[self.source], operation="effect"
        )
        claim = persist_publication(
            self.registry, self.result["contracts"], dependencies=[stat]
        )
        skill = self.registry.add_asset(
            "skill", {"name": "test"}, dependencies=[claim["publication_ref"]]
        )
        revised = self.registry.revise_resource("observations", {"rows": "v2"})
        self.assertEqual(revised["version"], 2)
        other = HypothesisRegistry(self.path)
        try:
            self.assertEqual(other.asset(stat)["status"], "INVALID")
            self.assertEqual(other.asset(claim["publication_ref"])["status"], "REVOKED")
            self.assertEqual(other.asset(skill)["status"], "SUSPENDED")
            self.assertIsNone(govern_output(claim, registry=other)["effect_estimate"])
            with self.assertRaises(ValueError):
                other.record_result(
                    self.result, dependencies=[self.source], operation="effect"
                )
        finally:
            other.close()

    def test_only_evidence_moves_states_and_parent_gate(self):
        h = self.registry.register({"factor_id": "assignment"})
        with self.assertRaises(ValueError):
            self.registry.register({"factor_id": "x"}, parents=[h])
        with self.assertRaises(ValueError):
            self.registry.register({"factor_id": "x", "state": "supported"})
        stat = self.registry.record_result(
            self.result, dependencies=[self.source], operation="effect"
        )
        self.assertEqual(self.registry.apply_evidence(h, stat)["state"], "supported")
        child = self.registry.register(
            {"factor_id": "assignment", "variant": "refined"}, parents=[h]
        )
        self.assertEqual(self.registry.hypothesis(child)["state"], "open")
        with self.assertRaises(ValueError):
            self.registry.apply_evidence(child, self.source)
        self.registry.invalidate(self.source, reason="corrected")
        self.assertEqual(self.registry.hypothesis(h)["state"], "dormant")

    def test_actual_skill_is_suspended_on_evidence_revision(self):
        store = SkillStore(Path(self.tmp.name) / "skills.json")
        name = "factor_mining"
        # Use the same evolvable skill and valid rule schema as production.
        entry = store.register(name, [], "fixture")
        skill_ref = store.bind_evidence(
            name, entry["version"], self.registry, [self.source]
        )
        record = store._record(name)
        record["active"] = entry["version"]
        store.save()
        self.assertIsNotNone(store.active(name))
        self.registry.invalidate(self.source, reason="corrected")
        self.assertEqual(self.registry.asset(skill_ref)["status"], "SUSPENDED")
        self.assertIsNone(SkillStore(store.path).active(name))
        with self.assertRaises(ValueError):
            store.activate(name, entry["version"], "cannot revive")

    def test_revision_cannot_depend_on_invalidated_predecessor(self):
        with self.assertRaises(ValueError):
            self.registry.revise_resource(
                "observations", {"rows": "v2"}, dependencies=[self.source]
            )
        self.assertEqual(self.registry.asset(self.source)["status"], "VALID")


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = HypothesisRegistry(Path(self.tmp.name) / "r.db")
        self.addCleanup(self.registry.close)
        self.data = self.registry.revise_resource("panel", panel())["ref"]
        self.config = {
            "max_lag": 1,
            "derived_layers": ["level"],
            "smoothing_window": 1,
            "bootstrap_reps": 19,
            "block_length": 3,
            "min_abs_correlation": 0.1,
        }
        self.loop = LoopController.create(
            self.registry, data_ref=self.data, resource_name="panel", config=self.config
        )

    def test_no_model_loop_completes_and_charges_both_lag_directions(self):
        result = run_loop(self.loop)
        self.assertEqual(result["phase"], "COMPLETED")
        self.assertLessEqual(result["round"], 3)
        self.assertEqual(result["tests_spent"], 6)
        self.assertEqual(len(result["attempts"][0]["test_manifest"]), 3)
        self.assertIsNotNone(result["exit_report"])
        self.assertEqual(
            self.registry.db.execute("SELECT count(*) FROM holdouts").fetchone()[0], 1
        )
        self.assertEqual(self.loop.finish(), result)

    def test_holdout_is_hidden_and_reuse_cannot_reset_via_seed(self):
        state = self.loop.state()
        seen = self.loop._data(state, ["x"])
        self.assertLess(
            max(seen["days"]), min(state["holdout_days"]) - state["config"]["gap_days"]
        )
        self.assertNotIn("residual", self.loop.snapshot_for_policy())
        run_loop(self.loop)
        second = LoopController.create(
            self.registry,
            data_ref=self.data,
            resource_name="panel",
            config={**self.config, "seed": 1234},
        )
        with self.assertRaises(ValueError):
            second.step(
                {"action": "ADD_HYPOTHESES", "parameters": {"factor_ids": ["x"]}}
            )
            second.finish()

    def test_schema_forbids_budget_window_and_status_escape(self):
        for parameters_ in [{"alpha": 1}, {"window": [80, 99]}, {"state": "supported"}]:
            with self.assertRaises(ValueError):
                validate_proposal(
                    {"action": "ADJUST_THRESHOLD", "parameters": parameters_}
                )
        with self.assertRaises(ValueError):
            self.loop.step({"action": "SYNTHESIZE_FACTOR"})
        with self.assertRaises(ValueError):
            LoopController.create(
                self.registry,
                data_ref=self.data,
                resource_name="panel",
                config={"max_rounds": 4},
            )

    def test_crash_consumes_holdout_and_does_not_rerun(self):
        self.loop.step(
            {"action": "ADD_HYPOTHESES", "parameters": {"factor_ids": ["x"]}}
        )
        with (
            patch(
                "track2_v5.association_discovery.discover_association_factors",
                side_effect=RuntimeError("crash"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.loop.finish()
        self.assertEqual(self.loop.state()["phase"], "STOPPED")
        self.assertEqual(
            self.registry.db.execute("SELECT status FROM holdouts").fetchone()[0],
            "CONSUMED",
        )
        self.assertEqual(self.loop.recover()["phase"], "STOPPED")

    def test_pending_attempt_recovers_without_reset(self):
        state = self.loop.state()
        state["pending"] = {"round": 1}
        state["tests_spent"] = 3
        self.loop._save(state)
        recovered = self.loop.recover()
        self.assertEqual(recovered["phase"], "STOPPED")
        self.assertEqual(recovered["tests_spent"], 3)
        self.assertEqual(recovered["attempts"][-1]["status"], "INTERRUPTED")

    def test_optimistic_concurrent_update_rejected(self):
        first, second = self.loop.state(), self.loop.state()
        self.loop._save(first)
        with self.assertRaises(ValueError):
            self.loop._save(second)

    def test_no_progress_stops_and_budget_cannot_overrun(self):
        constrained = LoopController.create(
            self.registry,
            data_ref=self.data,
            resource_name="panel",
            config={**self.config, "max_tests": 5},
        )
        result = run_loop(constrained)
        self.assertEqual(result["tests_spent"], 0)
        self.assertEqual(result["reason_codes"], ["INSUFFICIENT_POWER"])


class WorkerTests(unittest.TestCase):
    def test_four_real_processes_and_bound_handoffs(self):
        report = run_pipeline(
            {"route": "A", "parameters": parameters()}, baseline_bytes=10000000
        )
        self.assertEqual(report["execution_status"], "COMPLETED", report.get("error"))
        self.assertEqual(
            [r["stage"] for r in report["records"]],
            ["L0", "L1", "identification", "L3"],
        )
        self.assertEqual(len({r["pid"] for r in report["records"]}), 4)
        self.assertFalse(report["fallback"])
        self.assertEqual(report["publication"]["claim_type"], "RANDOMIZED_EFFECT")

    def test_cost_fallback_runs_remaining_stages_in_one_process(self):
        report = run_pipeline(
            {"route": "A", "parameters": parameters()}, baseline_bytes=1
        )
        self.assertEqual(report["execution_status"], "COMPLETED", report.get("error"))
        self.assertTrue(report["fallback"])
        self.assertEqual(len(report["cost_ledger"]), 2)
        self.assertEqual(len({r["pid"] for r in report["records"][1:]}), 1)

    def test_worker_capability_and_timeout_fail_closed(self):
        with self.assertRaises(ValueError):
            handle(
                {
                    "schema_version": "worker/1",
                    "previous_ref": "root",
                    "jobs": [{"stage": "shell", "payload": {}}],
                }
            )
        report = run_pipeline(
            {"route": "A", "parameters": parameters()}, timeout=0.00001
        )
        self.assertEqual(report["execution_status"], "FAILED")
        self.assertEqual(report["records"], [])
        self.assertNotIn("publication", report)

    def test_identification_handoff_cannot_be_forged(self):
        with self.assertRaises(ValueError):
            invoke_worker(
                [
                    {
                        "stage": "L3",
                        "payload": {
                            "route": "A",
                            "parameters": parameters(),
                            "identification": {},
                            "publication_options": {},
                        },
                    }
                ],
                "root",
            )


class PolicyTests(unittest.TestCase):
    def test_real_local_http_schema_and_timeout_fallback(self):
        class Handler(BaseHTTPRequestHandler):
            mode = "valid"

            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                if self.mode == "slow":
                    time.sleep(0.15)
                proposal = {
                    "action": "ADD_HYPOTHESES",
                    "parameters": {"factor_ids": ["x"]},
                }
                if self.mode == "invalid":
                    proposal["parameters"]["alpha"] = 1
                raw = json.dumps(
                    {"choices": [{"message": {"content": json.dumps(proposal)}}]}
                ).encode()
                self.send_response(200)
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except BrokenPipeError:
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            adapter = LocalPolicyAdapter(
                f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                timeout=1,
            )
            snapshot = {
                "phase": "DISCOVERY",
                "round": 0,
                "allowed_actions": ["ADD_HYPOTHESES", "STOP"],
            }
            self.assertEqual(
                adapter.propose(snapshot, factor_ids=["x"])["provider"], "local_http"
            )
            Handler.mode = "invalid"
            self.assertEqual(
                adapter.propose(snapshot, factor_ids=["x"])["provider"], "rules"
            )
            Handler.mode = "slow"
            adapter.timeout = 0.05
            self.assertEqual(
                adapter.propose(snapshot, factor_ids=["x"])["provider"], "rules"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class FactorTests(unittest.TestCase):
    def test_versions_asof_alias_next_window_and_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            factor = FactorRegistry(Path(tmp) / "f.db")
            registry = HypothesisRegistry(Path(tmp) / "r.db")
            try:
                declaration = {
                    "factor_id": "x",
                    "name": "X",
                    "aliases": ["人工事件"],
                    "source_type": "human_reported",
                    "license_ref": "operator-entry",
                    "metadata": {"kind": "event", "lineage": ["parent:a"]},
                }
                evidence = {
                    "factor_id": "x",
                    "evidence_id": "e1",
                    "source_uri": "manual:entry",
                    "license_ref": "operator-entry",
                }
                snapshot = {
                    "factor_id": "x",
                    "day": 5,
                    "value": 1,
                    "source_uri": "manual:entry",
                    "license_ref": "operator-entry",
                }
                factor.intake_next_window(
                    declaration,
                    evidence=[evidence],
                    snapshots=[snapshot],
                    current_window=1,
                    available_day=10,
                )
                self.assertEqual(
                    factor.retrieve_factor_candidates(as_of=10, search_window=1), []
                )
                self.assertEqual(
                    factor.retrieve_factor_candidates(as_of=9, search_window=2), []
                )
                item = factor.retrieve_factor_candidates(
                    "人工事件", as_of=10, search_window=2
                )[0]
                self.assertEqual(item["snapshots"][0]["value"], 1)
                self.assertIsNone(item["posterior_probability"])
                exported = factor.export_window(
                    registry, name="factors", as_of=20, search_window=3
                )
                dependent = registry.add_asset(
                    "statistic", {"test": 1}, dependencies=[exported["ref"]]
                )
                factor.intake_next_window(
                    declaration,
                    evidence=[evidence],
                    snapshots=[{**snapshot, "value": 2}],
                    current_window=2,
                    available_day=15,
                )
                self.assertEqual(
                    factor.retrieve_factor_candidates(as_of=10, search_window=2)[0][
                        "snapshots"
                    ][0]["value"],
                    1,
                )
                self.assertEqual(
                    factor.retrieve_factor_candidates(as_of=20, search_window=3)[0][
                        "snapshots"
                    ][0]["value"],
                    2,
                )
                factor.export_window(
                    registry, name="factors", as_of=20, search_window=3
                )
                self.assertEqual(registry.asset(dependent)["status"], "INVALID")
                self.assertEqual(
                    len([v for v in factor.history("x") if v["kind"] == "snapshot"]), 2
                )
            finally:
                factor.close()
                registry.close()


if __name__ == "__main__":
    unittest.main()


class IntegrationTests(unittest.TestCase):
    def test_legacy_artifact_and_saved_run_cannot_bypass_publication(self):
        from track2_v5.scenario_reports import read_run, run_causal_investigation

        with tempfile.TemporaryDirectory() as tmp:
            report = run_causal_investigation(
                {"route": "A", "parameters": parameters()}, tmp, baseline_bytes=10000000
            )
            self.assertEqual(report["execution_status"], "COMPLETED")
            registry = HypothesisRegistry(report["registry_path"])
            try:
                registry.invalidate(report["data_ref"], reason="corrected observation")
                current = read_run(Path(tmp), report["run_id"])
                self.assertEqual(current["publication_status"], "REVOKED")
                self.assertNotIn("publication", current)
            finally:
                registry.close()
            import sys

            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
            from goai_control_tower.foundation import LocalEvidenceProvider

            pack = {
                "payload": {
                    "claim_type": "BUNDLE_EFFECT",
                    "effect": 123,
                    "statement": "fake",
                }
            }
            path = LocalEvidenceProvider(Path(tmp) / "evidence").write_pack(
                "task", pack
            )
            self.assertEqual(
                json.loads(path.read_text())["payload"]["claim_type"],
                "ASSOCIATION_ONLY",
            )
            self.assertIsNone(pack["payload"]["effect"])

    def test_adapter_to_factor_contract_to_real_loop(self):
        from track2_v5.adapters import intake_factor_series
        from track2_v5.investigation_api import create_loop_from_factors

        with tempfile.TemporaryDirectory() as tmp:
            factors = FactorRegistry(Path(tmp) / "factor.db")
            registry = HypothesisRegistry(Path(tmp) / "registry.db")
            try:
                data = panel()
                series = {
                    **data["factor_series"][0],
                    "days": data["days"],
                    "source_uri": "fixture:source",
                    "license_ref": "fixture-license",
                    "response_window": [0, 1],
                }
                intake_factor_series(
                    factors, [series], current_window=0, available_day=0
                )
                self.assertEqual(
                    factors.retrieve_factor_candidates(as_of=99, search_window=0), []
                )
                contract = factors.retrieve_factor_candidates(
                    as_of=99, search_window=1
                )[0]["factor_contract"]
                self.assertEqual(contract["unit"], "index")
                source = registry.revise_resource("raw", data)["ref"]
                prepared = create_loop_from_factors(
                    registry,
                    data_ref=source,
                    resource_name="analysis",
                    factor_db_path=factors.db_path,
                    as_of=99,
                    search_window=1,
                    config={
                        "max_lag": 1,
                        "derived_layers": ["level"],
                        "smoothing_window": 1,
                        "bootstrap_reps": 19,
                        "block_length": 3,
                    },
                )
                state = run_loop(LoopController(registry, prepared["loop_id"]))
                self.assertEqual(state["phase"], "COMPLETED")
                self.assertTrue(state["exit_report"])
                self.assertTrue(state["attempts"][0]["progressed"])
            finally:
                factors.close()
                registry.close()

    def test_graph_attempts_are_counted_and_budget_stops_computation(self):
        from track2_v5.causal_discovery import discover_causal_graph

        data = panel()
        params = dict(
            days=data["days"],
            columns={"x": data["factor_series"][0]["values"], "y": data["residual"]},
            screened_candidates=["x", "y"],
            tau_max=1,
            response_window_basis="registered one day",
            max_condition_dim=1,
        )
        result = discover_causal_graph(**params)
        self.assertEqual(result["ci_tests_spent"], len(result["attempted_tests"]))
        self.assertGreater(result["ci_tests_spent"], 1)
        json.dumps(result, allow_nan=False)
        with self.assertRaises(ValueError) as caught:
            discover_causal_graph(**params, max_ci_tests=1)
        self.assertEqual(len(caught.exception.attempted_tests), 1)

    def test_component_contract_and_three_terminal_hypothesis_states(self):
        contracts = estimate_randomized_effect(**parameters())["contracts"]
        design = {
            "independent_randomization": True,
            "assignment_provenance": "signed_config",
            "design_code_traceable": True,
            "stable_randomization_unit": True,
        }
        self.assertEqual(
            publish_conclusion(contracts, component_design=design)["claim_type"],
            "COMPONENT_RANDOMIZED_EFFECT",
        )
        with self.assertRaises(ValueError):
            publish_conclusion(
                contracts, component_design={**design, "assignment_provenance": "model"}
            )
        registry = HypothesisRegistry()
        try:
            data = registry.add_asset("data", parameters())
            stat = registry.record_result(
                {"contracts": contracts}, dependencies=[data], operation="effect"
            )
            for direction, threshold, expected in [
                ("positive", 0.01, "supported"),
                ("negative", 0.01, "refuted"),
                ("positive", 0.5, "dormant"),
            ]:
                h = registry.register(
                    {
                        "factor_id": "assignment",
                        "direction": direction,
                        "threshold": threshold,
                    }
                )
                self.assertEqual(registry.apply_evidence(h, stat)["state"], expected)
        finally:
            registry.close()

    def test_loop_preregistered_independent_quantification(self):
        registry = HypothesisRegistry()
        try:
            source = registry.revise_resource("panel", panel())["ref"]
            request = registry.add_asset(
                "data",
                {
                    "independent_of_search": True,
                    "independence_ref": "preregistration:separate_experiment",
                    "route": "A",
                    "parameters": parameters(),
                },
            )
            loop = LoopController.create(
                registry,
                data_ref=source,
                resource_name="panel",
                config={"quantification_requests": {"experiment": request}},
            )
            state = loop.step(
                {"action": "QUANTIFY", "parameters": {"request_id": "experiment"}}
            )
            self.assertEqual(state["phase"], "COMPLETED")
            self.assertEqual(state["reason_codes"], [])
            self.assertEqual(state["tests_spent"], 1)
            self.assertEqual(
                registry.db.execute("SELECT count(*) FROM holdouts").fetchone()[0], 0
            )
        finally:
            registry.close()
