# 变更日志

## 2026-08-29 — 整改

### 1：修复候选级 rate/mix/interaction 重复计算 interaction

原实现使用：

```text
rate        = after_share × delta_rate
mix         = delta_share × before_rate
interaction = delta_share × delta_rate
```

由于 `after_share = before_share + delta_share`，原来的 rate 项已经包含一次 interaction，随后又单独加入 interaction，导致交互贡献被重复计算。

现在改为严格闭合的三项分解：

```text
rate        = before_share × delta_rate
mix         = delta_share × before_rate
interaction = delta_share × delta_rate
```

同时新增以下候选级输出字段，方便复核每个候选自身是否闭合：

- `treatment_share_before`：候选在基准窗口中的流量占比；
- `treatment_share_after`：候选在当前窗口中的流量占比；
- `candidate_contribution_change`：候选对总体 treatment rate 的加权贡献变化；
- `candidate_closure_error`：候选贡献变化减去 rate、mix、interaction 三项之和；合法输入下应接近 0；
- `decomposition_basis`：更新为正确的 `before_share × delta_rate` 定义。

行为变化：候选的 rate、mix、interaction 数值及依赖这些数值的 priority 排序可能与旧结果不同；旧版已生成的 RCA 输出不能与新版逐字段直接比较。

### 2：实现真正的 Student-t 随机效应分布

原来的 `likelihood="student_t"` 只会被写入 `likelihood_requested`，实际计算仍与 Gaussian 路径完全相同。现在 Student-t 已进入随机效应分布、`tau` 估计和分群后验计算。

Student-t 路径显式采用以下层次模型：

```text
y_i | theta_i ~ Normal(theta_i, se_i)
theta_i        ~ StudentT(nu, location=mu, scale=tau)
```

其中：

- `y_i` 是第 i 个 segment 的原始 treatment effect 后验均值；
- `se_i` 是该原始 effect 后验的标准误；
- `theta_i` 是第 i 个 segment 的潜在真实效应；
- `mu` 使用 pooled effect；
- `nu` 是 Student-t 自由度，必须为有限值且大于 2，默认值为 4；
- `tau` 是 Student-t 的 scale 参数，不是标准差；
- Student-t 随机效应标准差为 `tau × sqrt(nu / (nu - 2))`；
- 随机效应方差为 `tau² × nu / (nu - 2)`。

`tau` 现在有三种明确处理方式：

1. 调用方传入 `tau`：将其作为固定的 Student-t scale 使用，`tau_source="fixed"`；
2. 未传入 `tau`：通过经验贝叶斯边际似然数值积分估计，估计时包含 `tau=0` 的零异质性边界，`tau_source="empirical_bayes_marginal_likelihood"`；
3. 兼容旧参数 `shrinkage_strength`：先得到旧概率尺度方差，再根据 `nu` 换算为 Student-t scale，`tau_source="legacy_shrinkage_strength"`。

分群后验不再套用 Gaussian 的线性收缩公式，而是显式计算并归一化：

```text
p(theta_i | y_i) ∝ Normal(y_i | theta_i, se_i) × StudentT(theta_i | mu, tau, nu)
```

随后从该数值后验中抽样，计算 posterior mean、credible interval、实际伤害/收益概率和 moderation。重尾真值或极端 segment 因此会与 Gaussian 路径产生不同的收缩和区间。

新增或明确的输出包括：

- `random_effects_distribution`：实际使用的 `gaussian` 或 `student_t`；
- `random_effects_parameters`：显式记录 `location`、`nu`、`scale`、`tau`，并声明 `scale_equals_tau=true`；
- `tau_scale_probability_difference`：概率差尺度上的 `tau`；
- `tau_definition`：解释 Gaussian 与 Student-t 下 `tau` 的不同含义；
- `tau_source`：说明 `tau` 是固定值、边际似然估计值还是旧参数换算值；
- `random_effect_variance_probability_difference`：随机效应的实际方差；
- `student_t_nu`：Student-t 自由度；
- `posterior_calculation`：记录实际采用的后验计算方法。

