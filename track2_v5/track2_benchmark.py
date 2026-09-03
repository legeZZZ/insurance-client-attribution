"""Backward-compatible import surface for the renamed benchmark module."""

from .benchmark import _segment_predictive_brier, _split, run_benchmark

__all__ = ["_segment_predictive_brier", "_split", "run_benchmark"]
