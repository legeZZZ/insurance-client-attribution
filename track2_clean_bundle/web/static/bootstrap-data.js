window.__GOAI_BOOTSTRAP_DATA__ = {
  "track2": {
    "A": {
      "task_id": "T2-case-A",
      "trace_id": "trace_8c77f10e2c6b",
      "domain": "insurance-growth-attribution",
      "input_payload": {
        "case": "A",
        "question": "DAU rose while premium declined; explain what is known and what should be tested."
      },
      "state": "CLOSED",
      "state_version": 12,
      "artifacts": [
        {
          "artifact_id": "art_f9406c543ca5",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "AnalysisIntent",
          "schema_version": "1.0",
          "producer": "intent",
          "payload": {
            "question": "DAU rose while premium declined; explain what is known and what should be tested.",
            "target": "premium growth and conversion",
            "unit": "user_id"
          },
          "evidence_refs": [
            "ev_fdc50522caa1"
          ],
          "created_at": "2026-08-01T07:36:16.259173+00:00"
        },
        {
          "artifact_id": "art_f8d72c5337ca",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "MetricContract",
          "schema_version": "1.0",
          "producer": "metric_contract",
          "payload": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "evidence_refs": [
            "ev_fdc50522caa1"
          ],
          "created_at": "2026-08-01T07:36:16.260189+00:00"
        },
        {
          "artifact_id": "art_8047b012ff09",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "DataQualityReport",
          "schema_version": "1.0",
          "producer": "data_acquisition",
          "payload": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": true,
            "outcome_complete": true,
            "missing_fields": []
          },
          "evidence_refs": [
            "ev_b530a33ba475"
          ],
          "created_at": "2026-08-01T07:36:16.261327+00:00"
        },
        {
          "artifact_id": "art_44719e68c3c9",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "FeatureSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "segments": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "group_outcomes": {
                "0": {
                  "count": 858.0,
                  "issued": 0.039627,
                  "net_premium": 37.215408
                },
                "1": {
                  "count": 342.0,
                  "issued": 0.087719,
                  "net_premium": 85.747398
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": true,
              "outcome_complete": true
            }
          },
          "evidence_refs": [
            "ev_b530a33ba475",
            "ev_81e6139054ef"
          ],
          "created_at": "2026-08-01T07:36:16.261420+00:00"
        },
        {
          "artifact_id": "art_e093437af016",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "AttributionCandidateSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "metrics": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "features": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "decomposition": {
              "method": "fixed-order log-chain decomposition",
              "baseline_premium": 62845.22,
              "current_premium": 61256.43,
              "total_log_change": -0.025612,
              "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
              "unexplained_residual": 0.0,
              "factors": [
                {
                  "key": "active",
                  "label": "活跃流量",
                  "before": 1200,
                  "after": 1200,
                  "log_change": 0.0,
                  "share": -0.0
                },
                {
                  "key": "quote_rate",
                  "label": "报价率",
                  "before": 0.441667,
                  "after": 0.420833,
                  "log_change": -0.04832,
                  "share": 1.886626
                },
                {
                  "key": "apply_rate",
                  "label": "投保率",
                  "before": 0.401887,
                  "after": 0.431683,
                  "log_change": 0.071521,
                  "share": -2.792495
                },
                {
                  "key": "paid_rate",
                  "label": "支付率",
                  "before": 0.525822,
                  "after": 0.504587,
                  "log_change": -0.041222,
                  "share": 1.609489
                },
                {
                  "key": "issue_rate",
                  "label": "出单率",
                  "before": 0.589286,
                  "after": 0.581818,
                  "log_change": -0.012754,
                  "share": 0.497972
                },
                {
                  "key": "avg_premium",
                  "label": "件均保费",
                  "before": 952.2,
                  "after": 957.13,
                  "log_change": 0.005164,
                  "share": -0.201625
                }
              ]
            },
            "interpretation": "structural contribution only"
          },
          "evidence_refs": [
            "ev_81e6139054ef",
            "ev_b172a6cb8ffa"
          ],
          "created_at": "2026-08-01T07:36:16.262902+00:00"
        },
        {
          "artifact_id": "art_de8a908f56ac",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "EvidenceReport",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "outcome": "DESCRIPTIVE_ONLY",
            "estimand": null,
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "not identified",
            "assumptions": [
              "observational co-movement only"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "contract_missing_fields": [],
              "missing_evidence": [],
              "design_checks": {
                "randomized_assignment": false,
                "assignment_verified": false,
                "trusted_assignment_provenance": false,
                "both_arms_present": true,
                "randomization_unit_matches": true
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.039627,
                "required_per_arm": 239,
                "actual_min_arm": 342,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": true,
                "reason_code": "DATA_COMPLETE"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": false,
                "reason_code": "POWER_NOT_ESTABLISHED"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L1/L2",
            "reason_codes": [
              "CAUSAL_DESIGN_NOT_VERIFIED",
              "POWER_NOT_ESTABLISHED"
            ],
            "allowed_claim_type": "descriptive_only"
          },
          "evidence_refs": [
            "ev_b530a33ba475",
            "ev_81e6139054ef",
            "ev_0bdfb76a6d29"
          ],
          "created_at": "2026-08-01T07:36:16.264776+00:00"
        },
        {
          "artifact_id": "art_3a868321e4da",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "ClaimLedger",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "claim_id": "claim-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "观察到",
              "同时出现",
              "对应"
            ],
            "prohibited_actions": [
              "声称导致",
              "自动触达个人",
              "直接上线配置"
            ],
            "uncertainty": "causal identification unavailable",
            "statement": "当前只能说明指标变化与候选因素同时出现，不能断言因果。"
          },
          "evidence_refs": [
            "ev_6dab1b8b68e8"
          ],
          "created_at": "2026-08-01T07:36:16.266886+00:00"
        },
        {
          "artifact_id": "art_f7512487e0d1",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "ExperimentSpec",
          "schema_version": "1.0",
          "producer": "experiment_planner",
          "payload": {
            "experiment_id": "observational-ranking-change-A",
            "treatment": "new ranking",
            "unit": "user_id",
            "randomization": "observational",
            "primary_metric": "issued",
            "guardrails": [
              "refund_rate",
              "cancel_rate",
              "privacy_policy"
            ],
            "stop_rule": "guardrail breach or final observation window",
            "approval": "required"
          },
          "evidence_refs": [
            "ev_582d2e8de8c6"
          ],
          "created_at": "2026-08-01T07:36:16.266920+00:00"
        },
        {
          "artifact_id": "art_3fd92974ff37",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "artifact_type": "MonitoringReport",
          "schema_version": "1.0",
          "producer": "monitor_review",
          "payload": {
            "status": "waiting_for_real_randomized_window",
            "causal_estimate": null
          },
          "evidence_refs": [
            "ev_cb5aae1f3c28"
          ],
          "created_at": "2026-08-01T07:36:16.277516+00:00"
        }
      ],
      "evidence": [
        {
          "evidence_id": "ev_fdc50522caa1",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "metric-contract",
          "label": "versioned insurance metric contract",
          "source": "metric_contract",
          "content": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba",
          "created_at": "2026-08-01T07:36:16.256184+00:00"
        },
        {
          "evidence_id": "ev_b530a33ba475",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "data-quality",
          "label": "schema and data quality report",
          "source": "data_acquisition",
          "content": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": true,
            "outcome_complete": true,
            "missing_fields": []
          },
          "content_digest": "c444ebea24c9fa1faceba0bfcf7a014e477f556db3a92147c280a01988492dc2",
          "created_at": "2026-08-01T07:36:16.260220+00:00"
        },
        {
          "evidence_id": "ev_81e6139054ef",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "feature-set",
          "label": "deterministic funnel, segment and treatment features",
          "source": "diagnostic",
          "content": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "segments": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "group_outcomes": {
                "0": {
                  "count": 858.0,
                  "issued": 0.039627,
                  "net_premium": 37.215408
                },
                "1": {
                  "count": 342.0,
                  "issued": 0.087719,
                  "net_premium": 85.747398
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": true,
              "outcome_complete": true
            }
          },
          "content_digest": "65caa169dc7311e6a53ccc932d3a47417cacc23b7e0ee0fba0e219ce81888594",
          "created_at": "2026-08-01T07:36:16.261407+00:00"
        },
        {
          "evidence_id": "ev_b172a6cb8ffa",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "analysis",
          "label": "fixed-order log-chain decomposition",
          "source": "diagnostic",
          "content": {
            "method": "fixed-order log-chain decomposition",
            "baseline_premium": 62845.22,
            "current_premium": 61256.43,
            "total_log_change": -0.025612,
            "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
            "unexplained_residual": 0.0,
            "factors": [
              {
                "key": "active",
                "label": "活跃流量",
                "before": 1200,
                "after": 1200,
                "log_change": 0.0,
                "share": -0.0
              },
              {
                "key": "quote_rate",
                "label": "报价率",
                "before": 0.441667,
                "after": 0.420833,
                "log_change": -0.04832,
                "share": 1.886626
              },
              {
                "key": "apply_rate",
                "label": "投保率",
                "before": 0.401887,
                "after": 0.431683,
                "log_change": 0.071521,
                "share": -2.792495
              },
              {
                "key": "paid_rate",
                "label": "支付率",
                "before": 0.525822,
                "after": 0.504587,
                "log_change": -0.041222,
                "share": 1.609489
              },
              {
                "key": "issue_rate",
                "label": "出单率",
                "before": 0.589286,
                "after": 0.581818,
                "log_change": -0.012754,
                "share": 0.497972
              },
              {
                "key": "avg_premium",
                "label": "件均保费",
                "before": 952.2,
                "after": 957.13,
                "log_change": 0.005164,
                "share": -0.201625
              }
            ]
          },
          "content_digest": "1b1485aecc88c0acb16dbd57ea64cb6c8f0fc9304e3564dc31bb94cb67016b94",
          "created_at": "2026-08-01T07:36:16.262878+00:00"
        },
        {
          "evidence_id": "ev_0bdfb76a6d29",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "causal-readiness",
          "label": "metadata-derived five-layer readiness check",
          "source": "causal_evidence",
          "content": {
            "outcome": "DESCRIPTIVE_ONLY",
            "estimand": null,
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "not identified",
            "assumptions": [
              "observational co-movement only"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "contract_missing_fields": [],
              "missing_evidence": [],
              "design_checks": {
                "randomized_assignment": false,
                "assignment_verified": false,
                "trusted_assignment_provenance": false,
                "both_arms_present": true,
                "randomization_unit_matches": true
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.039627,
                "required_per_arm": 239,
                "actual_min_arm": 342,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": true,
                "reason_code": "DATA_COMPLETE"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": false,
                "reason_code": "POWER_NOT_ESTABLISHED"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L1/L2",
            "reason_codes": [
              "CAUSAL_DESIGN_NOT_VERIFIED",
              "POWER_NOT_ESTABLISHED"
            ],
            "allowed_claim_type": "descriptive_only"
          },
          "content_digest": "60ded0128b9bfa98189591ca4a74942e903395376ed81a84b479b7d8a256c97f",
          "created_at": "2026-08-01T07:36:16.264759+00:00"
        },
        {
          "evidence_id": "ev_6dab1b8b68e8",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "claim-ledger",
          "label": "structured claim and prohibited actions",
          "source": "causal_evidence",
          "content": {
            "claim_id": "claim-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "观察到",
              "同时出现",
              "对应"
            ],
            "prohibited_actions": [
              "声称导致",
              "自动触达个人",
              "直接上线配置"
            ],
            "uncertainty": "causal identification unavailable",
            "statement": "当前只能说明指标变化与候选因素同时出现，不能断言因果。"
          },
          "content_digest": "2ac414e7df998ef0794c05bb9a335cda4d9321c439657a8a86d83d7add0ebc15",
          "created_at": "2026-08-01T07:36:16.266866+00:00"
        },
        {
          "evidence_id": "ev_582d2e8de8c6",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "experiment",
          "label": "bounded experiment draft",
          "source": "experiment_planner",
          "content": {
            "experiment_id": "observational-ranking-change-A",
            "treatment": "new ranking",
            "unit": "user_id",
            "randomization": "observational",
            "primary_metric": "issued",
            "guardrails": [
              "refund_rate",
              "cancel_rate",
              "privacy_policy"
            ],
            "stop_rule": "guardrail breach or final observation window",
            "approval": "required"
          },
          "content_digest": "29a16bc8cbfd001339a8859447a61c4add4fa87de46f0c076cd1d02cfe862f1f",
          "created_at": "2026-08-01T07:36:16.266908+00:00"
        },
        {
          "evidence_id": "ev_cb5aae1f3c28",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "kind": "monitoring",
          "label": "pre-experiment monitoring placeholder",
          "source": "monitor_review",
          "content": {
            "status": "waiting for a real randomized window",
            "claim_policy": "descriptive-only"
          },
          "content_digest": "cec4f066c7e78a1e59d8992fbd10bddf3a7294101f4db921c0af3fe326474889",
          "created_at": "2026-08-01T07:36:16.277493+00:00"
        }
      ],
      "approvals": [
        {
          "approval_id": "approval_aab919e180cc",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "requested_by": "experiment_planner",
          "scope": {
            "experiment_id": "observational-ranking-change-A",
            "scope": "draft only; no production change"
          },
          "scope_digest": "35d74790ee4ac05ce9abef4b399cb39c17e4319dc4a1705ef9e82af6fcf585ef",
          "requested_state": "COMPLIANCE_REVIEWED",
          "requested_state_version": 8,
          "expected_state": null,
          "status": "APPROVED",
          "created_at": "2026-08-01T07:36:16.271566+00:00",
          "reviewer": "human-reviewer",
          "note": "draft approved for synthetic monitoring only",
          "decision_evidence": {
            "provider": "local-conformance",
            "reviewer_identity": "human-reviewer",
            "scope_digest": "35d74790ee4ac05ce9abef4b399cb39c17e4319dc4a1705ef9e82af6fcf585ef",
            "event_id": "approval_evt_7acc6f5b9f45"
          },
          "decided_at": "2026-08-01T07:36:16.275094+00:00"
        }
      ],
      "trace": [
        {
          "event_id": "evt_f950d96f99a6",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "TASK_CREATED",
          "actor": "control-plane",
          "payload": {
            "domain": "insurance-growth-attribution",
            "input_digest": "32814321a366c7ec45de2c8a32db5ca57395c0e3bff1a32fef1813ad46a162f2"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.229308+00:00"
        },
        {
          "event_id": "evt_cc5084a4b47d",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "metric_contract",
          "payload": {
            "evidence_id": "ev_fdc50522caa1",
            "kind": "metric-contract",
            "label": "versioned insurance metric contract",
            "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.256199+00:00"
        },
        {
          "event_id": "evt_f85630deacfa",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "intent",
          "payload": {
            "from": "RECEIVED",
            "to": "INTENT_PARSED",
            "reason": "business question normalized",
            "metadata": {
              "evidence_ref": "ev_fdc50522caa1"
            }
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.256211+00:00"
        },
        {
          "event_id": "evt_6e61ac93e122",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "intent",
          "payload": {
            "artifact_id": "art_f9406c543ca5",
            "artifact_type": "AnalysisIntent",
            "evidence_refs": [
              "ev_fdc50522caa1"
            ]
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.259186+00:00"
        },
        {
          "event_id": "evt_82bdf97aa7e7",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "metric_contract",
          "payload": {
            "from": "INTENT_PARSED",
            "to": "METRIC_CONFIRMED",
            "reason": "metric version accepted",
            "metadata": {}
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.259197+00:00"
        },
        {
          "event_id": "evt_92c0158661e9",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "metric_contract",
          "payload": {
            "artifact_id": "art_f8d72c5337ca",
            "artifact_type": "MetricContract",
            "evidence_refs": [
              "ev_fdc50522caa1"
            ]
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.260197+00:00"
        },
        {
          "event_id": "evt_a33726bb86f6",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "data_acquisition",
          "payload": {
            "evidence_id": "ev_b530a33ba475",
            "kind": "data-quality",
            "label": "schema and data quality report",
            "content_digest": "c444ebea24c9fa1faceba0bfcf7a014e477f556db3a92147c280a01988492dc2"
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.260227+00:00"
        },
        {
          "event_id": "evt_33d5dcf30dbb",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "data_acquisition",
          "payload": {
            "from": "METRIC_CONFIRMED",
            "to": "DATA_VALIDATED",
            "reason": "read-only dataset passed schema checks",
            "metadata": {
              "evidence_ref": "ev_b530a33ba475"
            }
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.260235+00:00"
        },
        {
          "event_id": "evt_c0963af8301c",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "data_acquisition",
          "payload": {
            "artifact_id": "art_8047b012ff09",
            "artifact_type": "DataQualityReport",
            "evidence_refs": [
              "ev_b530a33ba475"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.261363+00:00"
        },
        {
          "event_id": "evt_1c965b3975d2",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_81e6139054ef",
            "kind": "feature-set",
            "label": "deterministic funnel, segment and treatment features",
            "content_digest": "65caa169dc7311e6a53ccc932d3a47417cacc23b7e0ee0fba0e219ce81888594"
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.261414+00:00"
        },
        {
          "event_id": "evt_fb824d44ffb8",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_44719e68c3c9",
            "artifact_type": "FeatureSet",
            "evidence_refs": [
              "ev_b530a33ba475",
              "ev_81e6139054ef"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.261426+00:00"
        },
        {
          "event_id": "evt_8820dd397283",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "diagnostic",
          "payload": {
            "from": "DATA_VALIDATED",
            "to": "DIAGNOSING",
            "reason": "funnel and product structure decomposition is available",
            "metadata": {}
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.261435+00:00"
        },
        {
          "event_id": "evt_4b0514dba712",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_b172a6cb8ffa",
            "kind": "analysis",
            "label": "fixed-order log-chain decomposition",
            "content_digest": "1b1485aecc88c0acb16dbd57ea64cb6c8f0fc9304e3564dc31bb94cb67016b94"
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.262894+00:00"
        },
        {
          "event_id": "evt_43e07ce608ba",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_e093437af016",
            "artifact_type": "AttributionCandidateSet",
            "evidence_refs": [
              "ev_81e6139054ef",
              "ev_b172a6cb8ffa"
            ]
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.262908+00:00"
        },
        {
          "event_id": "evt_edf8244d21e5",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "DIAGNOSING",
            "to": "EVIDENCE_GRADED",
            "reason": "candidate causes are separated from causal claims",
            "metadata": {}
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.262918+00:00"
        },
        {
          "event_id": "evt_eb7b1a9e2970",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_0bdfb76a6d29",
            "kind": "causal-readiness",
            "label": "metadata-derived five-layer readiness check",
            "content_digest": "60ded0128b9bfa98189591ca4a74942e903395376ed81a84b479b7d8a256c97f"
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.264770+00:00"
        },
        {
          "event_id": "evt_488d5f19be00",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_de8a908f56ac",
            "artifact_type": "EvidenceReport",
            "evidence_refs": [
              "ev_b530a33ba475",
              "ev_81e6139054ef",
              "ev_0bdfb76a6d29"
            ]
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.264782+00:00"
        },
        {
          "event_id": "evt_4ed972d6d9e6",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "EVIDENCE_GRADED",
            "to": "DESCRIPTIVE_ONLY",
            "reason": "observable design evidence does not identify an effect",
            "metadata": {
              "reason_codes": [
                "CAUSAL_DESIGN_NOT_VERIFIED",
                "POWER_NOT_ESTABLISHED"
              ]
            }
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.264793+00:00"
        },
        {
          "event_id": "evt_94aa5ea040ea",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_6dab1b8b68e8",
            "kind": "claim-ledger",
            "label": "structured claim and prohibited actions",
            "content_digest": "2ac414e7df998ef0794c05bb9a335cda4d9321c439657a8a86d83d7add0ebc15"
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.266879+00:00"
        },
        {
          "event_id": "evt_c63cd442d75b",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_3a868321e4da",
            "artifact_type": "ClaimLedger",
            "evidence_refs": [
              "ev_6dab1b8b68e8"
            ]
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.266892+00:00"
        },
        {
          "event_id": "evt_645894d349b3",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "experiment_planner",
          "payload": {
            "evidence_id": "ev_582d2e8de8c6",
            "kind": "experiment",
            "label": "bounded experiment draft",
            "content_digest": "29a16bc8cbfd001339a8859447a61c4add4fa87de46f0c076cd1d02cfe862f1f"
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.266915+00:00"
        },
        {
          "event_id": "evt_54d5e4adf42f",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "experiment_planner",
          "payload": {
            "artifact_id": "art_f7512487e0d1",
            "artifact_type": "ExperimentSpec",
            "evidence_refs": [
              "ev_582d2e8de8c6"
            ]
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.266926+00:00"
        },
        {
          "event_id": "evt_9f83bc6d94d8",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "experiment_planner",
          "payload": {
            "from": "DESCRIPTIVE_ONLY",
            "to": "ACTION_DRAFTED",
            "reason": "only a pre-experiment draft is permitted",
            "metadata": {}
          },
          "state_version": 7,
          "created_at": "2026-08-01T07:36:16.266935+00:00"
        },
        {
          "event_id": "evt_7f605194b794",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "ACTION_DRAFTED",
            "to": "COMPLIANCE_REVIEWED",
            "reason": "descriptive-only claim policy passes",
            "metadata": {}
          },
          "state_version": 8,
          "created_at": "2026-08-01T07:36:16.269122+00:00"
        },
        {
          "event_id": "evt_9c1d9266aaba",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "APPROVAL_REQUESTED",
          "actor": "experiment_planner",
          "payload": {
            "approval_id": "approval_aab919e180cc",
            "scope": {
              "experiment_id": "observational-ranking-change-A",
              "scope": "draft only; no production change"
            },
            "scope_digest": "35d74790ee4ac05ce9abef4b399cb39c17e4319dc4a1705ef9e82af6fcf585ef",
            "expected_state": null
          },
          "state_version": 8,
          "created_at": "2026-08-01T07:36:16.271577+00:00"
        },
        {
          "event_id": "evt_787ec63743a5",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "experiment_planner",
          "payload": {
            "from": "COMPLIANCE_REVIEWED",
            "to": "AWAITING_APPROVAL",
            "reason": "draft still requires explicit human approval",
            "metadata": {
              "approval_id": "approval_aab919e180cc"
            }
          },
          "state_version": 9,
          "created_at": "2026-08-01T07:36:16.271589+00:00"
        },
        {
          "event_id": "evt_84c0dd296808",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "APPROVAL_DECIDED",
          "actor": "human-reviewer",
          "payload": {
            "approval_id": "approval_aab919e180cc",
            "decision": "APPROVED",
            "note": "draft approved for synthetic monitoring only",
            "scope_digest": "35d74790ee4ac05ce9abef4b399cb39c17e4319dc4a1705ef9e82af6fcf585ef",
            "decision_evidence": {
              "provider": "local-conformance",
              "reviewer_identity": "human-reviewer",
              "scope_digest": "35d74790ee4ac05ce9abef4b399cb39c17e4319dc4a1705ef9e82af6fcf585ef",
              "event_id": "approval_evt_7acc6f5b9f45"
            }
          },
          "state_version": 9,
          "created_at": "2026-08-01T07:36:16.275127+00:00"
        },
        {
          "event_id": "evt_53604fa410c9",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "AWAITING_APPROVAL",
            "to": "MONITORING",
            "reason": "approved draft enters a non-production monitoring state",
            "metadata": {}
          },
          "state_version": 10,
          "created_at": "2026-08-01T07:36:16.275140+00:00"
        },
        {
          "event_id": "evt_6803e9925fb6",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "monitor_review",
          "payload": {
            "evidence_id": "ev_cb5aae1f3c28",
            "kind": "monitoring",
            "label": "pre-experiment monitoring placeholder",
            "content_digest": "cec4f066c7e78a1e59d8992fbd10bddf3a7294101f4db921c0af3fe326474889"
          },
          "state_version": 10,
          "created_at": "2026-08-01T07:36:16.277506+00:00"
        },
        {
          "event_id": "evt_b9410be60026",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "monitor_review",
          "payload": {
            "artifact_id": "art_3fd92974ff37",
            "artifact_type": "MonitoringReport",
            "evidence_refs": [
              "ev_cb5aae1f3c28"
            ]
          },
          "state_version": 10,
          "created_at": "2026-08-01T07:36:16.277523+00:00"
        },
        {
          "event_id": "evt_af8cbd48d50d",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "MONITORING",
            "to": "REVIEWED",
            "reason": "descriptive case reviewed without causal overclaim",
            "metadata": {}
          },
          "state_version": 11,
          "created_at": "2026-08-01T07:36:16.277533+00:00"
        },
        {
          "event_id": "evt_89f322a2b3c8",
          "task_id": "T2-case-A",
          "trace_id": "trace_8c77f10e2c6b",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "REVIEWED",
            "to": "CLOSED",
            "reason": "evidence pack finalized",
            "metadata": {}
          },
          "state_version": 12,
          "created_at": "2026-08-01T07:36:16.280011+00:00"
        }
      ],
      "topologies": [
        {
          "team_id": "insurance-growth-team",
          "control_plane": "AgentTeamsControlPlane",
          "nodes": [
            "intent",
            "metric_contract",
            "data_acquisition",
            "diagnostic",
            "causal_evidence",
            "experiment_planner",
            "monitor_review"
          ],
          "edges": [
            {
              "from": "intent",
              "to": "metric_contract",
              "mode": "sequential"
            },
            {
              "from": "metric_contract",
              "to": "data_acquisition",
              "mode": "contract-gated"
            },
            {
              "from": "data_acquisition",
              "to": "diagnostic",
              "mode": "read-only"
            },
            {
              "from": "diagnostic",
              "to": "causal_evidence",
              "mode": "fan-in",
              "input": "funnel+mix+segment artifacts"
            },
            {
              "from": "causal_evidence",
              "to": "experiment_planner",
              "mode": "evidence-gated"
            },
            {
              "from": "experiment_planner",
              "to": "monitor_review",
              "mode": "approval-gated"
            }
          ],
          "execution_semantics": {
            "fan_out": [
              "diagnostic -> funnel, product_mix, segment, event_alignment skills"
            ],
            "fan_in": "causal_evidence consumes typed diagnostic artifacts",
            "conflict_policy": "ClaimPolicyGuard is deterministic and can block model output"
          }
        }
      ],
      "track": "track2",
      "case": "A",
      "agents": [
        "intent",
        "metric_contract",
        "data_acquisition",
        "diagnostic",
        "causal_evidence",
        "experiment_planner",
        "monitor_review"
      ],
      "skills": [
        "MetricContractResolver",
        "SchemaProfiler",
        "DataQualityGate",
        "ReadOnlyQueryPlanner",
        "FunnelDecomposer",
        "ProductMixDecomposer",
        "SegmentProfiler",
        "EventAligner",
        "CausalReadinessCheck",
        "ExperimentPlanner",
        "ExperimentMonitor",
        "ClaimPolicyGuard",
        "WeeklyBriefComposer"
      ],
      "metric_contract": {
        "metric_id": "insurance-premium-v2",
        "version": "2026-07-31",
        "identity": "user_id",
        "funnel": [
          "active",
          "quoted",
          "applied",
          "paid",
          "issued"
        ],
        "outcomes": [
          "issued",
          "net_premium"
        ],
        "treatment": "treatment",
        "premium": "net premium after refund and cancellation",
        "window": "7d",
        "owner": "growth-analytics"
      },
      "experiment_metadata": {
        "treatment_column": "treatment",
        "window_closed": true,
        "outcome_complete": true,
        "minimum_detectable_effect": 0.05,
        "alpha": 0.05,
        "target_power": 0.8,
        "approval_required": true,
        "guardrails": [
          "refund_rate",
          "cancel_rate",
          "privacy_policy"
        ],
        "stop_rule": "guardrail breach or final observation window",
        "production_auto_action": false,
        "experiment_id": "observational-ranking-change-A",
        "activity_config": "ranking-v2-observed",
        "assignment_method": "observational",
        "assignment_provenance": "event_log",
        "assignment_verified": false,
        "randomization_unit": "user_id",
        "control_group": 0,
        "treatment_group": 1
      },
      "feature_set": {
        "schema_version": "1.0",
        "row_count": 1200,
        "observation_unit": "user_id",
        "available_fields": [
          "active",
          "applied",
          "assignment",
          "cancel",
          "channel",
          "channel_quality",
          "gross_premium",
          "issued",
          "net_premium",
          "paid",
          "product_mix",
          "quoted",
          "refund",
          "season",
          "treatment",
          "user_id",
          "user_quality"
        ],
        "funnel": {
          "active": 1200,
          "quoted": 505,
          "applied": 218,
          "paid": 110,
          "issued": 64,
          "net_premium": 61256.43,
          "quote_rate": 0.420833,
          "apply_rate": 0.431683,
          "paid_rate": 0.504587,
          "issue_rate": 0.581818,
          "issued_user_rate": 0.053333,
          "avg_premium": 957.13
        },
        "segments": {
          "channel_distribution": {
            "new": 342,
            "owned": 858
          },
          "assignment_distribution": {
            "observational-confounded": 1200
          },
          "average_product_mix": 0.40978
        },
        "treatment": {
          "column": "treatment",
          "group_counts": {
            "0": 858,
            "1": 342
          },
          "group_outcomes": {
            "0": {
              "count": 858.0,
              "issued": 0.039627,
              "net_premium": 37.215408
            },
            "1": {
              "count": 342.0,
              "issued": 0.087719,
              "net_premium": 85.747398
            }
          }
        },
        "data_quality": {
          "missing_row_fields": [],
          "missing_experiment_fields": [],
          "null_counts": {
            "active": 0,
            "applied": 0,
            "issued": 0,
            "net_premium": 0,
            "paid": 0,
            "quoted": 0,
            "treatment": 0,
            "user_id": 0
          },
          "duplicate_count": 0,
          "duplicate_rate": 0.0,
          "window_closed": true,
          "outcome_complete": true
        }
      },
      "metrics": {
        "baseline": {
          "active": 1200,
          "quoted": 530,
          "applied": 213,
          "paid": 112,
          "issued": 66,
          "net_premium": 62845.22,
          "quote_rate": 0.441667,
          "apply_rate": 0.401887,
          "paid_rate": 0.525822,
          "issue_rate": 0.589286,
          "issued_user_rate": 0.055,
          "avg_premium": 952.2
        },
        "current": {
          "active": 1200,
          "quoted": 505,
          "applied": 218,
          "paid": 110,
          "issued": 64,
          "net_premium": 61256.43,
          "quote_rate": 0.420833,
          "apply_rate": 0.431683,
          "paid_rate": 0.504587,
          "issue_rate": 0.581818,
          "issued_user_rate": 0.053333,
          "avg_premium": 957.13
        }
      },
      "decomposition": {
        "method": "fixed-order log-chain decomposition",
        "baseline_premium": 62845.22,
        "current_premium": 61256.43,
        "total_log_change": -0.025612,
        "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
        "unexplained_residual": 0.0,
        "factors": [
          {
            "key": "active",
            "label": "活跃流量",
            "before": 1200,
            "after": 1200,
            "log_change": 0.0,
            "share": -0.0
          },
          {
            "key": "quote_rate",
            "label": "报价率",
            "before": 0.441667,
            "after": 0.420833,
            "log_change": -0.04832,
            "share": 1.886626
          },
          {
            "key": "apply_rate",
            "label": "投保率",
            "before": 0.401887,
            "after": 0.431683,
            "log_change": 0.071521,
            "share": -2.792495
          },
          {
            "key": "paid_rate",
            "label": "支付率",
            "before": 0.525822,
            "after": 0.504587,
            "log_change": -0.041222,
            "share": 1.609489
          },
          {
            "key": "issue_rate",
            "label": "出单率",
            "before": 0.589286,
            "after": 0.581818,
            "log_change": -0.012754,
            "share": 0.497972
          },
          {
            "key": "avg_premium",
            "label": "件均保费",
            "before": 952.2,
            "after": 957.13,
            "log_change": 0.005164,
            "share": -0.201625
          }
        ]
      },
      "causal_readiness": {
        "outcome": "DESCRIPTIVE_ONLY",
        "estimand": null,
        "observation_unit": "user_id",
        "attribution_window": "7d",
        "identification_strategy": "not identified",
        "assumptions": [
          "observational co-movement only"
        ],
        "diagnostics": {
          "sample_size": 1200,
          "group_counts": {
            "0": 858,
            "1": 342
          },
          "contract_missing_fields": [],
          "missing_evidence": [],
          "design_checks": {
            "randomized_assignment": false,
            "assignment_verified": false,
            "trusted_assignment_provenance": false,
            "both_arms_present": true,
            "randomization_unit_matches": true
          },
          "power": {
            "method": "two-arm binary normal approximation",
            "alpha": 0.05,
            "target_power": 0.8,
            "minimum_detectable_effect": 0.05,
            "baseline_rate": 0.039627,
            "required_per_arm": 239,
            "actual_min_arm": 342,
            "passed": true
          },
          "governance_checks": {
            "approval_required": true,
            "guardrails_defined": true,
            "stop_rule_defined": true,
            "production_auto_action_disabled": true
          }
        },
        "gates": [
          {
            "name": "semantic",
            "passed": true,
            "reason_code": "SEMANTIC_DEFINED"
          },
          {
            "name": "data",
            "passed": true,
            "reason_code": "DATA_COMPLETE"
          },
          {
            "name": "design",
            "passed": false,
            "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
          },
          {
            "name": "statistics",
            "passed": false,
            "reason_code": "POWER_NOT_ESTABLISHED"
          },
          {
            "name": "governance",
            "passed": true,
            "reason_code": "GOVERNANCE_READY"
          }
        ],
        "evidence_level": "L1/L2",
        "reason_codes": [
          "CAUSAL_DESIGN_NOT_VERIFIED",
          "POWER_NOT_ESTABLISHED"
        ],
        "allowed_claim_type": "descriptive_only"
      },
      "claim": {
        "claim_id": "claim-001",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "allowed_verbs": [
          "观察到",
          "同时出现",
          "对应"
        ],
        "prohibited_actions": [
          "声称导致",
          "自动触达个人",
          "直接上线配置"
        ],
        "uncertainty": "causal identification unavailable",
        "statement": "当前只能说明指标变化与候选因素同时出现，不能断言因果。"
      },
      "sample": [
        {
          "user_id": "u0000",
          "active": 1,
          "season": 0.0,
          "channel": "owned",
          "channel_quality": 0.0816,
          "user_quality": 0.7129,
          "product_mix": 0.3058,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 0,
          "applied": 0,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0001",
          "active": 1,
          "season": 0.0,
          "channel": "owned",
          "channel_quality": -0.9559,
          "user_quality": 0.1043,
          "product_mix": 0.4253,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 0,
          "applied": 0,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0002",
          "active": 1,
          "season": 0.08,
          "channel": "owned",
          "channel_quality": 0.3187,
          "user_quality": -0.281,
          "product_mix": 0.4893,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 1,
          "applied": 1,
          "paid": 1,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        }
      ],
      "summary": {
        "final_state": "CLOSED",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "causal_outcome": "DESCRIPTIVE_ONLY"
      },
      "evidence_pack_path": "runtime_data/evidence/T2-case-A.json",
      "evidence_pack_relative_path": "evidence/T2-case-A.json"
    },
    "B": {
      "task_id": "T2-case-B",
      "trace_id": "trace_c59b1b0f6fa6",
      "domain": "insurance-growth-attribution",
      "input_payload": {
        "case": "B",
        "question": "DAU rose while premium declined; explain what is known and what should be tested."
      },
      "state": "CLOSED",
      "state_version": 6,
      "artifacts": [
        {
          "artifact_id": "art_4ed96ad36edc",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "AnalysisIntent",
          "schema_version": "1.0",
          "producer": "intent",
          "payload": {
            "question": "DAU rose while premium declined; explain what is known and what should be tested.",
            "target": "premium growth and conversion",
            "unit": "user_id"
          },
          "evidence_refs": [
            "ev_2cba50e92302"
          ],
          "created_at": "2026-08-01T07:36:16.317671+00:00"
        },
        {
          "artifact_id": "art_6f1727ccdbbf",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "MetricContract",
          "schema_version": "1.0",
          "producer": "metric_contract",
          "payload": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "evidence_refs": [
            "ev_2cba50e92302"
          ],
          "created_at": "2026-08-01T07:36:16.318687+00:00"
        },
        {
          "artifact_id": "art_3404f1e02de4",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "DataQualityReport",
          "schema_version": "1.0",
          "producer": "data_acquisition",
          "payload": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [
              "activity_config",
              "assignment_method",
              "assignment_provenance",
              "assignment_verified",
              "control_group",
              "experiment_id",
              "treatment_group"
            ],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": false,
            "outcome_complete": false,
            "missing_fields": [
              "activity_config",
              "assignment_method",
              "assignment_provenance",
              "assignment_verified",
              "control_group",
              "experiment_id",
              "treatment_group"
            ]
          },
          "evidence_refs": [
            "ev_4ac68e990dee"
          ],
          "created_at": "2026-08-01T07:36:16.319936+00:00"
        },
        {
          "artifact_id": "art_efa7e0594815",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "FeatureSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "segments": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "group_outcomes": {
                "0": {
                  "count": 858.0,
                  "issued": 0.039627,
                  "net_premium": 37.215408
                },
                "1": {
                  "count": 342.0,
                  "issued": 0.087719,
                  "net_premium": 85.747398
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [
                "activity_config",
                "assignment_method",
                "assignment_provenance",
                "assignment_verified",
                "control_group",
                "experiment_id",
                "treatment_group"
              ],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": false,
              "outcome_complete": false
            }
          },
          "evidence_refs": [
            "ev_4ac68e990dee",
            "ev_4557b236b349"
          ],
          "created_at": "2026-08-01T07:36:16.320012+00:00"
        },
        {
          "artifact_id": "art_f00e54d6ed55",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "AttributionCandidateSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "metrics": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "features": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "decomposition": {
              "method": "fixed-order log-chain decomposition",
              "baseline_premium": 62845.22,
              "current_premium": 61256.43,
              "total_log_change": -0.025612,
              "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
              "unexplained_residual": 0.0,
              "factors": [
                {
                  "key": "active",
                  "label": "活跃流量",
                  "before": 1200,
                  "after": 1200,
                  "log_change": 0.0,
                  "share": -0.0
                },
                {
                  "key": "quote_rate",
                  "label": "报价率",
                  "before": 0.441667,
                  "after": 0.420833,
                  "log_change": -0.04832,
                  "share": 1.886626
                },
                {
                  "key": "apply_rate",
                  "label": "投保率",
                  "before": 0.401887,
                  "after": 0.431683,
                  "log_change": 0.071521,
                  "share": -2.792495
                },
                {
                  "key": "paid_rate",
                  "label": "支付率",
                  "before": 0.525822,
                  "after": 0.504587,
                  "log_change": -0.041222,
                  "share": 1.609489
                },
                {
                  "key": "issue_rate",
                  "label": "出单率",
                  "before": 0.589286,
                  "after": 0.581818,
                  "log_change": -0.012754,
                  "share": 0.497972
                },
                {
                  "key": "avg_premium",
                  "label": "件均保费",
                  "before": 952.2,
                  "after": 957.13,
                  "log_change": 0.005164,
                  "share": -0.201625
                }
              ]
            },
            "interpretation": "structural contribution only"
          },
          "evidence_refs": [
            "ev_4557b236b349",
            "ev_03a968e85341"
          ],
          "created_at": "2026-08-01T07:36:16.321822+00:00"
        },
        {
          "artifact_id": "art_77f75bdc7507",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "EvidenceReport",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "outcome": "DATA_INSUFFICIENT",
            "estimand": null,
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "not identified",
            "assumptions": [
              "observational co-movement only"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "contract_missing_fields": [],
              "missing_evidence": [
                "activity_config",
                "assignment_method",
                "assignment_provenance",
                "assignment_verified",
                "closed_experiment_window",
                "complete_outcome_observation",
                "control_group",
                "experiment_id",
                "treatment_group"
              ],
              "design_checks": {
                "randomized_assignment": false,
                "assignment_verified": false,
                "trusted_assignment_provenance": false,
                "both_arms_present": true,
                "randomization_unit_matches": false
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.039627,
                "required_per_arm": 239,
                "actual_min_arm": 342,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": false,
                "reason_code": "DATA_INSUFFICIENT"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": false,
                "reason_code": "POWER_NOT_ESTABLISHED"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L1/L2",
            "reason_codes": [
              "DATA_INSUFFICIENT",
              "CAUSAL_DESIGN_NOT_VERIFIED",
              "POWER_NOT_ESTABLISHED"
            ],
            "allowed_claim_type": "descriptive_only"
          },
          "evidence_refs": [
            "ev_4ac68e990dee",
            "ev_4557b236b349",
            "ev_503f79776da0"
          ],
          "created_at": "2026-08-01T07:36:16.321876+00:00"
        },
        {
          "artifact_id": "art_fbdec7470386",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "artifact_type": "ClaimLedger",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "claim_id": "claim-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "当前缺少",
              "需要补充"
            ],
            "prohibited_actions": [
              "声称导致",
              "自动触达个人",
              "直接上线配置"
            ],
            "uncertainty": "required evidence is missing",
            "statement": "当前证据不足，必须补齐实验配置、观察窗口或结果数据后才能评估因果效应。"
          },
          "evidence_refs": [
            "ev_53a54562c757"
          ],
          "created_at": "2026-08-01T07:36:16.323915+00:00"
        }
      ],
      "evidence": [
        {
          "evidence_id": "ev_2cba50e92302",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "metric-contract",
          "label": "versioned insurance metric contract",
          "source": "metric_contract",
          "content": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba",
          "created_at": "2026-08-01T07:36:16.313760+00:00"
        },
        {
          "evidence_id": "ev_4ac68e990dee",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "data-quality",
          "label": "schema and data quality report",
          "source": "data_acquisition",
          "content": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [
              "activity_config",
              "assignment_method",
              "assignment_provenance",
              "assignment_verified",
              "control_group",
              "experiment_id",
              "treatment_group"
            ],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": false,
            "outcome_complete": false,
            "missing_fields": [
              "activity_config",
              "assignment_method",
              "assignment_provenance",
              "assignment_verified",
              "control_group",
              "experiment_id",
              "treatment_group"
            ]
          },
          "content_digest": "72df25b5e893e1615c7010445113fdcac747d78ba6ceb771e3a4829b6b135a3c",
          "created_at": "2026-08-01T07:36:16.318730+00:00"
        },
        {
          "evidence_id": "ev_4557b236b349",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "feature-set",
          "label": "deterministic funnel, segment and treatment features",
          "source": "diagnostic",
          "content": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 505,
              "applied": 218,
              "paid": 110,
              "issued": 64,
              "net_premium": 61256.43,
              "quote_rate": 0.420833,
              "apply_rate": 0.431683,
              "paid_rate": 0.504587,
              "issue_rate": 0.581818,
              "issued_user_rate": 0.053333,
              "avg_premium": 957.13
            },
            "segments": {
              "channel_distribution": {
                "new": 342,
                "owned": 858
              },
              "assignment_distribution": {
                "observational-confounded": 1200
              },
              "average_product_mix": 0.40978
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "group_outcomes": {
                "0": {
                  "count": 858.0,
                  "issued": 0.039627,
                  "net_premium": 37.215408
                },
                "1": {
                  "count": 342.0,
                  "issued": 0.087719,
                  "net_premium": 85.747398
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [
                "activity_config",
                "assignment_method",
                "assignment_provenance",
                "assignment_verified",
                "control_group",
                "experiment_id",
                "treatment_group"
              ],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": false,
              "outcome_complete": false
            }
          },
          "content_digest": "1a7a791c3f97c7ca3c94209b8d0a4f8680224c3b2ce1150a51ca2298a5001272",
          "created_at": "2026-08-01T07:36:16.319998+00:00"
        },
        {
          "evidence_id": "ev_03a968e85341",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "analysis",
          "label": "fixed-order log-chain decomposition",
          "source": "diagnostic",
          "content": {
            "method": "fixed-order log-chain decomposition",
            "baseline_premium": 62845.22,
            "current_premium": 61256.43,
            "total_log_change": -0.025612,
            "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
            "unexplained_residual": 0.0,
            "factors": [
              {
                "key": "active",
                "label": "活跃流量",
                "before": 1200,
                "after": 1200,
                "log_change": 0.0,
                "share": -0.0
              },
              {
                "key": "quote_rate",
                "label": "报价率",
                "before": 0.441667,
                "after": 0.420833,
                "log_change": -0.04832,
                "share": 1.886626
              },
              {
                "key": "apply_rate",
                "label": "投保率",
                "before": 0.401887,
                "after": 0.431683,
                "log_change": 0.071521,
                "share": -2.792495
              },
              {
                "key": "paid_rate",
                "label": "支付率",
                "before": 0.525822,
                "after": 0.504587,
                "log_change": -0.041222,
                "share": 1.609489
              },
              {
                "key": "issue_rate",
                "label": "出单率",
                "before": 0.589286,
                "after": 0.581818,
                "log_change": -0.012754,
                "share": 0.497972
              },
              {
                "key": "avg_premium",
                "label": "件均保费",
                "before": 952.2,
                "after": 957.13,
                "log_change": 0.005164,
                "share": -0.201625
              }
            ]
          },
          "content_digest": "1b1485aecc88c0acb16dbd57ea64cb6c8f0fc9304e3564dc31bb94cb67016b94",
          "created_at": "2026-08-01T07:36:16.321803+00:00"
        },
        {
          "evidence_id": "ev_503f79776da0",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "causal-readiness",
          "label": "metadata-derived five-layer readiness check",
          "source": "causal_evidence",
          "content": {
            "outcome": "DATA_INSUFFICIENT",
            "estimand": null,
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "not identified",
            "assumptions": [
              "observational co-movement only"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 858,
                "1": 342
              },
              "contract_missing_fields": [],
              "missing_evidence": [
                "activity_config",
                "assignment_method",
                "assignment_provenance",
                "assignment_verified",
                "closed_experiment_window",
                "complete_outcome_observation",
                "control_group",
                "experiment_id",
                "treatment_group"
              ],
              "design_checks": {
                "randomized_assignment": false,
                "assignment_verified": false,
                "trusted_assignment_provenance": false,
                "both_arms_present": true,
                "randomization_unit_matches": false
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.039627,
                "required_per_arm": 239,
                "actual_min_arm": 342,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": false,
                "reason_code": "DATA_INSUFFICIENT"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": false,
                "reason_code": "POWER_NOT_ESTABLISHED"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L1/L2",
            "reason_codes": [
              "DATA_INSUFFICIENT",
              "CAUSAL_DESIGN_NOT_VERIFIED",
              "POWER_NOT_ESTABLISHED"
            ],
            "allowed_claim_type": "descriptive_only"
          },
          "content_digest": "5062ff051f6ae7f8035fb0d63bd23abf959a1e08ba01e28f8ff4d1bb0ce83aa6",
          "created_at": "2026-08-01T07:36:16.321863+00:00"
        },
        {
          "evidence_id": "ev_53a54562c757",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "kind": "claim-ledger",
          "label": "structured claim and prohibited actions",
          "source": "causal_evidence",
          "content": {
            "claim_id": "claim-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "当前缺少",
              "需要补充"
            ],
            "prohibited_actions": [
              "声称导致",
              "自动触达个人",
              "直接上线配置"
            ],
            "uncertainty": "required evidence is missing",
            "statement": "当前证据不足，必须补齐实验配置、观察窗口或结果数据后才能评估因果效应。"
          },
          "content_digest": "8bfe4304e4422bf87398e82c79a36b1fe2e0e86a5e20eb1fbe38c68e2e69b3dd",
          "created_at": "2026-08-01T07:36:16.323894+00:00"
        }
      ],
      "approvals": [],
      "trace": [
        {
          "event_id": "evt_4e403680c7bb",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "TASK_CREATED",
          "actor": "control-plane",
          "payload": {
            "domain": "insurance-growth-attribution",
            "input_digest": "576b62573e0b3abf21b562d091c9a1bbe3a2fc13284f72eca87fb1860be70c41"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.287042+00:00"
        },
        {
          "event_id": "evt_4e2eede017f5",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "metric_contract",
          "payload": {
            "evidence_id": "ev_2cba50e92302",
            "kind": "metric-contract",
            "label": "versioned insurance metric contract",
            "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.313778+00:00"
        },
        {
          "event_id": "evt_e9c44a53922c",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "intent",
          "payload": {
            "from": "RECEIVED",
            "to": "INTENT_PARSED",
            "reason": "business question normalized",
            "metadata": {
              "evidence_ref": "ev_2cba50e92302"
            }
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.313793+00:00"
        },
        {
          "event_id": "evt_6fee1fd5f53f",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "intent",
          "payload": {
            "artifact_id": "art_4ed96ad36edc",
            "artifact_type": "AnalysisIntent",
            "evidence_refs": [
              "ev_2cba50e92302"
            ]
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.317688+00:00"
        },
        {
          "event_id": "evt_5c549d1ae140",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "metric_contract",
          "payload": {
            "from": "INTENT_PARSED",
            "to": "METRIC_CONFIRMED",
            "reason": "metric version accepted",
            "metadata": {}
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.317700+00:00"
        },
        {
          "event_id": "evt_6c8df389aed0",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "metric_contract",
          "payload": {
            "artifact_id": "art_6f1727ccdbbf",
            "artifact_type": "MetricContract",
            "evidence_refs": [
              "ev_2cba50e92302"
            ]
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.318697+00:00"
        },
        {
          "event_id": "evt_97b6a7e6cba5",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "data_acquisition",
          "payload": {
            "evidence_id": "ev_4ac68e990dee",
            "kind": "data-quality",
            "label": "schema and data quality report",
            "content_digest": "72df25b5e893e1615c7010445113fdcac747d78ba6ceb771e3a4829b6b135a3c"
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.318737+00:00"
        },
        {
          "event_id": "evt_324da845b150",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "data_acquisition",
          "payload": {
            "from": "METRIC_CONFIRMED",
            "to": "DATA_VALIDATED",
            "reason": "read-only dataset passed schema checks",
            "metadata": {
              "evidence_ref": "ev_4ac68e990dee"
            }
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.318747+00:00"
        },
        {
          "event_id": "evt_08f24850f4c4",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "data_acquisition",
          "payload": {
            "artifact_id": "art_3404f1e02de4",
            "artifact_type": "DataQualityReport",
            "evidence_refs": [
              "ev_4ac68e990dee"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.319946+00:00"
        },
        {
          "event_id": "evt_f02f1739a50c",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_4557b236b349",
            "kind": "feature-set",
            "label": "deterministic funnel, segment and treatment features",
            "content_digest": "1a7a791c3f97c7ca3c94209b8d0a4f8680224c3b2ce1150a51ca2298a5001272"
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.320005+00:00"
        },
        {
          "event_id": "evt_b9196d3efdb7",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_efa7e0594815",
            "artifact_type": "FeatureSet",
            "evidence_refs": [
              "ev_4ac68e990dee",
              "ev_4557b236b349"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.320017+00:00"
        },
        {
          "event_id": "evt_e8e368be4ca3",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "data_acquisition",
          "payload": {
            "from": "DATA_VALIDATED",
            "to": "DATA_INSUFFICIENT",
            "reason": "required experiment evidence is missing",
            "metadata": {
              "missing_evidence": [
                "activity_config",
                "assignment_method",
                "assignment_provenance",
                "assignment_verified",
                "closed_experiment_window",
                "complete_outcome_observation",
                "control_group",
                "experiment_id",
                "treatment_group"
              ]
            }
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.320028+00:00"
        },
        {
          "event_id": "evt_a0a1942106a8",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_03a968e85341",
            "kind": "analysis",
            "label": "fixed-order log-chain decomposition",
            "content_digest": "1b1485aecc88c0acb16dbd57ea64cb6c8f0fc9304e3564dc31bb94cb67016b94"
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.321814+00:00"
        },
        {
          "event_id": "evt_a6ffe6de128a",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_f00e54d6ed55",
            "artifact_type": "AttributionCandidateSet",
            "evidence_refs": [
              "ev_4557b236b349",
              "ev_03a968e85341"
            ]
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.321828+00:00"
        },
        {
          "event_id": "evt_3c349035450f",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_503f79776da0",
            "kind": "causal-readiness",
            "label": "metadata-derived five-layer readiness check",
            "content_digest": "5062ff051f6ae7f8035fb0d63bd23abf959a1e08ba01e28f8ff4d1bb0ce83aa6"
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.321870+00:00"
        },
        {
          "event_id": "evt_00b9868af961",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_77f75bdc7507",
            "artifact_type": "EvidenceReport",
            "evidence_refs": [
              "ev_4ac68e990dee",
              "ev_4557b236b349",
              "ev_503f79776da0"
            ]
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.321882+00:00"
        },
        {
          "event_id": "evt_50a1cc3da1f7",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "DATA_INSUFFICIENT",
            "to": "DESCRIPTIVE_ONLY",
            "reason": "required experiment metadata is absent",
            "metadata": {
              "reason_codes": [
                "DATA_INSUFFICIENT",
                "CAUSAL_DESIGN_NOT_VERIFIED",
                "POWER_NOT_ESTABLISHED"
              ]
            }
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.321892+00:00"
        },
        {
          "event_id": "evt_b3258ba89e90",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_53a54562c757",
            "kind": "claim-ledger",
            "label": "structured claim and prohibited actions",
            "content_digest": "8bfe4304e4422bf87398e82c79a36b1fe2e0e86a5e20eb1fbe38c68e2e69b3dd"
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.323907+00:00"
        },
        {
          "event_id": "evt_1fd2d40b3b7d",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_fbdec7470386",
            "artifact_type": "ClaimLedger",
            "evidence_refs": [
              "ev_53a54562c757"
            ]
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.323921+00:00"
        },
        {
          "event_id": "evt_b95bf6fb7cc5",
          "task_id": "T2-case-B",
          "trace_id": "trace_c59b1b0f6fa6",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "DESCRIPTIVE_ONLY",
            "to": "CLOSED",
            "reason": "closed with safe refusal and补数路径",
            "metadata": {}
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.323932+00:00"
        }
      ],
      "topologies": [
        {
          "team_id": "insurance-growth-team",
          "control_plane": "AgentTeamsControlPlane",
          "nodes": [
            "intent",
            "metric_contract",
            "data_acquisition",
            "diagnostic",
            "causal_evidence",
            "experiment_planner",
            "monitor_review"
          ],
          "edges": [
            {
              "from": "intent",
              "to": "metric_contract",
              "mode": "sequential"
            },
            {
              "from": "metric_contract",
              "to": "data_acquisition",
              "mode": "contract-gated"
            },
            {
              "from": "data_acquisition",
              "to": "diagnostic",
              "mode": "read-only"
            },
            {
              "from": "diagnostic",
              "to": "causal_evidence",
              "mode": "fan-in",
              "input": "funnel+mix+segment artifacts"
            },
            {
              "from": "causal_evidence",
              "to": "experiment_planner",
              "mode": "evidence-gated"
            },
            {
              "from": "experiment_planner",
              "to": "monitor_review",
              "mode": "approval-gated"
            }
          ],
          "execution_semantics": {
            "fan_out": [
              "diagnostic -> funnel, product_mix, segment, event_alignment skills"
            ],
            "fan_in": "causal_evidence consumes typed diagnostic artifacts",
            "conflict_policy": "ClaimPolicyGuard is deterministic and can block model output"
          }
        }
      ],
      "track": "track2",
      "case": "B",
      "agents": [
        "intent",
        "metric_contract",
        "data_acquisition",
        "diagnostic",
        "causal_evidence",
        "experiment_planner",
        "monitor_review"
      ],
      "skills": [
        "MetricContractResolver",
        "SchemaProfiler",
        "DataQualityGate",
        "ReadOnlyQueryPlanner",
        "FunnelDecomposer",
        "ProductMixDecomposer",
        "SegmentProfiler",
        "EventAligner",
        "CausalReadinessCheck",
        "ExperimentPlanner",
        "ExperimentMonitor",
        "ClaimPolicyGuard",
        "WeeklyBriefComposer"
      ],
      "metric_contract": {
        "metric_id": "insurance-premium-v2",
        "version": "2026-07-31",
        "identity": "user_id",
        "funnel": [
          "active",
          "quoted",
          "applied",
          "paid",
          "issued"
        ],
        "outcomes": [
          "issued",
          "net_premium"
        ],
        "treatment": "treatment",
        "premium": "net premium after refund and cancellation",
        "window": "7d",
        "owner": "growth-analytics"
      },
      "experiment_metadata": {
        "treatment_column": "treatment",
        "window_closed": false,
        "outcome_complete": false,
        "minimum_detectable_effect": 0.05,
        "alpha": 0.05,
        "target_power": 0.8,
        "approval_required": true,
        "guardrails": [
          "refund_rate",
          "cancel_rate",
          "privacy_policy"
        ],
        "stop_rule": "guardrail breach or final observation window",
        "production_auto_action": false,
        "experiment_id": null,
        "activity_config": null,
        "assignment_method": null,
        "assignment_provenance": null,
        "assignment_verified": null,
        "randomization_unit": null,
        "control_group": null,
        "treatment_group": null
      },
      "feature_set": {
        "schema_version": "1.0",
        "row_count": 1200,
        "observation_unit": "user_id",
        "available_fields": [
          "active",
          "applied",
          "assignment",
          "cancel",
          "channel",
          "channel_quality",
          "gross_premium",
          "issued",
          "net_premium",
          "paid",
          "product_mix",
          "quoted",
          "refund",
          "season",
          "treatment",
          "user_id",
          "user_quality"
        ],
        "funnel": {
          "active": 1200,
          "quoted": 505,
          "applied": 218,
          "paid": 110,
          "issued": 64,
          "net_premium": 61256.43,
          "quote_rate": 0.420833,
          "apply_rate": 0.431683,
          "paid_rate": 0.504587,
          "issue_rate": 0.581818,
          "issued_user_rate": 0.053333,
          "avg_premium": 957.13
        },
        "segments": {
          "channel_distribution": {
            "new": 342,
            "owned": 858
          },
          "assignment_distribution": {
            "observational-confounded": 1200
          },
          "average_product_mix": 0.40978
        },
        "treatment": {
          "column": "treatment",
          "group_counts": {
            "0": 858,
            "1": 342
          },
          "group_outcomes": {
            "0": {
              "count": 858.0,
              "issued": 0.039627,
              "net_premium": 37.215408
            },
            "1": {
              "count": 342.0,
              "issued": 0.087719,
              "net_premium": 85.747398
            }
          }
        },
        "data_quality": {
          "missing_row_fields": [],
          "missing_experiment_fields": [
            "activity_config",
            "assignment_method",
            "assignment_provenance",
            "assignment_verified",
            "control_group",
            "experiment_id",
            "treatment_group"
          ],
          "null_counts": {
            "active": 0,
            "applied": 0,
            "issued": 0,
            "net_premium": 0,
            "paid": 0,
            "quoted": 0,
            "treatment": 0,
            "user_id": 0
          },
          "duplicate_count": 0,
          "duplicate_rate": 0.0,
          "window_closed": false,
          "outcome_complete": false
        }
      },
      "metrics": {
        "baseline": {
          "active": 1200,
          "quoted": 530,
          "applied": 213,
          "paid": 112,
          "issued": 66,
          "net_premium": 62845.22,
          "quote_rate": 0.441667,
          "apply_rate": 0.401887,
          "paid_rate": 0.525822,
          "issue_rate": 0.589286,
          "issued_user_rate": 0.055,
          "avg_premium": 952.2
        },
        "current": {
          "active": 1200,
          "quoted": 505,
          "applied": 218,
          "paid": 110,
          "issued": 64,
          "net_premium": 61256.43,
          "quote_rate": 0.420833,
          "apply_rate": 0.431683,
          "paid_rate": 0.504587,
          "issue_rate": 0.581818,
          "issued_user_rate": 0.053333,
          "avg_premium": 957.13
        }
      },
      "decomposition": {
        "method": "fixed-order log-chain decomposition",
        "baseline_premium": 62845.22,
        "current_premium": 61256.43,
        "total_log_change": -0.025612,
        "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
        "unexplained_residual": 0.0,
        "factors": [
          {
            "key": "active",
            "label": "活跃流量",
            "before": 1200,
            "after": 1200,
            "log_change": 0.0,
            "share": -0.0
          },
          {
            "key": "quote_rate",
            "label": "报价率",
            "before": 0.441667,
            "after": 0.420833,
            "log_change": -0.04832,
            "share": 1.886626
          },
          {
            "key": "apply_rate",
            "label": "投保率",
            "before": 0.401887,
            "after": 0.431683,
            "log_change": 0.071521,
            "share": -2.792495
          },
          {
            "key": "paid_rate",
            "label": "支付率",
            "before": 0.525822,
            "after": 0.504587,
            "log_change": -0.041222,
            "share": 1.609489
          },
          {
            "key": "issue_rate",
            "label": "出单率",
            "before": 0.589286,
            "after": 0.581818,
            "log_change": -0.012754,
            "share": 0.497972
          },
          {
            "key": "avg_premium",
            "label": "件均保费",
            "before": 952.2,
            "after": 957.13,
            "log_change": 0.005164,
            "share": -0.201625
          }
        ]
      },
      "causal_readiness": {
        "outcome": "DATA_INSUFFICIENT",
        "estimand": null,
        "observation_unit": "user_id",
        "attribution_window": "7d",
        "identification_strategy": "not identified",
        "assumptions": [
          "observational co-movement only"
        ],
        "diagnostics": {
          "sample_size": 1200,
          "group_counts": {
            "0": 858,
            "1": 342
          },
          "contract_missing_fields": [],
          "missing_evidence": [
            "activity_config",
            "assignment_method",
            "assignment_provenance",
            "assignment_verified",
            "closed_experiment_window",
            "complete_outcome_observation",
            "control_group",
            "experiment_id",
            "treatment_group"
          ],
          "design_checks": {
            "randomized_assignment": false,
            "assignment_verified": false,
            "trusted_assignment_provenance": false,
            "both_arms_present": true,
            "randomization_unit_matches": false
          },
          "power": {
            "method": "two-arm binary normal approximation",
            "alpha": 0.05,
            "target_power": 0.8,
            "minimum_detectable_effect": 0.05,
            "baseline_rate": 0.039627,
            "required_per_arm": 239,
            "actual_min_arm": 342,
            "passed": true
          },
          "governance_checks": {
            "approval_required": true,
            "guardrails_defined": true,
            "stop_rule_defined": true,
            "production_auto_action_disabled": true
          }
        },
        "gates": [
          {
            "name": "semantic",
            "passed": true,
            "reason_code": "SEMANTIC_DEFINED"
          },
          {
            "name": "data",
            "passed": false,
            "reason_code": "DATA_INSUFFICIENT"
          },
          {
            "name": "design",
            "passed": false,
            "reason_code": "CAUSAL_DESIGN_NOT_VERIFIED"
          },
          {
            "name": "statistics",
            "passed": false,
            "reason_code": "POWER_NOT_ESTABLISHED"
          },
          {
            "name": "governance",
            "passed": true,
            "reason_code": "GOVERNANCE_READY"
          }
        ],
        "evidence_level": "L1/L2",
        "reason_codes": [
          "DATA_INSUFFICIENT",
          "CAUSAL_DESIGN_NOT_VERIFIED",
          "POWER_NOT_ESTABLISHED"
        ],
        "allowed_claim_type": "descriptive_only"
      },
      "claim": {
        "claim_id": "claim-001",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "allowed_verbs": [
          "当前缺少",
          "需要补充"
        ],
        "prohibited_actions": [
          "声称导致",
          "自动触达个人",
          "直接上线配置"
        ],
        "uncertainty": "required evidence is missing",
        "statement": "当前证据不足，必须补齐实验配置、观察窗口或结果数据后才能评估因果效应。"
      },
      "sample": [
        {
          "user_id": "u0000",
          "active": 1,
          "season": 0.0,
          "channel": "owned",
          "channel_quality": 0.0816,
          "user_quality": 0.7129,
          "product_mix": 0.3058,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 0,
          "applied": 0,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0001",
          "active": 1,
          "season": 0.0,
          "channel": "owned",
          "channel_quality": -0.9559,
          "user_quality": 0.1043,
          "product_mix": 0.4253,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 0,
          "applied": 0,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0002",
          "active": 1,
          "season": 0.08,
          "channel": "owned",
          "channel_quality": 0.3187,
          "user_quality": -0.281,
          "product_mix": 0.4893,
          "treatment": 0,
          "assignment": "observational-confounded",
          "quoted": 1,
          "applied": 1,
          "paid": 1,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        }
      ],
      "summary": {
        "final_state": "CLOSED",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "causal_outcome": "DATA_INSUFFICIENT"
      },
      "evidence_pack_path": "runtime_data/evidence/T2-case-B.json",
      "evidence_pack_relative_path": "evidence/T2-case-B.json"
    },
    "C": {
      "task_id": "T2-case-C",
      "trace_id": "trace_acece15dafd2",
      "domain": "insurance-growth-attribution",
      "input_payload": {
        "case": "C",
        "question": "DAU rose while premium declined; explain what is known and what should be tested."
      },
      "state": "CLOSED",
      "state_version": 11,
      "artifacts": [
        {
          "artifact_id": "art_57b67cad9525",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "AnalysisIntent",
          "schema_version": "1.0",
          "producer": "intent",
          "payload": {
            "question": "DAU rose while premium declined; explain what is known and what should be tested.",
            "target": "premium growth and conversion",
            "unit": "user_id"
          },
          "evidence_refs": [
            "ev_37add46b35c0"
          ],
          "created_at": "2026-08-01T07:36:16.359331+00:00"
        },
        {
          "artifact_id": "art_45d61c6c0b28",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "MetricContract",
          "schema_version": "1.0",
          "producer": "metric_contract",
          "payload": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "evidence_refs": [
            "ev_37add46b35c0"
          ],
          "created_at": "2026-08-01T07:36:16.360304+00:00"
        },
        {
          "artifact_id": "art_28329bc5acaa",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "DataQualityReport",
          "schema_version": "1.0",
          "producer": "data_acquisition",
          "payload": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": true,
            "outcome_complete": true,
            "missing_fields": []
          },
          "evidence_refs": [
            "ev_cb0591802072"
          ],
          "created_at": "2026-08-01T07:36:16.361416+00:00"
        },
        {
          "artifact_id": "art_0e5ed36b8fcb",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "FeatureSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 493,
              "applied": 212,
              "paid": 118,
              "issued": 66,
              "net_premium": 61470.68,
              "quote_rate": 0.410833,
              "apply_rate": 0.43002,
              "paid_rate": 0.556604,
              "issue_rate": 0.559322,
              "issued_user_rate": 0.055,
              "avg_premium": 931.37
            },
            "segments": {
              "channel_distribution": {
                "new": 348,
                "owned": 852
              },
              "assignment_distribution": {
                "randomized": 1200
              },
              "average_product_mix": 0.409175
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 590,
                "1": 610
              },
              "group_outcomes": {
                "0": {
                  "count": 590.0,
                  "issued": 0.033898,
                  "net_premium": 32.033322
                },
                "1": {
                  "count": 610.0,
                  "issued": 0.07541,
                  "net_premium": 69.788557
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": true,
              "outcome_complete": true
            }
          },
          "evidence_refs": [
            "ev_cb0591802072",
            "ev_963560b4618f"
          ],
          "created_at": "2026-08-01T07:36:16.361512+00:00"
        },
        {
          "artifact_id": "art_b8c1f8b42bc0",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "AttributionCandidateSet",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "metrics": {
              "active": 1200,
              "quoted": 493,
              "applied": 212,
              "paid": 118,
              "issued": 66,
              "net_premium": 61470.68,
              "quote_rate": 0.410833,
              "apply_rate": 0.43002,
              "paid_rate": 0.556604,
              "issue_rate": 0.559322,
              "issued_user_rate": 0.055,
              "avg_premium": 931.37
            },
            "features": {
              "channel_distribution": {
                "new": 348,
                "owned": 852
              },
              "assignment_distribution": {
                "randomized": 1200
              },
              "average_product_mix": 0.409175
            },
            "decomposition": {
              "method": "fixed-order log-chain decomposition",
              "baseline_premium": 51502.87,
              "current_premium": 61470.68,
              "total_log_change": 0.176915,
              "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
              "unexplained_residual": 0.0,
              "factors": [
                {
                  "key": "active",
                  "label": "活跃流量",
                  "before": 1200,
                  "after": 1200,
                  "log_change": 0.0,
                  "share": 0.0
                },
                {
                  "key": "quote_rate",
                  "label": "报价率",
                  "before": 0.395833,
                  "after": 0.410833,
                  "log_change": 0.037194,
                  "share": 0.210237
                },
                {
                  "key": "apply_rate",
                  "label": "投保率",
                  "before": 0.418947,
                  "after": 0.43002,
                  "log_change": 0.026087,
                  "share": 0.147455
                },
                {
                  "key": "paid_rate",
                  "label": "支付率",
                  "before": 0.497487,
                  "after": 0.556604,
                  "log_change": 0.112285,
                  "share": 0.634684
                },
                {
                  "key": "issue_rate",
                  "label": "出单率",
                  "before": 0.555556,
                  "after": 0.559322,
                  "log_change": 0.006756,
                  "share": 0.038188
                },
                {
                  "key": "avg_premium",
                  "label": "件均保费",
                  "before": 936.42,
                  "after": 931.37,
                  "log_change": -0.005407,
                  "share": -0.030563
                }
              ]
            },
            "interpretation": "structural contribution only"
          },
          "evidence_refs": [
            "ev_963560b4618f",
            "ev_e42111980489"
          ],
          "created_at": "2026-08-01T07:36:16.363091+00:00"
        },
        {
          "artifact_id": "art_096b93cc0a0b",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "EvidenceReport",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "outcome": "CAUSAL_READY",
            "estimand": "ITT on issued and net_premium",
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "randomized",
            "assumptions": [
              "stable metric contract",
              "no cross-unit interference",
              "complete outcome window"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 590,
                "1": 610
              },
              "contract_missing_fields": [],
              "missing_evidence": [],
              "design_checks": {
                "randomized_assignment": true,
                "assignment_verified": true,
                "trusted_assignment_provenance": true,
                "both_arms_present": true,
                "randomization_unit_matches": true
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.033898,
                "required_per_arm": 206,
                "actual_min_arm": 590,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": true,
                "reason_code": "DATA_COMPLETE"
              },
              {
                "name": "design",
                "passed": true,
                "reason_code": "RANDOM_ASSIGNMENT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": true,
                "reason_code": "POWER_SCREEN_PASS"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L3",
            "reason_codes": [],
            "allowed_claim_type": "causal_effect"
          },
          "evidence_refs": [
            "ev_cb0591802072",
            "ev_963560b4618f",
            "ev_fdd23e7d7855"
          ],
          "created_at": "2026-08-01T07:36:16.365018+00:00"
        },
        {
          "artifact_id": "art_f9e137fe0444",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "ClaimLedger",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "claim_id": "claim-001",
            "claim_type": "causal_effect",
            "evidence_level": "L3",
            "allowed_verbs": [
              "估计",
              "在本实验中提升"
            ],
            "prohibited_actions": [
              "未经审批上线排序"
            ],
            "uncertainty": "95% CI attached",
            "statement": "经验证的随机分配满足因果门禁，可报告本实验中的 ITT 估计与置信区间。"
          },
          "evidence_refs": [
            "ev_c6e906ae4fba"
          ],
          "created_at": "2026-08-01T07:36:16.365056+00:00"
        },
        {
          "artifact_id": "art_d71d2c211b70",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "ExperimentSpec",
          "schema_version": "1.0",
          "producer": "experiment_planner",
          "payload": {
            "experiment_id": "randomized-ranking-C",
            "treatment": "new ranking",
            "unit": "user_id",
            "randomization": "randomized",
            "primary_metric": "issued",
            "guardrails": [
              "refund_rate",
              "cancel_rate",
              "privacy_policy"
            ],
            "stop_rule": "guardrail breach or final observation window",
            "approval": "required"
          },
          "evidence_refs": [
            "ev_7a24f156fa59"
          ],
          "created_at": "2026-08-01T07:36:16.365087+00:00"
        },
        {
          "artifact_id": "art_86e626522ff7",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "artifact_type": "MonitoringReport",
          "schema_version": "1.0",
          "producer": "monitor_review",
          "payload": {
            "estimator": "difference in means (ITT)",
            "confidence": 0.95,
            "issued": {
              "control_mean": 0.033898,
              "treatment_mean": 0.07541,
              "estimate": 0.041512,
              "standard_error": 0.013042,
              "ci95": [
                0.01595,
                0.067074
              ]
            },
            "net_premium": {
              "control_mean": 32.033322,
              "treatment_mean": 69.788557,
              "estimate": 37.755235,
              "standard_error": 12.171586,
              "ci95": [
                13.898926,
                61.611545
              ]
            }
          },
          "evidence_refs": [
            "ev_ecad5364d549"
          ],
          "created_at": "2026-08-01T07:36:16.377328+00:00"
        }
      ],
      "evidence": [
        {
          "evidence_id": "ev_37add46b35c0",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "metric-contract",
          "label": "versioned insurance metric contract",
          "source": "metric_contract",
          "content": {
            "metric_id": "insurance-premium-v2",
            "version": "2026-07-31",
            "identity": "user_id",
            "funnel": [
              "active",
              "quoted",
              "applied",
              "paid",
              "issued"
            ],
            "outcomes": [
              "issued",
              "net_premium"
            ],
            "treatment": "treatment",
            "premium": "net premium after refund and cancellation",
            "window": "7d",
            "owner": "growth-analytics"
          },
          "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba",
          "created_at": "2026-08-01T07:36:16.357603+00:00"
        },
        {
          "evidence_id": "ev_cb0591802072",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "data-quality",
          "label": "schema and data quality report",
          "source": "data_acquisition",
          "content": {
            "freshness": "simulated-current",
            "privacy": "aggregated-demo-only",
            "missing_row_fields": [],
            "missing_experiment_fields": [],
            "null_counts": {
              "active": 0,
              "applied": 0,
              "issued": 0,
              "net_premium": 0,
              "paid": 0,
              "quoted": 0,
              "treatment": 0,
              "user_id": 0
            },
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
            "window_closed": true,
            "outcome_complete": true,
            "missing_fields": []
          },
          "content_digest": "c444ebea24c9fa1faceba0bfcf7a014e477f556db3a92147c280a01988492dc2",
          "created_at": "2026-08-01T07:36:16.360344+00:00"
        },
        {
          "evidence_id": "ev_963560b4618f",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "feature-set",
          "label": "deterministic funnel, segment and treatment features",
          "source": "diagnostic",
          "content": {
            "schema_version": "1.0",
            "row_count": 1200,
            "observation_unit": "user_id",
            "available_fields": [
              "active",
              "applied",
              "assignment",
              "cancel",
              "channel",
              "channel_quality",
              "gross_premium",
              "issued",
              "net_premium",
              "paid",
              "product_mix",
              "quoted",
              "refund",
              "season",
              "treatment",
              "user_id",
              "user_quality"
            ],
            "funnel": {
              "active": 1200,
              "quoted": 493,
              "applied": 212,
              "paid": 118,
              "issued": 66,
              "net_premium": 61470.68,
              "quote_rate": 0.410833,
              "apply_rate": 0.43002,
              "paid_rate": 0.556604,
              "issue_rate": 0.559322,
              "issued_user_rate": 0.055,
              "avg_premium": 931.37
            },
            "segments": {
              "channel_distribution": {
                "new": 348,
                "owned": 852
              },
              "assignment_distribution": {
                "randomized": 1200
              },
              "average_product_mix": 0.409175
            },
            "treatment": {
              "column": "treatment",
              "group_counts": {
                "0": 590,
                "1": 610
              },
              "group_outcomes": {
                "0": {
                  "count": 590.0,
                  "issued": 0.033898,
                  "net_premium": 32.033322
                },
                "1": {
                  "count": 610.0,
                  "issued": 0.07541,
                  "net_premium": 69.788557
                }
              }
            },
            "data_quality": {
              "missing_row_fields": [],
              "missing_experiment_fields": [],
              "null_counts": {
                "active": 0,
                "applied": 0,
                "issued": 0,
                "net_premium": 0,
                "paid": 0,
                "quoted": 0,
                "treatment": 0,
                "user_id": 0
              },
              "duplicate_count": 0,
              "duplicate_rate": 0.0,
              "window_closed": true,
              "outcome_complete": true
            }
          },
          "content_digest": "f74aa04e1c9fb23a15fe5576c63940b62552662e8d49b3cd445d4db256c93208",
          "created_at": "2026-08-01T07:36:16.361496+00:00"
        },
        {
          "evidence_id": "ev_e42111980489",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "analysis",
          "label": "fixed-order log-chain decomposition",
          "source": "diagnostic",
          "content": {
            "method": "fixed-order log-chain decomposition",
            "baseline_premium": 51502.87,
            "current_premium": 61470.68,
            "total_log_change": 0.176915,
            "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
            "unexplained_residual": 0.0,
            "factors": [
              {
                "key": "active",
                "label": "活跃流量",
                "before": 1200,
                "after": 1200,
                "log_change": 0.0,
                "share": 0.0
              },
              {
                "key": "quote_rate",
                "label": "报价率",
                "before": 0.395833,
                "after": 0.410833,
                "log_change": 0.037194,
                "share": 0.210237
              },
              {
                "key": "apply_rate",
                "label": "投保率",
                "before": 0.418947,
                "after": 0.43002,
                "log_change": 0.026087,
                "share": 0.147455
              },
              {
                "key": "paid_rate",
                "label": "支付率",
                "before": 0.497487,
                "after": 0.556604,
                "log_change": 0.112285,
                "share": 0.634684
              },
              {
                "key": "issue_rate",
                "label": "出单率",
                "before": 0.555556,
                "after": 0.559322,
                "log_change": 0.006756,
                "share": 0.038188
              },
              {
                "key": "avg_premium",
                "label": "件均保费",
                "before": 936.42,
                "after": 931.37,
                "log_change": -0.005407,
                "share": -0.030563
              }
            ]
          },
          "content_digest": "5e06f53273f9c550da6578fc2954a96858a270ccb88234593b3fd399545d3175",
          "created_at": "2026-08-01T07:36:16.363068+00:00"
        },
        {
          "evidence_id": "ev_fdd23e7d7855",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "causal-readiness",
          "label": "metadata-derived five-layer readiness check",
          "source": "causal_evidence",
          "content": {
            "outcome": "CAUSAL_READY",
            "estimand": "ITT on issued and net_premium",
            "observation_unit": "user_id",
            "attribution_window": "7d",
            "identification_strategy": "randomized",
            "assumptions": [
              "stable metric contract",
              "no cross-unit interference",
              "complete outcome window"
            ],
            "diagnostics": {
              "sample_size": 1200,
              "group_counts": {
                "0": 590,
                "1": 610
              },
              "contract_missing_fields": [],
              "missing_evidence": [],
              "design_checks": {
                "randomized_assignment": true,
                "assignment_verified": true,
                "trusted_assignment_provenance": true,
                "both_arms_present": true,
                "randomization_unit_matches": true
              },
              "power": {
                "method": "two-arm binary normal approximation",
                "alpha": 0.05,
                "target_power": 0.8,
                "minimum_detectable_effect": 0.05,
                "baseline_rate": 0.033898,
                "required_per_arm": 206,
                "actual_min_arm": 590,
                "passed": true
              },
              "governance_checks": {
                "approval_required": true,
                "guardrails_defined": true,
                "stop_rule_defined": true,
                "production_auto_action_disabled": true
              }
            },
            "gates": [
              {
                "name": "semantic",
                "passed": true,
                "reason_code": "SEMANTIC_DEFINED"
              },
              {
                "name": "data",
                "passed": true,
                "reason_code": "DATA_COMPLETE"
              },
              {
                "name": "design",
                "passed": true,
                "reason_code": "RANDOM_ASSIGNMENT_VERIFIED"
              },
              {
                "name": "statistics",
                "passed": true,
                "reason_code": "POWER_SCREEN_PASS"
              },
              {
                "name": "governance",
                "passed": true,
                "reason_code": "GOVERNANCE_READY"
              }
            ],
            "evidence_level": "L3",
            "reason_codes": [],
            "allowed_claim_type": "causal_effect"
          },
          "content_digest": "46e30e09fea921648b638b12744ccfe9b463f00316295b3b4bf3a282f6675599",
          "created_at": "2026-08-01T07:36:16.365000+00:00"
        },
        {
          "evidence_id": "ev_c6e906ae4fba",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "claim-ledger",
          "label": "structured claim and prohibited actions",
          "source": "causal_evidence",
          "content": {
            "claim_id": "claim-001",
            "claim_type": "causal_effect",
            "evidence_level": "L3",
            "allowed_verbs": [
              "估计",
              "在本实验中提升"
            ],
            "prohibited_actions": [
              "未经审批上线排序"
            ],
            "uncertainty": "95% CI attached",
            "statement": "经验证的随机分配满足因果门禁，可报告本实验中的 ITT 估计与置信区间。"
          },
          "content_digest": "a0b2c0340e2c102a6307ecde661ee6f6217df17a2d05c677befd081ebe060dc8",
          "created_at": "2026-08-01T07:36:16.365043+00:00"
        },
        {
          "evidence_id": "ev_7a24f156fa59",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "experiment",
          "label": "bounded experiment draft",
          "source": "experiment_planner",
          "content": {
            "experiment_id": "randomized-ranking-C",
            "treatment": "new ranking",
            "unit": "user_id",
            "randomization": "randomized",
            "primary_metric": "issued",
            "guardrails": [
              "refund_rate",
              "cancel_rate",
              "privacy_policy"
            ],
            "stop_rule": "guardrail breach or final observation window",
            "approval": "required"
          },
          "content_digest": "96f3d4f710cdd1954aaea6a7a7c2e86cfd4afbb495bc529a26b76cea033ebd27",
          "created_at": "2026-08-01T07:36:16.365075+00:00"
        },
        {
          "evidence_id": "ev_ecad5364d549",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "kind": "monitoring",
          "label": "ITT estimate and confidence intervals",
          "source": "monitor_review",
          "content": {
            "estimator": "difference in means (ITT)",
            "confidence": 0.95,
            "issued": {
              "control_mean": 0.033898,
              "treatment_mean": 0.07541,
              "estimate": 0.041512,
              "standard_error": 0.013042,
              "ci95": [
                0.01595,
                0.067074
              ]
            },
            "net_premium": {
              "control_mean": 32.033322,
              "treatment_mean": 69.788557,
              "estimate": 37.755235,
              "standard_error": 12.171586,
              "ci95": [
                13.898926,
                61.611545
              ]
            }
          },
          "content_digest": "03805c21171378a379b05516d9ab97c7f60ed3e3760e4a8e8d38cd7465858f1b",
          "created_at": "2026-08-01T07:36:16.377309+00:00"
        }
      ],
      "approvals": [
        {
          "approval_id": "approval_4fed3d12d344",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "requested_by": "experiment_planner",
          "scope": {
            "experiment_id": "randomized-ranking-C",
            "scope": "synthetic dataset only"
          },
          "scope_digest": "ce60f74da01f89dbdadf236dcef88e6e17419b975a1711d54544d04cc9518f34",
          "requested_state": "COMPLIANCE_REVIEWED",
          "requested_state_version": 7,
          "expected_state": null,
          "status": "APPROVED",
          "created_at": "2026-08-01T07:36:16.371647+00:00",
          "reviewer": "human-reviewer",
          "note": "synthetic demo only",
          "decision_evidence": {
            "provider": "local-conformance",
            "reviewer_identity": "human-reviewer",
            "scope_digest": "ce60f74da01f89dbdadf236dcef88e6e17419b975a1711d54544d04cc9518f34",
            "event_id": "approval_evt_0ee6981b2652"
          },
          "decided_at": "2026-08-01T07:36:16.374014+00:00"
        }
      ],
      "trace": [
        {
          "event_id": "evt_380ed7eca19f",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "TASK_CREATED",
          "actor": "control-plane",
          "payload": {
            "domain": "insurance-growth-attribution",
            "input_digest": "f98e0b8c39caf8a668b53f74ce084ffa1178cc56bf5bf5f2d75e0784278347fc"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.331014+00:00"
        },
        {
          "event_id": "evt_49df0b4aaa11",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "metric_contract",
          "payload": {
            "evidence_id": "ev_37add46b35c0",
            "kind": "metric-contract",
            "label": "versioned insurance metric contract",
            "content_digest": "f47f20217866aec0ea4115eed50075569a128d5af3c49d1745ad46ca3d817cba"
          },
          "state_version": 0,
          "created_at": "2026-08-01T07:36:16.357618+00:00"
        },
        {
          "event_id": "evt_cd3397ae82b4",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "intent",
          "payload": {
            "from": "RECEIVED",
            "to": "INTENT_PARSED",
            "reason": "business question normalized",
            "metadata": {
              "evidence_ref": "ev_37add46b35c0"
            }
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.357631+00:00"
        },
        {
          "event_id": "evt_850f1af11ed7",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "intent",
          "payload": {
            "artifact_id": "art_57b67cad9525",
            "artifact_type": "AnalysisIntent",
            "evidence_refs": [
              "ev_37add46b35c0"
            ]
          },
          "state_version": 1,
          "created_at": "2026-08-01T07:36:16.359366+00:00"
        },
        {
          "event_id": "evt_a97a8a006a2e",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "metric_contract",
          "payload": {
            "from": "INTENT_PARSED",
            "to": "METRIC_CONFIRMED",
            "reason": "metric version accepted",
            "metadata": {}
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.359381+00:00"
        },
        {
          "event_id": "evt_82e9d9e9014b",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "metric_contract",
          "payload": {
            "artifact_id": "art_45d61c6c0b28",
            "artifact_type": "MetricContract",
            "evidence_refs": [
              "ev_37add46b35c0"
            ]
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.360313+00:00"
        },
        {
          "event_id": "evt_df7e34941ed5",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "data_acquisition",
          "payload": {
            "evidence_id": "ev_cb0591802072",
            "kind": "data-quality",
            "label": "schema and data quality report",
            "content_digest": "c444ebea24c9fa1faceba0bfcf7a014e477f556db3a92147c280a01988492dc2"
          },
          "state_version": 2,
          "created_at": "2026-08-01T07:36:16.360352+00:00"
        },
        {
          "event_id": "evt_388692374af1",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "data_acquisition",
          "payload": {
            "from": "METRIC_CONFIRMED",
            "to": "DATA_VALIDATED",
            "reason": "read-only dataset passed schema checks",
            "metadata": {
              "evidence_ref": "ev_cb0591802072"
            }
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.360362+00:00"
        },
        {
          "event_id": "evt_2c4fb12f5878",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "data_acquisition",
          "payload": {
            "artifact_id": "art_28329bc5acaa",
            "artifact_type": "DataQualityReport",
            "evidence_refs": [
              "ev_cb0591802072"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.361428+00:00"
        },
        {
          "event_id": "evt_d5762faee436",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_963560b4618f",
            "kind": "feature-set",
            "label": "deterministic funnel, segment and treatment features",
            "content_digest": "f74aa04e1c9fb23a15fe5576c63940b62552662e8d49b3cd445d4db256c93208"
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.361505+00:00"
        },
        {
          "event_id": "evt_c760cea5025b",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_0e5ed36b8fcb",
            "artifact_type": "FeatureSet",
            "evidence_refs": [
              "ev_cb0591802072",
              "ev_963560b4618f"
            ]
          },
          "state_version": 3,
          "created_at": "2026-08-01T07:36:16.361518+00:00"
        },
        {
          "event_id": "evt_c00d5bdf01b1",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "diagnostic",
          "payload": {
            "from": "DATA_VALIDATED",
            "to": "DIAGNOSING",
            "reason": "funnel and product structure decomposition is available",
            "metadata": {}
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.361528+00:00"
        },
        {
          "event_id": "evt_06eea785299b",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "diagnostic",
          "payload": {
            "evidence_id": "ev_e42111980489",
            "kind": "analysis",
            "label": "fixed-order log-chain decomposition",
            "content_digest": "5e06f53273f9c550da6578fc2954a96858a270ccb88234593b3fd399545d3175"
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.363083+00:00"
        },
        {
          "event_id": "evt_10fe47ccced1",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "diagnostic",
          "payload": {
            "artifact_id": "art_b8c1f8b42bc0",
            "artifact_type": "AttributionCandidateSet",
            "evidence_refs": [
              "ev_963560b4618f",
              "ev_e42111980489"
            ]
          },
          "state_version": 4,
          "created_at": "2026-08-01T07:36:16.363097+00:00"
        },
        {
          "event_id": "evt_5f5f965a2bfc",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "DIAGNOSING",
            "to": "EVIDENCE_GRADED",
            "reason": "candidate causes are separated from causal claims",
            "metadata": {}
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.363107+00:00"
        },
        {
          "event_id": "evt_e6fc19ca70c0",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_fdd23e7d7855",
            "kind": "causal-readiness",
            "label": "metadata-derived five-layer readiness check",
            "content_digest": "46e30e09fea921648b638b12744ccfe9b463f00316295b3b4bf3a282f6675599"
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365011+00:00"
        },
        {
          "event_id": "evt_5b5a8839de81",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_096b93cc0a0b",
            "artifact_type": "EvidenceReport",
            "evidence_refs": [
              "ev_cb0591802072",
              "ev_963560b4618f",
              "ev_fdd23e7d7855"
            ]
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365025+00:00"
        },
        {
          "event_id": "evt_1e624cb853a3",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "causal_evidence",
          "payload": {
            "evidence_id": "ev_c6e906ae4fba",
            "kind": "claim-ledger",
            "label": "structured claim and prohibited actions",
            "content_digest": "a0b2c0340e2c102a6307ecde661ee6f6217df17a2d05c677befd081ebe060dc8"
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365050+00:00"
        },
        {
          "event_id": "evt_6597441bdfc5",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "causal_evidence",
          "payload": {
            "artifact_id": "art_f9e137fe0444",
            "artifact_type": "ClaimLedger",
            "evidence_refs": [
              "ev_c6e906ae4fba"
            ]
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365062+00:00"
        },
        {
          "event_id": "evt_1c3c75c20c2e",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "experiment_planner",
          "payload": {
            "evidence_id": "ev_7a24f156fa59",
            "kind": "experiment",
            "label": "bounded experiment draft",
            "content_digest": "96f3d4f710cdd1954aaea6a7a7c2e86cfd4afbb495bc529a26b76cea033ebd27"
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365081+00:00"
        },
        {
          "event_id": "evt_a8d41cec3bf9",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "experiment_planner",
          "payload": {
            "artifact_id": "art_d71d2c211b70",
            "artifact_type": "ExperimentSpec",
            "evidence_refs": [
              "ev_7a24f156fa59"
            ]
          },
          "state_version": 5,
          "created_at": "2026-08-01T07:36:16.365092+00:00"
        },
        {
          "event_id": "evt_e01809271cfb",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "experiment_planner",
          "payload": {
            "from": "EVIDENCE_GRADED",
            "to": "ACTION_DRAFTED",
            "reason": "causal-ready evidence permits an experiment draft",
            "metadata": {}
          },
          "state_version": 6,
          "created_at": "2026-08-01T07:36:16.365102+00:00"
        },
        {
          "event_id": "evt_16261dc45905",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "causal_evidence",
          "payload": {
            "from": "ACTION_DRAFTED",
            "to": "COMPLIANCE_REVIEWED",
            "reason": "claim and privacy guardrails pass",
            "metadata": {}
          },
          "state_version": 7,
          "created_at": "2026-08-01T07:36:16.367427+00:00"
        },
        {
          "event_id": "evt_1976b8c0225f",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "APPROVAL_REQUESTED",
          "actor": "experiment_planner",
          "payload": {
            "approval_id": "approval_4fed3d12d344",
            "scope": {
              "experiment_id": "randomized-ranking-C",
              "scope": "synthetic dataset only"
            },
            "scope_digest": "ce60f74da01f89dbdadf236dcef88e6e17419b975a1711d54544d04cc9518f34",
            "expected_state": null
          },
          "state_version": 7,
          "created_at": "2026-08-01T07:36:16.371676+00:00"
        },
        {
          "event_id": "evt_3dcf901b5a19",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "experiment_planner",
          "payload": {
            "from": "COMPLIANCE_REVIEWED",
            "to": "AWAITING_APPROVAL",
            "reason": "experiment requires explicit human approval",
            "metadata": {
              "approval_id": "approval_4fed3d12d344"
            }
          },
          "state_version": 8,
          "created_at": "2026-08-01T07:36:16.371692+00:00"
        },
        {
          "event_id": "evt_00229da2761e",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "APPROVAL_DECIDED",
          "actor": "human-reviewer",
          "payload": {
            "approval_id": "approval_4fed3d12d344",
            "decision": "APPROVED",
            "note": "synthetic demo only",
            "scope_digest": "ce60f74da01f89dbdadf236dcef88e6e17419b975a1711d54544d04cc9518f34",
            "decision_evidence": {
              "provider": "local-conformance",
              "reviewer_identity": "human-reviewer",
              "scope_digest": "ce60f74da01f89dbdadf236dcef88e6e17419b975a1711d54544d04cc9518f34",
              "event_id": "approval_evt_0ee6981b2652"
            }
          },
          "state_version": 8,
          "created_at": "2026-08-01T07:36:16.374026+00:00"
        },
        {
          "event_id": "evt_aec2a5c69a6a",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "AWAITING_APPROVAL",
            "to": "MONITORING",
            "reason": "approved experiment enters monitoring",
            "metadata": {}
          },
          "state_version": 9,
          "created_at": "2026-08-01T07:36:16.374037+00:00"
        },
        {
          "event_id": "evt_da1b29cfd89c",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "EVIDENCE_RECORDED",
          "actor": "monitor_review",
          "payload": {
            "evidence_id": "ev_ecad5364d549",
            "kind": "monitoring",
            "label": "ITT estimate and confidence intervals",
            "content_digest": "03805c21171378a379b05516d9ab97c7f60ed3e3760e4a8e8d38cd7465858f1b"
          },
          "state_version": 9,
          "created_at": "2026-08-01T07:36:16.377321+00:00"
        },
        {
          "event_id": "evt_584bc70ec0ba",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "ARTIFACT_PUBLISHED",
          "actor": "monitor_review",
          "payload": {
            "artifact_id": "art_86e626522ff7",
            "artifact_type": "MonitoringReport",
            "evidence_refs": [
              "ev_ecad5364d549"
            ]
          },
          "state_version": 9,
          "created_at": "2026-08-01T07:36:16.377335+00:00"
        },
        {
          "event_id": "evt_d090fd9e3c4d",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "MONITORING",
            "to": "REVIEWED",
            "reason": "monitoring report completed",
            "metadata": {}
          },
          "state_version": 10,
          "created_at": "2026-08-01T07:36:16.377393+00:00"
        },
        {
          "event_id": "evt_255b7b643031",
          "task_id": "T2-case-C",
          "trace_id": "trace_acece15dafd2",
          "event_type": "STATE_TRANSITION",
          "actor": "monitor_review",
          "payload": {
            "from": "REVIEWED",
            "to": "CLOSED",
            "reason": "evidence pack finalized",
            "metadata": {}
          },
          "state_version": 11,
          "created_at": "2026-08-01T07:36:16.379822+00:00"
        }
      ],
      "topologies": [
        {
          "team_id": "insurance-growth-team",
          "control_plane": "AgentTeamsControlPlane",
          "nodes": [
            "intent",
            "metric_contract",
            "data_acquisition",
            "diagnostic",
            "causal_evidence",
            "experiment_planner",
            "monitor_review"
          ],
          "edges": [
            {
              "from": "intent",
              "to": "metric_contract",
              "mode": "sequential"
            },
            {
              "from": "metric_contract",
              "to": "data_acquisition",
              "mode": "contract-gated"
            },
            {
              "from": "data_acquisition",
              "to": "diagnostic",
              "mode": "read-only"
            },
            {
              "from": "diagnostic",
              "to": "causal_evidence",
              "mode": "fan-in",
              "input": "funnel+mix+segment artifacts"
            },
            {
              "from": "causal_evidence",
              "to": "experiment_planner",
              "mode": "evidence-gated"
            },
            {
              "from": "experiment_planner",
              "to": "monitor_review",
              "mode": "approval-gated"
            }
          ],
          "execution_semantics": {
            "fan_out": [
              "diagnostic -> funnel, product_mix, segment, event_alignment skills"
            ],
            "fan_in": "causal_evidence consumes typed diagnostic artifacts",
            "conflict_policy": "ClaimPolicyGuard is deterministic and can block model output"
          }
        }
      ],
      "track": "track2",
      "case": "C",
      "agents": [
        "intent",
        "metric_contract",
        "data_acquisition",
        "diagnostic",
        "causal_evidence",
        "experiment_planner",
        "monitor_review"
      ],
      "skills": [
        "MetricContractResolver",
        "SchemaProfiler",
        "DataQualityGate",
        "ReadOnlyQueryPlanner",
        "FunnelDecomposer",
        "ProductMixDecomposer",
        "SegmentProfiler",
        "EventAligner",
        "CausalReadinessCheck",
        "ExperimentPlanner",
        "ExperimentMonitor",
        "ClaimPolicyGuard",
        "WeeklyBriefComposer"
      ],
      "metric_contract": {
        "metric_id": "insurance-premium-v2",
        "version": "2026-07-31",
        "identity": "user_id",
        "funnel": [
          "active",
          "quoted",
          "applied",
          "paid",
          "issued"
        ],
        "outcomes": [
          "issued",
          "net_premium"
        ],
        "treatment": "treatment",
        "premium": "net premium after refund and cancellation",
        "window": "7d",
        "owner": "growth-analytics"
      },
      "experiment_metadata": {
        "treatment_column": "treatment",
        "window_closed": true,
        "outcome_complete": true,
        "minimum_detectable_effect": 0.05,
        "alpha": 0.05,
        "target_power": 0.8,
        "approval_required": true,
        "guardrails": [
          "refund_rate",
          "cancel_rate",
          "privacy_policy"
        ],
        "stop_rule": "guardrail breach or final observation window",
        "production_auto_action": false,
        "experiment_id": "randomized-ranking-C",
        "activity_config": "ranking-v2-randomized",
        "assignment_method": "randomized",
        "assignment_provenance": "experiment_platform",
        "assignment_verified": true,
        "randomization_unit": "user_id",
        "control_group": 0,
        "treatment_group": 1
      },
      "feature_set": {
        "schema_version": "1.0",
        "row_count": 1200,
        "observation_unit": "user_id",
        "available_fields": [
          "active",
          "applied",
          "assignment",
          "cancel",
          "channel",
          "channel_quality",
          "gross_premium",
          "issued",
          "net_premium",
          "paid",
          "product_mix",
          "quoted",
          "refund",
          "season",
          "treatment",
          "user_id",
          "user_quality"
        ],
        "funnel": {
          "active": 1200,
          "quoted": 493,
          "applied": 212,
          "paid": 118,
          "issued": 66,
          "net_premium": 61470.68,
          "quote_rate": 0.410833,
          "apply_rate": 0.43002,
          "paid_rate": 0.556604,
          "issue_rate": 0.559322,
          "issued_user_rate": 0.055,
          "avg_premium": 931.37
        },
        "segments": {
          "channel_distribution": {
            "new": 348,
            "owned": 852
          },
          "assignment_distribution": {
            "randomized": 1200
          },
          "average_product_mix": 0.409175
        },
        "treatment": {
          "column": "treatment",
          "group_counts": {
            "0": 590,
            "1": 610
          },
          "group_outcomes": {
            "0": {
              "count": 590.0,
              "issued": 0.033898,
              "net_premium": 32.033322
            },
            "1": {
              "count": 610.0,
              "issued": 0.07541,
              "net_premium": 69.788557
            }
          }
        },
        "data_quality": {
          "missing_row_fields": [],
          "missing_experiment_fields": [],
          "null_counts": {
            "active": 0,
            "applied": 0,
            "issued": 0,
            "net_premium": 0,
            "paid": 0,
            "quoted": 0,
            "treatment": 0,
            "user_id": 0
          },
          "duplicate_count": 0,
          "duplicate_rate": 0.0,
          "window_closed": true,
          "outcome_complete": true
        }
      },
      "metrics": {
        "baseline": {
          "active": 1200,
          "quoted": 475,
          "applied": 199,
          "paid": 99,
          "issued": 55,
          "net_premium": 51502.87,
          "quote_rate": 0.395833,
          "apply_rate": 0.418947,
          "paid_rate": 0.497487,
          "issue_rate": 0.555556,
          "issued_user_rate": 0.045833,
          "avg_premium": 936.42
        },
        "current": {
          "active": 1200,
          "quoted": 493,
          "applied": 212,
          "paid": 118,
          "issued": 66,
          "net_premium": 61470.68,
          "quote_rate": 0.410833,
          "apply_rate": 0.43002,
          "paid_rate": 0.556604,
          "issue_rate": 0.559322,
          "issued_user_rate": 0.055,
          "avg_premium": 931.37
        }
      },
      "decomposition": {
        "method": "fixed-order log-chain decomposition",
        "baseline_premium": 51502.87,
        "current_premium": 61470.68,
        "total_log_change": 0.176915,
        "interaction_policy": "multiplicative interaction is represented in log scale; no causal claim",
        "unexplained_residual": 0.0,
        "factors": [
          {
            "key": "active",
            "label": "活跃流量",
            "before": 1200,
            "after": 1200,
            "log_change": 0.0,
            "share": 0.0
          },
          {
            "key": "quote_rate",
            "label": "报价率",
            "before": 0.395833,
            "after": 0.410833,
            "log_change": 0.037194,
            "share": 0.210237
          },
          {
            "key": "apply_rate",
            "label": "投保率",
            "before": 0.418947,
            "after": 0.43002,
            "log_change": 0.026087,
            "share": 0.147455
          },
          {
            "key": "paid_rate",
            "label": "支付率",
            "before": 0.497487,
            "after": 0.556604,
            "log_change": 0.112285,
            "share": 0.634684
          },
          {
            "key": "issue_rate",
            "label": "出单率",
            "before": 0.555556,
            "after": 0.559322,
            "log_change": 0.006756,
            "share": 0.038188
          },
          {
            "key": "avg_premium",
            "label": "件均保费",
            "before": 936.42,
            "after": 931.37,
            "log_change": -0.005407,
            "share": -0.030563
          }
        ]
      },
      "causal_readiness": {
        "outcome": "CAUSAL_READY",
        "estimand": "ITT on issued and net_premium",
        "observation_unit": "user_id",
        "attribution_window": "7d",
        "identification_strategy": "randomized",
        "assumptions": [
          "stable metric contract",
          "no cross-unit interference",
          "complete outcome window"
        ],
        "diagnostics": {
          "sample_size": 1200,
          "group_counts": {
            "0": 590,
            "1": 610
          },
          "contract_missing_fields": [],
          "missing_evidence": [],
          "design_checks": {
            "randomized_assignment": true,
            "assignment_verified": true,
            "trusted_assignment_provenance": true,
            "both_arms_present": true,
            "randomization_unit_matches": true
          },
          "power": {
            "method": "two-arm binary normal approximation",
            "alpha": 0.05,
            "target_power": 0.8,
            "minimum_detectable_effect": 0.05,
            "baseline_rate": 0.033898,
            "required_per_arm": 206,
            "actual_min_arm": 590,
            "passed": true
          },
          "governance_checks": {
            "approval_required": true,
            "guardrails_defined": true,
            "stop_rule_defined": true,
            "production_auto_action_disabled": true
          }
        },
        "gates": [
          {
            "name": "semantic",
            "passed": true,
            "reason_code": "SEMANTIC_DEFINED"
          },
          {
            "name": "data",
            "passed": true,
            "reason_code": "DATA_COMPLETE"
          },
          {
            "name": "design",
            "passed": true,
            "reason_code": "RANDOM_ASSIGNMENT_VERIFIED"
          },
          {
            "name": "statistics",
            "passed": true,
            "reason_code": "POWER_SCREEN_PASS"
          },
          {
            "name": "governance",
            "passed": true,
            "reason_code": "GOVERNANCE_READY"
          }
        ],
        "evidence_level": "L3",
        "reason_codes": [],
        "allowed_claim_type": "causal_effect"
      },
      "claim": {
        "claim_id": "claim-001",
        "claim_type": "causal_effect",
        "evidence_level": "L3",
        "allowed_verbs": [
          "估计",
          "在本实验中提升"
        ],
        "prohibited_actions": [
          "未经审批上线排序"
        ],
        "uncertainty": "95% CI attached",
        "statement": "经验证的随机分配满足因果门禁，可报告本实验中的 ITT 估计与置信区间。"
      },
      "sample": [
        {
          "user_id": "u0000",
          "active": 1,
          "season": -0.04,
          "channel": "owned",
          "channel_quality": -0.0922,
          "user_quality": 0.2129,
          "product_mix": 0.4984,
          "treatment": 1,
          "assignment": "randomized",
          "quoted": 1,
          "applied": 1,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0001",
          "active": 1,
          "season": -0.04,
          "channel": "owned",
          "channel_quality": -0.647,
          "user_quality": -1.2299,
          "product_mix": 0.3326,
          "treatment": 0,
          "assignment": "randomized",
          "quoted": 0,
          "applied": 0,
          "paid": 0,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        },
        {
          "user_id": "u0002",
          "active": 1,
          "season": -0.04,
          "channel": "owned",
          "channel_quality": -0.0223,
          "user_quality": -0.1351,
          "product_mix": 0.3556,
          "treatment": 1,
          "assignment": "randomized",
          "quoted": 1,
          "applied": 1,
          "paid": 1,
          "issued": 0,
          "gross_premium": 0.0,
          "refund": 0.0,
          "cancel": 0.0,
          "net_premium": 0.0
        }
      ],
      "summary": {
        "final_state": "CLOSED",
        "claim_type": "causal_effect",
        "evidence_level": "L3",
        "causal_outcome": "CAUSAL_READY"
      },
      "estimate": {
        "estimator": "difference in means (ITT)",
        "confidence": 0.95,
        "issued": {
          "control_mean": 0.033898,
          "treatment_mean": 0.07541,
          "estimate": 0.041512,
          "standard_error": 0.013042,
          "ci95": [
            0.01595,
            0.067074
          ]
        },
        "net_premium": {
          "control_mean": 32.033322,
          "treatment_mean": 69.788557,
          "estimate": 37.755235,
          "standard_error": 12.171586,
          "ci95": [
            13.898926,
            61.611545
          ]
        }
      },
      "evidence_pack_path": "runtime_data/evidence/T2-case-C.json",
      "evidence_pack_relative_path": "evidence/T2-case-C.json"
    },
    "REAL": {
      "task_id": "T2-real-uci-bank-marketing",
      "trace_id": "trace_real_94a5cb4b7d46",
      "state": "CLOSED",
      "state_version": 5,
      "real_data": true,
      "case": "REAL",
      "provider": "uci-official",
      "agents": [
        "data_acquisition",
        "diagnostic",
        "causal_evidence"
      ],
      "skills": [
        "SchemaProfiler",
        "DataQualityGate",
        "SegmentProfiler",
        "CausalReadinessCheck",
        "ClaimPolicyGuard"
      ],
      "topologies": [],
      "trace": [
        {
          "event_type": "TASK_CREATED",
          "payload": {}
        },
        {
          "event_type": "STATE_TRANSITION",
          "payload": {
            "to": "DATA_VALIDATED"
          }
        },
        {
          "event_type": "STATE_TRANSITION",
          "payload": {
            "to": "DIAGNOSING"
          }
        },
        {
          "event_type": "STATE_TRANSITION",
          "payload": {
            "to": "EVIDENCE_GRADED"
          }
        },
        {
          "event_type": "STATE_TRANSITION",
          "payload": {
            "to": "DESCRIPTIVE_ONLY"
          }
        },
        {
          "event_type": "STATE_TRANSITION",
          "payload": {
            "to": "CLOSED"
          }
        }
      ],
      "artifacts": [
        {
          "artifact_id": "art_real_01_cd2a8a2eae",
          "artifact_type": "SourceManifest",
          "schema_version": "1.0",
          "producer": "data_acquisition",
          "payload": {
            "dataset_id": "uci-bank-marketing",
            "name": "UCI Bank Marketing",
            "official_source": "https://archive.ics.uci.edu/static/public/222/data.csv",
            "official_page": "https://archive.ics.uci.edu/dataset/222/bank+marketing",
            "dataset_doi": "10.24432/C5K306",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "S. Moro, P. Rita and P. Cortez; UCI Machine Learning Repository",
            "local_path": "/Users/lege/Documents/Codex/2026-07-24/zhe/goai_control_tower/runtime_data/datasets/uci-bank-marketing/data.csv",
            "bytes": 3542816,
            "sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
            "expected_sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
            "checksum_verified": true,
            "retrieved_at": "2026-08-01T03:57:44.789690+00:00"
          },
          "evidence_refs": [
            "ev_real_01_cd2a8a2eae"
          ]
        },
        {
          "artifact_id": "art_real_02_ffb679e1a9",
          "artifact_type": "DataQualityReport",
          "schema_version": "1.0",
          "producer": "data_acquisition",
          "payload": {
            "row_count": 45211,
            "field_count": 17,
            "fields": [
              "age",
              "job",
              "marital",
              "education",
              "default",
              "balance",
              "housing",
              "loan",
              "contact",
              "day_of_week",
              "month",
              "duration",
              "campaign",
              "pdays",
              "previous",
              "poutcome",
              "y"
            ],
            "target": "y",
            "subscriptions": 5289,
            "non_subscriptions": 39922,
            "subscription_rate": 0.116985,
            "missing_cells": 52124,
            "missing_by_field": {
              "contact": 13020,
              "education": 1857,
              "job": 288,
              "poutcome": 36959
            },
            "numeric_summary": {
              "age": {
                "count": 45211,
                "min": 18.0,
                "max": 95.0,
                "mean": 40.93621
              },
              "balance": {
                "count": 45211,
                "min": -8019.0,
                "max": 102127.0,
                "mean": 1362.272058
              },
              "duration": {
                "count": 45211,
                "min": 0.0,
                "max": 4918.0,
                "mean": 258.16308
              },
              "campaign": {
                "count": 45211,
                "min": 1.0,
                "max": 63.0,
                "mean": 2.763841
              },
              "pdays": {
                "count": 45211,
                "min": -1.0,
                "max": 871.0,
                "mean": 40.197828
              },
              "previous": {
                "count": 45211,
                "min": 0.0,
                "max": 275.0,
                "mean": 0.580323
              }
            },
            "segment_subscription_rates": {
              "contact": [
                {
                  "value": "cellular",
                  "records": 29285,
                  "subscriptions": 4369,
                  "subscription_rate": 0.149189
                },
                {
                  "value": "NaN",
                  "records": 13020,
                  "subscriptions": 530,
                  "subscription_rate": 0.040707
                },
                {
                  "value": "telephone",
                  "records": 2906,
                  "subscriptions": 390,
                  "subscription_rate": 0.134205
                }
              ],
              "month": [
                {
                  "value": "may",
                  "records": 13766,
                  "subscriptions": 925,
                  "subscription_rate": 0.067195
                },
                {
                  "value": "jul",
                  "records": 6895,
                  "subscriptions": 627,
                  "subscription_rate": 0.090935
                },
                {
                  "value": "aug",
                  "records": 6247,
                  "subscriptions": 688,
                  "subscription_rate": 0.110133
                },
                {
                  "value": "jun",
                  "records": 5341,
                  "subscriptions": 546,
                  "subscription_rate": 0.102228
                },
                {
                  "value": "nov",
                  "records": 3970,
                  "subscriptions": 403,
                  "subscription_rate": 0.101511
                },
                {
                  "value": "apr",
                  "records": 2932,
                  "subscriptions": 577,
                  "subscription_rate": 0.196794
                },
                {
                  "value": "feb",
                  "records": 2649,
                  "subscriptions": 441,
                  "subscription_rate": 0.166478
                },
                {
                  "value": "jan",
                  "records": 1403,
                  "subscriptions": 142,
                  "subscription_rate": 0.101212
                },
                {
                  "value": "oct",
                  "records": 738,
                  "subscriptions": 323,
                  "subscription_rate": 0.437669
                },
                {
                  "value": "sep",
                  "records": 579,
                  "subscriptions": 269,
                  "subscription_rate": 0.464594
                },
                {
                  "value": "mar",
                  "records": 477,
                  "subscriptions": 248,
                  "subscription_rate": 0.519916
                },
                {
                  "value": "dec",
                  "records": 214,
                  "subscriptions": 100,
                  "subscription_rate": 0.46729
                }
              ],
              "job": [
                {
                  "value": "blue-collar",
                  "records": 9732,
                  "subscriptions": 708,
                  "subscription_rate": 0.07275
                },
                {
                  "value": "management",
                  "records": 9458,
                  "subscriptions": 1301,
                  "subscription_rate": 0.137556
                },
                {
                  "value": "technician",
                  "records": 7597,
                  "subscriptions": 840,
                  "subscription_rate": 0.11057
                },
                {
                  "value": "admin.",
                  "records": 5171,
                  "subscriptions": 631,
                  "subscription_rate": 0.122027
                },
                {
                  "value": "services",
                  "records": 4154,
                  "subscriptions": 369,
                  "subscription_rate": 0.08883
                },
                {
                  "value": "retired",
                  "records": 2264,
                  "subscriptions": 516,
                  "subscription_rate": 0.227915
                },
                {
                  "value": "self-employed",
                  "records": 1579,
                  "subscriptions": 187,
                  "subscription_rate": 0.118429
                },
                {
                  "value": "entrepreneur",
                  "records": 1487,
                  "subscriptions": 123,
                  "subscription_rate": 0.082717
                },
                {
                  "value": "unemployed",
                  "records": 1303,
                  "subscriptions": 202,
                  "subscription_rate": 0.155027
                },
                {
                  "value": "housemaid",
                  "records": 1240,
                  "subscriptions": 109,
                  "subscription_rate": 0.087903
                },
                {
                  "value": "student",
                  "records": 938,
                  "subscriptions": 269,
                  "subscription_rate": 0.28678
                },
                {
                  "value": "NaN",
                  "records": 288,
                  "subscriptions": 34,
                  "subscription_rate": 0.118056
                }
              ],
              "poutcome": [
                {
                  "value": "NaN",
                  "records": 36959,
                  "subscriptions": 3386,
                  "subscription_rate": 0.091615
                },
                {
                  "value": "failure",
                  "records": 4901,
                  "subscriptions": 618,
                  "subscription_rate": 0.126097
                },
                {
                  "value": "other",
                  "records": 1840,
                  "subscriptions": 307,
                  "subscription_rate": 0.166848
                },
                {
                  "value": "success",
                  "records": 1511,
                  "subscriptions": 978,
                  "subscription_rate": 0.647253
                }
              ]
            }
          },
          "evidence_refs": [
            "ev_real_02_ffb679e1a9"
          ]
        },
        {
          "artifact_id": "art_real_03_aedcddca88",
          "artifact_type": "FeaturePolicy",
          "schema_version": "1.0",
          "producer": "diagnostic",
          "payload": {
            "prediction_time": "before outbound call",
            "blocked_features": [
              {
                "field": "duration",
                "reason_code": "POST_OUTCOME_LEAKAGE",
                "reason": "Call duration is only known after the call has occurred and must not be used for pre-call targeting."
              },
              {
                "field": "y",
                "reason_code": "OUTCOME_FIELD",
                "reason": "Subscription is the target outcome."
              }
            ],
            "allowed_pre_call_features": [
              "age",
              "job",
              "marital",
              "education",
              "default",
              "balance",
              "housing",
              "loan",
              "contact",
              "day_of_week",
              "month",
              "campaign",
              "pdays",
              "previous",
              "poutcome"
            ],
            "restricted_individual_targeting_fields": [
              "age",
              "marital",
              "education",
              "job"
            ],
            "evidence_pack_policy": "aggregate-only; no row samples or individual targeting lists"
          },
          "evidence_refs": [
            "ev_real_03_aedcddca88"
          ]
        },
        {
          "artifact_id": "art_real_04_4d8a0dd70a",
          "artifact_type": "EvidenceReport",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "outcome": "DESCRIPTIVE_ONLY",
            "evidence_level": "L1/L2",
            "identification_strategy": "not identified",
            "allowed_claim_type": "descriptive_only",
            "reason_codes": [
              "NO_TREATMENT_ASSIGNMENT",
              "NO_RANDOMIZATION_PROVENANCE",
              "POST_OUTCOME_LEAKAGE_FIELD_BLOCKED"
            ],
            "gates": [
              {
                "name": "source",
                "passed": true,
                "reason_code": "OFFICIAL_SOURCE_VERIFIED"
              },
              {
                "name": "schema",
                "passed": true,
                "reason_code": "REAL_ROWS_PROFILED"
              },
              {
                "name": "leakage",
                "passed": true,
                "reason_code": "POST_OUTCOME_FIELD_EXCLUDED"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_AVAILABLE"
              }
            ]
          },
          "evidence_refs": [
            "ev_real_04_4d8a0dd70a"
          ]
        },
        {
          "artifact_id": "art_real_05_e83392f9e7",
          "artifact_type": "ClaimLedger",
          "schema_version": "1.0",
          "producer": "causal_evidence",
          "payload": {
            "claim_id": "claim-real-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "观察到",
              "历史记录显示",
              "对应"
            ],
            "prohibited_actions": [
              "声称导致",
              "使用 duration 做呼叫前决策",
              "生成个人营销名单"
            ],
            "statement": "UCI 的 45211 条真实银行营销记录中，定期存款订阅率为 11.70%。该数据没有随机处理分配，且 duration 属于结果后变量，因此只能报告历史相关性，不能声称因果。"
          },
          "evidence_refs": [
            "ev_real_05_e83392f9e7"
          ]
        }
      ],
      "evidence": [
        {
          "evidence_id": "ev_real_01_cd2a8a2eae",
          "kind": "source",
          "label": "official UCI source and checksum",
          "content": {
            "dataset_id": "uci-bank-marketing",
            "name": "UCI Bank Marketing",
            "official_source": "https://archive.ics.uci.edu/static/public/222/data.csv",
            "official_page": "https://archive.ics.uci.edu/dataset/222/bank+marketing",
            "dataset_doi": "10.24432/C5K306",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "S. Moro, P. Rita and P. Cortez; UCI Machine Learning Repository",
            "local_path": "/Users/lege/Documents/Codex/2026-07-24/zhe/goai_control_tower/runtime_data/datasets/uci-bank-marketing/data.csv",
            "bytes": 3542816,
            "sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
            "expected_sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
            "checksum_verified": true,
            "retrieved_at": "2026-08-01T03:57:44.789690+00:00"
          },
          "content_digest": "cd2a8a2eaefaabbc5c0730bfdaa22887a7a6f058fa0ffc8b2c00258339165828",
          "source": "uci-official"
        },
        {
          "evidence_id": "ev_real_02_ffb679e1a9",
          "kind": "data-quality",
          "label": "real-data schema and missingness audit",
          "content": {
            "row_count": 45211,
            "field_count": 17,
            "fields": [
              "age",
              "job",
              "marital",
              "education",
              "default",
              "balance",
              "housing",
              "loan",
              "contact",
              "day_of_week",
              "month",
              "duration",
              "campaign",
              "pdays",
              "previous",
              "poutcome",
              "y"
            ],
            "target": "y",
            "subscriptions": 5289,
            "non_subscriptions": 39922,
            "subscription_rate": 0.116985,
            "missing_cells": 52124,
            "missing_by_field": {
              "contact": 13020,
              "education": 1857,
              "job": 288,
              "poutcome": 36959
            },
            "numeric_summary": {
              "age": {
                "count": 45211,
                "min": 18.0,
                "max": 95.0,
                "mean": 40.93621
              },
              "balance": {
                "count": 45211,
                "min": -8019.0,
                "max": 102127.0,
                "mean": 1362.272058
              },
              "duration": {
                "count": 45211,
                "min": 0.0,
                "max": 4918.0,
                "mean": 258.16308
              },
              "campaign": {
                "count": 45211,
                "min": 1.0,
                "max": 63.0,
                "mean": 2.763841
              },
              "pdays": {
                "count": 45211,
                "min": -1.0,
                "max": 871.0,
                "mean": 40.197828
              },
              "previous": {
                "count": 45211,
                "min": 0.0,
                "max": 275.0,
                "mean": 0.580323
              }
            },
            "segment_subscription_rates": {
              "contact": [
                {
                  "value": "cellular",
                  "records": 29285,
                  "subscriptions": 4369,
                  "subscription_rate": 0.149189
                },
                {
                  "value": "NaN",
                  "records": 13020,
                  "subscriptions": 530,
                  "subscription_rate": 0.040707
                },
                {
                  "value": "telephone",
                  "records": 2906,
                  "subscriptions": 390,
                  "subscription_rate": 0.134205
                }
              ],
              "month": [
                {
                  "value": "may",
                  "records": 13766,
                  "subscriptions": 925,
                  "subscription_rate": 0.067195
                },
                {
                  "value": "jul",
                  "records": 6895,
                  "subscriptions": 627,
                  "subscription_rate": 0.090935
                },
                {
                  "value": "aug",
                  "records": 6247,
                  "subscriptions": 688,
                  "subscription_rate": 0.110133
                },
                {
                  "value": "jun",
                  "records": 5341,
                  "subscriptions": 546,
                  "subscription_rate": 0.102228
                },
                {
                  "value": "nov",
                  "records": 3970,
                  "subscriptions": 403,
                  "subscription_rate": 0.101511
                },
                {
                  "value": "apr",
                  "records": 2932,
                  "subscriptions": 577,
                  "subscription_rate": 0.196794
                },
                {
                  "value": "feb",
                  "records": 2649,
                  "subscriptions": 441,
                  "subscription_rate": 0.166478
                },
                {
                  "value": "jan",
                  "records": 1403,
                  "subscriptions": 142,
                  "subscription_rate": 0.101212
                },
                {
                  "value": "oct",
                  "records": 738,
                  "subscriptions": 323,
                  "subscription_rate": 0.437669
                },
                {
                  "value": "sep",
                  "records": 579,
                  "subscriptions": 269,
                  "subscription_rate": 0.464594
                },
                {
                  "value": "mar",
                  "records": 477,
                  "subscriptions": 248,
                  "subscription_rate": 0.519916
                },
                {
                  "value": "dec",
                  "records": 214,
                  "subscriptions": 100,
                  "subscription_rate": 0.46729
                }
              ],
              "job": [
                {
                  "value": "blue-collar",
                  "records": 9732,
                  "subscriptions": 708,
                  "subscription_rate": 0.07275
                },
                {
                  "value": "management",
                  "records": 9458,
                  "subscriptions": 1301,
                  "subscription_rate": 0.137556
                },
                {
                  "value": "technician",
                  "records": 7597,
                  "subscriptions": 840,
                  "subscription_rate": 0.11057
                },
                {
                  "value": "admin.",
                  "records": 5171,
                  "subscriptions": 631,
                  "subscription_rate": 0.122027
                },
                {
                  "value": "services",
                  "records": 4154,
                  "subscriptions": 369,
                  "subscription_rate": 0.08883
                },
                {
                  "value": "retired",
                  "records": 2264,
                  "subscriptions": 516,
                  "subscription_rate": 0.227915
                },
                {
                  "value": "self-employed",
                  "records": 1579,
                  "subscriptions": 187,
                  "subscription_rate": 0.118429
                },
                {
                  "value": "entrepreneur",
                  "records": 1487,
                  "subscriptions": 123,
                  "subscription_rate": 0.082717
                },
                {
                  "value": "unemployed",
                  "records": 1303,
                  "subscriptions": 202,
                  "subscription_rate": 0.155027
                },
                {
                  "value": "housemaid",
                  "records": 1240,
                  "subscriptions": 109,
                  "subscription_rate": 0.087903
                },
                {
                  "value": "student",
                  "records": 938,
                  "subscriptions": 269,
                  "subscription_rate": 0.28678
                },
                {
                  "value": "NaN",
                  "records": 288,
                  "subscriptions": 34,
                  "subscription_rate": 0.118056
                }
              ],
              "poutcome": [
                {
                  "value": "NaN",
                  "records": 36959,
                  "subscriptions": 3386,
                  "subscription_rate": 0.091615
                },
                {
                  "value": "failure",
                  "records": 4901,
                  "subscriptions": 618,
                  "subscription_rate": 0.126097
                },
                {
                  "value": "other",
                  "records": 1840,
                  "subscriptions": 307,
                  "subscription_rate": 0.166848
                },
                {
                  "value": "success",
                  "records": 1511,
                  "subscriptions": 978,
                  "subscription_rate": 0.647253
                }
              ]
            }
          },
          "content_digest": "ffb679e1a9ce3710d1bc678d9eefe905e812b0c5c76d253de246964f14781e8d",
          "source": "uci-official"
        },
        {
          "evidence_id": "ev_real_03_aedcddca88",
          "kind": "leakage",
          "label": "pre-call leakage policy",
          "content": {
            "prediction_time": "before outbound call",
            "blocked_features": [
              {
                "field": "duration",
                "reason_code": "POST_OUTCOME_LEAKAGE",
                "reason": "Call duration is only known after the call has occurred and must not be used for pre-call targeting."
              },
              {
                "field": "y",
                "reason_code": "OUTCOME_FIELD",
                "reason": "Subscription is the target outcome."
              }
            ],
            "allowed_pre_call_features": [
              "age",
              "job",
              "marital",
              "education",
              "default",
              "balance",
              "housing",
              "loan",
              "contact",
              "day_of_week",
              "month",
              "campaign",
              "pdays",
              "previous",
              "poutcome"
            ],
            "restricted_individual_targeting_fields": [
              "age",
              "marital",
              "education",
              "job"
            ],
            "evidence_pack_policy": "aggregate-only; no row samples or individual targeting lists"
          },
          "content_digest": "aedcddca88161e01b0ca9266f8285f9e62e190eb87f849e93eef7db0cae0caf9",
          "source": "uci-official"
        },
        {
          "evidence_id": "ev_real_04_4d8a0dd70a",
          "kind": "causal-readiness",
          "label": "observational causal-readiness refusal",
          "content": {
            "outcome": "DESCRIPTIVE_ONLY",
            "evidence_level": "L1/L2",
            "identification_strategy": "not identified",
            "allowed_claim_type": "descriptive_only",
            "reason_codes": [
              "NO_TREATMENT_ASSIGNMENT",
              "NO_RANDOMIZATION_PROVENANCE",
              "POST_OUTCOME_LEAKAGE_FIELD_BLOCKED"
            ],
            "gates": [
              {
                "name": "source",
                "passed": true,
                "reason_code": "OFFICIAL_SOURCE_VERIFIED"
              },
              {
                "name": "schema",
                "passed": true,
                "reason_code": "REAL_ROWS_PROFILED"
              },
              {
                "name": "leakage",
                "passed": true,
                "reason_code": "POST_OUTCOME_FIELD_EXCLUDED"
              },
              {
                "name": "design",
                "passed": false,
                "reason_code": "CAUSAL_DESIGN_NOT_AVAILABLE"
              }
            ]
          },
          "content_digest": "4d8a0dd70ab4682f87e01f43306db7b7dc967ecb6ff29e39a9f68874a13c5df6",
          "source": "uci-official"
        },
        {
          "evidence_id": "ev_real_05_e83392f9e7",
          "kind": "claim-ledger",
          "label": "real-data claim boundary",
          "content": {
            "claim_id": "claim-real-001",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "allowed_verbs": [
              "观察到",
              "历史记录显示",
              "对应"
            ],
            "prohibited_actions": [
              "声称导致",
              "使用 duration 做呼叫前决策",
              "生成个人营销名单"
            ],
            "statement": "UCI 的 45211 条真实银行营销记录中，定期存款订阅率为 11.70%。该数据没有随机处理分配，且 duration 属于结果后变量，因此只能报告历史相关性，不能声称因果。"
          },
          "content_digest": "e83392f9e745a89f85f5341daddf13112c4d50d13b09608b145d0a793e7095db",
          "source": "uci-official"
        }
      ],
      "source": {
        "dataset_id": "uci-bank-marketing",
        "name": "UCI Bank Marketing",
        "official_source": "https://archive.ics.uci.edu/static/public/222/data.csv",
        "official_page": "https://archive.ics.uci.edu/dataset/222/bank+marketing",
        "dataset_doi": "10.24432/C5K306",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "S. Moro, P. Rita and P. Cortez; UCI Machine Learning Repository",
        "local_path": "runtime_data/datasets/uci-bank-marketing/data.csv",
        "bytes": 3542816,
        "sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
        "expected_sha256": "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686",
        "checksum_verified": true,
        "retrieved_at": "2026-08-01T03:57:44.789690+00:00"
      },
      "profile": {
        "row_count": 45211,
        "field_count": 17,
        "fields": [
          "age",
          "job",
          "marital",
          "education",
          "default",
          "balance",
          "housing",
          "loan",
          "contact",
          "day_of_week",
          "month",
          "duration",
          "campaign",
          "pdays",
          "previous",
          "poutcome",
          "y"
        ],
        "target": "y",
        "subscriptions": 5289,
        "non_subscriptions": 39922,
        "subscription_rate": 0.116985,
        "missing_cells": 52124,
        "missing_by_field": {
          "contact": 13020,
          "education": 1857,
          "job": 288,
          "poutcome": 36959
        },
        "numeric_summary": {
          "age": {
            "count": 45211,
            "min": 18.0,
            "max": 95.0,
            "mean": 40.93621
          },
          "balance": {
            "count": 45211,
            "min": -8019.0,
            "max": 102127.0,
            "mean": 1362.272058
          },
          "duration": {
            "count": 45211,
            "min": 0.0,
            "max": 4918.0,
            "mean": 258.16308
          },
          "campaign": {
            "count": 45211,
            "min": 1.0,
            "max": 63.0,
            "mean": 2.763841
          },
          "pdays": {
            "count": 45211,
            "min": -1.0,
            "max": 871.0,
            "mean": 40.197828
          },
          "previous": {
            "count": 45211,
            "min": 0.0,
            "max": 275.0,
            "mean": 0.580323
          }
        },
        "segment_subscription_rates": {
          "contact": [
            {
              "value": "cellular",
              "records": 29285,
              "subscriptions": 4369,
              "subscription_rate": 0.149189
            },
            {
              "value": "NaN",
              "records": 13020,
              "subscriptions": 530,
              "subscription_rate": 0.040707
            },
            {
              "value": "telephone",
              "records": 2906,
              "subscriptions": 390,
              "subscription_rate": 0.134205
            }
          ],
          "month": [
            {
              "value": "may",
              "records": 13766,
              "subscriptions": 925,
              "subscription_rate": 0.067195
            },
            {
              "value": "jul",
              "records": 6895,
              "subscriptions": 627,
              "subscription_rate": 0.090935
            },
            {
              "value": "aug",
              "records": 6247,
              "subscriptions": 688,
              "subscription_rate": 0.110133
            },
            {
              "value": "jun",
              "records": 5341,
              "subscriptions": 546,
              "subscription_rate": 0.102228
            },
            {
              "value": "nov",
              "records": 3970,
              "subscriptions": 403,
              "subscription_rate": 0.101511
            },
            {
              "value": "apr",
              "records": 2932,
              "subscriptions": 577,
              "subscription_rate": 0.196794
            },
            {
              "value": "feb",
              "records": 2649,
              "subscriptions": 441,
              "subscription_rate": 0.166478
            },
            {
              "value": "jan",
              "records": 1403,
              "subscriptions": 142,
              "subscription_rate": 0.101212
            },
            {
              "value": "oct",
              "records": 738,
              "subscriptions": 323,
              "subscription_rate": 0.437669
            },
            {
              "value": "sep",
              "records": 579,
              "subscriptions": 269,
              "subscription_rate": 0.464594
            },
            {
              "value": "mar",
              "records": 477,
              "subscriptions": 248,
              "subscription_rate": 0.519916
            },
            {
              "value": "dec",
              "records": 214,
              "subscriptions": 100,
              "subscription_rate": 0.46729
            }
          ],
          "job": [
            {
              "value": "blue-collar",
              "records": 9732,
              "subscriptions": 708,
              "subscription_rate": 0.07275
            },
            {
              "value": "management",
              "records": 9458,
              "subscriptions": 1301,
              "subscription_rate": 0.137556
            },
            {
              "value": "technician",
              "records": 7597,
              "subscriptions": 840,
              "subscription_rate": 0.11057
            },
            {
              "value": "admin.",
              "records": 5171,
              "subscriptions": 631,
              "subscription_rate": 0.122027
            },
            {
              "value": "services",
              "records": 4154,
              "subscriptions": 369,
              "subscription_rate": 0.08883
            },
            {
              "value": "retired",
              "records": 2264,
              "subscriptions": 516,
              "subscription_rate": 0.227915
            },
            {
              "value": "self-employed",
              "records": 1579,
              "subscriptions": 187,
              "subscription_rate": 0.118429
            },
            {
              "value": "entrepreneur",
              "records": 1487,
              "subscriptions": 123,
              "subscription_rate": 0.082717
            },
            {
              "value": "unemployed",
              "records": 1303,
              "subscriptions": 202,
              "subscription_rate": 0.155027
            },
            {
              "value": "housemaid",
              "records": 1240,
              "subscriptions": 109,
              "subscription_rate": 0.087903
            },
            {
              "value": "student",
              "records": 938,
              "subscriptions": 269,
              "subscription_rate": 0.28678
            },
            {
              "value": "NaN",
              "records": 288,
              "subscriptions": 34,
              "subscription_rate": 0.118056
            }
          ],
          "poutcome": [
            {
              "value": "NaN",
              "records": 36959,
              "subscriptions": 3386,
              "subscription_rate": 0.091615
            },
            {
              "value": "failure",
              "records": 4901,
              "subscriptions": 618,
              "subscription_rate": 0.126097
            },
            {
              "value": "other",
              "records": 1840,
              "subscriptions": 307,
              "subscription_rate": 0.166848
            },
            {
              "value": "success",
              "records": 1511,
              "subscriptions": 978,
              "subscription_rate": 0.647253
            }
          ]
        }
      },
      "feature_policy": {
        "prediction_time": "before outbound call",
        "blocked_features": [
          {
            "field": "duration",
            "reason_code": "POST_OUTCOME_LEAKAGE",
            "reason": "Call duration is only known after the call has occurred and must not be used for pre-call targeting."
          },
          {
            "field": "y",
            "reason_code": "OUTCOME_FIELD",
            "reason": "Subscription is the target outcome."
          }
        ],
        "allowed_pre_call_features": [
          "age",
          "job",
          "marital",
          "education",
          "default",
          "balance",
          "housing",
          "loan",
          "contact",
          "day_of_week",
          "month",
          "campaign",
          "pdays",
          "previous",
          "poutcome"
        ],
        "restricted_individual_targeting_fields": [
          "age",
          "marital",
          "education",
          "job"
        ],
        "evidence_pack_policy": "aggregate-only; no row samples or individual targeting lists"
      },
      "causal_readiness": {
        "outcome": "DESCRIPTIVE_ONLY",
        "evidence_level": "L1/L2",
        "identification_strategy": "not identified",
        "allowed_claim_type": "descriptive_only",
        "reason_codes": [
          "NO_TREATMENT_ASSIGNMENT",
          "NO_RANDOMIZATION_PROVENANCE",
          "POST_OUTCOME_LEAKAGE_FIELD_BLOCKED"
        ],
        "gates": [
          {
            "name": "source",
            "passed": true,
            "reason_code": "OFFICIAL_SOURCE_VERIFIED"
          },
          {
            "name": "schema",
            "passed": true,
            "reason_code": "REAL_ROWS_PROFILED"
          },
          {
            "name": "leakage",
            "passed": true,
            "reason_code": "POST_OUTCOME_FIELD_EXCLUDED"
          },
          {
            "name": "design",
            "passed": false,
            "reason_code": "CAUSAL_DESIGN_NOT_AVAILABLE"
          }
        ]
      },
      "claim": {
        "claim_id": "claim-real-001",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "allowed_verbs": [
          "观察到",
          "历史记录显示",
          "对应"
        ],
        "prohibited_actions": [
          "声称导致",
          "使用 duration 做呼叫前决策",
          "生成个人营销名单"
        ],
        "statement": "UCI 的 45211 条真实银行营销记录中，定期存款订阅率为 11.70%。该数据没有随机处理分配，且 duration 属于结果后变量，因此只能报告历史相关性，不能声称因果。"
      },
      "summary": {
        "final_state": "CLOSED",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "causal_outcome": "DESCRIPTIVE_ONLY"
      },
      "evidence_pack_path": "runtime_data/evidence/T2-real-uci-bank-marketing.json",
      "evidence_pack_relative_path": "evidence/T2-real-uci-bank-marketing.json"
    }
  }
};
