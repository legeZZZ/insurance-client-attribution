"""Declared enterprise file adapters; all execution uses the existing engines."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .contracts import digest, integer, validate_contract
from .hypothesis_registry import HypothesisRegistry


def _table(root, declaration):
    path = (root / declaration["path"]).resolve()
    raw = path.read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("enterprise table exceeds 32 MiB")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    else:
        rows = json.loads(raw)
    if not isinstance(rows, list):
        raise TypeError("table must contain an array of rows")
    mapping = declaration.get("field_mapping", {})
    if len(set(mapping.values())) != len(mapping.values()):
        raise ValueError("field mapping aliases collide")
    mapped = []
    for row in rows:
        out = {}
        for key, value in row.items():
            key = mapping.get(key, key)
            if key in out:
                raise ValueError("field mapping overwrites an existing column")
            out[key] = value
        mapped.append(out)
    return mapped, {
        "path": str(path),
        "sha256": digest(rows),
        "mapped_digest": digest(mapped),
        "rows": len(rows),
    }


def load_manifest(path, *, as_of):
    path = Path(path).resolve()
    body = json.loads(path.read_text())
    if body.get("schema") != "enterprise/1" or body.get("line") not in {"A", "B", "C"}:
        raise ValueError("enterprise/1 and line A/B/C required")
    source = body.get("source", {})
    if any(not source.get(k) for k in ("source_uri", "license_ref", "timezone")):
        raise ValueError("declared source/timezone/license metadata required")
    if integer(source["available_day"], "available_day") > integer(as_of, "as_of"):
        raise ValueError("data unavailable at analysis time")
    loaded, evidence = {}, []
    for name, declaration in body.get("tables", {}).items():
        loaded[name], item = _table(path.parent, declaration)
        evidence.append({"table": name, **item})
    return (
        body,
        loaded,
        {
            "manifest_digest": digest(body),
            "tables": evidence,
            "source": source,
            "as_of": as_of,
        },
    )


def run_enterprise(*, manifest_path, as_of, runtime_dir):
    from .agent_orchestrator import run_pipeline
    from .baseline_attribution import attribute_baseline
    from .watchlist_scan import run_c_line

    body, tables, provenance = load_manifest(manifest_path, as_of=as_of)
    parameters = dict(body.get("parameters", {}))
    metric = validate_contract("MetricContract", body["metric_contract"])
    if metric["timezone"] != body["source"]["timezone"]:
        raise ValueError("metric/source timezone mismatch")
    if metric["window"][1] + metric["maturity_days"] > as_of:
        raise ValueError("metric window is not mature")
    line = body["line"]
    if line == "A":
        rows = tables.get("observations", [])
        if not rows:
            raise ValueError("A requires row-level observations")
        seen = set()
        for row in rows:
            if not str(row.get("unit_id", "")) or row["unit_id"] in seen:
                raise ValueError("nonempty unique assignment units required")
            seen.add(row["unit_id"])
            row["treatment"] = integer(float(row["treatment"]), "treatment")
            row["outcome"] = float(row["outcome"])
            for field in parameters.get("features", []):
                row[field] = float(row[field])
        parameters.update(rows=rows, metric_contract=metric, observed_through=as_of)
        result = run_pipeline({"route": "A", "parameters": parameters})
    elif body.get("route") in {
        "B_DiD",
        "B_series",
        "B_ratio",
        "B_staggered_DiD",
        "B_BSTS_mixture",
        "C",
    }:
        if (
            line == "B"
            and not body["route"].startswith("B_")
            or line == "C"
            and body["route"] != "C"
        ):
            raise ValueError("line and causal route mismatch")
        parameters.update(tables)
        parameters.update(metric_contract=metric, observed_through=as_of)
        result = run_pipeline({"route": body["route"], "parameters": parameters})
    else:
        panel = sorted(
            tables.get("panel", []), key=lambda r: integer(float(r["day"]), "day")
        )
        days = [integer(float(r["day"]), "day") for r in panel]
        if not panel or max(days) > as_of:
            raise ValueError("nonempty as-of panel required")
        grouped = {}
        for row in tables.get("factors", []):
            key = (
                row["factor_id"],
                row.get("scope_id", "global"),
                row.get("metric_id", metric["name"]),
            )
            item = grouped.setdefault(
                key,
                {
                    "factor_id": key[0],
                    "scope_id": key[1],
                    "metric_id": key[2],
                    "days": [],
                    "values": [],
                    "effect_shape": row.get("effect_shape", "persistent"),
                },
            )
            day = integer(float(row["day"]), "day")
            if day > as_of:
                raise ValueError("future factor values forbidden")
            item["days"].append(day)
            item["values"].append(float(row["value"]))
        factors = list(grouped.values())
        baseline = None
        if line == "B":
            baseline = attribute_baseline(
                days,
                [float(r["control"]) for r in panel],
                [float(r["treated"]) for r in panel],
                tables.get("changes", []),
                tables.get("external_events", []),
                body.get("experiments", {}),
                metric_contract=metric,
                detection_threshold=parameters.pop("detection_threshold", None),
            )
            residual = baseline["series"]["residual"]
        else:
            residual = [float(r["residual"]) for r in panel]
        scan = run_c_line(days, residual, factors, **parameters)
        result = {
            "baseline": baseline,
            "scan": scan,
            "execution_status": "COMPLETED",
            "causal_eligible": False,
        }
    registry = HypothesisRegistry(Path(runtime_dir) / "enterprise.db")
    try:
        data_ref = registry.revise_resource(
            "enterprise:" + body["case_id"],
            {"provenance": provenance, "manifest": body, "tables": tables},
        )["ref"]
        result_ref = registry.add_asset("manifest", result, dependencies=[data_ref])
        registry._audit(
            "ENTERPRISE_SANDBOX_EXECUTED",
            {
                "case_id": body["case_id"],
                "data_ref": data_ref,
                "result_ref": result_ref,
            },
        )
    finally:
        registry.close()
    return {
        "schema": "enterprise-result/1",
        "case_id": body["case_id"],
        "domain": body["domain"],
        "line": line,
        "engine": "track2_v5_shared",
        "mode": "sandbox_no_production_actions",
        "provenance": provenance,
        "data_ref": data_ref,
        "result_ref": result_ref,
        "result": result,
    }


def external_adapter(*, kind, parameters):
    """Replaceable capability interfaces; N3 deliberately has no production mode."""
    if kind == "N1":
        from .adapters import intake_factor_series
        from .factor_registry import FactorRegistry

        registry = FactorRegistry(parameters["db_path"])
        try:
            result = intake_factor_series(
                registry,
                parameters["factor_series"],
                current_window=parameters["current_window"],
                available_day=parameters["available_day"],
            )
            return {"result": result, "status": "INTAKE_QUEUED"}
        finally:
            registry.close()
    if kind == "N2":
        from .policy_adapter import LocalPolicyAdapter

        return LocalPolicyAdapter(**parameters.get("provider", {})).propose(
            parameters["snapshot"], factor_ids=parameters["factor_ids"]
        )
    if kind == "N3":
        from .experiment_platform import DryRunExperimentPlatform

        if parameters.get("mode", "sandbox") != "sandbox":
            raise ValueError(
                "production traffic operations require business platform; sandbox only"
            )
        platform = DryRunExperimentPlatform(metric_fixture=parameters.get("metrics"))
        record = platform.create_experiment(
            parameters["design"], parameters["approval_ref"]
        )
        canary = platform.start_canary(record["experiment_id"], 5)
        metrics = platform.read_metrics(record["experiment_id"])
        failed = [
            key
            for key, value in metrics.get("guardrails", {}).items()
            if value["value"] > value["limit"]
        ]
        final = (
            platform.pause_experiment(record["experiment_id"], ",".join(failed))
            if failed
            else canary
        )
        return {
            "record": record,
            "canary": canary,
            "metrics": metrics,
            "final": final,
            "side_effect": "none_sandbox",
        }
    raise ValueError("adapter kind must be N1/N2/N3")
