# Insurance Sales Client Attribution Tool

[中文](README.zh-CN.md)

**Spec-driven open factor mining and Bayesian experiment attribution agent.**

Built for insurance platform operations analytics: when a business metric moves
unexpectedly (carousel CTR drops, monthly premium fluctuates), the tool answers
three questions — **how much of the change is real, which factor caused it, and
what experiment to run next** — while keeping every conclusion verifiable,
traceable, and within its evidence authority.

## Highlights

Two attribution lines, with every conclusion constrained by an evidence-graded
state machine and a Claim Ledger:

- **Component attribution (Line A)**: Growth UI Spec diffs (Spec / Render /
  Runtime) → open candidate discovery with FactorMiner → Bayesian bundle and
  HTE estimation → factorial experiment design. The factor space is open:
  candidates are discovered from spec differences, not enumerated by hand.
- **Experiment baseline attribution (Line B)**: persistent A/B control baseline
  + change registry + external-event alignment, bucketing each month's movement
  into "what we did / what happened externally / unexplained residual" — with
  the residual honestly labeled as unknown instead of being allocated away.

Governance principles (not optional):

- Without randomization, conclusions are `ASSOCIATION_ONLY` — causal verbs forbidden
- External factors are always `TEMPORAL_ASSOCIATION`, never promoted to causal
- High-risk actions (rollback, ramp-up, config changes) are suggestions
  requiring human approval
- Insufficient evidence means refusal (`REFUSED` / `DATA_INSUFFICIENT`), never
  a hallucinated answer

### Fail-closed experiment integrity

Randomized metadata alone never authorizes a causal estimate. The runtime
checks realized row-level evidence for sample-ratio mismatch, pre-treatment
balance, allocation stability, contamination, temporal ordering, sample-funnel
consistency, cluster integrity, and concurrent experiments. All eight checks
must pass before ITT, Bayesian bundle decisions, or HTE are evaluated.

Repeated observations are handled according to an explicit primary estimand:

- `user_level` aggregates repeated observations to the analysis unit for ITT
- `exposure_level` keeps eligible exposures and uses CR1 cluster-robust errors
- `triggered_user` is explicitly labeled post-assignment and non-ITT
- cluster-randomized designs infer at the declared cluster level

## Architecture

### Seven-agent governance pipeline

| Agent | Responsibility | Artifacts |
|---|---|---|
| `intent` | Business question intent parsing | `AnalysisIntent` |
| `metric_contract` | Metric definition governance (definition/window/granularity/version) | `MetricContract` |
| `data_acquisition` | Read-only data profiling and quality validation | `QueryPlan`, `DataQualityReport` |
| `diagnostic` | Funnel and structure diagnosis, segment profiling | `AttributionCandidateSet` |
| `causal_evidence` | Causal-readiness grading and claim governance | `EvidenceReport`, `ClaimLedger` |
| `experiment_planner` | Experiment and action planning with guardrails | `ExperimentSpec` |
| `monitor_review` | Experiment monitoring and review | `MonitoringReport`, `PlaybookPatch` |

Business state path (exception/recovery states omitted):

```
RECEIVED → INTENT_PARSED → METRIC_CONFIRMED → DATA_VALIDATED → DIAGNOSING
→ EVIDENCE_GRADED → ACTION_DRAFTED → COMPLIANCE_REVIEWED → AWAITING_APPROVAL
→ MONITORING → REVIEWED → CLOSED
```

When evidence is insufficient or authority is exceeded, tasks move to
`DATA_INSUFFICIENT` / `DESCRIPTIVE_ONLY` / `BLOCKED_BY_GUARDRAIL` /
`NEEDS_HUMAN` instead of producing an answer.

### Claim Ledger: evidence-graded state machine

Every attribution claim is promoted through 9 states, each with an explicit
evidence threshold:

```
OBSERVED_ANOMALY → FACTORS_DISCOVERED → BUNDLE_EXPERIMENT_READY
→ BUNDLE_EFFECT_ESTIMATED → HETEROGENEITY_RANKED
→ COMPONENT_EXPERIMENT_DESIGNED → COMPONENT_EFFECT_ESTIMATED
→ POSTERIOR_UPDATED → DECISION_READY
```

