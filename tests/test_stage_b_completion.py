import copy
import unittest

import numpy as np
from test_causal_graph_and_tracks import metric as rct_metric
from test_causal_graph_and_tracks import rows as rct_rows
from test_observational_tracks import did_fixture, metric, series_fixture

from track2_v5.action_interface import (
    decide_action,
    evaluate_checkpoint,
    propose_experiment,
    register_sequential_policy,
)
from track2_v5.association_discovery import discover_association_factors
from track2_v5.experiment_designer import design_experiment
from track2_v5.gcm_track import estimate_gcm_effect
from track2_v5.observational_extensions import (
    apply_negative_controls,
    estimate_bsts_mixture,
    estimate_ratio_series,
    estimate_staggered_did,
    run_negative_control_suite,
)
from track2_v5.observational_tracks import estimate_controlled_series_effect
from track2_v5.quant_track import estimate_randomized_effect
from track2_v5.randomized_extensions import (
    estimate_causal_forest,
    estimate_ratio_effect,
)


def random_design():
    return dict(
        assignment_ref="fixed randomization",
        randomized=True,
        observed_through=11,
        no_interference_ref="independent groups",
        cluster_column="cluster",
    )


def gcm_request(seed=44):
    rng = np.random.default_rng(seed)
    frames = []
    for shift in (0, 0.5):
        x = rng.normal(size=100) + shift
        y = 2 * x + rng.normal(scale=0.1, size=100)
        frames.append([{"x": float(a), "revenue": float(b)} for a, b in zip(x, y)])
    return {
        "old_rows": frames[0],
        "new_rows": frames[1],
        "metric_contract": metric(),
        "accepted_dag": {"nodes": ["x", "revenue"], "edges": [["x", "revenue"]]},
        "treatment": "x",
        "treatment_reference": 0.0,
        "treatment_alternative": 1.0,
        "causal_sufficiency_ref": "synthetic DAG",
        "independent_rows_ref": "iid rows",
        "mechanism_rmse_limits": {"revenue": 0.3},
        "bootstrap_samples": 20,
        "simulation_samples": 200,
        "observed_through": 56,
    }


class StatisticalCompletionTests(unittest.TestCase):
    def test_max_t_confirmation_preserves_duplicate_factor_dependence(self):
        x = np.random.default_rng(6).normal(size=140).tolist()
        days = list(range(140))
        r = discover_association_factors(
            days,
            x,
            [],
            factor_series=[
                {"factor_id": f"x{i}", "days": days, "values": x} for i in range(3)
            ],
            discovery_days=days[:70],
            holdout_days=days[80:],
            max_lag=0,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=99,
            confirmation_max_t_threshold=2,
        )
        self.assertEqual(r["search_manifest"]["confirmation_correction"], "max_t")
        self.assertEqual(r["test_family_contract"]["correction"], "max_t")
        self.assertEqual(
            len({c["holdout"]["adjusted_pvalue"] for c in r["candidates"]}), 1
        )
        self.assertTrue(all(c["holdout"]["survives"] for c in r["candidates"]))

    def test_cuped_uses_training_only_covariate_adjustment(self):
        result = estimate_randomized_effect(
            rct_rows(),
            rct_metric(),
            method="CUPED",
            features=["x"],
            feature_roles={"x": "pre_treatment"},
            **random_design(),
        )
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertIn(
            "CUPED",
            result["contracts"]["EffectEstimate"]["diagnostics"]["crossfit"][
                "nuisance_model"
            ],
        )
        with self.assertRaises(ValueError):
            estimate_randomized_effect(
                rct_rows(), rct_metric(), method="CUPED", **random_design()
            )

    def test_ratio_itt_matches_ratio_of_sums_not_mean_ratios(self):
        data = rct_rows()
        for r in data:
            r.update(numerator=r["outcome"], denominator=1 + r["unit_id"] % 3)
        result = estimate_ratio_effect(data, rct_metric(), **random_design())
        self.assertEqual(result["status"], "ESTIMATED")
        ratios = [
            sum(r["numerator"] for r in data if r["treatment"] == arm)
            / sum(r["denominator"] for r in data if r["treatment"] == arm)
            for arm in (0, 1)
        ]
        self.assertAlmostEqual(
            result["contracts"]["EffectEstimate"]["estimate"], ratios[1] - ratios[0]
        )
        for r in data:
            r.update(numerator=0, denominator=0)
        self.assertEqual(
            estimate_ratio_effect(data, rct_metric(), **random_design())["status"],
            "REFUSED",
        )

    def test_real_honest_forest_and_post_treatment_refusal(self):
        rng = np.random.default_rng(4)
        data = rct_rows()
        for r in data:
            r["x"] = float(r["cluster"] % 10) / 10
            r["outcome"] = int(rng.random() < 0.1 + 0.7 * r["x"] * r["treatment"])
        result = estimate_causal_forest(
            data,
            rct_metric(),
            features=["x"],
            feature_roles={"x": "pre_treatment"},
            query_features=[[0.1], [0.8]],
            n_estimators=40,
            **random_design(),
        )
        self.assertEqual(result["challenger"], "EconML_CausalForestDML")
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertTrue(result["contracts"]["EffectEstimate"]["diagnostics"]["honest"])
        rejected = estimate_causal_forest(
            data,
            rct_metric(),
            features=["x"],
            feature_roles={"x": "post_treatment"},
            query_features=[[0.1]],
            n_estimators=40,
            **random_design(),
        )
        self.assertEqual(rejected["status"], "REFUSED")


