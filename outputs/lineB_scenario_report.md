# 归因报告 · 线 B · 开放因子发现（分层异常+三层因子+下一窗口验证）

- 场景：`line_b`
- 生成时间：2026-08-31T15:25:12+00:00
- API 执行耗时：9.24s（计算链路真实执行；数据模式为 competition_deidentified）

## 关键指标

| 指标 | 值 |
|---|---|
| unregistered_change_recall | 1.0 |
| external_alignment_accuracy | 1.0 |
| unknown_label_honesty | 1.0 |
| att_per_experiment_rmse_naive | 10.233 |
| att_per_experiment_rmse_hierarchical | 5.552 |
| naive_total | 116.37 |
| hierarchical_total | 119.35 |
| rate_candidate_count | 8 |
| rate_candidates_scored | 26 |

## 关键输出

```json
{
  "external_associations": [
    {
      "event_id": "ext_regulation",
      "kind": "regulation",
      "window_deviation": -86.23,
      "claim_type": "TEMPORAL_ASSOCIATION",
      "note": "外生事件不可随机化；仅报告与指标的共同变化，不作因果断言。",
      "alignment": "ALIGNED"
    }
  ],
  "unregistered_alerts": [
    {
      "alert": "UNEXPLAINED_STEP_SUSPECTED",
      "onset_day": 39,
      "step_score": -42.796779169555535,
      "absolute_step": 30.56,
      "direction": "down",
      "note": "未注册变更，或已注册变动的线上效果与实验 ATT 不一致（解释赤字）；上涨和下降均检测。"
    },
    {
      "alert": "UNEXPLAINED_STEP_SUSPECTED",
      "onset_day": 54,
      "step_score": -31.55681335830488,
      "absolute_step": 25.23,
      "direction": "down",
      "note": "未注册变更，或已注册变动的线上效果与实验 ATT 不一致（解释赤字）；上涨和下降均检测。"
    }
  ],
  "unknown_bucket": {
    "window_start_day": 50,
    "mean_residual_late_window": -95.77,
    "claim_type": "UNEXPLAINED",
    "policy": "残差不建模、不摊派、不假装分解。"
  },
  "association_discovery": {
    "model": "line_b_association_factor_discovery",
    "claim_policy": "association_only_until_randomized_or_quasi_experimental_validation",
    "candidate_generation": "source adapters enumerate observable internal and authorized external snapshots; ranking does not invent unobserved factor names.",
    "anomaly_windows": [
      {
        "start_day": 37,
        "end_day": 41
      },
      {
        "start_day": 52,
        "end_day": 56
      }
    ],
    "candidate_count": 14,
    "input_validation": {
      "status": "PASS",
      "component": "association_discovery",
      "used_sample_count": 60,
      "excluded_sample_count": 0,
      "exclusion_reasons": [],
      "checks_performed": [
        "finite",
        "equal_length",
        "unique_days",
        "strictly_increasing_days",
        "forward_discovery_holdout",
        "sorted_non_overlapping_anomaly_windows",
        "unique_factor_series",
        "unique_events"
      ],
      "factor_series_count": 4,
      "event_count": 2,
      "anomaly_window_count": 2
    },
    "search_manifest": {
      "factors_considered": 4,
      "scopes_considered": 3,
      "lags_considered": 29,
      "metrics_considered": 1,
      "M": 4,
      "D": 3,
      "S": 3,
      "L": 29,
      "K": 1,
      "candidate_series_considered": 12,
      "comparisons": 1044,
      "N": 1044,
      "candidate_series_comparisons": 348,
      "valid_comparisons": 348,
      "block_length": 4,
      "bootstrap_replicates": 199,
      "bootstrap_method": "detrended_moving_block_independent_null_max_t",
      "seasonal_period": 7,
      "derived_layers": [
        "level",
        "velocity",
        "acceleration"
      ],
      "smoothing_window": 3,
      "selection_policy": "discovery_then_holdout_then_validation",
      "selection_set_digest": "sha256:e5e0b83d17cd01bc",
      "bh_is_auxiliary": true,
      "post_selection_warning": "BH 仅报告锁定候选集合内的辅助 q 值；跨 lag 选择后的可信防线是 holdout。"
    },
    "tested_lag_count": 348,
    "bh_q_survivors": 0,
    "holdout_survivors": 0,
    "holdout_window": [
      50,
      59
    ],
    "discovery_window": [
      0,
      49
    ],
    "event_candidate_coverage": 1.0,
    "candidates": [
      {
        "factor_id": "internal.audit.unregistered_release",
        "source_type": "internal_event",
        "kind": "release_audit",
        "scope": null,
        "source_uri": "deidentified://internal-release-audit/day-40",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "start_day": 40,
        "end_day": 40,
        "matched_window": {
          "start_day": 37,
          "end_day": 41
        },
        "distance_days": 0,
        "alignment_score": 1.0,
        "window_residual_mean": -68.3,
        "scope_match": 0.85,
        "source_reliability": 0.9,
        "association_score": 0.765,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "line_a_or_gray_release",
        "candidate_id": "cand-001"
      },
      {
        "factor_id": "internal.page_latency_p95.level",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "level",
        "transform": "identity",
        "unit": "ms",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": -0.5842543872883281,
        "lag_days": -3,
        "coverage": 0.94,
        "n_pairs": 47,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.05,
        "holdout": {
          "correlation": -0.03530673119622166,
          "coverage": 0.7,
          "n_pairs": 7,
          "survives": false
        },
        "scope_match": 0.92,
        "source_reliability": 0.9,
        "source_uri": "deidentified://internal-observability/page-latency",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.459575,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-002"
      },
      {
        "factor_id": "internal.checkout_error_rate.level",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "level",
        "transform": "identity",
        "unit": "rate",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": -0.6093224358831067,
        "lag_days": 0,
        "coverage": 1.0,
        "n_pairs": 50,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.04,
        "holdout": {
          "correlation": -0.03323901839562359,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.88,
        "source_reliability": 0.88,
        "source_uri": "deidentified://internal-observability/checkout-errors",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.452985,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-003"
      },
      {
        "factor_id": "external.competitor_campaign",
        "source_type": "external_event",
        "kind": "competitor_marketing",
        "scope": null,
        "source_uri": "deidentified://authorized-event-feed/competitor-campaign",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "start_day": 51,
        "end_day": 54,
        "matched_window": {
          "start_day": 52,
          "end_day": 56
        },
        "distance_days": 0,
        "alignment_score": 0.75,
        "window_residual_mean": -85.31,
        "scope_match": 0.6,
        "source_reliability": 0.65,
        "association_score": 0.2925,
        "claim_type": "TEMPORAL_ASSOCIATION",
        "evidence_level": "TEMPORAL_ASSOCIATION",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-004"
      },
      {
        "factor_id": "external.fx_rate_usd_cny.velocity",
        "parent_factor_id": "external.fx_rate_usd_cny",
        "derived_layer": "velocity",
        "transform": "first_difference",
        "unit": "delta_per_day(cny_per_usd)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "macro",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "global",
        "correlation": -0.6055684952563372,
        "lag_days": 13,
        "coverage": 0.74,
        "n_pairs": 37,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.045,
        "holdout": {
          "correlation": 0.0,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.55,
        "source_reliability": 0.7,
        "source_uri": "deidentified://authorized-macro-feed/usd-cny",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.222652,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-005"
      },
      {
        "factor_id": "external.fx_rate_usd_cny.level",
        "parent_factor_id": "external.fx_rate_usd_cny",
        "derived_layer": "level",
        "transform": "identity",
        "unit": "cny_per_usd",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "macro",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "global",
        "correlation": -0.5791212994226089,
        "lag_days": 9,
        "coverage": 0.82,
        "n_pairs": 41,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.06,
        "holdout": {
          "correlation": 0.0,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.55,
        "source_reliability": 0.7,
        "source_uri": "deidentified://authorized-macro-feed/usd-cny",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.209584,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-006"
      },
      {
        "factor_id": "external.competitor_pressure_index.velocity",
        "parent_factor_id": "external.competitor_pressure_index",
        "derived_layer": "velocity",
        "transform": "first_difference",
        "unit": "delta_per_day(pressure_index)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "competitor_marketing",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "paid",
        "correlation": -0.565175874993454,
        "lag_days": -8,
        "coverage": 0.84,
        "n_pairs": 42,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.085,
        "holdout": {
          "correlation": 0.0,
          "coverage": 0.0,
          "n_pairs": 2,
          "survives": false
        },
        "scope_match": 0.62,
        "source_reliability": 0.65,
        "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.208406,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-007"
      },
      {
        "factor_id": "external.competitor_pressure_index.level",
        "parent_factor_id": "external.competitor_pressure_index",
        "derived_layer": "level",
        "transform": "identity",
        "unit": "pressure_index",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "competitor_marketing",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "paid",
        "correlation": -0.5379043876857798,
        "lag_days": -8,
        "coverage": 0.84,
        "n_pairs": 42,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.21,
        "holdout": {
          "correlation": 0.0,
          "coverage": 0.0,
          "n_pairs": 2,
          "survives": false
        },
        "scope_match": 0.62,
        "source_reliability": 0.65,
        "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.171253,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-008"
      },
      {
        "factor_id": "external.competitor_pressure_index.acceleration",
        "parent_factor_id": "external.competitor_pressure_index",
        "derived_layer": "acceleration",
        "transform": "second_difference",
        "unit": "delta2_per_day2(pressure_index)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "competitor_marketing",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "paid",
        "correlation": -0.5120823687374639,
        "lag_days": -8,
        "coverage": 0.84,
        "n_pairs": 42,
        "raw_pvalue": 0.01,
        "bh_q": 0.09157894736842105,
        "max_t_pvalue": 0.335,
        "holdout": {
          "correlation": 0.0,
          "coverage": 0.0,
          "n_pairs": 2,
          "survives": false
        },
        "scope_match": 0.62,
        "source_reliability": 0.65,
        "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.137236,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-009"
      },
      {
        "factor_id": "internal.checkout_error_rate.velocity",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "velocity",
        "transform": "first_difference",
        "unit": "delta_per_day(rate)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": -0.42444686412478977,
        "lag_days": 4,
        "coverage": 0.92,
        "n_pairs": 46,
        "raw_pvalue": 0.005,
        "bh_q": 0.062142857142857146,
        "max_t_pvalue": 0.93,
        "holdout": {
          "correlation": 0.39258850709799364,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.88,
        "source_reliability": 0.88,
        "source_uri": "deidentified://internal-observability/checkout-errors",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.023008,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-010"
      },
      {
        "factor_id": "external.fx_rate_usd_cny.acceleration",
        "parent_factor_id": "external.fx_rate_usd_cny",
        "derived_layer": "acceleration",
        "transform": "second_difference",
        "unit": "delta2_per_day2(cny_per_usd)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "macro",
        "scope": null,
        "target_scope": null,
        "experimentability": "external_or_observational",
        "scope_id": "global",
        "correlation": -0.34006749942404096,
        "lag_days": -12,
        "coverage": 0.76,
        "n_pairs": 38,
        "raw_pvalue": 0.045,
        "bh_q": 0.24092307692307693,
        "max_t_pvalue": 1.0,
        "holdout": {
          "correlation": 0.0,
          "coverage": 0.0,
          "n_pairs": 0,
          "survives": false
        },
        "scope_match": 0.55,
        "source_reliability": 0.7,
        "source_uri": "deidentified://authorized-macro-feed/usd-cny",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.0,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-011"
      },
      {
        "factor_id": "internal.page_latency_p95.velocity",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "velocity",
        "transform": "first_difference",
        "unit": "delta_per_day(ms)",
        "direction": "negative",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": -0.313697514748438,
        "lag_days": 4,
        "coverage": 0.92,
        "n_pairs": 46,
        "raw_pvalue": 0.015,
        "bh_q": 0.1213953488372093,
        "max_t_pvalue": 1.0,
        "holdout": {
          "correlation": 0.21815059966130546,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.92,
        "source_reliability": 0.9,
        "source_uri": "deidentified://internal-observability/page-latency",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.0,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-012"
      },
      {
        "factor_id": "internal.page_latency_p95.acceleration",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "acceleration",
        "transform": "second_difference",
        "unit": "delta2_per_day2(ms)",
        "direction": "positive",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": 0.26378035823290535,
        "lag_days": 3,
        "coverage": 0.94,
        "n_pairs": 47,
        "raw_pvalue": 0.015,
        "bh_q": 0.1213953488372093,
        "max_t_pvalue": 1.0,
        "holdout": {
          "correlation": -0.15641781466250287,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.92,
        "source_reliability": 0.9,
        "source_uri": "deidentified://internal-observability/page-latency",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.0,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-013"
      },
      {
        "factor_id": "internal.checkout_error_rate.acceleration",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "acceleration",
        "transform": "second_difference",
        "unit": "delta2_per_day2(rate)",
        "direction": "positive",
        "source_type": "factor_series",
        "kind": "runtime_quality",
        "scope": null,
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "experimentability": "controllable",
        "scope_id": "east-paid-8.4",
        "correlation": 0.2718385762069833,
        "lag_days": 3,
        "coverage": 0.94,
        "n_pairs": 47,
        "raw_pvalue": 0.055,
        "bh_q": 0.2734285714285714,
        "max_t_pvalue": 1.0,
        "holdout": {
          "correlation": -0.5514140586418734,
          "coverage": 1.0,
          "n_pairs": 10,
          "survives": false
        },
        "scope_match": 0.88,
        "source_reliability": 0.88,
        "source_uri": "deidentified://internal-observability/checkout-errors",
        "content_digest": null,
        "license_ref": "competition-deidentified",
        "association_score": 0.0,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "validation_route": "stratified_quasi_experiment",
        "candidate_id": "cand-014"
      }
    ]
  },
  "rate_aware_rca": {
    "model": "rate_aware_squeeze_style_beam_search",
    "metric_type": "ratio_of_counts",
    "dimensions": [
      "channel",
      "region",
      "version"
    ],
    "baseline_window": [
      0,
      39
    ],
    "current_window": [
      40,
      59
    ],
    "overall_change": {
      "treatment_rate_change": -0.0028001527954081076,
      "control_rate_change": 2.6498612468207894e-05,
      "gap_change": -0.0028266514078763155,
      "treatment_decomposition": {
        "status": "CLOSED",
        "closed": true,
        "reason": null,
        "rate": -0.002764893353180502,
        "mix": -1.527107192263285e-05,
        "interaction": -1.998837030497584e-05,
        "delta": -0.0028001527954081146,
        "closure_error": -4.069146278609659e-18,
        "share_sum_before": 1.0,
        "share_sum_after": 1.0,
        "rate_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": -0.0027621861452853647,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 1.520582201365803e-05,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": -8.172722867552023e-06,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": 8.246247483391596e-06,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": 3.6823251932054314e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": -3.2154474556495304e-07,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": -5.366892955916519e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": -1.5980442016358864e-05
        },
        "mix_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": 4.2392799579977055e-05,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 5.138615683631181e-05,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": -0.00016217767100756752,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": -2.9821453294303302e-05,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": -9.202677316910367e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": 7.634358121064958e-05,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": 9.06210111322652e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": 6.746090955983358e-06
        },
        "interaction_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": -2.025967508148206e-05,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 1.3669010032967963e-07,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": 2.101731628609543e-07,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": -3.9330942403005225e-08,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": -5.466981221985462e-09,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": -4.2729843615530434e-09,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": -7.794410689198802e-09,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": -1.8693168008671554e-08
        },
        "basis": "probability_difference; rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate"
      },
      "control_decomposition": {
        "status": "CLOSED",
        "closed": true,
        "reason": null,
        "rate": 4.1968867557947955e-05,
        "mix": -1.557246616900148e-05,
        "interaction": 1.0221107926153775e-07,
        "delta": 2.6498612468214833e-05,
        "closure_error": 6.8214607267043e-18,
        "share_sum_before": 1.0,
        "share_sum_after": 1.0,
        "rate_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": -5.47241112205095e-07,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 1.0638747421737857e-05,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": -8.767484796018292e-07,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": 9.148010195960756e-06,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": 6.966024891256489e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": 1.7074643431437621e-06,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": 6.579675939122688e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": 8.352934358533326e-06
        },
        "mix_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": 3.6785409514787994e-05,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 4.468485447419568e-05,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": -0.00014268045603231167,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": -2.628100678447734e-05,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": -8.11945531952583e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": 6.622626509217587e-05,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": 7.956404993666598e-06,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": 5.855517892487204e-06
        },
        "interaction_by_cell": {
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.4'))": -4.013823305655126e-09,
          "(('channel', 'paid'), ('region', 'east'), ('version', '8.3'))": 9.563517520810647e-08,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.4'))": 2.2546830961691892e-08,
          "(('channel', 'organic'), ('region', 'west'), ('version', '8.3'))": -4.363195051374509e-08,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.4'))": -1.0342141248864424e-08,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.4'))": 2.2690367473875972e-08,
          "(('channel', 'organic'), ('region', 'east'), ('version', '8.3'))": 9.55575169704573e-09,
          "(('channel', 'paid'), ('region', 'west'), ('version', '8.3'))": 9.7708689890823e-09
        },
        "basis": "probability_difference; rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate"
      }
    },
    "candidate_count_scored": 26,
    "candidate_count": 8,
    "input_validation": {
      "status": "PASS",
      "component": "rate_panel",
      "used_sample_count": 947604,
      "excluded_sample_count": 0,
      "exclusion_reasons": [],
      "checks_performed": [
        "finite",
        "count_range",
        "unique_day_cell",
        "ordered_non_overlapping_windows",
        "common_cell_universe"
      ]
    },
    "candidates": [
      {
        "scope": {
          "version": "8.4",
          "region": "east",
          "channel": "paid"
        },
        "depth": 3,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.006090164762963708,
        "current_gap": -0.015909430951074756,
        "gap_change": -0.021999595714038464,
        "treatment_rate_before": 0.04604265642373395,
        "treatment_rate_after": 0.02403870131165528,
        "control_rate_before": 0.039952491660770244,
        "control_rate_after": 0.039948132262730036,
        "treatment_rate_change": -0.02200395511207867,
        "control_rate_change": -4.359398040207352e-06,
        "rate_contribution": -0.0027621861452853647,
        "mix_contribution": 4.2392799579977055e-05,
        "interaction_contribution": -2.025967508148206e-05,
        "treatment_share_before": 0.12553134794249388,
        "treatment_share_after": 0.12645207673776218,
        "candidate_contribution_change": -0.0027400530207868697,
        "candidate_closure_error": 0.0,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": 9.822194056360867e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.12645207673776218,
        "scope_focus": 0.8735479232622378,
        "isolation": 0.9953457358161009,
        "stability": 1.0,
        "complement_gap_change": -5.131538287034276e-05,
        "baseline_impressions": 39572,
        "current_impressions": 20051,
        "priority": 0.002640077125968194,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.021999595714038464
      },
      {
        "scope": {
          "version": "8.4",
          "channel": "paid"
        },
        "depth": 2,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.006097560975609755,
        "current_gap": -0.004914188784673722,
        "gap_change": -0.011011749760283476,
        "treatment_rate_before": 0.046054966786674104,
        "treatment_rate_after": 0.03504789463181002,
        "control_rate_before": 0.03995740581106435,
        "control_rate_after": 0.03996208341648374,
        "treatment_rate_change": -0.011007072154864087,
        "control_rate_change": 4.677605419389774e-06,
        "rate_contribution": -0.002754386808182754,
        "mix_contribution": 0.0001187271794343369,
        "interaction_contribution": -2.8375628557729684e-05,
        "treatment_share_before": 0.25023791698917636,
        "treatment_share_after": 0.2528158621646507,
        "candidate_contribution_change": -0.0026640352573061472,
        "candidate_closure_error": -8.673617379884035e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": -4.496050884025826e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.2528158621646507,
        "scope_focus": 0.7471841378353493,
        "isolation": 0.9896118115856315,
        "stability": 1.0,
        "complement_gap_change": -5.749469852138478e-05,
        "baseline_impressions": 78884,
        "current_impressions": 40088,
        "priority": 0.002521552751011502,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.011011749760283476
      },
      {
        "scope": {
          "region": "east",
          "channel": "paid"
        },
        "depth": 2,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.006044137440637941,
        "current_gap": -0.004982847985577285,
        "gap_change": -0.011026985426215226,
        "treatment_rate_before": 0.046016710262335885,
        "treatment_rate_after": 0.03503017252172171,
        "control_rate_before": 0.039972572821697944,
        "control_rate_after": 0.040013020507299,
        "treatment_rate_change": -0.010986537740614172,
        "control_rate_change": 4.0447685601054106e-05,
        "rate_contribution": -0.0027447175869010155,
        "mix_contribution": 9.378434578402891e-05,
        "interaction_contribution": -2.2391110719585372e-05,
        "treatment_share_before": 0.24982552754127066,
        "treatment_share_after": 0.2518635773116557,
        "candidate_contribution_change": -0.0026733243518365715,
        "candidate_closure_error": 4.336808689942018e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": -4.9873299934333204e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.2518635773116557,
        "scope_focus": 0.7481364226883442,
        "isolation": 0.988092692988186,
        "stability": 1.0,
        "complement_gap_change": -6.604405385515072e-05,
        "baseline_impressions": 78754,
        "current_impressions": 39937,
        "priority": 0.0024857278660730562,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.011026985426215226
      },
      {
        "scope": {
          "version": "8.4",
          "region": "east"
        },
        "depth": 2,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.005983003696505472,
        "current_gap": -0.005136598262621174,
        "gap_change": -0.011119601959126646,
        "treatment_rate_before": 0.04796565171550881,
        "treatment_rate_after": 0.03686264635528138,
        "control_rate_before": 0.04198264801900334,
        "control_rate_after": 0.041999244617902554,
        "treatment_rate_change": -0.01110300536022743,
        "control_rate_change": 1.659659889921561e-05,
        "rate_contribution": -0.0027727223127218463,
        "mix_contribution": 3.5319069378994844e-05,
        "interaction_contribution": -8.175596548945264e-06,
        "treatment_share_before": 0.24972718851907777,
        "treatment_share_after": 0.25046352938208694,
        "candidate_contribution_change": -0.002745578839891797,
        "candidate_closure_error": -4.336808689942018e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": 4.453699236663111e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.25046352938208694,
        "scope_focus": 0.7495364706179131,
        "isolation": 0.9900773997369653,
        "stability": 1.0,
        "complement_gap_change": -5.544275078901706e-05,
        "baseline_impressions": 78723,
        "current_impressions": 39715,
        "priority": 0.0024513148094412567,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.011119601959126646
      },
      {
        "scope": {
          "channel": "paid"
        },
        "depth": 1,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.006067606849541121,
        "current_gap": 0.0005008639903834114,
        "gap_change": -0.00556674285915771,
        "treatment_rate_before": 0.0460338415059851,
        "treatment_rate_after": 0.0405073752222584,
        "control_rate_before": 0.03996623465644398,
        "control_rate_after": 0.040006511231874986,
        "treatment_rate_change": -0.005526466283726703,
        "control_rate_change": 4.027657543100721e-05,
        "rate_contribution": -0.002762181269688144,
        "mix_contribution": 0.00017685327025106465,
        "interaction_contribution": -2.1231633147154186e-05,
        "treatment_share_before": 0.4998096664086589,
        "treatment_share_after": 0.5036514763568483,
        "candidate_contribution_change": -0.002606559632584233,
        "candidate_closure_error": 4.336808689942018e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": 5.6954495373379155e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.5036514763568483,
        "scope_focus": 0.49634852364315174,
        "isolation": 0.9832843820288509,
        "stability": 0.05,
        "complement_gap_change": -4.691790437139076e-05,
        "baseline_impressions": 157558,
        "current_impressions": 79862,
        "priority": 0.0011530491659589195,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.00556674285915771
      },
      {
        "scope": {
          "region": "east"
        },
        "depth": 1,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.006016548688888464,
        "current_gap": 0.000440739434846113,
        "gap_change": -0.005575809254042351,
        "treatment_rate_before": 0.047986109786113604,
        "treatment_rate_after": 0.04244950385332191,
        "control_rate_before": 0.04196956109722514,
        "control_rate_after": 0.0420087644184758,
        "treatment_rate_change": -0.005536605932791691,
        "control_rate_change": 3.920332125065956e-05,
        "rate_contribution": -0.0027615410696450785,
        "mix_contribution": 9.764446714611482e-05,
        "interaction_contribution": -1.1266154695913879e-05,
        "treatment_share_before": 0.4987786927888947,
        "treatment_share_after": 0.5008135413644792,
        "candidate_contribution_change": -0.002675162757194878,
        "candidate_closure_error": -4.336808689942018e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": -1.0740377771184528e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.5008135413644792,
        "scope_focus": 0.4991864586355208,
        "isolation": 0.9757376732830575,
        "stability": 0.0,
        "complement_gap_change": -6.847169422453253e-05,
        "baseline_impressions": 157233,
        "current_impressions": 79412,
        "priority": 0.0010627844393857112,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.005575809254042351
      },
      {
        "scope": {
          "version": "8.4"
        },
        "depth": 1,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.0060214235913037956,
        "current_gap": 0.0004291574629220543,
        "gap_change": -0.005592266128381741,
        "treatment_rate_before": 0.04801293021486975,
        "treatment_rate_after": 0.04241085515935626,
        "control_rate_before": 0.041991506623565954,
        "control_rate_after": 0.04198169769643421,
        "treatment_rate_change": -0.005602075055513488,
        "control_rate_change": -9.808927131746414e-06,
        "rate_contribution": -0.002803738727519582,
        "mix_contribution": -4.071288678911365e-05,
        "interaction_contribution": 4.750317185361083e-06,
        "treatment_share_before": 0.5004821784313974,
        "treatment_share_after": 0.49963422171209465,
        "candidate_contribution_change": -0.002839701297123333,
        "candidate_closure_error": 1.3010426069826053e-18,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": 8.30431101488116e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.49963422171209465,
        "scope_focus": 0.5003657782879054,
        "isolation": 0.9769895746686772,
        "stability": 0.0,
        "complement_gap_change": -6.508907473706804e-05,
        "baseline_impressions": 157770,
        "current_impressions": 79225,
        "priority": 0.0010564155179406845,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 0.005592266128381741
      },
      {
        "scope": {
          "region": "west",
          "channel": "organic"
        },
        "depth": 2,
        "baseline_days": [
          0,
          39
        ],
        "current_days": [
          40,
          59
        ],
        "baseline_gap": 0.005972297630020579,
        "current_gap": 0.005939483545336362,
        "gap_change": -3.281408468421704e-05,
        "treatment_rate_before": 0.04998800489905175,
        "treatment_rate_after": 0.04998852889444034,
        "control_rate_before": 0.044015707269031173,
        "control_rate_after": 0.04404904534910398,
        "treatment_rate_change": 5.239953885863291e-07,
        "control_rate_change": 3.3338080072803367e-05,
        "rate_contribution": 1.3164711765359502e-07,
        "mix_contribution": -0.00019188439316994034,
        "interaction_contribution": -2.0114132853628285e-09,
        "treatment_share_before": 0.25123716834371707,
        "treatment_share_after": 0.2473985595903283,
        "candidate_contribution_change": -0.00019175475746557175,
        "candidate_closure_error": 3.5236570605778894e-19,
        "decomposition_status": "CLOSED",
        "decomposition_closure_error": -4.9873299934333204e-18,
        "decomposition_basis": "rate=before_share*delta_rate; mix=delta_share*before_rate; interaction=delta_share*delta_rate",
        "coverage": 0.2473985595903283,
        "scope_focus": 0.7526014404096717,
        "isolation": 0.9826298752419477,
        "stability": 0.0,
        "complement_gap_change": -0.0037454068712712493,
        "baseline_impressions": 79199,
        "current_impressions": 39229,
        "priority": 8.340208006952119e-05,
        "claim_type": "FACTOR_CANDIDATE",
        "evidence_level": "FACTOR_CANDIDATE",
        "note": "该结果定位异常分层，不证明分层因素造成了指标变化。",
        "beam_score": 3.281408468421704e-05
      }
    ],
    "claim_policy": "candidate_only_until_randomized_or_quasi_experimental_validation",
    "limitations": [
      "候选名称来自输入面板维度，算法不能命名不存在数据入口的外部因素。",
      "rate/mix/interaction 是概率尺度上的闭合描述性分解，不是因果贡献。",
      "多维搜索使用 beam_width 和 min_impressions，需在留出窗口评估召回与假阳性。"
    ],
    "truth_for_offline_evaluation": {
      "affected_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "onset_day": 40,
      "direction": "negative"
    },
    "output_path": "runtime_data/evidence/T2-lineB-rate-aware-rca.json"
  },
  "factor_library": {
    "query": "",
    "candidate_count": 6,
    "candidates": [
      {
        "factor_id": "internal.audit.unregistered_release",
        "name": "未登记发布变更",
        "description": "内部发布审计中发现的未登记版本/配置变更",
        "source_type": "internal_event",
        "scope": {},
        "aliases": [
          "internal.audit.unregistered_release",
          "未登记发布变更"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "release_audit"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:a50225e8464791a8",
            "factor_id": "internal.audit.unregistered_release",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://internal-release-audit/day-40",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      },
      {
        "factor_id": "internal.page_latency_p95",
        "name": "页面 P95 延迟",
        "description": "内部可观测性中的页面响应延迟",
        "source_type": "factor_series",
        "scope": {},
        "aliases": [
          "internal.page_latency_p95",
          "页面 P95 延迟"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "runtime_quality"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:d1bfa8cb4cf2e011",
            "factor_id": "internal.page_latency_p95",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://internal-observability/page-latency",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [
          {
            "snapshot_id": 1,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 0,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 2,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 1,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 3,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 2,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 4,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 3,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 5,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 4,
            "value": 192.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 6,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 5,
            "value": 195.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 7,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 6,
            "value": 198.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 8,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 7,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 9,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 8,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 10,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 9,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 11,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 10,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 12,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 11,
            "value": 192.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 13,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 12,
            "value": 195.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 14,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 13,
            "value": 198.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 15,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 14,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 16,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 15,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 17,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 16,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 18,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 17,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 19,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 18,
            "value": 192.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 20,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 19,
            "value": 195.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 21,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 20,
            "value": 198.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 22,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 21,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 23,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 22,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 24,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 23,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 25,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 24,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 26,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 25,
            "value": 192.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 27,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 26,
            "value": 195.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 28,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 27,
            "value": 198.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 29,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 28,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 30,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 29,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 31,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 30,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 32,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 31,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 33,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 32,
            "value": 192.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 34,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 33,
            "value": 195.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 35,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 34,
            "value": 198.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 36,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 35,
            "value": 180.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 37,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 36,
            "value": 183.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 38,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 37,
            "value": 186.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 39,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 38,
            "value": 189.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 40,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 39,
            "value": 194.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 41,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 40,
            "value": 200.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 42,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 41,
            "value": 205.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 43,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 42,
            "value": 190.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 44,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 43,
            "value": 195.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 45,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 44,
            "value": 201.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 46,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 45,
            "value": 206.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 47,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 46,
            "value": 212.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 48,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 47,
            "value": 217.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 49,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 48,
            "value": 223.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 50,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 49,
            "value": 207.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 51,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 50,
            "value": 213.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 52,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 51,
            "value": 218.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 53,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 52,
            "value": 224.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 54,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 53,
            "value": 229.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 55,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 54,
            "value": 235.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 56,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 55,
            "value": 240.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 57,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 56,
            "value": 225.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 58,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 57,
            "value": 230.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 59,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 58,
            "value": 236.0,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 60,
            "factor_id": "internal.page_latency_p95",
            "scope_id": "global",
            "day": 59,
            "value": 241.5,
            "source_uri": "deidentified://internal-observability/page-latency",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          }
        ],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      },
      {
        "factor_id": "internal.checkout_error_rate",
        "name": "结算错误率",
        "description": "内部可观测性中的结算失败比例",
        "source_type": "factor_series",
        "scope": {},
        "aliases": [
          "internal.checkout_error_rate",
          "结算错误率"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "runtime_quality"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:b5d91039a206ef45",
            "factor_id": "internal.checkout_error_rate",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [
          {
            "snapshot_id": 61,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 0,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 62,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 1,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 63,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 2,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 64,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 3,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 65,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 4,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 66,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 5,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 67,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 6,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 68,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 7,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 69,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 8,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 70,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 9,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 71,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 10,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 72,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 11,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 73,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 12,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 74,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 13,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 75,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 14,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 76,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 15,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 77,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 16,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 78,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 17,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 79,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 18,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 80,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 19,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 81,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 20,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 82,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 21,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 83,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 22,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 84,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 23,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 85,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 24,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 86,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 25,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 87,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 26,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 88,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 27,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 89,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 28,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 90,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 29,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 91,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 30,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 92,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 31,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 93,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 32,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 94,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 33,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 95,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 34,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 96,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 35,
            "value": 0.008,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 97,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 36,
            "value": 0.0082,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 98,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 37,
            "value": 0.0084,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 99,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 38,
            "value": 0.0086,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 100,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 39,
            "value": 0.0088,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 101,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 40,
            "value": 0.026,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 102,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 41,
            "value": 0.026199999999999998,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 103,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 42,
            "value": 0.0264,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 104,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 43,
            "value": 0.0266,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 105,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 44,
            "value": 0.026799999999999997,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 106,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 45,
            "value": 0.026,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 107,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 46,
            "value": 0.026199999999999998,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 108,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 47,
            "value": 0.0264,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 109,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 48,
            "value": 0.0266,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 110,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 49,
            "value": 0.026799999999999997,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 111,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 50,
            "value": 0.026,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 112,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 51,
            "value": 0.026199999999999998,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 113,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 52,
            "value": 0.0264,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 114,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 53,
            "value": 0.0266,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 115,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 54,
            "value": 0.026799999999999997,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 116,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 55,
            "value": 0.026,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 117,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 56,
            "value": 0.026199999999999998,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 118,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 57,
            "value": 0.0264,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 119,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 58,
            "value": 0.0266,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 120,
            "factor_id": "internal.checkout_error_rate",
            "scope_id": "global",
            "day": 59,
            "value": 0.026799999999999997,
            "source_uri": "deidentified://internal-observability/checkout-errors",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          }
        ],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      },
      {
        "factor_id": "external.competitor_campaign",
        "name": "竞品营销活动",
        "description": "授权或公开来源观察到的竞品投放/促销活动",
        "source_type": "external_event",
        "scope": {},
        "aliases": [
          "external.competitor_campaign",
          "竞品营销活动"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "competitor_marketing"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:7babb51e77d046f4",
            "factor_id": "external.competitor_campaign",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://authorized-event-feed/competitor-campaign",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      },
      {
        "factor_id": "external.fx_rate_usd_cny",
        "name": "美元兑人民币汇率",
        "description": "授权宏观数据源中的日度汇率快照",
        "source_type": "factor_series",
        "scope": {},
        "aliases": [
          "external.fx_rate_usd_cny",
          "美元兑人民币汇率"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "macro"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:9cbd2c7702f48b47",
            "factor_id": "external.fx_rate_usd_cny",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [
          {
            "snapshot_id": 121,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 0,
            "value": 7.1,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 122,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 1,
            "value": 7.101,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 123,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 2,
            "value": 7.101999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 124,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 3,
            "value": 7.103,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 125,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 4,
            "value": 7.103999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 126,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 5,
            "value": 7.1049999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 127,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 6,
            "value": 7.106,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 128,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 7,
            "value": 7.106999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 129,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 8,
            "value": 7.108,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 130,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 9,
            "value": 7.109,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 131,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 10,
            "value": 7.109999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 132,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 11,
            "value": 7.111,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 133,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 12,
            "value": 7.111999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 134,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 13,
            "value": 7.1129999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 135,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 14,
            "value": 7.114,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 136,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 15,
            "value": 7.114999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 137,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 16,
            "value": 7.116,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 138,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 17,
            "value": 7.117,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 139,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 18,
            "value": 7.117999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 140,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 19,
            "value": 7.119,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 141,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 20,
            "value": 7.119999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 142,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 21,
            "value": 7.1209999999999996,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 143,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 22,
            "value": 7.122,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 144,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 23,
            "value": 7.122999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 145,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 24,
            "value": 7.124,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 146,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 25,
            "value": 7.125,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 147,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 26,
            "value": 7.1259999999999994,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 148,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 27,
            "value": 7.1419999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 149,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 28,
            "value": 7.1579999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 150,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 29,
            "value": 7.1739999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 151,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 30,
            "value": 7.1899999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 152,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 31,
            "value": 7.2059999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 153,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 32,
            "value": 7.2219999999999995,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 154,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 33,
            "value": 7.238,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 155,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 34,
            "value": 7.254,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 156,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 35,
            "value": 7.27,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 157,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 36,
            "value": 7.286,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 158,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 37,
            "value": 7.302,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 159,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 38,
            "value": 7.318,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 160,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 39,
            "value": 7.334,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 161,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 40,
            "value": 7.35,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 162,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 41,
            "value": 7.366,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 163,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 42,
            "value": 7.382,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 164,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 43,
            "value": 7.398,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 165,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 44,
            "value": 7.414,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 166,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 45,
            "value": 7.43,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 167,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 46,
            "value": 7.446,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 168,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 47,
            "value": 7.462,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 169,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 48,
            "value": 7.478,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 170,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 49,
            "value": 7.494,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 171,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 50,
            "value": 7.51,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 172,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 51,
            "value": 7.526,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 173,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 52,
            "value": 7.541999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 174,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 53,
            "value": 7.558,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 175,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 54,
            "value": 7.574,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 176,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 55,
            "value": 7.589999999999999,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 177,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 56,
            "value": 7.606,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 178,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 57,
            "value": 7.622,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 179,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 58,
            "value": 7.638,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 180,
            "factor_id": "external.fx_rate_usd_cny",
            "scope_id": "global",
            "day": 59,
            "value": 7.654,
            "source_uri": "deidentified://authorized-macro-feed/usd-cny",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          }
        ],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      },
      {
        "factor_id": "external.competitor_pressure_index",
        "name": "竞品压力指数",
        "description": "授权或公开来源构造的竞品压力序列",
        "source_type": "factor_series",
        "scope": {},
        "aliases": [
          "external.competitor_pressure_index",
          "竞品压力指数"
        ],
        "status": "active",
        "license_ref": "competition-deidentified",
        "valid_from": null,
        "valid_to": null,
        "metadata": {
          "deidentified_data": true,
          "derived_layers": [
            "level",
            "velocity",
            "acceleration"
          ],
          "kind": "competitor_marketing"
        },
        "updated_at": "2026-08-31T15:25:12+00:00",
        "evidence": [
          {
            "evidence_id": "sha256:ae9ad1082abf9ffd",
            "factor_id": "external.competitor_pressure_index",
            "evidence_type": "deidentified_scenario",
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "observed_at": "2026-08-27",
            "excerpt": "可复现演示候选，不能替代授权生产数据。",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": {},
            "created_at": "2026-08-31T15:25:12+00:00"
          }
        ],
        "snapshots": [
          {
            "snapshot_id": 181,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 0,
            "value": 20.0,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 182,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 1,
            "value": 20.05,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 183,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 2,
            "value": 20.1,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 184,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 3,
            "value": 20.15,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 185,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 4,
            "value": 20.2,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 186,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 5,
            "value": 20.25,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 187,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 6,
            "value": 20.3,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 188,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 7,
            "value": 20.35,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 189,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 8,
            "value": 20.4,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 190,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 9,
            "value": 20.45,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 191,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 10,
            "value": 20.5,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 192,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 11,
            "value": 20.55,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 193,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 12,
            "value": 20.6,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 194,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 13,
            "value": 20.65,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 195,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 14,
            "value": 20.7,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 196,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 15,
            "value": 20.75,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 197,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 16,
            "value": 20.8,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 198,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 17,
            "value": 20.85,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 199,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 18,
            "value": 20.9,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 200,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 19,
            "value": 20.95,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 201,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 20,
            "value": 21.0,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 202,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 21,
            "value": 21.05,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 203,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 22,
            "value": 21.1,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 204,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 23,
            "value": 21.15,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 205,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 24,
            "value": 21.2,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 206,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 25,
            "value": 21.25,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 207,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 26,
            "value": 21.3,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 208,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 27,
            "value": 21.35,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 209,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 28,
            "value": 21.4,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 210,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 29,
            "value": 21.45,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 211,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 30,
            "value": 21.5,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 212,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 31,
            "value": 21.55,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 213,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 32,
            "value": 21.6,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 214,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 33,
            "value": 21.65,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 215,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 34,
            "value": 21.7,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 216,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 35,
            "value": 21.75,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 217,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 36,
            "value": 21.8,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 218,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 37,
            "value": 21.85,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 219,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 38,
            "value": 21.9,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 220,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 39,
            "value": 21.95,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 221,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 40,
            "value": 22.0,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 222,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 41,
            "value": 22.05,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 223,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 42,
            "value": 22.1,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 224,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 43,
            "value": 22.15,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 225,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 44,
            "value": 22.2,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 226,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 45,
            "value": 22.25,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 227,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 46,
            "value": 22.3,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 228,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 47,
            "value": 22.35,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 229,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 48,
            "value": 23.2,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 230,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 49,
            "value": 24.489297003710817,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 231,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 50,
            "value": 26.025361691040178,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 232,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 51,
            "value": 27.74841533667991,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 233,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 52,
            "value": 29.625860019784113,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 234,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 53,
            "value": 31.636574416918926,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 235,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 54,
            "value": 33.76553308478939,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 236,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 55,
            "value": 36.00139102516964,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 237,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 56,
            "value": 38.33521881581707,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 238,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 57,
            "value": 40.75976910854672,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 239,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 58,
            "value": 43.26901893771151,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          },
          {
            "snapshot_id": 240,
            "factor_id": "external.competitor_pressure_index",
            "scope_id": "global",
            "day": 59,
            "value": 45.85786785255884,
            "source_uri": "deidentified://authorized-event-feed/competitor-pressure",
            "content_digest": null,
            "license_ref": "competition-deidentified",
            "metadata": "{}"
          }
        ],
        "production_eligible": true,
        "eligibility_reason": "source_and_evidence_license_present",
        "retrieval_basis": "structured_filter+fts5+provenance"
      }
    ],
    "claim_policy": "retrieval supplies candidates and evidence only; no causal conclusion"
  },
  "validation_plans": [
    {
      "plan_id": "validation:internal.audit.unregistered_release",
      "factor_id": "internal.audit.unregistered_release",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": null,
      "target_scope": {
        "scope_id": "global"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-001",
        "factor_id": "internal.audit.unregistered_release",
        "parent_factor_id": "internal.audit.unregistered_release",
        "derived_layer": "level",
        "target_scope": {
          "scope_id": "global"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.page_latency_p95.level",
      "factor_id": "internal.page_latency_p95.level",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": -3,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-002",
        "factor_id": "internal.page_latency_p95.level",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "level",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.checkout_error_rate.level",
      "factor_id": "internal.checkout_error_rate.level",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 0,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-003",
        "factor_id": "internal.checkout_error_rate.level",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "level",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.competitor_campaign",
      "factor_id": "external.competitor_campaign",
      "route": "stratified_quasi_experiment",
      "design": "control_series_or_synthetic_control_with_holdout",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": null,
      "target_scope": {
        "scope_id": "global"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-004",
        "factor_id": "external.competitor_campaign",
        "derived_layer": "level",
        "target_scope": {
          "scope_id": "global"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "stratified_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.fx_rate_usd_cny.velocity",
      "factor_id": "external.fx_rate_usd_cny.velocity",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 13,
      "target_scope": {
        "scope_id": "global"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-005",
        "factor_id": "external.fx_rate_usd_cny.velocity",
        "derived_layer": "velocity",
        "target_scope": {
          "scope_id": "global"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.fx_rate_usd_cny.level",
      "factor_id": "external.fx_rate_usd_cny.level",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 9,
      "target_scope": {
        "scope_id": "global"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-006",
        "factor_id": "external.fx_rate_usd_cny.level",
        "derived_layer": "level",
        "target_scope": {
          "scope_id": "global"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.competitor_pressure_index.velocity",
      "factor_id": "external.competitor_pressure_index.velocity",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": -8,
      "target_scope": {
        "scope_id": "paid"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-007",
        "factor_id": "external.competitor_pressure_index.velocity",
        "derived_layer": "velocity",
        "target_scope": {
          "scope_id": "paid"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.competitor_pressure_index.level",
      "factor_id": "external.competitor_pressure_index.level",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": -8,
      "target_scope": {
        "scope_id": "paid"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-008",
        "factor_id": "external.competitor_pressure_index.level",
        "derived_layer": "level",
        "target_scope": {
          "scope_id": "paid"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.competitor_pressure_index.acceleration",
      "factor_id": "external.competitor_pressure_index.acceleration",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": -8,
      "target_scope": {
        "scope_id": "paid"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-009",
        "factor_id": "external.competitor_pressure_index.acceleration",
        "derived_layer": "acceleration",
        "target_scope": {
          "scope_id": "paid"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.checkout_error_rate.velocity",
      "factor_id": "internal.checkout_error_rate.velocity",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 4,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-010",
        "factor_id": "internal.checkout_error_rate.velocity",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "velocity",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:external.fx_rate_usd_cny.acceleration",
      "factor_id": "external.fx_rate_usd_cny.acceleration",
      "route": "holdout_then_quasi_experiment",
      "design": "lagged_association_as_screen_only_then_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": -12,
      "target_scope": {
        "scope_id": "global"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "external_or_observational",
      "next_window_action": "run_mitigation_abtest_and_quasi_experiment",
      "experiment_spec": {
        "template_id": "external_factor_mitigation_abtest",
        "candidate_id": "cand-011",
        "factor_id": "external.fx_rate_usd_cny.acceleration",
        "derived_layer": "acceleration",
        "target_scope": {
          "scope_id": "global"
        },
        "randomization_unit": "hashed_subject_id",
        "treatment": "mitigation_strategy_on",
        "control": "current_strategy",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "factor_itself_randomizable": false,
        "factor_validation_route": "holdout_then_quasi_experiment",
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.page_latency_p95.velocity",
      "factor_id": "internal.page_latency_p95.velocity",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 4,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-012",
        "factor_id": "internal.page_latency_p95.velocity",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "velocity",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.page_latency_p95.acceleration",
      "factor_id": "internal.page_latency_p95.acceleration",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 3,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-013",
        "factor_id": "internal.page_latency_p95.acceleration",
        "parent_factor_id": "internal.page_latency_p95",
        "derived_layer": "acceleration",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    },
    {
      "plan_id": "validation:internal.checkout_error_rate.acceleration",
      "factor_id": "internal.checkout_error_rate.acceleration",
      "route": "targeted_abtest_or_gray_release",
      "design": "within_scope_randomized_intervention",
      "metric_contract": {
        "name": "issued_policies",
        "unit": "count",
        "estimand": "rate difference"
      },
      "discovery_window": [
        0,
        49
      ],
      "holdout_window": [
        50,
        59
      ],
      "selected_lag_days": 3,
      "target_scope": {
        "region": "east",
        "channel": "paid",
        "version": "8.4"
      },
      "target_window": [
        60,
        73
      ],
      "experimentability": "controllable",
      "next_window_action": "run_targeted_abtest",
      "experiment_spec": {
        "template_id": "targeted_factor_validation",
        "candidate_id": "cand-014",
        "factor_id": "internal.checkout_error_rate.acceleration",
        "parent_factor_id": "internal.checkout_error_rate",
        "derived_layer": "acceleration",
        "target_scope": {
          "region": "east",
          "channel": "paid",
          "version": "8.4"
        },
        "randomization_unit": "hashed_subject_id",
        "stable_randomization_unit": "hashed_subject_id",
        "treatment": "candidate_intervention_or_flag_on",
        "control": "current_behavior_or_flag_off",
        "metric": "issued_policies",
        "metric_contract": {
          "name": "issued_policies",
          "unit": "count",
          "estimand": "rate difference"
        },
        "traffic_plan": [
          5,
          10,
          25
        ],
        "planned_window": [
          60,
          73
        ],
        "guardrails": [
          "error_rate",
          "latency_p95",
          "complaint_rate"
        ],
        "pre_registration_required": true,
        "causal_claim_allowed": false
      },
      "primary_estimand": "rate difference",
      "gates": [
        "候选必须来自授权数据入口并保留 content_digest/license_ref。",
        "先在 holdout 复核方向、滞后和覆盖率，再进入验证实验。",
        "无随机化时只允许 ASSOCIATION_ONLY/FACTOR_CANDIDATE；外部因子 A/B 只验证我方应对策略。",
        "验证数据不能与候选搜索窗口复用。"
      ],
      "expected_outputs": [
        "holdout_survives",
        "effect_estimate",
        "interval_or_posterior",
        "assumptions",
        "claim_type",
        "evidence_refs"
      ],
      "claim_type_before_validation": "FACTOR_CANDIDATE",
      "causal_claim_allowed": false
    }
  ]
}
```

证据文件：`outputs/lineB_baseline_attribution.json`

合规说明：本系统输出为经营决策支持，不构成投资建议；证据不足时应拒答而非强行归因。