Four explicit refusal types: `ASSOCIATION_ONLY`, `FACTOR_SPACE_INCOMPLETE`,
`EXPERIMENT_NOT_IDENTIFIED`, `INCONCLUSIVE_NEED_MORE_DATA`.

### Factor experience store (cross-period learning)

Attribution posteriors are written back after each period and loaded as
informative priors for the next:

- Stale experience decays by 0.5 per period with an upper cap
- PID feedback adaptively tunes the legacy pseudo-impression
  `shrinkage_strength`; this is separate from Student-t degrees of freedom `nu`
- Prior–data mismatch alarms trigger automatic degradation to flat estimation

### Statistical correctness upgrades

- Rate/mix/interaction decomposition closes exactly and reports closure error
- Student-t random effects are implemented in posterior and `tau` estimation;
  `tau`, `nu`, and the actual posterior method are recorded in every result
- Beam search ranks candidates by anomaly magnitude instead of field order
- Factorial designs fail closed when the arm budget cannot preserve a valid
  full or supported fractional design; component effects require full rank
- Shared input validation rejects non-finite values, invalid counts, duplicate
  segment IDs, invalid p-values, and unidentifiable experiment arms
- BH/FDR correction, design diagnostics, power design, attrition inflation,
  unequal allocation, and cluster design effects are reported explicitly

### Technical notes

- **Pure numpy, single dependency** — no PyMC/scipy/frameworks; fully
  reproducible offline
- Zero LLM dependency in the statistical core; LLMs are only used for intent
  parsing and report writing (replaceable; demos use rule templates)
- Simulator ships with explicit DAG + structural equations, with **truth and
  evaluation oracle separated**
- Benchmarks are process-isolated; seeds and ground truth are never exposed
  to the code under test

## Quick Start

Requires Python 3.12+ and numpy (`pip install -r requirements.txt`).

```bash
# ① Line A end-to-end demo + 7-seed benchmark (~16 s)
python3 -m attribution

# ② Line B experiment baseline attribution + 5-seed validation
python3 -m attribution.baseline_attribution

# ③ Experience-store cross-period ablation (write-back + PID shrinkage + mismatch alarm)
python3 -m attribution.experience_benchmark

# ④ Nested shrinkage + calibration ablation, 50 seeds (~90 s)
python3 -m attribution.nested_benchmark

# ④b Student-t calibration across four truth families (~65 s)
python3 -m attribution.student_t_calibration_benchmark

# ⑤ Public external-event timeline mapping + coverage stats
python3 -m attribution.external_events

# ⑥ Multi-dimensional rate anomaly discovery with auditable beam search
python3 -m attribution.rate_aware_rca

# ⑦ Temporal association discovery from event and factor snapshots
python3 -m attribution.association_discovery

# ⑧ Causal governance benchmark (process-isolated, 3 seeds / 9 cases)
python3 -m runtime --benchmark --benchmark-seeds 3

# ⑨ Print and validate the public dataset provenance catalog
python3 -m runtime --datasets

# ⑩ Real public-data case (UCI Bank Marketing, CC BY 4.0, downloaded on first run)
python3 -m runtime --fetch-real-data

# ⑪ Local console (REST API, default port 8765)
python3 run_server.py 8765
```

Generated evidence JSON goes to `outputs/` and runtime state to
`runtime_data/`; both are local artifacts and are not distributed with the
repository (see .gitignore).

## Console API

```text
GET  /api/health                            Health check
GET  /api/attribution/case?case=A|B|C       Causal-readiness cases (observational / missing metadata / randomized)
GET  /api/attribution/benchmark?seeds=8     Process-isolated governance benchmark
GET  /api/attribution/datasets              Public dataset provenance catalog
GET  /api/attribution/bayes-case?case=C     Gate + Bayesian decision layer (refuses when the gate fails)
GET  /api/attribution/line-b-review         Line B monthly attribution evidence pack
GET  /api/attribution/real-data             UCI real data (requires --fetch-real-data first)
GET  /api/attribution/scenarios             Demo scenario catalog
GET  /api/attribution/scenario-run?scenario=line_a|line_b|external|bayes_case_a|experience
GET  /api/attribution/scenario-report?scenario=...   Download Markdown audit report
POST /api/attribution/chat                  Multi-turn agent chat (intent → clarify → plan → confirm → real execution)
       body: {"session_id": "demo", "message": "上个月注册量为什么掉了"}
       send "reset"/"重置" to clear the session
```

