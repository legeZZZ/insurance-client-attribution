"""Rate-aware multidimensional root-cause candidate generation.

The input is an aggregate panel, one row per day and scope.  A scope is a
combination of dimensions such as region, channel, version and placement:

    {"day": 40, "scope": {"region": "east", "channel": "paid"},
     "control": {"clicks": 40, "impressions": 1000},
     "treatment": {"clicks": 28, "impressions": 1000}}

This module is inspired by Adtributor/Squeeze-style multidimensional search,
but keeps numerator and denominator throughout.  It generates investigation
candidates only; it does not infer causality.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from .input_validation import validate_rate_panel, validate_windows


def _period(days: Sequence[int], start: int | None, end: int | None) -> set[int]:
    values = {int(day) for day in days}
    if start is None and end is None:
        return values
    return {
        day
        for day in values
        if (start is None or day >= start) and (end is None or day <= end)
    }


def _sum_arm(rows: Iterable[Mapping[str, Any]], arm: str) -> tuple[float, float]:
    rows = list(rows)
    clicks = sum(float(row[arm].get("clicks", 0.0)) for row in rows)
    impressions = sum(float(row[arm].get("impressions", 0.0)) for row in rows)
    return clicks, impressions


def _rate(clicks: float, impressions: float) -> float:
    return clicks / impressions if impressions > 0 else float("nan")


def _safe(value: float) -> float:
    return float(value) if math.isfinite(value) else 0.0


def decompose_rate_mix(
    before: Mapping[Any, Mapping[str, float]],
    after: Mapping[Any, Mapping[str, float]],
    *,
    share_key: str = "share",
    rate_key: str = "rate",
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Decompose a rate change on the probability scale.

    For a common set of cells i, with share s and rate r:

      delta R = sum(s_before * delta r)                 [rate]
              + sum(delta s * r_before)                 [mix]
              + sum(delta s * delta r)                   [interaction]

    The interaction is retained explicitly.  Missing cells or non-unit share
    totals are a contract failure, rather than silently being treated as zero.
    """
    before_keys, after_keys = set(before), set(after)
    if before_keys != after_keys:
        return {
            "status": "DECOMPOSITION_NOT_CLOSED",
            "closed": False,
            "reason": "cell_set_mismatch",
            "missing_in_after": sorted(map(str, before_keys - after_keys)),
            "missing_in_before": sorted(map(str, after_keys - before_keys)),
            "closure_error": None,
        }
    if not before_keys:
        return {
            "status": "DECOMPOSITION_NOT_CLOSED",
            "closed": False,
            "reason": "empty_cell_set",
            "closure_error": None,
        }
    try:
        s_before = {key: float(value[share_key]) for key, value in before.items()}
        s_after = {key: float(value[share_key]) for key, value in after.items()}
        r_before = {key: float(value[rate_key]) for key, value in before.items()}
        r_after = {key: float(value[rate_key]) for key, value in after.items()}
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "status": "DECOMPOSITION_NOT_CLOSED",
            "closed": False,
            "reason": f"invalid_cell:{exc}",
            "closure_error": None,
        }
    sums = (sum(s_before.values()), sum(s_after.values()))
    if not all(
        math.isfinite(value) for value in (*sums, *r_before.values(), *r_after.values())
    ) or any(abs(value - 1.0) > tolerance for value in sums):
        return {
            "status": "DECOMPOSITION_NOT_CLOSED",
            "closed": False,
            "reason": "shares_must_sum_to_one",
            "share_sum_before": sums[0],
            "share_sum_after": sums[1],
            "closure_error": None,
        }
    rate_by_cell = {
        key: s_before[key] * (r_after[key] - r_before[key]) for key in before_keys
    }
    mix_by_cell = {
        key: (s_after[key] - s_before[key]) * r_before[key] for key in before_keys
    }
    interaction_by_cell = {
        key: (s_after[key] - s_before[key]) * (r_after[key] - r_before[key])
        for key in before_keys
    }
    delta = sum(s_after[key] * r_after[key] for key in before_keys) - sum(
        s_before[key] * r_before[key] for key in before_keys
    )
    rate = sum(rate_by_cell.values())
    mix = sum(mix_by_cell.values())
    interaction = sum(interaction_by_cell.values())
    closure_error = delta - rate - mix - interaction

    def display_key(key: Any) -> str:
        return str(key)

    return {
        "status": "CLOSED"
        if abs(closure_error) <= tolerance
        else "DECOMPOSITION_NOT_CLOSED",
        "closed": abs(closure_error) <= tolerance,
        "reason": None
        if abs(closure_error) <= tolerance
        else "floating_point_or_invalid_input",
        "rate": rate,
        "mix": mix,
        "interaction": interaction,
        "delta": delta,
        "closure_error": closure_error,
        "share_sum_before": sums[0],
        "share_sum_after": sums[1],
        "rate_by_cell": {
            display_key(key): value for key, value in rate_by_cell.items()
        },
        "mix_by_cell": {display_key(key): value for key, value in mix_by_cell.items()},
        "interaction_by_cell": {
            display_key(key): value for key, value in interaction_by_cell.items()
        },
        "basis": (
            "probability_difference; rate=before_share*delta_rate; "
            "mix=delta_share*before_rate; interaction=delta_share*delta_rate"
        ),
    }


