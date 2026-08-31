# 变更日志

## 2026-08-30 — P0 因果门禁与 Line B 归因修复

### 修复范围

本次修改覆盖因果就绪门禁、Line B 外部冲击归因、实验完整性检查、聊天确认、演示页 API、场景报告和文档。除最初确认的 4 个 P0 外，最终审查继续修复了完整性门禁空值/类型绕过、基线平衡重复行加权、完整性报告跨数据复用、评委页面失效入口和根 CLI 占位入口，并加入回归测试。

### 1. 必要结果字段为 `NULL` 时错误通过 `CAUSAL_READY`

**原问题：** 门禁只检查必要列是否存在，没有把必要结果字段中的空值纳入 `data_missing`。因此，列存在但部分出单或保费结果为 `NULL` 时，仍可能输出因果估计。

**修复：**

- `causal_readiness` 同时检查必要列的存在性和非空数量。
- 任一必要结果字段存在空值时，将对应的 `non_null_<field>` 检查加入 `data_missing`。
- 门禁按 fail-closed 处理：返回 `DATA_INSUFFICIENT`，不再生成因果估计。

**修改文件：** `runtime/analysis.py`、`tests/test_regressions.py`。

### 2. Line B 对共同外部冲击进行了二次扣减

**原问题：** 处理组和对照组共同经历的冲击已经通过 `treated-control` 差分消除，旧实现又从差分残差中减去一次 control 侧冲击，可能人为放大、缩小甚至反转归因结果。

**修复：**

- 共同外部事件只作为 `TEMPORAL_ASSOCIATION` 展示，不自动分配为处理-对照 gap 的贡献。
- 新增 `external_control_deviation`，用于描述 control 序列在事件附近的偏离，但不把它解释为差分效应。
- 无法识别组间差异暴露时，事件的 `gap_contribution` 为 `null`，allocation policy 明确标记为不分配。
- 删除语义已经失效的旧字段 `external_explained`，避免下游把全零占位值误解为外部事件不存在；外部事件观测统一读取 `external_control_deviation`。

**行为变化：** Line B 的归因残差保持为处理组与对照组的差异。共同冲击可以作为解释上下文，但只有在未来存在可识别的组间差异暴露时，才能进入 gap allocation。

**修改文件：** `attribution/baseline_attribution.py`、`tests/test_regressions.py`、`README.md`、`README.zh-CN.md`、`docs/methodology.md`。

### 3. SRM 与分配稳定性按明细行而不是随机化单位计算

**原问题：** 旧实现直接统计数据行数。同一客户、代理人或门店产生不同数量的曝光行时，高频单位会被重复计数。例如两组各有 90 个客户，但 A 组每位客户有 10 行、B 组每位客户只有 1 行，按行会错误得到 900:90，并触发虚假 SRM。分配稳定性也会把重复观测误当成新分配。

**修复：**

- SRM 改为按 `randomization_unit` 去重后统计分组数量。
- 分配稳定性改为按“分配周期 + 随机化单位”去重后统计。
- 同一随机化单位落入多个处理组时，显式报告分配不一致并使完整性检查失败。
- 同一随机化单位跨越多个分配周期时，显式报告周期不一致。
- 诊断新增 `counting_unit`、`raw_row_count` 和 `randomization_unit_count`，可直接核对明细行数与真实随机化单位数。

**修改文件：** `runtime/experiment_integrity.py`、`tests/test_regressions.py`、`README.md`、`README.zh-CN.md`。

### 4. 否定表达可能被误判为确认并执行

**原问题：** 旧逻辑使用子串匹配，所以“`不好`”包含“`好`”、“`not ok`”包含“`ok`”，都可能触发已规划分析。

**修复：**

- 输入先进行 Unicode NFKC 规范化、大小写折叠和首尾标点清理。
- 规范化后的整条指令必须与允许词完全相等，不再使用子串匹配。
- 当前允许的完整确认指令为：`确认`、`执行`、`好`、`好的`、`可以`、`run`、`yes`、`ok`。
- “`不好`”、“`不执行`”、“`not ok`”等表达不会触发执行；`OK！` 等规范化后完全匹配的指令仍能确认。

**修改文件：** `attribution/agent_chat.py`、`tests/test_regressions.py`。

### 5. Web 演示页、场景目录与体验场景 schema 不一致

**原问题：**

- Web 演示页仍调用废弃的 `/api/track2/chat` 和 `/api/track2/scenario-run`。
- 前端缺少 `EXPERIENCE_ABLATION` 场景映射。
- 聊天场景目录把场景数硬编码为 5，但实际已有 6 个场景。
- 体验场景报告仍读取旧字段 `nu_trajectory`，与当前产物中的 `shrinkage_strength_trajectory` 不一致。
- 文档中的场景耗时与当前实测不一致。

**修复：**

- 演示页统一改用 `/api/attribution/chat` 和 `/api/attribution/scenario-run`。
- 补充体验消融场景的前端映射和意图提示。
- 场景数量改为根据 `SCENARIOS` 动态生成。
- 体验报告改为读取和返回 `shrinkage_strength_trajectory`。
- 按真实运行更新耗时：完整审查约 10 秒、Line A 约 2 秒、Line B 约 8 秒、外部证据和贝叶斯案例小于 1 秒、体验消融约 20–30 秒。

**修改文件：** `web/static/semifinal-demo.html`、`attribution/agent_chat.py`、`attribution/scenario_reports.py`、`tests/test_regressions.py`、`README.md`、`README.zh-CN.md`。