## Repository Layout

```text
attribution/                  # Attribution methods package (pure numpy)
  bayes.py                    # Beta-Binomial decisions, hierarchical HTE, moderation scan
  spec.py                     # Growth UI Spec + SpecDiff/RenderDiff/RuntimeDiff
  factor_miner.py             # Open candidate discovery
  association_discovery.py    # Temporal event/factor association discovery
  rate_aware_rca.py           # Rate/mix/interaction decomposition + beam search
  input_validation.py         # Shared fail-fast statistical input contract
  factor_registry.py          # Factor metadata and provenance registry
  factor_store.py             # Persistent factor snapshots and experience
  factor_retriever.py         # Time-safe candidate retrieval
  fdr.py                      # Multiple-testing correction
  experiment_designer.py      # Full/Resolution-IV factorial designs + component effects
  experiment_platform.py      # Approval-aware experiment platform adapter
  validation_planner.py       # Evidence-aware validation plan generation
  claim_ledger.py             # Evidence-graded state machine and promotion gates
  insursim_carousel.py        # Explicit-DAG simulator (truth separated from oracle)
  benchmark.py                # Bayesian benchmark (in-distribution + mismatch, segment Brier)
  baseline_attribution.py     # Line B: baseline attribution + registries + unknown labeling
  experience_store.py         # Factor experience store: write-back/priors/PID ν/mismatch alarm
  experience_benchmark.py     # Cross-period ablation (7-period traffic ramp)
  calibration.py              # Binned calibration layer (out-of-sample reliability mapping)
  nested_benchmark.py         # Nested pooling + calibration ablation, 50 seeds
  student_t_calibration_benchmark.py # Four-truth-family Student-t release gates
  external_events.py          # Public external-event timeline + mapping coverage
  scenario_reports.py         # Console scenario runner + audit report rendering
  agent_chat.py               # Multi-turn chat agent: Plan-and-Execute state machine
runtime/                      # Causal governance runtime (7-agent state machine + gates)
  cases.py                    # Causal-readiness cases A/B/C vertical slice
  analysis.py                 # Deterministic feature extraction and readiness skills
  experiment_integrity.py     # Eight fail-closed row-level integrity checks
  benchmark.py                # Process-isolated benchmark (seeds/truth hidden from the tested code)
  real_data.py                # UCI Bank Marketing adapter (SHA-256 pinned)
  dataset_catalog.py          # Dataset provenance catalog
  bayes_bridge.py             # Governance runtime ↔ Bayesian layer bridge
  foundation.py               # Control plane, evidence packs, checkpoints
  cli.py / configuration.py   # CLI entry point and configuration
specs/                        # Carousel Growth UI Spec, two versions (reusable templates)
scripts/                      # Benchmark plotting utility
docs/methodology.md           # Theoretical provenance and adaptation boundaries (Chinese)
```

## Sample Output

### Line A: carousel anomaly attribution

Input: old style CTR 4.1% → new style 3.2%; two Growth UI Spec versions;
impression-level logs (simulated).

```text
BUNDLE_EFFECT: new style bundle changes CTR by -0.0166, P(actual harm)=1.000 → ROLLBACK_RECOMMENDED
HETEROGENEOUS_TREATMENT_EFFECT: low-end device segment harmed most (shrunk -0.0272)
COMPONENT_EFFECT: carousel.text_density = -0.0117; carousel.image_component = -0.0078 (independent randomization)
EXPERIMENT_INCONCLUSIVE ×3: layout / indicator_position / media_aspect_ratio below component-level evidence bar
Final state: DECISION_READY
```

### Line B: monthly baseline attribution

Input: 60-day control/treatment premium panel + change registry (2 entries) +
external-event registry (1 entry).

```text
ATT summary: naive 116.4 → hierarchical 119.4 (truth 100, with experimental noise)
External association: ext_regulation window deviation -86.2, claim_type=TEMPORAL_ASSOCIATION
Governance alert: UNEXPLAINED_STEP_SUSPECTED (day 44/51; truth: unregistered change day 40 + drift)
Unknown bucket: last-10-day mean -95.8, claim_type=UNEXPLAINED (not allocated)
```

## Evaluation Metrics

