"""Data contract for external (company intranet) data sources.

Defines the five logical tables the attribution pipeline consumes, plus
row-level validation.  The goal: a company can map its own exports onto
these tables via `config.json` field mapping and run the *same* algorithmic
core that the demo fixtures use — no code changes.

Tables
------
metric_panel        日度 × 分层（region/channel/version 等）的处理/对照分子分母
factor_snapshots    内外部因子的日度取值快照
change_registry     已登记内部变更（可选挂实验读数）
external_events     外部/内部事件候选（时间窗 + 范围 + 来源）
experiment_readouts 已登记变更对应的实验 ATT 读数（可选）

All validation errors are raised as `ContractError` with machine-readable
messages so the console can show *which row, which column, why*.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


class ContractError(ValueError):
    """Raised when an external data table violates the contract."""


# --- table specs ------------------------------------------------------------

# column -> (type, required, check)  check receives the parsed value
TABLE_SPECS: dict[str, dict[str, tuple[str, bool]]] = {
    "value_panel": {
        "day": ("int", True),
        "region": ("str", True),
        "channel": ("str", True),
        "version": ("str", True),
        "control_value": ("number", True),
        "treatment_value": ("number", True),
        "control_users": ("int", True),
        "treatment_users": ("int", True),
    },
    "metric_panel": {
        "day": ("int", True),
        "region": ("str", True),
        "channel": ("str", True),
        "version": ("str", True),
        "control_clicks": ("number", True),
        "control_impressions": ("number", True),
        "treatment_clicks": ("number", True),
        "treatment_impressions": ("number", True),
        "missing_rate": ("number", False),
        "late_arrival_rate": ("number", False),
    },
    "factor_snapshots": {
        "factor_id": ("str", True),
        "day": ("int", True),
        "value": ("number", True),
        "scope_id": ("str", False),
        "unit": ("str", False),
    },
    "change_registry": {
        "change_id": ("str", True),
        "start_day": ("int", True),
        "scope": ("str", True),
        "experiment_id": ("str", False),
        "owner": ("str", False),
        "registered": ("bool", False),
        "coverage": ("number", False),
        "end_day": ("int", False),
        "ramp_days": ("int", False),
        "allocation_weight": ("number", False),
        "target_population": ("str", False),
    },
    "external_events": {
        "event_id": ("str", True),
        "kind": ("str", True),
        "start_day": ("int", True),
        "end_day": ("int", True),
        "source_type": ("str", False),
        "source_uri": ("str", False),
        "license_ref": ("str", False),
        "claim_type": ("str", False),
    },
    "experiment_readouts": {
        "experiment_id": ("str", True),
        "att_estimate": ("number", True),
        "att_se": ("number", True),
        "unit": ("str", False),
        "target_population": ("str", False),
        "estimand": ("str", False),
        "evidence_ref": ("str", False),
        "pooling_group": ("str", False),
    },
    # 埋点事件明细（可选）。粒度：一行 = 一个主体在一个事件上的一次记录。
    # 聚合为 metric_panel 的规则见 adapters.aggregate_events_to_panel。
    "tracking_events": {
        "day": ("int", True),
        "event_name": ("str", True),  # 如 impression / click / submit / pay_success
        "subject_id": ("str", True),  # 必须是散列后的主体 ID，禁止明文身份证/手机号
        "arm": ("str", True),  # control | treatment
        "region": ("str", True),
        "channel": ("str", True),
        "version": ("str", True),
        "value": ("number", False),  # 金额类事件的可选取值
    },
    # A 线实验暴露表（可选）：一行 = 一个主体在一个实验中的分组。
    "experiment_exposures": {
        "experiment_id": ("str", True),
        "subject_id": ("str", True),
        "variant": ("str", True),  # 如 A / B / bundle_x
        "day": ("int", True),
        "converted": ("bool", False),  # 是否转化（用于门禁与效应估计）
    },
}

REQUIRED_TABLES = ("metric_panel", "change_registry", "external_events")
OPTIONAL_TABLES = (
    "factor_snapshots",
    "experiment_readouts",
    "tracking_events",
    "experiment_exposures",
)


def _reject_plain_identifier(value: str, where: str) -> None:
    """Privacy guard: subject ids must be hashed, never raw phone / id numbers."""
    text = str(value).strip()
    if text.isdigit() and (len(text) == 11 or len(text) in {15, 18}):
        raise ContractError(
            f"{where}: looks like a raw phone/id number; subject_id must be hashed "
            f"(e.g. sha256 with a salt kept inside the company)"
        )


def _parse_value(raw: Any, kind: str, where: str) -> Any:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ContractError(f"{where}: value is empty")
    try:
        if kind == "int":
            parsed = Decimal(str(raw).strip())
            if not parsed.is_finite() or parsed != parsed.to_integral_value():
                raise ContractError(f"{where}: must be a finite integer")
            value = int(parsed)
        elif kind == "number":
            value = float(str(raw).strip())
            if not math.isfinite(value):
                raise ContractError(f"{where}: value must be finite, got {raw!r}")
            return value
        elif kind == "bool":
            text = str(raw).strip().lower()
            if text in {"true", "1", "yes", "y", "是"}:
                return True
            if text in {"false", "0", "no", "n", "否"}:
                return False
            raise ContractError(f"{where}: cannot parse boolean from {raw!r}")
        else:
            return str(raw).strip()
    except (TypeError, ValueError, OverflowError, InvalidOperation) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"{where}: cannot parse {kind} from {raw!r}") from exc
    return value


def validate_rows(
    table: str, rows: Iterable[Mapping[str, Any]], *, min_rows: int = 1
) -> list[dict[str, Any]]:
    """Validate and normalize rows of one table. Returns typed dicts."""
    if table not in TABLE_SPECS:
        raise ContractError(f"unknown table: {table}")
    spec = TABLE_SPECS[table]
    output: list[dict[str, Any]] = []
    seen_keys: set[tuple] = set()
    for index, raw in enumerate(rows):
        where = f"{table}[{index}]"
        row: dict[str, Any] = {}
        for column, (kind, required) in spec.items():
            value = raw.get(column)
            if value is None or (isinstance(value, str) and not value.strip()):
                if required:
                    raise ContractError(f"{where}.{column}: required but missing")
                continue
            row[column] = _parse_value(value, kind, f"{where}.{column}")
        output.append(row)
        if table == "value_panel":
            if row["control_users"] <= 0 or row["treatment_users"] <= 0:
                raise ContractError(f"{where}: users must be positive integers")
        if table == "metric_panel":
            key = (
                row["day"],
                row["region"],
                row["channel"],
                row["version"],
            )
            if key in seen_keys:
                raise ContractError(
                    f"{where}: duplicate (day, region, channel, version)"
                )
            seen_keys.add(key)
            for arm in ("control", "treatment"):
                clicks = row[f"{arm}_clicks"]
                impressions = row[f"{arm}_impressions"]
                if not clicks.is_integer() or not impressions.is_integer():
                    raise ContractError(
                        f"{where}: counts must be integers, not weighted observations"
                    )
                if impressions <= 0:
                    raise ContractError(f"{where}.{arm}_impressions: must be > 0")
                if clicks < 0 or clicks > impressions:
                    raise ContractError(
                        f"{where}.{arm}_clicks: must satisfy 0 <= clicks <= impressions"
                    )
        key_columns = {
            "value_panel": ("day", "region", "channel", "version"),
            "factor_snapshots": ("factor_id", "scope_id", "day"),
            "experiment_readouts": ("experiment_id",),
            "change_registry": ("change_id",),
            "external_events": ("event_id",),
        }.get(table)
        if key_columns:
            signature = tuple(
                row.get(k, "global" if k == "scope_id" else None) for k in key_columns
            )
            if signature in seen_keys:
                raise ContractError(f"{where}: duplicate {key_columns}")
            seen_keys.add(signature)
        if table == "external_events" and row["start_day"] > row["end_day"]:
            raise ContractError(f"{where}: start_day must be <= end_day")
        if table == "experiment_readouts" and row["att_se"] <= 0:
            raise ContractError(f"{where}.att_se: must be > 0")
        if table == "tracking_events":
            if row["arm"] not in {"control", "treatment"}:
                raise ContractError(
                    f"{where}.arm: must be control|treatment, got {row['arm']!r}"
                )
            _reject_plain_identifier(row["subject_id"], f"{where}.subject_id")
        if table == "experiment_exposures":
            _reject_plain_identifier(row["subject_id"], f"{where}.subject_id")
    if len(output) < min_rows:
        raise ContractError(
            f"{table}: need at least {min_rows} rows, got {len(output)}"
        )
    return output


def check_day_alignment(
    panel: Sequence[Mapping[str, Any]],
    change_registry: Sequence[Mapping[str, Any]],
    external_events: Sequence[Mapping[str, Any]],
) -> list[int]:
    """All registry/event days must exist in the panel's day axis."""
    days = sorted({int(row["day"]) for row in panel})
    day_set = set(days)
    for index, change in enumerate(change_registry):
        if int(change["start_day"]) not in day_set:
            raise ContractError(
                f"change_registry[{index}].start_day={change['start_day']} "
                f"not in panel days ({days[0]}..{days[-1]})"
            )
    for index, event in enumerate(external_events):
        for key in ("start_day", "end_day"):
            if int(event[key]) not in day_set:
                raise ContractError(
                    f"external_events[{index}].{key}={event[key]} "
                    f"not in panel days ({days[0]}..{days[-1]})"
                )
    return days