### 6. Line B 合并告警的数值字段不一致

**原问题：** 合并相邻告警时，`step_score` 会被取整，但 `absolute_step` 没有同步。同一个告警对象中的有符号值与绝对值可能互相矛盾，影响 UI 展示和下游排序。

**修复：** 合并后统一更新 `step_score`，并由最终值重新计算 `absolute_step`。

**修改文件：** `attribution/baseline_attribution.py`、`tests/test_regressions.py`。

### 7. 文档职责与数字同步

- `README.md` 和 `README.zh-CN.md` 只描述当前可运行功能、API、统计口径、输出字段和可复现实测结果；同步了 Line B 外部事件语义、随机化单位口径、告警日期、六个场景和运行时间。
- `docs/methodology.md` 只定义方法目标、评价指标、输出语义和限制；明确 Line B 的逐实验 RMSE 是精度指标，而效应总和只是当次样本的汇总展示值。
- 删除方法文档中类似评语或宣传语的表述，避免把单次 demo 数字写成普遍方法结论；同时删除不存在的 `outputs/chat_demo_evidence.json` 引用。
- 审计发现、修复历史、兼容性变化和验证证据集中记录在本 CHANGELOG。

### 8. 完整性检查对空值和伪布尔值 fail-open

**原问题：** 完整性检查只确认某个字段曾在任意一行出现，没有逐行检查关键值。基线协变量、分配周期或随机化单位为 `NULL` 时可能被字符串化后参与计算；`"false"`、`"yes"` 等字符串又会被 Python 的 `bool()` 当成真值，导致漏斗或污染检查错误通过。

**修复：**

- SRM、基线平衡、分配稳定性和 cluster integrity 对随机化单位、处理组、周期及所需协变量逐行执行非空检查。
- contamination 和 sample funnel 只接受布尔值或数值 `0/1`；空值、字符串布尔和其他数值均返回 `NOT_EVALUABLE` 并阻断因果估计。
- 诊断输出增加 `missing_value_counts` 和 `invalid_binary_value_counts`，可以定位具体字段及坏值数量。

**修改文件：** `runtime/experiment_integrity.py`、`tests/test_regressions.py`。

### 9. 基线平衡被重复明细行改变

**原问题：** SRM 和稳定性已改为按随机化单位，但 pre-treatment balance 仍按明细行计算。同一客户产生更多曝光行时，其基线特征会被重复加权，可能凭空制造或掩盖组间不平衡。

**修复：**

- 基线平衡改为每个 `randomization_unit` 只贡献一条记录。
- 同一随机化单位若跨处理组，或重复行中的任一基线协变量不一致，门禁显式失败，不再任取一行。
- 平衡诊断增加 `counting_unit`、`raw_row_count` 和 `randomization_unit_count`。

**修改文件：** `runtime/experiment_integrity.py`、`tests/test_regressions.py`。

### 10. 通过的完整性报告可被复用于另一批数据

**原问题：** `estimate_itt` 只检查报告状态为 PASS，没有证明报告就是由当前待估计数据和契约生成。调用方可以把一份干净实验的 PASS 报告传给另一批数据，从而绕过门禁。

**修复：**

- 完整性报告写入 rows、metric contract 和 experiment metadata 的 SHA-256 指纹；行指纹对输入顺序不敏感，但保留重复行数量。
- `estimate_itt` 在估计前核对当前 rows；调用方提供契约或元数据时同时核对对应指纹。
- Bayesian bridge 也在进入后验决策前核对三类输入；任一不匹配均抛出 `PermissionError`，不输出估计。

**修改文件：** `runtime/experiment_integrity.py`、`runtime/analysis.py`、`runtime/bayes_bridge.py`、`runtime/cases.py`、`tests/test_regressions.py`。

### 11. 评委页面与实际仓库脱节，根入口仍为 Hello

**原问题：** 演示页包含开发者绝对路径、旧包名 `track2_v5`、不存在的 ZIP/图片/测试文件和 404 链接，且展示的测试数、Python 版本、候选数、外部映射率和告警日期已经过期；仓库根 `main.py` 仍只打印 Hello。

**修复：**

- 启动命令改为仓库根目录可直接运行的 `python3 run_server.py 8765`，证据链接改为当前 Attribution API。
- 页面代码树、命令、测试文件、Python 版本和 fallback 数字与当前仓库及真实场景报告同步；删除不存在的 ZIP/benchmark 图片链接。
- 当前聊天意图能力明确描述为确定性规则，并保留可选本地模型 adapter 的边界，避免把 adapter 演示写成默认在线能力。
- `main.py` 改为真正转发到 runtime CLI；中文 README 的 Line A 实测耗时同步为约 2 秒。

**修改文件：** `web/static/semifinal-demo.html`、`main.py`、`README.zh-CN.md`、`docs/完整方法与统计讲解.md`、`tests/test_regressions.py`。

### 文件级变更清单