兼容性和拒答规则：

- `likelihood` 仅接受 `gaussian` 或 `student_t`，其他值直接报错，不再静默忽略；
- `tau` 必须有限且非负；
- `tau` 与旧参数 `shrinkage_strength` 不能同时指定；
- `estimate_hte_nested` 当前只支持 Gaussian 随机效应。传入 Student-t 时会明确报错，并提示改用已经实现 Student-t 的 `estimate_hte`，避免再次出现“参数被接受但未进入计算”的情况。

### 3：修复 beam search 未按异常强度剪枝

原实现虽然计算了候选 metrics，但 `next_beam` 中只保存 scope；随后却尝试读取 scope 中不存在的 `gap_change`，导致所有候选的剪枝分数都退化为 0，实际结果依赖生成顺序。

现在：

- beam 节点同时保存 `scope` 和 `beam_score`；
- `beam_score` 明确定义为 `abs(gap_change)`；
- 每层扩展后按 `beam_score` 从高到低保留 `beam_width` 个候选；
- 输出候选中保留 `beam_score`，便于审计剪枝依据；
- dimensions、dimension values 和并列候选采用规范化排序，减少字段顺序、值顺序及输入行顺序对结果的影响。

行为变化：较小 `beam_width` 下，高异常强度交集会被继续搜索，不再因为字段排列顺序稳定漏检。测试中 `beam_width=1` 仍能找到演示数据中的真实三维异常 scope。

### 4：禁止截断因子设计，并升级组件效应分析

原实现当所需 arm 数超过 `max_arms` 时，直接保留设计矩阵前几行，并继续用 factor=1 与 factor=0 的边际 CTR 差估计组件效应。该截断可能破坏水平平衡、正交性和矩阵秩，使组件效应不可识别。

设计阶段现在改为：

- 不再生成带 `_truncated` 后缀的任意前缀设计；
- 当 `max_arms` 不能容纳完整设计或既定 fractional factorial 时直接抛出 `ValueError`；
- `max_arms` 必须为正数；
- 只有可完整执行的设计才会生成 arms。

新增 `design_diagnostics`，包括：

- `model_columns`：分析矩阵列；
- `rank` 与 `full_column_rank`：矩阵秩和是否满列秩；
- `factor_balance`：每个 factor 的 0/1 水平 arm 数；
- `factor_correlation_matrix`：因子列相关矩阵；
- `condition_number`：设计矩阵条件数；
- `main_effect_aliases`：完全相同或完全相反的主效应列。

组件分析也从边际均值差升级为使用完整设计矩阵的聚合 Binomial logistic GLM：

- 使用 `-1/+1` 编码和完整主效应设计矩阵；
- 通过 IRLS 拟合各 arm 的聚合 Binomial outcome；
- `component_effect` 改为模型调整后的平均概率差；
- 新增 `log_odds_ratio`、`standard_error_scale="log_odds_ratio"`、`analysis_model` 和 `design_matrix_rank`；
- 若设计矩阵降秩，或任何设计 arm 没有 outcome 数据，分析会直接拒绝，不再输出不可识别的组件效应。

### 5：按随机化单位处理重复观测与 cluster

- 主分析默认使用 `primary_estimand="user_level"`，将同一分析单位的重复曝光聚合后再计算 ITT；二元 `issued` 使用 `max`，金额 `net_premium` 使用 `sum`，也可通过 `outcome_aggregations` 显式配置。
- `primary_estimand="exposure_level"` 保留合格曝光并以曝光加权，但标准误按 `randomization_unit` 使用 CR1 cluster-robust sandwich 估计，不再把曝光行视为独立样本。
- `primary_estimand="triggered_user"` 只分析 triggered 用户并聚合到用户，同时明确标记为 post-assignment conditional estimand、`is_itt=false`。
- cluster-randomized 设计使用 `cluster_column` 作为推断 cluster；功效检查使用聚合后的分析单位数，并另行披露原始行数、重复观测数和排除数。
- 现有 Beta-Binomial 决策层只接受独立的 user-level 分析行；exposure-level 或仍有 cluster 相关性时拒绝输出损害/收益决策概率，保留 cluster-aware 频率学结果。
- 新增跨臂随机化单位拒答、用户聚合、曝光级 robust SE 和 triggered-user 口径测试。

