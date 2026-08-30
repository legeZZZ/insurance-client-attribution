# 方法依据与借鉴边界

本文档说明方案中每个核心机制的理论来源、我们借鉴了什么、以及我们没有直接照搬的部分。
原则：**站在成熟方法与开源实践之上，但每一层都针对"金融归因的可审计、可拒答"约束做了改造**。

---

## 1. 部分池化 / 收缩估计（线 B 月度归因的核心）

**理论来源**

- Efron & Morris (1975, 1977)：Stein 悖论与 James–Stein 估计——小样本分组直接向全局均值收缩，均方误差优于各组独立估计。
- Gelman & Hill (2006)《Data Analysis Using Regression and Multilevel/Hierarchical Models》：多层模型部分池化的工程化标准做法。
- Gelman & Pardoe (2006)：pooling factor 量化每个组的收缩程度。

**我们借鉴了什么**：单实验的效应估计向全局/分层先验收缩，收缩权重由组内样本量与组间方差自动决定（`attribution/bayes.py` 的层级估计）。
实测效果：per-experiment ATT RMSE 朴素 10.23 → 层级 5.55（`outputs/lineB_baseline_attribution.json`），总量守恒误差从 116.4 降至近零。

**没有照搬的部分**：标准部分池化假设"组间真值同分布"。金融业务中渠道/地区结构突变会违反该假设，因此我们加了**错配退化检测**（先验与新数据冲突时自动降级为扁平估计并报警），见 §3。

## 2. 模拟基准校验 SBC（可验证性的金标准）

**理论来源**

- Cook, Gelman & Rubin (2006)：从贝叶斯模型生成数据再回拟合，检验后验校准。
- Talts et al. (2018, arXiv:1804.06788) "Validating Bayesian Inference Algorithms with Simulation-Based Calibration"：SBC 的统一框架与 rank 统计量均匀性判据。
- Modrák et al. (2023) / Säilynoja et al. (2026)：SBC 在实现层的落地检查清单。

**我们借鉴了什么**：全部验证均为"模拟真值已知 → 管线盲跑 → 对比真值"的 SBC 式闭环——
主基准 7 seeds（5 个 matched + 2 个 mismatched，Recall@5=1.00、ATE RMSE=0.0010）、
50 seeds 嵌套消融（方向召回 0.18 vs 0.02）和校准对比（ECE 0.0626→0.0390）。
区间覆盖率必须单独解读：Gaussian 为 0.8775，当前 Student-t plug-in-`tau` 路径仅为 0.3075，
是明确的负结果。所有结果可一键复现。

**没有照搬的部分**：经典 SBC 检验后验 rank 均匀性；我们面向的是决策场景，改为检验**决策级指标**（召回、RMSE、拒答正确率、报警 onset 精度），对评审更直观。

## 3. 错配退化的控制论处理（团队内部迭代引入）

**理论来源**

- 控制论 PID：用误差的比例/积分/微分反馈调节参数。
- 强化学习/深度学习中的探索-利用：局部最优 vs 全局最优的修正思想。

**我们的改造**：经验库先验更新不是纯贝叶斯共轭更新，而是 PID 式反馈调节——
用"先验预测误差"驱动增益调整；检测到系统性错配（onset 精确触发，实测 0.013，零误报）时
触发退化策略：降级先验权重、回退扁平估计、记入 Claim Ledger。
这解决了 §1 标准部分池化"结构突变下静默失效"的痛点，是我们的差异化创新点之一。

## 4. 元分析汇总（跨期证据积累）

**理论来源**：DerSimonian & Laird (1986) 随机效应元分析——医学循证领域汇总多研究效应量的标准方法。

**借鉴**：经验库把历史多期实验的 ATT 用随机效应模型汇总为先验（`experience_store.py`），
实测冷启动场景 ATE 估计误差下降 10.9%（0.00451→0.00402，`outputs/experience_ablation.json`）。

## 5. Agent 编排模式选型

**理论来源**

- ReAct (Yao et al. 2023)：观察→推理→行动交替循环，适合探索式任务。
- Plan-and-Execute (Wang et al. 2023)：先出完整计划再逐步执行，计划本身可审计，企业/合规场景更优。
- Reflexion (Shinn et al. 2023)：跨尝试的语言化反思。

**选型理由**：金融归因要求每一步可追溯、每个结论有状态机记录，因此选 **Plan-and-Execute**：
意图识别 → 澄清 → 出示执行计划（含步骤与耗时）→ 用户确认 → 真实执行 → 交付报告指针
（`attribution/agent_chat.py`，证据 `outputs/chat_demo_evidence.json`）。
当前意图层为确定性规则（金融场景的可审计性优先，避免 LLM 意图解析引入不可复现性），
`_classify_intent` 预留 LLM 插拔点。

## 6. 因果推断开源生态对标

- DoWhy（Microsoft）：因果假设显式建模 + refutation 检验——我们的因果门禁（DESCRIPTIVE_ONLY / REFUSED）与之同思路，但面向 AB 实验场景做了轻量化。
- EconML / CausalML：异质效应（HTE）估计——我们的 `estimate_hte_nested` 做嵌套分组的 HTE。
  Student-t 随机效应目前只在 `estimate_hte` 中实现；50-seed 回放显示 plug-in-`tau` 会严重欠覆盖，
  因而它仅保留为实验路径，不替代生产默认的 Gaussian 路径。

**边界声明**：未直接使用上述库，原因是（a）依赖体积与本地化部署要求冲突；（b）它们不内置"证据不足即拒答"的门禁语义——这正是金融合规场景的核心要求。

## 7. AB 实验决策引擎对标

工业界 AB 平台（VWO、Statsig 的贝叶斯引擎）以"胜率"报告为主，通常不回答"为什么没变"。
本方案差异化在：AB 决策线（线 A）+ 基线归因线（线 B）双线闭环——
不仅判定实验输赢，还把"未注册变动 / 外部事件 / 未知残差"显式分桶，
unknown_label_honesty=1.0（绝不把未知伪装成已知），这是面向评审"诚实性"维度的核心设计。