class ObservationalCompletionTests(unittest.TestCase):
    def test_negative_control_suite_executes_the_estimator(self):
        primary = estimate_controlled_series_effect(**series_fixture())
        negative = series_fixture()
        negative["outcome"][50:] = [v - 2 for v in negative["outcome"][50:]]
        result = run_negative_control_suite(
            primary,
            negative_requests=[
                {
                    "operation": "series",
                    "parameters": negative,
                    "tolerance": 0.2,
                    "prespecified_ref": "independent negative outcome",
                }
            ],
        )
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertEqual(len(result["negative_control_runs"]), 1)
        self.assertLess(
            abs(
                result["negative_control_runs"][0]["contracts"]["EffectEstimate"][
                    "estimate"
                ]
            ),
            0.1,
        )

    def test_staggered_cohorts_and_shared_controls_recover_total(self):
        req = did_fixture()
        for r in req["rows"]:
            if int(r["unit_id"]) < 10 and 50 <= r["day"] < 52:
                r["treatment"] = 0
                r["outcome"] -= 2
        req.pop("intervention_day")
        result = estimate_staggered_did(**req)
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertAlmostEqual(
            result["contracts"]["EffectEstimate"]["estimate"], 160, delta=3
        )
        self.assertEqual(
            len(result["contracts"]["EffectEstimate"]["diagnostics"]["cohort_reports"]),
            2,
        )
        req["rows"][0]["treatment"] = 1
        with self.assertRaises(ValueError):
            estimate_staggered_did(**req)

    def test_hyperparameter_posterior_uses_preperiod_only(self):
        req = series_fixture("BSTS")
        grid = [
            {
                "observation_variance": r,
                "level_variance": 0.00001,
                "prior_variance": 1000,
                "prior_mass": 1.0,
            }
            for r in (0.0001, 0.001)
        ]
        before = estimate_bsts_mixture(hyperparameter_grid=grid, **req)
        self.assertEqual(before["status"], "ESTIMATED")
        for i in range(50, 55):
            req["outcome"][i] += 20
        after = estimate_bsts_mixture(hyperparameter_grid=grid, **req)
        a, b = (v["contracts"]["EffectEstimate"] for v in (before, after))
        self.assertEqual(
            a["diagnostics"]["posterior_weights"], b["diagnostics"]["posterior_weights"]
        )
        self.assertAlmostEqual(sum(a["diagnostics"]["posterior_weights"]), 1)
        self.assertAlmostEqual(b["estimate"] - a["estimate"], 100)

    def test_ratio_series_preserves_scale_and_denominator(self):
        req = series_fixture("SCM")
        num, controls, eligibility = (
            req.pop("outcome"),
            req.pop("controls"),
            req.pop("control_eligibility"),
        )
        den = [100 + x for x in controls["c3"]]
        dc = {k: [100 + v for v in values] for k, values in controls.items()}
        met = req.pop("metric_contract")
        met.update(unit="rate", aggregation="ratio_of_sums", denominator="exposure")
        result = estimate_ratio_series(
            numerator=num,
            denominator=den,
            numerator_controls=controls,
            denominator_controls=dc,
            numerator_eligibility=eligibility,
            denominator_eligibility=eligibility,
            metric_contract=met,
            **req,
        )
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertAlmostEqual(
            result["contracts"]["EffectEstimate"]["estimate"], 2 / 110, delta=0.002
        )
        self.assertTrue(
            result["contracts"]["EffectEstimate"]["diagnostics"][
                "paired_residual_blocks"
            ]
        )

    def test_negative_control_equivalence_failure_blocks_numeric_effect(self):
        source = estimate_controlled_series_effect(**series_fixture())
        bad = apply_negative_controls(
            source,
            checks=[
                {
                    "estimate": 1.0,
                    "interval": [0.5, 1.5],
                    "tolerance": 0.1,
                    "evidence_ref": "negative run",
                    "prespecified_ref": "design",
                }
            ],
        )
        self.assertEqual(bad["status"], "REFUSED")
        self.assertIsNone(bad["contracts"]["EffectEstimate"]["estimate"])


