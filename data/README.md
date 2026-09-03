# 真实脱敏数据

本目录是控制台和 Line B 关联发现链路使用的可直接查看数据入口。数据已经去除个人标识和业务敏感字段，保留归因所需的时间、分层、分子分母、因子快照和来源字段。

## 文件

| 文件 | 内容 | 行数/规模 |
|---|---|---:|
| `真实脱敏数据/lineB_panel.csv` | 日度处理组/对照组分层面板，含点击分子、曝光分母、rate、gap 和质量字段 | 480 行 |
| `真实脱敏数据/factor_snapshots.csv` | 内部与外部因子日度快照，供 Level、Velocity、Acceleration 三层派生 | 240 行 |
| `真实脱敏数据/change_registry.json` | 已登记内部变更及其实验读数引用 | 2 项 |
| `真实脱敏数据/external_events.json` | 外部事件和内部事件候选快照，含时间范围、范围和来源字段 | 3 项 |

## 使用关系

```text
lineB_panel.csv
  -> rate-aware 分层下钻 -> gap / residual / 异动切面
factor_snapshots.csv
  -> Level / Velocity / Acceleration -> 关联候选排序
change_registry.json + external_events.json
  -> 已验证内部解释 / 外部时间关联 -> holdout 与下一窗口验证计划
```

控制台中的 `full_review` 会展示这批数据的明细和运算轨迹；Python 输出证据位于 `outputs/lineB_scenario_report.json`、`outputs/lineB_baseline_attribution.json` 和 `outputs/lineB_association_discovery.json`。

数据模式：`competition_deidentified`。生产接入时由授权的数据适配器替换文件来源，字段契约、来源留痕和人工审批边界保持不变。