### 验证

本次新增和扩展的回归测试覆盖：

- 100 组随机合法面板的 rate/mix/interaction property test，均在数值容差内闭合；
- 候选级 share、贡献变化和 closure error；
- Gaussian 与 Student-t 路径产生不同的后验收缩；
- 固定 `tau`、估计 `tau`、`nu` 敏感性和非法参数拒绝；
- beam search 对 dimensions 顺序和输入行顺序不敏感；
- 预算不足时拒绝截断因子设计；
- 合法设计的秩、平衡、相关和 alias 诊断；
- 完整设计矩阵 Binomial GLM 能识别真实组件效应并保持零效应接近 0。

最终验证结果：Ruff 静态检查通过，测试套件 12/12 通过。

## 2026-08-29 — Experiment Integrity Gate 升级

### 升级目的

此前的因果门禁主要检查实验元数据，例如 `assignment_method="randomized"`、`assignment_verified=true` 和可信 assignment provenance。元数据只能说明实验“计划如何随机”，不能证明实际进入分析的数据仍保持正确随机化。

本次增加基于实际行级数据的 `ExperimentIntegrityGate`。系统会先生成实验健康报告；SRM、基线平衡、稳定分流、跨臂污染、时间顺序、样本漏斗、cluster 完整性和并发实验八项检查必须全部通过，才能运行 ITT、Bayesian bundle decision 和 HTE。任一检查失败或缺少检查所需证据时均 fail closed，不输出因果估计。

### 新增的八项检查

1. **SRM（Sample Ratio Mismatch）**
   - 按 `expected_allocation` 比较实际 assignment arm 数；
   - 当前支持两臂实验，使用自由度为 1 的卡方检验；
   - 输出 observed counts、expected counts、卡方统计量、p-value 和 `srm_alpha`；
   - 出现未知 arm、缺少 assignment 字段或 p-value 低于阈值时失败。

2. **Treatment 前协变量平衡**
   - 基线协变量由 `baseline_covariates` 明确定义，避免误把 treatment 后变量用于平衡检查；
   - 数值变量计算 standardized mean difference，默认要求绝对值不超过 0.10；
   - 分类变量计算各类别占比的臂间差异，默认最大绝对差不超过 0.10；
   - 报告每个协变量的均值、SMD 或类别占比差，以及具体失败变量。

3. **稳定分流与重复入组**
   - 检查同一 randomization unit 是否在不同记录中被分到不同 arm；
   - 按 `assignment_period` 检查各时间桶的实际分流比例；
   - 同时使用配置容差和基于桶样本量的抽样误差容差，避免把合理随机波动误判为漂移；
   - 时间桶小于 `allocation_stability_min_period_size` 时拒绝评估，不会用极小样本宣布稳定。

4. **跨臂污染**
   - 分别读取 assigned arm 和实际 exposed arm；
   - 只在真实曝光记录中计算污染率；
   - 污染率超过 `max_contamination_rate`，或没有可验证曝光数据时失败。

5. **Assignment → exposure → outcome 时间顺序**
   - 支持数值时间和 ISO-8601 时间；
   - 每条记录必须满足 `assigned_at <= exposed_at <= outcome_observed_at`；
   - 无法解析时间或出现 outcome 早于 assignment/exposure 时失败。

