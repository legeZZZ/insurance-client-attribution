"""InsurSim-Carousel: explicit causal-structure simulator for the carousel case.

DAG (explicit, per v5 §16 requirements):

  device_low_end, user_new_old, channel, placement   (exogenous context)
  bundle T in {old, new}                              (randomized treatment)
  spec factors (text_density, media_aspect_ratio,
    indicator_position, image_component)              (confounded with T in bundle stage)
  image_load_failure ~ f(image_component, device)     (mediator: runtime quality)
  clicked ~ Bernoulli(g(base, T, moderators, mediator))

Ground truth (oracle) is stored separately and sanitized rows never carry it.
Supports matched (in_generator=True) and mismatched (nonlinear + noise)
regimes for the dual backtest required by the plan.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

TRUE_MODERATORS = ("device_low_end",)          # context factor with real moderation
TRUE_COMPONENT_EFFECTS = {                     # per-component effects (used in factorial stage)
    "carousel.text_density": -0.020,
    "carousel.media_aspect_ratio": -0.004,
    "carousel.indicator_position": 0.0,
    "carousel.image_component": -0.012,
}
MEDIATOR_EFFECT = -0.30                        # load failure -> click logit penalty
BASE_CTR = 0.040


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def generate_bundle_stage(
    seed: int,
    n: int = 100_000,
    bundle_logit_effect: float = -0.30,
    moderator_logit_effect: float = -1.20,
    mismatched: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bundle A/B stage: all spec factors move together with T (confounded)."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    clicks = {0: 0, 1: 0}
    impressions = {0: 0, 1: 0}
    for i in range(n):
        device_low_end = int(rng.random() < 0.35)
        user_new_old = "new" if rng.random() < 0.4 else "old"
        channel = str(rng.choice(["organic", "paid", "social"], p=[0.5, 0.3, 0.2]))
        placement = str(rng.choice(["home_top", "home_mid"], p=[0.7, 0.3]))
        t = int(rng.random() < 0.5)

        logit = math.log(BASE_CTR / (1 - BASE_CTR))
        logit += -0.3 * device_low_end + (0.15 if user_new_old == "new" else 0.0)
        logit += {"organic": 0.2, "paid": 0.0, "social": -0.1}[channel]
        if mismatched:
            logit += 0.5 * math.sin(3.0 * (i % 100) / 100.0)  # unobserved nonlinear drift

        # Bundle effect, amplified on low-end devices (true moderation).
        logit += t * (bundle_logit_effect + moderator_logit_effect * device_low_end)

        # Mediator: new image component fails more, especially on low-end devices.
        fail_prob = 0.02 + t * (0.10 + 0.12 * device_low_end)
        image_load_failure = int(rng.random() < fail_prob)
        logit += MEDIATOR_EFFECT * image_load_failure

        if mismatched:
            logit += float(rng.normal(0.0, 0.15))  # extra noise in mismatched regime

        p = _sigmoid(logit)
        clicked = int(rng.random() < p)
        impressions[t] += 1
        clicks[t] += clicked
        rows.append({
            "impression_id": i,
            "_oracle_clicked_potential": clicked,  # sanitized before Agent use
            "_oracle_true_p": p,                   # god-model probability (benchmark floor only)
            "treatment": t,
            "clicked": clicked,
            "device_low_end": device_low_end,
            "user_new_old": user_new_old,
            "channel": channel,
            "placement": placement,
            "image_load_failure": image_load_failure,
            "render_latency_ms": float(120 + t * 80 * device_low_end + rng.normal(0, 20)),
            "qualified_exposure": 1,
        })

    oracle_ctr = {arm: clicks[arm] / impressions[arm] for arm in (0, 1)}
    truth = {
        "oracle_bundle_ate": oracle_ctr[1] - oracle_ctr[0],
        "oracle_ctr": oracle_ctr,
        "true_moderators": list(TRUE_MODERATORS),
        "true_component_effects": dict(TRUE_COMPONENT_EFFECTS),
        "mediator": "image_load_failure",
        "mismatched": mismatched,
    }
    return rows, truth


def generate_factorial_stage(
    seed: int,
    arms: list[dict[str, Any]],
    base_ctr: float = BASE_CTR,
) -> dict[str, list[dict[str, Any]]]:
    """Execute a factorial design: each arm fixes its component levels."""
    rng = np.random.default_rng(seed + 7777)
    arm_rows: dict[str, list[dict[str, Any]]] = {}
    for arm in arms:
        code = arm["design_code"]
        rows = []
        for i in range(arm["planned_impressions"]):
            device_low_end = int(rng.random() < 0.35)
            logit = math.log(base_ctr / (1 - base_ctr)) - 0.3 * device_low_end
            for factor, bit in code.items():
                if bit:
                    effect = TRUE_COMPONENT_EFFECTS.get(factor, 0.0)
                    # Component effects are given on the probability scale;
                    # convert to logit via the derivative at base_ctr.
                    logit += effect / (base_ctr * (1.0 - base_ctr))
            p = _sigmoid(logit)
            rows.append({
                "treatment": 1,
                "clicked": int(rng.random() < p),
                "device_low_end": device_low_end,
            })
        arm_rows[arm["arm_id"]] = rows
    return arm_rows


def sanitize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
