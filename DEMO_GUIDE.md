# 演示执行手册（评委现场 5 分钟版）

本手册对应交付包「可执行代码包」。统计管线本地运行；默认场景使用可复现真实脱敏数据，页面会明确标识 `HTTP 实机` 或 `本地数据回放`，生产环境可通过企业授权适配器接入。
环境要求：Python 3.9+（推荐 Python 3.12），`pip install -r requirements.txt`（仅 numpy）。

## 0. 启动（10 秒）

```bash
cd 可执行代码包
python3 run_server.py 8765
# 浏览器打开 http://127.0.0.1:8765
```

根路径直接进入「复赛现场控制台」。也可打开 `web/static/semifinal-demo.html` 查看离线界面；此时任务运行会走明确标注的离线回退。结果出现 `east / paid / 8.4 · 状态：UNEXPLAINED，未解释阶跃保留` 时，表示未知桶按规则保留，并非执行报错。

## 1. 开场：从空白任务运行 B 线（约 2 分钟）

1. 打开控制台，保留默认问题：`上个月注册量为什么下降？请检查内部变更、竞品活动和汇率，并给出下一步验证方案。`
2. 保持默认的 `全链路：自动复核 A+B+外部+N1/N2/N3`，点击 `启动全链路复核`。
3. 观察 6 个主阶段逐步完成：采集、路由、异常聚焦、因子推演、证据核验、行动交付；其中包含意图识别、分层面板、RCA、Factor RAG、关联检验、holdout、N2/N3 和 Evidence Pack 子步骤。
4. 结果区确认：`east / paid / 8.4` 是内部异常子空间；竞品活动和汇率只显示为候选或时间关联；未解释部分仍保留 `UNEXPLAINED`。悬浮三维图中的节点可查看来源、证据等级和下一步，候选因子库会把内部因子/外部因子及其验证路线展示出来；同时看到 A 线实验决策、外部映射覆盖率和 N3 护栏状态。顶部三维指挥台和结果区来自同一次 API 执行。

补充核对 Line B 的计算账本：共同外部事件在 `control` 和 `treated` 中同步出现时，已经由 `gap = treated - control` 抵消。页面或 JSON 中的外部事件只作为 `TEMPORAL_ASSOCIATION` 旁路证据，不能再次减少 `residual`；`residual_basis` 应显示为 `gap - explained_registered`。
5. 结果区先查看数据资产总览：480 行原始面板、60 天、8 个切面、240 条因子快照；随后查看总体趋势、分层热力、因子轨迹、候选关联关系和 3 份验证计划。原始明细首屏展示 48 行，展开可查看全部 480 行。需要只演示 B 线时再切换到 `B 线：开放因子挖掘`。

6. 结果区的“业务价值评测”是脱敏口径：平均归因时间 7.4 分钟、错误回滚率 0%、无效实验减少 31%、损失规避估算 18.6 万元。现场说明这些数字是验收示例，生产需接入工单、实验平台和财务口径重新计算。

**评委看点**：用户输入不是预制结果；页面显示工具调用和中间对象；外部候选不会自动变成因果结论。

## 2. 异常处理与治理（约 1 分钟）

1. 勾选 `注入本地模型超时`，重跑 B 线：结果保留，且 trace 显示 `LLM_FALLBACK`，规则解析接管。
2. 勾选 `注入外部源不可用`，重跑：页面显示外部候选保持 `UNKNOWN`，不会拿内部事件强行解释。
3. 切换 `拒答：没有随机化`：结果为 `REFUSED / DESCRIPTIVE_ONLY`，并给出补建随机实验的下一步。

**评委看点**：模型故障不影响确定性统计管线；数据不足时拒答；未知桶不是被任意分配的“其他”。

## 3. A 线与护栏（约 1 分钟）

1. 切换 `A 线：UI 改版实验`，勾选 `注入护栏超限` 后运行。
2. 结果区展示随机化条件下的 Bayes Bundle、高维 CATE 和重叠 subgroup 输出。
3. 护栏结果为 `PAUSE_RECOMMENDED`：只生成暂停建议，不自动回滚、放量或修改真实流量。

**评委看点**：A 线可以在随机化条件下讨论效应；B 线没有随机化时只做候选和验证编排。

## 3. 命令行复现（评委技术核查用，约 2 分钟）

```bash
# 主基准：线 A demo + 7 seeds 隐藏基准（约 16s）
python3 -m track2_v5
#   看点：Recall@5=1.00、ATE RMSE=0.0010、决策准确率 1.00、
#   matched factor recovery=0.90；mismatched factor recovery=0.75；
#   Brier 与基率噪声下界接近，避免把数据噪声误报成模型能力

# 50 seeds 消融：嵌套 vs 扁平 + 校准层 + t 后验（约 90s）
python3 -m track2_v5.nested_benchmark
#   看点：嵌套方向召回 0.18 vs 0.02；ECE 0.039 vs 0.063；
#   小样本决策准确率 0.52；Student-t 联合覆盖率 0.9383（experimental）

# 超参自证（两个，各约 40-60s）
python3 -m track2_v5.offline_pid_ablation   # PID 离线无增益（如实负结果）
python3 -m track2_v5.nu_annealing_sweep     # ν 扫参：曲线平坦，决策指标不敏感
```

## 4. 证据核对（1 分钟）

每次运行都会重写 `outputs/` 下对应 JSON，可当场打开与 PPT/手册数字逐字段比对：
`benchmark_metrics.json`、`nested_ablation_50seeds.json`、`experience_ablation.json`、
`offline_pid_ablation.json`、`nu_annealing_sweep.json`、`lineB_baseline_attribution.json` 等 11 份。

## 常见问题

- **端口被占**：`python3 run_server.py 8766` 换端口即可；
- **经验库场景较慢**：约 23–30 秒属正常（7 期 × 真实管线）；
- **想重置对话**：对话窗输入 `reset`；
- **停止服务**：终端 `Ctrl+C`。
