# 保险销售客户端归因工具

[English](README.md)

**Spec 驱动的开放影响因子挖掘与贝叶斯实验归因 Agent。**

面向保险自营平台的经营分析场景:当经营指标异常时(轮播 CTR 下降、保费月度波动),
自动回答三个问题——**变了多少是真的、当前证据支持哪些因子、下一步做什么实验**——
并保证每条结论可验证、可追溯、不越权。

## 目录

- [场景与痛点](#场景与痛点)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [控制台 API](#控制台-api)
- [目录结构](#目录结构)
- [样例输出](#样例输出)
- [评测指标](#评测指标)
- [验证](#验证)
- [数据来源与授权](#数据来源与授权)
- [合规边界](#合规边界)
- [文档](#文档)
- [License](#license)

## 场景与痛点

保险自营平台每月经营复盘的真实流程:指标异动 → 分析师人工排查配置变更、渠道结构、
素材版本、外部事件 → 结论常停留在"可能相关",无法区分因果与巧合,也无法回答
"接下来做什么实验"。具体痛点:

1. 影响因子空间开放,人工维度清单覆盖不全(新组件、新渲染器、运行质量问题)
2. 一次改版同时变多个属性,整体 A/B 拆不出组件级原因
3. 小分群噪声被当成"重大发现"(多重比较误报)
4. 无随机化证据时仍输出因果话术,金融场景下越权风险高
5. 月度归因把"我主动做的、外部发生的、用户自发的"混在一起,贡献百分比靠拍脑袋

## 核心能力

两条归因线,全部结论经证据分级状态机与 Claim Ledger 约束:

### 线 A:组件归因(Spec 驱动)

```
Growth UI Spec 三类 Diff(SpecDiff / RenderDiff / RuntimeDiff)
  → FactorMiner 开放候选扫描(不穷举因子清单)
  → 贝叶斯 Bundle 效应估计(Beta-Binomial 后验)
  → 层级收缩 HTE 分群分析(Gaussian 为已验证默认路径;Student-t 由独立上线门禁管理)
  → 因子化实验设计(全因子 / Resolution-IV)
```

### 线 B:实验基线归因(月度复盘)

```
A/B 持续对照基线
  + 变动注册表(我们主动做了什么)
  + 外部事件注册表(世界上发生了什么,恒为 TEMPORAL_ASSOCIATION)
  → gap 分桶:已注册且有实验的内部变动 / 未知残差
  → 旁路报告:共同外部冲击(已在 treated-control 中抵消,不再摊入 gap)
```

### 治理原则(不可关闭)

- 无随机化证据时只输出 `ASSOCIATION_ONLY`,禁止因果动词
- 外部因子恒为 `TEMPORAL_ASSOCIATION`,永不升级为因果
- 高风险动作(回滚、放量、配置变更)一律为**建议**状态,必须人工审批执行
- 证据不足即拒答(`REFUSED` / `DATA_INSUFFICIENT`),不硬答
- 每条结论带 claim_type、证据引用、后验不确定性;错误结论可撤回并留痕

### 实验完整性闭锁门禁

仅在元数据中声明 randomized 不足以输出因果结论。运行时会按
`randomization_unit` 检查 SRM 与分流稳定性，并结合基线平衡、跨臂污染、时间顺序、样本漏斗、cluster
完整性和并发实验。八项全部通过后，才允许运行 ITT、Bayesian bundle 决策和 HTE。

重复观测按显式主估计目标处理：

- `user_level`：先聚合到分析单元，再计算 ITT
- `exposure_level`：保留合格曝光，使用 CR1 cluster-robust 标准误
- `triggered_user`：明确标注为分配后条件估计，不属于 ITT
- cluster 随机设计按声明的 cluster 层级推断

## 系统架构

### 七 Agent 治理流水线(因果治理运行时)

| Agent | 职责 | 产出物 |
|---|---|---|
| `intent` | 业务问题意图解析 | `AnalysisIntent` |
| `metric_contract` | 指标口径治理(口径/窗口/粒度/版本锁定) | `MetricContract` |
| `data_acquisition` | 只读数据探查与质量校验 | `QueryPlan`, `DataQualityReport` |
| `diagnostic` | 漏斗与结构诊断、分群画像 | `AttributionCandidateSet` |
| `causal_evidence` | 因果就绪度分级与结论约束 | `EvidenceReport`, `ClaimLedger` |
| `experiment_planner` | 实验与行动方案设计(含护栏) | `ExperimentSpec` |
| `monitor_review` | 实验监控与复盘 | `MonitoringReport`, `PlaybookPatch` |

业务状态路径(异常/恢复态另计):

```
RECEIVED → INTENT_PARSED → METRIC_CONFIRMED → DATA_VALIDATED → DIAGNOSING
→ EVIDENCE_GRADED → ACTION_DRAFTED → COMPLIANCE_REVIEWED → AWAITING_APPROVAL
→ MONITORING → REVIEWED → CLOSED
```

证据不足或越权时进入 `DATA_INSUFFICIENT` / `DESCRIPTIVE_ONLY` /
`BLOCKED_BY_GUARDRAIL` / `NEEDS_HUMAN`,而不是硬答。

### Claim Ledger:证据分级状态机

每条归因结论在 9 个状态中晋升,每一级都有明确的证据门槛:

```
OBSERVED_ANOMALY → FACTORS_DISCOVERED → BUNDLE_EXPERIMENT_READY
→ BUNDLE_EFFECT_ESTIMATED → HETEROGENEITY_RANKED
→ COMPONENT_EXPERIMENT_DESIGNED → COMPONENT_EFFECT_ESTIMATED
→ POSTERIOR_UPDATED → DECISION_READY
```

4 类显式拒答:`ASSOCIATION_ONLY`(只有关联证据)、
`FACTOR_SPACE_INCOMPLETE`(因子空间不完整)、
`EXPERIMENT_NOT_IDENTIFIED`(实验不可识别)、
`INCONCLUSIVE_NEED_MORE_DATA`(数据不足)。

### 因子经验库(跨期学习)

归因后验逐期写回经验库,下一期作为信息先验加载:

- 旧经验按 0.5 衰减、上限封顶,防止陈旧先验主导
- PID 反馈调节的是旧版伪曝光尺度 `shrinkage_strength`，与 Student-t
  自由度 `nu` 是两个不同参数
- 先验与新数据偏离超过阈值时触发错配报警,自动降级为扁平估计

### 统计正确性升级

- rate/mix/interaction 分解严格闭合，并报告 closure error
- Student-t 真正进入随机效应后验和 `tau` 估计，输出显式记录 `tau`、`nu`和计算方法
- beam search 按异常强度剪枝，不再依赖字段顺序
- 实验臂不足以保持合法全因子/分数因子设计时直接拒绝，组件效应必须满秩可识别
- 统一输入契约拒绝非有限值、非法计数、重复 segment ID、非法 p-value 和不可识别实验臂
- 显式报告 BH/FDR、设计诊断、功效设计、流失膨胀、不等分流和 cluster design effect

### 技术特点

- **纯 numpy 单依赖**,无 PyMC/scipy/框架依赖,离线可完整复现
- 核心统计层零 LLM 依赖;LLM 仅用于意图理解与报告撰写(可替换,当前演示为规则模板)
- 仿真器显式 DAG + 结构方程公开,**真值与评测 oracle 分离**
- 基准评测进程隔离,种子与真值不暴露给被测方

## 快速开始

环境要求:Python 3.12+,仅依赖 `numpy`(`pip install -r requirements.txt`)。

```bash
# ① 线 A 端到端 demo + 7 seeds 基准(约 16 秒)
python3 -m attribution

# ② 线 B 实验基线归因 + 5 seeds 验证
python3 -m attribution.baseline_attribution

# ③ 经验库跨期学习消融(后验写回 + PID 自适应收缩 + 错配报警)
python3 -m attribution.experience_benchmark

# ④ 多因子嵌套收缩 + 校准层 50 seeds 消融(约 90 秒)
python3 -m attribution.nested_benchmark

# ④b Student-t 四真值族校准基准(约 65 秒)
python3 -m attribution.student_t_calibration_benchmark

# ⑤ 公开外部事件时间线映射 + 覆盖率统计
python3 -m attribution.external_events

# ⑥ 多维 rate 异常候选生成与可审计 beam search
python3 -m attribution.rate_aware_rca

# ⑦ 基于事件和因子快照的时序关联发现
python3 -m attribution.association_discovery

# ⑧ 因果治理基准(进程隔离,3 seeds / 9 cases)
python3 -m runtime --benchmark --benchmark-seeds 3

# ⑨ 输出并验证公开数据集来源目录
python3 -m runtime --datasets

# ⑩ UCI 真实公开数据案例(首次运行自动下载,CC BY 4.0)
python3 -m runtime --fetch-real-data

# ⑪ 本地控制台(REST API,默认端口 8765)
python3 run_server.py 8765
```

运行生成的证据 JSON 写入 `outputs/`,运行状态写入 `runtime_data/`,
两者均为本地生成物,不随仓库分发(见 .gitignore)。

## 控制台 API

```text
GET  /api/health                            健康检查
GET  /api/attribution/case?case=A|B|C       因果就绪度案例(观测/缺元数据/随机实验)
GET  /api/attribution/benchmark?seeds=8     进程隔离治理基准
GET  /api/attribution/datasets              公开数据集来源目录
GET  /api/attribution/bayes-case?case=C     门禁 + 贝叶斯决策层(门禁失败即拒答)
GET  /api/attribution/line-b-review         线 B 月度归因 Evidence Pack
GET  /api/attribution/real-data             UCI 真实数据(需先 --fetch-real-data)
GET  /api/attribution/scenarios             演示场景目录
GET  /api/attribution/scenario-run?scenario=full_review|line_a|line_b|external|bayes_case_a|experience
GET  /api/attribution/scenario-report?scenario=...   下载 Markdown 审计报告
POST /api/attribution/chat                  多轮对话 Agent(意图→澄清→计划→确认→真实执行)
       body: {"session_id": "demo", "message": "上个月注册量为什么掉了"}
       发送 "reset"/"重置" 清空会话
```

## 目录结构

```text
attribution/                  # 归因方法包(纯 numpy)
  bayes.py                    # Beta-Binomial 决策、层级 HTE、调节扫描
  spec.py                     # Growth UI Spec + SpecDiff/RenderDiff/RuntimeDiff
  factor_miner.py             # 开放候选发现
  association_discovery.py    # 事件/因子快照时序关联发现
  rate_aware_rca.py           # rate/mix/interaction 分解 + beam search
  input_validation.py         # 共享 fail-fast 统计输入契约
  factor_registry.py          # 因子元数据与来源注册
  factor_store.py             # 因子快照与经验持久化
  factor_retriever.py         # 时间安全的候选检索
  fdr.py                      # 多重检验校正
  experiment_designer.py      # 全因子/Resolution-IV 因子设计 + 组件效应
  experiment_platform.py      # 需审批的实验平台适配器
  validation_planner.py       # 基于证据的验证计划
  claim_ledger.py             # 证据分级状态机与晋升门禁
  insursim_carousel.py        # 显式 DAG 仿真器(真值与 oracle 分离)
  benchmark.py                # 贝叶斯专项评测(同构+错配,含分群预测 Brier)
  baseline_attribution.py     # 线 B:基线归因 + 变动/外部注册 + 未知标注
  experience_store.py         # 因子经验库:后验写回/跨期先验/PID 自适应收缩/错配报警
  experience_benchmark.py     # 经验库跨期消融(流量爬坡 7 期)
  calibration.py              # 分箱校准层(样本外可靠性映射)
  nested_benchmark.py         # 嵌套池化 + 校准 50 seeds 消融
  student_t_calibration_benchmark.py # Student-t 四真值族上线门槛
  external_events.py          # 公开外部事件时间线 + 映射覆盖率
  scenario_reports.py         # 控制台场景运行 + 审计报告渲染
  agent_chat.py               # 多轮对话 Agent:Plan-and-Execute 状态机
runtime/                      # 因果治理运行时(七 Agent 状态机 + 五层门禁)
  cases.py                    # 因果就绪度案例 A/B/C 纵向切片
  analysis.py                 # 确定性特征提取与因果就绪技能
  experiment_integrity.py     # 八项显式证据单位的 fail-closed 完整性检查
  benchmark.py                # 进程隔离基准(种子与真值不暴露给被测方)
  real_data.py                # UCI Bank Marketing 适配器(SHA-256 锁定)
  dataset_catalog.py          # 数据集来源目录
  bayes_bridge.py             # 治理运行时 ↔ 贝叶斯层桥接
  foundation.py               # 控制平面、证据包、检查点
  cli.py / configuration.py   # CLI 入口与配置
specs/                        # 轮播图 Growth UI Spec 两版本(可复用模板)
scripts/                      # 基准结果绘图工具
docs/methodology.md           # 每个机制的理论出处、工程改造与创新点
```

## 样例输出

### 线 A:轮播图异常归因

输入:旧样式 CTR 4.1% → 新样式 3.2%;两版 Growth UI Spec;曝光级日志(仿真器生成)。

```text
BUNDLE_EFFECT: 整套新样式使 CTR 变化 -0.0166,P(实际损害)=1.000 → ROLLBACK_RECOMMENDED
HETEROGENEOUS_TREATMENT_EFFECT: 低端设备分群负向效应最大(收缩后 -0.0272)
COMPONENT_EFFECT: carousel.text_density = -0.0117;carousel.image_component = -0.0078(独立随机化)
EXPERIMENT_INCONCLUSIVE ×3: layout / indicator_position / media_aspect_ratio 未达组件级证据标准
状态机终态: DECISION_READY
```

### 线 B:月度基线归因

输入:60 天对照组/处理组保费面板 + 变动注册表(2 项)+ 外部事件注册表(1 项)。

```text
效应估计验证: per-experiment ATT RMSE 10.233 → 5.552(下降 45.7%)
外部关联: ext_regulation 窗口偏离 -86.2,claim_type=TEMPORAL_ASSOCIATION
外部 gap 摊入: 无(共同冲击已在 treated-control 中抵消)
治理告警: UNEXPLAINED_STEP_SUSPECTED(day 39/54,真值未注册变更 day 40 + 漂移)
未知桶: 末 10 天均值 -95.8,claim_type=UNEXPLAINED(不摊派)
```

## 评测指标

全部指标本地可复现(命令见[快速开始](#快速开始)):

| 评测 | 指标 | 结果 |
|---|---|---|
| 仿真真值回测(5 seeds) | Recall@5 / ATE RMSE / CrI 覆盖率 / 决策准确率 / HTE 方向 / 因子还原 | 1.00 / 0.001 / 1.00 / 1.00 / 1.00 / 0.90 |
| 错配回测(2 seeds) | 决策准确率 / 因子还原 / Brier | 1.00 / 0.75 / 0.0445(接近 Bernoulli 方差下界) |
| 经验库跨期消融(7 期流量爬坡) | 冷启动期 ATE RMSE / 决策一致性 / 错配报警 | ↓10.9% / 无回退 / 精确触发无误报 |
| 嵌套池化 + 校准(50 seeds 小样本) | 方向召回 嵌套 vs 扁平 / 校准 ECE / Gaussian vs 联合 Student-t vs plug-in Student-t 95% 覆盖率 | 0.18 vs 0.02 / 0.0626→0.0390(−37.7%) / 0.8775 vs 0.9475 vs 0.3075 |
| 外部事件映射(90 天面板) | 真值事件召回 / 未注册变动错挂 / 映射覆盖率 | 100% / 0 错挂 / 0.500 |
| 治理基准(3 seeds / 9 cases) | 门禁准确率 / 错误因果断言率 / 拒答召回 | 1.00 / 0.00 / 1.00 |
| 线 B 验证(5 seeds) | 未注册变动召回 / 外部对齐 / 未知诚实率 | 1.00 / 1.00 / 1.00 |
| 收缩消融 | 调节 RMSE 层级 vs 朴素 | 同构 0.0030 vs 0.0048;线 B 5.55 vs 10.23(↓46%) |
| Student-t 四真值族校准(4 × 50 seeds) | 联合后验 vs plug-in 覆盖率 / 最低真值族覆盖率 / 相对 Gaussian 区间宽度 | 0.9383 vs 0.5588 / 0.9100 / 1.122 |
| UCI 真实数据(45,211 条) | 门禁识别无随机分配 + 泄漏变量标记 + 贝叶斯层拒答 | 全部正确 |

## 验证

不向工作树写入生成证据时，可用以下命令验证安装与核心链路：

```bash
python3 -m runtime --datasets
python3 -m runtime --benchmark --benchmark-seeds 1
python3 -m unittest discover -s tests -v
ruff check . && ruff format --check .
python3 -c "import attribution, runtime, run_server"
```

因果就绪 fixture 的 A、B、C 案例必须分别保持
`DESCRIPTIVE_ONLY`、`DATA_INSUFFICIENT`和 `CAUSAL_READY`。

## 数据来源与授权

| 数据 | 来源 | 授权 | 处理方式 |
|---|---|---|---|
| 仿真数据(轮播场景生成器) | 本仓库内置生成器 | 自有 | 显式 DAG + 结构方程公开;真值与评测 oracle 分离;仅用于方法验证,不声称代表真实因果 |
| UCI Bank Marketing | UCI ML Repository(doi:10.24432/C5K306) | CC BY 4.0 | 只读分析;行级数据不含可识别个人信息;运行时下载,不随仓库分发 |
| Growth UI Spec 示例 | 本仓库编写(参考 OpenUI/WICG 公开草案思想) | 自有 | 模板可复用 |
| 公开外部事件时间线(LPR 调整、报行合一、618、开学季) | 公开发布/公开日历 | 公开信息 | 仅作外生事件示例与映射演示;生产接入需对接正式数据源 |

## 合规边界

- 系统**不做**承保、理赔、精算、风控、授信、投资判断或保险赔付结论
- 不做个人级保险推荐、个人营销名单;所有分群分析聚合到小分群抑制阈值以上
- 无随机化证据时只输出关联级结论并附非因果警告;外部因子永不升级为因果
- 高风险动作(回滚、放量、配置变更)一律为建议状态,必须人工审批执行
- 演示与评测全部使用合成数据与 CC BY 4.0 公开数据,不含真实用户数据

## 文档

- [方法依据、工程改造与创新点](docs/methodology.md) — 每个核心机制的理论出处、
  项目特有改造、可验证的差异化优势，以及部分池化、DoWhy/EconML 和工业 AB 引擎对标

## License

代码:[Apache-2.0](LICENSE);文档:CC BY 4.0。
