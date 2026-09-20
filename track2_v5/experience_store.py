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
        from .persistence import atomic_json

        atomic_json(self.path, self.data)

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


class GovernedPriorStore:
    """Versioned statistical memory. Method retrieval never supplies these parameters."""

    def __init__(self, path):
        from .hypothesis_registry import HypothesisRegistry

        self.registry = HypothesisRegistry(path)
        self.db = self.registry.db
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS prior_observations(id TEXT PRIMARY KEY, period INTEGER NOT NULL, context_ref TEXT NOT NULL, body TEXT NOT NULL);
        """)

    def close(self):
        self.registry.close()

    def observe(
        self, *, task_id, period, context, arm_key, successes, trials, data_ref
    ):
        from .contracts import digest, integer

        period, successes, trials = (
            integer(period, "period"),
            integer(successes, "successes"),
            integer(trials, "trials"),
        )
        if (
            not task_id
            or period < 0
            or not 0 <= successes <= trials
            or trials < 1
            or set(context) != {"metric", "population", "assignment_version"}
        ):
            raise ValueError(
                "bound binomial counts, period and complete statistical context required"
            )
        asset = self.registry.asset(data_ref)
        if (
            asset["status"] != "VALID"
            or asset["kind"] != "data"
            or asset["body"].get("successes") != successes
            or asset["body"].get("trials") != trials
            or asset["body"].get("arm_key") != arm_key
        ):
            raise ValueError("prior observation counts must match current evidence")
        body = {
            "task_id": task_id,
            "period": period,
            "context": context,
            "arm_key": arm_key,
            "successes": successes,
            "trials": trials,
            "data_ref": data_ref,
        }
        ref = digest({"task": task_id, "data": data_ref, "arm": arm_key})
        context_ref = digest(context)
        with self.registry.transaction():
            for row in self.db.execute("SELECT id,body FROM prior_observations"):
                previous = json.loads(row["body"])
                if previous["data_ref"] == data_ref and previous["arm_key"] == arm_key:
                    if any(
                        previous[k] != body[k]
                        for k in ("period", "context", "successes", "trials")
                    ):
                        raise ValueError(
                            "same statistical observations cannot be relabeled or counted in another period"
                        )
                    return {"observation_ref": row["id"]}
            old = self.db.execute(
                "SELECT body FROM prior_observations WHERE id=?", (ref,)
            ).fetchone()
            if old and json.loads(old[0]) != body:
                raise ValueError(
                    "statistical observation revision requires a new data version"
                )
            self.db.execute(
                "INSERT OR IGNORE INTO prior_observations VALUES (?,?,?,?)",
                (ref, period, context_ref, json.dumps(body)),
            )
            self.registry._audit("STATISTICAL_MEMORY_OBSERVED", {"ref": ref, **body})
        return {"observation_ref": ref}

    def prior_for(
        self,
        *,
        context,
        arm_key,
        current_period,
        fresh_successes,
        fresh_trials,
        max_fraction=0.25,
    ):
        from .contracts import digest, integer, finite

        current_period = integer(current_period, "current_period")
        fresh_successes = integer(fresh_successes, "fresh_successes")
        fresh_trials = integer(fresh_trials, "fresh_trials")
        if (
            not 0 <= fresh_successes <= fresh_trials
            or fresh_trials < 1
            or not 0 < finite(max_fraction, "max_fraction") <= 0.25
        ):
            raise ValueError("valid fresh binomial data and prior cap required")
        observations = [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT body FROM prior_observations WHERE context_ref=? AND period<? ORDER BY period",
                (digest(context), current_period),
            )
        ]
        eligible = [
            o
            for o in observations
            if o["arm_key"] == arm_key
            and self.registry.asset(o["data_ref"])["status"] == "VALID"
        ]
        if not eligible:
            return {
                "prior": None,
                "reason": "NO_COMPATIBLE_VALID_HISTORY",
                "method_retrieval_used": False,
            }
        successes = sum(
            o["successes"] * DECAY ** (current_period - o["period"]) for o in eligible
        )
        failures = sum(
            (o["trials"] - o["successes"]) * DECAY ** (current_period - o["period"])
            for o in eligible
        )
        cap = min(CAP, max_fraction * fresh_trials)
        total = successes + failures
        if total > cap:
            successes, failures = successes * cap / total, failures * cap / total
        a, b = 1 + successes, 1 + failures
        from scipy.stats import betabinom

        lower, upper = betabinom.ppf([0.005, 0.995], fresh_trials, a, b)
        mismatch = not lower <= fresh_successes <= upper
        # A failed predictive check discards borrowed information for this task.
        result = {
            "prior": None if mismatch else [a, b],
            "reason": "PREDICTIVE_MISMATCH" if mismatch else "COMPATIBLE",
            "predictive_interval": [float(lower), float(upper)],
            "historical_refs": [o["data_ref"] for o in eligible],
            "effective_pseudo_trials": 0 if mismatch else successes + failures,
            "context_ref": digest(context),
            "method_retrieval_used": False,
            "causal_eligible": False,
        }
        with self.registry.transaction():
            self.registry._audit("STATISTICAL_PRIOR_CHECKED", result)
        return result

    def estimate_rate(self, *, task_id, context, arm_key, current_period, data_ref):
        from .contracts import digest
        from scipy.stats import beta

        asset = self.registry.asset(data_ref)
        if (
            asset["status"] != "VALID"
            or asset["kind"] != "data"
            or asset["body"].get("arm_key") != arm_key
        ):
            raise ValueError("current binomial evidence required")
        data = asset["body"]
        checked = self.prior_for(
            context=context,
            arm_key=arm_key,
            current_period=current_period,
            fresh_successes=data["successes"],
            fresh_trials=data["trials"],
        )
        a, b = checked["prior"] or [1.0, 1.0]
        a += data["successes"]
        b += data["trials"] - data["successes"]
        result = {
            "task_id": task_id,
            "data_ref": data_ref,
            "context_ref": digest(context),
            "prior_check": checked,
            "posterior_shape": [a, b],
            "posterior_mean": a / (a + b),
            "posterior_interval": beta.ppf([0.025, 0.975], a, b).tolist(),
            "claim_type": "DESCRIPTIVE_FACT",
            "causal_eligible": False,
            "method_memory_used": False,
        }
        ref = self.registry.add_asset(
            "manifest",
            result,
            dependencies=[data_ref, *checked.get("historical_refs", [])],
        )
        return {**result, "evidence_ref": ref}
