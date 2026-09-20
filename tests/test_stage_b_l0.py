import unittest

from track2_v5.rate_aware_rca import (
    _atomic_ledger,
    decompose_rate_mix,
    discover_rate_candidates,
    make_demo_panel,
)


class L0Tests(unittest.TestCase):
    def test_crossing_slices_do_not_double_count_atoms(self):
        fixture = make_demo_panel()
        candidates = [
            {"candidate_id": "east", "scope": {"region": "east"}},
            {"candidate_id": "paid", "scope": {"channel": "paid"}},
        ]
        ledger = _atomic_ledger(
            fixture["panel"],
            ("channel", "region", "version"),
            set(range(40)),
            set(range(40, 60)),
            candidates,
        )
        self.assertEqual(ledger["status"], "CLOSED")
        assignments = [
            atom
            for candidate in candidates
            for atom in candidate["atomic_accounting"]["assigned_atom_ids"]
        ]
        self.assertEqual(len(assignments), len(set(assignments)))
        self.assertTrue(
            any(len(a["covering_candidates"]) == 2 for a in ledger["atoms"])
        )
        self.assertAlmostEqual(
            sum(c["atomic_accounting"]["assigned_total"] for c in candidates)
            + ledger["unassigned_total"],
            ledger["total"],
        )
        self.assertLess(abs(ledger["closure_error"]), 1e-10)

    def test_budget_and_pruning_are_explicit(self):
        result = discover_rate_candidates(
            make_demo_panel()["panel"],
            ("region", "channel", "version"),
            (0, 39),
            (40, 59),
            max_candidates=3,
            beam_width=1,
        )
        self.assertEqual(result["search_manifest"]["evaluated_candidates"], 3)
        self.assertTrue(result["search_manifest"]["budget_exhausted"])
        self.assertEqual(len(result["pruning_trace"]), 3)
        self.assertIn(
            "PRUNED_BEAM_WIDTH", {t["status"] for t in result["pruning_trace"]}
        )
        self.assertEqual(len(result["l0_triples"]), result["candidate_count"])

    def test_known_local_anomaly_is_recalled(self):
        for seed in range(5):
            f = make_demo_panel(seed=seed)
            r = discover_rate_candidates(
                f["panel"],
                ("region", "channel", "version"),
                (0, 39),
                (40, 59),
                top_k=8,
                beam_width=20,
            )
            self.assertIn(
                f["truth"]["affected_scope"], [c["scope"] for c in r["candidates"]]
            )
            self.assertLess(abs(r["atomic_ledger"]["closure_error"]), 1e-10)

    def test_invalid_probability_and_budget_refused(self):
        before = {"a": {"share": -1, "rate": 0.2}, "b": {"share": 2, "rate": 0.1}}
        self.assertFalse(decompose_rate_mix(before, before)["closed"])
        for budget in (True, 0, 1.5):
            with self.assertRaises(ValueError):
                discover_rate_candidates(
                    make_demo_panel()["panel"],
                    ("region",),
                    (0, 39),
                    (40, 59),
                    max_candidates=budget,
                )

    def test_missing_cell_cannot_produce_closed_ledger(self):
        f = make_demo_panel()
        rows = [
            r
            for r in f["panel"]
            if not (r["day"] >= 40 and r["scope"] == f["truth"]["affected_scope"])
        ]
        ledger = _atomic_ledger(
            rows,
            ("channel", "region", "version"),
            set(range(40)),
            set(range(40, 60)),
            [],
        )
        self.assertEqual(ledger["status"], "DECOMPOSITION_NOT_CLOSED")
        self.assertIsNone(ledger["assigned_total"])


if __name__ == "__main__":
    unittest.main()
