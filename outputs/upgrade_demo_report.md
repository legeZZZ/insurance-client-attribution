# 升级 Demo 报告

- 数据模式：`competition_deidentified`（真实脱敏数据）
- 适配器：`authorized_adapter_compatible`

## 结果

- N1 外部事件映射覆盖率：`0.5`；未映射异常：`UNEXPLAINED`
- N2 本地模型规则兜底：`True`；trace 完整：`True`
- N3 灰度流量：`5%`；护栏：`BREACHED`；建议：`PAUSE_RECOMMENDED`
- 治理：无随机化拒答、外部事件不升级因果、执行需要人工审批

## Trace

```json
[
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n1",
    "event": "event_ingest",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "source_id": "authorized.deidentified-events",
    "count": 2,
    "output_digest": "sha256:2b251e97a7489fe0"
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n1",
    "event": "event_mapping",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "mapping_coverage": 0.5,
    "unmapped_policy": "UNEXPLAINED"
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n1",
    "event": "factor_rag_retrieval",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "candidate_count": 1,
    "retrieval_basis": "structured_filter+fts5+provenance"
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n2",
    "event": "local_llm_intent",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "provider": "local-open-source-adapter",
    "output_digest": "sha256:319ac5daa451da18",
    "latency_seconds": 0.000127
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n2",
    "event": "rule_fallback",
    "status": "degraded",
    "at": "2026-08-30T19:17:46+00:00",
    "reason": "local model timeout",
    "output_digest": "sha256:cbb71b09f0edd5e2"
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n3",
    "event": "experiment_created",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "experiment_id": "exp-001",
    "approval_ref": "approval-demo-001"
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n3",
    "event": "canary_started",
    "status": "ok",
    "at": "2026-08-30T19:17:46+00:00",
    "traffic_percent": 5
  },
  {
    "trace_id": "upgrade-replay-20260824-001",
    "stage": "n3",
    "event": "guardrail_evaluated",
    "status": "breached",
    "at": "2026-08-30T19:17:46+00:00",
    "decision": "PAUSE_RECOMMENDED"
  }
]
```
