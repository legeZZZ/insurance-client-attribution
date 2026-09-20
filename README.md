# GOAI 赛道二参赛交付包 · Spec 驱动的开放影响因子挖掘与贝叶斯实验归因 Agent

> **2026-09-16 后端交付更新：**阶段A–F当前授权范围已完成。本机及Linux容器234/234后端测试，E/F共48项CLI验收；控制台相关内容保持历史版本，全部暂缓。当前运行、锁定依赖与离线部署以[后端交付与迁移说明](docs/后端交付与迁移说明.md)为准；逐文件落实见[交付映射与验收索引](docs/交付映射与验收索引.md)，统计适用条件与负结果见[阶段E-F评测报告](docs/阶段E-F评测报告.md)。下文旧版本指标只表示历史快照。

> 适用赛题：**AI+金融｜面向企业经营与风险研判的金融服务 Agent**（参赛手册 §4.3.3）
> 版本：v13.0 决赛版 · 2026-09-14 · 在 v12.0 实施版（统计修订、Factor RAG、N2/N3 适配器、实验完整性门禁）之上，新增决赛 D5–D7 升级：人在回路确认、技能自进化、C 线主动盯防。

---

## 1. 项目信息

| 项目 | 内容 |
|---|---|
| 项目名称 | 保险销售客户端经营归因 Agent —— 异动下钻、证据分级与决策闭环 |
| 所选赛题 | AI+金融（企业经营与风险研判） |
| 目标用户 | 保险自营平台的经营分析、增长、产品与运营团队；二审用户为合规与风控审阅者 |
| 核心问题 | 经营指标异常时，"变了多少是真的、哪个因子造成的、下一步做什么实验"缺少可验证、可追溯、不越权的自动化回答 |
| 解决方案 | 两条归因线：组件归因（Growth UI Spec 三类 Diff → FactorMiner → 聚合 Beta-Binomial Bundle 门禁 → 高维重叠 CATE/HTE → 因子化实验）+ 实验基线归因（A/B 持续对照基线 → rate-aware 多维候选生成 → 内外部因子关联 → 反事实验证），全部结论经证据分级状态机与 Claim Ledger 约束 |
| 创新点 | ① Spec-driven 开放因子空间（不穷举因子清单）；② 证据分级状态机与拒答治理；③ 后验驱动的决策与下一轮实验闭环；④ 归因=汇总非分解 + "未知"诚实标注 |
| 开放/复用价值 | 含锁定统计依赖的方法包、组件 Spec 模板、脱敏数据生成器、评测 harness、示例数据与证据 JSON，可整体复用 |
| 当前进展 | 两条归因线可运行且指标达标；v3 治理基线不回退；UCI 真实数据接入；v6.1（经验库+PID+重尾+错配报警）与三期产品化（M1 嵌套+校准 50 seeds、M2 外部事件映射、M3 控制台场景→实测→报告下载）全部落地并有消融证据；A 线新增 high-dimensional overlap ridge CATE；决赛新增 D5 人在回路（候选确认/因子补充/告警反馈留证）、D6 技能自进化（轨迹→patch→影子回放→证据门晋级，保护统计核心不可自改）、D7 C 线主动盯防（复用 lead-lag 观测 + 三杀证伪，产出 WATCHLIST）；当前回归 61/61 |

## 2. 场景来源与用户痛点

保险自营平台每月经营复盘的真实流程：指标异动（如轮播 CTR 下降、保费月度波动）→ 分析师人工排查配置变更、渠道结构、素材版本、外部事件 → 结论常停留在"可能相关"，无法区分因果与巧合，也无法回答"接下来做什么实验"。痛点：

1. 影响因子空间开放，人工维度清单覆盖不全（新组件、新渲染器、运行质量问题）；
2. 一次改版同时变多个属性，整体 A/B 拆不出组件级原因；
3. 小分群噪声被当成"重大发现"（多重比较误报）；
4. 无随机化证据时仍输出因果话术，金融场景下越权风险高；
5. 月度归因把"我主动做的、外部发生的、用户自发的"混在一起，贡献百分比靠拍脑袋。

## 3. 任务闭环（对应参赛手册 §8.2）

