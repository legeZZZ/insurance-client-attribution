"""attribution: Spec-driven open factor mining + Bayesian experiment attribution.

Pure-numpy implementation of the v5 plan:
  Growth UI Spec -> SpecDiff/RenderDiff/RuntimeDiff -> FactorMiner
  -> Bayesian Bundle A/B -> high-dimensional overlapping CATE/HTE
  -> Factorial experiment design -> Posterior decision guard -> Claim Ledger.
"""

__version__ = "0.1.0"
