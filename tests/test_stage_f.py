"""Research validity and opt-in synthesis cannot bypass production gates."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from track2_v5.evaluation import mean_interval
from track2_v5.factor_synthesis import FactorSynthesis, evaluate_expression
from track2_v5.knockoff_research import (
    coefficient_difference,
    e_bh,
    gaussian_knockoffs,
    run_knockoff_research,
)


def data(seed=1, start=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=100)
    z = rng.normal(size=100)
    return {
        "days": list(range(start, start + 100)),
        "response": (x * z + 0.05 * rng.normal(size=100)).tolist(),
        "available_day": start + 99,
        "factors": {
            "x": {"values": x.tolist(), "unit": "index"},
            "z": {"values": z.tolist(), "unit": "index"},
        },
    }


class KnockoffTests(unittest.TestCase):
    def test_gaussian_joint_swap_and_empirical_marginal(self):
        cov = np.array([[1, 0.4], [0.4, 1]])
        x = np.random.default_rng(1).multivariate_normal([0, 0], cov, size=4000)
        knock, diagnosis = gaussian_knockoffs(x, cov, seed=2)
        self.assertLess(diagnosis["row_exchangeability_max_error"], 1e-12)
        self.assertGreater(diagnosis["min_joint_eigenvalue"], 0)
        np.testing.assert_allclose(np.cov(knock, rowvar=False), cov, atol=0.07)
        with self.assertRaises(ValueError):
            gaussian_knockoffs(x, [[1, 1], [1, 1]])

    def test_exact_flip_sign_all_other_features_unchanged(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=(100, 8))
        knock, _ = gaussian_knockoffs(x, np.eye(8))
        y = x[:, 0] + rng.normal(size=100)
        original = coefficient_difference(x, knock, y)
        for j in range(8):
            a = x.copy()
            b = knock.copy()
            a[:, j], b[:, j] = knock[:, j], x[:, j]
            expected = original.copy()
            expected[j] *= -1
            np.testing.assert_allclose(
                coefficient_difference(a, b, y), expected, atol=1e-10
            )

    def test_dependent_rows_never_claim_exact_fdr_from_thinning(self):
        rng = np.random.default_rng(8)
        x = rng.normal(size=(160, 12))
        y = rng.normal(size=160)
        common = {
            "x": x.tolist(),
            "y": y.tolist(),
            "feature_ids": [str(i) for i in range(12)],
            "covariance": np.eye(12).tolist(),
            "distribution_known": True,
            "distribution_ref": "known:DGP",
        }
        iid = run_knockoff_research(**common)
        dependent = run_knockoff_research(**common, temporal_rho=0.8, subsample_gap=3)
        self.assertTrue(iid["eligible_under_declared_iid_gaussian_model"])
        self.assertFalse(dependent["eligible_under_declared_iid_gaussian_model"])
        self.assertGreater(dependent["full_temporal_swap_error"], 0.01)
        self.assertFalse(iid["formal_selection_allowed"])
        self.assertFalse(dependent["causal_eligible"])

    def test_e_bh_and_zero_error_uncertainty(self):
        self.assertEqual(e_bh([100, 100, 0, 0], alpha=0.1), [0, 1])
        self.assertGreater(
            mean_interval([0.0] * 50, bounded=True)["mc_interval_95"][1], 0
        )


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = FactorSynthesis(Path(self.tmp.name) / "state.db")
        self.addCleanup(self.service.close)
        self.ref = self.service.registry.add_asset("data", data())
        self.expression = {"op": "multiply", "args": [{"factor": "x"}, {"factor": "z"}]}

    def setup_family(self):
        self.service.configure(policy_id="p", enabled=True, max_candidates=2)
        return self.service.propose(
            policy_id="p",
            task_id="task",
            data_ref=self.ref,
            expression=self.expression,
            current_window=99,
        )

    def test_default_disabled_and_protected_complexity(self):
        self.service.configure(policy_id="off")
        with self.assertRaises(ValueError):
            self.service.propose(
                policy_id="off",
                task_id="t",
                data_ref=self.ref,
                expression=self.expression,
                current_window=99,
            )
        with self.assertRaises(ValueError):
            evaluate_expression({"op": "eval", "args": []}, data())
        with self.assertRaises(ValueError):
            evaluate_expression(
                {"op": "lag", "steps": -1, "args": [{"factor": "x"}]}, data()
            )
        with self.assertRaises(ValueError):
            evaluate_expression(self.expression, data(), max_nodes=2)

    def test_unit_division_and_trailing_alignment(self):
        d = data()
        d["factors"]["z"]["unit"] = "currency"
        with self.assertRaises(ValueError):
            evaluate_expression(
                {"op": "add", "args": [{"factor": "x"}, {"factor": "z"}]}, d
            )
        d["factors"]["z"]["values"][0] = 0
        with self.assertRaises(ValueError):
            evaluate_expression(
                {"op": "divide", "args": [{"factor": "x"}, {"factor": "z"}]}, d
            )
        r = evaluate_expression(
            {"op": "lag", "steps": 2, "args": [{"factor": "x"}]}, data()
        )
        self.assertEqual(r["days"][0], 2)
        self.assertEqual(r["values"][0], data()["factors"]["x"]["values"][0])
        self.assertEqual(r["omitted_days"], [0, 1])

    def test_freeze_whole_family_and_real_next_window_confirmation(self):
        first = self.setup_family()
        self.service.propose(
            policy_id="p",
            task_id="task",
            data_ref=self.ref,
            expression={"op": "subtract", "args": [{"factor": "x"}, {"factor": "z"}]},
            current_window=99,
        )
        frozen = self.service.freeze(task_id="task")
        self.assertEqual(len(frozen["items"]), 2)
        with self.assertRaises(ValueError):
            self.service.propose(
                policy_id="p",
                task_id="task",
                data_ref=self.ref,
                expression={"factor": "x"},
                current_window=99,
            )
        with self.assertRaises(ValueError):
            self.service.confirm(task_id="task", data_ref=self.ref)
        ref = self.service.registry.add_asset("data", data(2, 110))
        result = self.service.confirm(task_id="task", data_ref=ref)
        selected = {
            r["alert_id"] for r in result["confirmation"]["results"] if r["confirmed"]
        }
        self.assertIn(first["factor_id"], selected)
        self.assertEqual(len(result["confirmation"]["results"]), 2)
        self.assertEqual(result["tests_spent"], 4)
        self.assertFalse(result["confirmation"]["causal_eligible"])
        self.assertEqual(
            self.service.confirm(task_id="task", data_ref=ref)["result_ref"],
            result["result_ref"],
        )

    def test_new_window_units_and_source_invalidation(self):
        self.setup_family()
        self.service.freeze(task_id="task")
        new = data(2, 110)
        new["factors"]["x"]["unit"] = "currency"
        ref = self.service.registry.add_asset("data", new)
        with self.assertRaises(ValueError):
            self.service.confirm(task_id="task", data_ref=ref)
        self.service.registry.invalidate(self.ref, reason="source corrected")
        ref = self.service.registry.add_asset("data", data(2, 110))
        with self.assertRaises(ValueError):
            self.service.confirm(task_id="task", data_ref=ref)

    def test_disable_preserves_budget_and_revised_evidence_withdraws(self):
        self.setup_family()
        self.service.set_enabled(policy_id="p", enabled=False)
        with self.assertRaises(ValueError):
            self.service.freeze(task_id="task")
        self.service.set_enabled(policy_id="p", enabled=True)
        self.service.freeze(task_id="task")
        ref = self.service.registry.add_asset("data", data(2, 110))
        self.service.confirm(task_id="task", data_ref=ref)
        self.service.registry.invalidate(ref, reason="corrected validation")
        result = self.service.read(task_id="task")
        self.assertEqual(result["state"], "WITHDRAWN")
        self.assertEqual(result["confirmation"]["results"], [])

    def test_budget_idempotency_and_future_data(self):
        self.setup_family()
        r = self.service.propose(
            policy_id="p",
            task_id="task",
            data_ref=self.ref,
            expression=self.expression,
            current_window=99,
        )
        self.assertEqual(r["decision"], "NOOP")
        self.service.propose(
            policy_id="p",
            task_id="task",
            data_ref=self.ref,
            expression={"factor": "x"},
            current_window=99,
        )
        with self.assertRaises(ValueError):
            self.service.propose(
                policy_id="p",
                task_id="task",
                data_ref=self.ref,
                expression={"factor": "z"},
                current_window=99,
            )
        with self.assertRaises(ValueError):
            self.service.propose(
                policy_id="p",
                task_id="future",
                data_ref=self.ref,
                expression=self.expression,
                current_window=98,
            )
