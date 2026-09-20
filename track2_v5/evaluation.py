"""Truth-separated evaluation; missing/unknown labels never become true negatives."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import beta, t

from .contracts import finite

TRUTH_KEYS = (
    "marginal_dependence",
    "conditional_relevance",
    "graph_edges",
    "intervention_effects",
    "changed_mechanisms",
)


def binomial_interval(hits, n):
    if not n:
        return [None, None]
    return [
        float(beta.ppf(0.025, hits, n - hits + 1)) if hits else 0.0,
        float(beta.ppf(0.975, hits + 1, n - hits)) if hits < n else 1.0,
    ]


def mean_interval(values, *, bounded=False):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"mean": None, "se": None, "mc_interval_95": [None, None], "n": 0}
    mean = float(values.mean())
    se = float(values.std(ddof=1) / math.sqrt(len(values))) if len(values) > 1 else None
    radius = float(t.ppf(0.975, len(values) - 1)) * se if se is not None else None
    interval = [mean - radius, mean + radius] if radius is not None else [None, None]
    if bounded:
        if np.any((values < 0) | (values > 1)):
            raise ValueError("bounded observations must lie in [0,1]")
        radius = math.sqrt(math.log(40.0) / (2 * len(values)))
        interval = [max(0.0, mean - radius), min(1.0, mean + radius)]
    return {
        "mean": mean,
        "se": se,
        "mc_interval_95": interval,
        "n": len(values),
        "interval_method": "Hoeffding_95_bounded_mean" if bounded else "Student_t_mean",
    }


def validate_truth(truth):
    if set(TRUTH_KEYS) - set(truth):
        raise ValueError(
            "all five distinct truth tables required; use [] for explicitly empty and null for unknown"
        )
    for key in TRUTH_KEYS:
        rows = truth[key]
        if rows is None:
            continue
        if not isinstance(rows, list) or any(
            not isinstance(r, dict) or not r.get("id") for r in rows
        ):
            raise ValueError("truth table requires objects with id")
        if len({r["id"] for r in rows}) != len(rows):
            raise ValueError("duplicate truth id")
        for row in rows:
            if key == "intervention_effects":
                finite(row["effect"], "truth effect")
            elif not isinstance(row.get("positive"), bool):
                raise ValueError("explicit positive/negative truth labels required")
    return truth


def score_predictions(predictions, truth):
    validate_truth(truth)
    scores = {}
    for key in TRUTH_KEYS:
        table = truth[key]
        predicted = predictions.get(key, [])
        if len({p["id"] for p in predicted}) != len(predicted):
            raise ValueError("duplicate prediction id")
        if table is None:
            scores[key] = {"status": "UNKNOWN_TRUTH", "predictions": len(predicted)}
            continue
        labels = {r["id"]: r for r in table}
        if key == "intervention_effects":
            errors = []
            widths = []
            covered = 0
            unavailable = 0
            false_causal = 0
            by_id = {r["id"]: r for r in predicted}
            for name, row in labels.items():
                pred = by_id.get(name, {})
                if pred.get("causal_eligible") and not row.get("identifiable", True):
                    false_causal += 1
                if pred.get("estimate") is None or pred.get("interval") is None:
                    unavailable += 1
                    continue
                est = finite(pred["estimate"], "estimate")
                lo, hi = map(float, pred["interval"])
                if not math.isfinite(lo + hi) or lo > hi:
                    raise ValueError("invalid interval")
                errors.append(est - row["effect"])
                widths.append(hi - lo)
                covered += lo <= row["effect"] <= hi
            scores[key] = {
                "evaluated": len(errors),
                "total": len(table),
                "unavailable": unavailable,
                "bias": mean_interval(errors),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
                "coverage": covered / len(errors) if errors else None,
                "coverage_mc_interval_95": binomial_interval(covered, len(errors)),
                "unconditional_coverage": covered / len(table) if table else None,
                "width": mean_interval(widths),
                "false_causal_assertions": false_causal,
                "unlabelled_predictions": len(set(by_id) - set(labels)),
            }
        else:
            selected = {r["id"] for r in predicted if r.get("selected", True)}
            positive = {r["id"] for r in table if r["positive"]}
            negative = set(labels) - positive
            tp = len(selected & positive)
            fp = len(selected & negative)
            unknown = selected - set(labels)
            scores[key] = {
                "tp": tp,
                "fp": fp,
                "fn": len(positive - selected),
                "tn": len(negative - selected),
                "fdp": fp / max(1, tp + fp),
                "power": tp / len(positive) if positive else None,
                "unknown_selected": sorted(unknown),
                "complete_truth": not unknown,
                "discoveries": len(selected),
            }
    return scores


def normalize_result(result):
    """Only map fields whose semantics are explicit in the actual engine report."""
    predictions = {k: [] for k in TRUTH_KEYS}
    result = result.get("result", result)
    pub = result.get("publication", {})
    effect = pub.get("effect_estimate")
    # Different routes expose effect dictionaries through statistical_uncertainty.
    if not pub and "contracts" in result:
        from .publication import publish_conclusion

        pub = publish_conclusion(result["contracts"])
    if pub:
        stats = pub.get("statistical_uncertainty", {})
        predictions["intervention_effects"].append(
            {
                "id": "effect",
                "estimate": stats.get("effect", effect),
                "interval": stats.get("interval_95", stats.get("interval")),
                "causal_eligible": pub.get("claim_type")
                in {
                    "RANDOMIZED_EFFECT",
                    "COMPONENT_RANDOMIZED_EFFECT",
                    "OBSERVATIONAL_EFFECT_UNDER_ASSUMPTIONS",
                },
            }
        )
    scan = result.get("scan", result)
    candidates = scan.get("watchlist", scan.get("candidates", []))
    selected = {
        c["factor_id"]
        for c in candidates
        if c.get("confirmation_status", "CONFIRMED_ASSOCIATION")
        == "CONFIRMED_ASSOCIATION"
    }
    predictions["marginal_dependence"] = [
        {"id": key, "selected": True} for key in sorted(selected)
    ]
    graph = result.get("consensus_time_expanded_edges", [])
    graph_ids = {
        f"{edge['source'][0]}->{edge['target'][0]}@{edge['target'][1] - edge['source'][1]}"
        for edge in graph
    }
    predictions["graph_edges"] = [
        {"id": key, "selected": True} for key in sorted(graph_ids)
    ]
    # Conditional relevance is intentionally not inferred from marginal selections.
    mechanism = result.get("mechanism_attribution", {})
    intervals = mechanism.get("bootstrap_intervals") or {}
    predictions["changed_mechanisms"] = [
        {"id": key, "selected": True}
        for key, interval in intervals.items()
        if interval[0] > 0 or interval[1] < 0
    ]
    return predictions
