import copy
import unittest

import numpy as np

from track2_v5.observational_tracks import _gaussian_forecast
from track2_v5.quant_track import estimate_controlled_series_effect, estimate_did_effect


def metric(start=50, end=54, unit="currency"):
    return {
        "name": "revenue",
        "numerator": "revenue",
        "denominator": None,
        "aggregation": "sum",
        "unit": unit,
        "analysis_unit": "unit",
        "target_population": "treated units",
        "timezone": "UTC",
        "window": [start, end],
        "maturity_days": 2,
        "deduplication": "unit/day",
    }


def did_fixture(seed=7, effect=2):
    rng = np.random.default_rng(seed)
    data = []
    for u in range(40):
        for day in range(55):
            treated = u < 20 and day >= 50
            data.append(
                {
                    "unit_id": str(u),
                    "day": day,
                    "treatment": int(treated),
                    "outcome": float(
                        10
                        + u / 20
                        + 0.1 * day
                        + rng.normal(scale=0.05)
                        + effect * treated
                    ),
                }
            )
    settings = {
        "rows": data,
        "metric_contract": metric(),
        "intervention_day": 50,
        "observed_through": 56,
        "control_eligibility": {
            str(u): {
                "eligible": True,
                "unaffected": True,
                "evidence_ref": "design:never exposed",
            }
            for u in range(20, 40)
        },
        "no_anticipation_ref": "audit:no early exposure",
        "no_differential_shock_ref": "design:common shocks",
        "parallel_trends_ref": "design:stable group relationship",
        "trend_tolerance": 0.3,
        "independent_units_ref": "design:independent units",
    }
    return settings


def series_fixture(method="SCM", seed=12):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=55) * 2 + 10
    z = rng.normal(size=55)
    controls = {"c1": (x + z).tolist(), "c2": (x - z).tolist(), "c3": x.tolist()}
    y = x + rng.normal(scale=0.01, size=55)
    y[50:] += 2
    return {
        "days": list(range(55)),
        "outcome": y.tolist(),
        "controls": controls,
        "metric_contract": metric(),
        "method": method,
        "intervention_day": 50,
        "observed_through": 56,
        "control_eligibility": {
            name: {
                "eligible": True,
                "unaffected": True,
                "evidence_ref": "design:" + name,
            }
            for name in controls
        },
        "backtest_rmse_limit": 0.5,
        "relationship_ref": "design:stable",
        "no_spillover_ref": "design:no spillover",
        "prefit_rmse_limit": 0.1,
        "loo_effect_limit": 0.2,
        "max_weight": 0.7,
        "bootstrap_samples": 199,
        "block_length": 2,
        "observation_variance": 0.0001,
        "level_variance": 0.00001,
        "prior_variance": 1000,
    }


