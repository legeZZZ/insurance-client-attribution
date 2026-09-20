import copy
import unittest

import numpy as np

from track2_v5.causal_discovery import discover_causal_graph, graph_variables
from track2_v5.identification import REQUIREMENTS, identify_effect
from track2_v5.quant_track import estimate_randomized_effect


def metric():
    return {
        "name": "conversion",
        "numerator": "converted_users",
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


def rows(seed=1):
    rng = np.random.default_rng(seed)
    return [
        {
            "unit_id": i,
            "cluster": i // 4,
            "treatment": (i // 4) % 2,
            "x": float(x),
            "outcome": int(y),
        }
        for i, (x, y) in enumerate(
            zip(rng.normal(size=400), rng.binomial(1, 0.3, size=400))
        )
    ]


def estimate(data, **kwargs):
    settings = dict(
        assignment_ref="experiment:pre_registered",
        randomized=True,
        observed_through=11,
        no_interference_ref="design:separated_users",
        cluster_column="cluster",
    )
    settings.update(kwargs)
    return estimate_randomized_effect(data, metric(), **settings)


class GraphTests(unittest.TestCase):
    def test_protected_variables_and_parent_views_survive(self):
        self.assertEqual(
            graph_variables(["x.velocity"], ["u"], ["m"], {"x.velocity": "x"}),
            ["m", "u", "x"],
        )
        with self.assertRaises(ValueError):
            graph_variables(["x"], [], [], {"x": "y", "y": "x"})

    def test_real_pcmciplus_and_lpcmci_run_and_preserve_endpoints(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=150)
        y = np.roll(x, 1) + rng.normal(size=150) * 0.2
        r = discover_causal_graph(
            list(range(150)),
            {"x": x.tolist(), "y": y.tolist()},
            screened_candidates=["y"],
            protected_covariates=["x"],
            tau_max=1,
            response_window_basis="known one-day lag",
            max_condition_dim=1,
        )
        self.assertEqual([v["algorithm"] for v in r["runs"]], ["PCMCI+", "LPCMCI"])
        self.assertTrue(
            any(
                e["source"] == "x" and e["target"] == "y" and e["lag"] == 1
                for e in r["runs"][0]["edges"]
            )
        )
        self.assertFalse(r["causal_effect_allowed"])
        self.assertTrue(r["ambiguities"])

    def test_deterministic_composition_and_short_data_rejected(self):
        kwargs = dict(
            screened_candidates=["x", "y"], tau_max=1, response_window_basis="one day"
        )
        x = np.linspace(0, 1, 50)
        r = discover_causal_graph(
            list(range(50)), {"x": x.tolist(), "y": (1 - x).tolist()}, **kwargs
        )
        self.assertEqual(r["reason_codes"], ["MODEL_MISMATCH"])
        r = discover_causal_graph(
            list(range(10)),
            {"x": x[:10].tolist(), "y": (x[:10] ** 2).tolist()},
            **kwargs,
        )
        self.assertEqual(r["reason_codes"], ["INSUFFICIENT_POWER"])


class IdentificationTests(unittest.TestCase):
    def identify(self, design="DiD", **kwargs):
        checks = {
            name: {"status": "supported", "evidence_refs": [name]}
            for name in [
                "data_valid",
                "outcome_mature",
                "support_overlap",
                *REQUIREMENTS[design],
            ]
        }
        settings = dict(
            treatment="x",
            outcome="y",
            design=design,
            checks=checks,
            data_digest="input:1",
            target_population="users",
        )
        settings.update(kwargs)
        return identify_effect(**settings)

    def test_missing_evidence_never_implies_identification(self):
        r = self.identify(checks={})
        self.assertEqual(r["status"], "NOT_IDENTIFIED")
        self.assertTrue(r["supplemental_evidence_needed"])

    def test_mediator_adjustment_rejected_and_audited(self):
        r = self.identify(adjustment_set=["m"], feature_roles={"m": "mediator"})
        self.assertEqual(r["rejected_adjustments"], ["m"])
        self.assertEqual(r["status"], "NOT_IDENTIFIED")

    def test_gcm_requires_accepted_dag_not_pag(self):
        cyclic = {"nodes": ["x", "y"], "edges": [["x", "y"], ["y", "x"]]}
        self.assertIn(
            "GRAPH_AMBIGUOUS", self.identify("GCM", accepted_dag=cyclic)["reason_codes"]
        )
        dag = {"nodes": ["x", "y"], "edges": [["x", "y"]]}
        self.assertEqual(self.identify("GCM", accepted_dag=dag)["status"], "IDENTIFIED")

    def test_single_series_and_simultaneous_events_do_not_identify_individual_effects(
        self,
    ):
        self.assertEqual(self.identify("ITS")["status"], "NOT_IDENTIFIED")
        self.assertEqual(
            self.identify(simultaneous_interventions=["x", "z"])["status"],
            "NOT_IDENTIFIED",
        )
        self.assertEqual(
            self.identify(
                simultaneous_interventions=["x", "z"], requested_effect="bundle"
            )["status"],
            "IDENTIFIED",
        )


class TrackATests(unittest.TestCase):
    def test_failed_randomization_or_maturity_has_no_numeric_effect(self):
        for override in (
            {"randomized": False},
            {"observed_through": 10},
            {"no_interference_ref": None},
        ):
            r = estimate(rows(), **override)
            self.assertEqual(r["status"], "REFUSED")
            self.assertIsNone(r["contracts"]["EffectEstimate"]["estimate"])

    def test_group_assignment_conflict_and_srm_fail_closed(self):
        data = rows()
        data[0]["treatment"] = 1
        self.assertEqual(estimate(data)["status"], "REFUSED")
        data = rows()
        for row in data:
            row["treatment"] = int(row["cluster"] < 95)
        self.assertEqual(estimate(data)["status"], "REFUSED")

    def test_all_three_estimators_run_with_cluster_disjoint_crossfitting(self):
        for method in ("ITT", "CUPAC", "AIPW"):
            kwargs = dict(method=method)
            if method != "ITT":
                kwargs.update(features=["x"], feature_roles={"x": "pre_treatment"})
            r = estimate(rows(), **kwargs)
            self.assertEqual(r["status"], "ESTIMATED")
            e = r["contracts"]["EffectEstimate"]
            self.assertLessEqual(e["interval"][0], e["estimate"])
            self.assertGreaterEqual(e["interval"][1], e["estimate"])
            for fold in e["diagnostics"].get("crossfit", {}).get("folds", []):
                self.assertFalse(
                    set(fold["training_group_indices"])
                    & set(fold["evaluation_group_indices"])
                )

    def test_post_treatment_feature_is_blocked_before_fit(self):
        r = estimate(
            rows(), method="AIPW", features=["x"], feature_roles={"x": "post_treatment"}
        )
        self.assertEqual(r["status"], "REFUSED")
        self.assertIsNone(r["contracts"]["EffectEstimate"]["interval"])

    def test_duplicate_analysis_unit_rejected(self):
        data = rows()
        data.append(copy.deepcopy(data[0]))
        with self.assertRaises(ValueError):
            estimate(data)


if __name__ == "__main__":
    unittest.main()
