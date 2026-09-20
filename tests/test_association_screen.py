import unittest

import numpy as np

from track2_v5.association_discovery import discover_association_factors
from track2_v5.association_screen import dependence_statistic


class ScreenTests(unittest.TestCase):
    def test_symmetric_nonlinearity_and_tied_ranks(self):
        x = np.arange(-50, 51, dtype=float)
        self.assertAlmostEqual(dependence_statistic(x, x * x, "pearson"), 0.0)
        self.assertAlmostEqual(
            dependence_statistic(x, x * x, "spearman"), 0.0, places=2
        )
        self.assertGreater(dependence_statistic(x, x * x, "dcor"), 0.4)
        self.assertAlmostEqual(
            dependence_statistic([1, 1, 2, 3], [4, 4, 2, 0], "spearman"), -1.0
        )
        self.assertEqual(dependence_statistic([1, 1, 1, 1], [1, 2, 3, 4], "dcor"), 0.0)

    def test_discovery_and_holdout_keep_dcor_and_unsigned_direction(self):
        rng = np.random.default_rng(27)
        x = rng.uniform(-2, 2, 200)
        y = x * x
        result = discover_association_factors(
            list(range(200)),
            y.tolist(),
            [],
            factor_series=[
                {
                    "factor_id": "quadratic",
                    "days": list(range(200)),
                    "values": x.tolist(),
                }
            ],
            discovery_days=list(range(100)),
            holdout_days=list(range(110, 200)),
            statistic_method="dcor",
            max_lag=0,
            smoothing_window=1,
            derived_layers=("level",),
            seasonal_period=None,
            bootstrap_reps=99,
        )
        candidate = result["candidates"][0]
        self.assertEqual(candidate["statistic_method"], "dcor")
        self.assertEqual(candidate["direction"], "unsigned_dependency")
        self.assertEqual(candidate["confirmation_status"], "CONFIRMED_ASSOCIATION")
        self.assertEqual(result["test_family_contract"]["statistic"], "absolute_dcor")

    def test_bad_method_and_nonfinite_input_refused(self):
        # Published dcor example: collinear 4-D rows reduce to these 1-D distances.
        self.assertAlmostEqual(
            dependence_statistic([1, 5, 9, 13], [1, 0, 0, 1], "dcor"),
            0.5266403,
            places=6,
        )
        with self.assertRaises(ValueError):
            dependence_statistic([1, 2, 3, 4], [1, 2, 3, 4], "unknown")
        with self.assertRaises(ValueError):
            dependence_statistic([1, 2, 3, float("nan")], [1, 2, 3, 4], "dcor")


if __name__ == "__main__":
    unittest.main()