class DiDTests(unittest.TestCase):
    def test_known_effect_scale_and_twenty_unique_placebos(self):
        result = estimate_did_effect(**did_fixture())
        self.assertEqual(result["status"], "ESTIMATED")
        effect = result["contracts"]["EffectEstimate"]
        self.assertAlmostEqual(effect["estimate"], 200, delta=3)
        self.assertEqual(effect["diagnostics"]["scale_multiplier"], 100)
        runs = effect["diagnostics"]["time_placebos"]["runs"]
        self.assertEqual(len(runs), 20)
        self.assertEqual(len({r["day"] for r in runs}), 20)
        self.assertTrue(all(r["day"] + 5 <= 50 for r in runs))

    def test_staggered_adoption_and_switching_are_not_common_did(self):
        for mode in ("late", "switch"):
            request = did_fixture()
            for row in request["rows"]:
                if row["unit_id"] == "0" and row["day"] == (
                    50 if mode == "late" else 53
                ):
                    row["treatment"] = 0
            result = estimate_did_effect(**request)
            self.assertEqual(result["status"], "REFUSED")
            self.assertIn(
                "rollout_design_compatible",
                result["contracts"]["IdentificationReport"][
                    "supplemental_evidence_needed"
                ],
            )
            self.assertIsNone(result["contracts"]["EffectEstimate"]["estimate"])

    def test_nonparallel_trends_rejected(self):
        request = did_fixture()
        for row in request["rows"]:
            if int(row["unit_id"]) < 20:
                row["outcome"] += 0.2 * row["day"]
        result = estimate_did_effect(**request)
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn(
            "parallel_trends",
            result["contracts"]["IdentificationReport"]["supplemental_evidence_needed"],
        )

    def test_missing_assumption_and_contamination_fail_closed(self):
        for key in (
            "parallel_trends_ref",
            "independent_units_ref",
            "no_anticipation_ref",
            "no_differential_shock_ref",
        ):
            request = did_fixture()
            request[key] = None
            self.assertEqual(estimate_did_effect(**request)["status"], "REFUSED")
        request = did_fixture()
        request["control_eligibility"]["20"]["unaffected"] = False
        self.assertEqual(estimate_did_effect(**request)["status"], "REFUSED")

    def test_duplicate_missing_and_nonbinary_rate_rejected(self):
        for transform in (lambda r: r.append(copy.deepcopy(r[0])), lambda r: r.pop()):
            request = did_fixture()
            transform(request["rows"])
            with self.assertRaises(ValueError):
                estimate_did_effect(**request)
        request = did_fixture()
        request["metric_contract"].update(
            unit="rate", denominator="users", aggregation="ratio_of_sums"
        )
        with self.assertRaises(ValueError):
            estimate_did_effect(**request)

    def test_no_postperiod_data_leak_in_trend_or_placebos(self):
        request = did_fixture()
        before = estimate_did_effect(**request)["contracts"]["EffectEstimate"]
        for row in request["rows"]:
            if row["treatment"]:
                row["outcome"] += 100
        after = estimate_did_effect(**request)["contracts"]["EffectEstimate"]
        for key in ("preperiod_event_study", "time_placebos"):
            self.assertEqual(before["diagnostics"][key], after["diagnostics"][key])
        self.assertAlmostEqual(after["estimate"] - before["estimate"], 10000)


