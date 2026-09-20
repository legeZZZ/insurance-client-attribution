"""Phase D executable governance, durable feedback and resident scan tests."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np

from track2_v5.contracts import digest
from track2_v5.skill_governance import SkillGovernance, isolated_replay
from track2_v5.skill_evolution import SkillStore
from track2_v5.feedback_service import FeedbackService
from track2_v5.experience_store import GovernedPriorStore
from track2_v5.scan_service import ScanService
from track2_v5.watchlist_scan import hunter_scan, falsify, run_c_line, confirm_watchlist
from test_stage_c import metric


def metric_request(index):
    m = metric()
    m["window"] = [index, index + 9]
    return {"metric_contract": m}


def scan_request(seed=1, start=0, shape="persistent"):
    rng = np.random.default_rng(seed)
    n = 80
    x = rng.normal(size=n)
    y = 0.9 * np.roll(x, 2) + rng.normal(size=n) * 0.15
    if shape == "onset":
        x[n // 2 :] = 0
        y[n // 2 + 2 :] = rng.normal(size=n - n // 2 - 2) * 0.05
    if shape == "pulse":
        x[:15] = 0
        x[35:] = 0
        y = 0.9 * np.roll(x, 2) + rng.normal(size=n) * 0.05
    days = list(range(start, start + n))
    f = {
        "factor_id": "driver",
        "days": days,
        "values": x.tolist(),
        "effect_shape": shape,
        "kind": "internal_event",
    }
    return {
        "days": days,
        "residual": y.tolist(),
        "factors": [f],
        "lags": [2],
        "budget": 2,
        "test_budget": 30,
    }


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "governance.db"
        self.service = SkillGovernance(self.path)
        self.addCleanup(self.service.close)
        self.context = {"metric_kind": "ratio_of_sums"}

    def asset(self, request):
        return self.service.registry.add_asset("data", request)

    def candidate(self, name="metric_skill"):
        request = metric_request(0)
        ref = self.asset(request)
        trace = self.service.capture(
            task_id="source",
            data_ref=ref,
            context=self.context,
            operation="check_metric",
            author="author",
        )
        proposal = self.service.propose(
            name=name, trace_ids=[trace["trace_id"]], applicability=self.context
        )
        return proposal, trace

    def suite(self, offset=10, critical=False, expected="check_metric"):
        cases = []
        for i in (offset, offset + 1):
            request = metric_request(i)
            ref = self.asset(request)
            cases.append(
                {
                    "task_id": f"holdout-{i}",
                    "data_ref": ref,
                    "context": self.context,
                    "request": request,
                    "expected_operation": expected,
                    "critical": critical,
                }
            )
        return self.service.freeze_suite(cases=cases)["suite_ref"]

    def trusted(self):
        candidate, trace = self.candidate()
        self.service.review(name="metric_skill", version=1, reviewer="reviewer")
        suite = self.suite()
        result = self.service.validate(name="metric_skill", version=1, suite_ref=suite)
        self.assertTrue(result["passed"])
        receipt = self.service.approve(
            name="metric_skill",
            version=1,
            approver="human",
            credential_ref="fixture:explicit-human-approval",
            suite_ref=suite,
        )["approval_ref"]
        return trace, suite, receipt

    def test_independent_review_and_real_paired_replay(self):
        candidate, trace = self.candidate()
        self.assertEqual(candidate["spec"]["rules"][0]["action"], "check_metric")
        with self.assertRaises(ValueError):
            self.service.review(name="metric_skill", version=1, reviewer="author")
        review = self.service.review(
            name="metric_skill", version=1, reviewer="independent"
        )
        self.assertTrue(review["passed"])
        self.assertNotEqual(review["checks"][0]["pid"], os.getpid())
        result = self.service.validate(
            name="metric_skill", version=1, suite_ref=self.suite()
        )
        self.assertEqual(result["decision"], "CRYSTALLIZE")
        self.assertEqual(result["paired_gain"], 1)
        self.assertEqual(
            self.service.get("metric_skill", 1)["lifecycle"]["trust_state"], "trusted"
        )

    def test_provisional_retrieval_is_audit_only_and_scope_cannot_expand(self):
        _, trace = self.candidate()
        ref = self.asset(metric_request(20))
        hits = self.service.retrieve(
            name="metric_skill", context=self.context, task_id="current", data_ref=ref
        )
        self.assertEqual(hits[0]["mode"], "AUDIT_ONLY")
        with self.assertRaises(ValueError):
            self.service.propose(
                name="broad",
                trace_ids=[trace["trace_id"]],
                applicability={"domain": "anything"},
            )
        with self.assertRaises(ValueError):
            self.service.propose(
                name="statistical_core",
                trace_ids=[trace["trace_id"]],
                applicability=self.context,
            )
        with self.assertRaises(ValueError):
            self.service.propose(
                name="fake",
                trace_ids=[trace["trace_id"]],
                applicability=self.context,
                claim_ceiling="RANDOMIZED_EFFECT",
            )

    def test_same_task_data_cannot_validate_own_extraction(self):
        _, trace = self.candidate()
        self.service.review(name="metric_skill", version=1, reviewer="reviewer")
        suite = self.service.freeze_suite(
            cases=[
                {
                    "task_id": "another-name",
                    "data_ref": trace["data_ref"],
                    "context": self.context,
                    "request": metric_request(0),
                    "expected_operation": "check_metric",
                }
            ]
        )["suite_ref"]
        with self.assertRaises(ValueError):
            self.service.validate(name="metric_skill", version=1, suite_ref=suite)

    def test_critical_regression_vetoes_release(self):
        self.candidate()
        self.service.review(name="metric_skill", version=1, reviewer="reviewer")
        result = self.service.validate(
            name="metric_skill",
            version=1,
            suite_ref=self.suite(critical=True, expected="check_overlap"),
        )
        self.assertFalse(result["passed"])
        self.assertTrue(result["critical_failures"])
        with self.assertRaises(ValueError):
            self.service.publish(name="metric_skill", version=1, approval_ref="made-up")

    def test_canary_human_receipt_scope_replay_and_invalidation(self):
        trace, suite, receipt = self.trusted()
        with self.assertRaises(ValueError):
            self.service.publish(
                name="metric_skill", version=1, approval_ref=receipt, fraction=1
            )
        self.service.publish(
            name="metric_skill", version=1, approval_ref=receipt, effective_window=2
        )
        canary = self.suite(30)
        self.assertTrue(
            self.service.monitor(name="metric_skill", version=1, suite_ref=canary)[
                "passed"
            ]
        )
        receipt = self.service.approve(
            name="metric_skill",
            version=1,
            approver="human",
            credential_ref="fixture:canary-approved",
            suite_ref=canary,
        )["approval_ref"]
        self.service.publish(
            name="metric_skill",
            version=1,
            approval_ref=receipt,
            fraction=1,
            effective_window=3,
        )
        ref = self.asset(metric_request(40))
        blocked = self.service.replay(
            name="metric_skill",
            context=self.context,
            task_id="task",
            data_ref=ref,
            window=2,
        )
        self.assertEqual(blocked["decision"], "AUDIT_ONLY")
        result = self.service.replay(
            name="metric_skill",
            context=self.context,
            task_id="task",
            data_ref=ref,
            window=3,
        )
        self.assertEqual(
            result["attribution"], "existing_skill_replay_not_new_discovery"
        )
        self.assertEqual(result["report"]["binding"]["data_ref"], ref)
        self.assertEqual(
            self.service.replay(
                name="metric_skill",
                context={"metric_kind": "count"},
                task_id="wrong",
                data_ref=ref,
                window=3,
            )["decision"],
            "AUDIT_ONLY",
        )
        store = SkillStore(self.service.skill_store_path)
        self.assertIsNotNone(store.active("metric_skill"))
        self.service.registry.invalidate(trace["data_ref"], reason="source correction")
        self.assertIsNone(
            SkillStore(self.service.skill_store_path).active("metric_skill")
        )
        self.assertEqual(
            self.service.get("metric_skill", 1)["lifecycle"]["trust_state"], "suspended"
        )

    def test_failed_trace_without_verified_correction_does_not_generalize(self):
        request = {"metric_contract": {}}
        ref = self.asset(request)
        trace = self.service.capture(
            task_id="bad",
            data_ref=ref,
            context=self.context,
            operation="check_metric",
            author="author",
        )
        self.assertEqual(trace["outcome"], "failure")
        result = self.service.propose(
            name="bad_lesson", trace_ids=[trace["trace_id"]], applicability=self.context
        )
        self.assertEqual(result["decision"], "AUDIT_ONLY")
        fixed = self.asset(metric_request(2))
        corrected = self.service.capture(
            task_id="fixed",
            data_ref=ref,
            context=self.context,
            operation="check_metric",
            author="author",
            correction={"operation": "check_metric", "data_ref": fixed},
        )
        skill = self.service.propose(
            name="check_first",
            trace_ids=[corrected["trace_id"]],
            applicability=self.context,
        )
        self.assertEqual(skill["spec"]["negative_examples"], [corrected["trace_id"]])
        self.assertEqual(skill["spec"]["rules"][0]["action"], "check_metric")

    def test_worker_timeout_and_capability_guard(self):
        binding = {"task_id": "t", "data_ref": "d", "skill_ref": "s"}
        with self.assertRaises(ValueError):
            isolated_replay("shell", {}, binding)
        with self.assertRaises(TimeoutError):
            isolated_replay("check_metric", metric_request(0), binding, timeout=0.00001)

    def test_capture_idempotent_after_reopen(self):
        _, trace = self.candidate()
        another = SkillGovernance(self.path)
        try:
            replay = another.capture(
                task_id="source",
                data_ref=trace["data_ref"],
                context=self.context,
                operation="check_metric",
                author="author",
            )
            self.assertEqual(replay["trace_id"], trace["trace_id"])
            self.assertEqual(
                another.db.execute("SELECT count(*) FROM skill_traces").fetchone()[0], 1
            )
        finally:
            another.close()


class FeedbackPriorTests(unittest.TestCase):
    def test_feedback_idempotency_revision_queue_and_factor_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = FeedbackService(Path(tmp) / "state.db")
            try:
                payload = {
                    "factor_id": "f",
                    "decision": "confirmed",
                    "operator": "human",
                }
                first = service.submit(
                    request_id="r1", kind="candidate_review", payload=payload
                )
                self.assertFalse(first["claim_promotion_allowed"])
                self.assertEqual(
                    first,
                    service.submit(
                        request_id="r1", kind="candidate_review", payload=payload
                    ),
                )
                with self.assertRaises(ValueError):
                    service.submit(
                        request_id="r1",
                        kind="candidate_review",
                        payload={**payload, "decision": "rejected"},
                    )
                revision = service.submit(
                    request_id="r2",
                    kind="candidate_review",
                    payload={**payload, "decision": "rejected"},
                )
                self.assertEqual(revision["supersedes"], first["event_id"])
                self.assertEqual(service.queue()[-1]["status"], "REJECTED")
                supplement = service.submit(
                    request_id="r3",
                    kind="factor_supplement",
                    payload={
                        "factor_id": "new",
                        "operator": "human",
                        "note": "declared event",
                        "current_window": 2,
                        "available_day": 10,
                    },
                )
                intake = service.register_supplement(
                    event_id=supplement["event_id"],
                    factor_db_path=str(Path(tmp) / "factors.db"),
                )
                self.assertEqual(intake["eligible_from_window"], 3)
                self.assertEqual(
                    intake,
                    service.register_supplement(
                        event_id=supplement["event_id"],
                        factor_db_path=str(Path(tmp) / "factors.db"),
                    ),
                )
            finally:
                service.close()

    def test_prior_context_drift_idempotency_and_invalid_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GovernedPriorStore(Path(tmp) / "prior.db")
            try:
                context = {
                    "metric": "conversion",
                    "population": "a",
                    "assignment_version": "v1",
                }
                data = {"arm_key": "control", "successes": 20, "trials": 100}
                ref = store.registry.add_asset("data", data)
                kwargs = {
                    "task_id": "t",
                    "period": 1,
                    "context": context,
                    **data,
                    "data_ref": ref,
                }
                self.assertEqual(store.observe(**kwargs), store.observe(**kwargs))
                self.assertEqual(
                    store.db.execute(
                        "SELECT count(*) FROM prior_observations"
                    ).fetchone()[0],
                    1,
                )
                prior = store.prior_for(
                    context=context,
                    arm_key="control",
                    current_period=2,
                    fresh_successes=21,
                    fresh_trials=100,
                )
                self.assertIsNotNone(prior["prior"])
                self.assertLessEqual(prior["effective_pseudo_trials"], 25)
                drift = store.prior_for(
                    context=context,
                    arm_key="control",
                    current_period=2,
                    fresh_successes=99,
                    fresh_trials=100,
                )
                self.assertIsNone(drift["prior"])
                self.assertEqual(drift["reason"], "PREDICTIVE_MISMATCH")
                mismatch = store.prior_for(
                    context={**context, "population": "b"},
                    arm_key="control",
                    current_period=2,
                    fresh_successes=20,
                    fresh_trials=100,
                )
                self.assertIsNone(mismatch["prior"])
                store.registry.invalidate(ref, reason="correction")
                self.assertIsNone(
                    store.prior_for(
                        context=context,
                        arm_key="control",
                        current_period=2,
                        fresh_successes=20,
                        fresh_trials=100,
                    )["prior"]
                )
            finally:
                store.close()


class WatchlistTests(unittest.TestCase):
    def test_actual_budget_and_scope_keys(self):
        request = scan_request()
        factors = request["factors"]
        factors.append({**factors[0], "scope_id": "other"})
        hunted = hunter_scan(
            request["days"],
            request["residual"],
            factors,
            lags=[0, 1, 2, 3],
            test_budget=3,
        )
        self.assertEqual(hunted["manifest"]["tested"], 3)
        self.assertTrue(hunted["manifest"]["truncated"])
        self.assertEqual(hunted["manifest"]["S"], 2)
        result = run_c_line(**{**request, "test_budget": 3})
        self.assertLessEqual(result["manifest"]["total_tests_spent"], 3)

    def test_persistent_onset_pulse_not_rejected_by_inapplicable_split(self):
        for shape in ("persistent", "onset", "pulse"):
            for seed in range(5):
                request = scan_request(seed=seed, shape=shape)
                result = run_c_line(**request)
                self.assertTrue(result["watchlist"], (shape, seed, result))
                split = result["watchlist"][0]["falsification"]["split_half"]
                self.assertEqual(split["applicable"], shape == "persistent")
                self.assertFalse(split["kill"])

    def test_negative_control_and_budget_exhaustion_do_not_promote(self):
        request = scan_request()
        negative = {**request["factors"][0], "factor_id": "negative_control"}
        result = run_c_line(**request, negative_controls=[negative])
        self.assertFalse(result["watchlist"])
        self.assertTrue(result["killed"])
        h = hunter_scan(
            request["days"], request["residual"], request["factors"], lags=[2]
        )["hypotheses"][0]
        verdict = falsify(
            h,
            request["days"],
            request["residual"],
            request["factors"][0],
            test_budget=0,
        )
        self.assertFalse(verdict["survived"])
        self.assertEqual(verdict["status"], "INSUFFICIENT_EVIDENCE")

    def test_next_window_confirmation_and_overlap_rejection(self):
        request = scan_request()
        items = run_c_line(**request)["watchlist"]
        next_request = scan_request(seed=10, start=90)
        confirmation = confirm_watchlist(
            items,
            next_request["days"],
            next_request["residual"],
            next_request["factors"],
        )
        self.assertTrue(confirmation["results"][0]["confirmed"])
        self.assertFalse(confirmation["causal_eligible"])
        with self.assertRaises(ValueError):
            confirm_watchlist(
                items, request["days"], request["residual"], request["factors"]
            )


class ResidentScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.input = self.path / "input.json"
        self.db = self.path / "state.db"
        self.service = ScanService(self.db)
        self.addCleanup(self.service.close)
        self.write(1)
        self.service.configure(
            name="job",
            input_path=self.input,
            interval_seconds=0.1,
            test_budget=30,
            timeout=10,
            error_policy="alpha_spending_empirical",
        )

    def write(self, window, seed=1):
        self.input.write_text(
            json.dumps(
                {
                    "window_id": window,
                    "expected_through": 79,
                    "observed_through": 79,
                    "request": scan_request(seed=seed),
                }
            )
        )

    def test_start_stop_reopen_dedup_correction_and_budget(self):
        self.assertEqual(self.service.tick("job")["status"], "STOPPED")
        self.service.start("job")
        result = self.service.tick("job", force=True)
        self.assertEqual(result["status"], "COMPLETED", result)
        self.assertEqual(self.service.status("job")["watermark"], 1)
        alerts = self.service.alerts("job")
        self.assertTrue(alerts)
        self.assertEqual(
            self.service.tick("job", force=True)["status"], "ALREADY_PROCESSED"
        )
        self.write(1, seed=2)
        correction = self.service.tick("job", force=True)
        self.assertTrue(correction["corrected"])
        self.assertEqual(self.service.alerts("job")[0]["status"], "WITHDRAWN")
        self.service.stop("job")
        self.assertEqual(self.service.tick("job")["status"], "STOPPED")
        with self.assertRaises(ValueError):
            self.service.configure(name="job", input_path=self.input, test_budget=1000)

    def test_failure_preserves_watermark_and_spent_budget(self):
        self.service.start("job")
        with patch(
            "track2_v5.scan_service.isolated_replay",
            side_effect=TimeoutError("fixture timeout"),
        ):
            failed = self.service.tick("job", force=True)
        self.assertEqual(failed["status"], "FAILED")
        self.assertIsNone(self.service.status("job")["watermark"])
        self.assertEqual(
            self.service.status("job")["runs"][0]["body"]["tests_charged"], 30
        )
        self.assertEqual(self.service.tick("job", force=True)["status"], "COMPLETED")

    def test_freshness_and_next_window_confirmation_are_persistent(self):
        self.service.start("job")
        self.service.tick("job", force=True)
        alert_ids = [a["alert_id"] for a in self.service.alerts("job")]
        request = scan_request(seed=9, start=90)
        result = self.service.confirm(
            name="job",
            alert_ids=alert_ids,
            days=request["days"],
            residual=request["residual"],
            factors=request["factors"],
        )
        self.assertEqual(result["alpha"], 0.025)
        with self.assertRaises(ValueError):
            self.service.confirm(
                name="job",
                alert_ids=alert_ids,
                days=request["days"],
                residual=request["residual"],
                factors=request["factors"],
            )
        os.utime(self.input, (0, 0))
        self.assertEqual(self.service.tick("job", force=True)["status"], "STALE")

    def test_expired_run_recovery_keeps_charged_budget(self):
        self.service.start("job")
        body = {"owner_pid": 99999999, "lease_until": 0, "tests_charged": 30}
        self.service.db.execute(
            "INSERT INTO scan_runs VALUES (?,?,?,?,?)",
            ("crashed", "job", 1, "RUNNING", json.dumps(body)),
        )
        self.assertEqual(self.service.recover()["recovered"], ["crashed"])
        status = self.service.status("job")
        self.assertEqual(status["runs"][0]["status"], "INTERRUPTED")
        self.assertEqual(status["runs"][0]["body"]["tests_charged"], 30)
        self.assertEqual(self.service.tick("job", force=True)["status"], "COMPLETED")

    def test_real_resident_process_stops_via_database_flag(self):
        self.service.start("job")
        worker = Path(__file__).resolve().parents[1] / "track2_v5/scan_worker.py"
        process = subprocess.Popen(
            [sys.executable, "-I", str(worker), "--db", str(self.db), "--job", "job"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.time() + 15
            while (
                time.time() < deadline
                and self.service.status("job")["watermark"] is None
            ):
                time.sleep(0.1)
            self.assertEqual(self.service.status("job")["watermark"], 1)
            self.service.stop("job")
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, err)
            self.assertIn("COMPLETED", out)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()


class ExtendedGovernanceTests(unittest.TestCase):
    setUp = GovernanceTests.setUp
    asset = GovernanceTests.asset
    candidate = GovernanceTests.candidate
    suite = GovernanceTests.suite
    trusted = GovernanceTests.trusted

    def test_validation_data_cannot_be_repackaged_as_new_suite(self):
        _, original, receipt = self.trusted()
        self.service.publish(name="metric_skill", version=1, approval_ref=receipt)
        body = json.loads(
            self.service.db.execute(
                "SELECT body FROM skill_suites WHERE id=?", (original,)
            ).fetchone()[0]
        )
        body["cases"][0]["task_id"] = "renamed-holdout"
        repackaged = self.service.freeze_suite(cases=body["cases"], tolerance=0.1)[
            "suite_ref"
        ]
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.service.validate(name="metric_skill", version=1, suite_ref=repackaged)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.service.monitor(name="metric_skill", version=1, suite_ref=repackaged)

    def test_delta_replacement_conflict_and_bound_rollback(self):
        from track2_v5.skill_evolution import _digest

        _, _, receipt1 = self.trusted()
        self.service.publish(name="metric_skill", version=1, approval_ref=receipt1)
        request = {
            **metric_request(50),
            "rows": [
                {"treatment": 0, "channel": "a"},
                {"treatment": 1, "channel": "a"},
            ],
            "group_column": "channel",
        }
        source = self.asset(request)
        trace = self.service.capture(
            task_id="new-method",
            data_ref=source,
            context=self.context,
            operation="check_overlap",
            author="author2",
        )
        conflict = self.service.propose(
            name="metric_skill",
            trace_ids=[trace["trace_id"]],
            applicability=self.context,
            base_version=1,
        )
        self.assertEqual(conflict["decision"], "AUDIT_ONLY")
        self.assertTrue(conflict["conflicts"])
        old_rule = self.service.get("metric_skill", 1)["spec"]["rules"][0]
        candidate = self.service.propose(
            name="metric_skill",
            trace_ids=[trace["trace_id"]],
            applicability=self.context,
            base_version=1,
            replacements={trace["trace_id"]: _digest(old_rule)},
        )
        self.assertEqual(candidate["version"], 2)
        self.assertEqual(candidate["spec"]["delta"]["base_version"], 1)
        self.assertEqual(len(candidate["spec"]["source_trace_ids"]), 2)
        self.service.review(name="metric_skill", version=2, reviewer="independent")
        cases = []
        for i in (60, 61):
            r = {**request, "metric_contract": metric_request(i)["metric_contract"]}
            ref = self.asset(r)
            cases.append(
                {
                    "task_id": f"overlap-{i}",
                    "data_ref": ref,
                    "context": self.context,
                    "request": r,
                    "expected_operation": "check_overlap",
                    "critical": True,
                }
            )
        suite = self.service.freeze_suite(cases=cases)["suite_ref"]
        self.assertTrue(
            self.service.validate(name="metric_skill", version=2, suite_ref=suite)[
                "passed"
            ]
        )
        receipt2 = self.service.approve(
            name="metric_skill",
            version=2,
            approver="human",
            credential_ref="fixture:second-release",
            suite_ref=suite,
        )["approval_ref"]
        self.service.publish(name="metric_skill", version=2, approval_ref=receipt2)
        with self.assertRaises(ValueError):
            self.service.rollback(
                name="metric_skill",
                target_version=1,
                approval_ref="forged",
                effective_window=3,
            )
        self.assertTrue(
            self.service.get("metric_skill", 2)["lifecycle"]["execution_eligible"]
        )
        self.service.rollback(
            name="metric_skill",
            target_version=1,
            approval_ref=receipt1,
            effective_window=3,
        )
        active = SkillStore(self.service.skill_store_path).active("metric_skill")
        self.assertEqual(active["governance_binding"]["version"], 1)
        self.assertFalse(
            self.service.get("metric_skill", 2)["lifecycle"]["execution_eligible"]
        )

    def test_frozen_noninferiority_tolerance_is_effective(self):
        from track2_v5.skill_evolution import _digest

        self.trusted()
        request = {
            **metric_request(100),
            "rows": [
                {"treatment": 0, "channel": "a"},
                {"treatment": 1, "channel": "a"},
            ],
            "group_column": "channel",
        }
        source = self.asset(request)
        trace = self.service.capture(
            task_id="replacement",
            data_ref=source,
            context=self.context,
            operation="check_overlap",
            author="second",
        )
        old = self.service.get("metric_skill", 1)["spec"]["rules"][0]
        self.service.propose(
            name="metric_skill",
            trace_ids=[trace["trace_id"]],
            applicability=self.context,
            base_version=1,
            replacements={trace["trace_id"]: _digest(old)},
        )
        self.service.review(name="metric_skill", version=2, reviewer="reviewer")
        cases = []
        for i in range(5):
            r = {
                **request,
                "metric_contract": metric_request(110 + i)["metric_contract"],
            }
            cases.append(
                {
                    "task_id": f"noninferiority-{i}",
                    "data_ref": self.asset(r),
                    "context": self.context,
                    "request": r,
                    "expected_operation": "check_metric" if i < 3 else "check_overlap",
                }
            )
        suite = self.service.freeze_suite(cases=cases, tolerance=0.25)["suite_ref"]
        result = self.service.validate(name="metric_skill", version=2, suite_ref=suite)
        self.assertAlmostEqual(result["paired_gain"], -0.2)
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "NOOP")

    def test_governed_name_cannot_be_reactivated_by_legacy_shortcut(self):
        _, _, receipt = self.trusted()
        self.service.publish(name="metric_skill", version=1, approval_ref=receipt)
        store = SkillStore(self.service.skill_store_path)
        candidate = store.register("metric_skill", [], "unreviewed legacy candidate")
        entry = store._record("metric_skill")["versions"][-1]
        from track2_v5.skill_evolution import _digest

        entry["validation"] = {
            "passed": True,
            "rules_digest": _digest([]),
            "base_version": store._record("metric_skill")["active"],
        }
        with self.assertRaises(ValueError):
            store.activate("metric_skill", candidate["version"], "bypass")

    def test_failed_environment_routes_issue_and_noop_does_not_add_version(self):
        _, trace = self.candidate()
        result = self.service.propose(
            name="metric_skill",
            trace_ids=[trace["trace_id"]],
            applicability=self.context,
            base_version=1,
        )
        self.assertEqual(result["decision"], "NOOP")
        bad = self.asset({"metric_contract": {}})
        t = self.service.capture(
            task_id="environment",
            data_ref=bad,
            context=self.context,
            operation="check_metric",
            author="author",
            failure_kind="environment",
        )
        self.assertEqual(
            self.service.propose(
                name="environment",
                trace_ids=[t["trace_id"]],
                applicability=self.context,
            )["decision"],
            "ISSUE",
        )


class CrossPeriodLoopTests(unittest.TestCase):
    def test_feedback_to_skill_to_next_scan_and_false_positive_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            source = path / "input.json"
            db = path / "state.db"
            first = scan_request()
            source.write_text(
                json.dumps(
                    {
                        "window_id": 1,
                        "expected_through": 79,
                        "observed_through": 79,
                        "request": first,
                    }
                )
            )
            scans = ScanService(db)
            feedback = FeedbackService(db)
            skills = SkillGovernance(db)
            context = {"workflow": "c_line"}
            try:
                scans.configure(
                    name="loop",
                    input_path=source,
                    skill_name="watch_skill",
                    skill_context=context,
                    interval_seconds=0.1,
                    test_budget=30,
                )
                scans.start("loop")
                self.assertEqual(scans.tick("loop", force=True)["status"], "COMPLETED")
                alert = scans.alerts("loop")[0]
                event = feedback.submit(
                    request_id="useful",
                    kind="alert_feedback",
                    payload={
                        "alert_id": alert["alert_id"],
                        "label": "useful",
                        "operator": "analyst",
                        "source_kind": "internal_event",
                    },
                )
                candidate = skills.learn_from_feedback(
                    event_id=event["event_id"], name="watch_skill", context=context
                )
                self.assertEqual(candidate["spec"]["claim_ceiling"], "WATCHLIST")
                self.assertEqual(
                    scans.tick("loop", force=True)["status"], "ALREADY_PROCESSED"
                )
                self.assertEqual(scans.alerts("loop")[0]["status"], "WATCHLIST")
                skills.review(name="watch_skill", version=1, reviewer="reviewer")

                def suite(offset):
                    cases = []
                    for i in range(offset, offset + 2):
                        request = scan_request(seed=i, start=i * 100)
                        ref = skills.registry.add_asset("data", request)
                        cases.append(
                            {
                                "task_id": f"scan-validation-{i}",
                                "data_ref": ref,
                                "context": context,
                                "request": request,
                                "expected_operation": "scan_window",
                                "critical": True,
                            }
                        )
                    return skills.freeze_suite(cases=cases)["suite_ref"]

                frozen = suite(10)
                self.assertTrue(
                    skills.validate(name="watch_skill", version=1, suite_ref=frozen)[
                        "passed"
                    ]
                )
                approval = skills.approve(
                    name="watch_skill",
                    version=1,
                    approver="human",
                    credential_ref="fixture:scan-canary",
                    suite_ref=frozen,
                )["approval_ref"]
                skills.publish(
                    name="watch_skill",
                    version=1,
                    approval_ref=approval,
                    effective_window=2,
                )
                canary = suite(20)
                self.assertTrue(
                    skills.monitor(name="watch_skill", version=1, suite_ref=canary)[
                        "passed"
                    ]
                )
                approval = skills.approve(
                    name="watch_skill",
                    version=1,
                    approver="human",
                    credential_ref="fixture:scan-full",
                    suite_ref=canary,
                )["approval_ref"]
                skills.publish(
                    name="watch_skill",
                    version=1,
                    approval_ref=approval,
                    fraction=1,
                    effective_window=2,
                )
                second = scan_request(seed=2, start=90)
                source.write_text(
                    json.dumps(
                        {
                            "window_id": 2,
                            "expected_through": 169,
                            "observed_through": 169,
                            "request": second,
                        }
                    )
                )
                result = scans.tick("loop", force=True)
                self.assertEqual(result["status"], "COMPLETED", result)
                self.assertEqual(
                    result["skill_usage"]["report"]["operation"], "scan_window"
                )
                self.assertEqual(scans.status("loop")["watermark"], 2)
                revised = feedback.submit(
                    request_id="false-positive",
                    kind="alert_feedback",
                    payload={
                        "alert_id": alert["alert_id"],
                        "label": "false_positive",
                        "operator": "analyst",
                        "source_kind": "internal_event",
                    },
                )
                self.assertEqual(
                    skills.learn_from_feedback(
                        event_id=revised["event_id"],
                        name="watch_skill",
                        context=context,
                    )["decision"],
                    "AUDIT_ONLY",
                )
            finally:
                scans.close()
                feedback.close()
                skills.close()

    def test_multi_metric_series_are_not_cross_wired(self):
        request = scan_request()
        factor = request["factors"][0]
        factors = [{**factor, "metric_id": "first"}, {**factor, "metric_id": "second"}]
        noise = np.random.default_rng(7).normal(size=80).tolist()
        with self.assertRaises(ValueError):
            hunter_scan(request["days"], request["residual"], factors, lags=[2])
        result = hunter_scan(
            request["days"],
            request["residual"],
            factors,
            lags=[2],
            metric_series={"first": request["residual"], "second": noise},
        )
        records = result["manifest"]["attempts"]
        self.assertGreater(abs(records[0]["correlation"]), 0.8)
        self.assertLess(abs(records[1]["correlation"]), 0.4)

    def test_multi_metric_confirmation_uses_current_metric_responses(self):
        request = scan_request(start=100)
        factor = request["factors"][0]
        factors = [{**factor, "metric_id": "first"}, {**factor, "metric_id": "second"}]
        items = [
            {
                "alert_id": key,
                "factor_id": "driver",
                "metric_id": key,
                "discovery_window": [0, 79],
                "lag": 2,
                "correlation": 0.9,
            }
            for key in ("first", "second")
        ]
        with self.assertRaises(ValueError):
            confirm_watchlist(items, request["days"], request["residual"], factors)
        result = confirm_watchlist(
            items,
            request["days"],
            request["residual"],
            factors,
            metric_series={
                "first": request["residual"],
                "second": (-np.array(request["residual"])).tolist(),
            },
        )
        self.assertTrue(result["results"][0]["confirmed"])
        self.assertFalse(result["results"][1]["confirmed"])
        self.assertLess(result["results"][1]["correlation"], -0.8)

    def test_statistical_memory_executes_posterior_without_skill_prior(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GovernedPriorStore(Path(tmp) / "state.db")
            try:
                context = {
                    "metric": "conversion",
                    "population": "eligible",
                    "assignment_version": "v1",
                }
                old = {"arm_key": "control", "successes": 20, "trials": 100}
                ref = store.registry.add_asset("data", old)
                store.observe(
                    task_id="old", period=1, context=context, **old, data_ref=ref
                )
                store.observe(
                    task_id="renamed-task",
                    period=1,
                    context=context,
                    **old,
                    data_ref=ref,
                )
                self.assertEqual(
                    store.db.execute(
                        "SELECT count(*) FROM prior_observations"
                    ).fetchone()[0],
                    1,
                )
                current = {"arm_key": "control", "successes": 21, "trials": 100}
                current_ref = store.registry.add_asset("data", current)
                result = store.estimate_rate(
                    task_id="current",
                    context=context,
                    arm_key="control",
                    current_period=2,
                    data_ref=current_ref,
                )
                self.assertFalse(result["method_memory_used"])
                self.assertFalse(result["causal_eligible"])
                self.assertGreater(sum(result["posterior_shape"]), 102)
                self.assertTrue(
                    result["posterior_interval"][0]
                    < result["posterior_mean"]
                    < result["posterior_interval"][1]
                )
            finally:
                store.close()
