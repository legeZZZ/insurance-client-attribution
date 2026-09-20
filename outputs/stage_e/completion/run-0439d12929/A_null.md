# 盲测 A_null

输入、结果和事后真值分别冻结。

状态：SCORED

输入摘要：sha256:1e24c045f8dceb8fec30f2ba413a7409a5c5e6cd3b5f4e57c8655cd4b0e4aa23

结果摘要：sha256:25821bddbe9bd757171ebe2b201d395a248f7023270780d3d093177b789cf019

真值范围：full

```json
{
  "marginal_dependence": {
    "status": "UNKNOWN_TRUTH",
    "predictions": 0
  },
  "conditional_relevance": {
    "status": "UNKNOWN_TRUTH",
    "predictions": 0
  },
  "graph_edges": {
    "status": "UNKNOWN_TRUTH",
    "predictions": 0
  },
  "intervention_effects": {
    "evaluated": 1,
    "total": 1,
    "unavailable": 0,
    "bias": {
      "mean": 0.023001377867571622,
      "se": null,
      "mc_interval_95": [
        null,
        null
      ],
      "n": 1,
      "interval_method": "Student_t_mean"
    },
    "rmse": 0.023001377867571622,
    "coverage": 1.0,
    "coverage_mc_interval_95": [
      0.025,
      1.0
    ],
    "unconditional_coverage": 1.0,
    "width": {
      "mean": 0.3636199194245559,
      "se": null,
      "mc_interval_95": [
        null,
        null
      ],
      "n": 1,
      "interval_method": "Student_t_mean"
    },
    "false_causal_assertions": 0,
    "unlabelled_predictions": 0
  },
  "changed_mechanisms": {
    "status": "UNKNOWN_TRUTH",
    "predictions": 0
  }
}
```