class ControlledSeriesTests(unittest.TestCase):
    def test_controls_must_improve_out_of_sample_predictions(self):
        for method in ("SCM", "BSTS"):
            request = series_fixture(method)
            request["min_backtest_gain"] = 1000
            result = estimate_controlled_series_effect(**request)
            self.assertEqual(result["status"], "REFUSED")
            self.assertIn(
                "control_predictive_gain",
                result["contracts"]["IdentificationReport"][
                    "supplemental_evidence_needed"
                ],
            )

    def test_scm_short_effect_uses_longer_heldout_residual_window(self):
        result = estimate_controlled_series_effect(**series_fixture())
        diag = result["contracts"]["EffectEstimate"]["diagnostics"]
        self.assertEqual(diag["backtest"]["window"], [30, 49])
        self.assertEqual(len(diag["backtest"]["prediction"]), 20)

    def test_scm_recovers_known_total_and_convex_weights(self):
        result = estimate_controlled_series_effect(**series_fixture())
        self.assertEqual(result["status"], "ESTIMATED")
        effect = result["contracts"]["EffectEstimate"]
        self.assertAlmostEqual(effect["estimate"], 10, delta=0.1)
        diag = effect["diagnostics"]
        weights = list(diag["weights"].values())
        self.assertAlmostEqual(sum(weights), 1)
        self.assertTrue(all(w >= 0 for w in weights))
        self.assertEqual(len(diag["leave_one_out"]), 3)
        self.assertEqual(diag["time_placebos"]["executed"], 20)

    def test_bsts_actual_state_and_joint_covariance(self):
        result = estimate_controlled_series_effect(**series_fixture("BSTS"))
        self.assertEqual(result["status"], "ESTIMATED")
        effect = result["contracts"]["EffectEstimate"]
        self.assertAlmostEqual(effect["estimate"], 10, delta=0.1)
        joint = np.asarray(effect["diagnostics"]["counterfactual_joint_covariance"])
        self.assertGreater(joint.sum(), np.trace(joint))
        self.assertGreaterEqual(np.linalg.eigvalsh(joint).min(), 0)

    def test_gaussian_filter_matches_closed_form_constant_model(self):
        y = np.array([1.0, 2.0, 3.0])
        prediction, covariance, _ = _gaussian_forecast(
            y, np.empty((3, 0)), np.empty((2, 0)), 2.0, 0.0, 4.0
        )
        posterior_var = 1 / (1 / 4 + 3 / 2)
        posterior_mean = posterior_var * y.sum() / 2
        np.testing.assert_allclose(prediction, posterior_mean)
        np.testing.assert_allclose(
            covariance, np.full((2, 2), posterior_var) + np.eye(2) * 2
        )

    def test_postperiod_outcomes_never_train_models_or_placebos(self):
        for method in ("SCM", "BSTS"):
            request = series_fixture(method)
            first = estimate_controlled_series_effect(**request)["contracts"][
                "EffectEstimate"
            ]
            request["outcome"][50:] = [v + 3 for v in request["outcome"][50:]]
            second = estimate_controlled_series_effect(**request)["contracts"][
                "EffectEstimate"
            ]
            for key in ("counterfactual", "time_placebos", "backtest"):
                self.assertEqual(first["diagnostics"][key], second["diagnostics"][key])
            self.assertAlmostEqual(second["estimate"] - first["estimate"], 15)

    def test_contaminated_control_and_missing_relationship_refuse(self):
        for method in ("SCM", "BSTS"):
            request = series_fixture(method)
            request["control_eligibility"]["c1"]["unaffected"] = False
            result = estimate_controlled_series_effect(**request)
            self.assertEqual(result["status"], "REFUSED")
            self.assertIn(
                "CONTROL_CONTAMINATED",
                result["contracts"]["IdentificationReport"]["reason_codes"],
            )
            self.assertIsNone(result["contracts"]["EffectEstimate"]["interval"])
            request = series_fixture(method)
            request["relationship_ref"] = None
            self.assertEqual(
                estimate_controlled_series_effect(**request)["status"], "REFUSED"
            )

    def test_scm_prefit_loo_and_concentration_gates_are_executed(self):
        for key, value, requirement in (
            ("max_weight", 0.1, "weight_concentration_acceptable"),
            ("prefit_rmse_limit", 0.0, "preperiod_fit"),
            ("loo_effect_limit", 0.0, "leave_one_out_stable"),
            ("backtest_rmse_limit", 0.0, "preperiod_backtest"),
        ):
            request = series_fixture()
            request[key] = value
            result = estimate_controlled_series_effect(**request)
            self.assertEqual(result["status"], "REFUSED")
            self.assertIn(
                requirement,
                result["contracts"]["IdentificationReport"][
                    "supplemental_evidence_needed"
                ],
            )

    def test_bsts_hyperparameters_invalid_and_bad_backtest(self):
        request = series_fixture("BSTS")
        request["observation_variance"] = -1
        with self.assertRaises(ValueError):
            estimate_controlled_series_effect(**request)
        request = series_fixture("BSTS")
        request["outcome"][45:50] = [v + 50 for v in request["outcome"][45:50]]
        result = estimate_controlled_series_effect(**request)
        self.assertEqual(result["status"], "REFUSED")

    def test_simultaneous_events_require_bundle_and_maturity_is_enforced(self):
        for function, request in (
            (estimate_did_effect, did_fixture()),
            (estimate_controlled_series_effect, series_fixture()),
        ):
            request["simultaneous_interventions"] = ["price", "promotion"]
            self.assertEqual(function(**request)["status"], "REFUSED")
            request["requested_effect"] = "bundle"
            self.assertEqual(function(**request)["status"], "ESTIMATED")
            request["observed_through"] = 55
            self.assertEqual(function(**request)["status"], "REFUSED")

    def test_misaligned_windows_missing_dates_ratio_inputs_refused(self):
        for mutation in (
            lambda r: r["days"].__setitem__(2, 4),
            lambda r: r["metric_contract"]["window"].__setitem__(0, 49),
            lambda r: r["metric_contract"].update(
                unit="rate", aggregation="ratio_of_sums", denominator="visits"
            ),
        ):
            request = series_fixture()
            mutation(request)
            with self.assertRaises(ValueError):
                estimate_controlled_series_effect(**request)

    def test_short_preperiod_reports_actual_placebo_count(self):
        request = series_fixture("BSTS")
        request["days"] = request["days"][35:]
        request["outcome"] = request["outcome"][35:]
        request["controls"] = {
            n: values[35:] for n, values in request["controls"].items()
        }
        result = estimate_controlled_series_effect(**request)
        placebos = result["contracts"]["EffectEstimate"]["diagnostics"]["time_placebos"]
        self.assertEqual(placebos["executed"], 6)
        self.assertIsNone(placebos["formal_pvalue"])


if __name__ == "__main__":
    unittest.main()
