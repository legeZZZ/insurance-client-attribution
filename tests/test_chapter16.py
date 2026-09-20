"""Chapter 16 real-process proposals, human input and next-window integration."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from test_stage_d import metric_request, scan_request

from track2_v5.cognitive_loop import CognitiveLoop
from track2_v5.feedback_service import FeedbackService
from track2_v5.scan_factor_bridge import registry_factors
from track2_v5.skill_governance import SkillGovernance


class Chapter16Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "state.db"
        self.factor_db = self.root / "factors.db"
        self.loop = CognitiveLoop(self.db)
        self.addCleanup(self.loop.close)
        self.skills = SkillGovernance(self.db)
        self.addCleanup(self.skills.close)

    def trace(self, index, operation="check_metric", request=None):
        data = request or metric_request(index)
        ref = self.skills.registry.add_asset("data", data)
        return self.skills.capture(
            task_id=str(index),
            data_ref=ref,
            context={"workflow": "check"},
            operation=operation,
            author="author",
        )

    def alert(self):
        request = scan_request()
        path = self.root / "scan.json"
        path.write_text(
            json.dumps(
                {
                    "window_id": 0,
                    "observed_through": 79,
                    "expected_through": 79,
                    "request": request,
                }
            )
        )
        scans = self.loop.scans
        scans.configure(name="c", input_path=path, test_budget=30)
        scans.start("c")
        result = scans.tick("c", force=True)
        self.assertEqual(result["status"], "COMPLETED", result)
        return scans.alerts("c")[0]

    def supplement(self, request_id="supplement", snapshots=None):
        req = scan_request()
        rows = (
            snapshots
            if snapshots is not None
            else [
                {"day": d, "value": v}
                for d, v in zip(req["days"], req["factors"][0]["values"])
            ]
        )
        return self.loop.respond(
            request_id=request_id,
            kind="factor_supplement",
            factor_db_path=str(self.factor_db),
            payload={
                "factor_id": "manual",
                "operator": "ops",
                "note": "declared event",
                "current_window": 0,
                "available_day": 79,
                "factor_kind": "internal_event",
                "snapshots": rows,
            },
        )

    def test_parallel_workers_export_and_no_release(self):
        traces = [self.trace(i) for i in range(3)]
        proposal = self.skills.propose(
            name="metric_skill",
            trace_ids=[t["trace_id"] for t in traces],
            applicability={"workflow": "check"},
        )
        audits = [
            a
            for a in self.skills.registry.audit()
            if a["event"] == "PARALLEL_SKILL_ANALYSIS"
        ]
        pids = {a["analyst_pid"] for a in audits[-1]["body"]["analyses"]}
        self.assertEqual(len(pids), 3)
        self.assertNotIn(os.getpid(), pids)
        self.assertEqual(len(proposal["spec"]["rules"]), 1)
        exported = self.skills.export_markdown(name="metric_skill")
        self.assertIn('"source_trace_ids"', exported["markdown"])
        self.assertFalse(exported["execution_eligible"])

    def test_parallel_conflict_does_not_create_skill(self):
        a = self.trace(1)
        b = self.trace(
            2,
            "check_overlap",
            {
                "rows": [{"treatment": 0, "g": "a"}, {"treatment": 1, "g": "a"}],
                "group_column": "g",
            },
        )
        result = self.skills.propose(
            name="conflict",
            trace_ids=[a["trace_id"], b["trace_id"]],
            applicability={"workflow": "check"},
        )
        self.assertTrue(result["conflicts"])
        with self.assertRaises(KeyError):
            self.skills.get("conflict")

    def test_failed_trace_no_verified_patch(self):
        trace = self.trace(
            1,
            "check_overlap",
            {"rows": [{"treatment": 1, "g": "a"}], "group_column": "g"},
        )
        result = self.skills.propose(
            name="failure",
            trace_ids=[trace["trace_id"]],
            applicability={"workflow": "check"},
        )
        self.assertEqual(result["reason"], "no_verified_executable_correction")

    def test_supplement_next_window_complete_and_no_imputation(self):
        result = self.supplement()
        self.assertEqual(result["registration"]["eligible_from_window"], 1)
        for window, as_of in [(0, 79), (1, 78)]:
            factors, _ = registry_factors(
                self.factor_db,
                days=list(range(80)),
                as_of=as_of,
                window=window,
                existing=[],
            )
            self.assertEqual(factors, [])
        factors, report = registry_factors(
            self.factor_db, days=list(range(80)), as_of=79, window=1, existing=[]
        )
        self.assertEqual(report["added"], ["manual"])
        self.assertEqual(factors[0]["source_type"], "human_reported")
        factors, report = registry_factors(
            self.factor_db, days=list(range(81)), as_of=80, window=1, existing=[]
        )
        self.assertFalse(factors)
        self.assertEqual(report["skipped"][0]["reason"], "incomplete_global_snapshots")

    def test_supplement_bad_snapshots_atomic(self):
        for rows in [
            [{"day": 80, "value": 1}],
            [{"day": 0, "value": 1}, {"day": 0, "value": 2}],
            [{"day": 0, "value": float("nan")}],
        ]:
            with self.assertRaises(ValueError):
                self.supplement(str(len(str(rows))), rows)
        self.assertFalse(self.loop.feedback.ledger()["entries"])

    def test_scan_reads_registry_and_freezes_current_window(self):
        self.supplement()
        req = scan_request()
        req["factors"] = []
        path = self.root / "bridge.json"
        payload = {
            "window_id": 0,
            "observed_through": 79,
            "expected_through": 79,
            "request": req,
        }
        path.write_text(json.dumps(payload))
        scans = self.loop.scans
        scans.configure(
            name="bridge",
            input_path=path,
            test_budget=30,
            factor_db_path=self.factor_db,
        )
        scans.start("bridge")
        first = scans.tick("bridge", force=True)
        self.assertEqual(first["registry_intake"]["added"], [])
        payload["window_id"] = 1
        path.write_text(json.dumps(payload))
        second = scans.tick("bridge", force=True)
        self.assertEqual(second["status"], "COMPLETED", second)
        self.assertEqual(second["registry_intake"]["added"], ["manual"])
        self.assertLessEqual(second["tests_charged"], 30)
        self.assertTrue(scans.alerts("bridge"))
        self.assertEqual(
            scans.tick("bridge", force=True)["status"], "ALREADY_PROCESSED"
        )

    def test_real_alert_feedback_proposal_and_retry(self):
        alert = self.alert()
        params = {
            "request_id": "useful",
            "kind": "alert_feedback",
            "payload": {
                "alert_id": alert["alert_id"],
                "label": "useful",
                "operator": "ops",
            },
            "skill_name": "watch_skill",
            "context": {"workflow": "c_line"},
        }
        result = self.loop.respond(**params)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["claim_promotion_allowed"])
        self.assertEqual(result["skill_proposal"]["spec"]["claim_ceiling"], "WATCHLIST")
        self.assertEqual(self.loop.respond(**params), result)
        skills_count = self.skills.db.execute(
            "SELECT COUNT(*) FROM governed_skills"
        ).fetchone()[0]
        self.assertEqual(skills_count, 1)
        self.assertFalse(
            self.skills.get("watch_skill")["lifecycle"]["execution_eligible"]
        )
        self.assertEqual(self.loop.scans.alerts("c")[0]["status"], "WATCHLIST")

    def test_revision_rejects_stale_learning_and_false_positive_audit(self):
        alert = self.alert()
        base = {"alert_id": alert["alert_id"], "operator": "ops"}
        first = self.loop.respond(
            request_id="yes", kind="alert_feedback", payload={**base, "label": "useful"}
        )
        second = self.loop.respond(
            request_id="no",
            kind="alert_feedback",
            payload={**base, "label": "false_positive"},
            skill_name="watch_skill",
            context={"workflow": "c_line"},
        )
        self.assertTrue(second["skill_proposal"]["negative_example_retained"])
        with self.assertRaises(ValueError):
            self.skills.learn_from_feedback(
                event_id=first["feedback"]["event_id"],
                name="watch_skill",
                context={"workflow": "c_line"},
            )
        entries = self.loop.feedback.ledger()["entries"]
        self.assertEqual([e["is_current"] for e in entries], [False, True])
        self.assertEqual(
            second["feedback"]["supersedes"], first["feedback"]["event_id"]
        )

    def test_invalid_alert_and_spoofed_source_rejected(self):
        with self.assertRaises(ValueError):
            self.loop.respond(
                request_id="bad",
                kind="alert_feedback",
                payload={"alert_id": "missing", "label": "useful", "operator": "ops"},
            )
        alert = self.alert()
        with self.assertRaises(ValueError):
            self.loop.respond(
                request_id="badkind",
                kind="alert_feedback",
                payload={
                    "alert_id": alert["alert_id"],
                    "label": "useful",
                    "operator": "ops",
                    "source_kind": "fake",
                },
            )
        self.skills.registry.invalidate(alert["evidence_ref"], reason="corrected")
        with self.assertRaises(ValueError):
            self.loop.respond(
                request_id="invalidated",
                kind="alert_feedback",
                payload={
                    "alert_id": alert["alert_id"],
                    "label": "useful",
                    "operator": "ops",
                },
            )

    def test_candidate_review_queue_and_persistent_ledger(self):
        alert = self.alert()
        result = self.loop.respond(
            request_id="candidate",
            kind="candidate_review",
            alert_id=alert["alert_id"],
            payload={
                "factor_id": alert["factor_id"],
                "decision": "confirmed",
                "operator": "ops",
                "current_window": 0,
            },
        )
        self.assertFalse(result["claim_promotion_allowed"])
        store = FeedbackService(self.db)
        try:
            self.assertEqual(
                store.queue()[0]["status"], "AWAITING_STATISTICAL_VALIDATION"
            )
            self.assertEqual(store.ledger()["entries"][0]["entry_type"], "HUMAN_LABEL")
        finally:
            store.close()

    def test_same_event_learning_is_idempotent(self):
        alert = self.alert()
        event = self.loop.respond(
            request_id="learn",
            kind="alert_feedback",
            payload={
                "alert_id": alert["alert_id"],
                "label": "useful",
                "operator": "ops",
            },
        )["feedback"]
        params = {
            "event_id": event["event_id"],
            "name": "watch_skill",
            "context": {"workflow": "c_line"},
        }
        first = self.skills.learn_from_feedback(**params)
        self.assertEqual(first, self.skills.learn_from_feedback(**params))
        with self.assertRaises(ValueError):
            self.skills.learn_from_feedback(**{**params, "name": "different"})

    def test_candidate_supplement_registers_human_event(self):
        alert = self.alert()
        result = self.loop.respond(
            request_id="add",
            kind="candidate_review",
            alert_id=alert["alert_id"],
            factor_db_path=str(self.factor_db),
            payload={
                "factor_id": alert["factor_id"],
                "decision": "supplemented",
                "operator": "ops",
                "note": "missed SMS",
            },
            supplement={
                "factor_id": "sms",
                "operator": "ops",
                "note": "missed SMS",
                "current_window": 0,
                "available_day": 79,
            },
        )
        self.assertEqual(result["registration"]["factor_id"], "sms")
        self.assertEqual(result["registration"]["eligible_from_window"], 1)
        self.assertEqual(len(self.loop.feedback.ledger()["entries"]), 2)

    def test_labels_change_next_window_budget_without_changing_test_limit(self):
        request = scan_request()
        template = request["factors"][0]
        request["factors"] = [
            {**template, "factor_id": f"{kind}-{i}", "kind": kind}
            for kind in ["noisy", "useful"]
            for i in range(4)
        ]
        request["budget"] = 8
        path = self.root / "calibration.json"
        payload = {
            "window_id": 0,
            "expected_through": 79,
            "observed_through": 79,
            "request": request,
        }
        path.write_text(json.dumps(payload))
        scans = self.loop.scans
        scans.configure(name="calibrate", input_path=path, test_budget=200)
        scans.start("calibrate")
        self.assertEqual(scans.tick("calibrate", force=True)["status"], "COMPLETED")
        alerts = scans.alerts("calibrate")
        self.assertEqual(len(alerts), 8)
        for i, alert in enumerate(alerts):
            self.loop.respond(
                request_id=f"label-{i}",
                kind="alert_feedback",
                payload={
                    "alert_id": alert["alert_id"],
                    "operator": "ops",
                    "label": "false_positive" if alert["kind"] == "noisy" else "useful",
                },
            )
        self.assertEqual(
            self.loop.feedback.calibration(), {"noisy": 0.5, "useful": 1.5}
        )
        payload["window_id"] = 1
        path.write_text(json.dumps(payload))
        result = scans.tick("calibrate", force=True)
        frozen = self.skills.registry.asset(result["data_ref"])["body"]
        self.assertEqual(frozen["budget_multipliers"], {"noisy": 0.5, "useful": 1.5})
        self.assertEqual(frozen["test_budget"], 200)
        self.assertLessEqual(result["tests_charged"], 200)


if __name__ == "__main__":
    unittest.main()