| 文件 | 具体变化 |
|---|---|
| `runtime/analysis.py` | 必要结果字段空值进入因果就绪门禁；缺失时 fail closed。 |
| `runtime/experiment_integrity.py` | SRM 和稳定性按随机化单位计算；增加跨组、跨周期检查及计数诊断。 |
| `runtime/bayes_bridge.py` | 贝叶斯决策前校验完整性报告与当前数据、契约、元数据的输入指纹。 |
| `runtime/cases.py` | 内置案例估计显式传入当前 metric contract 和 experiment metadata，执行完整指纹校验。 |
| `attribution/baseline_attribution.py` | 移除共同冲击的二次扣减；增加外部 control 偏离字段；同步告警绝对值。 |
| `attribution/agent_chat.py` | 确认指令改为规范化后的完整匹配；场景数动态生成。 |
| `attribution/scenario_reports.py` | 体验场景切换到当前 trajectory schema；更新运行耗时。 |
| `web/static/semifinal-demo.html` | 更新 Attribution API 路径；补齐体验消融场景映射。 |
| `tests/test_regressions.py` | 增加 NULL 门禁、共同冲击、unit-level SRM、精确确认、告警一致性、前端 API 和体验 schema 测试。 |
| `README.md` | 同步英文功能说明、API、统计口径、场景输出和实测数字。 |
| `README.zh-CN.md` | 同步中文功能说明、API、统计口径、场景输出和实测数字。 |
| `docs/methodology.md` | 重构方法定义与指标边界，移除评语式表述和失效引用。 |
| `CHANGELOG.md` | 记录问题原因、修复方式、文件影响、兼容性和验证结果。 |
 |
|  |

### 输出与兼容性变化

- Line B 新增 `external_control_deviation`；无法识别差异外部贡献时，事件的 `gap_contribution` 为 `null`。
- Line B 删除旧字段 `external_explained`；外部事件观测统一由 `external_control_deviation` 表达。
- 实验完整性诊断新增 `counting_unit`、`raw_row_count`、`randomization_unit_count`。
- 完整性报告新增 `input_fingerprints`，旧的无指纹 PASS 报告不能再授权新的因果估计。
- 基线平衡也按随机化单位计数；关键空值和非 `0/1` 布尔字段会使完整性检查 fail closed。
- 体验场景统一使用 `shrinkage_strength_trajectory`，不再读取旧名称 `nu_trajectory`。
- 因果门禁比旧版更严格：必要结果字段存在空值的数据会由可分析变为 `DATA_INSUFFICIENT`。这是预期的安全性变化。

### 验证结果

- `python -m unittest discover -s tests -v`：24/24 项通过。
- `uv run --frozen ruff check .`：通过。
- `ruff format --check`：54 个文件通过。
- Python `compileall`：通过。
- 6 个内置场景均完成真实运行，没有使用 mock fallback。
- 3 个种子、9 个治理案例通过：门禁准确率 1.0、错误因果输出率 0、拒绝召回率 1.0。
- README 指标交叉检查、HTTP 健康及场景接口 smoke test、JSON 非有限数检查均通过。
- Line B 实测复现当前文档数字：naive RMSE 约 10.233，hierarchical RMSE 约 5.552；效应总和分别约 116.37 和 119.35。这些是不同评价量，不再把效应总和包装成“总量守恒误差”。

### 当前边界

- Student-t 路径仍是实验性能力：即使校准覆盖通过，生产效用门禁未通过时也不会标记为 production eligible。
- 本地 demo server 和静态演示页用于验证与展示，不等同于生产部署配置。

## 两日改动的项目综合影响（2026-08-29—2026-08-30）

### 总体判断

8 月 29 日和 8 月 30 日的改动共同把项目从“统计方法演示原型”推进为“具有明确输入契约、因果门禁、证据链、拒答机制和可复现校准基准的本地验证系统”。改动的主要价值不是让所有评测数字单向上升，而是同时提高了四类质量：

1. **统计正确性**：修复错误分解、伪 Student-t、无效因子设计、错误功效公式和重复观测独立性假设等会直接改变结论的问题。
2. **因果安全性**：从只相信实验元数据升级为检查真实行级随机化证据，八项完整性检查全部通过后才允许因果估计。
3  **结果诚实性**：过期或偏乐观的文档数据被实际回放结果替换；Student-t 即使覆盖率修复，也因效用门槛失败而继续保持实验状态。

因此，项目整体是**明显变得更可靠、更保守、更可验证**，但还没有达到可直接公网部署或自动执行生产决策的成熟度。

### 全部改动对项目本身的影响