6. **Assigned / exposed / triggered / outcome 样本漏斗**
   - 分 arm 输出 assigned、exposed、triggered 和 outcome observed 数；
   - 检查漏斗计数是否单调且不超过 assignment 样本；
   - 检查各 arm 的曝光率和结果观察率差异，防止差异流失造成选择偏差。

7. **Cluster 和分析单位完整性**
   - 检查同一 randomization unit 是否拥有多个 assignment；
   - cluster-randomized 实验额外检查同一 cluster 内 assignment 是否一致；
   - randomization unit 与 analysis unit 不一致时，必须声明分析已进行 cluster adjustment；
   - cluster 字段缺失、cluster 跨臂或分析未处理聚类时失败。

8. **并发实验冲突**
   - 从实际记录读取 `concurrent_experiment_ids`，而不是只相信实验配置；
   - 与 `compatible_concurrent_experiments` 白名单比较；
   - 发现未声明兼容的重叠实验时失败，并列出冲突实验 ID。

### 新的健康报告与门禁行为

`extract_features` 以及公开评估结果的顶层现在都新增 `experiment_integrity`，报告包括：

- `gate="EXPERIMENT_INTEGRITY_GATE"`；
- 总体 `status`、`passed` 和 `causal_estimators_allowed`；
- `failed_checks` 和结构化 `reason_codes`；
- 八项检查各自的 `PASS/FAIL` 状态、阈值、统计量和诊断明细。

`causal_readiness` 新增独立的 `experiment_integrity` gate，并把实际检查结果加入 design checks。元数据写着 randomized、assignment verified 或 provenance 可信，不再足以单独获得 `CAUSAL_READY`。

公开估计链路改为：

```text
行级实验数据
  → Experiment Integrity Report
  → 全部八项 PASS
  → Causal Readiness 其他门禁
  → ITT
  → Bayesian bundle decision
  → 可选 HTE
```

- `estimate_itt` 现在必须接收通过的完整 Integrity Report；没有报告、报告失败或报告缺少任一检查都会抛出 `PermissionError`；
- `evaluate_public_dataset` 只在 Integrity Gate 和其余因果门禁全部通过后调用 ITT；
- `evaluate_with_bayes` 在运行 Beta-Binomial bundle 和 HTE 前再次验证同一报告；
- 门禁失败时 `bayes_layer.status="REFUSED"`，且不会生成 `bundle_decision` 或 `hte`；
- 底层 Bayesian 数学函数仍可用于明确标注为非因果的仿真和校准，但系统公开实验评估入口不能绕过 Integrity Gate。

### Fixture 和验证变化

- 随机实验 fixture 增加 assigned/exposed arm、曝光状态、trigger 状态、结果观察状态、三个时间点、assignment period 和并发实验 ID；
- 案例 C 改用两人一组的随机区组分配，在维持随机性的同时保证预定 50/50 allocation；
- 控制平面注册新的 `ExperimentIntegrityGate` skill；
- 新增逐项故障注入测试，分别验证 SRM、失衡、分流漂移、污染、时间倒置、差异流失、cluster 错配和并发实验冲突都会阻断总体门禁；
- 新增缺失检查证据时 fail-closed、ITT 不能绕过，以及 ITT/Bayesian bundle/HTE 共用同一门禁的集成测试。

升级后的最终验证结果：Ruff 静态检查通过，完整测试套件 17/17 通过。

## 2026-08-29 — 功效规划与 统计输入契约升级

### 1：功效计算不再固定使用 1.96 和 0.84

原功效筛查无论配置何种 `alpha` 和 `target_power`，都会固定使用 `z_alpha=1.96`、`z_power=0.84`。这会使非默认显著性水平或目标功效的样本量结论失真。

现在使用 Python 标准库的正态分布逆 CDF，根据实际配置计算：

```text
z_alpha = Phi^-1(1 - alpha_tail)
z_power = Phi^-1(target_power)
```

