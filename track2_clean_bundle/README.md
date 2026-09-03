# GOAI 方案二干净包

这是一个只保留 **Track 2** 的独立目录，便于压缩传递。
已剥离其它赛道、旧版双轨入口、`deploy/`、`packages/`、`fixtures/` 和原始 native 日志。

## 目录里有什么

- `src/goai_control_tower/`：Track 2 核心代码、配置、数据目录
- `web/static/`：Track 2 控制台和方案页
- `docs/`：Track 2 数据研究与真实数据说明
- `runtime_data/`：Track 2 证据与真实数据文件
- `samples/track2/`：示例输入输出

## 运行

```bash
PYTHONPATH=src python3 -m goai_control_tower --track2-benchmark --track2-benchmark-seeds 3
PYTHONPATH=src python3 -m goai_control_tower --track2-real-data --track2-real-data-path runtime_data/datasets/uci-bank-marketing/data.csv
python3 run_server.py 8765
```

## 真实数据格式

期望的是“行级、可追踪、带窗口与处理分配”的数据。关键字段：

- `schema_version`, `record_id`, `subject_id_hash`, `event_time`
- `window_start`, `window_end`, `channel`, `campaign_id`, `product_code`, `segment`
- `treatment_group`, `control_group`, `assignment_method`, `assignment_provenance`, `assignment_verified`
- `active`, `quoted`, `applied`, `paid`, `issued`, `gross_premium`, `refund`, `cancel`, `net_premium`
- `source_system`, `snapshot_date`, `authorization_id`, `data_owner`

对于只做描述性说明，聚合表也可以；要做因果结论，必须有可信分配和完整窗口。

## 当前进展

- 公开案例 A/B/C 已跑通
- UCI Bank Marketing 已接入并完成真实数据基线
- 隐藏基准已完成，3 seeds / 9 cases 门禁通过
- 方案页与控制台已收口为 Track 2