| 改动领域 | 8 月 29—30 日的关键变化 | 对项目的实际影响 |
|---|---|---|
| Rate/mix/interaction | 修正 interaction 被重复计入的问题，增加候选级 closure 字段 | 描述性贡献现在严格闭合，避免候选优先级被错误贡献值扭曲；旧 RCA 输出不能与新版逐字段直接比较。 |
| Student-t 模型 | 从“参数被记录但计算仍是 Gaussian”，升级到真实 Student-t，再从 plug-in `tau` 升级为联合传播 `mu/tau/nu` | 模型语义与输出一致，严重欠覆盖得到修复；计算成本和模型复杂度增加，且重叠 segment 的协方差问题仍未解决。 |
| Beam search | 从按字段生成顺序剪枝改为按 `abs(gap_change)` 剪枝 | 小 beam width 下不再稳定漏掉高异常交叉 scope，候选搜索更接近算法声明。 |
| 因子实验设计 | 禁止截断设计，增加秩、平衡、alias、条件数诊断；组件效应改用完整设计矩阵 GLM | 系统宁可拒答，也不再输出不可识别的组件因果效应；arm 预算不足时的行为由“给出可能错误的数”变为明确失败。 |
| 重复观测与 cluster | 支持 user-level、exposure-level、triggered-user 和 cluster-randomized 口径，exposure-level 使用 CR1 robust SE | 推断单位和估计目标更加明确，降低把重复曝光当独立样本造成的虚假精度；部分旧调用方需要补充 estimand/cluster 配置。 |
| Experiment Integrity Gate | 新增 SRM、平衡、稳定分流、污染、时间顺序、漏斗、cluster、并发实验八项检查 | 随机化元数据不再足以授权因果估计，系统的错误因果断言风险显著下降；数据要求更严格，更多不完整实验会被拒答。 |
| 功效规划 | 使用实际 alpha/power 分位数，支持 absolute/relative MDE、不等分流、cluster effect、流失、NI/equivalence | 样本量结论不再只对默认 50/50 superiority 场景有效；非法或含糊配置会 fail closed，而不是静默套用默认公式。 |
| 统一输入契约 | 对计数、概率、时间窗、segment ID、实验 SE、FDR、校准输入等统一执行 finite/range/uniqueness 校验 | NaN、Inf、重复行、窗口重叠、非法概率等问题会在统计计算前暴露，减少“格式正常但语义错误”的 outputs。 |
| 测试与文档 | 保留 14 项快速回归测试，Ruff/format/compile 通过；README、方法文档和 CHANGELOG 与实跑数据同步 | 代码变更有最低回归防线，评审看到的指标与 outputs 一致；尚缺 CI、property tests、并发测试和跨平台构建验证。 |

### 兼容性与运行成本影响

- `likelihood="student_t"` 且不固定 `tau` 时，默认行为已从 plug-in empirical Bayes 改为联合网格混合后验；需要复现旧结果时必须显式传入 `student_t_hyperparameter_method="plug_in"`。
- `max_arms` 不足时不再返回截断设计，而是抛出明确错误；这是有意的 fail-closed 兼容性变化。
- 功效配置现在要求明确 `minimum_detectable_effect_type`，cluster 和流失场景也必须提供完整参数；旧的含糊配置可能被拒绝。
- 输出新增 input validation、design diagnostics、integrity report、Student-t hyperparameter posterior 和 release gate 字段，下游消费者应按 schema/version 读取，不应假定旧字段全集固定不变。
- 联合 Student-t 的计算明显重于 plug-in 路径：四真值族 200 数据集基准约 63.5 秒，50-seed 仓库回放约 91.8 秒。它适合离线校准和实验验证，不适合在当前同步 HTTP 请求线程中高并发运行。

### 数据综合分析

#### 1. 因果治理与拒答表现稳定

- A/B/C 三类案例分别稳定为 `DESCRIPTIVE_ONLY`、`DATA_INSUFFICIENT`、`CAUSAL_READY`。
- 3 seeds × 3 families 的 9 个治理案例中，causal gate accuracy 为 `1.00`，false causal assertion rate 为 `0.00`，refusal recall 为 `1.00`。
- 这说明新增完整性门禁没有破坏合法随机实验的通过能力，同时能继续阻断观察性数据和缺失实验元数据的场景。

#### 2. Line A 主决策能力强，但因子恢复不是满分

- matched 5 seeds：Recall@5 `1.00`、ATE RMSE `0.001`、95% coverage `1.00`、decision accuracy `1.00`、HTE direction accuracy `1.00`。
- matched factor recovery 为 `0.90`，mismatched 为 `0.75`，错配后下降约 `16.7%`。
- mismatched Brier 为 `0.0445`，接近对应 Bernoulli variance floor `0.0437`；说明概率预测没有明显失控，但开放因子恢复能力对结构错配仍然敏感。
- 结论：Line A 的 bundle 决策和方向判断已经稳定，下一步瓶颈是错配环境下的候选恢复，而不是主 ATE 估计。

#### 3. Line B 的层级汇总有效，但不应掩盖 unknown

- 未注册变化召回、外部事件对齐、unknown honesty 均为 `1.00`。
- per-experiment ATT RMSE 从 naive `10.233` 降到 hierarchical `5.552`，下降约 `45.7%`。
- 外部事件映射率为 `0.500`：4 个异常只映射 2 个，但两个真值事件全部召回，未注册变化没有被错挂。
- 结论：较低 mapping coverage 不是单纯失败，而是“证据不足时保持 UNEXPLAINED”策略的结果；系统没有为了提高覆盖率而强行归因。

#### 4. Experience store 对冷启动有帮助，但 rich-period 并非全面改善

- sparse-period ATE RMSE 从 `0.004509` 降到 `0.004019`，改善约 `10.9%`。
- rich-period ATE RMSE 从 `0.000491` 上升到 `0.000642`，恶化约 `30.8%`，绝对误差仍很小。
- mismatch alarm 在首个错配 seed `601` 触发，后续 seed `701` 因经验库已适应而不重复报警，符合当前 onset alarm 语义。
- 结论：经验库的主要价值是冷启动和错配 onset 检测，不能概括为所有流量阶段都降低 RMSE。

#### 5. Nested pooling 提高方向召回，但存在误差代价

- nested direction recall 为 `0.18`，flat 为 `0.02`，方向召回提高到 9 倍。
- nested moderation RMSE 为 `0.004296`，flat 为 `0.002835`，反而高约 `51.5%`。
- 校准 ECE 从 `0.06257` 降到 `0.03900`，改善约 `37.7%`；但 small-sample decision accuracy 只有 `0.52`。
- 结论：nested pooling 更容易发现真实方向，但点估计误差和小样本决策能力仍不足，适合作为探索性层而不是自动决策层。

