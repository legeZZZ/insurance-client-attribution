"""Factor mining: scan data for candidate factors, interactions, and heterogeneity signals."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .track2_bayesian import beta_posterior, empirical_bayes_prior, posterior_summary


# ---------------------------------------------------------------------------
# Single-factor scan
# ---------------------------------------------------------------------------

def scan_single_factors(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcome_column: str = "issued",
    segment_columns: Optional[Sequence[str]] = None,
    min_subgroup_size: int = 30,
) -> List[Dict[str, Any]]:
    """Scan segment columns for subgroups with divergent treatment effects.

    Returns candidate factors with control/treatment click-like counts.
    For binary outcomes, treats each row as a Bernoulli trial.
    """
    if segment_columns is None:
        # Auto-detect categorical columns with reasonable cardinality
        segment_columns = _auto_detect_segments(rows, treatment_column, outcome_column)

    candidates: List[Dict[str, Any]] = []
    for col in segment_columns:
        groups = _group_by(rows, col)
        for value, subset in groups.items():
            if len(subset) < min_subgroup_size:
                continue
            ctrl = [r for r in subset if r.get(treatment_column) == 0]
            treat = [r for r in subset if r.get(treatment_column) == 1]
            if len(ctrl) < min_subgroup_size // 2 or len(treat) < min_subgroup_size // 2:
                continue

            ctrl_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in ctrl)
            ctrl_impressions = len(ctrl)
            treat_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in treat)
            treat_impressions = len(treat)

            # Stability heuristic: rate difference from global mean
            global_rate = (ctrl_clicks + treat_clicks) / max(1, ctrl_impressions + treat_impressions)
            ctrl_rate = ctrl_clicks / max(1, ctrl_impressions)
            treat_rate = treat_clicks / max(1, treat_impressions)
            raw_effect = treat_rate - ctrl_rate

            candidates.append({
                "factor_id": "%s=%s" % (col, str(value)),
                "factor_name": "%s = %s" % (col, str(value)),
                "source_type": "SEGMENT_DIFF",
                "source_column": col,
                "source_value": value,
                "control": {"clicks": ctrl_clicks, "impressions": ctrl_impressions},
                "treatment": {"clicks": treat_clicks, "impressions": treat_impressions},
                "raw_effect": round(raw_effect, 6),
                "raw_control_rate": round(ctrl_rate, 6),
                "raw_treatment_rate": round(treat_rate, 6),
                "global_rate": round(global_rate, 6),
                "stability": 1.0,  # Would be computed from cross-validation in production
                "experimentability": 1.0 if _is_experimentable(col) else 0.5,
            })
    return candidates


# ---------------------------------------------------------------------------
# Two-way interaction scan
# ---------------------------------------------------------------------------

def scan_interactions(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcome_column: str = "issued",
    segment_columns: Optional[Sequence[str]] = None,
    min_subgroup_size: int = 60,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """Scan two-way interactions between segment columns.

    Only returns combinations where both factors are present in both arms
    with sufficient sample size.
    """
    if segment_columns is None:
        segment_columns = _auto_detect_segments(rows, treatment_column, outcome_column)

    candidates: List[Dict[str, Any]] = []
    cols = list(segment_columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col_a, col_b = cols[i], cols[j]
            groups = _group_by_two(rows, col_a, col_b)
            for (val_a, val_b), subset in groups.items():
                if len(subset) < min_subgroup_size:
                    continue
                ctrl = [r for r in subset if r.get(treatment_column) == 0]
                treat = [r for r in subset if r.get(treatment_column) == 1]
                if len(ctrl) < min_subgroup_size // 3 or len(treat) < min_subgroup_size // 3:
                    continue

                ctrl_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in ctrl)
                ctrl_impressions = len(ctrl)
                treat_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in treat)
                treat_impressions = len(treat)

                raw_effect = (treat_clicks / max(1, treat_impressions)) - (ctrl_clicks / max(1, ctrl_impressions))

                candidates.append({
                    "factor_id": "%s=%s&%s=%s" % (col_a, str(val_a), col_b, str(val_b)),
                    "factor_name": "%s=%s & %s=%s" % (col_a, str(val_a), col_b, str(val_b)),
                    "source_type": "INTERACTION_DIFF",
                    "source_columns": [col_a, col_b],
                    "source_values": [val_a, val_b],
                    "control": {"clicks": ctrl_clicks, "impressions": ctrl_impressions},
                    "treatment": {"clicks": treat_clicks, "impressions": treat_impressions},
                    "raw_effect": round(raw_effect, 6),
                    "stability": 0.8,  # Interactions are less stable
                    "experimentability": 0.7,  # Harder to experiment on interactions
                })

    # Sort by absolute raw effect and take top_k
    candidates.sort(key=lambda x: abs(x["raw_effect"]), reverse=True)
    return candidates[:top_k]


# ---------------------------------------------------------------------------
# Continuous factor binning scan
# ---------------------------------------------------------------------------

def scan_binned_continuous(
    rows: Sequence[Mapping[str, Any]],
    column: str,
    treatment_column: str = "treatment",
    outcome_column: str = "issued",
    bins: int = 4,
    min_subgroup_size: int = 30,
) -> List[Dict[str, Any]]:
    """Bin a continuous column and scan each bin for treatment effect heterogeneity."""
    values = [float(r.get(column, 0) or 0) for r in rows if r.get(column) is not None]
    if len(values) < bins * min_subgroup_size:
        return []

    # Quantile-based binning
    sorted_vals = sorted(values)
    bin_edges = [sorted_vals[int(len(sorted_vals) * i / bins)] for i in range(bins + 1)]
    bin_edges[0] = float("-inf")
    bin_edges[-1] = float("inf")

    def _bin_label(value: float) -> str:
        for i in range(bins):
            if bin_edges[i] <= value < bin_edges[i + 1]:
                return "bin_%d_[%.2f,%.2f)" % (i, bin_edges[i], bin_edges[i + 1])
        return "bin_%d" % (bins - 1)

    candidates: List[Dict[str, Any]] = []
    for i in range(bins):
        subset = [r for r in rows if bin_edges[i] <= float(r.get(column, 0) or 0) < bin_edges[i + 1]]
        if len(subset) < min_subgroup_size:
            continue
        ctrl = [r for r in subset if r.get(treatment_column) == 0]
        treat = [r for r in subset if r.get(treatment_column) == 1]
        if len(ctrl) < min_subgroup_size // 2 or len(treat) < min_subgroup_size // 2:
            continue

        ctrl_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in ctrl)
        treat_clicks = sum(int(r.get(outcome_column, 0) or 0) for r in treat)
        raw_effect = (treat_clicks / max(1, len(treat))) - (ctrl_clicks / max(1, len(ctrl)))

        candidates.append({
            "factor_id": "%s_%s" % (column, _bin_label(bin_edges[i] + 0.001)),
            "factor_name": "%s in %s" % (column, _bin_label(bin_edges[i] + 0.001)),
            "source_type": "BINNED_DIFF",
            "source_column": column,
            "control": {"clicks": ctrl_clicks, "impressions": len(ctrl)},
            "treatment": {"clicks": treat_clicks, "impressions": len(treat)},
            "raw_effect": round(raw_effect, 6),
            "stability": 0.9,
            "experimentability": 0.8,
        })
    return candidates


# ---------------------------------------------------------------------------
# Candidate factor report builder
# ---------------------------------------------------------------------------

def build_factor_report(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str = "treatment",
    outcome_column: str = "issued",
    segment_columns: Optional[Sequence[str]] = None,
    min_subgroup_size: int = 30,
    top_k: int = 15,
) -> Dict[str, Any]:
    """Full factor mining pipeline: single factors + interactions + binned continuous."""
    # Single factor scan
    single = scan_single_factors(rows, treatment_column, outcome_column, segment_columns, min_subgroup_size)

    # Interaction scan
    interactions = scan_interactions(rows, treatment_column, outcome_column, segment_columns, min_subgroup_size, top_k)

    # Try to bin continuous columns
    binned: List[Dict[str, Any]] = []
    if segment_columns:
        for col in segment_columns:
            if _is_numeric_column(rows, col):
                binned.extend(scan_binned_continuous(rows, col, treatment_column, outcome_column, bins=4, min_subgroup_size=min_subgroup_size))

    all_candidates = single + interactions + binned

    # Compute empirical Bayes prior for shrinkage
    all_groups = []
    for c in all_candidates:
        all_groups.append(c["control"])
        all_groups.append(c["treatment"])
    global_prior = empirical_bayes_prior(all_groups)

    # Apply shrinkage to raw effects
    for c in all_candidates:
        c_ctrl = c["control"]
        c_treat = c["treatment"]
        # Shrink both arms
        post_ctrl = posterior_summary(beta_posterior(c_ctrl["clicks"], c_ctrl["impressions"], global_prior))
        post_treat = posterior_summary(beta_posterior(c_treat["clicks"], c_treat["impressions"], global_prior))
        c["shrunken_control_rate"] = post_ctrl["mean"]
        c["shrunken_treatment_rate"] = post_treat["mean"]
        c["shrunken_effect"] = round(post_treat["mean"] - post_ctrl["mean"], 6)
        c["shrinkage_weight"] = post_ctrl.get("shrinkage_weight", 0.5)

    # Sort by absolute shrunken effect
    all_candidates.sort(key=lambda x: abs(x.get("shrunken_effect", x["raw_effect"])), reverse=True)

    return {
        "scan_type": "factor_mining_v1",
        "total_candidates": len(all_candidates),
        "single_factors": len(single),
        "interactions": len(interactions),
        "binned_continuous": len(binned),
        "global_prior": {"alpha": global_prior[0], "beta": global_prior[1]},
        "top_candidates": all_candidates[:top_k],
        "all_candidates": all_candidates,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auto_detect_segments(
    rows: Sequence[Mapping[str, Any]],
    treatment_column: str,
    outcome_column: str,
    max_cardinality: int = 20,
) -> List[str]:
    """Auto-detect categorical columns suitable for segmentation."""
    if not rows:
        return []
    candidates = []
    for col in rows[0].keys():
        if col in (treatment_column, outcome_column, "user_id", "net_premium", "gross_premium", "refund", "cancel"):
            continue
        if col.startswith("_"):
            continue
        unique_vals = set(str(r.get(col, "<missing>")) for r in rows)
        if 2 <= len(unique_vals) <= max_cardinality:
            candidates.append(col)
    return candidates


def _group_by(rows: Sequence[Mapping[str, Any]], column: str) -> Dict[Any, List[Mapping[str, Any]]]:
    groups: Dict[Any, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row.get(column, "<missing>")].append(row)
    return dict(groups)


def _group_by_two(rows: Sequence[Mapping[str, Any]], col_a: str, col_b: str) -> Dict[Tuple[Any, Any], List[Mapping[str, Any]]]:
    groups: Dict[Tuple[Any, Any], List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row.get(col_a, "<missing>"), row.get(col_b, "<missing>"))].append(row)
    return dict(groups)


def _is_experimentable(column: str) -> bool:
    """Heuristic: some columns are easier to experiment on than others."""
    easily_experimentable = {"channel", "product_mix", "season", "layout", "media_aspect_ratio", "text_density", "indicator_position"}
    return column in easily_experimentable


def _is_numeric_column(rows: Sequence[Mapping[str, Any]], column: str) -> bool:
    """Check if a column contains numeric values."""
    for row in rows:
        val = row.get(column)
        if val is not None:
            try:
                float(val)
                return True
            except (ValueError, TypeError):
                return False
    return False
