import unittest

from track2_v5.rate_aware_rca import make_demo_panel
from track2_v5.risk_loc import discover_risk_candidates


class RiskLocTests(unittest.TestCase):
    def test_localization_and_nonoverlapping_removal(self):
        f = make_demo_panel()
        r = discover_risk_candidates(
            f["panel"], ["region", "channel", "version"], (0, 39), (40, 59)
        )
        self.assertEqual(r["candidates"][0]["scope"], f["truth"]["affected_scope"])
        ids = [i for c in r["candidates"] for i in c["assigned_atom_ids"]]
        self.assertEqual(len(ids), len(set(ids)))
        for c in r["candidates"]:
            self.assertAlmostEqual(c["risk"], c["r1"] - c["r2"])

    def test_budget_is_respected(self):
        r = discover_risk_candidates(
            make_demo_panel()["panel"],
            ["region", "channel", "version"],
            (0, 39),
            (40, 59),
            max_candidates=1,
        )
        self.assertTrue(r["search_manifest"]["budget_exhausted"])
        self.assertEqual(r["search_manifest"]["evaluated_candidates"], 1)

    def test_exact_null_returns_no_candidates(self):
        panel = []
        for day in range(4):
            for region in ("east", "west"):
                panel.append(
                    {
                        "day": day,
                        "scope": {"region": region},
                        "control": {"clicks": 10, "impressions": 100},
                        "treatment": {"clicks": 10, "impressions": 100},
                    }
                )
        r = discover_risk_candidates(panel, ["region"], (0, 1), (2, 3))
        self.assertEqual(r["candidates"], [])


if __name__ == "__main__":
    unittest.main()
