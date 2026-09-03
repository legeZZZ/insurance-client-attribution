const state = { caseId: "A", data: null, requestSeq: 0 };
const BOOTSTRAP_DATA = window.__GOAI_BOOTSTRAP_DATA__ || null;

const STATUS_LABELS = {
  RECEIVED: "已接收",
  INTENT_PARSED: "意图已解析",
  METRIC_CONFIRMED: "口径已确认",
  NEEDS_CLARIFICATION: "需要澄清",
  DATA_VALIDATED: "数据已校验",
  DATA_INSUFFICIENT: "数据不足",
  DIAGNOSING: "诊断中",
  CANDIDATES_READY: "候选已生成",
  EVIDENCE_GRADED: "证据已分级",
  COMPLIANCE_REVIEWED: "治理已复核",
  DESCRIPTIVE_ONLY: "仅描述性",
  CAUSAL_READY: "因果就绪",
  ACTION_DRAFTED: "动作草稿已生成",
  AWAITING_APPROVAL: "等待审批",
  MONITORING: "监测中",
  REVIEWED: "已复盘",
  FUSED: "已汇聚",
  TRIAGED: "已分诊",
  BOOTSTRAPPED: "环境已初始化",
  LOCATED: "问题已定位",
  PLANNED: "计划已生成",
  PATCHED: "修复已应用",
  VERIFYING: "验证中",
  RELEASE_READY: "可发布",
  POSTMORTEM: "复盘中",
  SKILL_DISTILLING: "Skill 提炼中",
  CLOSED: "已关闭",
  RUNNING: "运行中",
  IDLE: "空闲",
};

const CLAIM_LABELS = {
  causal_effect: "因果效应",
  descriptive_only: "仅描述性结论",
};

const CASE_LABELS = {
  A: "A / 描述性降级",
  B: "B / 数据不足拒答",
  C: "C / 随机实验",
  REAL: "真实数据 / UCI 银行营销历史",
};

const PROVIDER_LABELS = {
  "uci-official": "UCI 官方数据",
};

const AGENT_LABELS = {
  intent: "意图 Agent",
  metric_contract: "指标契约 Agent",
  data_acquisition: "数据获取 Agent",
  diagnostic: "诊断 Agent",
  causal_evidence: "因果证据 Agent",
  experiment_planner: "实验规划 Agent",
  monitor_review: "监测复盘 Agent",
};

const ARTIFACT_LABELS = {
  AnalysisIntent: "分析意图",
  MetricContract: "指标契约",
  DataQualityReport: "数据质量报告",
  FeatureSet: "特征集",
  AttributionCandidateSet: "归因候选集",
  RootCauseHypotheses: "根因假设",
  ExperimentSpec: "实验规格",
  MonitoringReport: "监测报告",
  ClaimLedger: "声明台账",
  SkillCandidate: "Skill 候选",
  VerificationResult: "验证结果",
  VerificationReport: "验证报告",
  PatchBundle: "修复包",
  ChangePlan: "变更计划",
  EnvironmentSnapshot: "环境快照",
  RiskAssessment: "风险评估",
  IssueCluster: "问题聚类",
  EvidenceReport: "证据报告",
  SourceManifest: "数据源清单",
  FeaturePolicy: "特征使用策略",
};

const MODE_LABELS = {
  sequential: "顺序执行",
  "contract-gated": "契约门控",
  "read-only": "只读",
  "fan-in": "汇聚",
  "evidence-gated": "证据门控",
  "approval-gated": "审批门控",
  "bounded-repair": "有界修复",
};

