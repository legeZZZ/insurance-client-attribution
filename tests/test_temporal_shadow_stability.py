import unittest

import numpy as np

from track2_v5.temporal_shadow_stability import diagnose_shadow_stability


class ShadowTests(unittest.TestCase):
    def test_categorical_labels_are_not_ordinal(self):
        x = ["a", "a", "b", "c"] * 10
        y = np.random.default_rng(1).normal(size=40).tolist()
        r = diagnose_shadow_stability(
            list(range(40)), x, y, kind="categorical", replicates=9
        )
        mapped = [{"a": "z", "b": "u", "c": "q"}[v] for v in x]
        other = diagnose_shadow_stability(
            list(range(40)), mapped, y, kind="categorical", replicates=9
        )
        self.assertEqual(r["shadow_scores"], other["shadow_scores"])
        self.assertIsNone(r["formal_qvalue"])
        self.assertFalse(r["changes_claim_eligibility"])

    def test_event_and_continuous_have_distinct_shadow_policies(self):
        x = [0] * 20 + [1] * 10 + [0] * 10
        y = np.random.default_rng(2).normal(size=40).tolist()
        for kind, expected in (
            ("event", "whole_event_circular_shift"),
            ("continuous", "block_order_permutation"),
        ):
            r = diagnose_shadow_stability(
                list(range(40)), x, y, kind=kind, replicates=9
            )
            self.assertEqual(r["shadow_method"], expected)
            self.assertEqual(r["guarantee"], "empirical_only")
            self.assertEqual(len(r["subsamples"]), 5)

    def test_short_series_and_bad_event_fail_explicitly(self):
        r = diagnose_shadow_stability(
            list(range(5)), [0, 1, 0, 1, 0], [1, 2, 3, 4, 5], kind="event"
        )
        self.assertEqual(r["status"], "NOT_APPLICABLE")
        with self.assertRaises(ValueError):
            diagnose_shadow_stability(
                list(range(5)), [0, 2, 0, 1, 0], [1, 2, 3, 4, 5], kind="event"
            )


if __name__ == "__main__":
    unittest.main()