#### 6. Student-t 的覆盖率缺陷已修复，但效用没有同步提升

- 四真值族 4 × 50 seeds：joint coverage `0.9383`，plug-in `0.5588`，Gaussian `0.8963`；最低单族覆盖率 `0.9100`。
- joint RMSE `0.006076`，Gaussian `0.006188`，改善约 `1.8%`。
- joint false-harm rate `0.0108`，Gaussian `0.0208`，下降约 `48%`。
- joint mean interval width `0.024862`，Gaussian `0.022167`，只增加约 `12.2%`，覆盖率改善不是靠无限放宽区间获得。
- 50-seed 仓库回放中，coverage 从 plug-in `0.3075` 提升到 joint `0.9475`，进入预设 `0.93–0.97` 区间。
- 但 joint direction recall 为 `0.00`，低于 Gaussian `0.02`；moderation RMSE `0.003976`，高于 Gaussian `0.002835`。平均 `P(tau=0)` 为 `0.231`，后验平均 `nu≈10.03`，说明这些回放数据并不持续支持强重尾异质性。
- 结论：Student-t 已从“错误的过度自信”变为“校准但偏保守”，校准门槛通过、效用门槛失败，保持 experimental 是正确决策。

#### 7. 数据与 Evidence Pack 本身正常，但真实业务外推有限

- 当前 12 个 outputs JSON 均可解析，无 `NaN`/`Infinity`；4 个 Evidence Pack 的 digest 全部重算匹配；SQLite integrity 为 `ok`。
- UCI Bank Marketing 数据为 45,211 行、17 列，无空单元格和完全重复行，SHA-256 与 catalog pin 一致。
- UCI 数据不是随机实验，且 `duration` 是结果后变量；系统正确拒绝将其用于呼叫前因果决策。
- 结论：文件和证据完整性正常，但 UCI 属于银行营销观察性数据，只能验证 schema、泄漏防护和拒答机制，不能证明保险业务中的实际因果效果。

### 两日改动后的项目定位

项目当前可以可靠支持：本地离线演示、合成真值回放、随机实验完整性审查、因果就绪度分级、候选发现、保守拒答和 Evidence Pack 生成.


## 2026-08-30 — Student-t 联合后验校准与仓库审计

- 将 Student-t 默认实验路径从固定 `mu/nu`、plug-in empirical-Bayes `tau` 改为 `mu/tau/nu` 联合离散后验。
- `tau` 先验显式包含 10% 的零异质性质量点和 weakly informative half-normal 非零部分。
- 使用确定性网格积分计算超参数后验，并通过分层重采样压缩混合分量；区间保留后验尾部，不再使用 top-k 截断。
- 旧 plug-in 路径通过 `student_t_hyperparameter_method="plug_in"` 保留，仅用于回放对照。
- 新增四真值族校准基准：Gaussian、Student-t、零异质性和混合异常，共 4 × 50 seeds。
- 四真值族总体覆盖率从 plug-in 的 `0.5588` 提升到联合后验的 `0.9383`，最低单族覆盖率 `0.9100`；Gaussian 基线为 `0.8963`。
- 原 50-seed 仓库回放中，Student-t 覆盖率从 `0.3075` 提升到 `0.9475`，Gaussian 为 `0.8775`。
- 效用门槛仍失败：联合 Student-t 方向召回 `0.00`（Gaussian `0.02`），moderation RMSE `0.00398`（Gaussian `0.00284`），因此继续保持实验状态，Gaussian 仍为生产默认。
- 联合超参数似然显式披露 segment 条件独立假设；重叠 segment 在实现 covariance-aware likelihood 前仅用于验证压力测试，不获得生产授权。
- 回归测试扩展为 14 项，新增联合后验生成与非法 `nu_grid` 拒答测试。

### 仓库审计与 outputs 分析报告（2026-08-30）

#### 结论

仓库的演示与离线验证链路可运行，核心因果治理逻辑在现有 fixture 上表现正确，没有发现会把观察性数据直接升级为因果结论的致命错误。A/B/C 三类场景稳定输出 `DESCRIPTIVE_ONLY`、`DATA_INSUFFICIENT`、`CAUSAL_READY`，3-seed/9-case 治理基准的门禁准确率为 1.00、错误因果断言率为 0、拒答召回为 1.00。

本次发现并修复了两个真实系统缺陷：HTTP 非法参数导致连接被异常断开，以及无请求体上限导致工作线程可被超大 `Content-Length` 占用。证据文件写入也已改为原子替换，降低并发时产生截断 JSON 的风险。

当前版本适合作为本地方法验证和演示原型，但不应直接作为公网或生产服务部署。Student-t 的欠覆盖已通过联合传播 `mu/tau/nu` 修复到目标范围，但方向召回和 moderation RMSE 尚未通过效用门槛；其余主要生产阻断项是审计证据仍使用固定任务 ID 覆盖历史版本，以及服务缺少生产认证、限流和任务队列。

#### 审计范围与方法

