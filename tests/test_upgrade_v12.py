"""Focused v12 regression tests; runnable with stdlib unittest."""

from __future__ import annotations

import unittest

import numpy as np

from track2_v5.agent_adapter import LocalLLMIntentAdapter
from track2_v5.association_discovery import discover_association_factors
from track2_v5.experiment_platform import DryRunExperimentPlatform
from track2_v5.factor_retriever import retrieve_factor_candidates
from track2_v5.factor_store import FactorStore
from track2_v5.rate_aware_rca import decompose_rate_mix, make_demo_panel, discover_rate_candidates
from track2_v5.baseline_attribution import (
    attribute_baseline, change_registry_entry, external_event_entry, simulate_panel,
)


class UpgradeV12Tests(unittest.TestCase):
    def test_probability_decomposition_closes_with_interaction(self):
        result = decompose_rate_mix(
            {"a": {"share": 0.5, "rate": 0.1}, "b": {"share": 0.5, "rate": 0.2}},
            {"a": {"share": 0.6, "rate": 0.2}, "b": {"share": 0.4, "rate": 0.1}},
        )
        self.assertTrue(result["closed"])
        self.assertAlmostEqual(result["delta"], result["rate"] + result["mix"] + result["interaction"])
        self.assertNotEqual(result["interaction"], 0.0)
        self.assertEqual(decompose_rate_mix({"a": {"share": 1, "rate": .1}}, {})["status"],
                         "DECOMPOSITION_NOT_CLOSED")

    def test_rate_rca_marks_complete_panel_closed(self):
        fixture = make_demo_panel()
        result = discover_rate_candidates(
            fixture["panel"], ("region", "channel", "version"), (0, 39), (40, 59),
            min_impressions=1000, top_k=5, beam_width=20,
        )
        self.assertEqual(result["overall_change"]["treatment_decomposition"]["status"], "CLOSED")
        self.assertEqual(result["candidates"][0]["decomposition_status"], "CLOSED")
        self.assertEqual(result["candidates"][0]["scope"], fixture["truth"]["affected_scope"])

    def test_baseline_step_detection_is_two_sided(self):
        days = list(range(40))
        control = np.full(40, 100.0)
        treated = control.copy()
        treated[15:] += 50.0
        treated[30:] -= 40.0
        # A common shock is present, but it must not create an artificial
        # upward step when the event window ends.
        control[10:13] -= 70.0
        treated[10:13] -= 70.0
        result = attribute_baseline(
            days,
            control,
            treated,
            [],
            [external_event_entry("regulation", 10, 12, "regulation", "fixture")],
            {},
            detection_threshold=10.0,
        )
        directions = {alert["direction"] for alert in result["unregistered_alerts"]}
        self.assertEqual(directions, {"up", "down"})
        self.assertTrue(all(alert["absolute_step"] >= 0 for alert in result["unregistered_alerts"]))

    def test_common_external_shock_is_not_subtracted_twice(self):
        days = list(range(20))
        control = [100.0] * 20
        treated = [100.0] * 20
        for index in range(8, 12):
            control[index] -= 20.0
            treated[index] -= 20.0
        result = attribute_baseline(
            days,
            control,
            treated,
            [],
            [external_event_entry("macro", 8, 11, "macro", "common shock")],
            {},
            detection_threshold=5.0,
        )
        self.assertEqual(result["series"]["gap"][8:12], [0.0] * 4)
        self.assertNotIn("external_explained", result["series"])
        self.assertEqual(result["series"]["residual"][8:12], [0.0] * 4)
        self.assertEqual(
            result["series"]["external_control_deviation"][8:12], [-20.0] * 4
        )

    def test_association_has_holdout_and_block_manifest(self):
        days = list(range(60))
        residual = (np.sin(np.arange(60) / 3.0) + np.random.default_rng(4).normal(0, .1, 60)).tolist()
        factor = {"factor_id": "internal.quality", "scope_id": "global", "days": days,
                  "values": residual, "source_reliability": .9, "scope_match": .9}
        result = discover_association_factors(
            days, residual, [{"start_day": 20, "end_day": 25}], factor_series=[factor],
            max_lag=3, bootstrap_reps=19, discovery_days=list(range(45)),
            holdout_days=list(range(45, 60)), seed=7,
        )
        manifest = result["search_manifest"]
        self.assertEqual(manifest["comparisons"], 21)
        self.assertEqual(manifest["D"], 3)
        self.assertEqual(set(manifest["derived_layers"]), {"level", "velocity", "acceleration"})
        self.assertEqual(manifest["bootstrap_method"], "detrended_moving_block_independent_null_max_t")
        self.assertIn("max_t_pvalue", result["candidates"][0])
        self.assertIn("holdout_survivors", result)
        series_candidates = [
            item for item in result["candidates"]
            if item["source_type"] == "factor_series"
        ]
        self.assertTrue(series_candidates)
        self.assertTrue(
            all(item["factor_id"] == "internal.quality" for item in series_candidates)
        )
        self.assertTrue(
            all(item["derived_feature_id"].startswith("internal.quality.") for item in series_candidates)
        )

    def test_factor_rag_keeps_provenance(self):
        store = FactorStore()
        store.register_factor({"factor_id": "fx", "name": "汇率", "description": "美元汇率",
                               "aliases": ["外汇"], "source_type": "authorized_external",
                               "license_ref": "public", "metadata": {"kind": "macro"}})
        store.ingest_evidence({"factor_id": "fx", "evidence_type": "official", "source_uri": "https://example.test",
                               "license_ref": "public"})
        store.ingest_factor_snapshot({"factor_id": "fx", "day": 1, "value": 7.1,
                                     "license_ref": "public"})
        result = retrieve_factor_candidates(store, "汇率")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["evidence"][0]["source_uri"], "https://example.test")
        self.assertEqual(len(result["candidates"][0]["snapshots"]), 1)
        store.close()

    def test_n2_fallback_and_n3_human_gate(self):
        adapter = LocalLLMIntentAdapter(lambda _text: {"bad": True})
        output = adapter.analyze("请找出竞品因子")
        self.assertTrue(output["fallback"])
        self.assertEqual(output["intent"]["intent"], "factor_search")
        platform = DryRunExperimentPlatform()
        design = {"template_id": "x", "metric": "qualified_ctr", "factors": ["a"],
                  "stable_randomization_unit": "hashed_subject_id",
                  "metric_contract": {"name": "qualified_ctr", "unit": "rate"}}
        created = platform.create_experiment(design, "approval-1")
        platform.start_canary(created["experiment_id"], 5)
        paused = platform.pause_experiment(created["experiment_id"], "guardrail")
        self.assertEqual(paused["status"], "PAUSE_RECOMMENDED")
        with self.assertRaises(PermissionError):
            platform.promote(created["experiment_id"], "approval-2")


if __name__ == "__main__":
    unittest.main()
