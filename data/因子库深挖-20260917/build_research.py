"""Rebuild the research catalog; no production registry or statistical core is changed."""
import ast, json, pathlib, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT.parent/'可执行代码包'
sources={
'S1':('保险销售行为管理办法（商务部法规库转引监管总局）','https://policy.mofcom.gov.cn/claw/clawContent.shtml?id=98055','监管要求与业务对象定义；不证明经营效果'),
'S2':('Google Web Vitals','https://web.dev/articles/vitals','浏览器性能测量定义；不提供本业务转化效果量'),
'S3':('W3C Carousel Pattern','https://www.w3.org/WAI/ARIA/apg/patterns/carousel/','轮播交互与可访问性设计依据'),
'S4':('Microsoft：Diagnosing Sample Ratio Mismatch','https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/','实验数据质量诊断依据'),
'S5':('Cole et al.：Barriers to Household Risk Management（2013）','https://pmc.ncbi.nlm.nih.gov/articles/PMC3995033/','印度降雨保险实验证据；跨市场、跨险种外推有限'),
'S6':('Handel et al.：Information Frictions and Adverse Selection（2015）','https://www.nber.org/papers/w21759','信息摩擦研究；本地因子操作化属于研究设计'),
'S7':('Heiss et al.：Inattention and Switching Costs（2016）','https://www.nber.org/papers/w22765','美国Medicare Part D续保惰性研究；不能直接迁移效应量'),
'S8':('Jaspersen et al.：Predicting Insurance Demand from Risk Attitudes（2019）','https://www.nber.org/papers/w26508','风险态度模型预测保险选择的局限'),
'S9':('UCI Bank Marketing','https://archive.ics.uci.edu/dataset/222/bank+marketing','银行定存营销数据，非保险实证'),
'S10':('金融监管总局：健全人身保险产品定价机制的通知（2024）','https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1175200&itemId=928','历史政策机制依据；不代表2026年当前利率上限'),
'S11':('人民银行：2025年3月20日LPR公告','https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125440/3876551/5625437/index.html','官方发布日期示例；不是当前利率行情'),
'S12':('国家统计局国家数据月度入口','https://data.stats.gov.cn/easyquery.htm?Cn=A01','月度宏观数据源入口；具体序列和可用日期需接入核验')}
# Each row is a proposed operational definition, not a measured business effect.
# id | name | group | priority | causal role | formula | data | scope | lag | validation | failure mode | sources
raw='''
product.matched_quote_gap|同保障报价差|产品与价格|P0|pre_exposure_context|自身年化报价/同日同风险同保障竞品报价中位数-1|报价引擎+授权竞品报价快照|产品×保障篮子×风险层×渠道|0,1,7日|固定保障篮子和风险层做时间外验证；不把价格观察差异解释为随机效果|免赔额、等待期、除外责任不匹配时不可比；竞品样本选择偏差|S5
product.renewal_premium_change|续保保费变化率|产品与价格|P0|pre_exposure_context|续期同保障年化保费/上期同保障年化保费-1|续期报价+历史保单版本|续保批次×产品×保障版本|续保前30,14,7日|按到期批次验证流失预测增量；控制已知保障变化|年龄及保障变化引起的自然涨价混杂；不能用成交价替代首次报价|S7
product.coverage_version|保障责任版本|产品与价格|P1|change_candidate|责任/免赔/等待期/续保条件的结构化版本及逐项差异|产品条款库+生效记录|产品×版本×生效日|0,7,30日|逐字段编码并核对实施范围；同期改价单列|不能将文本差异总字数当作保障改善幅度|S1
product.sale_unavailable_rate|可售性阻断率|产品与价格|P0|upstream_diagnostic|因地区/产品停售/系统不可售被阻断的去重请求数/全部产品资格查询请求数|资格查询服务+产品上下架日志|产品×地区×渠道|0,1日|按明确原因码拆分；自然灰度需验证可比性|不含不进入资格查询的用户；技术不可售与核保拒绝不能合并|S1
product.withdrawal_horizon|距正式停售生效日|产品与价格|P1|external_event_context|已公告停售生效日期-当前日期；无公告为缺失并附未公告标记|正式公告+产品版本|受影响产品×地区|公告至生效及后30日|公告日与生效日分开事件研究；检验提前购买及后续回落|禁止用事后得知的停售日期回填；营销宣传并非公告|S1,S10
product.payment_schedule|缴费方式配置|产品与价格|P1|treatment_candidate|趸交/年交/月交类别及各方式年化总额、首期金额分别记录|产品费率配置+首次报价|产品×缴费年期×版本|0,7日|仅在允许的产品方案内比较展示方式；总成本明示|不能把降低首期付款等同降低总保费；人群自选择|S5
experience.lcp_p75|首屏最大内容绘制P75|体验与组件|P0|mediator_diagnostic|同页面类型有效访问LCP的75分位数（毫秒）|浏览器RUM+页面版本|页面×端类型×网络层|0,1日|随机化加载策略，按分组估计总效果；LCP作机制指标|仅有成功上报会话可导致选择偏差；原生App不能直接套用|S2
experience.inp_p75|交互响应P75|体验与组件|P1|mediator_diagnostic|存在合格交互的访问INP的75分位数（毫秒）|浏览器RUM+交互覆盖率|页面×浏览器×设备层|0,1日|随机化脚本优化并同时报告无交互与未上报比例|无交互访问不能填0；不把处理后INP放入总效果回归|S2
experience.cls_p75|布局偏移P75|体验与组件|P1|mediator_diagnostic|有效访问CLS的75分位数|浏览器RUM+模板版本|页面×设备层|0,1日|图片占位方案实验；观察误触和最终承保|偏移下降不必然带来销售提升；和首屏渲染共线|S2
experience.carousel_rotation_config|轮播自动切换配置|体验与组件|P1|treatment_candidate|自动切换开关、间隔毫秒、暂停控件存在性分别编码|Growth UI Spec+渲染快照|组件×版本×设备层|0,1日|比较符合可访问性要求的配置；点击和有效投保共同评估|可访问性缺陷应修复；不得故意取消必要控制做实验|S3
experience.offer_count|可见可选方案数|体验与组件|P1|treatment_candidate|首屏实际展示且符合资格的去重方案数|推荐响应+渲染曝光|产品族×新老客×页面|0,7日|在同一合格方案池内随机化分组展示；记录选择质量|方案数与方案质量同时变动造成混杂|S6
experience.explanation_variant|条款解释呈现版本|体验与组件|P0|treatment_candidate|完整条款不变时摘要/术语说明/对比呈现的版本类别|CMS版本+审核记录+曝光|产品×页面×版本|0,7日|随机化已审阅的解释方式；理解题与成熟撤单作为护栏|停留长短不是理解程度；少披露不能视为优化|S1,S6
journey.quote_validity_remaining|报价剩余有效时长|投保与核保|P1|pre_exposure_context|报价过期时间-展示时间（分钟）|quote_id+issued_at+expires_at+展示时刻|产品×报价版本|0日|检验过期集中分布；优化提醒方案可实验|展示之后重报价会内生；按首次报价定义主分析|S1
journey.premium_requote_gap|提交前后报价变化|投保与核保|P0|mediator_diagnostic|最终确认前报价/首次相同保障报价-1|同一申请报价版本链|产品×风险层×渠道|0,1日|按健康告知/参数补全/版本切换原因拆解|处理后因子，不能解释首次点击；客户主动改保障单列|S1
journey.underwriting_backlog_age_p90|核保待处理队列年龄P90|投保与核保|P0|pre_exposure_context|时点t尚未结案申请的(t-入队时间)90分位数|核保队列时点快照|队列×产品×日期|1,3,7日|服务容量变化事件分析；明确队列干扰，按队列聚类|只统计结案耗时会漏掉最慢单；申请复杂度混杂|S1
journey.additional_material_rate|补件请求率|投保与核保|P1|mediator_diagnostic|固定观察窗内收到至少一次补件请求的申请/同期成熟申请|核保状态日志+申请批次|产品×申请批次×原因码|1,7,14日|分解资料质量与规则变更；随机化提交指引|健康风险与规则调整混杂；未成熟申请右删失|S1
journey.otp_delivery_latency_p95|验证码送达延迟P95|投保与核保|P0|mediator_diagnostic|成功送达验证码的送达时间-请求时间的95分位数，另报未送达比例|验证码请求+供应商回执|供应商×运营商×地区|0,1日|路由灰度与供应商故障窗口核验|只看成功回执会低估故障；不能替代短信失败率|S4
journey.payment_decline_reason_share|支付拒绝原因结构|投保与核保|P0|mediator_diagnostic|各拒绝原因去重支付意图数/全部支付意图数|支付意图日志+网关标准原因码|支付通道×产品×端|0,1日|区分技术、授权、余额等原因；仅对可修复链路验证|同一订单重试不可当独立订单；不推断个人财务状况|S4
service.renewal_reminder_lead_days|续保提醒提前天数|续保与服务|P0|treatment_candidate|分配的首次提醒计划日期距保单到期日的天数|续保日历+触达分配日志|续保批次×产品×渠道|到期前30,14,7日|用户级提醒计划实验；按全部分配用户做ITT|实际打开日是处理后变量；不能只比较已读用户|S7
service.contact_frequency_cap|触达频控配置|续保与服务|P1|treatment_candidate|每用户每7日计划允许触达上限，分渠道记录|CRM频控配置+分配日志|活动×用户预处理层|0,7,14日|频控方案随机化；退订投诉与投保共同评估|实际触达次数受用户反馈影响；不能替代分配策略|S9
service.agent_capacity_load|顾问在手待办负载|续保与服务|P1|pre_exposure_context|分配前未处理有效线索数/当班合格顾问数|CRM队列+排班快照|团队×产品资质×小时|0,1,7日|团队或时间块设计，处理共享顾问溢出|线索质量与排班同时变化；零顾问时记停服不算0|S1
service.claim_history_at_renewal|续保前理赔体验|续保与服务|P2|pre_exposure_context|仅用续保分配前已发生的是否理赔、已结案耗时和未结案标记|最小化理赔汇总+保单时间轴|产品×续保批次|前365日历史|分层相关验证；不对理赔权益或服务质量人为降级实验|理赔需求本身混杂；未结案不能用未来处理时间回填|S7
service.cooling_off_cancel_rate|成熟犹豫期撤单率|续保与服务|P0|outcome_guardrail|合同规定犹豫期已完整经过的保单中犹豫期撤单数/该成熟保单数|承保+撤单+合同犹豫期字段|承保批次×产品×渠道|按合同成熟时间|作为理解/提醒实验的延迟护栏，报告成熟覆盖率|结果不能回填为销售前因子；不可统一假设所有产品同一天数|S1
service.renewal_persistency_rate|到期批次续保率|续保与服务|P1|outcome_guardrail|固定宽限观察窗内完成续保的合格到期保单/同期合格到期保单|到期日历+续期保单+资格规则|到期批次×产品|按续保窗口成熟|明确停售迁移和不可续保单；长期效果验证|按当月新保单分母算续保率错误；需冻结资格规则|S7
mix.new_visitor_share|新访客流量占比|客群与渠道|P0|composition_context|预先定义历史窗口内未访问的合格访客/全部合格访客|分配前身份标识+访问历史|渠道×端×地区|0,1,7日|先做固定分层mix/rate分解，再检验组内变化|cookie重置伪造新客；不可用购买后身份信息分层|S4
mix.renewal_due_share|近期到期客群占比|客群与渠道|P1|composition_context|分配前已知30日内到期客户/全部合格访问客户|保单日历+授权关联键|产品×渠道×日期|0,7,30日|区分自然续保季节与新客转化，按到期批次核验|登录后才匹配出的到期身份可能产生选择偏差|S7
mix.product_portfolio_share|产品组合占比|客群与渠道|P0|composition_context|每个产品族的预定义入口合格流量/总合格入口流量|入口产品标记+资格快照|渠道×地区×日期|0,1,7日|冻结产品族权重分解；同时报告各族保费和投保率|用成交产品占比解释成交是循环定义|S1
mix.partner_lead_duplicate_rate|渠道线索重复率|客群与渠道|P1|measurement_diagnostic|授权去重窗口内重复线索数/入站线索数|渠道lead_id+最小化稳定去重键|合作渠道×日期|0,1,7日|与合同有效线索及下游接通分开对账|跨渠道身份不可拼接时单报未知覆盖率|S4
external.matched_competitor_coverage_change|竞品同类保障变化|外部环境|P2|external_event_context|匹配保障篮子下责任/免赔/等待期变化的类别向量|竞品正式条款版本及授权快照|同险种×目标地区|0,7,30日|事件研究加不受影响产品负对照|不能把保障扩展与竞品同时降价分开强行归因|S1,S6
external.policy_product_exposure|政策影响产品暴露度|外部环境|P1|external_event_context|政策适用产品指示×事件前冻结的合格流量占比|政策原文+内部产品映射+公告日期|产品族×地区|公告/生效分别0,7,30日|区别适用与不适用产品，检查预趋势及提前反应|通知条数不是政策强度；冻结权重避免反向反馈|S10
external.deposit_alternative_gap|储蓄替代产品收益差|外部环境|P2|external_context|同币种同期限公开存款利率与保单保证现金流IRR之差|银行正式利率页+产品保证现金流|储蓄型产品×币种×期限|7,30,90日|低频验证，仅在期限与流动性可比子集分析|LPR不是存款利率；非保证分红不能当保证收益|S10,S11
external.holiday_distance|距节假日距离|外部环境|P1|calendar_context|当地工作日/调休日类别及距假期首尾天数|正式日历+企业营业日历|地区×渠道×日期|前后7,14日|跨年同类节假日窗口验证，拆营业时间和需求|公历同比错位；固定效应与该因子重复编码|S12
quality.assignment_srm_stat|分流比例失配统计量|数据质量|P0|quality_gate|按预设分流比例计算各组去重分配人数的拟合优度统计量及p值|分配服务日志+预设概率|实验×分配单位×日期|当日累计|A/A及分配日志对账；失败先排障|有意非等比例分流不得用50:50检验；稀疏格需适用检验|S4
quality.cross_variant_contamination|跨组污染率|数据质量|P0|quality_gate|同实验同随机化单位出现多个不允许variant的单位数/分配单位数|分配日志+曝光版本|实验×随机化单位|0,1日|核对粘性分流及跨端标识；比较分配与实际暴露|合法多因子设计不可误判污染；主分析遵循原分配|S4
quality.event_duplicate_rate|事件重复率|数据质量|P0|quality_gate|重复event_id条数/接收事件条数|采集原始元数据+去重结果|事件×SDK×版本|0,1日|重放幂等性和分组丢重率对账|无稳定event_id不能可靠区分重复与真实多次行为|S4
quality.denominator_contract_change|指标分母口径变更|数据质量|P0|quality_gate|曝光资格/去重单位/机器人过滤/时间窗配置的版本差异|指标契约版本+ETL部署记录|指标×版本×日期|0日|同一原始窗口双算旧新口径，报告差额|口径变化不能当业务改善；重算会影响历史可比性|S4
quality.source_availability_lag|数据可用时间延迟|数据质量|P0|quality_gate|available_at-event_time，汇总P95并记录缺失可用时间占比|数据入仓日志+外部发布时间|来源×频率×日期|0,1,7日|按as-of重建快照与实时视图对照|不能把月末所属日期当月度指标公布日|S4,S12
quality.order_policy_reconcile_gap|支付承保对账差额|数据质量|P0|quality_gate|成熟支付意图中已支付但无有效保单映射的数量/成熟已支付意图数|支付账本+保单主键+退款状态|产品×支付渠道×支付批次|合同定义成熟窗口|区分异步出单、退款和真实丢单，按状态机核对|异步延迟未成熟时不能判故障；保单拆分多对多映射|S4
'''
rows=[]
for line in raw.strip().splitlines():
 vals=line.split('|'); assert len(vals)==12,(len(vals),line)
 keys=['factor_id','name','family','priority','causal_role','formula','data_source','scope','lag_candidates','validation','failure_mode','source_ids']
 rows.append(dict(zip(keys,vals)))
