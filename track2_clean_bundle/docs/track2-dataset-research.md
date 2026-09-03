# Track 2 public dataset research

Date: 2026-08-01

## Decision

There is no verified public dataset that simultaneously contains insurance business semantics, a complete exposure-to-policy funnel, trustworthy treatment assignment, refunds/cancellations, and causal ground truth. Track 2 should use a composite evidence stack instead of pretending one sales table can train the whole system.

The causal gate, data-quality gate and ClaimPolicyGuard remain deterministic. Public data is used to test adapters, candidate ranking and estimators; it must not teach the system to relax an evidence rule.

## Implemented real-data baseline

UCI Bank Marketing is no longer only a catalog entry. On 2026-08-01 the official `data.csv` was downloaded, its 45,211 rows were analyzed, and SHA-256 `94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686` was pinned in the adapter. The run produced a SourceManifest, DataQualityReport, FeaturePolicy, EvidenceReport and ClaimLedger under `runtime_data/evidence/T2-real-uci-bank-marketing.json`.

This closes the “no real rows have run through the system” gap. It does not close the insurance-domain or causal-effect gaps: the records are banking telemarketing history, not an insurance funnel, and have no randomized treatment assignment. Detailed observed results are in [`track2-real-data.md`](track2-real-data.md).

## Recommended stack

| Dataset | What it can validate | What it cannot validate | License decision |
|---|---|---|---|
| [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing) | Financial-product conversion fields, campaign segmentation, leakage detection; 45,211 records | No random treatment and no insurance funnel | CC BY 4.0; suitable for an attributed open baseline |
| [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) | 1,067,371 historical transactions, cancellations, revenue aggregation and query-scale tests | No exposure, treatment or causal design | CC BY 4.0; suitable for an attributed open baseline |
| [Criteo Uplift](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) | 25M randomized incrementality rows, treatment, visit and conversion; useful for ITT/uplift evaluation | Anonymous advertising features, not insurance | CC BY-NC-SA 4.0; private non-commercial benchmark, do not bundle casually |
| [Retailrocket](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset) | 2,756,101 view/add-to-cart/transaction events from 1,407,580 visitors; event and funnel adapters | No randomized treatment; hashed product features | CC BY-NC-SA 4.0; private benchmark with attribution/share-alike review |
| [Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | About 100k marketplace orders, sellers, products, payments, freight and reviews | Starts at orders; no impression funnel or randomization | CC BY-NC-SA 4.0; private benchmark with attribution/share-alike review |
| [CoIL 2000](https://archive.ics.uci.edu/dataset/125/insurance+company+benchmark+coil+2000) | Real insurance product-ownership taxonomy, 9,000 records and 86 attributes | No timeline, funnel or causal assignment | Blocked: UCI says CC BY 4.0, but archive documentation restricts commercial education/demo; obtain permission before use or redistribution |

## GitHub finding

GitHub contains many notebooks and mirrors for these datasets, but most repositories have no data license. An MIT license on analysis code does not grant MIT rights to copied CSV files. The project must record the official dataset URL and original terms, and should not train from an arbitrary GitHub mirror merely because the repository is public.

## Training and evaluation map

1. MetricContract, schema mapping and leakage checks: UCI Bank Marketing plus UCI Online Retail II.
2. Funnel and EventAligner: Retailrocket; keep it outside the distributable package unless license review approves inclusion.
3. Product/channel/seller structure decomposition: Olist.
4. Causal estimator and confidence calibration: Criteo Uplift.
5. Insurance vocabulary and feature taxonomy: derive only from licensed documentation or authorized data; CoIL raw data remains blocked pending review.
6. Final business proof: authorized, de-identified aggregate insurance data in shadow mode, followed by a governed real experiment.

## Immediate ingestion rules

- Preserve source URL, checksum, retrieval time, license text and attribution in a dataset manifest.
- Separate train/example/test data and generate hidden tests only after Agent code is frozen.
- Remove post-outcome leakage. In UCI Bank Marketing, call `duration` is not available before the call and cannot be used for pre-call targeting.
- Never infer randomization from balanced groups. Require signed experiment configuration or experiment-platform provenance.
- Do not place personal-level public data in prompts or Evidence Packs; use aggregate or pseudonymous views.
- Report results by dataset and scenario family. Do not average unrelated insurance, banking and retail tasks into one flattering score.