All metrics are locally reproducible (see [Quick Start](#quick-start)):

| Evaluation | Metric | Result |
|---|---|---|
| Simulated-truth backtest (5 seeds) | Recall@5 / ATE RMSE / CrI coverage / decision accuracy / HTE direction / factor recovery | 1.00 / 0.001 / 1.00 / 1.00 / 1.00 / 0.90 |
| Mismatch backtest (2 seeds) | Decision accuracy / factor recovery / Brier | 1.00 / 0.75 / 0.0445 (near the Bernoulli variance floor) |
| Experience-store ablation (7-period ramp) | Cold-start ATE RMSE / decision consistency / mismatch alarm | ↓10.9% / no regression / precise trigger, no false alarms |
| Nested pooling + calibration (50 seeds, small samples) | Direction recall nested vs flat / calibration ECE / Gaussian vs joint Student-t vs plug-in Student-t 95% coverage | 0.18 vs 0.02 / 0.0626→0.0390 (−37.7%) / 0.8775 vs 0.9475 vs 0.3075 |
| External-event mapping (90-day panel) | True-event recall / misattributed unregistered changes / coverage | 100% / 0 misattributed / 0.500 |
| Governance benchmark (3 seeds / 9 cases) | Gate accuracy / false causal assertion rate / refusal recall | 1.00 / 0.00 / 1.00 |
| Line B prototype (5 seeds) | Unregistered-change recall / external alignment / unknown honesty | 1.00 / 1.00 / 1.00 |
| Shrinkage ablation | Moderation RMSE hierarchical vs naive | 0.0030 vs 0.0048 (in-dist); 5.55 vs 10.23 (Line B, ↓46%) |
| Student-t multi-truth calibration (4 × 50 seeds) | Joint vs plug-in coverage / minimum family coverage / interval-width ratio vs Gaussian | 0.9383 vs 0.5588 / 0.9100 / 1.122 |
| Student-t utility gate (repository replay) | Direction recall joint vs Gaussian / moderation RMSE joint vs Gaussian | 0.00 vs 0.02 / 0.00398 vs 0.00284; calibration is repaired, but utility gates fail, so Student-t remains experimental |
| UCI real data (45,211 rows) | Detects no randomization + leakage variable flagging + Bayesian-layer refusal | All correct |

## Verification

The repository can be checked without writing generated artifacts into the
working tree:

```bash
python3 -m runtime --datasets
python3 -m runtime --benchmark --benchmark-seeds 1
python3 -m unittest discover -s tests -v
ruff check . && ruff format --check .
python3 -c "import attribution, runtime, run_server"
```

The causal-readiness fixtures must remain `DESCRIPTIVE_ONLY`,
`DATA_INSUFFICIENT`, and `CAUSAL_READY` for cases A, B, and C respectively.

## Data Sources and Licensing

| Data | Source | License | Handling |
|---|---|---|---|
| Simulated data (carousel scenario generator) | In-repo generator | Own work | Explicit DAG + structural equations published; truth separated from evaluation oracle; method validation only, no real-world causal claim |
| UCI Bank Marketing | UCI ML Repository (doi:10.24432/C5K306) | CC BY 4.0 | Read-only analysis; no identifiable personal information; downloaded at runtime, not shipped |
| Growth UI Spec examples | Written for this repo (informed by public OpenUI/WICG draft ideas) | Own work | Reusable templates |
| Public external-event timeline (LPR adjustments, industry regulatory actions, shopping festivals, school season) | Public releases / calendars | Public information | Illustrative exogenous events only; production use requires an official data feed |

## Compliance Boundaries

- The system does **not** make underwriting, claims, actuarial, risk-control,
  credit, investment, or payout decisions
- No individual-level insurance recommendations or marketing lists; all
  segment analysis is aggregated above small-cell suppression thresholds
- Without randomization, only associational conclusions are emitted, with
  non-causal warnings; external factors are never upgraded to causal
- High-risk actions (rollback, ramp-up, config changes) are suggestions
  requiring human approval
- Demos and evaluations use synthetic and CC BY 4.0 public data only; no real
  user data is included

## Documentation

- [Methodology and adaptation boundaries](docs/methodology.md) (Chinese) —
  theoretical provenance of each mechanism, what was borrowed, and what was
  deliberately not copied (partial pooling, DoWhy/EconML comparison, A/B
  decision-engine comparison)

## License

Code: [Apache-2.0](LICENSE); documentation: CC BY 4.0.