const EVIDENCE_LABELS = {
  "fixed-order log-chain decomposition": "固定顺序对数链分解",
  "metadata-derived five-layer readiness check": "元数据驱动的五层因果门禁",
  "structured claim and prohibited actions": "结构化声明与禁止动作",
  "bounded experiment draft": "有界实验草稿",
  "ITT estimate and confidence intervals": "ITT 估计与置信区间",
  "trace review and failure signature": "追踪复核与失败特征",
  "independent hidden verification attempt 1": "独立隐藏验证，第 1 次",
  "independent hidden verification attempt 2": "独立隐藏验证，第 2 次",
  "provider execution attempt 1": "提供方执行，第 1 次",
  "provider execution attempt 2": "提供方执行，第 2 次",
  "CI regression and user report": "CI 回归与用户报告",
  "pre-experiment monitoring placeholder": "预实验监测占位",
  "deterministic funnel, segment and treatment features": "确定性漏斗、分群与处理特征",
  "schema and data quality report": "Schema 与数据质量报告",
  "versioned insurance metric contract": "版本化保险指标契约",
  "official UCI source and checksum": "UCI 官方来源与校验和",
  "real-data schema and missingness audit": "真实数据 Schema 与缺失审计",
  "pre-call leakage policy": "呼叫前特征泄漏策略",
  "observational causal-readiness refusal": "观察性数据因果拒答",
  "real-data claim boundary": "真实数据结论边界",
};

