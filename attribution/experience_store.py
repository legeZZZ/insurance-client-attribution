"""Persistent factor experience store: posterior write-back + cross-period loading.

Turns the static factor registry into a learning asset:

- After each attribution period, arm posteriors (Beta shapes) and per-segment
  shrunk effects are written back to a JSON store.
- On the next period, accumulated experience becomes (a) informative Beta
  priors for bundle/segment estimation and (b) one-step-ahead predictions
  for segment effects.
- The shrinkage strength nu is adapted online by a deterministic PID
  controller driven by one-step-ahead prediction error (expert consultation
  2026-08-10: feedback-controlled adaptive shrinkage instead of RL).

Determinism: no randomness anywhere in this module; the same period sequence
always yields the same store trajectory.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DECAY = 0.5  # per-period decay of accumulated pseudo-counts
CAP = 4000.0  # max pseudo-impressions a stored prior may carry
NU_MIN, NU_MAX = 100.0, 2000.0
TARGET_ERR = 0.002  # tolerated one-step-ahead prediction error (prob scale)
MISMATCH_THRESHOLD = 0.008  # prior-deviation alarm level (~4x TARGET_ERR):
# fires on the onset period of structural drift,
# before the decayed store has adapted to it
KP, KI, KD = 0.6, 0.15, 0.3


class FactorExperienceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {
                "version": 1,
                "periods": 0,
                "arms": {},  # arm_key -> {alpha, beta}
                "predictions": {},  # segment_id -> last shrunk effect
                "shrinkage_strength": 500.0,
                "_err_integral": 0.0,
                "_err_prev": None,
            }

    # ---- cross-period prior loading -------------------------------------
    def prior(
        self, arm_key: str, max_total: float | None = None
    ) -> tuple[float, float] | None:
        """Informative Beta prior for an arm, or None on cold start.

        `max_total` caps pseudo-impressions relative to the fresh data size
        (e.g. 0.25 * current impressions) so experience can rescue sparse
        periods but never drowns out rich new evidence.
        """
        if self.data["periods"] == 0:
            return None
        arm = self.data["arms"].get(arm_key)
        if not arm:
            return None
        alpha, beta = float(arm["alpha"]), float(arm["beta"])
        total = alpha + beta
        cap = CAP if max_total is None else min(CAP, max_total)
        if total > cap:
            scale = cap / total
            alpha, beta = alpha * scale, beta * scale
        return alpha, beta

    # ---- posterior write-back -------------------------------------------
    def write_back(self, arm_key: str, shape: tuple[float, float]) -> None:
        """Accumulate a posterior Beta shape into the arm record.

        Old experience decays so the store tracks drift instead of
        freezing at the first period; totals are capped so the prior
        can never overwhelm new experimental data.
        """
        arm = self.data["arms"].get(arm_key, {"alpha": 1.0, "beta": 1.0})
        alpha = DECAY * (arm["alpha"] - 1.0) + shape[0]
        beta = DECAY * (arm["beta"] - 1.0) + shape[1]
        total = alpha + beta
        if total > CAP:
            scale = CAP / total
            alpha, beta = alpha * scale, beta * scale
        self.data["arms"][arm_key] = {"alpha": float(alpha), "beta": float(beta)}

    # ---- segment predictions for the feedback loop ----------------------
    def predict_segment(self, segment_id: str) -> float | None:
        if self.data["periods"] == 0:
            return None
        value = self.data["predictions"].get(segment_id)
        return None if value is None else float(value)

    def update_predictions(self, effects: Mapping[str, float]) -> None:
        self.data["predictions"].update({k: float(v) for k, v in effects.items()})

    # ---- PID-controlled adaptive shrinkage (v6.1, expert consultation) --
    def adapt_shrinkage(self, errors: Mapping[str, float]) -> dict[str, float]:
        """One PID step on log(nu) from one-step-ahead prediction errors.

        e = mean absolute error of last period's segment predictions.
        e > TARGET_ERR  -> shrinkage was wrong (too loose: noise leaked in,
        or too tight: real signal was over-shrunk) -> relax/strengthen via
        the three PID terms; nu stays within [NU_MIN, NU_MAX].
        """
        if not errors:
            return {"nu": self.data["shrinkage_strength"], "skipped": True}  # type: ignore
        e = sum(abs(v) for v in errors.values()) / len(errors)
        err = e - TARGET_ERR
        integral = max(min(self.data["_err_integral"] + err, 0.05), -0.05)
        prev = self.data["_err_prev"]
        derivative = 0.0 if prev is None else err - prev
        step = KP * err + KI * integral + KD * derivative
        nu = self.data["shrinkage_strength"] * math.exp(max(min(step, 0.7), -0.7))
        nu = min(max(nu, NU_MIN), NU_MAX)
        self.data.update(
            {
                "shrinkage_strength": float(nu),
                "_err_integral": float(integral),
                "_err_prev": float(err),
            }
        )
        return {
            "nu": float(nu),
            "mean_abs_error": float(e),
            "p": KP * err,
            "i": KI * integral,
            "d": KD * derivative,
        }

    # ---- mismatch alarm --------------------------------------------------
    def arm_deviation(
        self, arm_key: str, fresh_rate: float, max_total: float | None = None
    ) -> float | None:
        """|prior mean - fresh MLE| for an arm; None on cold start."""
        pr = self.prior(arm_key, max_total=max_total)
        if pr is None:
            return None
        return abs(pr[0] / sum(pr) - fresh_rate)

    @staticmethod
    def mismatch_alarm(deviation: float | None) -> bool:
        """True when the experience prior no longer matches fresh evidence:
        the registered factor structure is likely wrong (onset of mismatch).
        The honest downstream behavior is to flag, widen intervals, or refuse
        — never to silently re-anchor.
        """
        return deviation is not None and deviation > MISMATCH_THRESHOLD

    def end_period(self) -> None:
        self.data["periods"] += 1

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- introspection ---------------------------------------------------
    def summary(self) -> dict[str, Any]:
        return {
            "periods": self.data["periods"],
            "arms": {
                k: round(v["alpha"] + v["beta"], 1)
                for k, v in self.data["arms"].items()
            },
            "shrinkage_strength": round(self.data["shrinkage_strength"], 1),
            "tracked_segments": len(self.data["predictions"]),
        }