- 盘点 49 个 Python 文件、约 14,000 行代码，以及配置、规格、双语 README、方法文档和静态前端。
- 执行 Ruff lint/format、全量 Python 编译和 14 项回归测试。
- 运行 Line A、Line B、外部事件、rate-aware RCA、association discovery、experience、nested 50-seed、Student-t 四真值族校准、replay、PID、参数 sweep、真实数据和治理 benchmark 入口。
- 实际启动本机 HTTP 服务，覆盖健康检查、非法 case、非法 seeds、非法 threshold 和超大请求体。
- 解析所有 `outputs/*.json` 与 `runtime_data/evidence/*.json`，递归检查非有限数值，重算 evidence digest，并检查 SQLite 完整性。
- 对 UCI Bank Marketing CSV 重算 SHA-256，核对行列数、缺失单元格和重复行。

#### 代码与系统问题

已修复：

1. HTTP API 对 `seeds=bad`、`threshold=bad` 和未知 case 抛出未捕获异常，客户端收到空响应。现在返回结构化 `400`。
2. Chat POST 无请求体大小限制，可因伪造超大 `Content-Length` 阻塞线程或消耗内存。现在限制为 64 KiB，并返回 `413`。
3. Chat session 使用无上限、无锁的进程内字典。现在增加锁、LRU 行为和 1,000 session 上限。
4. Evidence Pack 直接覆盖目标 JSON，进程中断或并发写可能留下半文件。现在先写同目录临时文件，再原子替换。
5. Ruff 有 9 项错误和 6 个未格式化文件；现已全部清理，服务入口补为可执行文件。
6. `pyproject.toml` 的占位描述已替换为项目实际描述。
7. README、中文 README 和方法文档中的过期指标已按实跑结果更正。
8. 补充 14 项快速回归测试，覆盖输入边界、证据原子写入、分解闭合、实验设计拒答、claim 降级、FDR、完整性门禁和 Student-t 联合后验。

#### Outputs 与数据检查

结构和完整性：

- 所有已生成 JSON 均可解析，未发现 `NaN`、`Infinity` 或 `-Infinity`。
- 4 个 runtime evidence pack 的 evidence digest 全部可重算匹配，缺失 digest 数为 0。
- A/B/C evidence pack 分别包含完整 trace、artifact 与 evidence；SQLite `PRAGMA integrity_check` 返回 `ok`，checkpoint 表有 3 条任务记录。
- UCI CSV：45,211 行、17 列、0 个空单元格、0 个完全重复行。
- UCI CSV SHA-256：`94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686`，与 catalog pin 一致。
- 真实数据适配器正确识别该数据不是随机实验，并将 `duration` 标为结果后泄漏变量；Bayesian 因果层正确拒答。

关键实跑结果：

| 输出 | 结果 | 判断 |
|---|---|---|
| Line A matched 5 seeds | Recall@5 1.00；ATE RMSE 0.001；CrI coverage 1.00；decision 1.00；factor recovery 0.90 | 正常，但 factor recovery 不是旧文档所写的 1.00。 |
| Line A mismatched 2 seeds | decision 1.00；factor recovery 0.75；Brier 0.0445 | 决策稳健，候选恢复能力下降，应诚实保留。 |
| Governance 3 seeds / 9 cases | gate accuracy 1.00；false causal assertion 0；refusal recall 1.00 | 正常。 |
| Line B 5 seeds | 未注册变化召回、外部对齐、unknown honesty 均为 1.00；层级 ATT RMSE 5.552 vs naive 10.233 | 正常。 |
| Rate-aware RCA | 947,604 样本全部通过输入校验；整体分解 closure error 约 `2.9e-18` | 数值闭合正常。 |
| External mapping | 4 个异常映射 2 个，coverage 0.500；两个真值事件均召回，未注册变化未被错挂 | 行为正常，旧文档 0.667 已更正。 |
| Experience 7 periods | sparse ATE RMSE 0.004019 vs 0.004509；错配 onset 正确报警；决策无回退 | 正常；rich RMSE 有轻微波动，不应泛化为全面提升。 |
| Nested 50 seeds | nested direction recall 0.18 vs flat 0.02；ECE 0.0626→0.0390；small-sample decision accuracy 0.52 | 校准有改善，但决策准确率偏低，仅适合研究验证。 |
| Student-t 四真值族 4 × 50 seeds | joint coverage 0.9383 vs plug-in 0.5588；最低单族 0.9100；区间宽度比 Gaussian 高 12.2% | 校准门槛全部通过，但不能替代效用门槛。 |
| Gaussian vs Student-t 仓库回放 | 95% coverage 0.8775 vs joint 0.9475 vs plug-in 0.3075 | 欠覆盖已修复，但效用门槛仍失败，Student-t 不升级为生产默认。 |

#### 建议升级顺序

1. 完成不可变 evidence/run 模型，并将耗时计算迁移到受限 worker。
2. 在维持当前覆盖率的前提下优化 Student-t 方向召回和 moderation RMSE，并实现 covariance-aware likelihood 或互斥分区契约。
3. 建立 CI：Ruff、14 项回归、property tests、1-seed governance benchmark、evidence schema/digest 校验和并发写测试。
4. 为所有 outputs 增加统一 `schema_version`、run manifest、相对路径和原子写入。
5. 拆分超大模块，并补类型检查与公开 API contract 测试。
6. 部署前增加认证、TLS、限流、超时、队列、指标监控和审计日志；不要直接把 demo server 暴露到公网。

#### 最终验证命令

```bash
ruff check .
ruff format --check .
python3 -m unittest discover -s tests -v
python3 -m compileall -q attribution runtime tests main.py run_server.py scripts
python3 -m runtime --benchmark --benchmark-seeds 1
python3 -m attribution
python3 -m attribution.student_t_calibration_benchmark
python3 -m attribution.nested_benchmark
```