def _decompose_aggregate(
    before: Mapping[Any, Mapping[str, Any]],
    after: Mapping[Any, Mapping[str, Any]],
    arm: str,
) -> dict[str, Any]:
    before_total = sum(float(item[f"{arm}_impressions"]) for item in before.values())
    after_total = sum(float(item[f"{arm}_impressions"]) for item in after.values())
    if before_total <= 0 or after_total <= 0:
        return {
            "status": "DECOMPOSITION_NOT_CLOSED",
            "closed": False,
            "reason": "non_positive_total_impressions",
            "closure_error": None,
        }
    before_cells = {
        key: {
            "share": item[f"{arm}_impressions"] / before_total,
            "rate": item[f"{arm}_rate"],
        }
        for key, item in before.items()
    }
    after_cells = {
        key: {
            "share": item[f"{arm}_impressions"] / after_total,
            "rate": item[f"{arm}_rate"],
        }
        for key, item in after.items()
    }
    return decompose_rate_mix(before_cells, after_cells)


def _scope_key(
    scope: Mapping[str, Any], dimensions: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (dimension, str(scope.get(dimension, "<missing>"))) for dimension in dimensions
    )


def _aggregate(
    panel: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
    selected_days: set[int],
) -> dict[tuple[tuple[str, str], ...], dict[str, Any]]:
    grouped: dict[tuple[tuple[str, str], ...], list[Mapping[str, Any]]] = defaultdict(
        list
    )
    for row in panel:
        if int(row["day"]) in selected_days:
            grouped[_scope_key(row.get("scope", {}), dimensions)].append(row)
    output: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for key, rows in grouped.items():
        control_clicks, control_imps = _sum_arm(rows, "control")
        treatment_clicks, treatment_imps = _sum_arm(rows, "treatment")
        output[key] = {
            "scope": dict(key),
            "rows": rows,
            "control_clicks": control_clicks,
            "control_impressions": control_imps,
            "treatment_clicks": treatment_clicks,
            "treatment_impressions": treatment_imps,
            "control_rate": _rate(control_clicks, control_imps),
            "treatment_rate": _rate(treatment_clicks, treatment_imps),
        }
    return output


def _daily_gap_change(
    panel: Sequence[Mapping[str, Any]],
    scope_filter: Mapping[str, str],
    baseline_days: set[int],
    current_days: set[int],
) -> tuple[list[float], list[float]]:
    daily: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in panel:
        scope = row.get("scope", {})
        if all(
            str(scope.get(k, "<missing>")) == str(v) for k, v in scope_filter.items()
        ):
            daily[int(row["day"])].append(row)

    def day_gap(rows: Sequence[Mapping[str, Any]]) -> float:
        cc, ci = _sum_arm(rows, "control")
        tc, ti = _sum_arm(rows, "treatment")
        return _safe(_rate(tc, ti) - _rate(cc, ci))

    return (
        [day_gap(daily[day]) for day in sorted(baseline_days) if day in daily],
        [day_gap(daily[day]) for day in sorted(current_days) if day in daily],
    )