1. **任务输入**：指标异常事件（控制台/API/真实脱敏数据），或月度归因请求。
2. **意图理解**：MetricContract 锁定指标口径、窗口、粒度与版本（v3 已有能力）。
3. **任务规划**：状态机驱动——发现 → 基线实验 → 异质分析 → 组件实验 → 决策，每步声明所需工具与证据。
4. **能力调用**：Spec 解析与三类 Diff、FactorMiner 候选扫描、Beta-Binomial 聚合后验、高维重叠 CATE/HTE、因子设计器、变动/外部注册表、基线归因引擎。
5. **结果交付**：Claim Ledger 结构化结论（claim_type、后验概率、区间、允许/禁止动词）+ 决策建议（回滚/放量/继续/等价）+ 下一轮实验设计 + Evidence Pack。
6. **验证与反馈**：脱敏数据回测、错配回测、真实公开数据、消融对照、v3 隐藏基准，指标见 §6。
7. **安全边界**：无随机化只输出 ASSOCIATION_ONLY；外部因子恒为 TEMPORAL_ASSOCIATION；残差标"未知"；高风险动作全部转人工（见 §7）。

## 4. 运行入口与依赖（复现说明）

### 4.1 环境要求

- Python 3.9+（推荐 Python 3.12），仅依赖 `numpy`（无 PyMC/scipy/框架依赖）。
- 本包不调用任何商业 API 或闭源模型；统计与归因全部为确定性可复现代码。

### 4.2 一键运行

#### 演示控制台

```bash
# 首次或重置演示数据（C线扫描、因子库、技能治理链全部真实管线生成）
.venv/bin/python tools/seed_console_v2.py

python3 run_server.py 8765
# 浏览器打开 http://127.0.0.1:8765
```

默认入口是决赛控制台 v3（`web/static/final-console-v3.html`，由 `tools/build_console_v3.py` 从模板生成）：浅色工作台 + 深色指挥中心双层设计（视觉体系复刻复赛演示页），六个视图——归因总控（3D 因子证据球，three.js r160，WebGL/CDN 不可用自动 2D 回退；高风险因子红色脉冲环）、风险预警中心（C 线：趋势预警 + 冲突预警「违背已验证归因逻辑」，如轮播图配置异常；预警生命周期 新预警→待确认→处置中→已闭环）、待办看板（HITL 统一收件箱：候选确认/证据冲突/发布审批/告警反馈四节点聚合，权限矩阵内嵌详情面板）、因子库（色条卡片网格，服务模式最多 40 条 B 线真实候选）、因子管理（人报因子补录/停用/启用 + 变更台账）、自进化与证据（技能治理时间线 + 负结果专区）。顶部全局预警条常驻所有视图。新增端点：`GET /api/v2/alerts`、`POST /api/v2/alerts/action`、`POST /api/v2/factors/manage`、`GET /api/v2/factors/ledger`。**零安装体验**：双击该文件即可离线回放（操作仅本地留痕并标注）。

历史入口：`/semifinal-demo.html`（复赛全流程页：提交经营问题后由 `GET /api/track2/scenario-run` 一次结果驱动 3D 指挥台、阶段轨迹与结果区；服务不可用时使用明确标注的本地脱敏数据回放）。`UNEXPLAINED` 是正常的证据状态，表示当前仍保留未解释阶跃，不是执行失败；真实管线失败时 API 返回 JSON 错误对象。

#### GitHub 仓库部署为可执行 HTTP 服务

本项目不是 GitHub Pages 静态页。仓库推送到 GitHub 后，应部署为 Web Service：服务启动 `run_server.py`，根路径打开控制台，`/api/...` 由 Python 后端实时返回结构化归因结果。

已内置三种部署入口：

- `render.yaml`：Render Blueprint / Web Service
- `Procfile`：Railway、Heroku 风格平台
- `Dockerfile`：Docker / Fly.io / 自有服务器

云平台会注入 `PORT`，服务会自动监听 `0.0.0.0:$PORT`。完整步骤见 `HTTP_DEPLOY.md`。

#### 升级 Demo（脱敏数据回放，采用可替换授权适配器）

```bash
# N1 外部事件适配器 + N2 本地模型/规则兜底 + N3 实验平台 dry-run 灰度
python3 -m track2_v5.replay_upgrade_demo
```

输出 `outputs/upgrade_demo_evidence.json` 和 `outputs/upgrade_demo_report.md`。快速运行与故障排查见 `运行说明.md`；决赛完整方案与叙事版见交付包根目录 `方案文档/`。