上述命令均已通过。`uv lock/build` 在当前受限 macOS 执行环境中因 `uv` 的 `system-configuration` 原生 panic 无法完成；这是工具运行环境故障，不是项目代码报错，但发布前仍应在 CI 中补做 lock、wheel 和 sdist 验证。

## 2026-08-29 — 综合整改

### A. 统计与归因实现整改

#### 1：修复候选级 rate/mix/interaction 重复计算 interaction

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

#### 2：实现真正的 Student-t 随机效应分布

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

#### 3：修复 beam search 未按异常强度剪枝

原实现虽然计算了候选 metrics，但 `next_beam` 中只保存 scope；随后却尝试读取 scope 中不存在的 `gap_change`，导致所有候选的剪枝分数都退化为 0，实际结果依赖生成顺序。

现在：

- beam 节点同时保存 `scope` 和 `beam_score`；
- `beam_score` 明确定义为 `abs(gap_change)`；
- 每层扩展后按 `beam_score` 从高到低保留 `beam_width` 个候选；
- 输出候选中保留 `beam_score`，便于审计剪枝依据；
- dimensions、dimension values 和并列候选采用规范化排序，减少字段顺序、值顺序及输入行顺序对结果的影响。

行为变化：较小 `beam_width` 下，高异常强度交集会被继续搜索，不再因为字段排列顺序稳定漏检。测试中 `beam_width=1` 仍能找到演示数据中的真实三维异常 scope。

#### 4：禁止截断因子设计，并升级组件效应分析

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

#### 5：按随机化单位处理重复观测与 cluster

- 主分析默认使用 `primary_estimand="user_level"`，将同一分析单位的重复曝光聚合后再计算 ITT；二元 `issued` 使用 `max`，金额 `net_premium` 使用 `sum`，也可通过 `outcome_aggregations` 显式配置。
- `primary_estimand="exposure_level"` 保留合格曝光并以曝光加权，但标准误按 `randomization_unit` 使用 CR1 cluster-robust sandwich 估计，不再把曝光行视为独立样本。
- `primary_estimand="triggered_user"` 只分析 triggered 用户并聚合到用户，同时明确标记为 post-assignment conditional estimand、`is_itt=false`。
- cluster-randomized 设计使用 `cluster_column` 作为推断 cluster；功效检查使用聚合后的分析单位数，并另行披露原始行数、重复观测数和排除数。
- 现有 Beta-Binomial 决策层只接受独立的 user-level 分析行；exposure-level 或仍有 cluster 相关性时拒绝输出损害/收益决策概率，保留 cluster-aware 频率学结果。
- 新增跨臂随机化单位拒答、用户聚合、曝光级 robust SE 和 triggered-user 口径测试。

#### 验证

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

### B. Experiment Integrity Gate 升级

#### 升级目的

此前的因果门禁主要检查实验元数据，例如 `assignment_method="randomized"`、`assignment_verified=true` 和可信 assignment provenance。元数据只能说明实验“计划如何随机”，不能证明实际进入分析的数据仍保持正确随机化。

本次增加基于实际行级数据的 `ExperimentIntegrityGate`。系统会先生成实验健康报告；SRM、基线平衡、稳定分流、跨臂污染、时间顺序、样本漏斗、cluster 完整性和并发实验八项检查必须全部通过，才能运行 ITT、Bayesian bundle decision 和 HTE。任一检查失败或缺少检查所需证据时均 fail closed，不输出因果估计。

#### 新增的八项检查

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

#### 新的健康报告与门禁行为

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

#### Fixture 和验证变化

- 随机实验 fixture 增加 assigned/exposed arm、曝光状态、trigger 状态、结果观察状态、三个时间点、assignment period 和并发实验 ID；
- 案例 C 改用两人一组的随机区组分配，在维持随机性的同时保证预定 50/50 allocation；
- 控制平面注册新的 `ExperimentIntegrityGate` skill；
- 新增逐项故障注入测试，分别验证 SRM、失衡、分流漂移、污染、时间倒置、差异流失、cluster 错配和并发实验冲突都会阻断总体门禁；
- 新增缺失检查证据时 fail-closed、ITT 不能绕过，以及 ITT/Bayesian bundle/HTE 共用同一门禁的集成测试。

升级后的最终验证结果：Ruff 静态检查通过，完整测试套件 17/17 通过。

### C. 功效规划与统计输入契约升级

#### 1：功效计算不再固定使用 1.96 和 0.84

原功效筛查无论配置何种 `alpha` 和 `target_power`，都会固定使用 `z_alpha=1.96`、`z_power=0.84`。这会使非默认显著性水平或目标功效的样本量结论失真。

现在使用 Python 标准库的正态分布逆 CDF，根据实际配置计算：

```text
z_alpha = Phi^-1(1 - alpha_tail)
z_power = Phi^-1(target_power)
```

其中 superiority 双侧检验使用 `alpha_tail=alpha/2`，单侧检验及 noninferiority/equivalence 的单侧组成检验使用 `alpha_tail=alpha`。输出新增实际使用的 `z_alpha` 和 `z_power`，便于审计。

##### 明确 MDE 的尺度

功效配置现在必须提供 `minimum_detectable_effect_type`：