# Audit actual local definitions without executing demo generation.
tree=ast.parse((BASE/'track2_v5/scenario_reports.py').read_text())
existing={}; series=set()
for n in ast.walk(tree):
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='factor_names' for t in n.targets): existing=ast.literal_eval(n.value)
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='factor' and n.args and isinstance(n.args[0],ast.Constant): series.add(n.args[0].value)
factors=[]
for r in rows:
 refs=r.pop('source_ids').split(','); fid=r.pop('factor_id'); name=r.pop('name')
 assert fid not in existing
 role=r['causal_role']
 r.update(source_ids=refs, source_links=[sources[s][1] for s in refs], evidence_status='mechanism_or_measurement_basis_only',definition_origin='proposed_operationalization_2026-09-17', business_effect_verified=False, production_ready=False, data_readiness='requires_authorized_data_mapping', claim_type='FACTOR_CANDIDATE', unit_policy='formula_specific; proportions 0..1; rates store numerator and denominator',missing_policy='missing_not_zero; preserve reason and coverage; do not interpolate binary events',time_contract={'event_time':'business occurrence time','published_at':'external first publication if applicable','available_at':'first usable in pipeline','as_of':'analysis cutoff; require available_at <= as_of'}, parent_factor_id=fid,transform_policy='numeric series only; prespecified trailing transforms; no differences for category hashes', causal_adjustment='role depends on target and DAG; mediator/outcome/quality_gate excluded from default pretreatment adjustment')
 factors.append({'factor_id':fid,'name':name,'description':r['formula'],'source_type':'RESEARCH_CANDIDATE','scope':{'domain':'insurance_sales','grain':r['scope']},'aliases':[name,fid.split('.')[-1]],'status':'research_candidate','license_ref':None,'metadata':r})