class GCMCompletionTests(unittest.TestCase):
    def test_collinear_parent_mechanisms_cannot_be_attributed(self):
        req = gcm_request()
        for rows in (req["old_rows"], req["new_rows"]):
            for row in rows:
                row["duplicate"] = row["x"]
        req["accepted_dag"]["nodes"].append("duplicate")
        req["accepted_dag"]["edges"].append(["duplicate", "revenue"])
        result = estimate_gcm_effect(**req)
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn(
            "MODEL_MISMATCH",
            result["contracts"]["IdentificationReport"]["reason_codes"],
        )

    def test_real_gcm_ate_and_shapley_are_separate(self):
        result = estimate_gcm_effect(**gcm_request())
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertAlmostEqual(
            result["contracts"]["EffectEstimate"]["estimate"], 2, delta=0.2
        )
        self.assertIsNotNone(result["mechanism_attribution"]["shapley_values"])
        self.assertEqual(len(result["mechanism_attribution"]["bootstrap_runs"]), 20)

    def test_cyclic_graph_and_missing_assumptions_refuse(self):
        for mutation in (
            lambda r: r["accepted_dag"]["edges"].append(["revenue", "x"]),
            lambda r: r.update(causal_sufficiency_ref=None),
            lambda r: r.update(treatment_alternative=100),
        ):
            req = gcm_request()
            mutation(req)
            result = estimate_gcm_effect(**req)
            self.assertEqual(result["status"], "REFUSED")
            self.assertIsNone(result["mechanism_attribution"]["shapley_values"])