其中 superiority 双侧检验使用 `alpha_tail=alpha/2`，单侧检验及 noninferiority/equivalence 的单侧组成检验使用 `alpha_tail=alpha`。输出新增实际使用的 `z_alpha` 和 `z_power`，便于审计。

#### 明确 MDE 的尺度

功效配置现在必须提供 `minimum_detectable_effect_type`：

- `absolute`：MDE 是概率的绝对百分点差；
- `relative`：MDE 是相对基准率的变化，系统换算为 `baseline_rate × MDE`。

缺少该字段或传入其他值会直接拒绝，不再默认猜测。输出同时记录原始 MDE、MDE 类型、换算后的 `absolute_effect_distance` 和相对零假设边界的实际距离。

#### 支持不等分流

从 `expected_allocation` 读取 control/treatment 目标比例，并使用一般化的两臂方差项：

```text
variance × (1 / allocation_control + 1 / allocation_treatment)
```

因此 70/30 等不等分流不会再套用 50/50 样本量公式。输出新增归一化 allocation、各 arm 所需样本量和实际样本量。

#### 支持 cluster design effect

当 `assignment_method="cluster_randomized"` 时，必须同时提供：

- `cluster_average_size`；
- `intracluster_correlation`。

系统使用：

```text
design_effect = 1 + (cluster_average_size - 1) × ICC
```

对所需样本量进行膨胀。cluster 配置缺失、平均 cluster size 小于 1、ICC 不在 `[0,1)` 时明确拒绝。

#### 支持预期流失

`expected_attrition_rate` 可配置为所有 arm 共用的单个值，也可以按 `{"0": ..., "1": ...}` 分 arm 设置。所需 assignment 样本量按各 arm 的 retention rate 分别膨胀：

```text
required_assigned = required_analyzable × design_effect / (1 - attrition)
```

流失率必须有限且位于 `[0,1)`。

#### 支持 superiority、noninferiority 和 equivalence

新增 `power_design`：

- `superiority`：使用 MDE 作为待检出的效应距离；
- `noninferiority`：使用 `margin + assumed_effect_absolute` 作为距非劣界的距离；
- `equivalence`：按 TOST 的单侧组成检验，使用 `margin - abs(assumed_effect_absolute)` 作为距最近等价界的距离。

noninferiority 和 equivalence 必须声明 `test_sidedness="one_sided"`。假定效应落在不可识别边界外、未知设计类型、非法 alpha/power 或其他未实现配置都会抛出明确错误，不会退回默认 superiority 公式。

在完整公开评估链路中，这些配置错误会被转换为 `status="REFUSED_INVALID_CONFIGURATION"` 和 `reason_code="POWER_CONFIGURATION_INVALID"`，使因果门禁降级而不是令服务返回一份使用默认公式的结果；底层功效函数直接调用时仍会抛出具体异常，便于开发和测试定位配置错误。

功效输出还新增：

- `required_analyzable_total_before_inflation`；
- `required_assigned_by_arm`；
- `actual_by_arm`；
- `cluster_design_effect`；
- `expected_attrition_rate`；
- `used_sample_count`、`excluded_sample_count` 和 `exclusion_reasons`。

### 2：新增统一统计输入有效性契约

新增 `attribution/input_validation.py`，主要统计入口在计算前统一执行 fail-fast 校验。关键条件不成立时直接拒绝统计计算，不再产生外观正常但语义错误的结果。

#### Bayesian bundle 和 HTE

- clicks、impressions 必须是有限、非负、整数值计数，并满足 `clicks <= impressions`；
- prior 参数必须有限且为正；
- practical/moderation threshold 必须有限且非负；
- posterior draws 必须为正整数；
- HTE 的 `segment_id` 必须非空且唯一；
- 每个 segment 必须同时具有合法的 control/treatment 计数。

成功输出新增 `input_validation`，报告实际使用样本、排除样本、排除原因及执行的检查。当前这些入口遇到非法输入直接拒绝，因此成功结果的排除数为 0。