(ROOT/'候选因子库.json').write_text(json.dumps(factors,ensure_ascii=False,indent=2)+'\n')
(ROOT/'研究来源.json').write_text(json.dumps([{'source_id':s,'title':v[0],'url':v[1],'use_boundary':v[2],'checked_at':'2026-09-17','access_scope':('page_text_opened' if s in {'S1','S2','S3','S4'} else 'search_index_excerpt_or_abstract; not full-paper review'),'license_ref':None} for s,v in sources.items()],ensure_ascii=False,indent=2)+'\n')
(ROOT/'现有因子盘点.json').write_text(json.dumps({'scope':'scenario_reports.py named definitions only; not an exhaustive inventory of runtime databases or all Spec paths','named_count':len(existing),'series_definition_count':len(series),'named_factors':[{'factor_id':k,'name':v[0],'description':v[1],'has_series_definition':k in series} for k,v in existing.items()]},ensure_ascii=False,indent=2)+'\n')
lines=['# 保险销售经营归因：新增候选因子卡片','',f'研究日期：2026-09-17。共 {len(factors)} 个新增ID；已与 scenario_reports.py 的49个具名ID去重。语义重叠及旧因子细化关系见研究报告。以下公式、时间窗和优先级均为研究建议，不是既有实证结果。','', 'P0：先补采集/口径；P1：第二批；P2：业务适用性确认后。数据均待映射，不含模拟快照。']
for f in factors:
 m=f['metadata']; lines += ['',f"## {f['name']} · {m['priority']}",f"`{f['factor_id']}` · {m['family']} · 角色：`{m['causal_role']}`",'',f"- 定义：{m['formula']}",f"- 数据与粒度：{m['data_source']}；{m['scope']}",f"- 候选时间窗：{m['lag_candidates']}（须预注册，非已证实滞后）",f"- 验证：{m['validation']}",f"- 主要陷阱：{m['failure_mode']}",'- 依据：'+'；'.join(f'[{s} {sources[s][0]}]({sources[s][1]})' for s in m['source_ids'])+'。来源支持机制或测量原则，具体公式是本次建议。']
(ROOT/'候选因子卡片.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'new_candidates':len(factors),'existing_named':len(existing),'existing_series':len(series),'priorities':{p:sum(f['metadata']['priority']==p for f in factors) for p in ['P0','P1','P2']}},ensure_ascii=False))
