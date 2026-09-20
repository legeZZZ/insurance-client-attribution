# 盲测 A_signal

输入、结果和事后真值分别冻结。

状态：SCORED

输入摘要：sha256:0504fa0e17d363bd623a6f071eb119e8170c5b3c5ef3cdf13d34ad7335cb1509

结果摘要：sha256:fd1bd002b4d3f7867c2e1517cfe811c407cd622dabc697d31972d28b55b1aaf2

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
      "mean": 0.023001377867571615,
      "se": null,
      "mc_interval_95": [
        null,
        null
      ],
      "n": 1,
      "interval_method": "Student_t_mean"
    },
    "rmse": 0.023001377867571615,
    "coverage": 1.0,
    "coverage_mc_interval_95": [
      0.025,
      1.0
    ],
    "unconditional_coverage": 1.0,
    "width": {
      "mean": 0.36361991942455596,
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
