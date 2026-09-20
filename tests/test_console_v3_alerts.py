#!/usr/bin/env python3
"""Regression tests for the v3 console backend additions:
alert board (trend + conflict), alert lifecycle, factor management.
Runs against a fresh seed in a temp workspace; never touches demo data."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import console_v2  # noqa: E402


def _seed(tmp: Path) -> Path:
    """Run the real seed script, then copy artifacts to a temp dir."""
    subprocess.run([sys.executable, str(PROJECT / "tools" / "seed_console_v2.py")],
                   check=True, capture_output=True)
    src = PROJECT / "runtime_data" / "console_v2"
    dst = tmp / "console_v2"
    shutil.copytree(src, dst)
    return dst


class AlertBoardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="v3-console-test-"))
        cls.workdir = _seed(cls._tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_alerts_include_conflict_and_trend(self):
        data = console_v2.alerts(self.workdir)
        ids = {a["alert_id"] for a in data["alerts"]}
        self.assertIn("conflict-cfg-carousel-0917", ids)
        self.assertTrue(any(i.startswith("trend-") for i in ids))
        conflict = next(a for a in data["alerts"]
                        if a["alert_id"] == "conflict-cfg-carousel-0917")
        self.assertEqual(conflict["level"], "high")
        self.assertEqual(conflict["conclusion"]["factor_id"],
                         "homepage.carousel_exposure")
        self.assertEqual(conflict["state"]["status"], "open")

    def test_lifecycle_and_idempotency(self):
        body = {"request_id": "t-1", "alert_id": "conflict-cfg-carousel-0917",
                "action": "confirm", "operator": "tester"}
        first = console_v2.alert_action(self.workdir, body)
        self.assertEqual(first["status"], "confirmed")
        replay = console_v2.alert_action(self.workdir, body)
        self.assertTrue(replay.get("idempotent"))
        states = console_v2._alert_states(self.workdir)
        self.assertEqual(states["conflict-cfg-carousel-0917"]["status"],
                         "confirmed")

    def test_dismiss_requires_reason(self):
        with self.assertRaises(ValueError):
            console_v2.alert_action(self.workdir, {
                "request_id": "t-2", "alert_id": "trend-x",
                "action": "dismiss", "operator": "tester"})

    def test_consistent_config_produces_no_conflict(self):
        data = console_v2.alerts(self.workdir)
        self.assertNotIn("conflict-cfg-feed-0915",
                         {a["alert_id"] for a in data["alerts"]})


class FactorManageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="v3-factor-test-"))
        cls.workdir = _seed(cls._tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_create_operator_factor(self):
        result = console_v2.factor_manage(self.workdir, {
            "action": "create", "operator": "op-test",
            "factor": {"factor_id": "operator.test_event",
                       "name": "测试事件", "category": "临时策略",
                       "mechanism": "单测录入", "available_day": 140}})
        self.assertTrue(result["ok"])
        self.assertEqual(result["factor"]["source_type"], "operator-entry")
        listed = console_v2.factors(self.workdir)["factors"]
        self.assertIn("operator.test_event",
                      {f["factor_id"] for f in listed})

    def test_create_never_overwrites_registered(self):
        with self.assertRaises(ValueError):
            console_v2.factor_manage(self.workdir, {
                "action": "create", "operator": "op-test",
                "factor": {"factor_id": "campaign.sms_push",
                           "name": "x", "category": "y", "mechanism": "z"}})

    def test_disable_enable_roundtrip(self):
        out = console_v2.factor_manage(self.workdir, {
            "action": "disable", "operator": "op-test",
            "factor": {"factor_id": "market.noise_index"}})
        self.assertEqual(out["status"], "disabled")
        out = console_v2.factor_manage(self.workdir, {
            "action": "enable", "operator": "op-test",
            "factor": {"factor_id": "market.noise_index"}})
        self.assertEqual(out["status"], "active")

    def test_operator_required(self):
        with self.assertRaises(ValueError):
            console_v2.factor_manage(self.workdir, {
                "action": "disable", "operator": "",
                "factor": {"factor_id": "market.noise_index"}})

    def test_ledger_tracks_versions(self):
        console_v2.factor_manage(self.workdir, {
            "action": "create", "operator": "op-test",
            "factor": {"factor_id": "operator.ledger_probe",
                       "name": "台账探针", "category": "配置变更",
                       "mechanism": "验证台账", "available_day": 1}})
        ledger = console_v2.factor_ledger(self.workdir)["ledger"]
        probe = [r for r in ledger if r["factor_id"] == "operator.ledger_probe"]
        self.assertEqual(len(probe), 1)
        self.assertEqual(probe[0]["body"]["source_type"], "operator-entry")


if __name__ == "__main__":
    unittest.main()
