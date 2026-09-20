"""Enterprise/dual-domain/blind scoring and backend deployment contracts."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.check_stage_e_statistics import effect_request
from tools.generate_domain_examples import generate
from track2_v5.agent_orchestrator import run_pipeline
from track2_v5.blind_validation import BlindValidation
from track2_v5.enterprise import external_adapter, load_manifest, run_enterprise
from track2_v5.evaluation import (
    TRUTH_KEYS,
    binomial_interval,
    normalize_result,
    score_predictions,
)


class EnterpriseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        generate(self.root / "domains")

    def test_both_domains_all_lines_use_shared_engine(self):
        outputs = []
        for domain in ("insurance", "ecommerce"):
            for line in ("A", "B", "C"):
                r = run_enterprise(
                    manifest_path=self.root / "domains" / domain / (line + ".json"),
                    as_of=101,
                    runtime_dir=self.root / "runtime",
                )
                self.assertEqual(r["engine"], "track2_v5_shared")
                self.assertEqual(r["result"]["execution_status"], "COMPLETED")
                outputs.append(r)
        self.assertEqual(
            outputs[0]["result"]["publication"]["statistical_uncertainty"]["effect"],
            outputs[3]["result"]["publication"]["statistical_uncertainty"]["effect"],
        )
        self.assertTrue(outputs[1]["result"]["scan"]["watchlist"])

    def test_source_availability_and_mapping_collisions(self):
        path = self.root / "domains/insurance/A.json"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            load_manifest(path, as_of=100)
        body = json.loads(path.read_text())
        body["tables"]["observations"]["field_mapping"]["conversion"] = "treatment"
        path.write_text(json.dumps(body))
        # treatment already mapped from assigned_arm: collision is rejected.
        with self.assertRaises(ValueError):
            load_manifest(path, as_of=101)

    def test_duplicate_unit_and_future_panel_rejected(self):
        folder = self.root / "domains/insurance"
        p = folder / "observations.json"
        rows = json.loads(p.read_text())
        rows.append(rows[0])
        p.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, "unique"):
            run_enterprise(
                manifest_path=folder / "A.json",
                as_of=101,
                runtime_dir=self.root / "runtime",
            )
        p = folder / "panel.json"
        rows = json.loads(p.read_text())
        rows[-1]["day"] = 200
        p.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, "as-of"):
            run_enterprise(
                manifest_path=folder / "C.json",
                as_of=101,
                runtime_dir=self.root / "runtime",
            )

    def test_n2_rules_and_n3_sandbox_guardrails(self):
        r = external_adapter(
            kind="N2",
            parameters={
                "snapshot": {"phase": "DISCOVERY", "round": 0},
                "factor_ids": ["x"],
            },
        )
        self.assertEqual(r["proposal"]["action"], "ADD_HYPOTHESES")
        p = {
            "design": {
                "template_id": "two_arm",
                "metric": "conversion",
                "factors": ["x"],
                "stable_randomization_unit": "user",
                "metric_contract": {"name": "conversion", "unit": "rate"},
            },
            "approval_ref": "fixture:sandbox",
        }
        r = external_adapter(kind="N3", parameters=p)
        self.assertEqual(r["side_effect"], "none_sandbox")
        self.assertEqual(r["final"]["status"], "PAUSE_RECOMMENDED")
        with self.assertRaises(ValueError):
            external_adapter(kind="N3", parameters={**p, "mode": "production"})

    def test_n1_next_window_intake(self):
        from track2_v5.factor_registry import FactorRegistry

        p = {
            "db_path": str(self.root / "factors.db"),
            "current_window": 100,
            "available_day": 101,
            "factor_series": [
                {
                    "factor_id": "x",
                    "days": [0, 1],
                    "values": [1.0, 2.0],
                    "source_uri": "declared://feed",
                    "license_ref": "declared",
                    "unit": "index",
                    "source_type": "authorized_external",
                    "response_window": [1, 2],
                }
            ],
        }
        result = external_adapter(kind="N1", parameters=p)
        self.assertTrue(result)
        registry = FactorRegistry(p["db_path"])
        self.addCleanup(registry.close)
        self.assertFalse(
            registry.retrieve_factor_candidates(query="x", as_of=100, search_window=100)
        )


class BlindTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "blind.db"
        self.service = BlindValidation(self.path)
        self.addCleanup(self.service.close)
        req, truth, _ = effect_request("A_signal", 60000)
        self.truth = {k: None for k in TRUTH_KEYS}
        self.truth["intervention_effects"] = [
            {"id": "effect", "effect": truth, "identifiable": True}
        ]
        self.request = {"operation": "effect", "parameters": req}
        self.protocol = {
            "frozen_by": "analyst",
            "analysis_as_of": 101,
            "truth_scope": "full",
        }
        self.service.freeze(
            case_id="case", request=self.request, protocol=self.protocol
        )

    def test_reveal_only_after_actual_result_freeze(self):
        with self.assertRaises(ValueError):
            self.service.reveal(
                case_id="case",
                truth=self.truth,
                reviewer="reviewer",
                evidence_ref="fixture:truth",
            )
        result = self.service.run(case_id="case")
        self.assertEqual(result["state"], "RESULT_FROZEN")
        r = self.service.reveal(
            case_id="case",
            truth=self.truth,
            reviewer="reviewer",
            evidence_ref="fixture:truth",
        )
        self.assertEqual(r["scores"]["intervention_effects"]["evaluated"], 1)
        self.assertEqual(r["scores"]["graph_edges"]["status"], "UNKNOWN_TRUTH")
        self.assertEqual(
            self.service.run(case_id="case")["result_digest"], result["result_digest"]
        )
        self.service.report(
            case_id="case", output_path=Path(self.tmp.name) / "report.md"
        )

    def test_no_input_or_oracle_replacement(self):
        req = copy.deepcopy(self.request)
        req["parameters"]["parameters"]["rows"][0]["outcome"] += 1
        with self.assertRaises(ValueError):
            self.service.freeze(case_id="case", request=req, protocol=self.protocol)
        self.service.run(case_id="case")
        with self.assertRaises(ValueError):
            self.service.reveal(
                case_id="case",
                truth=self.truth,
                reviewer="analyst",
                evidence_ref="fixture:truth",
            )
        self.service.reveal(
            case_id="case",
            truth=self.truth,
            reviewer="independent",
            evidence_ref="fixture:truth",
        )
        changed = copy.deepcopy(self.truth)
        changed["intervention_effects"][0]["effect"] = 100
        with self.assertRaises(ValueError):
            self.service.reveal(
                case_id="case",
                truth=changed,
                reviewer="independent",
                evidence_ref="fixture:truth",
            )

    def test_failed_run_is_frozen_and_not_silently_retried(self):
        with patch(
            "track2_v5.quant_track.estimate_effect", side_effect=ValueError("failed")
        ):
            r = self.service.run(case_id="case")
        self.assertEqual(r["result"]["execution_status"], "FAILED")
        self.assertEqual(
            self.service.run(case_id="case")["result_digest"], r["result_digest"]
        )
        r = self.service.reveal(
            case_id="case",
            truth=self.truth,
            reviewer="independent",
            evidence_ref="fixture:truth",
        )
        self.assertEqual(r["scores"]["intervention_effects"]["unavailable"], 1)

    def test_restart_preserves_frozen_digest(self):
        before = self.service.run(case_id="case")
        other = BlindValidation(self.path)
        try:
            self.assertEqual(
                other.read(case_id="case")["result_digest"], before["result_digest"]
            )
        finally:
            other.close()

    def test_separate_truth_and_unknowns_not_false_positive(self):
        truth = {k: None for k in TRUTH_KEYS}
        truth["marginal_dependence"] = [
            {"id": "x", "positive": True},
            {"id": "noise", "positive": False},
        ]
        r = score_predictions(
            {"marginal_dependence": [{"id": "x"}, {"id": "noise"}, {"id": "unknown"}]},
            truth,
        )
        self.assertEqual(r["marginal_dependence"]["fdp"], 0.5)
        self.assertEqual(r["marginal_dependence"]["unknown_selected"], ["unknown"])
        self.assertEqual(r["graph_edges"]["status"], "UNKNOWN_TRUTH")
        self.assertGreater(binomial_interval(0, 50)[1], 0)


class OrchestrationTests(unittest.TestCase):
    def test_single_worker_and_isolated_same_evidence_semantics(self):
        request, _, _ = effect_request("A_signal", 60000)
        a = run_pipeline(request, execution_mode="isolated")
        b = run_pipeline(request, execution_mode="single_worker")
        self.assertEqual(a["publication"], b["publication"])
        self.assertEqual(len(b["cost_ledger"]), 1)
        self.assertEqual(
            [r["stage"] for r in a["records"]], [r["stage"] for r in b["records"]]
        )
        self.assertEqual(normalize_result(a), normalize_result(b))
