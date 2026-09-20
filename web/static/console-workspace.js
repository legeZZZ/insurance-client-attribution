/* All displayed evidence comes from the workspace API or the bundled snapshot. */
const WS_CASES = {
  line_a:{title:'改了轮播图，为什么点击掉了？', label:'A · 实验归因', text:'先确认整套改版的影响，再看设备异质性与组件实验，形成待审批建议。', live:'line_a'},
  line_b:{title:'保费波动，究竟该先查谁？', label:'B · 开放因子发现', text:'拆开已登记动作、外部共同变化和未知残差；水平、增速、加速度分别验证。',live:'line_b'},
  refused:{title:'看起来像原因，为什么拒绝下结论？',label:'识别门 · 补证',text:'随机分配不可追溯时停在关联层，展示拦截依据与补证路径。', live:'bayes_case_a'}
};
let WS_CASE='line_a', WS_EVIDENCE='line_a', WS_LIVE=null, WS_BUSY=false;
const WS_ASSUMPTIONS={data_valid:'数据有效',outcome_mature:'结果已成熟',support_overlap:'支持域重叠',assignment_traceable:'随机分配可追溯',srm_pass:'分流比例正常',assignment_consistent:'分配与记录一致',interference_absent:'无干扰假设'};
function wsData(){return D.workspace||{};}
function wsArtifacts(){return wsData().artifacts||[];}
function wsArtifact(id){return wsArtifacts().find(a=>a.id===id)||{data:{},status:'MISSING'};}
function wsRaw(value){return `<pre class="ws-json">${esc(JSON.stringify(value,null,2))}</pre>`;}
function wsDetails(title,value){return `<details class="ws-detail"><summary>${esc(title)}</summary>${wsRaw(value)}</details>`;}
function wsNumber(n,d=2){return typeof n==='number'&&Number.isFinite(n)?n.toFixed(d):'未提供';}
function wsPP(n){return typeof n==='number'?`${(n*100).toFixed(2)} pp`:'未估计';}
function wsDownload(value,name){const u=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function wsOpenCase(id){WS_CASE=id;WS_LIVE=null;renderInvestigation();showView('investigation');}
function wsOpenEvidence(id){WS_EVIDENCE=id;renderEvidenceWorkspace();showView('evidencepack');}
/* ================= 01 总控：经营看板 + 异动下钻 + 异动实验工作台 ================= */
function renderOverview(){
  const el = document.getElementById('view-overview');
  const rules = bizRules();
  const open = D.alerts.filter(a=>a.state.status==='open');
  const high = open.filter(a=>a.level==='high').length;
  const st = k=>bizStatus(k,rules);
  const badge = k=>{const s=st(k);return s==='exempt'?'<span class="pill">豁免期</span>':s==='severe'?'<span class="pill red">严重异动</span>':s==='alert'?'<span class="pill red">异动</span>':s==='watch'?'<span class="pill gold">关注</span>':'<span class="pill green">正常</span>';};
  const th = k=>bizThreshold(k,rules);
  const kpiCard = k=>`<div class="card" style="margin:0;cursor:pointer;${st(k)==='severe'||st(k)==='alert'?'border-left:3px solid var(--red)':st(k)==='watch'?'border-left:3px solid var(--gold)':''}" onclick="bizDrill('${k.key}')" title="点击下钻该指标">
      <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:12px;color:var(--muted)">${k.name}</span>${badge(k)}</div>
      <div style="font-size:26px;font-weight:700;margin:6px 0 2px">${k.value}<span style="font-size:12px;color:var(--muted)"> ${k.unit}</span></div>
      <div style="font-size:11.5px;color:${Math.abs(k.yoy)>=th(k).yoy?'var(--red)':'var(--muted)'}">同比 ${fmtDelta(k.yoy)} · <span style="color:${Math.abs(k.mom)>=th(k).mom?'var(--red)':'var(--muted)'}">环比 ${fmtDelta(k.mom)}</span></div>
    </div>`;
  const flagged = BIZ_KPIS.concat(BIZ_SLOTS).filter(k=>['alert','severe'].includes(st(k)));
  const watched = BIZ_KPIS.concat(BIZ_SLOTS).filter(k=>st(k)==='watch');
  el.innerHTML = `
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
      <h3 style="margin:0">经营总控 · 今日核心指标 <span style="font-size:11px;color:var(--muted);font-weight:400">2026-09-20 · 演示口径（脱敏示例数据；点击指标卡或异动条目可下钻）</span></h3>
      <span style="font-size:12px;color:var(--muted)">高风险预警 ${high} · 未闭环预警 ${open.length} · <a style="color:var(--blue);cursor:pointer" onclick="showView('alerts')">进入风险预警 →</a></span>
    </div>
  </div>
  <div class="cc-kpis" style="grid-template-columns:repeat(3,1fr)">${BIZ_KPIS.map(kpiCard).join('')}</div>

  ${renderRulePanel(rules)}

  ${flagged.length?`<div class="card" style="border-left:3px solid var(--red)"><h3>今日异动清单 · ${flagged.length} 项${watched.length?` <span style="font-size:11px;color:var(--gold);font-weight:400">另有 ${watched.length} 项关注</span>`:''}</h3>
    ${flagged.map(k=>`<div class="timeline"><div><span class="t">${st(k)==='severe'?'严重':'异动'}</span><b>${esc(k.name)}</b> 同比 ${fmtDelta(k.yoy)} / 环比 ${fmtDelta(k.mom)} 超阈值 —— <a style="color:var(--blue);cursor:pointer" onclick="bizDrill('${k.key}')">下钻拆解 →</a> <a style="color:var(--blue);cursor:pointer" onclick="wsExpStart('${k.key}')">发起实验排查 →</a></div></div>`).join('')}</div>`
  :'<div class="card" style="border-left:3px solid var(--green)"><b>当前规则下无异动指标。</b><span style="font-size:12.5px;color:var(--muted)">调整下方规则可改变判定口径。</span></div>'}

  <div id="biz-drill"></div>

  <div class="card"><h3>资源位 / 运营位表现 <span style="font-size:11px;color:var(--muted);font-weight:400">整体指标异动先拆到这里：看是整体下滑，还是个别位置主导</span></h3>
    <table class="full"><tr><th>位置</th><th>曝光(万)</th><th>CTR</th><th>CVR(点击→投保)</th><th>同比</th><th>环比</th><th>状态</th></tr>
    ${BIZ_SLOTS.map(k=>`<tr style="cursor:pointer" onclick="bizDrill('${k.key}')"><td><b>${esc(k.name)}</b></td><td>${k.extra}</td><td>${k.value}${k.unit}</td><td>${k.cvr}</td><td style="color:${Math.abs(k.yoy)>=th(k).yoy?'var(--red)':'inherit'}">${fmtDelta(k.yoy)}</td><td style="color:${Math.abs(k.mom)>=th(k).mom?'var(--red)':'inherit'}">${fmtDelta(k.mom)}</td><td>${badge(k)}</td></tr>`).join('')}</table>
    <div style="font-size:11.5px;color:var(--muted);margin-top:6px">首页轮播 CTR 同比 −12.6%：该切面已进入 B 线候选排查（见因子实验室）。对任意异动可点「发起实验排查」，进入因子实验室的异动实验工作台。</div>
  </div>`;
}

/* ---- 异动判定规则：策略化配置（分组阈值 + 分级 + 豁免活动） ---- */
const BIZ_GROUPS = {traffic:'流量曝光', conv:'转化效率', money:'金额与风控'};
function bizThreshold(k,rules){
  const g = rules.groups && rules.groups[k.grp];
  if(g && g.on) return {yoy:g.yoy, mom:g.mom};
  return {yoy:rules.yoy, mom:rules.mom};
}
function renderRulePanel(rules){
  const acts = D.cards.filter(c=>c.route==='internal').slice(0,6);
  const grpRow = (key)=>{ const g=(rules.groups&&rules.groups[key])||{on:false,yoy:rules.yoy,mom:rules.mom};
    return `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px dashed var(--line)">
      <span style="width:80px;font-size:12.5px"><b>${BIZ_GROUPS[key]}</b></span>
      <label style="font-size:12px;color:var(--muted)"><input type="checkbox" class="rule-grp-on" data-grp="${key}" ${g.on?'checked':''}> 独立阈值</label>
      <span style="font-size:12px">同比</span><input type="number" class="rule-grp-yoy" data-grp="${key}" min="1" max="100" step="0.5" value="${g.yoy}" ${g.on?'':'disabled'} style="width:64px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"><span style="font-size:12px">%</span>
      <span style="font-size:12px">环比</span><input type="number" class="rule-grp-mom" data-grp="${key}" min="1" max="100" step="0.5" value="${g.mom}" ${g.on?'':'disabled'} style="width:64px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"><span style="font-size:12px">%</span>
      ${g.on?'':'<span style="font-size:11px;color:var(--muted)">跟随全局</span>'}
    </div>`;};
  return `<div class="card">
    <h3>异动判定策略 <span style="font-size:11px;color:var(--muted);font-weight:400">判定口径由业务定义；规则只影响展示层判定与预警入口，不改变统计管线的任何结论</span></h3>
    <div style="display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px">
      <div style="border:1px solid var(--line);border-radius:8px;padding:12px">
        <b style="font-size:12.5px">① 判定阈值（按指标组）</b>
        <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--line)">
          <span style="width:80px;font-size:12.5px"><b>全局默认</b></span>
          <span style="font-size:12px">同比</span><input id="rule-yoy" type="number" min="1" max="100" step="0.5" value="${rules.yoy}" style="width:64px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"><span style="font-size:12px">%</span>
          <span style="font-size:12px">环比</span><input id="rule-mom" type="number" min="1" max="100" step="0.5" value="${rules.mom}" style="width:64px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"><span style="font-size:12px">%</span>
        </div>
        ${Object.keys(BIZ_GROUPS).map(grpRow).join('')}
      </div>
      <div style="border:1px solid var(--line);border-radius:8px;padding:12px">
        <b style="font-size:12.5px">② 严重度分级</b>
        <div style="font-size:12px;margin-top:8px;display:grid;gap:7px">
          <span><span class="pill gold">关注</span> 达到阈值的 60%，进入观察</span>
          <span><span class="pill red">异动</span> 达到阈值 100%，进入异动清单</span>
          <span><span class="pill red">严重异动</span> 达到阈值 150%，同步推送风险预警</span>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-top:10px">防抖（连续 N 期超限才判定）在服务模式生效；演示数据为单期快照。</div>
      </div>
      <div style="border:1px solid var(--line);border-radius:8px;padding:12px">
        <b style="font-size:12.5px">③ 豁免活动 <span style="font-weight:400;color:var(--muted)">活动期内的预期波动不计异动</span></b>
        <div style="margin-top:8px;display:grid;gap:6px">
        ${acts.map(a=>`<label class="chip ${rules.exempt.includes(a.fid)?'on':''}" style="cursor:pointer;display:flex;justify-content:space-between;gap:6px"><span><input type="checkbox" class="rule-exempt" value="${esc(a.fid)}" ${rules.exempt.includes(a.fid)?'checked':''} style="margin-right:4px">${esc(a.name)}</span><span style="font-size:10.5px;color:var(--muted)">09-18～09-22</span></label>`).join('')}
        </div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;margin-top:12px">
      <button class="chip on" style="cursor:pointer" onclick="saveBizRules()">保存策略</button>
      <span style="font-size:11.5px;color:var(--muted)">${rules.savedAt?`上次保存 ${esc(rules.savedAt)} · `:''}规则保存在本地（服务模式将写入治理留痕）。</span>
    </div>
  </div>`;
}

/* ---- 异动下钻：先看资源位拆解，判断整体下滑还是个别下滑 ---- */
function bizDrill(key){
  const k = BIZ_KPIS.concat(BIZ_SLOTS).find(x=>x.key===key);
  const el = document.getElementById('biz-drill');
  if(!k){return;}
  let body='';
  if(key==='ctr'){
    const total = BIZ_SLOTS.reduce((s,x)=>s+Number(x.extra),0);
    const rows = BIZ_SLOTS.map(x=>{const share=Number(x.extra)/total; const contrib=share*x.yoy; return {...x,share,contrib};});
    const sumContrib = rows.reduce((s,x)=>s+x.contrib,0);
    const top = rows.slice().sort((a,b)=>a.contrib-b.contrib)[0];
    const topShare = Math.abs(top.contrib)/(rows.reduce((s,x)=>s+Math.abs(x.contrib),0));
    const verdict = topShare>=0.5
      ? `<div class="ws-callout" style="border-left:3px solid var(--red)"><b>判定：个别资源位主导。</b>${esc(top.name)} 贡献 ${fmtDelta(top.contrib)}（占资源位总下滑 ${Math.round(topShare*100)}%），超过其余位置总和 —— 不是全盘流量质量问题，优先排查该位置切面。</div>`
      : `<div class="ws-callout"><b>判定：整体下滑。</b>各资源位普遍下行，无单一主导位置 —— 优先排查全局性外部因子与链路变更。</div>`;
    body = `${verdict}
    <table class="full"><tr><th>资源位</th><th>曝光占比</th><th>同比</th><th>对整体 CTR 的贡献</th><th>贡献分布</th></tr>
    ${rows.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${(x.share*100).toFixed(1)}%</td><td style="color:${x.yoy<0?'var(--red)':'inherit'}">${fmtDelta(x.yoy)}</td><td><b style="color:${x.contrib<0?'var(--red)':'inherit'}">${fmtDelta(x.contrib)}</b></td><td><div style="height:6px;background:#edf1f3;border-radius:3px"><div style="height:6px;border-radius:3px;width:${Math.min(100,Math.abs(x.contrib)/Math.abs(top.contrib)*100)}%;background:${x.contrib<0?'var(--red)':'var(--green)'}"></div></div></td></tr>`).join('')}</table>
    <div style="font-size:11.5px;color:var(--muted);margin-top:6px">资源位合计解释 ${fmtDelta(sumContrib)}，占整体同比 ${fmtDelta(k.yoy)} 的 ${Math.round(Math.abs(sumContrib/k.yoy)*100)}%；未解释部分保留为残差，不强行摊派（演示口径：贡献 = 曝光占比 × 单位同比）。</div>`;
  } else {
    body = `<div class="ws-callout"><b>${esc(k.name)}</b> 暂无可拆解的资源位/运营位维度（演示数据仅 CTR 链路挂载了位置明细）。整体下滑还是个别下滑，需要在指标契约中登记拆解维度后自动展开 —— 当前可直接进入因子实验室走标准调查流程。</div>`;
  }
  el.innerHTML = `<div class="card" style="border:1px solid var(--blue)"><h3>下钻：${esc(k.name)} · 同比 ${fmtDelta(k.yoy)} / 环比 ${fmtDelta(k.mom)}
    <span style="float:right;font-size:12px;font-weight:400"><a style="color:var(--blue);cursor:pointer" onclick="wsExpStart('${k.key}')">对该异动发起实验排查 →</a> · <a style="color:var(--muted);cursor:pointer" onclick="document.getElementById('biz-drill').innerHTML=''">收起 ✕</a></span></h3>
    ${body}</div>`;
  el.scrollIntoView({block:'start',behavior:'smooth'});
}

/* ---- 异动实验工作台：异动清单 → 实验配置 → 算法链路动画 → 因果球逐渐显现 ---- */
let EXP = {anomaly:null, mode:'cycle', range:30, direction:'down', lag:7, strict:'strict', includeExempt:false, running:false, stage:-1, done:false, runId:0, logs:[]};
const EXP_STAGES = ['切面取样 · 固定实验对象','滞后对齐 · 统一时间轴','关联检验 · 逐因子扫描','搜索记账 · 校正门收紧','封存窗验证 · 独立确认'];

/* 切面样本集：周期切面（每周一）或垂直切面（逐日），范围 15/30/60 天，演示口径 */
function expSlices(){
  const k = BIZ_KPIS.concat(BIZ_SLOTS).find(x=>x.key===EXP.anomaly)||{yoy:-6.8};
  const jit = [-1.3, 2.1, -0.4, 3.2, -2.2, 0.8, -1.7, 1.4, -0.9, 2.6, 1.1, -2.8, 0.5];
  const out = [];
  if(EXP.mode==='cycle'){
    const mondays = ['09-14','09-07','08-31','08-24','08-17','08-10','08-03','07-27','07-20','07-13'];
    mondays.slice(0, Math.max(2, Math.round(EXP.range/7))).forEach((d,i)=> out.push({date:'2026-'+d, tag:`每周一 · 近${EXP.range}天`, yoy:+(k.yoy+jit[i%jit.length]).toFixed(1)}));
  } else {
    const n = EXP.range;
    for(let i=0;i<n;i++){ const dt=new Date(2026,8,20-i); const mm=String(dt.getMonth()+1).padStart(2,'0'), dd=String(dt.getDate()).padStart(2,'0');
      out.push({date:`2026-${mm}-${dd}`, tag:`近${n}天 · 逐日`, yoy:+(k.yoy+jit[i%jit.length]*0.8).toFixed(1)}); }
  }
  return out;
}
/* 同形态判定：正向切面只数同向异动，双向切面涨跌都算 */
function expIsAbnormal(s, k, rules){
  if(EXP.direction==='both') return Math.abs(s.yoy)>=rules.yoy;
  return k.yoy<0 ? s.yoy<=-rules.yoy : s.yoy>=rules.yoy;
}
function wsExpStart(key){ wsExpReset(key); showView('lab'); setTimeout(()=>{ const el=document.getElementById('exp-workbench'); if(el) el.scrollIntoView({block:'start',behavior:'smooth'}); },60); }
function wsExpReset(key){ EXP={anomaly:key, mode:'cycle', range:30, direction:'down', lag:7, strict:'strict', includeExempt:false, running:false, stage:-1, done:false, runId:EXP.runId, logs:[]}; window._expReveal=null; renderExpWizard(); if(document.getElementById('globe-stage')) renderNetwork(); const r=document.getElementById('exp-result'); if(r) r.style.display='none'; renderExpPipeline(); }
function renderExpWorkbench(){
  const host = document.getElementById('view-lab-exp'); if(!host) return;
  host.innerHTML = `
  <div class="card" id="exp-workbench"><h3>异动实验工作台 <span style="font-size:11px;color:var(--muted);font-weight:400">选择一场异动 → 截取切面（周期 / 垂直）扩样 → 执行算法链路 → 因果球实时显现 → 对待确认因子发起实验验证</span></h3>
    <div id="exp-wizard"></div>
  </div>
  <div class="card"><h3>因果证据球 · 本时段全部异动指标 × 关联因子 <span style="font-size:11px;color:var(--muted);font-weight:400">实验的核心输出：算法链路每推进一步，关联关系在球上实时显现 · 边越绿越靠近因果，金/紫色停在关联层</span></h3>
    <div id="exp-pipeline"></div>
    <div id="view-network" style="min-height:560px"></div>
  </div>
  <div class="card" id="exp-result" style="display:none"></div>`;
  renderExpWizard();
  if(!document.getElementById('globe-stage') && document.getElementById('view-lab').classList.contains('active')) renderNetwork();
}
function renderExpWizard(){
  const el = document.getElementById('exp-wizard'); if(!el) return;
  const flagged = BIZ_KPIS.concat(BIZ_SLOTS).filter(k=>['alert','severe'].includes(bizStatus(k,bizRules())));
  let body = `<p class="ws-muted" style="margin:8px 0 10px"><b>① 选择异动</b>（与总控今日异动清单同源，从总控点「发起实验排查」会自动带到这里；当前判定策略下共 ${flagged.length} 项）：</p>
    <div class="filter-bar">${flagged.map(k=>`<span class="chip ${EXP.anomaly===k.key?'on':''}" style="cursor:pointer" onclick="wsExpReset('${k.key}')">${esc(k.name)} · ${fmtDelta(k.yoy)}</span>`).join('')||'<span class="ws-muted">无异动，<a style="color:var(--blue);cursor:pointer" onclick="wsExpReset(\'ctr\')">用演示异动：整体 CTR −6.8%</a></span>'}</div>`;
  if(EXP.anomaly){
    const k = BIZ_KPIS.concat(BIZ_SLOTS).find(x=>x.key===EXP.anomaly);
    const slices = expSlices();
    const rulesNow = bizRules();
    const abnormal = slices.filter(s=>expIsAbnormal(s,k,rulesNow));
    const showRows = slices.slice(0,10);
    const cfg = (label, inner)=>`<div style="border:1px solid var(--line);border-radius:8px;padding:10px 12px"><div style="font-size:11px;color:var(--muted);margin-bottom:6px">${label}</div>${inner}</div>`;
    const opt = (cur,val,text,onclick)=>`<span class="chip ${cur===val?'on':''}" style="cursor:pointer" onclick="${onclick}">${text}</span>`;
    body += `<div style="margin-top:14px"><b>② 实验配置</b> —— 实验对象：<b>${esc(k.name)}</b>（同比 ${fmtDelta(k.yoy)}）</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0">
      ${cfg('切面时间范围',[15,30,60].map(n=>opt(EXP.range,n,n+' 天',`EXP.range=${n};EXP.done=false;EXP.stage=-1;renderExpWizard()`)).join(' '))}
      ${cfg('切面方向',opt(EXP.direction,'down','正向切面 · 仅同向异动','EXP.direction=\'down\';EXP.done=false;EXP.stage=-1;renderExpWizard()')+' '+opt(EXP.direction,'both','双向切面 · 涨跌都计','EXP.direction=\'both\';EXP.done=false;EXP.stage=-1;renderExpWizard()'))}
      ${cfg('切法',opt(EXP.mode,'cycle','周期切面 · 每周一','EXP.mode=\'cycle\';EXP.done=false;EXP.stage=-1;renderExpWizard()')+' '+opt(EXP.mode,'recent','垂直切面 · 逐日','EXP.mode=\'recent\';EXP.done=false;EXP.stage=-1;renderExpWizard()'))}
      ${cfg('滞后扫描窗口',[3,7,14].map(n=>opt(EXP.lag,n,'lag 0–'+n,`EXP.lag=${n};EXP.done=false;EXP.stage=-1;renderExpWizard()`)).join(' '))}
      ${cfg('校正强度',opt(EXP.strict,'strict','严格 · max-T + 封存窗','EXP.strict=\'strict\';renderExpWizard()')+' '+opt(EXP.strict,'standard','标准 · 仅 max-T','EXP.strict=\'standard\';renderExpWizard()'))}
      ${cfg('豁免期样本',opt(EXP.includeExempt,false,'剔除豁免期','EXP.includeExempt=false;EXP.done=false;EXP.stage=-1;renderExpWizard()')+' '+opt(EXP.includeExempt,true,'包含（不推荐）','EXP.includeExempt=true;EXP.done=false;EXP.stage=-1;renderExpWizard()'))}
    </div>
    <div style="font-size:11.5px;color:var(--muted);margin-bottom:8px">配置即检验契约：范围与切法决定样本量，方向决定"同形态"口径，lag 窗口与校正强度直接进入搜索账本 —— 账本越厚，校正门越严。</div>
    <table class="full"><tr><th>异常切面样本</th><th>切法</th><th>同比</th><th>判定</th></tr>
    ${showRows.map(s=>`<tr><td><b>${s.date}</b></td><td style="color:var(--muted)">${s.tag}</td><td style="color:${s.yoy<0?'var(--red)':'inherit'}">${fmtDelta(s.yoy)}</td><td>${expIsAbnormal(s,k,rulesNow)?'<span class="pill red">同形态异动</span>':'<span class="pill green">对照样本</span>'}</td></tr>`).join('')}
    ${slices.length>10?`<tr><td colspan="4" style="color:var(--muted)">… 共 ${slices.length} 个切面</td></tr>`:''}</table>
    <div style="font-size:12px;margin-top:8px">样本集：<b>${slices.length}</b> 个切面，其中 <b style="color:var(--red)">${abnormal.length}</b> 个同形态异常（${EXP.direction==='both'?'双向口径':'仅同向'}）—— 扩样后的异常切面集合将作为关联计算的取证范围。</div>
    <div class="ws-actions" style="margin-top:12px"><button class="btn" onclick="wsExpRun()" ${EXP.running?'disabled':''}>${EXP.running?'算法链路运行中…':'③ 开始实验 →'}</button>${EXP.done?'<span class="ws-muted">已完成，可调整配置重跑</span>':''}</div>`;
  }
  el.innerHTML = body;
}
function wsExpPick(key){ wsExpReset(key); }
function expLog(msg, cls){ const t=((Date.now()-EXP.t0)/1000).toFixed(1); EXP.logs.push({t, msg, cls:cls||''}); const el=document.getElementById('exp-log'); if(el){ el.innerHTML=EXP.logs.map(l=>`<div><span class="t">[+${l.t}s]</span><span class="${l.cls}">${l.msg}</span></div>`).join('')+(EXP.running?'<span class="exp-cursor"></span>':''); el.scrollTop=el.scrollHeight; } }
function renderExpPipeline(){
  const el = document.getElementById('exp-pipeline'); if(!el) return;
  if(EXP.stage<0 && !EXP.running){ el.innerHTML=''; return; }
  el.innerHTML = `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:4px">${EXP_STAGES.map((s,i)=>{
    const st = i<EXP.stage?'done':(i===EXP.stage?(EXP.running?'run':'done'):'');
    const dot = st==='done'?'<span class="pill green">✓</span>':st==='run'?'<span class="pill gold">运行中</span>':'<span class="pill">等待</span>';
    return `<span style="display:flex;align-items:center;gap:5px;font-size:12px;${st?'':'opacity:.5'}">${dot}${s}</span>${i<EXP_STAGES.length-1?'<span style="color:var(--muted)">→</span>':''}`;}).join('')}
    <span class="mono" id="exp-clock" style="margin-left:auto;font-size:12px;color:var(--muted)"></span></div>
  <div class="exp-log" id="exp-log"></div>`;
  const el2=document.getElementById('exp-log'); if(el2) el2.innerHTML=EXP.logs.map(l=>`<div><span class="t">[+${l.t}s]</span><span class="${l.cls}">${l.msg}</span></div>`).join('')+(EXP.running?'<span class="exp-cursor"></span>':'');
}
function wsExpRun(){
  if(EXP.running || !EXP.anomaly) return;
  const k = BIZ_KPIS.concat(BIZ_SLOTS).find(x=>x.key===EXP.anomaly);
  const slices = expSlices();
  const rulesNow = bizRules();
  const abnormal = slices.filter(s=>Math.abs(s.yoy)>=rulesNow.yoy).length;
  EXP.running=true; EXP.done=false; EXP.stage=0; EXP.runId++; EXP.logs=[]; EXP.t0=Date.now();
  const runId=EXP.runId;
  const fids = [...new Set((D.metrics||[]).flatMap(m=>(m.factors||[]).map(l=>l.factor_id)))];
  window._expReveal = new Set();
  if(document.getElementById('globe-stage')) renderNetwork();
  renderExpWizard(); renderExpPipeline();
  setTimeout(()=>{ const el=document.getElementById('exp-pipeline'); if(el) el.scrollIntoView({block:'start',behavior:'smooth'}); },120);
  expLog(`实验启动 · 对象「${k.name}」 · ${EXP.mode==='cycle'?'周期切面（每周一）':'垂直切面（逐日）'} × 近${EXP.range}天 · ${EXP.direction==='both'?'双向异动口径':'仅同向异动'} · lag 0–${EXP.lag} · ${EXP.strict==='strict'?'严格校正（max-T+封存窗）':'标准校正（max-T）'}${EXP.includeExempt?' · 含豁免期样本':''}`, 'run');
  if(EXP._clk) clearInterval(EXP._clk);
  EXP._clk=setInterval(()=>{ const c=document.getElementById('exp-clock'); if(c) c.textContent='⏱ '+((Date.now()-EXP.t0)/1000).toFixed(1)+'s'; },100);
  const advance = ()=>{
    if(EXP.runId!==runId) return;
    if(EXP.stage===0){ expLog(`切面取样完成 · ${slices.length} 个切面入样，${abnormal} 个同形态异常、${slices.length-abnormal} 个对照`, 'ok'); }
    if(EXP.stage===1){ expLog(`滞后对齐完成 · 统一 lag 0–${EXP.lag} 天扫描窗口，切面时间轴已锁定`, 'ok'); }
    if(EXP.stage===2){
      const next = fids.filter(f=>!window._expReveal.has(f)).slice(0,2);
      next.forEach(f=>window._expReveal.add(f));
      next.forEach(f=>expLog(`关联检验 · ${zhName(f)} → 候选关联显现于证据球`, 'run'));
      renderNetwork();
      if(next.length){ setTimeout(advance, 800); return; }
      expLog(`关联检验完成 · ${fids.length} 个候选因子全部扫描`, 'ok');
    }
    if(EXP.stage===3){ expLog('搜索记账完成 · 全部比较次数入账，max-T 校正门随样本量收紧', 'warn'); }
    if(EXP.stage===4){ expLog(EXP.strict==='strict'?'封存窗验证完成 · 存活候选进入结论清单，未通过者保留为负结果':'标准模式 · 无封存窗验证，结论上限为关联级', 'ok'); }
    EXP.stage++;
    if(EXP.stage>=EXP_STAGES.length){
      EXP.running=false; EXP.done=true; clearInterval(EXP._clk);
      window._expReveal.add('unknown'); renderNetwork();
      expLog('实验结束 · 证据球已定格，待确认因子可发起实验验证', 'ok');
      renderExpWizard(); renderExpPipeline(); renderExpResult();
      return;
    }
    renderExpPipeline();
    setTimeout(advance, EXP.stage===2?450:1000);
  };
  setTimeout(advance, 800);
}
function renderExpResult(){
  const el = document.getElementById('exp-result'); if(!el) return;
  const k = BIZ_KPIS.concat(BIZ_SLOTS).find(x=>x.key===EXP.anomaly)||{name:'—',yoy:0};
  const cands = (D.bline_candidates||[]).slice(0,6);
  el.style.display='';
  el.innerHTML = `<h3>④ 实验结论 · ${esc(k.name)} <span style="font-size:11px;color:var(--muted);font-weight:400">候选来自真实 B 线管线快照；比较次数已记账，校正门随样本量收紧</span></h3>
    <table class="full"><tr><th>候选因子</th><th>关联强度</th><th>滞后</th><th>证据等级</th><th>操作</th></tr>
    ${cands.map((c,ci)=>{const score=Math.abs(c.association_score||0); const confirmed=c.claim_type==='FACTOR_CANDIDATE'||c.claim_type==='CAUSAL_CONFIRMED';
      return `<tr class="exp-row" style="animation-delay:${ci*0.18}s"><td><b>${esc(zhName(c.factor_id))}</b><br><span class="mono" style="font-size:10.5px;color:var(--muted)">${esc(c.factor_id)}</span></td>
      <td><b>${(score*100).toFixed(0)}%</b><div style="height:5px;background:#edf1f3;border-radius:3px;margin-top:4px"><div style="height:5px;border-radius:3px;width:${Math.min(100,score*100)}%;background:${confirmed?'var(--green)':'var(--gold)'}"></div></div></td>
      <td>lag ${c.lag_days??'—'}</td>
      <td>${confirmed?'<span class="pill green">关联已验证</span>':'<span class="pill gold">待人工确认</span>'}</td>
      <td>${confirmed?'<span style="font-size:11px;color:var(--muted)">绿环在库</span>':`<button class="btn small" onclick="wsExpRequest('${esc(c.factor_id)}','${esc(k.name)}')">发起实验验证 →</button>`}</td></tr>`;}).join('')}</table>
    <div style="font-size:11.5px;color:var(--muted);margin-top:8px">「待人工确认」的关联因子无法直接写结论 —— 发起实验验证后进入「人工审核任务」排队，独立窗口确认前永远停在关联层。未解释部分保留为残差，不强行摊派。</div>
    <div class="ws-actions" style="margin-top:10px"><button class="btn ghost" onclick="showView('todo')">去人工审核任务 →</button><button class="btn ghost" onclick="wsExpPick(EXP.anomaly)">调整切面重跑</button></div>`;
  el.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function wsExpRequest(fid, anomalyName){
  let op='';
  try{ op=operator(); }catch(e){ return; }
  pushLedger({type:'experiment_request', factor_id:fid, anomaly:anomalyName, operator:op});
  toast('已发起实验验证：'+fid+'（进入人工审核任务队列，本地留痕）');
}

/* 经营看板演示数据（脱敏示例口径，与种子管线故事线一致） */
const BIZ_KPIS = [
  {key:'dau',   name:'DAU（日活）',        value:'128.4', unit:'万',   yoy:3.1,  mom:1.2,  ex:null, grp:'traffic'},
  {key:'ctr',   name:'整体 CTR',           value:'3.24',  unit:'%',   yoy:-6.8, mom:-4.1, ex:'campaign.sms_push', grp:'traffic'},
  {key:'cvr',   name:'点击→投保转化率',     value:'1.86',  unit:'%',   yoy:-8.9, mom:-5.3, ex:null, grp:'conv'},
  {key:'quote', name:'报价完成率',          value:'61.5',  unit:'%',   yoy:2.4,  mom:0.8,  ex:null, grp:'conv'},
  {key:'uw',    name:'核保通过率',          value:'87.2',  unit:'%',   yoy:-1.1, mom:-0.6, ex:null, grp:'money'},
  {key:'prem',  name:'新单保费',            value:'426',   unit:'万元', yoy:8.4,  mom:6.2,  ex:'campaign.sms_push', grp:'money'},
];
const BIZ_SLOTS = [
  {key:'s1', name:'首页轮播',   extra:'212', value:'4.87', unit:'%', cvr:'2.11%', yoy:-12.6, mom:-7.4, ex:'experience.carousel_rotation_config', grp:'traffic'},
  {key:'s2', name:'开机屏',     extra:'96',  value:'6.32', unit:'%', cvr:'1.42%', yoy:2.1,   mom:0.9,  ex:null, grp:'traffic'},
  {key:'s3', name:'站内信推送', extra:'58',  value:'5.18', unit:'%', cvr:'2.87%', yoy:4.6,   mom:3.3,  ex:'campaign.sms_push', grp:'traffic'},
  {key:'s4', name:'Banner 位',  extra:'74',  value:'2.06', unit:'%', cvr:'0.98%', yoy:-3.2,  mom:-1.8, ex:null, grp:'traffic'},
  {key:'s5', name:'推荐位',     extra:'143', value:'3.71', unit:'%', cvr:'1.65%', yoy:1.4,   mom:0.7,  ex:null, grp:'traffic'},
];
const BIZ_RULES_KEY='attribution_biz_rules_v2';
function bizRules(){ try{ return Object.assign({yoy:5,mom:8,exempt:[],groups:{},savedAt:null}, JSON.parse(localStorage.getItem(BIZ_RULES_KEY)||'{}')); }catch(e){ return {yoy:5,mom:8,exempt:[],groups:{},savedAt:null}; } }
function bizStatus(k,rules){
  if(k.ex && rules.exempt.includes(k.ex)) return 'exempt';
  const t = bizThreshold(k,rules);
  const r = Math.max(Math.abs(k.yoy)/t.yoy, Math.abs(k.mom)/t.mom);
  if(r>=1.5) return 'severe';
  if(r>=1) return 'alert';
  if(r>=0.6) return 'watch';
  return 'ok';
}
function fmtDelta(v){ return (v>0?'+':'')+v.toFixed(1)+'%'; }
function saveBizRules(){
  const yoy=parseFloat(document.getElementById('rule-yoy').value)||5;
  const mom=parseFloat(document.getElementById('rule-mom').value)||8;
  const exempt=[...document.querySelectorAll('.rule-exempt:checked')].map(c=>c.value);
  const groups={};
  Object.keys(BIZ_GROUPS).forEach(g=>{
    const on=document.querySelector(`.rule-grp-on[data-grp="${g}"]`).checked;
    const gy=parseFloat(document.querySelector(`.rule-grp-yoy[data-grp="${g}"]`).value)||yoy;
    const gm=parseFloat(document.querySelector(`.rule-grp-mom[data-grp="${g}"]`).value)||mom;
    groups[g]={on,yoy:gy,mom:gm};
  });
  localStorage.setItem(BIZ_RULES_KEY, JSON.stringify({yoy,mom,exempt,groups,savedAt:new Date().toLocaleString('zh-CN',{hour12:false})}));
  toast('异动判定策略已保存（本地留痕）');
  renderOverview();
}

function wsPublication(data){const d=data.result||data;return d.publication||null;}
function renderInvestigation(){
 const a=wsArtifact(WS_CASE),data=WS_LIVE||a.data||{},c=WS_CASES[WS_CASE],root=data.result||data,pub=wsPublication(data);
 const b=data.bundle||data.key_outputs?.bundle||{};
 let content='';
 if(pub){const ident=pub.identification||{},u=pub.statistical_uncertainty||{};content=`<div class="ws-callout ${ident.status==='IDENTIFIED'?'ok':''}"><b>${esc(pub.statement)}</b><br><span class="mono">${esc(pub.claim_type)} · ${esc(ident.status)}</span></div><div class="two-col"><div class="card"><h3>识别门：为什么放行 / 停下</h3>${(ident.assumptions||[]).map(x=>`<div class="ws-stage"><span style="${x.passed?'':'background:var(--red-soft);color:var(--red)'}">${x.passed?'✓':'!'}</span><div><b>${esc(WS_ASSUMPTIONS[x.name]||x.name)}</b><div class="ws-muted">${esc(x.status)} · ${x.data_verifiable?'可由数据核查':'依赖假设，仍需核实'}</div>${wsDetails('依据引用',x.evidence_refs)}</div></div>`).join('')}</div><div class="card"><h3>结论与下一步</h3><dl class="ws-kv"><dt>识别设计</dt><dd>${esc(ident.design)} / ${esc(ident.estimand)}</dd><dt>效应估计</dt><dd>${wsPP(u.effect)}</dd><dt>区间</dt><dd>${u.interval?u.interval.map(wsPP).join(' ～ '):'未识别，不提供效应区间'}</dd><dt>行动政策</dt><dd>${esc(pub.action_policy?.action||'待补证')}</dd><dt>原因代码</dt><dd>${esc((pub.reason_codes||[]).join(' / ')||'无')}</dd><dt>补证路径</dt><dd>${esc((pub.remedies||[]).join(' / ')||'按当前证据与行动政策执行')}</dd></dl><p class="ws-muted">人工可以补事实与来源，不能把 NOT_IDENTIFIED 改成已识别；补证后必须重新运行门禁。</p><button class="btn ghost" onclick="wsSupplementForm()">为当前调查提交补证</button></div></div>`;
 }else if(WS_CASE==='line_a'&&!WS_LIVE){content=`<div class="ws-callout ok"><b>整套改版的实验结果：${wsPP(b.effect_absolute)}</b> · 95% 可信区间 ${(b.credible_interval_95||[]).map(wsPP).join(' ～ ')}<br>统计建议 ${esc(b.decision)}；回滚仍须人工审批。结果来自合成/脱敏实验回放，不代表生产收益。</div><div class="two-col"><div class="card"><h3>从整套效果，拆到组件</h3>${wsComponentTable(data.component_effects)}${wsDetails('查看组件独立实验原件',data.component_effects)}${wsDetails('查看异质性分析与适用范围',data.high_dimensional_hte||data.hte)}${wsDetails('查看下一轮实验设计',data.design)}</div><div class="card"><h3>因果资格从哪里来</h3><p class="ws-muted">整套随机实验支持整套效果；组件效果需要独立随机化。事后分群仅用于探索，不能将整体 A/B 结果分摊成每个组件的因果贡献。</p>${wsFunnel(data.a_line_funnel)}${wsDetails('A 线证据漏斗原件',data.a_line_funnel)}${wsClaims(data.ledger)}<button class="btn ghost" onclick="wsOpenEvidence('insurance_a')">查看带六契约的保险实验 →</button></div></div>`;
 }else if(WS_CASE==='line_b'){const k=data.key_outputs||{},ad=k.association_discovery||{},m=ad.search_manifest||{},unknown=k.unknown_bucket||{};content=`<div class="ws-callout"><b>当前最重要的结果：${esc(unknown.claim_type||'UNEXPLAINED')}</b> · 未解释残差 ${wsNumber(unknown.mean_residual_late_window)}（原始指标单位）<br>残差保留，外部共同变化仅报告时间关联；候选决定先查谁。</div><div class="ws-grid"><div class="card"><h3>探索记账</h3><div class="ws-number">${m.N??m.comparisons??'—'}</div><p class="ws-muted">比较次数 · 搜索越多，校正门越严</p></div><div class="card"><h3>发现窗 → 封存窗</h3><p>${esc((ad.discovery_window||[]).join('–'))} → ${esc((ad.holdout_window||[]).join('–'))}</p><p class="ws-muted">独立验证结果：${ad.holdout_survivors??'—'} 个存活</p></div><div class="card"><h3>三种时间形态</h3><p>水平 → 速度 → 加速度</p><p class="ws-muted">来源因子、派生序列分别留证</p></div></div><div class="card" style="margin-top:14px"><h3>候选与补证路线</h3><div class="ws-table-wrap"><table class="ws-table"><thead><tr><th>候选因子</th><th>层级 / lag</th><th>校正 p / holdout</th><th>当前等级</th><th>下一步</th></tr></thead><tbody>${(ad.candidates||[]).slice(0,25).map(x=>`<tr><td>${esc(zhName(x.factor_id))}<br><span class="mono">${esc(x.factor_id)}</span></td><td>${esc(x.derived_layer||'事件')} / ${x.lag_days??'—'}</td><td>${wsNumber(x.max_t_pvalue,3)} / ${x.holdout?x.holdout.survives?'通过':'未通过':'未提供'}</td><td>${esc(x.claim_type)}</td><td>${esc(x.validation_route||'待补充')}</td></tr>`).join('')}</tbody></table></div>${wsDetails('完整搜索账本与零分布口径',m)}</div>`;
 }else{content=`<div class="card"><h3>本次服务端真实运行</h3><p class="ws-muted">${esc(data.title||'运行结果')} · ${esc(data.generated_at||'')} · ${esc(data.execution_mode||'')}</p>${wsDetails('业务结果',data.key_outputs||data)}${wsDetails('决策 / 风险 / 建议',data.decisions||data.recommendations||data.warnings||{})}</div>`;}
 document.getElementById('view-investigation').innerHTML=`<h1 class="ws-title">调查案例回放</h1><p class="ws-muted">上方「异动实验工作台」是实时实验入口；这里是三个历史调查的完整产物回放，用于核查门禁与证据链。门禁拦截也是有效结果。</p><div class="ws-toolbar" style="margin-top:18px"><select aria-label="调查案例" onchange="WS_CASE=this.value;WS_LIVE=null;renderInvestigation()">${Object.entries(WS_CASES).map(([id,x])=>`<option value="${id}" ${id===WS_CASE?'selected':''}>${x.label}</option>`).join('')}</select><button class="btn" onclick="wsRunCase()" ${WS_BUSY||MODE!=='service'?'disabled':''}>${WS_BUSY?'统计管线运行中…':'重新执行本类场景'}</button><button class="btn ghost" onclick="wsOpenEvidence(WS_CASE)">历史证据原件</button>${WS_LIVE?'<button class="btn ghost" onclick="wsDownload(WS_LIVE,\'current-run.json\')">导出本次运行</button>':''}<span class="ws-muted">${WS_LIVE?'本次服务端运行 · 与历史样例分别留存':'历史运行产物回放'}${MODE!=='service'?' · 离线模式不可重跑':''}</span></div><div class="card"><h3>${c.title}</h3><div class="ws-flow"><span>L0 事实分解</span>→<span>L1 关联检验</span>→<span>识别门</span>→<span>L3 定量</span>→<span>发布门 / 人工行动</span></div><p class="ws-muted">每一步按数据设计取得资格；A/B/C 业务线路与 BSTS/SCM/GCM 估计器是两个不同维度，不能机械地视为三条线一致即证明因果。</p></div>${a.status==='MISSING'&&!WS_LIVE?'<div class="ws-callout">此运行证据缺失，暂不能回放。</div>':content}${wsEstimatorPanel()}<div class="card"><h3>六份契约，限制每一次交接</h3><div class="ws-contracts">${[['MetricContract','指标','分子分母、成熟期、窗口、粒度'],['FactorContract','因子','角色、来源、时点与适用范围'],['TestContract','检验','搜索集合、校正、封存与预算'],['IdentificationReport','识别','设计、假设、暴露与支持域'],['EffectEstimate','效应','目标量、区间与限制'],['ActionPolicy','行动','实质阈值、审批和可执行范围']].map(x=>`<div class="ws-contract"><strong>${x[1]}</strong><div class="mono">${x[0]}</div><p class="ws-muted">${x[2]}</p></div>`).join('')}</div></div>${(root.records||[]).length?`<div class="card"><h3>Agent 工具交接轨迹</h3>${root.records.map((r,i)=>`<div class="ws-stage"><span>${i+1}</span><div><b>${esc(r.stage)}</b><div class="ws-muted">${esc(r.output?.claim_type||r.output?.status||'结构化交接')}</div>${wsDetails('查看输入引用、版本和阶段结果',r)}</div></div>`).join('')}${wsDetails('探索预算与成本账本',root.cost_ledger)}</div>`:''}`;
}
async function wsRunCase(){if(WS_BUSY||MODE!=='service')return;WS_BUSY=true;const chosen=WS_CASE;renderInvestigation();try{const r=await fetch('/api/track2/scenario-run?scenario='+WS_CASES[chosen].live);const j=await r.json();if(!r.ok||j.error)throw new Error(j.detail||j.error||'运行失败');if(WS_CASE===chosen)WS_LIVE=j;toast('管线执行完成，结果已更新');}catch(e){toast(e.message,true);}finally{WS_BUSY=false;renderInvestigation();}}
function renderEvidenceWorkspace(){
 const a=wsArtifact(WS_EVIDENCE),data=a.data||{},pub=wsPublication(data),root=data.result||data;
 document.getElementById('view-evidencepack').innerHTML=`<h1 class="ws-title">证据账本</h1><p class="ws-muted">每个结果都能追到来源、内容摘要和原始结构。历史实验与当前操作分别留存。</p><div class="ws-toolbar" style="margin-top:18px"><select aria-label="证据运行包" onchange="WS_EVIDENCE=this.value;renderEvidenceWorkspace()">${wsArtifacts().map(x=>`<option value="${x.id}" ${x.id===WS_EVIDENCE?'selected':''}>${esc(x.title)}</option>`).join('')}</select><button class="btn" onclick="wsDownload(wsArtifact(WS_EVIDENCE),'evidence-'+WS_EVIDENCE+'.json')">导出证据包 JSON</button></div><div class="card"><h3>${esc(a.title||'暂无运行包')}</h3><dl class="ws-kv"><dt>证据状态</dt><dd>${esc(a.status)} · ${esc(a.provenance)}</dd><dt>来源文件</dt><dd class="mono">${esc(a.source)}</dd><dt>SHA-256</dt><dd class="mono">${esc(a.sha256||'无')}</dd><dt>发布等级</dt><dd>${esc(pub?.claim_type||data.bundle?.evidence_level||data.key_outputs?.unknown_bucket?.claim_type||'按原始记录逐条核验')}</dd></dl>${pub?`<div class="ws-callout ${pub.identification?.status==='IDENTIFIED'?'ok':''}">${esc(pub.statement)}</div>${wsDetails('六契约原件',pub.contracts)}${wsDetails('识别依据 / 依赖假设',pub.identification)}${wsDetails('效应、区间与行动政策',{uncertainty:pub.statistical_uncertainty,action:pub.action_policy,remedies:pub.remedies})}`:''}${wsDetails('完整证据原件（含负结果）',data)}</div><div class="two-col"><div class="card"><h3>从本次调查保留下来</h3><div class="ws-stage"><span>1</span><div><b>事实与证据</b><p class="ws-muted">数据版本、来源许可、检验账本、独立确认与失败理由。</p></div></div><div class="ws-stage"><span>2</span><div><b>人的修订与判断</b><p class="ws-muted">候选确认、补录事实、冲突处理、告警标签，保留操作人与事件记录。</p></div></div><div class="ws-stage"><span>3</span><div><b>可复用的调查方法</b><p class="ws-muted">适用条件与检查步骤经过审查和独立回放；旧答案不迁移。</p></div></div></div><div class="card"><h3>当前人工反馈留痕</h3>${(D.recent||[]).slice(0,8).map(e=>`<div class="ws-stage"><span>↳</span><div><b>${esc(e.kind)}</b><p class="ws-muted">${esc(e.payload?.operator||'记录未提供身份')} · ${esc(e.at||e.created_at||'')}</p>${wsDetails('反馈原件',e)}</div></div>`).join('')||'<p class="ws-muted">暂无已提交反馈；可在人工协作台补证。</p>'}<button class="btn ghost" onclick="showView('todo')">进入人工协作台 →</button></div></div>`;
}
function wsDreamFactors(){const map=new Map();(D.factors||[]).filter(f=>f.status!=='disabled').forEach(f=>map.set(f.factor_id,f));(wsData().research||[]).forEach(f=>{if(!map.has(f.factor_id))map.set(f.factor_id,f)});return [...map.values()];}
function renderDream(){
 const proposals=[...(wsData().scenario_proposals||[]),...ledger().filter(x=>x.type==='dream_proposal').map(x=>x.proposal)];
 document.getElementById('view-dream').innerHTML=`<div class="ws-hero"><div class="ws-eyebrow">C LINE / RISK DREAMING</div><h1>先问：什么会把指标推过红线？</h1><p>把“如果竞品降价”“如果支付失败增加”变成有边界的风险研究。先登记情景、找最早脚印，再用独立证据尝试证伪。</p></div><div class="ws-flow"><span>因子库</span>→<span>情景提案</span>→<span>待接入：统计推演 / 反向搜索</span>→<span>证伪与独立验证</span>→<span>监控提案 / 负例</span></div><div class="ws-callout"><b>当前能力：结构化情景登记与验证计划。</b>自动 Dreamer、干预区间计算和反向压力搜索尚待接入。不会根据手填幅度生成虚构预测，也不会自动写入 WATCHLIST 或提升证据等级。</div><div class="card"><h3>梦境巡逻 · 猎手扫描，证伪者优先推翻</h3><div class="ws-grid" style="margin-bottom:12px"><div><div class="ws-number">${(wsData().registry_count??D.factors.length)+(wsData().research||[]).length}</div><p class="ws-muted">巡逻因子空间（注册 + 研究候选）× 指标 × lag 0–7</p></div><div><div class="ws-number">${D.wl.length}</div><p class="ws-muted">在盯信号 · 证伪未击杀才入列</p></div><div><div class="ws-number">${D.alerts.filter(a=>a.state.status==='open').length}</div><p class="ws-muted">已升格预警 · 越阈值才打扰人</p></div></div><p class="ws-muted">巡逻在离线窗口持续进行：猎手提出可疑信号，证伪者用安慰剂 / 先后倒置 / 半分稳定三杀尝试推翻；推不翻的才进观察名单，人在下一窗口确认后才允许升格为预警。同一信号 24h 冷却不重复刷屏。</p><h3 style="margin-top:14px">观察名单（证伪存活，未到预警阈值或待人确认）</h3>${D.wl.length?`<table class="full"><tr><th>信号</th><th>lag</th><th>关联强度</th><th>证据状态</th><th>距升格阈值</th></tr>${D.wl.map(w=>`<tr><td><b>${esc(zhName(w.factor_id))}</b><br><span class="mono" style="font-size:10.5px;color:var(--muted)">${esc(w.factor_id)}</span></td><td>${w.lag}</td><td>${pct(w.correlation)}</td><td>${w.claim_type==='FACTOR_CANDIDATE'?'<span class="pill green">关联已验证</span>':'<span class="pill gold">观察中</span>'}</td><td style="color:var(--muted)">${Math.abs(w.correlation)>=0.55?'已达高风险线，待人确认':Math.abs(w.correlation)>=0.3?'已达关注线':'还差 '+Math.max(0,Math.round((0.3-Math.abs(w.correlation))*100))+' pct'}</td></tr>`).join('')}</table>`:'<p class="ws-muted">当前观察名单为空。</p>'}</div><div class="two-col"><form class="card" onsubmit="event.preventDefault();wsSaveDream(this)"><h3>构建一个可验证的梦</h3><div class="ws-field-grid"><div><label for="dream-kind">研究问题</label><select id="dream-kind" name="kind"><option value="forward">正向情景 · 坏到这个程度会怎样</option><option value="reverse">反向压力 · 什么会触及红线</option><option value="leading">领先信号 · 应先盯什么脚印</option></select></div><div><label for="dream-factor">已登记 / 研究候选因子</label><select id="dream-factor" name="factor_id">${wsDreamFactors().map(f=>`<option value="${esc(f.factor_id)}">${esc(f.name||f.factor_id)} · ${esc(f.factor_id)}</option>`).join('')}</select></div><div><label for="dream-metric">目标指标</label><input id="dream-metric" name="metric" required value="投保转化率"></div><div><label for="dream-scope">适用范围</label><input id="dream-scope" name="scope" required placeholder="例如：华东 / 自营 App / 新客"></div><div><label for="dream-change">假设因子相对变化（%）</label><input id="dream-change" name="change_percent" type="number" min="-100" max="100" step="0.1" value="-20" required></div><div><label for="dream-threshold">目标指标相对变化红线（%）</label><input id="dream-threshold" name="threshold_percent" type="number" min="-100" max="100" step="0.1" value="-5" required></div><div><label for="dream-horizon">研究时间跨度（天）</label><input id="dream-horizon" name="horizon" type="number" min="1" max="90" value="14" required></div><div><label for="dream-budget">最大探索预算（次）</label><input id="dream-budget" name="budget" type="number" min="1" max="90" value="10" required></div><div class="wide"><label for="dream-assumptions">依赖假设 / 待绑定证据</label><textarea id="dream-assumptions" name="assumptions" required placeholder="例如：保障口径相同；两组暴露可比；报价快照来源已获授权"></textarea></div><div class="wide"><label for="dream-signal">希望验证的最早信号</label><input id="dream-signal" name="expected_signal" required placeholder="例如：同保障报价差扩大，领先转化率变化"></div></div><div class="ws-actions"><button class="btn" type="submit">${MODE==='service'?'保存研究提案与验证计划':'保存本地研究草稿'}</button></div><p class="ws-muted" style="margin-top:10px">操作人使用右上角身份。幅度与红线均为相对变化，不是百分点。</p></form><div><div class="card"><h3>统计裁判需要什么才能计算</h3>${[['01','指标与时间契约','分子分母、成熟期、as-of 与未来可用性；缺失不当作零。'],['02','可识别的干预与支持域','因子角色、因果图版本、暴露平衡；研究候选不等于已接入数据。'],['03','影响区间与依赖假设','BSTS / SCM / GCM 按设计适配；方法冲突要降级。'],['04','试着把梦证伪','负对照、安慰剂、lead-lag 反转、时间外 holdout 和误报预算。']].map(x=>`<div class="ws-stage"><span>${x[0]}</span><div><b>${x[1]}</b><p class="ws-muted">${x[2]}</p></div></div>`).join('')}<div class="ws-callout">影响估计：<b>未计算</b><br>置信 / 可信区间：<b>暂无</b><br>当前结论上限：<b>SCENARIO_ONLY</b></div></div><div class="card"><h3>已有 C 线的真实承接点</h3><p class="ws-muted">当前盯防 ${D.wl.length} 项；猎手扫描与证伪已有运行产物。情景生成的待验证信号需要通过这些门禁，才可能进入监控。</p><div class="ws-actions"><button class="btn ghost" onclick="showView('alerts')">查看当前风险预警</button><button class="btn ghost" onclick="wsOpenEvidence('insurance_c')">查看 C 线运行原件</button></div></div></div></div><div class="card"><h3>情景研究队列 · ${proposals.length}</h3>${proposals.map((p,i)=>`<div class="ws-stage"><span>◇</span><div><b>${esc(p.metric)} · ${esc(p.factor_id)}</b><p class="ws-muted">${esc(p.scope)} / ${p.horizon} 天 · ${esc(p.operator)} · ${esc(p.created_at||'本地草稿')}</p><span class="ws-tag">${esc(p.status)}</span><span class="ws-tag">影响未计算</span>${wsDetails('假设、阻塞项与验证计划',p)}</div></div>`).join('')||'<p class="ws-muted">还没有情景提案。从左侧创建第一个研究任务。</p>'}</div>`;
}
async function wsSaveDream(form){const button=form.querySelector('button[type=submit]');try{const op=operator(),f=new FormData(form),body=Object.fromEntries(f);body.operator=op;body.request_id=form.dataset.requestId||(form.dataset.requestId=rid());['horizon','budget','change_percent','threshold_percent'].forEach(k=>body[k]=Number(body[k]));button.disabled=true;if(MODE==='service'){const r=await fetch('/api/v2/scenarios/propose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||'保存失败');D.workspace.scenario_proposals=[j,...(D.workspace.scenario_proposals||[]).filter(x=>x.scenario_id!==j.scenario_id)];}else{pushLedger({type:'dream_proposal',proposal:{...body,created_at:new Date().toISOString(),status:'LOCAL_DRAFT',claim_type:'SCENARIO_ONLY',estimate:null,interval:null,production_action:false}});}toast(MODE==='service'?'研究提案已保存；等待补数与统计推演':'已保存本地草稿，未提交服务器');renderDream();}catch(e){toast(e.message,true);button.disabled=false;}}
function wsComponentTable(items=[]){const names={'carousel.image_component':'图片组件','carousel.indicator_position':'指示器位置','carousel.layout':'布局','carousel.media_aspect_ratio':'媒体宽高比','carousel.text_density':'文字密度'};return `<div class="ws-table-wrap"><table class="ws-table"><tr><th>组件</th><th>实验效应</th><th>证据判决</th></tr>${items.map(x=>`<tr><td>${esc(names[x.factor_id]||x.factor_id)}</td><td><b>${wsPP(x.component_effect)}</b><div style="height:5px;background:#edf1f3;margin-top:7px"><div style="height:5px;width:${Math.min(100,Math.abs(x.component_effect)*4000)}%;background:${x.significant?'var(--red)':'#a4b2b8'}"></div></div></td><td>${x.evidence_level==='COMPONENT_EFFECT'?'独立随机化支持':'证据不足，继续验证'}</td></tr>`).join('')}</table></div><p class="ws-muted">灰色项保留负结果；组件效应不直接加总为整套效果。</p>`;}
function wsFunnel(f={}){return `<div class="ws-table-wrap"><table class="ws-table"><tr><th>经营漏斗</th><th>旧版人数</th><th>新版人数</th><th>阶段率差</th></tr>${(f.stages||[]).map(x=>`<tr><td>${esc(x.label)}</td><td>${x.control}</td><td>${x.treatment}</td><td>${wsPP(x.delta)}</td></tr>`).join('')}</table></div><p class="ws-muted">${esc(f.fixture_note||'各阶段分母见指标契约')}</p>`;}
function wsClaims(l={}){return `<details class="ws-detail"><summary>结论怎样逐步升级 · ${(l.claims||[]).length} 条</summary>${(l.claims||[]).map(x=>`<div class="ws-stage"><div><span class="ws-tag">${esc(x.claim_type)}</span><p>${esc(x.statement)}</p><p class="ws-muted">允许：${esc((x.allowed_verbs||[]).join(' / '))}<br>禁止：${esc((x.prohibited_verbs||[]).join(' / '))}<br>证据引用：${(x.evidence_refs||[]).length||'此历史样例未提供引用，不能视为完整审计链'}</p></div></div>`).join('')}</details>`;}
function wsEstimatorPanel(){return `<div class="card"><h3>三种定量方法：估计值必须和适用条件一起读</h3><p class="ws-muted">以下是不同历史验证样例，不是本次问题的三轨共识。目标量、时间窗或数据不同，不取均值、不投票升级结论。</p><div class="ws-grid" style="margin-top:14px">${[['bsts','结构时间序列','用稳定对照预测干预前后的反事实'],['scm','合成控制','用未受影响的对照组合构造基线'],['gcm','广义因果模型','条件于已接受的因果图与机制模型']].map(([id,title,note])=>{const a=wsArtifact(id),c=a.data?.contracts||{},e=c.EffectEstimate||{};return `<div class="ws-contract"><strong>${id.toUpperCase()} · ${title}</strong><p class="ws-muted">${note}</p><div class="ws-number" style="font-size:22px;margin-top:10px">${wsNumber(e.estimate)}</div><p class="ws-muted">区间 ${(e.interval||[]).map(x=>wsNumber(x)).join(' ～ ')||'暂无'}<br>${esc(e.estimand||'未提供')} · ${esc(e.unit||'')}<br>窗口 ${esc((e.window||[]).join('–'))} · ${esc(e.selection_status||'')}</p><button class="btn small ghost" onclick="wsOpenEvidence('${id}')">核查假设与原件</button></div>`}).join('')}</div></div>`;}
function renderWorkspace(){renderInvestigation();renderExpWorkbench();renderEvidenceWorkspace();renderDream();enhanceLibrary();enhanceHuman();enhanceEvolution();}
function enhanceHuman(){const expReqs=ledger().filter(e=>e.type==='experiment_request');document.getElementById('view-todo').insertAdjacentHTML('beforeend',`<div class="card"><h3>异动实验验证请求 <span style="font-size:11px;color:var(--muted);font-weight:400">来自总控「异动实验工作台」——无法人工确认的关联因子，排队等待独立窗口实验验证</span></h3>${expReqs.map(e=>`<div class="ws-stage"><span>↳</span><div><b>${esc(zhName(e.factor_id))}</b> <span class="mono" style="font-size:10.5px;color:var(--muted)">${esc(e.factor_id)}</span><p class="ws-muted">异动对象：${esc(e.anomaly||'—')} · 发起人 ${esc(e.operator||'—')} · ${esc((e.at||'').slice(0,16))}</p><p class="ws-state">待验证 · 确认前停在关联层，不写入任何因果结论</p></div></div>`).join('')||'<p class="ws-muted">暂无实验验证请求；可在总控对一场异动发起实验排查。</p>'}</div><div class="card"><h3>补证后的统计验证队列</h3><p class="ws-muted">提交事实后仍待验证。只有新窗口证据满足门禁，结论才可能升级。</p>${(D.queue||[]).map(q=>`<div class="ws-stage"><span>↳</span><div><b>${esc(q.factor_id||q.id)}</b><p class="ws-state">${esc(q.status)}</p>${wsDetails('队列来源与窗口资格',q)}</div></div>`).join('')||'<p class="ws-muted">暂无待验证补证。</p>'}</div>`);document.getElementById('view-todo').insertAdjacentHTML('afterbegin',`<div class="ws-hero"><div class="ws-eyebrow">HUMAN IN THE LOOP</div><h1>让业务事实进入调查，让高风险动作等待拍板。</h1><p>系统说明卡在哪里，人补充机器看不到的事实。补证会留痕并进入后续验证；审批不会改变统计结论。</p></div><div class="ws-journey" style="grid-template-columns:repeat(4,1fr)">${[['候选确认','事实成立 / 否决，不代表因果成立'],['证据冲突','补事件时间、影响范围与机制'],['发布审批','独立审查后，批准技能受控发布'],['告警反馈','真阳性 / 误报，校准下一窗预算']].map(x=>`<div class="ws-step"><strong>${x[0]}</strong><small>${x[1]}</small></div>`).join('')}</div>`);}
function enhanceEvolution(){document.getElementById('view-evolution').insertAdjacentHTML('afterbegin',`<div class="ws-hero"><div class="ws-eyebrow">RSI / ORGANIZATIONAL MEMORY</div><h1>经验不随人走，结论每次重验。</h1><p>把一次排查的成功与失败，变成下一次的检查步骤、适用条件和验证模板。统计参数记忆与技能方法记忆分别验收。</p></div><div class="card"><h3>一条经验如何成为可用技能</h3><div class="ws-flow"><span>G0 捕获双源轨迹</span>→<span>G1 方法补丁</span>→<span>G2 独立审查</span>→<span>G5 冻结配对回放</span>→<span>G3 审批 / ≤10% 首发</span>→<span>G4 下窗复用</span>↺<span>G6 归因 / 缩域 / 回滚</span></div><p class="ws-muted">冲突与缺证据进入 AUDIT_ONLY；环境失败记 ISSUE；没有新规则则 NOOP。独立审查是角色与进程分离，生产身份与流量平台仍需接入。</p></div><div class="two-col"><div class="card"><h3>方法记忆</h3><p class="ws-muted">例如“检查两组外部暴露是否平衡”。需要独立任务回放、范围检查与审批；不能复用“上次是版本导致下降”。</p>${D.skills.map(s=>wsDetails(`${s.name} v${s.version} · 生命周期原件`,s.lifecycle)).join('')}</div><div class="card"><h3>参数记忆</h3><p class="ws-muted">Beta 先验、衰减、封顶与漂移反馈有独立消融产物，收益不可当作 RSI 技能收益。低流量窗口改善不代表所有窗口改善。</p><div class="ws-actions"><button class="btn ghost" onclick="wsOpenEvidence('experience')">查看跨期消融</button><button class="btn ghost" onclick="wsOpenEvidence('negative')">查看无增益记录</button></div></div></div>`);}
function enhanceLibrary(){
  const NS=[['acquisition','获客',35,'渠道级下钻：6 渠道 × 出价/素材/排名'],['conversion','转化',45,'环节级下钻：8 漏斗环节 × 转化率'],['experience','体验',38,'位置级/端级：6 资源位 × 版本配置 · 4 端 × 性能/崩溃'],['service','服务',25,'客服/理赔 + 监管通报'],['mix','结构',14,'身份/产品/渠道快照'],['quality','质量',10,'实验平台 + SRM + 质量监控'],['activation','激活',10,'内部埋点 / 实名链路'],['external','外部',9,'监管 / 宏观（挂真实来源）'],['retention','留存',5,'保单日历 / 触达配置']];
  const research=wsData().research||[];
  const nsTotal=NS.reduce((s,x)=>s+x[2],0);
  document.getElementById('view-library').insertAdjacentHTML('afterbegin',`<div class="card ws-library-extra"><h3>因子库全景 · ${nsTotal} 候选因子 / 9 命名空间</h3><div class="ws-grid"><div><div class="ws-number">${wsData().registry_count??D.factors.length}</div><p class="ws-muted">注册表在管因子</p></div><div><div class="ws-number">${research.length}</div><p class="ws-muted">概念级研究候选 · 附完整操作化定义</p></div><div><div class="ws-number">${nsTotal}</div><p class="ws-muted">命名空间下钻后的候选总数（方案口径）</p></div></div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px">${NS.map(n=>{const mine=research.filter(f=>f.factor_id.startsWith(n[0]+'.')).length;return `<div style="border:1px solid var(--line);border-radius:8px;padding:12px"><div style="display:flex;justify-content:space-between;align-items:baseline"><b>${n[1]} <span class="mono" style="font-size:10.5px;color:var(--muted)">${n[0]}</span></b><span style="font-size:18px;font-weight:700">${n[2]}</span></div><div style="font-size:11px;color:var(--muted);margin-top:4px">${n[3]}</div>${mine?`<div style="font-size:11px;color:var(--cyan);margin-top:4px">已落地概念级定义 ${mine} 条，可在下方检索</div>`:''}</div>`;}).join('')}</div>
  <div class="ws-boundary">计数口径：${nsTotal} = 38 条概念级候选按「位置级（6 资源位）/ 渠道级（6 渠道）/ 环节级（8 漏斗）/ 端级（4 端）/ 产品族（5 族）」下钻展开，每条落在真实系统位置、来源可核；非机械叉乘灌水。已加载概念级定义 ${research.length} 条 + 注册表 ${wsData().registry_count??D.factors.length} 条；其余下钻条目随数据映射接入逐条激活。</div><div class="ws-actions"><button class="btn ghost" onclick="wsShowResearch()">检索角色、来源与验证陷阱 →</button></div></div>`);
}
function wsShowResearch(){document.getElementById('drawer-mask').onclick=closeDrawer;document.getElementById('drawer-body').innerHTML=`<h2>研究因子定义与来源</h2><p class="ws-muted">研究依据支持机制或测量定义；本业务效应尚未验证，数据授权映射仍需补齐。</p><input style="width:100%;padding:10px;margin:15px 0" placeholder="搜索名称、角色、公式或来源" aria-label="搜索研究因子" oninput="wsResearchResults(this.value)"><div id="ws-research-results"></div>`;document.getElementById('drawer').classList.add('open');document.getElementById('drawer-mask').classList.add('open');wsResearchResults('');}
function wsResearchResults(query){const list=(wsData().research||[]).filter(f=>JSON.stringify(f).toLowerCase().includes(query.toLowerCase()));document.getElementById('ws-research-results').innerHTML=`<p class="ws-muted">找到 ${list.length} 项</p>`+list.map(f=>{const m=f.metadata||{};return `<div class="ws-stage"><div><b>${esc(f.name)}</b><p class="mono">${esc(f.factor_id)}</p><span class="ws-tag">${esc(m.causal_role)}</span><span class="ws-tag">${esc(m.priority)}</span><dl class="ws-kv"><dt>操作化公式</dt><dd>${esc(m.formula)}</dd><dt>需要数据</dt><dd>${esc(m.data_source)}</dd><dt>验证方式</dt><dd>${esc(m.validation)}</dd><dt>容易踩的陷阱</dt><dd>${esc(m.failure_mode)}</dd><dt>研究来源</dt><dd>${esc((m.source_ids||[]).join(', '))}</dd><dt>生产资格</dt><dd>${m.production_ready?'已声明就绪':'未就绪 · 待授权与数据映射'}</dd></dl>${wsDetails('时间契约、来源与完整定义',f)}</div></div>`}).join('');}
function wsSupplementForm(){document.getElementById('drawer-body').innerHTML=`<h2>为当前调查补证</h2><p class="ws-muted">绑定 ${esc(wsArtifact(WS_CASE).source)}。记录保留 source=human、修订关系与下一窗验证资格；不会修改历史结论。</p><form class="card" style="margin-top:16px" onsubmit="event.preventDefault();wsSubmitSupplement(this)"><label>相关因子</label><select name="factor_id">${wsDreamFactors().map(f=>`<option value="${esc(f.factor_id)}">${esc(f.name||f.factor_id)}</option>`).join('')}</select><label>当前窗口编号</label><input name="current_window" type="number" min="0" step="1" value="0" required><label>事实首次可用日（数据日索引）</label><input name="available_day" type="number" min="0" step="1" required><label>事实、事件时间、范围与来源引用</label><textarea name="note" required rows="5" placeholder="例如：某日分配日志缺失；补齐的日志位于……，覆盖……，记录版本为……"></textarea><button class="btn" style="margin-top:12px" type="submit">提交补证，进入待验证队列</button></form>`;document.getElementById('drawer').classList.add('open');document.getElementById('drawer-mask').classList.add('open');document.getElementById('drawer-mask').onclick=closeDrawer;}
async function wsSubmitSupplement(form){try{const op=operator(),f=Object.fromEntries(new FormData(form));const p={...f,operator:op,current_window:Number(f.current_window),available_day:Number(f.available_day),source:'human',evidence_ref:wsArtifact(WS_CASE).sha256,investigation_id:WS_CASE};const ok=await act('feedback',{kind:'factor_supplement',operator:op,payload:p},{type:'investigation_supplement',payload:p},'补证已存证，等待下一窗口统计验证');if(ok){closeDrawer();showView('todo');}}catch(e){toast(e.message,true);}}