def _candidate_metrics(
    panel: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, str],
    dimensions: Sequence[str],
    baseline_days: set[int],
    current_days: set[int],
    min_impressions: int,
) -> dict[str, Any] | None:
    baseline = _aggregate(panel, dimensions, baseline_days)
    current = _aggregate(panel, dimensions, current_days)
    full_key = tuple((d, str(candidate[d])) for d in dimensions)
    base = baseline.get(full_key)
    now = current.get(full_key)
    if base is None or now is None:
        return None
    total_current = sum(v["treatment_impressions"] for v in current.values())
    total_baseline = sum(v["treatment_impressions"] for v in baseline.values())
    if (
        min(base["treatment_impressions"], now["treatment_impressions"])
        < min_impressions
    ):
        return None

    candidate_filter = {d: str(candidate[d]) for d in dimensions}
    base_gap = _safe(base["treatment_rate"] - base["control_rate"])
    current_gap = _safe(now["treatment_rate"] - now["control_rate"])
    gap_change = current_gap - base_gap
    treatment_rate_change = _safe(now["treatment_rate"] - base["treatment_rate"])
    control_rate_change = _safe(now["control_rate"] - base["control_rate"])
    base_share = base["treatment_impressions"] / max(total_baseline, 1.0)
    current_share = now["treatment_impressions"] / max(total_current, 1.0)
    # Cell-level contributions use the same probability-scale convention as
    # the overall decomposition.  The third term is essential when both rate
    # and composition move in the same period.
    # Validate the candidate contribution against the complete cell universe,
    # not as a fake one-cell population whose shares do not sum to one.
    cell_decomposition = _decompose_aggregate(baseline, current, "treatment")
    rate_contribution = base_share * treatment_rate_change
    mix_contribution = (current_share - base_share) * base["treatment_rate"]
    interaction_contribution = (current_share - base_share) * treatment_rate_change
    candidate_contribution_change = (
        current_share * now["treatment_rate"] - base_share * base["treatment_rate"]
    )
    candidate_closure_error = candidate_contribution_change - (
        rate_contribution + mix_contribution + interaction_contribution
    )

    complement_base = [v for key, v in baseline.items() if key != full_key]
    complement_now = [v for key, v in current.items() if key != full_key]
    cb_imps = sum(v["treatment_impressions"] for v in complement_base)
    cn_imps = sum(v["treatment_impressions"] for v in complement_now)
    cb_gap = _safe(
        sum(v["treatment_clicks"] for v in complement_base) / max(cb_imps, 1.0)
        - sum(v["control_clicks"] for v in complement_base)
        / max(sum(v["control_impressions"] for v in complement_base), 1.0)
    )
    cn_gap = _safe(
        sum(v["treatment_clicks"] for v in complement_now) / max(cn_imps, 1.0)
        - sum(v["control_clicks"] for v in complement_now)
        / max(sum(v["control_impressions"] for v in complement_now), 1.0)
    )
    complement_change = cn_gap - cb_gap
    isolation = abs(gap_change - complement_change) / max(
        abs(gap_change) + abs(complement_change), 1e-6
    )
    _baseline_gap_values, current_gap_values = _daily_gap_change(
        panel, candidate_filter, baseline_days, current_days
    )
    current_sign = -1.0 if gap_change < 0 else 1.0
    same_direction = [value * current_sign > 0 for value in current_gap_values]
    stability = sum(same_direction) / max(len(same_direction), 1)
    coverage = current_share
    impact = (
        abs(rate_contribution) + abs(mix_contribution) + abs(interaction_contribution)
    )
    scope_focus = 1.0 - coverage
    # The score ranks investigation value. It is deliberately not a p-value.
    priority = (
        impact
        * (0.5 + 0.5 * isolation)
        * (0.5 + 0.5 * stability)
        * (0.5 + 0.5 * scope_focus)
    )
    return {
        "scope": {key: value for key, value in candidate.items()},
        "depth": len(candidate),
        "baseline_days": [min(baseline_days), max(baseline_days)]
        if baseline_days
        else [],
        "current_days": [min(current_days), max(current_days)] if current_days else [],
        "baseline_gap": base_gap,
        "current_gap": current_gap,
        "gap_change": gap_change,
        "treatment_rate_before": base["treatment_rate"],
        "treatment_rate_after": now["treatment_rate"],
        "control_rate_before": base["control_rate"],
        "control_rate_after": now["control_rate"],
        "treatment_rate_change": treatment_rate_change,
        "control_rate_change": control_rate_change,
        "rate_contribution": rate_contribution,
        "mix_contribution": mix_contribution,
        "interaction_contribution": interaction_contribution,
        "treatment_share_before": base_share,
        "treatment_share_after": current_share,
        "candidate_contribution_change": candidate_contribution_change,
        "candidate_closure_error": candidate_closure_error,
        "decomposition_status": cell_decomposition["status"],
        "decomposition_closure_error": cell_decomposition.get("closure_error"),
        "decomposition_basis": (
            "rate=before_share*delta_rate; mix=delta_share*before_rate; "
            "interaction=delta_share*delta_rate"
        ),
        "coverage": coverage,
        "scope_focus": scope_focus,
        "isolation": isolation,
        "stability": stability,
        "complement_gap_change": complement_change,
        "baseline_impressions": int(base["treatment_impressions"]),
        "current_impressions": int(now["treatment_impressions"]),
        "priority": priority,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
    }


