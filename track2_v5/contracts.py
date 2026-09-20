"""Versioned six-contract validation. Values are JSON, not executable expressions.

Validation establishes internal consistency, never certifies business assumptions.
Identification decisions are produced by the identification engine (phase B).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .data_contract import ContractError

SCHEMA_VERSION = "1.0"
REASONS = {
    "DATA_INVALID",
    "INSUFFICIENT_POWER",
    "NOT_IDENTIFIABLE",
    "GRAPH_AMBIGUOUS",
    "CONTROL_CONTAMINATED",
    "MODEL_MISMATCH",
}
REQUIRED = {
    "MetricContract": (
        "name",
        "numerator",
        "denominator",
        "aggregation",
        "unit",
        "analysis_unit",
        "target_population",
        "timezone",
        "window",
        "maturity_days",
        "deduplication",
    ),
    "FactorContract": (
        "factor_id",
        "source_uri",
        "available_at",
        "as_of",
        "unit",
        "grain",
        "lineage",
        "constraints",
        "window",
        "response_window",
    ),
    "InterventionContract": (
        "treatment_version",
        "control_version",
        "assignment_ref",
        "exposure_ref",
        "target_population",
        "window",
        "randomization_unit",
        "controllable",
        "estimand",
    ),
    "TestFamilyContract": (
        "hypothesis_keys",
        "search_manifest",
        "null_hypothesis",
        "statistic",
        "null_model",
        "correction",
        "frozen_at",
        "discovery_window",
        "holdout_window",
        "gap_days",
    ),
    "IdentificationReport": (
        "treatment",
        "outcome",
        "design",
        "status",
        "assumptions",
        "evidence_refs",
        "adjustment_set",
        "forbidden_adjustments",
        "support",
        "ambiguities",
        "reason_codes",
    ),
    "EffectEstimate": (
        "estimand",
        "unit",
        "estimate",
        "interval",
        "interval_method",
        "selection_status",
        "target_population",
        "window",
        "diagnostics",
        "identification_ref",
    ),
}


def digest(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )


def finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ContractError(f"{field}: boolean is not a number")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContractError(f"{field}: must be finite") from exc
    if not math.isfinite(number):
        raise ContractError(f"{field}: must be finite")
    return number


def integer(value: Any, field: str) -> int:
    number = finite(value, field)
    if not number.is_integer():
        raise ContractError(f"{field}: must be an integer")
    return int(number)


def window(value: Any, field: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ContractError(f"{field}: requires [start_day, end_day]")
    result = [integer(v, field) for v in value]
    if result[0] > result[1]:
        raise ContractError(f"{field}: start must not exceed end")
    return result


def _strings(value: Any, field: str, *, nonempty: bool = False) -> None:
    if not isinstance(value, list) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        raise ContractError(f"{field}: requires a list of non-empty strings")
    if nonempty and not value:
        raise ContractError(f"{field}: must not be empty")
    if len(set(value)) != len(value):
        raise ContractError(f"{field}: duplicates are not allowed")


def validate_contract(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in REQUIRED or not isinstance(payload, Mapping):
        raise ContractError(f"unknown/invalid contract: {kind}")
    out = copy.deepcopy(dict(payload))
    if out.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ContractError(f"{kind}: unsupported schema_version")
    missing = [key for key in REQUIRED[kind] if key not in out]
    if missing:
        raise ContractError(f"{kind}: missing {missing}")
    if "window" in out:
        out["window"] = window(out["window"], f"{kind}.window")
    text_fields = {
        "MetricContract": (
            "name",
            "numerator",
            "aggregation",
            "unit",
            "analysis_unit",
            "target_population",
            "timezone",
            "deduplication",
        ),
        "FactorContract": ("factor_id", "source_uri", "unit", "grain"),
        "InterventionContract": (
            "treatment_version",
            "control_version",
            "assignment_ref",
            "exposure_ref",
            "target_population",
            "randomization_unit",
            "estimand",
        ),
        "TestFamilyContract": (
            "null_hypothesis",
            "statistic",
            "null_model",
            "correction",
        ),
        "IdentificationReport": ("treatment", "outcome", "design", "status"),
        "EffectEstimate": (
            "estimand",
            "unit",
            "interval_method",
            "selection_status",
            "target_population",
            "identification_ref",
        ),
    }
    for key in text_fields[kind]:
        if not isinstance(out[key], str) or not out[key].strip():
            raise ContractError(f"{kind}.{key}: requires non-empty text")
    if kind == "MetricContract":
        if out["unit"] not in {"rate", "count", "currency", "currency_per_user"}:
            raise ContractError("MetricContract.unit: unsupported metric scale")
        if out["unit"] in {"rate", "currency_per_user"} and not out["denominator"]:
            raise ContractError(
                "MetricContract.denominator: required for normalized metric"
            )
        if out["aggregation"] not in {"ratio_of_sums", "sum", "standardized_rate"}:
            raise ContractError("MetricContract.aggregation: unsupported")
        if (out["unit"] in {"rate", "currency_per_user"}) != (
            out["aggregation"] in {"ratio_of_sums", "standardized_rate"}
        ):
            raise ContractError("MetricContract: unit and aggregation do not match")
        if integer(out["maturity_days"], "maturity_days") < 0:
            raise ContractError("maturity_days must be non-negative")
        try:
            ZoneInfo(out["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ContractError("MetricContract.timezone: invalid timezone") from exc
    elif kind == "FactorContract":
        if finite(out["available_at"], "available_at") > finite(out["as_of"], "as_of"):
            raise ContractError("FactorContract: factor was unavailable at task time")
        window(out["response_window"], "response_window")
        if not isinstance(out["lineage"], list) or not isinstance(
            out["constraints"], dict
        ):
            raise ContractError(
                "FactorContract: lineage must be a list and constraints an object"
            )
    elif kind == "InterventionContract":
        if out["treatment_version"] == out["control_version"]:
            raise ContractError(
                "InterventionContract: identical treatment/control versions"
            )
        if type(out["controllable"]) is not bool:
            raise ContractError("controllable must be boolean")
        if (
            out["estimand"] == "ITT"
            and out.get("population_filter", "assigned") != "assigned"
        ):
            raise ContractError("ITT cannot filter on actual exposure/use")
    elif kind == "TestFamilyContract":
        _strings(out["hypothesis_keys"], "hypothesis_keys", nonempty=True)
        if not isinstance(out["search_manifest"], dict):
            raise ContractError("search_manifest must be an object")
        if out["correction"] not in {"holm", "max_t", "exploratory_only"}:
            raise ContractError("unsupported correction")
        a = window(out["discovery_window"], "discovery_window")
        b = window(out["holdout_window"], "holdout_window")
        gap = integer(out["gap_days"], "gap_days")
        if gap < 0 or b[0] - a[1] - 1 < gap:
            raise ContractError(
                "discovery/holdout overlap or insufficient isolation gap"
            )
        if finite(out["frozen_at"], "frozen_at") > b[0]:
            raise ContractError("family must freeze before holdout")
        alpha = finite(out.get("alpha", 0.05), "alpha")
        if not 0 < alpha < 1:
            raise ContractError("alpha must be between zero and one")
    elif kind == "IdentificationReport":
        for key in (
            "adjustment_set",
            "forbidden_adjustments",
            "ambiguities",
            "reason_codes",
            "evidence_refs",
        ):
            _strings(out[key], key)
        if not isinstance(out["assumptions"], list) or not isinstance(
            out["support"], dict
        ):
            raise ContractError("identification assumptions/support malformed")
        if set(out["adjustment_set"]) & set(out["forbidden_adjustments"]):
            raise ContractError("forbidden variable in adjustment set")
        if not set(out["reason_codes"]) <= REASONS:
            raise ContractError("unknown identification reason code")
        if out["status"] not in {
            "IDENTIFIED",
            "NOT_IDENTIFIED",
            "INSUFFICIENT_EVIDENCE",
        }:
            raise ContractError("unknown identification status")
        if out["status"] == "IDENTIFIED" and (
            out["ambiguities"] or out["reason_codes"] or not out["evidence_refs"]
        ):
            raise ContractError("unresolved or unsupported identification cannot pass")
        if out["status"] != "IDENTIFIED" and not out["reason_codes"]:
            raise ContractError("failed identification requires a reason")
    else:
        if not isinstance(out["diagnostics"], dict):
            raise ContractError("diagnostics must be an object")
        if out["estimate"] is None:
            if out["interval"] is not None:
                raise ContractError("absent estimate must have no interval")
        else:
            estimate = finite(out["estimate"], "estimate")
            interval = out["interval"]
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ContractError("effect interval must have two endpoints")
            low, high = (finite(v, "interval") for v in interval)
            if not low <= estimate <= high:
                raise ContractError("effect interval must contain its point estimate")
        if out["selection_status"] not in {
            "pre_registered",
            "independent_confirmation",
            "exploratory",
        }:
            raise ContractError("unknown selection status")
    out["schema_version"] = SCHEMA_VERSION
    out["contract_type"] = kind
    supplied = out.pop("digest", None)
    expected = digest(out)
    if supplied is not None and supplied != expected:
        raise ContractError(f"{kind}: content digest mismatch")
    out["digest"] = expected
    return out


def validate_bundle(contracts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Validate contracts jointly, including reference identity and estimand scope."""
    result = {kind: validate_contract(kind, value) for kind, value in contracts.items()}
    metric = result.get("MetricContract")
    intervention = result.get("InterventionContract")
    identification = result.get("IdentificationReport")
    effect = result.get("EffectEstimate")
    for other in (intervention, effect):
        if (
            metric
            and other
            and other["target_population"] != metric["target_population"]
        ):
            raise ContractError("cross-contract target_population mismatch")
        if (
            metric
            and other
            and (
                other["window"][0] < metric["window"][0]
                or other["window"][1] > metric["window"][1]
            )
        ):
            raise ContractError("effect/intervention window outside metric window")
    if effect:
        if not metric or not identification:
            raise ContractError(
                "EffectEstimate requires MetricContract and IdentificationReport"
            )
        if effect["unit"] != metric["unit"]:
            raise ContractError("cross-contract effect unit mismatch")
        if effect["identification_ref"] != identification["digest"]:
            raise ContractError("effect does not reference this identification report")
        if identification["status"] != "IDENTIFIED" and effect["estimate"] is not None:
            raise ContractError(
                "unidentified effect must not contain a causal estimate"
            )
    return result
