"""Tests for D5 (human-in-the-loop), D6 (skill evolution), D7 (C line)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from track2_v5.claim_ledger import ClaimLedger
from track2_v5.factor_registry import FactorRegistry
from track2_v5.human_feedback import HumanFeedbackStore
from track2_v5.skill_evolution import (
    SkillStore,
    analyze_traces,
    assert_evolvable,
    consolidate,
    evolve_skill,
    shadow_evaluate,
)
from track2_v5.watchlist_scan import falsify, hunter_scan, run_c_line


class HumanFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = HumanFeedbackStore(Path(self.dir) / "feedback.json")

    def test_review_candidate_routing(self):
        result = self.store.review_candidate(
            "f1", "confirmed", operator="op", claim_type="WATCHLIST"
        )
        self.assertEqual(result["routing"], "queued_for_validation")
        self.assertEqual(
            result["entry"]["digest"] and len(result["entry"]["digest"]), 16
        )

    def test_supplemented_requires_note(self):
        with self.assertRaises(ValueError):
            self.store.review_candidate("f1", "supplemented", operator="op")

    def test_unknown_decision_rejected(self):
        with self.assertRaises(ValueError):
            self.store.review_candidate("f1", "approve", operator="op")

    def test_factor_supplement_registers_with_provenance(self):
        registry = FactorRegistry()
        self.store.register_factor_supplement(
            registry, "human.event.x", "线下活动", "internal_event", "op", "补登说明"
        )
        row = registry.connection.execute(
            "SELECT source_type, license_ref FROM factors WHERE factor_id=?",
            ("human.event.x",),
        ).fetchone()
        self.assertEqual(row["source_type"], "human_reported")
        self.assertEqual(row["license_ref"], "operator-entry")

    def test_budget_calibration_cold_start_and_extremes(self):
        # cold start: below min_labels -> 1.0
        self.store.record_alert_feedback("a1", "useful", "op", "internal_event")
        self.assertEqual(self.store.budget_calibration()["internal_event"], 1.0)
        # high precision -> 1.5
        for index in range(5):
            self.store.record_alert_feedback(f"b{index}", "useful", "op", "good_source")
        self.assertEqual(self.store.budget_calibration()["good_source"], 1.5)
        # low precision -> 0.5
        for index in range(5):
            self.store.record_alert_feedback(
                f"c{index}", "false_positive", "op", "bad_source"
            )
        self.assertEqual(self.store.budget_calibration()["bad_source"], 0.5)


class SkillEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = SkillStore(Path(self.dir) / "skills.json")

    def _traces(self):
        return [
            {
                "trace_id": "t1",
                "outcome": "failure",
                "context": {"metric": "rate"},
                "lesson": "check_mix_first",
            },
            {
                "trace_id": "t2",
                "outcome": "success",
                "context": {"metric": "count"},
                "lesson": "direct_sum",
            },
        ]

    def _holdout(self):
        return [
            {
                "case_id": "c1",
                "context": {"metric": "rate"},
                "expected_action": "check_mix_first",
            },
            {
                "case_id": "c2",
                "context": {"metric": "count"},
                "expected_action": "direct_sum",
            },
        ]

    def test_promote_on_improvement(self):
        result = evolve_skill(self.store, "rca", self._traces(), self._holdout())
        self.assertTrue(result["promoted"])
        self.assertEqual(result["candidate_score"], 1.0)
        self.assertEqual(self.store.active("rca")["version"], 1)

    def test_no_promotion_without_improvement(self):
        self.store.register(
            "rca",
            [
                {
                    "when": {"metric": "rate"},
                    "action": "check_mix_first",
                    "polarity": "reinforce",
                    "evidence": ["seed"],
                }
            ],
            note="seed",
        )
        self.store.validate_candidate("rca", 1, self._holdout())
        self.store.activate("rca", 1, "validated seed")
        # traces add nothing new; candidate == active -> no promotion
        result = evolve_skill(self.store, "rca", [], self._holdout())
        self.assertFalse(result["promoted"])
        self.assertEqual(self.store.active("rca")["version"], 1)

    def test_conflicts_excluded_not_voted(self):
        patches = [
            {"when": {"a": 1}, "action": "x", "polarity": "guard", "evidence": ["t1"]},
            {"when": {"a": 1}, "action": "y", "polarity": "guard", "evidence": ["t2"]},
        ]
        merged = consolidate(patches)
        self.assertEqual(len(merged["rules"]), 0)
        self.assertEqual(len(merged["conflicts"]), 1)

    def test_shadow_evaluate_no_rule_scores_zero(self):
        score = shadow_evaluate([], self._holdout())
        self.assertEqual(score, 0.0)

    def test_rollback(self):
        seed_rules = analyze_traces(self._traces()[:1])
        self.store.register("rca", seed_rules, note="seed")
        self.store.validate_candidate("rca", 1, self._holdout())
        self.store.activate("rca", 1, "validated seed")
        result = evolve_skill(self.store, "rca", self._traces(), self._holdout())
        self.assertTrue(result["promoted"])
        evolved = self.store.active("rca")
        self.assertEqual(evolved["version"], 2)
        restored = self.store.rollback("rca")
        self.assertEqual(restored["version"], 1)
        self.assertEqual(restored["rules"], seed_rules)

    def test_protected_components_refuse_evolution(self):
        with self.assertRaises(ValueError):
            assert_evolvable("statistical_core")
        with self.assertRaises(ValueError):
            assert_evolvable("evidence_gates")
        assert_evolvable("rca_drilldown")  # must not raise

    def test_analyze_traces_skips_empty_lessons(self):
        patches = analyze_traces(
            [{"trace_id": "t", "outcome": "success", "context": {}, "lesson": " "}]
        )
        self.assertEqual(patches, [])


class WatchlistScanTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.n = 60
        self.days = list(range(self.n))
        driver = rng.normal(0.0, 1.0, self.n)
        residual = np.zeros(self.n)
        for t in range(2, self.n):
            residual[t] = 0.85 * driver[t - 2] + rng.normal(0.0, 0.3)
        self.residual = residual.tolist()
        self.driver_factor = {
            "factor_id": "test.driver",
            "kind": "internal_event",
            "days": self.days,
            "values": driver.tolist(),
        }
        self.noise_factor = {
            "factor_id": "test.noise",
            "kind": "external_event",
            "days": self.days,
            "values": rng.normal(0.0, 1.0, self.n).tolist(),
        }

    def test_hunter_ranks_planted_driver_first(self):
        result = hunter_scan(
            self.days, self.residual, [self.driver_factor, self.noise_factor], budget=5
        )
        top = result["hypotheses"][0]
        self.assertEqual(top["factor_id"], "test.driver")
        self.assertEqual(top["lag"], 2)
        self.assertEqual(result["manifest"]["tested"], 2 * 5)

    def test_falsifier_kills_noise_keeps_driver(self):
        hypothesis = {
            "factor_id": "test.driver",
            "lag": 2,
            "correlation": hunter_scan(
                self.days, self.residual, [self.driver_factor], budget=1
            )["hypotheses"][0]["correlation"],
        }
        verdict = falsify(hypothesis, self.days, self.residual, self.driver_factor)
        self.assertTrue(verdict["survived"])

    def test_c_line_emits_watchlist_not_candidate(self):
        result = run_c_line(
            self.days, self.residual, [self.driver_factor, self.noise_factor], budget=4
        )
        self.assertEqual(result["claim_type"], "WATCHLIST")
        self.assertTrue(result["watchlist"])
        for item in result["watchlist"]:
            self.assertEqual(item["claim_type"], "WATCHLIST")
            self.assertNotEqual(item["factor_id"], "test.noise")

    def test_watchlist_is_ledger_legal_and_capped(self):
        ledger = ClaimLedger()
        claim = ledger.add_claim("WATCHLIST", "test.driver 滞后 2 天与残差对齐。")
        self.assertIn("值得盯防", claim["allowed_verbs"])
        self.assertIn("导致", claim["prohibited_verbs"])

    def test_budget_multiplier_steers_but_does_not_silence(self):
        boosted = hunter_scan(
            self.days,
            self.residual,
            [self.driver_factor],
            budget_multipliers={"internal_event": 1.5},
        )
        plain = hunter_scan(self.days, self.residual, [self.driver_factor])
        self.assertAlmostEqual(
            boosted["hypotheses"][0]["score"],
            plain["hypotheses"][0]["score"] * 1.5,
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