def _deduplicate(
    candidates: Sequence[Mapping[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in sorted(
        candidates, key=lambda item: float(item["priority"]), reverse=True
    ):
        scope = candidate["scope"]
        # Keep a broad candidate only when it adds a materially different
        # scope; otherwise the most specific candidate is more actionable.
        if any(
            set(scope.items()).issuperset(set(other["scope"].items()))
            and len(scope) > len(other["scope"])
            and abs(float(candidate["gap_change"]) - float(other["gap_change"])) < 0.002
            for other in kept
        ):
            continue
        kept.append(dict(candidate))
        if len(kept) >= top_k:
            break
    return kept


def discover_rate_candidates(
    panel: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
    baseline_window: tuple[int, int],
    current_window: tuple[int, int],
    min_impressions: int = 100,
    top_k: int = 10,
    beam_width: int = 30,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Find rate-metric anomaly subspaces with a Squeeze-style beam search."""
    if not panel or not dimensions:
        raise ValueError("panel and dimensions must be non-empty")
    validate_windows(baseline_window, current_window)
    if min_impressions < 0:
        raise ValueError("min_impressions must be non-negative")
    if top_k <= 0 or beam_width <= 0:
        raise ValueError("top_k and beam_width must be positive")
    days = [int(row["day"]) for row in panel]
    baseline_days = _period(days, baseline_window[0], baseline_window[1])
    current_days = _period(days, current_window[0], current_window[1])
    if not baseline_days or not current_days:
        raise ValueError("baseline and current windows must contain panel days")
    input_validation = validate_rate_panel(
        panel, dimensions, baseline_days, current_days
    )
    max_depth = max_depth or len(dimensions)
    # Canonical dimension order makes pruning invariant to caller field order.
    dimensions = tuple(sorted(dict.fromkeys(dimensions)))
    values = {
        dimension: sorted(
            {str(row.get("scope", {}).get(dimension, "<missing>")) for row in panel}
        )
        for dimension in dimensions
    }
    all_candidates: list[dict[str, Any]] = []
    beam: list[dict[str, Any]] = [{"scope": {}, "beam_score": float("inf")}]
    for depth in range(1, min(max_depth, len(dimensions)) + 1):
        next_beam: list[dict[str, Any]] = []
        used_signatures = set()
        for beam_item in beam:
            partial = beam_item["scope"]
            unused = [d for d in dimensions if d not in partial]
            for dimension in unused:
                for value in values[dimension]:
                    candidate = {**partial, dimension: value}
                    signature = tuple(sorted(candidate.items()))
                    if signature in used_signatures:
                        continue
                    used_signatures.add(signature)
                    metrics = _candidate_metrics(
                        panel,
                        candidate,
                        tuple(candidate.keys()),
                        baseline_days,
                        current_days,
                        min_impressions,
                    )
                    if metrics is None:
                        continue
                    metrics["beam_score"] = abs(float(metrics["gap_change"]))
                    all_candidates.append(metrics)
                    next_beam.append(
                        {"scope": candidate, "beam_score": metrics["beam_score"]}
                    )
        next_beam.sort(
            key=lambda item: (
                -float(item["beam_score"]),
                tuple(sorted(item["scope"].items())),
            )
        )
        beam = next_beam[:beam_width]
        if not beam:
            break
    ranked = _deduplicate(all_candidates, top_k)

    # Compute overall rates directly because the empty scope is not a lookup key.
    def total_metrics(selected: set[int]) -> dict[str, float]:
        c, ci = _sum_arm(
            (row for row in panel if int(row["day"]) in selected), "control"
        )
        t, ti = _sum_arm(
            (row for row in panel if int(row["day"]) in selected), "treatment"
        )
        return {
            "control_rate": _rate(c, ci),
            "treatment_rate": _rate(t, ti),
            "control_impressions": ci,
            "treatment_impressions": ti,
        }

    before, after = total_metrics(baseline_days), total_metrics(current_days)
    overall_treatment_decomposition = _decompose_aggregate(
        _aggregate(panel, tuple(dimensions), baseline_days),
        _aggregate(panel, tuple(dimensions), current_days),
        "treatment",
    )
    overall_control_decomposition = _decompose_aggregate(
        _aggregate(panel, tuple(dimensions), baseline_days),
        _aggregate(panel, tuple(dimensions), current_days),
        "control",
    )
    overall_summary = {
        "treatment_rate_change": _safe(
            after["treatment_rate"] - before["treatment_rate"]
        ),
        "control_rate_change": _safe(after["control_rate"] - before["control_rate"]),
        "gap_change": _safe(
            (after["treatment_rate"] - after["control_rate"])
            - (before["treatment_rate"] - before["control_rate"])
        ),
        "treatment_decomposition": overall_treatment_decomposition,
        "control_decomposition": overall_control_decomposition,
    }
    return {
        "model": "rate_aware_squeeze_style_beam_search",
        "metric_type": "ratio_of_counts",
        "dimensions": list(dimensions),
        "baseline_window": list(baseline_window),
        "current_window": list(current_window),
        "overall_change": overall_summary,
        "candidate_count_scored": len(all_candidates),
        "candidate_count": len(ranked),
        "input_validation": input_validation,
        "candidates": ranked,
        "claim_policy": "candidate_only_until_randomized_or_quasi_experimental_validation",
        "limitations": [
            "候选名称来自输入面板维度，算法不能命名不存在数据入口的外部因素。",
            "rate/mix/interaction 是概率尺度上的闭合描述性分解，不是因果贡献。",
            "多维搜索使用 beam_width 和 min_impressions，需在留出窗口评估召回与假阳性。",
        ],
    }


def make_demo_panel(seed: int = 20260826, n_days: int = 60) -> dict[str, Any]:
    """Fixture: an unregistered release hurts east/paid/version=8.4."""
    rng = np.random.default_rng(seed)
    panel: list[dict[str, Any]] = []
    for day in range(n_days):
        for region, channel, version in itertools.product(
            ("east", "west"), ("paid", "organic"), ("8.3", "8.4")
        ):
            impressions = int(900 + rng.integers(0, 180))
            base = 0.040 + (0.004 if channel == "organic" else 0.0)
            treatment_rate = base + 0.006
            affected = (
                day >= 40
                and region == "east"
                and channel == "paid"
                and version == "8.4"
            )
            if affected:
                treatment_rate -= 0.022
            control_clicks = round(impressions * base)
            treatment_clicks = round(impressions * treatment_rate)
            panel.append(
                {
                    "day": day,
                    "scope": {"region": region, "channel": channel, "version": version},
                    "control": {"clicks": control_clicks, "impressions": impressions},
                    "treatment": {
                        "clicks": treatment_clicks,
                        "impressions": impressions,
                    },
                }
            )
    return {
        "panel": panel,
        "truth": {
            "affected_scope": {"region": "east", "channel": "paid", "version": "8.4"},
            "onset_day": 40,
            "direction": "negative",
        },
    }


def run_demo(output_path=None) -> dict[str, Any]:
    fixture = make_demo_panel()
    result = discover_rate_candidates(
        fixture["panel"],
        ("region", "channel", "version"),
        baseline_window=(0, 39),
        current_window=(40, 59),
        min_impressions=1000,
        top_k=8,
        beam_width=20,
    )
    result["truth_for_offline_evaluation"] = fixture["truth"]
    if output_path is not None:
        import json
        from pathlib import Path

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result["output_path"] = str(path)
    return result


if __name__ == "__main__":
    from pathlib import Path

    output = (
        Path(__file__).resolve().parent.parent / "outputs" / "lineB_rate_aware_rca.json"
    )
    print(json.dumps(run_demo(output), ensure_ascii=False, indent=2))
