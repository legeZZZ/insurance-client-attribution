from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from attribution.agent_chat import handle_message, reset_session
from attribution.baseline_attribution import (
    attribute_baseline,
    change_registry_entry,
    external_event_entry,
    simulate_panel,
)
from attribution.bayes import estimate_hte
from attribution.claim_ledger import ClaimLedger
from attribution.experiment_designer import design_experiment
from attribution.fdr import benjamini_hochberg
from attribution.rate_aware_rca import decompose_rate_mix
from attribution.scenario_reports import _scenario_experience
from attribution.spec import spec_diff
from run_server import bounded_float, bounded_int, valid_case
from runtime.analysis import evaluate_public_dataset
from runtime.cases import (
    case_experiment_metadata,
    default_metric_contract,
    generate_dataset,
)
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

    def test_null_outcome_fields_fail_closed_before_causal_estimation(self) -> None:
        rows, _ = generate_dataset("C", seed=42, n=1_200)
        rows[0]["issued"] = None
        rows[0]["net_premium"] = None
        result = evaluate_public_dataset(
            {
                "rows": rows,
                "metric_contract": default_metric_contract(),
                "experiment_metadata": case_experiment_metadata("C"),
            }
        )
        self.assertEqual(result["causal_readiness"]["outcome"], "DATA_INSUFFICIENT")
        self.assertNotIn("estimate", result)
        missing = result["causal_readiness"]["diagnostics"]["missing_evidence"]
        self.assertIn("non_null_issued", missing)
        self.assertIn("non_null_net_premium", missing)

    def test_common_external_shock_is_not_subtracted_twice(self) -> None:
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

    def test_merged_line_b_alert_keeps_magnitude_fields_consistent(self) -> None:
        panel = simulate_panel()
        result = attribute_baseline(
            panel["days"],
            panel["control"],
            panel["treated"],
            [
                change_registry_entry(
                    "ranking", 15, "ranking", experiment_id="exp_ranking"
                ),
                change_registry_entry(
                    "subsidy", 30, "subsidy", experiment_id="exp_subsidy"
                ),
            ],
            [external_event_entry("regulation", 45, 49, "regulation", "event")],
            panel["experiments"],
        )
        for alert in result["unregistered_alerts"]:
            self.assertEqual(alert["absolute_step"], abs(alert["step_score"]))

    def test_srm_and_stability_count_randomization_units_not_rows(self) -> None:
        rows, _ = generate_dataset("C", seed=42, n=1_200)
        control = [row for row in rows if row["assigned_treatment"] == 0][:90]
        treatment = [row for row in rows if row["assigned_treatment"] == 1][:10]
        repeated = control + [dict(row) for row in treatment for _ in range(9)]
        for row in repeated:
            row["assignment_period"] = "period-1"
        report = experiment_integrity_report(
            repeated, default_metric_contract(), case_experiment_metadata("C")
        )
        self.assertFalse(report["checks"]["srm"]["passed"])
        self.assertEqual(report["checks"]["srm"]["observed"], {"0": 90, "1": 10})
        stability = report["checks"]["allocation_stability"]
        self.assertFalse(stability["passed"])
        self.assertEqual(
            stability["periods"]["period-1"]["arm_counts"], {"0": 90, "1": 10}
        )
        self.assertEqual(stability["randomization_unit_count"], 100)
        self.assertEqual(stability["raw_row_count"], 180)

    def test_confirmation_requires_a_complete_normalized_command(self) -> None:
        session_id = "confirmation-regression"
        reset_session(session_id)
        self.assertEqual(handle_message(session_id, "line_a")["stage"], "confirm")
        self.assertEqual(handle_message(session_id, "不好")["stage"], "clarify")

        reset_session(session_id)
        self.assertEqual(handle_message(session_id, "line_a")["stage"], "confirm")
        with patch(
            "attribution.agent_chat.run_scenario",
            return_value={"metrics": {}, "evidence_pointer": "test"},
        ) as runner:
            result = handle_message(session_id, "ＯＫ！")
        self.assertEqual(result["stage"], "done")
        runner.assert_called_once()

    def test_console_uses_current_api_contract_for_all_scenarios(self) -> None:
        html = (
            Path(__file__).resolve().parents[1]
            / "web"
            / "static"
            / "semifinal-demo.html"
        ).read_text(encoding="utf-8")
        self.assertIn("/api/attribution/chat", html)
        self.assertIn("/api/attribution/scenario-run", html)
        self.assertNotIn("/api/track2/", html)
        self.assertIn("experience:'EXPERIENCE_ABLATION'", html)
        self.assertIn("经验库跨期学习与错配报警", html)

    def test_experience_scenario_uses_current_trajectory_schema(self) -> None:
        fixture = {
            "static_baseline": {"ate_rmse_sparse": 0.2, "ate_rmse_rich": 0.1},
            "adaptive_experience_store": {
                "ate_rmse_sparse": 0.1,
                "ate_rmse_rich": 0.2,
                "mismatch_alarm": {"fired_periods": [601]},
                "shrinkage_strength_trajectory": [500.0, 510.0],
            },
            "store_final": {},
            "note": "fixture",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "attribution.experience_benchmark.run_experience_ablation",
                return_value=fixture,
            ),
        ):
            result = _scenario_experience(Path(directory))
        self.assertEqual(
            result["metrics"]["shrinkage_strength_trajectory"], [500.0, 510.0]
        )


if __name__ == "__main__":
    unittest.main()
