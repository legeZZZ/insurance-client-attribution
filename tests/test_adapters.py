"""Regression tests for the external data adapter + data contract (v13)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from track2_v5.adapters import load_config, load_line_b_inputs
from track2_v5.data_contract import ContractError, validate_rows

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = PROJECT / "config.example.json"


class TestDataContract(unittest.TestCase):
    def test_metric_panel_requires_impressions(self):
        with self.assertRaises(ContractError):
            validate_rows(
                "metric_panel",
                [
                    {
                        "day": 0,
                        "region": "east",
                        "channel": "paid",
                        "version": "8.4",
                        "control_clicks": 5,
                        "control_impressions": 0,
                        "treatment_clicks": 3,
                        "treatment_impressions": 100,
                    }
                ],
            )

    def test_metric_panel_rejects_duplicate_scope_day(self):
        row = {
            "day": 0,
            "region": "east",
            "channel": "paid",
            "version": "8.4",
            "control_clicks": 5,
            "control_impressions": 100,
            "treatment_clicks": 3,
            "treatment_impressions": 100,
        }
        with self.assertRaises(ContractError):
            validate_rows("metric_panel", [row, dict(row)])

    def test_event_window_must_be_ordered(self):
        with self.assertRaises(ContractError):
            validate_rows(
                "external_events",
                [
                    {
                        "event_id": "e1",
                        "kind": "regulation",
                        "start_day": 9,
                        "end_day": 3,
                    }
                ],
            )


class TestAdapterWithExampleData(unittest.TestCase):
    def test_example_config_loads_all_tables(self):
        config = load_config(EXAMPLE_CONFIG)
        inputs = load_line_b_inputs(config)
        self.assertGreaterEqual(len(inputs["days"]), 20)
        self.assertEqual(len(inputs["control"]), len(inputs["days"]))
        self.assertTrue(inputs["scoped_panel"])
        self.assertTrue(inputs["factor_series"])
        self.assertEqual(inputs["provenance"]["mode"], "company_adapter")

    def test_experiment_id_stripped_without_readouts(self):
        config = load_config(EXAMPLE_CONFIG)
        inputs = load_line_b_inputs(config)
        for change in inputs["registry"]:
            self.assertNotIn("experiment_id", change)

    def test_field_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "panel.csv").write_text(
                "日期,地区,渠道,版本,c_clk,c_imp,t_clk,t_imp\n"
                + "\n".join(f"{d},east,paid,8.4,40,1000,46,1000" for d in range(30))
                + "\n",
                encoding="utf-8",
            )
            (root / "registry.json").write_text(
                json.dumps([{"change_id": "c1", "start_day": 10, "scope": "s"}]),
                encoding="utf-8",
            )
            (root / "events.json").write_text(
                json.dumps(
                    [
                        {
                            "event_id": "e1",
                            "kind": "regulation",
                            "start_day": 20,
                            "end_day": 22,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "config.json").write_text(
                json.dumps(
                    {
                        "data_dir": ".",
                        "files": {
                            "metric_panel": "panel.csv",
                            "change_registry": "registry.json",
                            "external_events": "events.json",
                        },
                        "field_mapping": {
                            "metric_panel": {
                                "日期": "day",
                                "地区": "region",
                                "渠道": "channel",
                                "版本": "version",
                                "c_clk": "control_clicks",
                                "c_imp": "control_impressions",
                                "t_clk": "treatment_clicks",
                                "t_imp": "treatment_impressions",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            inputs = load_line_b_inputs(load_config(root / "config.json"))
            self.assertEqual(len(inputs["days"]), 30)
            self.assertAlmostEqual(inputs["control"][0], 0.04)


if __name__ == "__main__":
    unittest.main()


class TestTrackingEvents(unittest.TestCase):
    def _events(self):
        rows = []
        for day in range(30):
            for arm in ("control", "treatment"):
                for i in range(100):
                    rows.append(
                        {
                            "day": day,
                            "event_name": "impression",
                            "subject_id": f"h{day}{arm}{i}",
                            "arm": arm,
                            "region": "east",
                            "channel": "paid",
                            "version": "8.4",
                        }
                    )
                for i in range(4 if arm == "control" else 5):
                    rows.append(
                        {
                            "day": day,
                            "event_name": "click",
                            "subject_id": f"c{day}{arm}{i}",
                            "arm": arm,
                            "region": "east",
                            "channel": "paid",
                            "version": "8.4",
                        }
                    )
        return rows

    def test_aggregate_events_to_panel(self):
        from track2_v5.adapters import aggregate_events_to_panel

        panel = validate_rows(
            "metric_panel",
            aggregate_events_to_panel(validate_rows("tracking_events", self._events())),
        )
        self.assertEqual(len(panel), 30)
        row = next(r for r in panel if r["day"] == 0)
        self.assertEqual(row["control_impressions"], 100)
        self.assertEqual(row["treatment_clicks"], 5)

    def test_tracking_only_config_aggregates(self):
        import json
        import tempfile

        from track2_v5.adapters import load_config, load_line_b_inputs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import csv
            import io

            buf = io.StringIO()
            w = csv.DictWriter(
                buf,
                fieldnames=[
                    "day",
                    "event_name",
                    "subject_id",
                    "arm",
                    "region",
                    "channel",
                    "version",
                ],
            )
            w.writeheader()
            for e in self._events():
                w.writerow(e)
            (root / "events.csv").write_text(buf.getvalue(), encoding="utf-8")
            (root / "registry.json").write_text(
                json.dumps([{"change_id": "c1", "start_day": 10, "scope": "s"}]),
                encoding="utf-8",
            )
            (root / "events.json").write_text(
                json.dumps(
                    [
                        {
                            "event_id": "e1",
                            "kind": "regulation",
                            "start_day": 20,
                            "end_day": 22,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "config.json").write_text(
                json.dumps(
                    {
                        "data_dir": ".",
                        "files": {
                            "metric_panel": "absent.csv",
                            "tracking_events": "events.csv",
                            "change_registry": "registry.json",
                            "external_events": "events.json",
                        },
                    }
                ),
                encoding="utf-8",
            )
            inputs = load_line_b_inputs(load_config(root / "config.json"))
            self.assertEqual(len(inputs["days"]), 30)

    def test_plain_phone_subject_rejected(self):
        with self.assertRaises(ContractError):
            validate_rows(
                "tracking_events",
                [
                    {
                        "day": 0,
                        "event_name": "click",
                        "subject_id": "13800001234",
                        "arm": "control",
                        "region": "east",
                        "channel": "paid",
                        "version": "8.4",
                    }
                ],
            )
