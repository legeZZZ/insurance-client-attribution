"""External data adapter: load company data into the line-B pipeline.

Reads a JSON config (see `config.example.json`) that points at a data
directory holding the five contract tables, optionally with per-table
field mapping (company column name -> contract column name), and returns
structures that the algorithmic core already understands.

Design rules
------------
- Dependency-free (stdlib csv/json only); numpy only via the core modules.
- Source provenance is preserved end-to-end: every factor/event keeps its
  `source_uri` / `license_ref` so the Claim Ledger can grade it.
- If a change has an `experiment_id` but no matching row in
  `experiment_readouts`, the id is stripped (change stays registered but
  unexplained) — consistent with `attribute_baseline` semantics.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .data_contract import (
    OPTIONAL_TABLES,
    REQUIRED_TABLES,
    ContractError,
    check_day_alignment,
    validate_rows,
)

DEFAULT_FILES = {
    "metric_panel": "metric_panel.csv",
    "value_panel": "value_panel.csv",
    "factor_snapshots": "factor_snapshots.csv",
    "change_registry": "change_registry.json",
    "external_events": "external_events.json",
    "experiment_readouts": "experiment_readouts.json",
    "tracking_events": "tracking_events.csv",
    "experiment_exposures": "experiment_exposures.csv",
}


def aggregate_events_to_panel(
    events: list[Mapping[str, Any]],
    *,
    numerator_event: str = "click",
    denominator_event: str = "impression",
) -> list[dict[str, Any]]:
    """Aggregate raw tracking events into metric_panel rows.

    口径（与公司埋点侧对齐，见《真实数据验证手册》§3）：
      - 分母 = denominator_event 的事件条数（如 impression）
      - 分子 = numerator_event 的事件条数（如 click）；去重粒度由导出侧保证
      - 粒度 = day × region × channel × version × arm
    """
    cells: dict[tuple, dict[str, float]] = {}
    for event in events:
        key = (event["day"], event["region"], event["channel"], event["version"])
        cell = cells.setdefault(
            key,
            {
                "control_clicks": 0,
                "control_impressions": 0,
                "treatment_clicks": 0,
                "treatment_impressions": 0,
            },
        )
        field = f"{event['arm']}_{'clicks' if event['event_name'] == numerator_event else 'impressions' if event['event_name'] == denominator_event else ''}"
        if field.endswith("_"):
            continue  # 非分子/分母事件（如中间转化事件）不计入比率面板
        cell[field] += 1
    rows = []
    for (day, region, channel, version), cell in sorted(cells.items()):
        rows.append(
            {
                "day": day,
                "region": region,
                "channel": channel,
                "version": version,
                **cell,
            }
        )
    return rows


@dataclass
class DataSourceConfig:
    """Resolved configuration for an external data source."""

    data_dir: Path
    label: str = "company_adapter"
    license_ref: str = "company-authorized"
    source_uri_prefix: str = "company://intranet"
    detection_threshold: float = 0.005
    metric_name: str = "conversion_rate"
    metric_unit: str = "rate"
    numerator_event: str = "click"
    denominator_event: str = "impression"
    files: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_FILES))
    field_mapping: dict[str, dict[str, str]] = field(default_factory=dict)
    target_population: str = "eligible_population"
    timezone: str = "UTC"
    maturity_days: int = 0
    deduplication: str = "upstream_event_identity"
    association_statistic: str = "pearson"
    shadow_diagnostics: bool = False


def load_config(path: str | Path) -> DataSourceConfig:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ContractError("config root must be a JSON object")
    data_dir = Path(raw.get("data_dir", "")).expanduser()
    if not data_dir.is_absolute():
        data_dir = (config_path.parent / data_dir).resolve()
    if not data_dir.is_dir():
        raise ContractError(
            f"config.data_dir does not exist or is not a directory: {data_dir}"
        )
    files = dict(DEFAULT_FILES)
    files.update(raw.get("files") or {})
    mapping = raw.get("field_mapping") or {}
    if not isinstance(mapping, dict):
        raise ContractError(
            "config.field_mapping must be an object of table -> {company_col: contract_col}"
        )
    return DataSourceConfig(
        data_dir=data_dir,
        label=str(raw.get("label") or "company_adapter"),
        license_ref=str(raw.get("license_ref") or "company-authorized"),
        source_uri_prefix=str(raw.get("source_uri_prefix") or "company://intranet"),
        detection_threshold=float(
            raw.get(
                "detection_threshold",
                0.005 if raw.get("metric_unit", "rate") == "rate" else 18.0,
            )
        ),
        metric_name=str(raw.get("metric_name") or "conversion_rate"),
        metric_unit=str(raw.get("metric_unit") or "rate"),
        numerator_event=str(raw.get("numerator_event") or "click"),
        denominator_event=str(raw.get("denominator_event") or "impression"),
        files=files,
        field_mapping={t: dict(m) for t, m in mapping.items()},
        target_population=raw.get("target_population", "eligible_population"),
        timezone=raw.get("timezone", "UTC"),
        maturity_days=raw.get("maturity_days", 0),
        deduplication=raw.get("deduplication", "upstream_event_identity"),
        association_statistic=raw.get("association_statistic", "pearson"),
        shadow_diagnostics=raw.get("shadow_diagnostics", False),
    )


def _apply_mapping(
    table: str, rows: list[dict[str, Any]], config: DataSourceConfig
) -> list[dict[str, Any]]:
    mapping = config.field_mapping.get(table) or {}
    if not mapping:
        return rows
    return [
        {mapping.get(key, key): value for key, value in row.items()} for row in rows
    ]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "rows" in payload:
        payload = payload["rows"]
    if not isinstance(payload, list):
        raise ContractError(
            f'{path.name}: JSON root must be an array (or {{"rows": [...]}})'
        )
    return [dict(row) for row in payload]


def _load_table(
    table: str, config: DataSourceConfig, *, required: bool
) -> list[dict[str, Any]]:
    filename = config.files.get(table, DEFAULT_FILES[table])
    path = config.data_dir / filename
    if not path.is_file():
        if required:
            raise ContractError(f"missing required table file: {path}")
        return []
    rows = _read_csv(path) if filename.endswith(".csv") else _read_json(path)
    rows = _apply_mapping(table, rows, config)
    min_rows = (
        8
        if table in {"metric_panel", "value_panel"}
        else (
            0 if not required or table in {"change_registry", "external_events"} else 1
        )
    )
    if not rows and not required:
        return []
    return validate_rows(table, rows, min_rows=min_rows)


def load_line_b_inputs(config: DataSourceConfig) -> dict[str, Any]:
    """Load and normalize all contract tables into pipeline-ready structures."""
    monetary = config.metric_unit in {"currency", "currency_per_user"}
    panel_rows = _load_table(
        "value_panel" if monetary else "metric_panel", config, required=monetary
    )
    if not panel_rows:
        # 允许只给埋点明细：自动聚合为指标面板（口径见手册 §3）
        events = _load_table("tracking_events", config, required=False)
        if not events:
            raise ContractError(
                "缺少 metric_panel；也没有可用于聚合的 tracking_events。"
                "两表至少提供一张（见真实数据验证手册 §2/§3）"
            )
        panel_rows = validate_rows(
            "metric_panel",
            aggregate_events_to_panel(
                events,
                numerator_event=config.numerator_event,
                denominator_event=config.denominator_event,
            ),
        )
    registry = _load_table("change_registry", config, required=True)
    external_rows = _load_table("external_events", config, required=True)
    factor_rows = _load_table("factor_snapshots", config, required=False)
    readouts = _load_table("experiment_readouts", config, required=False)

    days = check_day_alignment(panel_rows, registry, external_rows)

    # Aggregate the scoped rate panel into daily totals for the persistent
    # control baseline, keeping denominators for rate metrics and scoped RCA.
    if config.metric_unit not in {"rate", "count", "currency", "currency_per_user"}:
        raise ContractError("unsupported metric_unit")
    control_denominators = {day: 0.0 for day in days}
    treated_denominators = {day: 0.0 for day in days}
    control_by_day = {day: 0.0 for day in days}
    treated_by_day = {day: 0.0 for day in days}
    scoped_panel: list[dict[str, Any]] = []
    for row in panel_rows:
        day = row["day"]
        if monetary:
            control_by_day[day] += row["control_value"]
            treated_by_day[day] += row["treatment_value"]
            control_denominators[day] += row["control_users"]
            treated_denominators[day] += row["treatment_users"]
            continue
        control_denominators[day] += row["control_impressions"]
        treated_denominators[day] += row["treatment_impressions"]
        control_by_day[day] += row["control_clicks"]
        treated_by_day[day] += row["treatment_clicks"]
        scoped_panel.append(
            {
                "day": day,
                "scope": {
                    "region": row["region"],
                    "channel": row["channel"],
                    "version": row["version"],
                },
                "control": {
                    "clicks": int(row["control_clicks"]),
                    "impressions": int(row["control_impressions"]),
                },
                "treatment": {
                    "clicks": int(row["treatment_clicks"]),
                    "impressions": int(row["treatment_impressions"]),
                },
            }
        )

    experiments = {
        r["experiment_id"]: {k: v for k, v in r.items() if k != "experiment_id"}
        for r in readouts
    }
    population = config.target_population
    metric_contract = {
        "name": config.metric_name,
        "numerator": "monetary_value" if monetary else config.numerator_event,
        "denominator": ("users" if monetary else config.denominator_event)
        if config.metric_unit in {"rate", "currency_per_user"}
        else None,
        "aggregation": "ratio_of_sums"
        if config.metric_unit in {"rate", "currency_per_user"}
        else "sum",
        "unit": config.metric_unit,
        "analysis_unit": "day",
        "target_population": population,
        "timezone": config.timezone,
        "window": [days[0], days[-1]],
        "maturity_days": config.maturity_days,
        "deduplication": config.deduplication,
    }
    from .contracts import digest, validate_contract

    metric_contract = validate_contract("MetricContract", metric_contract)
    if config.metric_unit in {"rate", "currency_per_user"}:
        control_by_day = {
            d: v / control_denominators[d] for d, v in control_by_day.items()
        }
        treated_by_day = {
            d: v / treated_denominators[d] for d, v in treated_by_day.items()
        }
    normalized_registry: list[dict[str, Any]] = []
    for change in registry:
        item = {
            "change_id": change["change_id"],
            "start_day": change["start_day"],
            "scope": change["scope"],
            "registered": change.get("registered", True),
        }
        for key in (
            "coverage",
            "end_day",
            "ramp_days",
            "allocation_weight",
            "target_population",
        ):
            if key in change:
                item[key] = change[key]
        exp_id = change.get("experiment_id")
        if exp_id and exp_id in experiments:
            item["experiment_id"] = exp_id
        normalized_registry.append(item)

    external = [
        {
            "event_id": event["event_id"],
            "start_day": event["start_day"],
            "end_day": event["end_day"],
            "kind": event["kind"],
            "desc": event.get("source_uri") or event["event_id"],
        }
        for event in external_rows
    ]
    events = [
        {
            "factor_id": event["event_id"],
            "source_type": event.get("source_type") or "external_event",
            "kind": event["kind"],
            "start_day": event["start_day"],
            "end_day": event["end_day"],
            "scope_match": 0.6,
            "source_reliability": 0.7,
            "source_uri": event.get("source_uri")
            or f"{config.source_uri_prefix}/events/{event['event_id']}",
            "license_ref": event.get("license_ref") or config.license_ref,
        }
        for event in external_rows
    ]

    factor_series: dict[tuple[str, str], dict[str, Any]] = {}
    for row in factor_rows:
        entry = factor_series.setdefault(
            (row["factor_id"], row.get("scope_id") or "global"),
            {
                "factor_id": row["factor_id"],
                "source_type": "factor_series",
                "kind": row["factor_id"].split(".")[0]
                if "." in row["factor_id"]
                else "unknown",
                "scope_id": row.get("scope_id") or "global",
                "unit": row.get("unit") or "value",
                "days": [],
                "values": [],
                "scope_match": 0.6,
                "source_reliability": 0.7,
                "source_uri": f"{config.source_uri_prefix}/factors/{row['factor_id']}",
                "license_ref": config.license_ref,
                "experimentability": "external_or_observational",
            },
        )
        entry["days"].append(row["day"])
        entry["values"].append(row["value"])
    for entry in factor_series.values():
        order = sorted(range(len(entry["days"])), key=lambda i: entry["days"][i])
        entry["days"] = [entry["days"][i] for i in order]
        entry["values"] = [entry["values"][i] for i in order]

    return {
        "days": days,
        "control": [control_by_day[day] for day in days],
        "treated": [treated_by_day[day] for day in days],
        "experiments": experiments,
        "metric_contract": metric_contract,
        "registry": normalized_registry,
        "external": external,
        "events": events,
        "scoped_panel": scoped_panel,
        "panel_row_count": len(panel_rows),
        "factor_series": list(factor_series.values()),
        "provenance": {
            "mode": "company_adapter",
            "input_digest": digest(
                {
                    "panel": panel_rows,
                    "registry": registry,
                    "events": external_rows,
                    "factors": factor_rows,
                    "readouts": readouts,
                }
            ),
            "config_digest": digest({**vars(config), "data_dir": str(config.data_dir)}),
            "label": config.label,
            "data_dir": str(config.data_dir),
            "license_ref": config.license_ref,
            "metric": {"name": config.metric_name, "unit": config.metric_unit},
            "tables": {
                table: (
                    config.data_dir / config.files.get(table, DEFAULT_FILES[table])
                ).name
                for table in (
                    *(
                        "value_panel" if monetary and t == "metric_panel" else t
                        for t in REQUIRED_TABLES
                    ),
                    *OPTIONAL_TABLES,
                )
            },
        },
    }


def intake_factor_series(registry, factor_series, *, current_window, available_day):
    """Persist declared adapter sources for the next window, retaining derivation lineage."""
    results = []
    for series in factor_series:
        days, values = series["days"], series["values"]
        if len(days) != len(values) or not days:
            raise ValueError("aligned nonempty factor series required")
        source, license_ref = series["source_uri"], series["license_ref"]
        contract = {
            "factor_id": series["factor_id"],
            "source_uri": source,
            "unit": series["unit"],
            "grain": series.get("grain", "day"),
            "lineage": series.get("lineage", []),
            "constraints": series.get("constraints", {}),
            "window": [min(days), max(days)],
            "response_window": series["response_window"],
        }
        factor = {
            "factor_id": series["factor_id"],
            "name": series.get("name", series["factor_id"]),
            "aliases": series.get("aliases", []),
            "source_type": series["source_type"],
            "license_ref": license_ref,
            "metadata": {
                "kind": series.get("kind", "continuous"),
                "factor_contract": contract,
            },
        }
        evidence = {
            "factor_id": series["factor_id"],
            "evidence_type": "adapter_snapshot",
            "source_uri": source,
            "license_ref": license_ref,
        }
        snapshots = [
            {
                "factor_id": series["factor_id"],
                "scope_id": series.get("scope_id", "global"),
                "day": day,
                "value": value,
                "source_uri": source,
                "license_ref": license_ref,
            }
            for day, value in zip(days, values)
        ]
        results.append(
            registry.intake_next_window(
                factor,
                evidence=[evidence],
                snapshots=snapshots,
                current_window=current_window,
                available_day=available_day,
            )
        )
    return results