```bash
# v13 回归测试：v12 全套 + D5–D7 共 61 条
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

```bash
# ① 线 A 端到端 demo + 7 seeds benchmark（约 16 秒）
python3 -m track2_v5

# ② 线 B 实验基线归因原型 + 5 seeds 验证
python3 -m track2_v5.baseline_attribution

# ②b 经验库跨期学习消融（后验写回 + PID 自适应收缩 + 错配报警，v6.1）
python3 -m track2_v5.experience_benchmark

# ②c 多因子嵌套收缩 + 校准层 50 seeds 消融（M1，约 90 秒）
python3 -m track2_v5.nested_benchmark

# ②g 概率差尺度 B 线关联因子发现脱敏数据回放（事件 + 因子快照时序）
python3 -m track2_v5.association_discovery

# ②h 内部多维 rate 指标候选生成（Squeeze 风格 beam search）
python3 -m track2_v5.rate_aware_rca

# ②e PID 离线单轮消融（fixed ν / PID / PID+t 三配置对照，约 40 秒）
python3 -m track2_v5.offline_pid_ablation

# ②f 收缩强度 ν 退火扫参（对数网格 50–2000 × 双侧指标，约 60 秒）
python3 -m track2_v5.nu_annealing_sweep

# ②d 公开外部事件时间线映射 + 覆盖率统计（M2）
python3 -m track2_v5.external_events

# ②e 决赛 D5 人在回路：候选确认/因子补充/告警反馈 → JSON 存证 + 预算校准
python3 -m track2_v5.human_feedback

# ②f 决赛 D6 技能自进化：Trace2Skill 式轨迹→patch→影子回放→证据门晋级（含回滚）
python3 -m track2_v5.skill_evolution

# ②g 决赛 D7 C 线主动盯防：扫描已关联因子 + 三杀证伪 → WATCHLIST 预警
python3 -m track2_v5.watchlist_scan

# ③ v3 治理基线隐藏基准（3 seeds / 9 cases）
cd track2_clean_bundle
PYTHONPATH=src python3 -m goai_control_tower --track2-benchmark --track2-benchmark-seeds 3

# ④ UCI 真实公开数据案例
PYTHONPATH=src python3 -m goai_control_tower \
  --track2-real-data --track2-real-data-path runtime_data/datasets/uci-bank-marketing/data.csv

# ⑤ 本地控制台（含 v5 贝叶斯端点与线 B 月报端点）
python3 run_server.py 8765
#   GET /api/track2/case?case=A|B|C      v3 案例
#   GET /api/track2/bayes-case?case=C    v3 门禁 + 贝叶斯决策层
#   GET /api/track2/line-b-review        线 B 月度归因 Evidence Pack
#   GET /api/track2/real-data            UCI 真实数据
#   GET /api/track2/scenarios            产品化演示场景目录（M3）
#   GET /api/track2/scenario-run?scenario=full_review|line_a|line_b|external|bayes_case_a|experience
#   GET /api/track2/scenario-report?scenario=...   下载 Markdown 审计报告
#   POST /api/track2/chat                多轮对话 Agent（意图→澄清→计划→确认→真实执行）
#     body: {"session_id": "demo", "message": "上个月注册量为什么掉了"}
#     证据样例: outputs/chat_demo_evidence.json
```

### 4.3 目录结构

```text
track2_v5/                    # v5/v6 方法包（纯 numpy）
  bayes.py                    # Beta-Binomial 决策、层级 HTE、高维重叠 CATE、调节扫描
  spec.py                     # Growth UI Spec + SpecDiff/RenderDiff/RuntimeDiff
  factor_miner.py             # 开放候选发现
  experiment_designer.py      # 全因子/Resolution-IV 因子设计 + 组件效应
  claim_ledger.py             # 证据分级状态机与晋升门禁
  insursim_carousel.py        # 显式 DAG 脱敏数据生成器（真值与 oracle 分离）
  benchmark.py                # 贝叶斯专项评测（同构+错配，含分群预测 Brier）
  baseline_attribution.py     # 线 B：基线归因 + 变动/外部注册 + 未知标注
  rate_aware_rca.py           # 线 B：概率差 rate/mix/interaction + 多维候选生成
  association_discovery.py    # 去趋势 block bootstrap + max-T + holdout
  factor_registry.py          # SQLite Factor Registry / Evidence / Series
  factor_store.py              # Factor Registry 应用 facade
  factor_retriever.py          # Factor RAG 候选与来源检索
  validation_planner.py        # 候选到验证方案的确定性编排
  fdr.py                       # 锁定候选集合后的 BH 辅助 q 值
  temporal_null.py             # 去趋势、季节项、moving-block、max-T
  agent_adapter.py             # N2 本地模型 schema/兜底 + N3 Agent 门面
  experiment_platform.py       # N3 dry-run 实验平台契约
  experience_store.py         # 因子经验库：后验写回/跨期先验/PID 自适应 ν/错配报警
  experience_benchmark.py     # 经验库跨期消融（流量爬坡 7 期）
  calibration.py              # 分箱校准层（样本外可靠性映射，M1）
  nested_benchmark.py         # 嵌套池化 + 校准 50 seeds 消融（M1）
  external_events.py          # 公开外部事件时间线 + 映射覆盖率（M2）
  scenario_reports.py         # 控制台场景运行 + 审计报告渲染（M3）
  agent_chat.py               # 多轮对话 Agent：Plan-and-Execute 状态机（8.1-2）
  human_feedback.py           # 决赛 D5：人在回路确认/补充/反馈存证 + 预算校准
  skill_evolution.py          # 决赛 D6：技能自进化（轨迹→patch→影子回放→晋级/回滚）
  watchlist_scan.py           # 决赛 D7：C 线主动盯防（三杀证伪 → WATCHLIST）