const EVIDENCE_KIND_LABELS = {
  analysis: "分析",
  "causal-readiness": "因果就绪检查",
  "claim-ledger": "声明台账",
  experiment: "实验方案",
  monitoring: "监测",
  verification: "验证",
  input: "输入",
  execution: "执行",
  postmortem: "复盘",
  "feature-set": "特征集",
  "data-quality": "数据质量",
  "metric-contract": "指标契约",
  source: "数据来源",
  leakage: "泄漏审计",
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
const pretty = (value) => typeof value === "number" ? value.toLocaleString("zh-CN", { maximumFractionDigits: 4 }) : escapeHtml(value);
const display = (mapping, value) => mapping[value] || value || "-";
const statusLabel = (value) => display(STATUS_LABELS, value);
const agentLabel = (value) => display(AGENT_LABELS, value);
const artifactLabel = (value) => display(ARTIFACT_LABELS, value);
const evidenceLabel = (value) => display(EVIDENCE_LABELS, value);
const evidenceKindLabel = (value) => display(EVIDENCE_KIND_LABELS, value);

function setText(selector, value) {
  const node = $(selector);
  if (node) node.textContent = value ?? "-";
}

function setRunBusy(isBusy) {
  const button = $("#run-button");
  if (button) {
    button.disabled = isBusy;
    button.setAttribute("aria-busy", String(isBusy));
  }
  setText("#run-state", isBusy ? "运行中" : state.data ? statusLabel(state.data.state) : "空闲");
}

function clearResultPanels() {
  state.data = null;
  setText("#task-id", "-");
  setText("#trace-id", "-");
  setText("#state-version", "-");
  setText("#provider-label", "-");
  setText("#agent-count", "- 个 Agent");
  setText("#skill-count", "- 个 Skill");
  setText("#artifact-count", "-");
  setText("#evidence-count", "-");
  setText("#evidence-level", "-");
  setText("#claim-type", "声明台账");
  $("#agent-list").innerHTML = "";
  $("#skill-list").innerHTML = "";
  $("#topology-list").innerHTML = "";
  $("#state-timeline").innerHTML = "";
  $("#artifact-list").innerHTML = "";
  $("#evidence-list").innerHTML = "";
  $("#metrics").innerHTML = "";
  $("#claim-content").innerHTML = `<p class="claim-statement">正在加载赛道二案例证据。</p>`;
}

function selectedCaseUrl() {
  const caseId = ($("#case")?.value || "A").toUpperCase();
  state.caseId = caseId;
  return caseId === "REAL" ? "/api/track2/real-data" : `/api/track2/case?case=${caseId}`;
}

function offlinePack(url) {
  if (!BOOTSTRAP_DATA) return null;
  if (url.includes("/api/track2/real-data")) return BOOTSTRAP_DATA.track2.REAL;
  const match = /[?&]case=([A-Z]+)/.exec(url);
  const caseId = (match?.[1] || state.caseId || "A").toUpperCase();
  return BOOTSTRAP_DATA.track2[caseId] || BOOTSTRAP_DATA.track2.A;
}

function transitionPath(trace) {
  const states = [];
  for (const event of trace || []) {
    if (event.event_type === "TASK_CREATED") states.push("RECEIVED");
    if (event.event_type === "STATE_TRANSITION") states.push(event.payload.to);
  }
  return states;
}

function renderTimeline(data) {
  const path = transitionPath(data.trace);
  const unique = [];
  for (const item of path) if (unique[unique.length - 1] !== item) unique.push(item);
  const current = data.state;
  $("#state-timeline").innerHTML = unique.map((item) => {
    const isCurrent = item === current;
    return `<div class="state-step ${isCurrent ? "current" : "done"}"><span></span><label title="${escapeHtml(item)}">${escapeHtml(statusLabel(item))}</label></div>`;
  }).join("");
}

function renderArtifacts(data) {
  const items = (data.artifacts || []).slice(-12).reverse();
  setText("#artifact-count", `${data.artifacts?.length || 0}`);
  $("#artifact-list").innerHTML = items.map((item) => `<div class="artifact-row"><div class="artifact-name">${escapeHtml(artifactLabel(item.artifact_type))}</div><div class="artifact-detail">${escapeHtml(agentLabel(item.producer))} · v${escapeHtml(item.schema_version)} · ${escapeHtml(item.artifact_id)}</div></div>`).join("") || `<div class="artifact-detail">暂无产物</div>`;
}

function renderEvidence(data) {
  const items = (data.evidence || []).slice(-10).reverse();
  setText("#evidence-count", `${data.evidence?.length || 0}`);
  $("#evidence-list").innerHTML = items.map((item) => `<div class="evidence-row"><div class="evidence-name">${escapeHtml(evidenceLabel(item.label))}</div><div class="evidence-detail">${escapeHtml(evidenceKindLabel(item.kind))} · ${escapeHtml(item.content_digest.slice(0, 12))}...</div></div>`).join("") || `<div class="evidence-detail">暂无证据</div>`;
}

function renderCommon(data) {
  state.data = data;
  setText("#task-id", data.task_id);
  setText("#trace-id", data.trace_id);
  setText("#state-version", data.state_version);
  setText("#run-state", statusLabel(data.state));
  setText("#provider-label", data.provider ? display(PROVIDER_LABELS, data.provider) : CASE_LABELS[data.case] || "赛道二");
  setText("#agent-count", `${data.agents?.length || 0} 个 Agent`);
  setText("#skill-count", `${data.skills?.length || 0} 个 Skill`);
  $("#agent-list").innerHTML = (data.agents || []).map((item) => `<span class="tag" title="${escapeHtml(item)}">${escapeHtml(agentLabel(item))}</span>`).join("");
  $("#skill-list").innerHTML = (data.skills || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("");
  const topology = (data.topologies || [])[0];
  $("#topology-list").innerHTML = topology ? topology.edges.slice(0, 7).map((edge) => `<div class="topology-edge"><strong>${escapeHtml(agentLabel(edge.from))}</strong> → <strong>${escapeHtml(agentLabel(edge.to))}</strong><br>${escapeHtml(display(MODE_LABELS, edge.mode))}${edge.condition ? ` · ${escapeHtml(edge.condition === "failure_signature" ? "失败特征" : edge.condition)}` : ""}</div>`).join("") : "";
  renderTimeline(data);
  renderArtifacts(data);
  renderEvidence(data);
}

function renderTrack2Case(data) {
  $("#metrics-panel").classList.remove("hidden");
  $("#claim-panel").classList.remove("hidden");
  setText("#evidence-level", data.summary?.evidence_level || "-");
  const current = data.metrics?.current || {};
  const readiness = data.causal_readiness || {};
  const decomposition = data.decomposition || {};
  $("#metrics").innerHTML = [
    ["净保费", current.net_premium, "当前脱敏数据窗口"],
    ["报价率", `${((current.quote_rate || 0) * 100).toFixed(2)}%`, "指标契约 v2026-07-26"],
    ["出单率", `${((current.issue_rate || 0) * 100).toFixed(2)}%`, "漏斗结果"],
    ["因果门禁", statusLabel(readiness.outcome), readiness.identification_strategy === "randomized" ? "随机实验" : "未识别"],
  ].map(([label, value, sub]) => `<div class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${pretty(value)}</div><div class="metric-sub">${escapeHtml(sub)}</div></div>`).join("");
  const claim = data.claim || {};
  setText("#claim-type", display(CLAIM_LABELS, claim.claim_type));
  $("#claim-content").innerHTML = `<p class="claim-statement">${escapeHtml(claim.statement || "暂无结论")}</p><div class="claim-meta"><span>${escapeHtml(claim.evidence_level || "-")}</span><span>${escapeHtml((claim.allowed_verbs || []).join(" / ") || "-")}</span><span>未解释残差 ${escapeHtml(decomposition.unexplained_residual ?? "-")}</span></div>`;
}

function renderTrack2Real(data) {
  $("#metrics-panel").classList.remove("hidden");
  $("#claim-panel").classList.remove("hidden");
  setText("#evidence-level", data.summary?.evidence_level || "-");
  const profile = data.profile || {};
  const readiness = data.causal_readiness || {};
  $("#metrics").innerHTML = [
    ["真实记录", profile.row_count, "UCI 官方历史数据"],
    ["订阅率", `${((profile.subscription_rate || 0) * 100).toFixed(2)}%`, "真实结果标签 y"],
    ["缺失单元格", profile.missing_cells, "按官方 NaN 标记统计"],
    ["因果门禁", statusLabel(readiness.outcome), "无随机实验分配"],
  ].map(([label, value, sub]) => `<div class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${pretty(value)}</div><div class="metric-sub">${escapeHtml(sub)}</div></div>`).join("");
  const claim = data.claim || {};
  $("#claim-type").textContent = "真实数据 / 仅描述性";
  $("#claim-content").innerHTML = `<p class="claim-statement">${escapeHtml(claim.statement || "暂无结论")}</p><div class="claim-meta"><span>${escapeHtml(data.source?.license || "-")}</span><span>${data.source?.checksum_verified ? "SHA-256 已验证" : "校验和异常"}</span><span>仅输出聚合结果</span><span>禁止 duration 前置决策</span></div>`;
}

function renderCase(data) {
  if (data.real_data) {
    renderTrack2Real(data);
  } else {
    renderTrack2Case(data);
  }
}

async function load(url) {
  const requestId = ++state.requestSeq;
  setRunBusy(true);
  setText("#runtime-status", "正在运行赛道二案例");
  clearResultPanels();
  const localPack = location.protocol === "file:" ? offlinePack(url) : null;
  if (localPack) {
    renderCommon(localPack);
    renderCase(localPack);
    setRunBusy(false);
    setText("#runtime-status", "离线预览");
    return;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (requestId !== state.requestSeq) return;
    renderCommon(data);
    renderCase(data);
    setText("#runtime-status", "追踪已记录");
  } catch (error) {
    if (requestId !== state.requestSeq) return;
    const fallback = offlinePack(url);
    if (fallback) {
      renderCommon(fallback);
      renderCase(fallback);
      setText("#runtime-status", "离线预览");
      return;
    }
    setText("#run-state", "运行错误");
    setText("#runtime-status", "运行错误");
    $("#state-timeline").innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  } finally {
    if (requestId === state.requestSeq) setRunBusy(false);
  }
}

function currentLoad() {
  return load(selectedCaseUrl());
}

$("#case").addEventListener("change", () => {
  state.caseId = $("#case").value.toUpperCase();
});
$("#run-button").addEventListener("click", () => currentLoad());
const portsButton = $("#ports-button");
if (portsButton) {
  portsButton.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/ports", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    $("#claim-content").innerHTML = `<p class="claim-statement">已注册 ${data.ports.length} 类端口。当前赛道二只使用只读查询、证据和复盘端口，其余契约用于兼容性校验。</p><div class="claim-meta">${data.ports.map((port) => `<span>${escapeHtml(port.port_id)}</span>`).join("")}</div>`;
  } catch (error) {
    $("#claim-content").innerHTML = `<p class="claim-statement">本地文件预览未连接后端。</p><div class="claim-meta"><span>离线预览</span><span>${escapeHtml(error.message)}</span></div>`;
  }
  });
}

currentLoad();
