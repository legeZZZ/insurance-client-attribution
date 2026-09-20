"""Render the complete recorded results without rerunning or filtering seeds."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path):return json.loads((ROOT/path).read_text())
def number(value):return '—' if value is None else f'{value:.4f}'

s=read('outputs/stage_e/statistics/statistics.json');g=read('outputs/stage_e/graphs/graphs.json');m=read('outputs/stage_e/agents-v2/memory.json');f=read('outputs/stage_f/research-v3/research.json');hidden=read('outputs/stage_e/graphs/historical_hidden.json');transfer=read('outputs/stage_e/graphs/transfer.json')
lines=['# 阶段E/F评测报告（2026-09-16）','','工程验收与统计适用性分开记录。全部协议、逐种子输出及拒答均归档；没有删除不利种子。控制台不在本次验收范围。','','## 阶段E统计矩阵','','22类场景各50种子，合计1,100次；关联流程从预处理重跑至独立留出确认，效应流程实际经过相同L0/L1/识别/L3实现。Monte Carlo为单进程四层执行，进程隔离的数值等价另外做配对验证。','','| 关联场景 | mean FDP | 功效 | 运行异常 |','|---|---:|---:|---:|']
for name,row in s['association'].items():
 r=row['summary'];lines.append(f"| {name} | {number(r['fdp']['mean'])} | {number(r['power']['mean'])} | {r['errors']} |")
lines+=['','| 效应场景 | 可估计/总数 | Bias | RMSE | 区间覆盖率 | 平均宽度 | 已发布数 |','|---|---:|---:|---:|---:|---:|---:|']
for name,row in s['effects'].items():
 r=row['summary'];lines.append(f"| {name} | {r['available']}/{r['total']} | {number(r['bias']['mean'])} | {number(r['rmse'])} | {number(r['coverage'])} | {number(r['width']['mean'])} | {r['publication_available']} |")
lines+=['','效应表使用各方法明确的目标尺度，不能跨生成机制按RMSE排名。上表覆盖率是可估计项的原始区间覆盖率；无条件覆盖率、发布后覆盖率、拒答数及原因在JSON单列。GCM探索估计没有因方法拟合成功就获得发布资格。均值同时报告sd/√R；[0,1]均值的95%区间采用保守Hoeffding界，二项率另报Clopper–Pearson区间。零次错误不等同真实错误率为零。','','## 图方向与解释账本','','图5类×20种子（共100次）真实运行PCMCI+/LPCMCI，非线性场景使用CMIknn。','','| 场景 | 共识方向 FDP | 共识方向功效 | 保留歧义率 |','|---|---:|---:|---:|']
for name,row in g.items():
 r=row['summary'];lines.append(f"| {name} | {number(r['orientation_fdp']['mean'])} | {number(r['power']['mean'])} | {number(r['ambiguity_rate']['mean'])} |")
lines+=['','**负结果：本矩阵的严格双算法共识没有输出方向边，植入滞后/非线性边的方向功效为0，不能把全不选择当作方法达标。**该模块保留图歧义，不授予因果效应资格；继续使用独立实验或明确接受并验证的设计。',f"解释账本另有100次A轨估计→coverage/时间响应→L0区间传播；固定迁移条件下覆盖率为{number(transfer['summary']['coverage'])}，不包含未知覆盖率或迁移假设的不确定性。",'',f"历史隐藏基准已实际隔离重跑24例：门禁准确率{hidden['metrics']['causal_gate_accuracy']}（22/24），错误因果断言率为0/16，拒答召回率为1；8个预期可识别实验中6个实际通过门禁、2个被拒绝。两个效应口径的可估计项覆盖率均6/6；失败清单完整保留。",'','## Agent与治理成本','','20个配对任务×3记忆条件，共60次实际方法执行；另有40次单层/隔离编排、40次单遍/循环。模型均为确定性规则，无模型调用，token为0；不外推为LLM能力提升。','','| 条件 | 正确率 | 包含治理的总耗时（秒） |','|---|---:|---:|']
for name,row in m['summary'].items():lines.append(f"| {name} | {number(row['correctness']['mean'])} | {number(row['total_seconds_including_governance'])} |")
lines+=['',f"治理一次性耗时{number(m['governance_once_seconds'])}秒，记录2次fixture人审凭证事件；任务运行中的人工介入为0。三组在本批口径检查任务的准确率相同，配对正确率增益为0，治理增加开销；不宣称“越用越强”。源轨迹、验证与灰度快照、单次I/O字节及耗时保存在memory.json。循环日志含完整轮次、测试预算、止步原因、FDP和功效，编排两组发布结果摘要一致。",'','## 阶段F研究支线','','TSKI的子采样、e-value聚合及其时间依赖条件参考[论文原文](https://arxiv.org/html/2112.09851v3)。本实现使用对称ridge系数差，验证flip-sign；不借用论文的Lasso功效定理。已知IID Gaussian联合分布的交换性与带时间相关的联合交换误差分别核验。所有研究输出formal_selection_allowed=false，不接入生产因果门。','','6种knockoff机制各50种子，共300次；合成因子正/负机制各50种子，共100次。数据生成与算法采样使用分开的随机流。','','| Knockoff场景 | mean FDP | 功效 | 判定 |','|---|---:|---:|---|']
for name,row in f['knockoffs'].items():
 r=row['summary'];lines.append(f"| {name} | {number(r['mean_fdp']['mean'])} | {number(r['power']['mean'])} | {r['assessment']} |")
lines+=['','IID强信号场景的FDP约0.050、功效1，属于已声明模型下的有限实验。只有3个信号时，knockoff+阈值导致本批不选择，功效0，明确为低功效负结果。时间依赖即使子采样后结果改善，也没有自动证明混合/KL条件；错设协方差时FDP约0.562，是禁止正式使用的直接压力证据。','','| 合成因子场景 | mean FDP | 交互恢复功效 |','|---|---:|---:|']
for name,row in f['synthesis'].items():r=row['summary'];lines.append(f"| {name} | {number(r['fdp']['mean'])} | {number(r['power']['mean'])} |")
lines+=['','合成实验冻结product(x,z)、add(u,v)、subtract(u,v)三个表达式；u/v独立于植入机制，是真实负对照。完整族在独立后窗Holm确认，实际检验6次/任务（发现3+确认3），首个确认额度0.025；晋级只到候选，不授予因果。', '', '研究首版及中间版本发现PRNG耦合和真零定义错误，保留于research及research-v2并标记INVALID_PROTOCOL；最终有效结果是research-v3。这些无效协议不得与最终结果混合计算。', '', '## 交付索引', '', '- E：outputs/stage_e/completion/acceptance.json；statistics、graphs、agents-v2。', '- F：outputs/stage_f/completion/acceptance.json；research-v3/research.json。', '- 部署：outputs/stage_e/deployment，含实际构建、容器回归、禁网离线安装日志及Linux ARM wheel。', '- 完整接口与迁移：后端交付与迁移说明.md；原逐文件表：交付映射与验收索引.md。', '', '真实业务2–3案例由用户后期替换数据后执行；本次已完成冻结/揭盲/评分工具及现有数据验收，不将现有生成场景当成未来业务验证。']
(ROOT/'阶段E-F评测报告.md').write_text('\n'.join(lines)+'\n')
for name in ('research','research-v2'):
 p=ROOT/'outputs/stage_f'/name/'research.json'
 if p.exists():
  r=json.loads(p.read_text());r['status']='INVALID_PROTOCOL';r['invalid_reason']='coupled data/knockoff RNG streams and invalid independence labels; retained for audit; superseded by research-v3';p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
