"""Bounded independent analyst processes; deterministic policy, frozen statistical core."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.contracts import digest
from track2_v5.skill_replay import OPS


def analyze(trace, replacement=None):
    failure = trace["outcome"] == "failure"
    selected = trace["correction"] if failure else trace
    issue = failure and trace["failure_kind"] in {"environment", "source_unavailable"}
    patch = None
    if not issue and selected and selected["replay"]["result"]["passed"]:
        if selected["operation"] not in OPS:
            raise ValueError("analyst cannot propose arbitrary executable operations")
        patch = {
            "when": trace["context"],
            "action": selected["operation"],
            "evidence": [trace["evidence_ref"]],
            "polarity": "guard" if failure else "reinforce",
            **({"replaces": replacement} if replacement is not None else {}),
        }
    return {
        "trace_id": trace["trace_id"],
        "patch": patch,
        "issue": issue,
        "negative_example": failure,
        "analyst_pid": os.getpid(),
        "policy": "verified-operation-only/1",
        "model_tokens": 0,
    }


def _run(item):
    raw = json.dumps(item, allow_nan=False).encode()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("analyst input exceeds budget")
    result = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve())],
        input=raw,
        capture_output=True,
        timeout=30,
        check=False,
        env={
            k: os.environ[k]
            for k in ("PATH", "TMPDIR", "SYSTEMROOT")
            if k in os.environ
        },
    )
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise ValueError("analyst rejected input or exceeded output budget")
    report = json.loads(result.stdout)
    if report.pop("input_digest") != digest(item):
        raise ValueError("analyst input binding mismatch")
    if report["trace_id"] != item["trace"]["trace_id"]:
        raise ValueError("analyst trace binding mismatch")
    return report


def analyze_parallel(traces, replacements=None):
    if not 0 < len(traces) <= 32:
        raise ValueError("each analyst batch requires 1..32 traces")
    replacements = replacements or {}
    with ThreadPoolExecutor(max_workers=min(4, len(traces))) as pool:
        return list(
            pool.map(
                _run,
                [
                    {"trace": t, "replacement": replacements.get(t["trace_id"])}
                    for t in traces
                ],
            )
        )


if __name__ == "__main__":
    raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("analyst input exceeds budget")
    job = json.loads(raw)
    print(json.dumps({**analyze(**job), "input_digest": digest(job)}, allow_nan=False))