specs/                        # 轮播图 Growth UI Spec 两版本（可复用模板）
track2_clean_bundle/          # v3 治理运行时（五层门禁、Claim Ledger、控制台）
outputs/                      # 运行证据（11 份 JSON + benchmark 图）
```

### 4.4 交付包结构（评审导览）

```text
决赛交付包结构：
  可执行代码包/                   # 即本 README 所在目录
    README.md（本文件：运行入口/依赖/配置/样例/证据索引）
    运行说明.md                    # 快速运行与故障排查
    演示手册.md                    # 控制台从初始状态开始的 5 分钟现场脚本
    数据来源与合规说明.md          # 数据类型、来源、授权、脱敏、隐私和专业决策边界
    验证交接手册.md / 真实数据验证手册.md
    requirements.txt / run_server.py
    track2_v5/ track2_clean_bundle/ src/ web/ specs/ outputs/ tests/
  方案文档/
    赛道二-升级方案-v17-决赛完整版.html   # 完整升级方案（算法 + Agent 架构 + D5–D7）
    赛道二-项目方案-叙事版-v18.html      # 15 分钟汇报叙事版
```


## 5. 样例输入输出

### 线 A 输入（轮播图异常）

```text
旧样式 CTR 4.1% → 新样式 3.2%；两版 Growth UI Spec（specs/*.json）；曝光级日志（脱敏数据生成器生成）
```

### 线 A 输出（节选，outputs/demo_evidence.json）

```text
BUNDLE_EFFECT: 整套新样式使 CTR 变化 -0.0166，P(实际损害)=1.000 → ROLLBACK_RECOMMENDED
HETEROGENEOUS_TREATMENT_EFFECT: 低端设备分群负向效应最大（收缩后 -0.0272）
COMPONENT_EFFECT: carousel.text_density = -0.0117；carousel.image_component = -0.0078（独立随机化）
EXPERIMENT_INCONCLUSIVE ×3: layout / indicator_position / media_aspect_ratio 未达组件级证据标准
状态机终态: DECISION_READY
```

### 线 B 输入

```text
60 天对照组/处理组保费面板 + 变动注册表（2 项）+ 外部事件注册表（1 项）
```

### 线 B 输出（节选，outputs/lineB_baseline_attribution.json）

Line B 的计算口径是 `gap = treated - control`，`residual = gap - explained_registered`。共同外部冲击已经在 treated-control 差分中抵消；外部事件只从 control 的趋势偏离生成 `TEMPORAL_ASSOCIATION` 旁路信号，不参与残差扣减，不重复计入解释量。输出中的 `external_explained` 为兼容字段，固定为零；实际旁路信号见 `external_association_signal`。

```text
ATT 汇总: naive 116.4 → 层级 119.4（真值 100，含实验噪声）
外部关联: ext_regulation 窗口偏离 -86.2，claim_type=TEMPORAL_ASSOCIATION
治理告警: UNEXPLAINED_STEP_SUSPECTED（onset day 39/54，异常窗口为 [37,41] / [52,56]；共同外部冲击未二次扣减）
未知桶: 末 10 天均值 -95.8，claim_type=UNEXPLAINED（不摊派）
```

## 6. 运行证据与评测指标

| 证据 | 指标 | 结果 |
|---|---|---|
| 脱敏数据回测（5 seeds） | Recall@5 / ATE RMSE / CrI 覆盖率 / 决策准确率 / HTE 方向 / 因子还原 | 1.00 / 0.001 / 1.00 / 1.00 / 1.00 / 1.00 |
| 错配回测（2 seeds） | 同上 + Brier | 决策与还原保持 1.00；Brier 0.032→0.044（接近 Bernoulli 方差下界 ~0.04，退化主要来自基率漂移）；分群自适应预测 0.044→0.0439，重尾似然作保险（如实报告） |
| 经验库跨期消融（v6.1，7 期流量爬坡） | 冷启动期 ATE RMSE / 决策一致性 / 错配报警 | 0.00451→0.00402（↓10.9%）/ 7 期一致无回退 / 错配 onset 期精确触发（偏离 0.013 vs 正常 ≤0.006），无误报 |
| 嵌套池化 + 校准（M1，50 seeds 小样本） | 方向召回 嵌套 vs 扁平 / 校准 ECE / 小样本决策准确率 / Student-t 联合覆盖率 | **0.18 vs 0.02** / ECE **0.039 vs 0.063** / 小样本决策准确率 **0.52** / 联合 Student-t 覆盖率 **0.9383**；moderation RMSE 高于 flat，不能宣传为全面提升 |
| 高维重叠 HTE（A 线行级实验） | 特征数 / 连续特征 / 设计列 / 重叠 subgroup / 多重命中样本 | 19 / 15 / 91 / 7 / 21385；聚合门禁仍由 Beta-Binomial 给出，事后 subgroup 标记为 EXPLORATORY_HDIM_HTE |
| 理论 Brier 下界（双重独立验证，2026-08-15） | 实测 Brier vs 上帝模型下界（最优占比） | 同构 0.0321 vs 0.0318（**99.1%**）；错配 0.0445 vs 0.0437（**98.2%**）——退化来自数据噪声下界，非模型缺陷 |
| 外部事件映射（M2，90 天面板） | 真值事件召回 / 未注册变动错挂 / 映射覆盖率 | 100% / 0 错挂（保持 UNEXPLAINED）/ 0.500 |
| 控制台产品化（M3） | 五场景 API 实测 / 报告下载 | 全部实机运行通过 / Markdown 报告 HTTP 200 |
| 多轮对话 Agent（8.1-2） | 意图→澄清→计划→确认→真实执行 | 五轮混合意图会话全通过（`chat_demo_evidence.json`），执行均为真实管线非预置输出 |
| UCI 真实数据（45,211 条，CC BY 4.0） | 门禁识别无随机分配 + 泄漏变量标记 + 贝叶斯层拒答 | 全部正确 |
| 收缩消融 | 调节 RMSE 层级 vs 朴素 | 同构 0.0042 vs 0.0048；线 B 5.55 vs 10.23（↓46%） |
| PID 离线消融（7 seeds 三配置） | fixed ν vs PID vs PID+t：Brier / 决策 / 伪分群 FP | 完全一致（等价判定通过，ν 仅 500→501）；如实验证「离线无增益」，PID 收益归时序场景 |
| ν 退火扫参（对数网格 × 7 seeds） | 内点最优 / 默认值差距 / 全网格方向检出与 FP | 最优 ν=1400，默认 500 差距 12.1%，曲线平坦（<15%）；全网格 7/7 检出、FP=0，决策指标对 ν 不敏感——默认 500 为保守选择，线上由 PID 自适应 |
| v3 隐藏基准（3 seeds / 9 cases） | 门禁准确率 / 错误因果断言率 / 拒答召回 | 1.00 / 0.00 / 1.00 |
| 线 B 原型（5 seeds） | 未注册变动召回 / 外部对齐 / 未知诚实率 | 1.00 / 1.00 / 1.00 |
| 决赛 D5 人在回路 | 确认/补充/反馈三类留证 / 预算校准三档 | 全通过（by_kind 计数、0.5/1.0/1.5 校准生效） |
| 决赛 D6 技能自进化 | patch 无冲突合并 / 影子回放晋级 / 回滚 / 统计核心自改拦截 | 全通过（`SELF_MODIFICATION_FORBIDDEN` 生效） |
| 决赛 D7 C 线主动盯防 | 埋针因子入 WATCHLIST / 噪声过滤 / 三杀证伪 | 埋针 driver 在 lag 2 入选；噪声被 MIN_STRENGTH 过滤；安慰剂/lead-lag 反转/半段符号三关生效 |

证据文件（均在 `outputs/`）：`benchmark_metrics.json`、`demo_evidence.json`、`v3_caseC_bayes.json`、`T2-real-uci-bayes.json`、`lineB_baseline_attribution.json`、`lineB_association_discovery.json`、`lineB_rate_aware_rca.json`、`experience_ablation.json`、`nested_ablation_50seeds.json`、`external_event_mapping.json`、`offline_pid_ablation.json`、`nu_annealing_sweep.json`、`chat_demo_evidence.json`。

文档归类：方案文档见交付包根目录 `方案文档/`（v17 完整版 + v18 叙事版）；历史修订稿与评审纪要未纳入本包，仅供团队内部溯源。

## 7. 数据来源、授权与合规边界

### 数据来源

| 数据 | 来源 | 授权 | 处理方式 |
|---|---|---|---|
| InsurSim / InsurSim-Carousel 脱敏数据 | 本团队自写生成器 | 自有 | 显式 DAG + 结构方程公开；真值与评测 oracle 分离；仅用于方法验证，不声称代表真实因果 |
| UCI Bank Marketing | UCI ML Repository（doi:10.24432/C5K306） | CC BY 4.0 | 只读分析；行级数据不含可识别个人信息；使用时附来源与许可 |
| Growth UI Spec 示例 | 本团队编写（参考 OpenUI/WICG 公开草案思想） | 自有 | 模板可复用 |
| 公开外部事件时间线（LPR 调整、报行合一、618、开学季） | 公开发布/公开日历 | 公开信息 | 仅作外生事件示例与映射演示，不声称实时性；生产接入需对接正式数据源 |

### 知识库与上下文增强说明（对应手册 §8.4 逐条）

**① 数据/知识库的来源、更新时间、授权与适用边界**

| 知识库 | 构建方式 | 来源与授权 | 更新时间 | 适用边界 |
|---|---|---|---|---|
| 变动注册表 / 外部因子注册表 | 结构化 JSON 注册，随代码交付 | 本团队整理（自有） | 随版本更新（当前 2026-08-15） | 仅注册"何时对何范围做了什么"，不含个人数据 |
| 因子经验库（experience_store.json） | 归因后验逐期写回，旧经验 0.5 衰减、上限封顶 | 系统自生成 | 每次归因运行后自动更新 | 仅聚合统计量（Beta 形状/效应估计），无行级数据 |
| 公开外部事件时间线 | 手工整理 + 滞后约束映射 | 公开发布信息 | 样例截至 2024-09；演示用途 | 时间对齐仅输出 TEMPORAL_ASSOCIATION，永不升级为因果 |

**② 检索策略、引用来源、错误处理**：v12 实现为 **Factor Registry + SQLite FTS5/中文 LIKE 回退 + 结构化过滤 + 统计对齐**。`factor_registry.py` 保存因子、别名、适用范围、证据、快照、来源和许可证；`factor_retriever.py` 只返回候选与可引用证据，`validation_planner.py` 再生成独立验证任务。`map_anomalies_to_events` 仍负责 ±7 天事件映射。检索失败、证据不足或来源未授权时不挂靠、不硬答，保持 `UNEXPLAINED`/`FACTOR_CANDIDATE`。

**③ 用户输入/业务数据的脱敏与最小化**：演示与评测全部使用合成数据与 CC BY 4.0 公开数据，不含真实用户输入；真实部署设计为字段级最小化（仅指标聚合值进归因层）、subject_id 哈希化、聚合输出、查询审计与留存期控制（v3 数据契约已含 subject_id_hash / authorization_id 字段）；删除机制：注册表与经验库均为可编辑 JSON，支持按键删除与整体重置。

**④ 上下文、记忆、状态与历史信息管理**：RAG 记忆由 `Factor Registry` 保存因子定义、证据和时序快照；跨期统计记忆仍由因子经验库负责后验写回、衰减加载、PID 自适应收缩和错配报警；流程状态由 Claim Ledger 记录。三者职责分离：RAG 不修改 Bayesian 后验，经验库不替代来源证据，任一会话可从 Evidence Pack 重建。

### 合规边界（金融赛题 §9.3 / §4.3.3）

- 系统**不做**承保、理赔、精算、风控、授信、投资判断或保险赔付结论；
- 不做个人级保险推荐、个人营销名单；所有分群分析聚合到小分群抑制阈值以上；
- 无随机化证据时只输出关联级结论并附非因果警告；外部因子永不升级为因果；
- 高风险动作（回滚、放量、配置变更）一律为**建议**状态，必须人工审批执行；
- 结论带 claim_type、证据引用、后验不确定性；错误结论可撤回并留痕。

### 隐私保护

脱敏数据生成器与公开数据集均不含个人敏感信息；真实部署设计为行列级权限、subject_id 哈希化、聚合输出、查询审计（v3 数据契约已含 subject_id_hash / authorization_id 字段）。

## 8. 模型、Agent 架构与工具接口

- **模型**：无 LLM 依赖的核心统计层（Beta-Binomial、层级部分池化、高维重叠 CATE、Resolution-IV 设计、PSI、CUSUM 式阶梯检测）；LLM 仅用于意图理解与报告撰写（可替换任意兼容模型，当前演示为规则模板，无商业 API 调用）。**显式声明：本交付包不调用任何商业 API、不依赖任何闭源模型；全部代码为确定性统计实现，离线可完整复现。**
- **Agent 架构**：v3 七 Agent（Intent / MetricContract / DataAcquisition / Diagnostic / CausalEvidence / ExperimentPlanner / MonitorReview）+ 确定性 Policy 护栏；状态机 23 态 + 证据分级 9 态。
- **工具接口**：控制台 REST API（§4.2⑤）；Evidence Pack JSON Schema；Spec JSON Schema；Claim Ledger Schema。
- **知识库**：`Factor Registry` 保存可检索的因子定义、证据和时序快照；`experience_store.py` 继续负责归因后验逐期写回、跨期加载为信息先验、PID 反馈自适应收缩和先验偏离报警。两者职责分离：RAG 不修改 Bayesian 后验，经验库不替代来源证据。

## 9. 基于已有项目的说明（手册 §9 要求）

本交付包基于本团队前期自研的 `track2_clean_bundle`（v3 治理运行时，2026-07/08）继续开发，新增贡献为：track2_v5 方法包（贝叶斯层、Spec 层、线 B 归因层）、v3-v5 桥接、控制台新端点、全套贝叶斯评测与参赛文档。无第三方代码拷贝；唯一外部数据为 CC BY 4.0 的 UCI 公开数据集。

## 10. 后续迭代计划

| 阶段 | 内容 |
|---|---|
| M3 | v6.1 已完成：经验库持久层 + PID 自适应收缩 + Student-t 重尾似然 + 错配报警（消融见 §6）；下一步：PyMC 分层 Logistic / BART challenger 接入预留接口；RenderDiff 真实渲染快照接入；控制台线 B 月报 UI 面板；跨实验元分析 |
| M4 | 变动注册表对接真实发布系统（assignment_provenance）；序贯监测与护栏实时联动；贝叶斯结构时序用于外部因子强度估计 |
| M5 | 多组件 Spec 模板库 + ModelScope/开源发布（许可证梳理后）；真实实验平台数据持续校准 |

## 11. 开放 / 复用计划

可复用资产：`track2_v5` 方法包（numpy 单依赖）、Growth UI Spec 模板（specs/）、InsurSim-Carousel 脱敏数据生成器、贝叶斯评测 harness、示例输入输出与证据 JSON、方法文档（v6 方案 + 验证报告 + 答辩 QA）。决赛提交时整理为可访问仓库（许可证：代码 Apache-2.0 意向，文档 CC BY 4.0 意向，提交前完成依赖与许可证扫描）。