- `absolute`：MDE 是概率的绝对百分点差；
- `relative`：MDE 是相对基准率的变化，系统换算为 `baseline_rate × MDE`。

缺少该字段或传入其他值会直接拒绝，不再默认猜测。输出同时记录原始 MDE、MDE 类型、换算后的 `absolute_effect_distance` 和相对零假设边界的实际距离。

##### 支持不等分流

从 `expected_allocation` 读取 control/treatment 目标比例，并使用一般化的两臂方差项：

```text
variance × (1 / allocation_control + 1 / allocation_treatment)
```

因此 70/30 等不等分流不会再套用 50/50 样本量公式。输出新增归一化 allocation、各 arm 所需样本量和实际样本量。

##### 支持 cluster design effect

当 `assignment_method="cluster_randomized"` 时，必须同时提供：

- `cluster_average_size`；
- `intracluster_correlation`。

系统使用：

```text
design_effect = 1 + (cluster_average_size - 1) × ICC
```

对所需样本量进行膨胀。cluster 配置缺失、平均 cluster size 小于 1、ICC 不在 `[0,1)` 时明确拒绝。

##### 支持预期流失

`expected_attrition_rate` 可配置为所有 arm 共用的单个值，也可以按 `{"0": ..., "1": ...}` 分 arm 设置。所需 assignment 样本量按各 arm 的 retention rate 分别膨胀：

```text
required_assigned = required_analyzable × design_effect / (1 - attrition)
```

流失率必须有限且位于 `[0,1)`。

##### 支持 superiority、noninferiority 和 equivalence

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

#### 2：新增统一统计输入有效性契约

新增 `attribution/input_validation.py`，主要统计入口在计算前统一执行 fail-fast 校验。关键条件不成立时直接拒绝统计计算，不再产生外观正常但语义错误的结果。

##### Bayesian bundle 和 HTE

- clicks、impressions 必须是有限、非负、整数值计数，并满足 `clicks <= impressions`；
- prior 参数必须有限且为正；
- practical/moderation threshold 必须有限且非负；
- posterior draws 必须为正整数；
- HTE 的 `segment_id` 必须非空且唯一；
- 每个 segment 必须同时具有合法的 control/treatment 计数。

成功输出新增 `input_validation`，报告实际使用样本、排除样本、排除原因及执行的检查。当前这些入口遇到非法输入直接拒绝，因此成功结果的排除数为 0。

##### Rate-aware RCA

- baseline/current 窗口必须各自合法、严格按时间排列且不重叠；
- day/cell 组合必须唯一；
- control/treatment 计数必须有限且合法；
- baseline 与 current 必须具有相同的 cell universe；
- dimensions 必须非空且唯一；
- `top_k`、`beam_width` 必须为正，`min_impressions` 必须非负。

重复 day/cell、窗口重叠或 cell 在某一窗口消失时现在直接报错，不再依赖后续 closure error 间接暴露数据问题。

##### 时间序列、discovery/holdout 和因子输入

- days 与所有统计序列必须等长、有限、唯一、整数值并严格递增；
- discovery 和 holdout 必须属于总体 days、互不重叠，且 holdout 必须严格晚于 discovery；
- anomaly windows 必须按时间排序、不重叠、start/end 合法且位于总体时间范围内；
- factor series 的 factor/scope 组合必须唯一，days/values 必须等长且合法；
- factor snapshots 的 factor/scope/day 组合必须唯一；
- event factor ID 必须非空且唯一，event window 不允许反向；
- block length、bootstrap reps 和 max lag 必须处于支持范围。

##### Baseline attribution 和实验汇总

- days、control、treated 必须等长、有限且严格按时间排序；
- 每个实验 ATT estimate 必须有限，`att_se` 必须有限且严格大于 0；
- change ID、external event ID 必须唯一；
- registry 的时间点和窗口必须包含在分析 days 中；
- change 引用的 experiment ID 必须真实存在。

##### 其他统计入口

- BH/FDR 的 p-value 必须有限且位于 `[0,1]`，不再用 `clip` 静默修正非法概率；
- calibration 的 predicted/realized 必须有限且位于 `[0,1]`；
- temporal null 要求输入数组一维、等长、非空、有限，null replicate 数量一致；
- 因子实验要求 factor ID 唯一、预算为正整数、outcome 严格为二元 0/1。

#### 验证

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

#### 证据文件同步回放

修复完成后重新运行了标准证据链和统计消融，并刷新 `outputs/` 中受影响的 JSON。回放同时纠正了两项旧证据口径：

- `nu_annealing_sweep.json` 中 50–2000 的参数实际是旧版 pseudo-impression `shrinkage_strength`，不是 Student-t 自由度 `nu`；输出字段和说明已经更名；
- 旧版 `nested_ablation_50seeds.json` 所称的 Student-t coverage 只是给 Gaussian 区间换用 t 临界值，并未运行 Student-t 随机效应；新版改为比较两种真实后验。

50-seed 回放得到 Gaussian coverage `0.8775`、真实 Student-t（`nu=5`、plug-in empirical-Bayes `tau`）coverage `0.3075`。这是必须保留的负结果：当前 Student-t 已经真实进入计算，但 plug-in `tau` 造成明显欠覆盖，不能据此宣称校准改善，也不能将其设为生产默认。后续需要联合传播 `mu`、`tau` 和 `nu` 的不确定性，并在 Gaussian 真值、重尾真值、零异质性和混合异常真值下重新校准。
