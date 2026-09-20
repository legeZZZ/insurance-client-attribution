"""Adversarial checks for the statistical repairs; no claims of full calibration."""

import unittest

import numpy as np

from track2_v5.association_discovery import (
    _joint_max_t_pvalues,
    discover_association_factors,
)
from track2_v5.bayes import estimate_high_dimensional_hte
from track2_v5.fdr import holm
from track2_v5.validation_planner import plan_validation


class ConfirmationTests(unittest.TestCase):
    def test_fixed_signal_can_pass_confirmation(self):
        days = list(range(100))
        x = np.random.default_rng(16).normal(size=100).tolist()
        r = discover_association_factors(
            days,
            x,
            [],
            factor_series=[{"factor_id": "x", "days": days, "values": x}],
            discovery_days=list(range(60)),
            holdout_days=list(range(65, 100)),
            max_lag=0,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=99,
        )
        self.assertEqual(
            r["candidates"][0]["confirmation_status"], "CONFIRMED_ASSOCIATION"
        )
        self.assertEqual(r["candidates"][0]["claim_type"], "FACTOR_CANDIDATE")

    def test_direction_reversal_is_watchlist_and_cannot_schedule_action(self):
        rng = np.random.default_rng(12)
        x = rng.normal(size=80)
        y = x.copy()
        y[50:] *= -1
        result = discover_association_factors(
            list(range(80)),
            y.tolist(),
            [],
            factor_series=[
                {"factor_id": "x", "days": list(range(80)), "values": x.tolist()}
            ],
            discovery_days=list(range(50)),
            holdout_days=list(range(50, 80)),
            max_lag=0,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=39,
        )
        candidate = result["candidates"][0]
        self.assertEqual(candidate["claim_type"], "WATCHLIST")
        self.assertEqual(candidate["confirmation_status"], "HOLDOUT_FAILED")
        plan = plan_validation(
            candidate, {"name": "y"}, discovery_window=[0, 49], holdout_window=[50, 79]
        )
        self.assertIsNone(plan["experiment_spec"])
        self.assertEqual(
            plan["next_window_action"], "collect_independent_confirmation_evidence"
        )
        self.assertIn("digest", result["test_family_contract"])

    def test_short_holdout_cannot_promote(self):
        x = np.random.default_rng(4).normal(size=20).tolist()
        r = discover_association_factors(
            list(range(20)),
            x,
            [],
            factor_series=[{"factor_id": "x", "days": list(range(20)), "values": x}],
            discovery_days=list(range(16)),
            holdout_days=list(range(16, 20)),
            max_lag=0,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=19,
        )
        self.assertEqual(
            r["candidates"][0]["confirmation_status"], "INSUFFICIENT_HOLDOUT"
        )
        self.assertEqual(r["holdout_survivors"], 0)

    def test_joint_null_preserves_duplicate_views_and_lag_target(self):
        rng = np.random.default_rng(9)
        y = rng.normal(size=30)
        x = rng.normal(size=26)
        base = {
            "_grid_days": list(range(30)),
            "_pair_days": np.arange(26),
            "_x": x,
            "lag_days": 4,
            "correlation": 0.4,
        }
        single = _joint_max_t_pvalues(
            [dict(base)], y, 3, 19, np.random.default_rng(1), None
        )
        duplicate = [dict(base), dict(base)]
        double = _joint_max_t_pvalues(
            duplicate, y, 3, 19, np.random.default_rng(1), None
        )
        self.assertEqual(double, single * 2)
        self.assertEqual(duplicate[0]["_positions"].tolist(), list(range(4, 30)))

    def test_holm_known_family(self):
        np.testing.assert_allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        with self.assertRaises(ValueError):
            holm([float("nan")])


class HTEInferenceTests(unittest.TestCase):
    def test_empty_subgroup_kept_as_explicit_insufficient_result(self):
        rows = [{"t": i % 2, "y": i % 3 == 0, "x": i % 2} for i in range(100)]
        r = estimate_high_dimensional_hte(
            rows,
            "t",
            "y",
            ["x"],
            [],
            [{"id": "absent", "condition": {"x": 9}}],
            propensity=0.5,
        )
        self.assertEqual(r["subgroups"][0]["inference_status"], "EMPTY_SUBGROUP")
        self.assertIsNone(r["subgroups"][0]["interval_95"])

    def test_strong_shrinkage_does_not_move_interval_center(self):
        rows = [
            {"t": i % 2, "y": int(i % 2 == 1 and i < 100), "x": int(i < 100)}
            for i in range(1000)
        ]
        r = estimate_high_dimensional_hte(
            rows,
            "t",
            "y",
            ["x"],
            [],
            [{"id": "group", "condition": {"x": 1}}],
            propensity=0.5,
            ridge_alpha=1e10,
        )
        group = r["subgroups"][0]
        self.assertEqual(group["estimate"], 1.0)
        self.assertEqual(group["interval_95"], [1.0, 1.0])
        self.assertLess(group["effect_shrunk"], 0.2)
        self.assertNotIn("aipw", group["se_method"])

    def test_missing_arm_in_subgroup_is_insufficient(self):
        rows = [{"t": i % 2, "y": i % 3 == 0, "x": i % 2} for i in range(100)]
        r = estimate_high_dimensional_hte(
            rows,
            "t",
            "y",
            ["x"],
            [],
            [{"id": "treated_only", "condition": {"x": 1}}],
            propensity=0.5,
        )
        self.assertIsNone(r["subgroups"][0]["interval_95"])
        self.assertEqual(
            r["subgroups"][0]["inference_status"], "INSUFFICIENT_ARM_OBSERVATIONS"
        )


if __name__ == "__main__":
    unittest.main()
