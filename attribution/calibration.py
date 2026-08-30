"""Binned calibration layer: learns a reliability map from past outcomes.

Collects (predicted probability, realized 0/1) pairs across periods and
builds a monotone binned adjustment. Applied to the current period's
decision probabilities; the map is deterministic and fully inspectable,
consistent with the auditability narrative (no learned black box).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from typing import Any

BINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.000001)
MIN_BIN_COUNT = 5


class BinnedCalibrator:
    def __init__(self) -> None:
        self.pairs: list[tuple[float, float]] = []

    def add(self, predicted: float, realized: float) -> None:
        predicted_value, realized_value = float(predicted), float(realized)
        if (
            not math.isfinite(predicted_value)
            or not math.isfinite(realized_value)
            or not 0.0 <= predicted_value <= 1.0
            or not 0.0 <= realized_value <= 1.0
        ):
            raise ValueError("predicted and realized must be finite and in [0, 1]")
        self.pairs.append((predicted_value, realized_value))

    def _table(self) -> list[tuple[float, float]] | None:
        """(bin_center, empirical_rate) for bins with enough support."""
        if len(self.pairs) < 2 * MIN_BIN_COUNT:
            return None
        table: list[tuple[float, float]] = []
        for lo, hi in pairwise(BINS):
            bucket = [r for p, r in self.pairs if lo <= p < hi]
            if len(bucket) >= MIN_BIN_COUNT:
                table.append(((lo + hi) / 2, sum(bucket) / len(bucket)))
        return table if len(table) >= 2 else None

    def calibrate(self, predicted: float) -> float:
        if not math.isfinite(predicted) or not 0.0 <= predicted <= 1.0:
            raise ValueError("predicted must be finite and in [0, 1]")
        table = self._table()
        if table is None:
            return predicted  # insufficient history: pass through
        p = min(max(predicted, 0.0), 1.0)
        if p <= table[0][0]:
            return table[0][1]
        if p >= table[-1][0]:
            return table[-1][1]
        for (x0, y0), (x1, y1) in pairwise(table):
            if x0 <= p <= x1:
                w = (p - x0) / (x1 - x0)
                return y0 + w * (y1 - y0)
        return p

    @staticmethod
    def ece(pairs: Sequence[tuple[float, float]]) -> float | None:
        """Expected calibration error over the shared bin grid."""
        if not pairs:
            return None
        if any(
            not math.isfinite(float(predicted))
            or not math.isfinite(float(realized))
            or not 0.0 <= float(predicted) <= 1.0
            or not 0.0 <= float(realized) <= 1.0
            for predicted, realized in pairs
        ):
            raise ValueError("calibration pairs must be finite and in [0, 1]")
        total = len(pairs)
        e = 0.0
        for lo, hi in pairwise(BINS):
            bucket = [(p, r) for p, r in pairs if lo <= p < hi]
            if bucket:
                mp = sum(p for p, _ in bucket) / len(bucket)
                mr = sum(r for _, r in bucket) / len(bucket)
                e += len(bucket) / total * abs(mp - mr)
        return e

    def summary(self) -> dict[str, Any]:
        return {"pairs": len(self.pairs), "table": self._table()}
