# watch_skill

Governed method memory; this document does not authorize execution. Current evidence, independent validation and human release approval remain required.

```json
{
  "schema_version": "skill/2",
  "name": "watch_skill",
  "version": 1,
  "rules": [
    {
      "when": {
        "workflow": "c_line"
      },
      "action": "scan_window",
      "polarity": "reinforce",
      "evidence": [
        "sha256:32c8bbb6d691ce9a9c847c8d4d29353d6f4192c050ff47d2572dce3a6eea8fa4"
      ]
    }
  ],
  "applicability": {
    "workflow": "c_line"
  },
  "claim_ceiling": "WATCHLIST",
  "preconditions": [
    "valid_current_data",
    "scope_matches"
  ],
  "postconditions": [
    "no_causal_without_identification",
    "no_traffic_mutation"
  ],
  "source_trace_ids": [
    "sha256:7f30dbc9031bff4bae9500883fac88b7191f6a0e008bfb096ae557d5a18dc106"
  ],
  "source_claim_refs": [],
  "source_evidence_refs": [
    "sha256:32c8bbb6d691ce9a9c847c8d4d29353d6f4192c050ff47d2572dce3a6eea8fa4"
  ],
  "negative_examples": [],
  "validation_task_refs": [],
  "compatibility_check_refs": [],
  "delta": {
    "base_version": null,
    "previous_digest": null,
    "added_rules": [
      {
        "when": {
          "workflow": "c_line"
        },
        "action": "scan_window",
        "polarity": "reinforce",
        "evidence": [
          "sha256:32c8bbb6d691ce9a9c847c8d4d29353d6f4192c050ff47d2572dce3a6eea8fa4"
        ]
      }
    ]
  },
  "digest": "sha256:fbaf5b0fb2ad9ee36ddc758a5849781cb6676a0420154e128c7d9d9105bde943"
}
```
