"""Stage A regression cases exercise the review failures, not static snapshots."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from track2_v5 import scenario_reports as sr
from track2_v5.adapters import DataSourceConfig, load_config, load_line_b_inputs
from track2_v5.baseline_attribution import attribute_baseline
from track2_v5.contracts import ContractError, validate_bundle, validate_contract
from track2_v5.data_contract import validate_rows
from track2_v5.factor_registry import FactorRegistry
from track2_v5.human_feedback import HumanFeedbackStore
from track2_v5.skill_evolution import SkillStore, _digest, analyze_traces, evolve_skill
from track2_v5.watchlist_scan import falsify


def metric():
    return dict(
        name="ctr",
        numerator="click",
        denominator="impression",
        aggregation="ratio_of_sums",
        unit="rate",
        analysis_unit="day",
        target_population="eligible_population",
        timezone="UTC",
        window=[0, 19],
        maturity_days=0,
        deduplication="event_id",
    )


def traces(action="a", context=None, **extras):
    return [
        dict(
            trace_id="trace",
            outcome="success",
            context=context or {"x": 1},
            lesson=action,
            **extras,
        )
    ]


def cases(action="a"):
    return [dict(case_id="case", context={"x": 1}, expected_action=action)]


class SkillGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SkillStore(Path(self.tmp.name) / "skills.json")

    def seed(self):
        self.assertTrue(evolve_skill(self.store, "rca", traces(), cases())["promoted"])

    def test_failed_first_candidate_stays_inactive(self):
        r = evolve_skill(self.store, "rca", traces(), cases("b"), min_delta=1)
        self.assertFalse(r["promoted"])
        self.assertIsNone(self.store.active("rca"))
        self.assertIsNone(SkillStore(self.store.path).active("rca"))

    def test_empty_holdout_never_promotes(self):
        self.assertFalse(evolve_skill(self.store, "rca", traces(), [])["promoted"])
        self.assertIsNone(self.store.active("rca"))

    def test_protected_target_rejected_at_all_public_mutators(self):
        for name in [
            "statistical_core",
            "evidence_gates",
            "release_actions",
            "foo.statistical_core",
        ]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    evolve_skill(self.store, name, traces(), cases())
                with self.assertRaises(ValueError):
                    self.store.register(name, analyze_traces(traces()), "bad")
                with self.assertRaises(ValueError):
                    self.store.activate(name, 1, "bad")

    def test_registration_and_direct_activation_cannot_bypass_gate(self):
        self.store.register("rca", analyze_traces(traces()), "candidate")
        self.assertIsNone(self.store.active("rca"))
        with self.assertRaises(ValueError):
            self.store.activate("rca", 1, "bypass")

    def test_failed_or_tampered_candidate_cannot_activate(self):
        self.store.register("rca", analyze_traces(traces()), "candidate")
        self.store.validate_candidate("rca", 1, cases("b"))
        with self.assertRaises(ValueError):
            self.store.activate("rca", 1, "failed")
        self.store.validate_candidate("rca", 1, cases())
        self.store.data["skills"]["rca"]["versions"][0]["rules"][0]["action"] = (
            "changed"
        )
        with self.assertRaises(ValueError):
            self.store.activate("rca", 1, "changed")

    def test_old_rule_conflict_is_reported_not_silently_shadowed(self):
        self.seed()
        r = evolve_skill(self.store, "rca", traces("b"), cases("b"))
        self.assertEqual(r["conflicts_excluded"], 1)
        self.assertFalse(r["promoted"])
        self.assertEqual(self.store.active("rca")["rules"][0]["action"], "a")

    def test_bound_replacement_can_fix_old_rule_and_rollback(self):
        self.seed()
        old = self.store.active("rca")["rules"][0]
        r = evolve_skill(
            self.store, "rca", traces("b", replaces=_digest(old)), cases("b")
        )
        self.assertTrue(r["promoted"])
        self.assertEqual(len(r["replacements"]), 1)
        self.assertEqual(self.store.active("rca")["rules"][0]["action"], "b")
        self.assertEqual(self.store.rollback("rca")["rules"][0]["action"], "a")

    def test_broad_rule_and_narrow_patch_conflict(self):
        self.seed()
        r = evolve_skill(
            self.store, "rca", traces("b", {"x": 1, "region": "east"}), cases("b")
        )
        self.assertFalse(r["promoted"])
        self.assertEqual(r["conflicts_excluded"], 1)

    def test_duplicate_holdout_and_negative_delta_rejected(self):
        with self.assertRaises(ValueError):
            evolve_skill(self.store, "rca", traces(), cases() * 2)
        with self.assertRaises(ValueError):
            evolve_skill(self.store, "rca", traces(), cases(), -1)


class DataAndBaselineTests(unittest.TestCase):
    def test_fractional_days_infinity_and_fractional_counts_rejected(self):
        for day in ["1.9", "Infinity", "nan"]:
            with self.subTest(day=day), self.assertRaises(ContractError):
                validate_rows(
                    "factor_snapshots", [{"factor_id": "f", "day": day, "value": 1}]
                )
        row = dict(
            day=0,
            region="east",
            channel="paid",
            version="v",
            control_clicks=1.5,
            treatment_clicks=2,
            control_impressions=100,
            treatment_impressions=100,
        )
        with self.assertRaises(ContractError):
            validate_rows("metric_panel", [row])

    def test_snapshot_and_readout_duplicates_rejected(self):
        for table, row in [
            ("factor_snapshots", {"factor_id": "f", "day": 0, "value": 1}),
            (
                "experiment_readouts",
                {"experiment_id": "e", "att_estimate": 1, "att_se": 1},
            ),
        ]:
            with self.subTest(table=table), self.assertRaises(ContractError):
                validate_rows(table, [row, row])

    def test_adapter_separates_scopes_and_uses_rate(self):
        from track2_v5 import adapters as ad

        config = load_config(ROOT / "config.example.json")
        original = ad._load_table

        def rows(table, config, *, required):
            if table == "factor_snapshots":
                return [
                    dict(factor_id="f", scope_id=sc, day=d, value=d)
                    for sc in ["east", "west"]
                    for d in range(60)
                ]
            if table == "metric_panel":
                return [
                    dict(
                        day=d,
                        region="east",
                        channel="paid",
                        version="v",
                        control_clicks=100,
                        control_impressions=1000,
                        treatment_clicks=200,
                        treatment_impressions=2000,
                    )
                    for d in range(60)
                ]
            return original(table, config, required=required)

        with patch.object(ad, "_load_table", side_effect=rows):
            result = load_line_b_inputs(config)
        self.assertEqual(len(result["factor_series"]), 2)
        self.assertEqual(result["control"], result["treated"])
        self.assertAlmostEqual(result["control"][0], 0.1)
        self.assertEqual(result["metric_contract"]["unit"], "rate")

    def test_same_experiment_cannot_be_counted_twice(self):
        changes = [
            dict(change_id=c, start_day=0, experiment_id="e") for c in ["a", "b"]
        ]
        with self.assertRaisesRegex(ValueError, "allocation"):
            attribute_baseline(
                range(20),
                [100.0] * 20,
                [110.0] * 20,
                changes,
                [],
                {"e": {"att_estimate": 10, "att_se": 1}},
            )
        for c in changes:
            c["allocation_weight"] = 0.5
        r = attribute_baseline(
            range(20),
            [100.0] * 20,
            [110.0] * 20,
            changes,
            [],
            {"e": {"att_estimate": 10, "att_se": 1}},
        )
        self.assertAlmostEqual(r["series"]["explained_registered"][0], 10)
        self.assertAlmostEqual(r["explained_uncertainty"]["standard_error"][0], 1)

    def test_transfer_contract_coverage_ramp_and_units(self):
        change = dict(
            change_id="a",
            start_day=0,
            end_day=9,
            ramp_days=2,
            experiment_id="e",
            coverage=0.5,
            target_population="eligible_population",
        )
        experiment = dict(
            att_estimate=0.02,
            att_se=0.001,
            unit="rate",
            target_population="eligible_population",
            evidence_ref="evidence",
        )
        r = attribute_baseline(
            range(20),
            [0.1] * 20,
            [0.11] * 20,
            [change],
            [],
            {"e": experiment},
            metric_contract=metric(),
        )
        self.assertAlmostEqual(r["series"]["explained_registered"][0], 0.005)
        self.assertAlmostEqual(r["series"]["explained_registered"][1], 0.01)
        self.assertEqual(r["series"]["explained_registered"][10], 0)
        experiment["unit"] = "count"
        r = attribute_baseline(
            range(20),
            [0.1] * 20,
            [0.11] * 20,
            [change],
            [],
            {"e": experiment},
            metric_contract=metric(),
        )
        self.assertEqual(sum(r["series"]["explained_registered"]), 0)
        self.assertIn("EFFECT_UNIT_MISMATCH", r["transfer_checks"][0]["reason_codes"])

    def test_supplied_shared_covariance_is_propagated(self):
        experiments = {k: dict(att_estimate=1.0, att_se=1.0) for k in ["e", "f"]}
        changes = [dict(change_id=k, start_day=0, experiment_id=k) for k in experiments]
        covariance = {"e": {"f": 0.5}, "f": {"e": 0.5}}
        r = attribute_baseline(
            range(20),
            [10.0] * 20,
            [12.0] * 20,
            changes,
            [],
            experiments,
            experiment_covariance=covariance,
        )
        self.assertAlmostEqual(
            r["explained_uncertainty"]["standard_error"][0], np.sqrt(3)
        )
        with self.assertRaises(ValueError):
            attribute_baseline(
                range(20),
                [10.0] * 20,
                [12.0] * 20,
                changes,
                [],
                experiments,
                experiment_covariance={"e": {"f": 5}},
            )

    def test_external_event_covering_all_days_does_not_crash(self):
        r = attribute_baseline(
            range(20),
            [1.0] * 20,
            [1.0] * 20,
            [],
            [dict(event_id="event", start_day=0, end_day=19, kind="policy")],
            {},
        )
        self.assertEqual(
            r["external_associations"][0]["alignment"], "INSUFFICIENT_DATA"
        )
        self.assertIsNone(r["external_associations"][0]["window_deviation"])

    def test_rate_step_detection_retains_probability_precision(self):
        r = attribute_baseline(
            range(20),
            [0.1] * 20,
            [0.1] * 10 + [0.12] * 10,
            [],
            [],
            {},
            detection_threshold=0.002,
            metric_contract=metric(),
        )
        self.assertTrue(r["unregistered_alerts"])
        self.assertAlmostEqual(r["series"]["residual"][-1], 0.02)


class PersistenceBoundaryTests(unittest.TestCase):
    def test_company_reruns_and_old_evidence_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            with patch.dict(
                sr._RUNNERS, {"company_line_b": lambda _: {"metrics": {"v": 1}}}
            ):
                a = sr.run_scenario("company_line_b", runtime)
            with patch.dict(
                sr._RUNNERS, {"company_line_b": lambda _: {"metrics": {"v": 2}}}
            ):
                b = sr.run_scenario("company_line_b", runtime)
            self.assertEqual(b["metrics"]["v"], 2)
            self.assertNotEqual(a["run_id"], b["run_id"])
            self.assertEqual(sr.read_run(runtime, a["run_id"])["metrics"]["v"], 1)
            with self.assertRaises(ValueError):
                sr.read_run(runtime, "../bad")

    def test_fixture_cache_is_explicit_and_defensive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                sr._RUNNERS, {"line_a": lambda _: {"metrics": {"v": 1}}}
            ) as _:
                a = sr.run_scenario("line_a", Path(tmp))
                a["metrics"]["v"] = 100
                b = sr.run_scenario("line_a", Path(tmp))
            self.assertEqual(b["metrics"]["v"], 1)
            self.assertTrue(b["cache_hit"])
            self.assertFalse(b["real_run"])
            self.assertEqual(a["computed_at"], b["computed_at"])

    def test_feedback_idempotency_and_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HumanFeedbackStore(Path(tmp) / "feedback.json")
            for _ in range(4):
                store.record_alert_feedback("same", "false_positive", "op", "external")
            self.assertEqual(store.summary()["entries"], 1)
            self.assertEqual(store.budget_calibration()["external"], 1)
            store.record_alert_feedback("same", "useful", "op", "external")
            self.assertEqual(store.precision_by_source()["external"]["n_labels"], 1)
            self.assertEqual(store.precision_by_source()["external"]["precision"], 1)
            store.save()
            self.assertEqual(HumanFeedbackStore(store.path).summary()["entries"], 2)

    def test_supplement_preserves_existing_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HumanFeedbackStore(Path(tmp) / "feedback.json")
            registry = FactorRegistry()
            self.addCleanup(registry.close)
            registry.register_factor(
                dict(
                    factor_id="f",
                    name="original",
                    source_type="source",
                    license_ref="license",
                )
            )
            store.register_factor_supplement(
                registry, "f", "replacement", "internal", "op", "new observation"
            )
            self.assertEqual(registry.get_factor("f")["source_type"], "source")
            self.assertEqual(registry.get_factor("f")["name"], "original")
            self.assertEqual(
                registry.connection.execute("select count(*) from evidence").fetchone()[
                    0
                ],
                1,
            )

    def test_short_placebo_is_insufficient_not_zero_padded(self):
        factor = dict(factor_id="f", days=list(range(10)), values=list(range(10)))
        result = falsify(
            dict(lag=0, correlation=0.8), list(range(10)), list(range(10)), factor
        )
        self.assertTrue(result["tests"]["placebo"]["insufficient_data"])
        self.assertEqual(result["tests"]["placebo"]["n_pairs"], 0)
        self.assertFalse(result["survived"])


class MonetaryAdapterTests(unittest.TestCase):
    def test_money_uses_values_and_configured_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            rows = [
                dict(
                    day=d,
                    region="all",
                    channel="all",
                    version="v1",
                    control_value=12.50,
                    treatment_value=18.75,
                    control_users=10,
                    treatment_users=15,
                )
                for d in range(20)
            ]
            (path / "value_panel.json").write_text(json.dumps(rows))
            for name in ("change_registry", "external_events"):
                (path / f"{name}.json").write_text("[]")
            cfg = DataSourceConfig(
                path,
                metric_unit="currency",
                target_population="customers",
                files={"value_panel": "value_panel.json"},
            )
            result = load_line_b_inputs(cfg)
            self.assertEqual(result["control"], [12.5] * 20)
            self.assertEqual(
                result["metric_contract"]["target_population"], "customers"
            )
            cfg.metric_unit = "currency_per_user"
            result = load_line_b_inputs(cfg)
            self.assertEqual(result["control"], [1.25] * 20)
            self.assertEqual(result["treated"], [1.25] * 20)
            self.assertEqual(result["scoped_panel"], [])
            with patch.object(sr, "_COMPANY_CONFIG", cfg):
                report = sr._scenario_company_line_b(path / "runtime")
            self.assertEqual(
                report["key_outputs"]["rate_aware_rca"]["status"], "NOT_APPLICABLE"
            )
            self.assertEqual(report["metrics"]["panel_rows"], 20)

    def test_fractional_user_count_and_duplicate_value_cells_rejected(self):
        row = dict(
            day=0,
            region="r",
            channel="c",
            version="v",
            control_value=1.25,
            treatment_value=1.5,
            control_users=2,
            treatment_users=3,
        )
        with self.assertRaises(ContractError):
            validate_rows("value_panel", [row, row])
        with self.assertRaises(ContractError):
            validate_rows("value_panel", [{**row, "control_users": 1.5}])


class StandaloneEntryTests(unittest.TestCase):
    def test_hidden_benchmark_handles_refused_estimates_without_hiding_failure(self):
        from goai_control_tower.track2_benchmark import run_hidden_benchmark

        r = run_hidden_benchmark(seeds=(101,), n=1200)
        self.assertEqual(r["evaluated_cases"], 3)
        self.assertEqual(r["metrics"]["false_causal_assertion_rate"], 0)
        self.assertEqual(
            r["metrics"]["issued_effect"]["evaluated"]
            + r["metrics"]["issued_effect"]["unavailable_due_to_gate"],
            1,
        )

    def test_uci_resolver_uses_shipped_file_without_network(self):
        from goai_control_tower.track2_real_data import resolve_bank_marketing_csv

        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(resolve_bank_marketing_csv(Path(tmp)).is_file())
            with self.assertRaises(FileNotFoundError):
                resolve_bank_marketing_csv(Path(tmp), Path(tmp) / "missing.csv")


class ContractsTests(unittest.TestCase):
    def test_metric_digest_and_normalization(self):
        m = validate_contract("MetricContract", metric())
        self.assertEqual(validate_contract("MetricContract", m), m)
        m["unit"] = "count"
        with self.assertRaises(ContractError):
            validate_contract("MetricContract", m)

    def test_factor_rejects_future_availability(self):
        f = dict(
            factor_id="f",
            source_uri="source",
            available_at=21,
            as_of=20,
            unit="rate",
            grain="day",
            lineage=[],
            constraints={},
            window=[0, 19],
            response_window=[0, 3],
        )
        with self.assertRaises(ContractError):
            validate_contract("FactorContract", f)
        f["available_at"] = 20
        self.assertIn("digest", validate_contract("FactorContract", f))

    def test_itt_rejects_exposure_selected_population(self):
        i = dict(
            treatment_version="v2",
            control_version="v1",
            assignment_ref="a",
            exposure_ref="e",
            target_population="eligible_population",
            window=[0, 19],
            randomization_unit="user",
            controllable=True,
            estimand="ITT",
            population_filter="exposed",
        )
        with self.assertRaises(ContractError):
            validate_contract("InterventionContract", i)
        i["population_filter"] = "assigned"
        self.assertIn("digest", validate_contract("InterventionContract", i))

    def test_family_freeze_gap_and_atomic_keys(self):
        f = dict(
            hypothesis_keys=["factor.scope.lag.metric.window"],
            search_manifest={},
            null_hypothesis="independent",
            statistic="correlation",
            null_model="joint_block",
            correction="max_t",
            frozen_at=16,
            discovery_window=[0, 14],
            holdout_window=[17, 19],
            gap_days=2,
        )
        self.assertIn("digest", validate_contract("TestFamilyContract", f))
        for field, value in [
            ("holdout_window", [14, 19]),
            ("hypothesis_keys", ["same", "same"]),
            ("frozen_at", 18),
        ]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_contract("TestFamilyContract", {**f, field: value})

    def test_effect_cannot_bypass_identification_or_mismatch_units(self):
        identification = dict(
            treatment="t",
            outcome="y",
            design="RCT",
            status="NOT_IDENTIFIED",
            assumptions=[],
            evidence_refs=[],
            adjustment_set=[],
            forbidden_adjustments=[],
            support={},
            ambiguities=[],
            reason_codes=["NOT_IDENTIFIABLE"],
        )
        i = validate_contract("IdentificationReport", identification)
        e = dict(
            estimand="ITT",
            unit="rate",
            estimate=0.01,
            interval=[0, 0.02],
            interval_method="normal",
            selection_status="pre_registered",
            target_population="eligible_population",
            window=[0, 19],
            diagnostics={},
            identification_ref=i["digest"],
        )
        with self.assertRaises(ContractError):
            validate_bundle(
                {
                    "MetricContract": metric(),
                    "IdentificationReport": i,
                    "EffectEstimate": e,
                }
            )
        identification.update(
            status="IDENTIFIED", evidence_refs=["experiment"], reason_codes=[]
        )
        i = validate_contract("IdentificationReport", identification)
        e["identification_ref"] = i["digest"]
        self.assertEqual(
            len(
                validate_bundle(
                    {
                        "MetricContract": metric(),
                        "IdentificationReport": i,
                        "EffectEstimate": e,
                    }
                )
            ),
            3,
        )
        e["unit"] = "count"
        with self.assertRaises(ContractError):
            validate_bundle(
                {
                    "MetricContract": metric(),
                    "IdentificationReport": i,
                    "EffectEstimate": e,
                }
            )


if __name__ == "__main__":
    unittest.main()