class ActionCompletionTests(unittest.TestCase):
    def test_preregistered_success_and_harm_stop_further_looks(self):
        policy = register_sequential_policy(
            metric_names=["primary", "harm"],
            checkpoints=[7, 14],
            minimum_units=100,
            deadline=14,
            stopping_rules={
                "primary": "primary",
                "threshold": 0.01,
                "guardrail_limits": {"harm": 0.05},
            },
        )
        samples = {
            "primary": {
                "control": {"n": 100000, "sum": 10000},
                "treatment": {"n": 100000, "sum": 50000},
            },
            "harm": {
                "control": {"n": 100000, "sum": 0},
                "treatment": {"n": 100000, "sum": 0},
            },
        }
        result = evaluate_checkpoint(policy, day=7, observed_through=7, samples=samples)
        self.assertEqual(result["decision"], "STOP_SUCCESS")
        with self.assertRaises(ValueError):
            evaluate_checkpoint(
                policy,
                day=14,
                observed_through=14,
                samples=samples,
                state=result["state"],
            )
        samples["harm"]["treatment"]["sum"] = 20000
        result = evaluate_checkpoint(policy, day=7, observed_through=7, samples=samples)
        self.assertEqual(result["decision"], "STOP_HARM")

    def test_fractional_interaction_aliases_and_resolution(self):
        design = design_experiment(["a", "b", "c", "d"])
        diag = design["design_diagnostics"]
        self.assertFalse(diag["second_order_jointly_identifiable"])
        self.assertTrue(
            any(
                {p["left"], p["right"]} == {"a:b", "c:d"}
                for p in diag["all_interaction_aliases"]
            )
        )
        self.assertEqual(
            design_experiment(list("abcde"))["design_diagnostics"]["resolution"], 5
        )
        self.assertEqual(
            sum(
                a["planned_impressions"]
                for a in design_experiment(["a", "b"], traffic_budget=101)["arms"]
            ),
            101,
        )
        with self.assertRaises(ValueError):
            design_experiment(["a", "b"], traffic_budget=3)

    def test_sample_size_increases_with_clustering_and_unequal_split(self):
        settings = dict(metric_contract=rct_metric(), mde=0.05, baseline_variance=0.25)
        a = propose_experiment(**settings)
        b = propose_experiment(**settings, cluster_size=10, icc=0.2, allocation=0.2)
        self.assertGreater(b["planned_units"], a["planned_units"])
        self.assertTrue(b["requires_approval_before_activation"])

    def test_checkpoint_maturity_schedule_counts_and_deadline(self):
        policy = register_sequential_policy(
            metric_names=["primary", "harm"],
            checkpoints=[7, 14],
            minimum_units=100,
            deadline=14,
            maturity_days=2,
        )
        samples = {
            name: {
                "control": {"n": 1000, "sum": 200},
                "treatment": {"n": 1000, "sum": 250},
            }
            for name in ("primary", "harm")
        }
        first = evaluate_checkpoint(policy, day=7, observed_through=8, samples=samples)
        self.assertIsNone(first["metrics"]["primary"]["interval"])
        with self.assertRaises(ValueError):
            evaluate_checkpoint(
                policy, day=7, observed_through=9, samples=samples, state=first["state"]
            )
        final = evaluate_checkpoint(
            policy, day=14, observed_through=16, samples=samples, state=first["state"]
        )
        self.assertEqual(final["status"], "DEADLINE")
        self.assertIsNotNone(final["metrics"]["primary"]["interval"])
        corrupt = copy.deepcopy(policy)
        corrupt["alpha"] = 0.99
        with self.assertRaises(ValueError):
            evaluate_checkpoint(corrupt, day=14, observed_through=16, samples=samples)

    def test_joint_guardrails_require_safety_and_identification(self):
        result = estimate_controlled_series_effect(**series_fixture())
        settings = dict(
            practical_threshold=0.0,
            business_value_per_unit=1.0,
            exposure=100.0,
            implementation_cost=1.0,
            guardrails={
                "harm": {
                    "max_harm": 0.1,
                    "interval": [-0.01, 0.01],
                    "simultaneous_evidence_ref": "registered family",
                }
            },
        )
        self.assertEqual(
            decide_action(result["contracts"], **settings)["action"], "LAUNCH_PROPOSAL"
        )
        settings["guardrails"]["harm"]["interval"] = None
        self.assertEqual(
            decide_action(result["contracts"], **settings)["action"], "COLLECT_EVIDENCE"
        )
        settings["guardrails"]["harm"]["interval"] = [0.2, 0.3]
        self.assertEqual(
            decide_action(result["contracts"], **settings)["action"],
            "ROLLBACK_PROPOSAL",
        )


if __name__ == "__main__":
    unittest.main()