#### Rate-aware RCA

- baseline/current 窗口必须各自合法、严格按时间排列且不重叠；
- day/cell 组合必须唯一；
- control/treatment 计数必须有限且合法；
- baseline 与 current 必须具有相同的 cell universe；
- dimensions 必须非空且唯一；
- `top_k`、`beam_width` 必须为正，`min_impressions` 必须非负。

重复 day/cell、窗口重叠或 cell 在某一窗口消失时现在直接报错，不再依赖后续 closure error 间接暴露数据问题。

#### 时间序列、discovery/holdout 和因子输入

- days 与所有统计序列必须等长、有限、唯一、整数值并严格递增；
- discovery 和 holdout 必须属于总体 days、互不重叠，且 holdout 必须严格晚于 discovery；
- anomaly windows 必须按时间排序、不重叠、start/end 合法且位于总体时间范围内；
- factor series 的 factor/scope 组合必须唯一，days/values 必须等长且合法；
- factor snapshots 的 factor/scope/day 组合必须唯一；
- event factor ID 必须非空且唯一，event window 不允许反向；
- block length、bootstrap reps 和 max lag 必须处于支持范围。

#### Baseline attribution 和实验汇总

- days、control、treated 必须等长、有限且严格按时间排序；
- 每个实验 ATT estimate 必须有限，`att_se` 必须有限且严格大于 0；
- change ID、external event ID 必须唯一；
- registry 的时间点和窗口必须包含在分析 days 中；
- change 引用的 experiment ID 必须真实存在。

#### 其他统计入口

- BH/FDR 的 p-value 必须有限且位于 `[0,1]`，不再用 `clip` 静默修正非法概率；
- calibration 的 predicted/realized 必须有限且位于 `[0,1]`；
- temporal null 要求输入数组一维、等长、非空、有限，null replicate 数量一致；
- 因子实验要求 factor ID 唯一、预算为正整数、outcome 严格为二元 0/1。

### 验证

新增测试覆盖：

- 非默认 alpha=0.01、power=0.90 使用正确正态分位数；
- 相对 MDE、不等分流、cluster design effect 和分 arm 流失；
- noninferiority/equivalence 边界公式；
- 未知设计、含糊 MDE、非法流失和缺失 cluster 参数的明确拒绝；
- NaN、Inf、负数、clicks 超过 impressions 和重复 segment；
- 重叠窗口、重复 day/cell、cell universe 漂移；
- 反向 discovery/holdout、未排序时间、非有限序列；
- 非正 experiment SE 和序列不等长；
- 非法 p-value 与 calibration 概率不再被静默裁剪；
- 成功输出包含使用/排除样本报告。

升级后完整测试套件为 27/27 通过。

### 证据文件同步回放

修复完成后重新运行了标准证据链和统计消融，并刷新 `outputs/` 中受影响的 JSON。回放同时纠正了两项旧证据口径：

- `nu_annealing_sweep.json` 中 50–2000 的参数实际是旧版 pseudo-impression `shrinkage_strength`，不是 Student-t 自由度 `nu`；输出字段和说明已经更名；
- 旧版 `nested_ablation_50seeds.json` 所称的 Student-t coverage 只是给 Gaussian 区间换用 t 临界值，并未运行 Student-t 随机效应；新版改为比较两种真实后验。

50-seed 回放得到 Gaussian coverage `0.8775`、真实 Student-t（`nu=5`、plug-in empirical-Bayes `tau`）coverage `0.3075`。这是必须保留的负结果：当前 Student-t 已经真实进入计算，但 plug-in `tau` 造成明显欠覆盖，不能据此宣称校准改善，也不能将其设为生产默认。后续需要联合传播 `mu`、`tau` 和 `nu` 的不确定性，并在 Gaussian 真值、重尾真值、零异质性和混合异常真值下重新校准。
