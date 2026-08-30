"""Real-data adapter for the UCI Bank Marketing history."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .foundation import LocalEvidenceProvider

DATASET_ID = "uci-bank-marketing"
DATASET_NAME = "UCI Bank Marketing"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/222/data.csv"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/222/bank+marketing"
LICENSE = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
DATASET_DOI = "10.24432/C5K306"
EXPECTED_SHA256 = "94a5cb4b7d461dab12f7f6123723054911fbdd28d84a2c4ec92378af019be686"
REQUIRED_FIELDS = (
    "age",
    "job",
    "marital",
    "education",
    "default",
    "balance",
    "housing",
    "loan",
    "contact",
    "day_of_week",
    "month",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
    "y",
)
NUMERIC_FIELDS = ("age", "balance", "duration", "campaign", "pdays", "previous")
SEGMENT_FIELDS = ("contact", "month", "job", "poutcome")
MISSING_MARKERS = {"", "nan", "null", "none"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_digest(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _is_missing(value: str | None) -> bool:
    return value is None or value.strip().lower() in MISSING_MARKERS


def _safe_float(value: str | None) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _segment_summary(values: Mapping[str, tuple[int, int]]) -> list[dict[str, Any]]:
    rows = [
        {
            "value": value,
            "records": counts[0],
            "subscriptions": counts[1],
            "subscription_rate": round(counts[1] / counts[0], 6) if counts[0] else 0.0,
        }
        for value, counts in values.items()
    ]
    return sorted(rows, key=lambda item: (-int(item["records"]), str(item["value"])))


def _source_manifest(path: Path, digest: str) -> dict[str, Any]:
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    return {
        "dataset_id": DATASET_ID,
        "name": DATASET_NAME,
        "official_source": SOURCE_URL,
        "official_page": SOURCE_PAGE,
        "dataset_doi": DATASET_DOI,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution": "S. Moro, P. Rita and P. Cortez; UCI Machine Learning Repository",
        "local_path": str(path),
        "bytes": path.stat().st_size,
        "sha256": digest,
        "expected_sha256": EXPECTED_SHA256,
        "checksum_verified": digest == EXPECTED_SHA256,
        "retrieved_at": modified,
    }


def fetch_bank_marketing_csv(destination: Path, force: bool = False) -> Path:
    """Download the official UCI file and fail if its pinned digest changes."""
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and not force:
        digest = _sha256_file(destination)
        if digest != EXPECTED_SHA256:
            raise ValueError("cached UCI Bank Marketing file failed SHA-256 verification")
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "insurance-attribution/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
        digest = _sha256_file(temporary)
        if digest != EXPECTED_SHA256:
            raise ValueError("downloaded UCI Bank Marketing file failed pinned SHA-256 verification")
        os.replace(str(temporary), str(destination))
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _evidence(kind: str, label: str, content: Mapping[str, Any], index: int) -> dict[str, Any]:
    digest = _content_digest(content)
    return {
        "evidence_id": "ev_real_%02d_%s" % (index, digest[:10]),
        "kind": kind,
        "label": label,
        "content": dict(content),
        "content_digest": digest,
        "source": "uci-official",
    }


def _artifact(
    artifact_type: str,
    producer: str,
    payload: Mapping[str, Any],
    evidence_ref: str,
    index: int,
) -> dict[str, Any]:
    digest = _content_digest(payload)
    return {
        "artifact_id": "art_real_%02d_%s" % (index, digest[:10]),
        "artifact_type": artifact_type,
        "schema_version": "1.0",
        "producer": producer,
        "payload": dict(payload),
        "evidence_refs": [evidence_ref],
    }


def analyze_bank_marketing_csv(path: Path, max_rows: int | None = None) -> dict[str, Any]:
    """Profile genuine historical rows without inventing an insurance funnel."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"UCI Bank Marketing CSV not found: {path}")
    digest = _sha256_file(path)
    if digest != EXPECTED_SHA256 and max_rows is None:
        raise ValueError("UCI Bank Marketing CSV failed pinned SHA-256 verification")

    missing_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    numeric: dict[str, dict[str, float]] = {
        field: {"count": 0.0, "sum": 0.0, "min": float("inf"), "max": float("-inf")}
        for field in NUMERIC_FIELDS
    }
    segments: dict[str, defaultdict[str, list[int]]] = {
        field: defaultdict(lambda: [0, 0]) for field in SEGMENT_FIELDS
    }
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        missing_fields = sorted(set(REQUIRED_FIELDS) - set(fields))
        if missing_fields:
            raise ValueError("UCI Bank Marketing CSV is missing fields: {}".format(", ".join(missing_fields)))
        for row in reader:
            if max_rows is not None and row_count >= max_rows:
                break
            row_count += 1
            subscribed = str(row.get("y", "")).strip().lower() == "yes"
            target_counts["yes" if subscribed else "no"] += 1
            for field in fields:
                if _is_missing(row.get(field)):
                    missing_counts[field] += 1
            for field in NUMERIC_FIELDS:
                value = _safe_float(row.get(field))
                if value is None:
                    continue
                summary = numeric[field]
                summary["count"] += 1.0
                summary["sum"] += value
                summary["min"] = min(summary["min"], value)
                summary["max"] = max(summary["max"], value)
            for field in SEGMENT_FIELDS:
                value = str(row.get(field) or "NaN")
                segments[field][value][0] += 1
                segments[field][value][1] += int(subscribed)

    numeric_summary: dict[str, dict[str, Any]] = {}
    for field, summary in numeric.items():
        count = int(summary["count"])
        numeric_summary[field] = {
            "count": count,
            "min": summary["min"] if count else None,
            "max": summary["max"] if count else None,
            "mean": round(summary["sum"] / count, 6) if count else None,
        }

    subscriptions = int(target_counts["yes"])
    source = _source_manifest(path, digest)
    profile = {
        "row_count": row_count,
        "field_count": len(fields),
        "fields": fields,
        "target": "y",
        "subscriptions": subscriptions,
        "non_subscriptions": int(target_counts["no"]),
        "subscription_rate": round(subscriptions / row_count, 6) if row_count else 0.0,
        "missing_cells": sum(missing_counts.values()),
        "missing_by_field": dict(sorted(missing_counts.items())),
        "numeric_summary": numeric_summary,
        "segment_subscription_rates": {
            field: _segment_summary({key: (value[0], value[1]) for key, value in values.items()})
            for field, values in segments.items()
        },
    }
    feature_policy = {
        "prediction_time": "before outbound call",
        "blocked_features": [
            {
                "field": "duration",
                "reason_code": "POST_OUTCOME_LEAKAGE",
                "reason": "Call duration is only known after the call has occurred and must not be used for pre-call targeting.",
            },
            {"field": "y", "reason_code": "OUTCOME_FIELD", "reason": "Subscription is the target outcome."},
        ],
        "allowed_pre_call_features": [field for field in fields if field not in {"duration", "y"}],
        "restricted_individual_targeting_fields": ["age", "marital", "education", "job"],
        "evidence_pack_policy": "aggregate-only; no row samples or individual targeting lists",
    }
    readiness = {
        "outcome": "DESCRIPTIVE_ONLY",
        "evidence_level": "L1/L2",
        "identification_strategy": "not identified",
        "allowed_claim_type": "descriptive_only",
        "reason_codes": [
            "NO_TREATMENT_ASSIGNMENT",
            "NO_RANDOMIZATION_PROVENANCE",
            "POST_OUTCOME_LEAKAGE_FIELD_BLOCKED",
        ],
        "gates": [
            {"name": "source", "passed": source["checksum_verified"], "reason_code": "OFFICIAL_SOURCE_VERIFIED"},
            {"name": "schema", "passed": row_count > 0, "reason_code": "REAL_ROWS_PROFILED"},
            {"name": "leakage", "passed": True, "reason_code": "POST_OUTCOME_FIELD_EXCLUDED"},
            {"name": "design", "passed": False, "reason_code": "CAUSAL_DESIGN_NOT_AVAILABLE"},
        ],
    }
    claim = {
        "claim_id": "claim-real-001",
        "claim_type": "descriptive_only",
        "evidence_level": "L1/L2",
        "allowed_verbs": ["观察到", "历史记录显示", "对应"],
        "prohibited_actions": ["声称导致", "使用 duration 做呼叫前决策", "生成个人营销名单"],
        "statement": (
            "UCI 的 %d 条真实银行营销记录中，定期存款订阅率为 %.2f%%。"
            "该数据没有随机处理分配，且 duration 属于结果后变量，因此只能报告历史相关性，不能声称因果。"
        ) % (row_count, profile["subscription_rate"] * 100.0),
    }

    evidence = [
        _evidence("source", "official UCI source and checksum", source, 1),
        _evidence("data-quality", "real-data schema and missingness audit", profile, 2),
        _evidence("leakage", "pre-call leakage policy", feature_policy, 3),
        _evidence("causal-readiness", "observational causal-readiness refusal", readiness, 4),
        _evidence("claim-ledger", "real-data claim boundary", claim, 5),
    ]
    artifacts = [
        _artifact("SourceManifest", "data_acquisition", source, evidence[0]["evidence_id"], 1),
        _artifact("DataQualityReport", "data_acquisition", profile, evidence[1]["evidence_id"], 2),
        _artifact("FeaturePolicy", "diagnostic", feature_policy, evidence[2]["evidence_id"], 3),
        _artifact("EvidenceReport", "causal_evidence", readiness, evidence[3]["evidence_id"], 4),
        _artifact("ClaimLedger", "causal_evidence", claim, evidence[4]["evidence_id"], 5),
    ]
    trace_id = "trace_real_" + digest[:12]
    trace = [{"event_type": "TASK_CREATED", "payload": {}}]
    for target in ("DATA_VALIDATED", "DIAGNOSING", "EVIDENCE_GRADED", "DESCRIPTIVE_ONLY", "CLOSED"):
        trace.append({"event_type": "STATE_TRANSITION", "payload": {"to": target}})

    return {
        "task_id": "T2-real-uci-bank-marketing",
        "trace_id": trace_id,
        "state": "CLOSED",
        "state_version": 5,
        "real_data": True,
        "case": "REAL",
        "provider": "uci-official",
        "agents": ["data_acquisition", "diagnostic", "causal_evidence"],
        "skills": ["SchemaProfiler", "DataQualityGate", "SegmentProfiler", "CausalReadinessCheck", "ClaimPolicyGuard"],
        "topologies": [],
        "trace": trace,
        "artifacts": artifacts,
        "evidence": evidence,
        "source": source,
        "profile": profile,
        "feature_policy": feature_policy,
        "causal_readiness": readiness,
        "claim": claim,
        "summary": {
            "final_state": "CLOSED",
            "claim_type": "descriptive_only",
            "evidence_level": "L1/L2",
            "causal_outcome": "DESCRIPTIVE_ONLY",
        },
    }


def run_real_data_case(base_dir: Path, csv_path: Path) -> dict[str, Any]:
    pack = analyze_bank_marketing_csv(csv_path)
    LocalEvidenceProvider(base_dir / "evidence").write_pack(str(pack["task_id"]), pack)
    return pack
