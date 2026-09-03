# Track 2 real-data execution

Date: 2026-08-01

## Source and provenance

- Dataset: UCI Bank Marketing
- Official page: https://archive.ics.uci.edu/dataset/222/bank+marketing
- Official file: https://archive.ics.uci.edu/static/public/222/data.csv
- DOI: `10.24432/C5K306`
- License: CC BY 4.0
- Attribution: S. Moro, P. Rita and P. Cortez; UCI Machine Learning Repository
- Local bytes: `3,542,816`
- SHA-256: `94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686`
- Checksum status: verified against the pinned adapter value

The project downloads from UCI directly. No GitHub mirror is used as a data authority.

## Observed run

The adapter analyzed 45,211 real historical marketing records and 17 columns. There were 5,289 term-deposit subscriptions, for an observed subscription rate of 11.70%. It found 52,124 officially marked missing cells: `contact` 13,020, `education` 1,857, `job` 288, and `poutcome` 36,959.

Descriptive segment rates were generated for contact channel, month, job and previous campaign outcome. These are historical associations only. They are not presented as treatment effects and must not be used to create individual targeting lists.

## Leakage and safety result

UCI explicitly states that `duration` is known only after a call and strongly affects the target. The adapter therefore marks it `POST_OUTCOME_LEAKAGE` and removes it from the pre-call feature set. The target `y` is also blocked as an input.

Age, marital status, education and job are restricted from individual targeting. Evidence Packs contain aggregates and digests, not source rows.

## Causal result

The final gate is `DESCRIPTIVE_ONLY` at evidence level L1/L2. Reason codes:

- `NO_TREATMENT_ASSIGNMENT`
- `NO_RANDOMIZATION_PROVENANCE`
- `POST_OUTCOME_LEAKAGE_FIELD_BLOCKED`

The source, checksum, schema and leakage gates pass. The causal-design gate fails because this dataset has no treatment/control assignment or trusted experiment provenance. This is the correct result for real observational history.

## Reproduce

```bash
PYTHONPATH=src python3 -m goai_control_tower --track2-fetch-real-data
PYTHONPATH=src python3 -m goai_control_tower --track2-real-data
```

The generated Evidence Pack is `runtime_data/evidence/T2-real-uci-bank-marketing.json`. The console exposes the same run through `/api/track2/real-data` and the “真实数据 / UCI 银行营销历史” case.

## Remaining gap

This proves that the system can process real financial-product marketing history, enforce a leakage policy and refuse unsupported causal claims. It still does not prove performance on a complete insurance exposure-to-policy funnel or estimate a real insurance intervention effect. Those require authorized insurance shadow data and approved experiment metadata.
