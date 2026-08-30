from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from attribution.bayes import estimate_hte
from attribution.claim_ledger import ClaimLedger
from attribution.experiment_designer import design_experiment
from attribution.fdr import benjamini_hochberg
from attribution.rate_aware_rca import decompose_rate_mix
from attribution.spec import spec_diff
from run_server import bounded_float, bounded_int, valid_case
from runtime.dataset_catalog import load_dataset_catalog
from runtime.experiment_integrity import experiment_integrity_report
from runtime.foundation import LocalEvidenceProvider


class RegressionTests(unittest.TestCase):
    @staticmethod
    def _hte_segments() -> list[dict[str, object]]:
        return [
            {
                "segment_id": f"segment-{index}",
                "control": {"clicks": 50 + index, "impressions": 1_000},
                "treatment": {"clicks": 42 + 3 * index, "impressions": 1_000},
            }
            for index in range(3)
        ]

    def test_bounded_int_accepts_value_in_range(self) -> None:
        self.assertEqual(bounded_int("3", minimum=1, maximum=5, name="n"), 3)

    def test_bounded_int_rejects_invalid_and_out_of_range_values(self) -> None:
        for value in ("bad", "0", "6"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bounded_int(value, minimum=1, maximum=5, name="n")

    def test_bounded_float_rejects_non_finite_values(self) -> None:
        for value in ("nan", "inf", "-inf", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bounded_float(value, minimum=0.0, maximum=1.0, name="threshold")

    def test_case_validation_is_closed_to_known_cases(self) -> None:
        self.assertEqual(valid_case("c"), "C")
        with self.assertRaises(ValueError):
            valid_case("unknown")

    def test_evidence_pack_write_is_atomic_and_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = LocalEvidenceProvider(Path(directory))
            payload = {"state": "CLOSED", "evidence": [{"content_digest": "abc"}]}
            path = provider.write_pack("task-1", payload)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["state"], "CLOSED"
            )
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_rate_mix_interaction_decomposition_closes(self) -> None:
        before = {"a": {"share": 0.4, "rate": 0.1}, "b": {"share": 0.6, "rate": 0.2}}
        after = {"a": {"share": 0.5, "rate": 0.15}, "b": {"share": 0.5, "rate": 0.18}}
        result = decompose_rate_mix(before, after)
        self.assertTrue(result["closed"])
        self.assertTrue(math.isclose(result["closure_error"], 0.0, abs_tol=1e-12))

    def test_rate_decomposition_refuses_mismatched_cells(self) -> None:
        result = decompose_rate_mix(
            {"a": {"share": 1.0, "rate": 0.1}},
            {"b": {"share": 1.0, "rate": 0.1}},
        )
        self.assertFalse(result["closed"])
        self.assertEqual(result["reason"], "cell_set_mismatch")

    def test_factorial_design_refuses_truncation(self) -> None:
        with self.assertRaises(ValueError):
            design_experiment(["a", "b", "c"], max_arms=4)

    def test_claim_ledger_downgrades_selected_hte(self) -> None:
        claim = ClaimLedger().add_claim(
            "HETEROGENEOUS_TREATMENT_EFFECT",
            "selected on the same outcome",
            selected_after_seeing_outcome=True,
        )
        self.assertEqual(claim["claim_type"], "EXPLORATORY_HETEROGENEITY")

    def test_bh_adjustment_is_monotone_in_rank(self) -> None:
        qvalues = benjamini_hochberg([0.01, 0.04, 0.03, 0.9])
        ranked = [q for _, q in sorted(zip([0.01, 0.04, 0.03, 0.9], qvalues))]
        self.assertEqual(ranked, sorted(ranked))

    def test_experiment_integrity_fails_closed_without_rows(self) -> None:
        report = experiment_integrity_report([], {"identity": "user_id"}, {})
        self.assertFalse(report["causal_estimators_allowed"])
        self.assertEqual(len(report["failed_checks"]), 8)

    def test_specs_and_dataset_catalog_have_required_structure(self) -> None:
        factors = spec_diff(
            {"component": {"name": "Card"}, "props": {"color": {"default": "blue"}}},
            {"component": {"name": "Card"}, "props": {"color": {"default": "red"}}},
        )
        self.assertEqual(factors[0]["factor_id"], "card.color")
        catalog = load_dataset_catalog()
        self.assertGreaterEqual(len(catalog["datasets"]), 1)
        self.assertTrue(
            all(
                item["official_url"].startswith("https://")
                for item in catalog["datasets"]
            )
        )

    def test_student_t_joint_posterior_propagates_hyperparameters(self) -> None:
        result = estimate_hte(
            self._hte_segments(),
            likelihood="student_t",
            draws=1_000,
            seed=7,
        )
        hyper = result["student_t_hyperparameter_posterior"]
        self.assertEqual(result["tau_source"], "joint_hyperparameter_posterior")
        self.assertGreater(hyper["candidate_component_count"], 100)
        self.assertGreater(result["segments"][0]["standard_error_shrunk"], 0.0)

    def test_student_t_joint_posterior_rejects_invalid_nu_grid(self) -> None:
        with self.assertRaises(ValueError):
            estimate_hte(
                self._hte_segments(),
                likelihood="student_t",
                draws=1_000,
                student_t_nu_grid=[2.0, 5.0],
            )


if __name__ == "__main__":
    unittest.main()
